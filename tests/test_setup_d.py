"""Setup D: signal timing, whipsaw band, monthly signal, and the switching engine."""

import numpy as np
import pandas as pd
import pytest

from earnings_bot.backtest.switching import buy_and_hold, run, stats
from earnings_bot.signals.setup_d import _hysteresis, signal_ema, signal_monthly_sma

IDX = pd.bdate_range("2026-01-05", periods=6)


def test_hysteresis_band():
    ma = np.full(6, 100.0)
    close = np.array([100.5, 101.5, 100.5, 99.5, 98.5, 100.5])
    assert list(_hysteresis(close, ma, 0.0)) == [1, 1, 1, 0, 0, 1]
    # 1% band: buy only above 101, sell only below 99
    assert list(_hysteresis(close, ma, 0.01)) == [0, 1, 1, 1, 0, 0]


def test_signal_is_cash_during_warmup():
    close = pd.Series(np.linspace(100, 120, 30), index=pd.bdate_range("2026-01-01", periods=30))
    s = signal_ema(close, 20)
    assert (s.iloc[:19] == 0).all() and s.iloc[-1] == 1


def test_monthly_signal_changes_only_after_month_end():
    idx = pd.bdate_range("2025-01-01", "2026-03-31")
    close = pd.Series(np.linspace(100, 130, len(idx)), index=idx)  # steady uptrend
    close[close.index >= "2026-02-10"] = 50.0  # crash mid-February
    s = signal_monthly_sma(close, months=10)
    assert s.loc["2026-02-26"] == 1  # mid-month crash is ignored until the month-end close
    assert s.loc["2026-02-27"] == 0  # decided at the Feb month-end close (executed next open)
    assert (s.loc["2026-03"] == 0).all()


def test_switch_executes_at_next_open():
    px = pd.DataFrame({"open": [100, 100, 110, 121], "close": [100, 105, 115, 121]},
                      index=pd.bdate_range("2026-01-05", periods=4), dtype=float)
    sig = pd.Series([1, 0, 0, 0], index=px.index, dtype=float)  # sell signal at close of day 1
    res = run(px, sig, slippage_bps=0)
    # day 1: invested all day (+5%); day 2: overnight still invested (105 -> 110), then cash
    assert res.ret.iloc[1] == pytest.approx(0.05)
    assert res.ret.iloc[2] == pytest.approx(110 / 105 - 1)
    assert res.ret.iloc[3] == pytest.approx(0.0)
    assert res.switch.sum() == 2  # the initial buy and the sell


def test_cash_earns_tbill_and_slippage_charged():
    px = pd.DataFrame({"open": 100.0, "close": 100.0}, index=IDX)
    sig = pd.Series(0.0, index=IDX)
    res = run(px, sig, cash=pd.Series(0.0002, index=IDX), slippage_bps=5)
    assert res.ret.iloc[1:].tolist() == pytest.approx([0.0002] * 5)
    sig2 = pd.Series([1, 1, 1, 1, 1, 1.0], index=IDX)
    res2 = run(px, sig2, slippage_bps=5)
    assert res2.ret.iloc[1] == pytest.approx(-0.0005)  # buy-in cost on the switch day


def test_stats_on_buy_and_hold():
    px = pd.DataFrame({"open": 100.0, "close": [100.0, 110.0, 99.0, 108.9, 108.9, 108.9]}, index=IDX)
    s = stats(buy_and_hold(px))
    assert s["max_drawdown"] == pytest.approx(-0.1)
    assert s["time_invested"] == 1.0
