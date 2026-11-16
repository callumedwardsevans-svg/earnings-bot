"""Setup G: signal conditions, next-open entry (rule 4), day-1-low stop, fixed hold."""

import numpy as np
import pandas as pd
import pytest

from earnings_bot.backtest.simulate import simulate
from earnings_bot.indicators import add_indicators
from earnings_bot.signals import setup_g

SESS = pd.bdate_range("2026-01-02", "2026-06-30")
D1 = pd.Timestamp("2026-04-15")
UNI = pd.DataFrame({"symbol": ["AAA"], "sector": ["Tech"], "date_added": [pd.NaT]})


def panel(day1_close_vs_prev=0.02):
    idx = SESS
    close = pd.Series(100.0, index=idx)
    df = pd.DataFrame({"open": close, "high": close + 0.2, "low": close - 0.2, "close": close, "volume": 1e6})
    df.loc[D1, ["open", "high", "low", "close"]] = [101.0, 104.0, 99.5, 100 * (1 + day1_close_vs_prev)]
    return add_indicators(df)


def hist(surprise=8.0):
    return pd.DataFrame([{"symbol": "AAA", "report_date": pd.Timestamp("2026-04-14"), "report_time": "amc",
                          "surprise_pct": surprise}])


def gen(h, px, hold=10, **kw):
    return setup_g.generate(h, {"AAA": px}, SESS, UNI, "2026-01-01", "2026-06-30", hold, **kw)


def test_signal_entry_next_open_stop_day1_low():
    c, f = gen(hist(), panel())
    assert len(c) == 1
    r = c.iloc[0]
    assert r.signal_date == D1 and r.entry_date == pd.Timestamp("2026-04-16")
    assert r.entry_type == "open_market" and r.stop == 99.5 and r.ref_price == pytest.approx(102.0)
    assert np.isnan(r.target) and r.max_hold_days == 10


@pytest.mark.parametrize("kw, reason", [(dict(surprise=3.0), "EPS surprise"), ])
def test_rejections(kw, reason):
    rej = []
    c, _ = gen(hist(**kw), panel(), rejected=rej)
    assert c.empty and reason in rej[0]["reason"]


def test_negative_day1_return_rejected():
    rej = []
    c, _ = gen(hist(), panel(day1_close_vs_prev=-0.01), rejected=rej)
    assert c.empty and "day-1 return" in rej[0]["reason"]


def test_revenue_variants_blocked_without_data():
    with pytest.raises(ValueError):
        gen(hist(), panel(), require_revenue_beat=True)


def test_open_market_fill_and_time_exit_at_close():
    c, _ = gen(hist(), panel())
    px = panel()
    out = simulate(c.iloc[0], px, pd.Timestamp("2026-06-30"), slip=0)
    assert out["entry_price"] == 100.0  # day-2 open
    i0 = px.index.get_loc(pd.Timestamp("2026-04-16"))
    assert out["exit_date"] == px.index[i0 + 10] and out["exit_reason"] == "time exit"
    assert out["r_multiple"] == pytest.approx((100 - 100) / (102 - 99.5))


def test_gap_below_stop_exits_at_open():
    c, _ = gen(hist(), panel())
    px = panel()
    px.loc[pd.Timestamp("2026-04-16"), ["open", "low"]] = [98.0, 97.5]
    out = simulate(c.iloc[0], px, pd.Timestamp("2026-06-30"), slip=0)
    assert out["exit_reason"] == "stop" and out["exit_price"] == 98.0 and out["exit_date"] == pd.Timestamp("2026-04-16")
