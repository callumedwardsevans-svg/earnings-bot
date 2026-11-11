"""Earnings normalisation, the Alpha Vantage budget, and the price-cache merge."""

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from earnings_bot.data import earnings
from earnings_bot.data.earnings import AlphaVantageBudget, RateLimited, normalize_av, normalize_finnhub, surprise_pct
from earnings_bot.data.prices import merge_bars


def test_surprise_pct():
    assert surprise_pct(1.10, 1.00) == pytest.approx(10.0)
    assert surprise_pct(-0.90, -1.00) == pytest.approx(10.0)  # smaller loss than expected is a beat
    assert math.isnan(surprise_pct(0.05, 0.0))  # estimate ~0: meaningless, so NaN
    assert math.isnan(surprise_pct(np.nan, 1.0))


def test_normalize_av_maps_timing_and_missing_values():
    raw = {
        "quarterlyEarnings": [
            {"fiscalDateEnding": "2026-07-31", "reportedDate": "2026-08-26", "reportedEPS": "2.22",
             "estimatedEPS": "2.09", "reportTime": "post-market"},
            {"fiscalDateEnding": "2026-04-30", "reportedDate": "2026-05-20", "reportedEPS": "None",
             "estimatedEPS": "1.50", "reportTime": "pre-market"},
            {"fiscalDateEnding": "2026-01-31", "reportedDate": "2026-02-25", "reportedEPS": "1.0",
             "estimatedEPS": "1.0", "reportTime": ""},
        ]
    }
    df = normalize_av("NVDA", raw)
    assert list(df.report_time) == ["amc", "bmo", "unknown"]
    assert df.surprise_pct.iloc[0] == pytest.approx((2.22 - 2.09) / 2.09 * 100)
    assert np.isnan(df.eps_actual.iloc[1])
    assert df.report_date.dtype.kind == "M"


def test_normalize_finnhub():
    rows = [
        {"symbol": "ABBV", "date": "2026-10-30", "hour": "bmo", "epsEstimate": 3.823, "epsActual": 3.82,
         "revenueEstimate": 1.7e10, "revenueActual": 1.74e10},
        {"symbol": "XYZ", "date": "2026-11-20", "hour": "", "epsEstimate": None, "epsActual": None},
    ]
    df = normalize_finnhub(rows)
    assert list(df.report_time) == ["bmo", "unknown"]
    assert df.revenue_actual.iloc[0] == 1.74e10


def test_budget_enforced(tmp_path):
    b = AlphaVantageBudget(limit=2, path=tmp_path / "u.json", today=date(2026, 11, 11))
    b.spend()
    b.spend()
    assert b.remaining() == 0
    with pytest.raises(RateLimited):
        b.spend()
    # new day, fresh budget
    assert AlphaVantageBudget(limit=2, path=tmp_path / "u.json", today=date(2026, 11, 12)).remaining() == 2


def test_cached_av_symbol_never_spends_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(earnings, "AV_DIR", tmp_path)
    (tmp_path / "EARNINGS_NVDA.json").write_text('{"quarterlyEarnings": []}')
    b = AlphaVantageBudget(limit=0, path=tmp_path / "u.json")

    class NoHTTP:
        def get(self, *a, **k):
            raise AssertionError("should not hit the network")

    assert earnings.fetch_av_earnings("NVDA", "key", b, session=NoHTTP()) == {"quarterlyEarnings": []}


def test_av_rate_limit_response_exhausts_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(earnings, "AV_DIR", tmp_path)
    b = AlphaVantageBudget(limit=25, path=tmp_path / "u.json")

    class Resp:
        def raise_for_status(self): ...
        def json(self):
            return {"Information": "We have detected your API key as SECRETKEY123 and our standard "
                                   "API rate limit is 25 requests per day."}

    class FakeHTTP:
        def get(self, *a, **k):
            return Resp()

    with pytest.raises(RateLimited) as exc:
        earnings.fetch_av_earnings("AAPL", "SECRETKEY123", b, session=FakeHTTP())
    assert "SECRETKEY123" not in str(exc.value)  # AV echoes the key; it must never reach logs
    assert b.remaining() == 0
    assert not (tmp_path / "EARNINGS_AAPL.json").exists()


def _bars(dates, close):
    return pd.DataFrame({"close": close}, index=pd.DatetimeIndex(dates))


def test_merge_bars_appends_without_duplicates():
    cached = _bars(["2026-11-02", "2026-11-03", "2026-11-04"], [10.0, 11.0, 12.0])
    new = _bars(["2026-11-04", "2026-11-05"], [12.0, 13.0])
    merged, refetch = merge_bars(cached, new)
    assert not refetch
    assert list(merged.close) == [10.0, 11.0, 12.0, 13.0]


def test_merge_bars_detects_new_adjustment():
    cached = _bars(["2026-11-03", "2026-11-04"], [100.0, 102.0])
    new = _bars(["2026-11-04", "2026-11-05"], [51.0, 52.0])  # 2:1 split re-based history
    _, refetch = merge_bars(cached, new)
    assert refetch


def test_http_errors_do_not_leak_key_in_url(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(earnings, "AV_DIR", tmp_path)

    class Resp:
        status_code = 500

        def raise_for_status(self):
            raise requests.HTTPError("500 Server Error for url: https://x/query?apikey=SECRETKEY123")

    class FakeHTTP:
        def get(self, *a, **k):
            return Resp()

    b = AlphaVantageBudget(limit=25, path=tmp_path / "u.json")
    with pytest.raises(RuntimeError) as exc:
        earnings.fetch_av_earnings("AAPL", "SECRETKEY123", b, session=FakeHTTP())
    assert "SECRETKEY123" not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__
