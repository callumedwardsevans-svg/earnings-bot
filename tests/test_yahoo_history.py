"""Yahoo timing classification and the AV/Yahoo reconciliation."""

import numpy as np
import pandas as pd
import pytest

from earnings_bot.data.earnings import _frame
from earnings_bot.data.history import _reconcile, combine
from earnings_bot.data.yahoo import classify_time, normalize_yahoo

NY = "America/New_York"


@pytest.mark.parametrize(
    "hhmm, expected",
    [("06:00", "bmo"), ("09:29", "bmo"), ("09:30", "dmh"), ("12:00", "dmh"), ("16:00", "amc"),
     ("21:00", "amc"), ("00:00", "unknown"), ("01:00", "unknown"), ("04:00", "bmo")],
)
def test_classify_time(hhmm, expected):
    assert classify_time(pd.Timestamp(f"2026-11-18 {hhmm}", tz=NY)) == expected


def test_normalize_yahoo_drops_upcoming_and_converts_tz():
    raw = pd.DataFrame(
        {
            "Earnings Date": pd.to_datetime(
                ["2026-11-17 16:00", "2026-08-26 16:00", "2026-05-20 21:30"]
            ).tz_localize(NY),
            "EPS Estimate": [2.53, 2.09, 1.77],
            "Reported EPS": [np.nan, 2.22, 1.87],  # first row not reported yet
            "Surprise(%)": [np.nan, 6.16, 5.54],
        }
    )
    df = normalize_yahoo("NVDA", raw)
    assert list(df.report_date) == [pd.Timestamp("2026-05-20"), pd.Timestamp("2026-08-26")]
    assert list(df.report_time) == ["amc", "amc"]
    assert df.report_date.dt.tz is None


@pytest.mark.parametrize(
    "y, a, expected",
    [
        ("amc", "amc", ("amc", "agree")),
        ("bmo", "amc", ("conflict", "conflict")),
        ("amc", np.nan, ("amc", "yahoo only")),
        ("unknown", "bmo", ("bmo", "av only")),
        ("dmh", "unknown", ("dmh", "yahoo only")),
        ("unknown", np.nan, ("unknown", "none")),
    ],
)
def test_reconcile(y, a, expected):
    assert _reconcile(y, a) == expected


def _rows(source, items):
    return _frame(
        [
            {"symbol": s, "report_date": d, "report_time": t, "report_time_raw": "", "fiscal_date_ending": None,
             "eps_actual": act, "eps_estimate": est, "surprise_pct": np.nan, "revenue_actual": np.nan,
             "revenue_estimate": np.nan, "source": source}
            for s, d, t, act, est in items
        ]
    )


def test_combine_matches_exact_near_and_unmatched():
    y = _rows("yahoo", [
        ("AAA", "2026-08-01", "amc", 1.10, 1.00),   # exact match, agree
        ("AAA", "2026-05-02", "bmo", 0.90, 1.00),   # AV dated a day earlier, conflicting timing
        ("BBB", "2026-07-15", "amc", 2.00, np.nan),  # Yahoo lacks the estimate
    ])
    a = _rows("alphavantage", [
        ("AAA", "2026-08-01", "amc", 1.10, 1.00),
        ("AAA", "2026-05-01", "amc", 0.90, 1.00),
        ("BBB", "2026-07-15", "unknown", 2.00, 1.60),
        ("CCC", "2026-06-01", "bmo", 0.50, 0.40),   # AV only
    ])
    df = combine(y, a).set_index(["symbol", "report_date"])
    assert df.loc[("AAA", pd.Timestamp("2026-08-01")), "timing_source"] == "agree"
    assert df.loc[("AAA", pd.Timestamp("2026-05-02")), "report_time"] == "conflict"
    bbb = df.loc[("BBB", pd.Timestamp("2026-07-15"))]
    assert bbb.report_time == "amc" and bbb.eps_estimate == 1.60  # filled from AV
    assert bbb.surprise_pct == pytest.approx(25.0)
    ccc = df.loc[("CCC", pd.Timestamp("2026-06-01"))]
    assert ccc.source == "av" and ccc.timing_source == "av only"
    assert len(df) == 4  # no duplicates from the near match
