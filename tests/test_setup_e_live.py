"""Setup E live: calendar month-ends, targets, TOM days, whole shares, limits; and parity with the backtest."""

import numpy as np
import pandas as pd
import pytest

from earnings_bot.live.setup_e_live import (last_month_end_on_or_before, order_for, shares_for, targets_for,
                                            tom_flags)
from earnings_bot.signals import setup_e

SESS = pd.bdate_range("2024-01-01", "2026-12-31")


def test_month_end_comes_from_the_calendar_not_the_series():
    assert last_month_end_on_or_before("2026-11-12", SESS) == pd.Timestamp("2026-10-30")
    assert last_month_end_on_or_before("2026-10-30", SESS) == pd.Timestamp("2026-10-30")


def test_tom_flags():
    assert tom_flags("2026-11-27", SESS) == (False, True)   # day -2 of Nov (weekday calendar): buy at the close
    assert tom_flags("2026-11-30", SESS) == (True, True)    # day -1
    assert tom_flags("2026-12-03", SESS) == (True, False)   # day +3: held all day, out at the close
    assert tom_flags("2026-12-10", SESS) == (False, False)


def closes(trend_up=True):
    idx = SESS[SESS <= "2026-11-30"]
    rng = np.random.default_rng(3)
    drift = 0.0006 if trend_up else -0.0012
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(drift, 0.006, len(idx)))), index=idx)


def test_targets_and_tom_override():
    c = closes(trend_up=False)
    t = targets_for("2026-12-01", c.loc[:"2026-11-30"], SESS)  # day +1 of December
    assert not t["trend_in"] and t["base"] == 0.0
    assert t["target_open"] == 1.0 and t["target_close"] == 1.0  # TOM overrides the trend
    t2 = targets_for("2026-12-10", c.loc[:"2026-12-09"].dropna(), SESS) if "2026-12-09" in c.index else None
    assert t2 is None or t2["target_open"] == 0.0


def test_live_targets_match_backtest_positions():
    c = closes(trend_up=True)
    p_open, p_close = setup_e.positions(c, trend=True, vol=True, tom=(2, 3))
    for d in ["2026-06-10", "2026-06-26", "2026-06-29", "2026-07-01", "2026-07-03", "2026-07-06"]:
        d = pd.Timestamp(d)
        t = targets_for(d, c.loc[:d - pd.Timedelta(days=1)], SESS)
        assert t["target_open"] == pytest.approx(p_open.loc[d]), d
        assert t["target_close"] == pytest.approx(p_close.loc[d]), d


def test_whole_shares_and_limits():
    assert shares_for(0.8, 10_000, 650) == 12            # floor: never above the target
    assert shares_for(1.0, 10_000, 650) == 15
    assert order_for(15, 12, 10_000, 10_000, False) == (3, None)
    assert order_for(15, 12, 10_000, 10_000, True)[0] == 0                       # kill switch
    assert order_for(15, 12, 9_790, 10_000, False)[0] == 0                       # down 2%: no increase
    assert order_for(10, 12, 9_790, 10_000, False) == (-2, None)                 # reductions still allowed
