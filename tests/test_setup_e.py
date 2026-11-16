"""Setup E: TOM window timing, trend timing, no same-bar fills, and the allocation backtester."""

import numpy as np
import pandas as pd
import pytest

from earnings_bot.backtest.allocation import run
from earnings_bot.signals.setup_e import month_positions, positions, tom_masks, trend_signal

IDX = pd.bdate_range("2026-01-01", "2026-03-31")


def test_month_positions():
    from_end, from_start = month_positions(IDX)
    s = pd.DataFrame({"end": from_end, "start": from_start}, index=IDX)
    assert s.loc["2026-01-30", "end"] == -1 and s.loc["2026-01-29", "end"] == -2
    assert s.loc["2026-02-02", "start"] == 1 and s.loc["2026-02-04", "start"] == 3


def test_tom_window_minus2_plus3():
    full, overnight = tom_masks(IDX, 2, 3)
    f = pd.Series(full, index=IDX)
    o = pd.Series(overnight, index=IDX)
    # entered at the close of Jan 29 (day -2): not held during Jan 29 itself, held overnight
    assert not f["2026-01-29"] and o["2026-01-29"]
    # held through Jan 30 (-1) and Feb 2-4 (+1..+3); exit at the close of Feb 4
    assert f["2026-01-30"] and f["2026-02-02"] and f["2026-02-04"] and not o["2026-02-04"]
    assert not f["2026-02-05"]
    full3, _ = tom_masks(IDX, 3, 3)
    assert pd.Series(full3, index=IDX)["2026-01-29"]  # -3..+3 also holds day -2


def test_trend_decided_at_month_end_and_filled_next_open():
    idx = pd.bdate_range("2025-01-01", "2026-03-31")
    close = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    close[close.index >= "2026-02-16"] = 50.0  # crash mid-February
    sig = trend_signal(close)
    assert sig["2026-02-26"] == 1 and sig["2026-02-27"] == 0  # flips at the Feb month-end close
    p_open, p_close = positions(close, trend=True, vol=False, tom=None)
    assert p_open["2026-02-27"] == 1 and p_open["2026-03-02"] == 0  # executed at the next open


def test_tom_exit_close_uses_previous_close_target():
    idx = pd.bdate_range("2025-01-01", "2026-03-31")
    close = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    p_open, p_close = positions(close, trend=False, vol=False, tom=(2, 3))
    assert p_close["2026-02-04"] == 0 and p_open["2026-02-04"] == 1  # +3: held all day, out at the close
    assert p_close["2026-01-29"] == 1 and p_open["2026-01-29"] == 0  # -2: bought at the close


def test_allocation_returns_costs_and_cash():
    idx = pd.bdate_range("2026-03-02", periods=3)  # Mon-Wed
    px = pd.DataFrame({"open": [100.0, 102.0, 101.0], "close": [101.0, 101.0, 103.0]}, index=idx)
    p_open = pd.Series([0.0, 1.0, 1.0], index=idx)
    p_close = pd.Series([0.0, 1.0, 0.0], index=idx)
    cash = pd.Series(3.6, index=pd.date_range("2026-03-01", "2026-03-05"))  # 3.6% -> 0.01%/day
    res = run(px, p_open, p_close, cash, model="alpaca", bps=2.0)
    # day 2: in cash overnight (+1 day of interest), buy at open 102, close 101
    assert res.ret.iloc[1] == pytest.approx(101 / 102 - 1 + 0.036 / 360 - 0.0002)
    # day 3: held overnight 101 -> 101, then intraday 101 -> 103, sold at the close
    assert res.ret.iloc[2] == pytest.approx(103 / 101 - 1 - 0.0002)


def test_ig_funding_charged_on_overnight_exposure():
    idx = pd.DatetimeIndex(["2026-03-06", "2026-03-09"])  # Fri -> Mon: 3 nights
    px = pd.DataFrame({"open": [100.0, 100.0], "close": [100.0, 100.0]}, index=idx)
    one = pd.Series(1.0, index=idx)
    ff = pd.Series(4.0, index=pd.date_range("2026-03-01", "2026-03-10"))
    lvl = pd.Series(5000.0, index=pd.date_range("2026-03-01", "2026-03-10"))
    res = run(px, one, one, ff * 0, model="ig", index_level=lvl, index_spread_pts=0.5, fed_funds=ff)
    assert res.funding.iloc[1] == pytest.approx(3 * (0.04 + 0.034) / 360)
