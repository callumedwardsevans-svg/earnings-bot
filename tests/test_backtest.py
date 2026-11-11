"""Fill/exit rules, portfolio limits, and no-lookahead checks on tiny synthetic data."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from earnings_bot.backtest import portfolio
from earnings_bot.backtest.simulate import simulate, simulate_all
from earnings_bot.indicators import add_indicators
from earnings_bot.signals import CANDIDATE_COLUMNS

DAYS = pd.bdate_range("2026-01-05", periods=40)


def bars(rows=None, base=100.0):
    df = pd.DataFrame({"open": base, "high": base + 1, "low": base - 1, "close": base, "volume": 1e6,
                       "atr": 2.0}, index=DAYS)
    for d, vals in (rows or {}).items():
        for k, v in vals.items():
            df.loc[pd.Timestamp(d), k] = v
    return df


def cand(**kw):
    base = dict(setup="A", variant="t", symbol="X", sector="Tech", date_added=pd.NaT,
                signal_date=DAYS[0], entry_date=DAYS[1], entry_type="open_limit", ref_price=100.5,
                stop=96.0, target=np.nan, atr=2.0, exit_by=pd.NaT, max_hold_days=20, trail=False,
                eps_surprise_pct=10.0, gap_pct=5.0, rank=10.0, notes="")
    base.update(kw)
    return SimpleNamespace(**base)


END = DAYS[-1]


def test_limit_not_reached_means_no_fill():
    df = bars({DAYS[1]: {"open": 103, "low": 102, "high": 104}})
    assert simulate(cand(), df, END, slip=0)["fill_reason"] == "limit not reached"


def test_limit_fill_at_open_or_limit():
    assert simulate(cand(), bars({DAYS[1]: {"open": 99.0}}), END, slip=0)["entry_price"] == 99.0
    df = bars({DAYS[1]: {"open": 102, "low": 100.0, "high": 103}})
    assert simulate(cand(), df, END, slip=0)["entry_price"] == 100.5


def test_slippage_applied_both_ways():
    out = simulate(cand(max_hold_days=1), bars(), END, slip=0.0005)
    assert out["entry_price"] == pytest.approx(100 * 1.0005)
    assert out["exit_price"] == pytest.approx(100 * 0.9995)
    assert out["exit_reason"] == "time exit"


def test_stop_gap_fills_at_open():
    df = bars({DAYS[3]: {"open": 90, "low": 89, "high": 91, "close": 90}})
    out = simulate(cand(), df, END, slip=0)
    assert out["exit_reason"] == "stop" and out["exit_price"] == 90 and out["exit_date"] == DAYS[3]


def test_stop_and_target_same_bar_assumes_stop():
    df = bars({DAYS[2]: {"low": 95, "high": 120}})
    out = simulate(cand(target=110.0), df, END, slip=0)
    assert out["exit_reason"] == "stop"


def test_target_hit():
    df = bars({DAYS[4]: {"high": 115}})
    out = simulate(cand(target=110.0), df, END, slip=0)
    assert out["exit_reason"] == "target" and out["exit_price"] == 110.0
    assert out["r_multiple"] == pytest.approx((110 - 100) / (100.5 - 96))  # R on planned risk


def test_flat_before_next_report():
    out = simulate(cand(exit_by=DAYS[5]), bars(), END, slip=0)
    assert out["exit_reason"] == "flat before report" and out["exit_date"] == DAYS[5]


def test_time_exit_on_20th_session_after_entry():
    out = simulate(cand(), bars(), END, slip=0)
    assert out["exit_date"] == DAYS[1 + 20]


def test_trailing_stop_ratchets_after_1r():
    rows = {DAYS[2]: {"high": 106, "close": 105}, DAYS[3]: {"open": 105, "high": 105.5, "low": 101, "close": 101.5}}
    out = simulate(cand(trail=True), bars(rows), END, slip=0)
    # 1R = 100.5 - 96 = 4.5 -> activates at 104.5; trail = 106 - 2*2 = 102, hit on DAYS[3]
    assert out["exit_reason"] == "trailing stop" and out["exit_price"] == 102 and out["exit_date"] == DAYS[3]


def test_indicators_are_causal():
    rng = np.random.default_rng(0)
    close = pd.Series(100 + rng.normal(0, 1, 120).cumsum(), index=pd.bdate_range("2026-01-01", periods=120))
    df = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1e6})
    full = add_indicators(df)
    cut = add_indicators(df.iloc[:80])
    cols = ["ema", "atr", "adv", "vol_avg_prior"]
    pd.testing.assert_frame_equal(full[cols].iloc[:80], cut[cols])  # future rows change nothing


def _sims(n, sector="Tech"):
    rows = [{**vars(cand(symbol=f"S{i}", sector=sector, rank=float(n - i))), "filled": True, "fill_reason": "",
             "entry_price": 100.0, "exit_date": DAYS[10], "exit_price": 101.0, "exit_reason": "time exit",
             "r_multiple": 0.25, "initial_risk": 4.0} for i in range(n)]
    return pd.DataFrame(rows)


def test_portfolio_enforces_sector_and_position_limits():
    sims = _sims(4)
    px = {s: bars() for s in sims.symbol}
    trades, skipped, curve = portfolio.run(sims, px, DAYS)
    assert len(trades) == 2  # max 2 per sector
    assert set(skipped.reason) == {"max 2 positions in Tech"}
    assert list(trades.ticker) == ["S0", "S1"]  # highest rank first


def test_portfolio_max_five_positions_and_columns():
    sims = _sims(7)
    sims["sector"] = [f"Sec{i}" for i in range(7)]
    trades, skipped, curve = portfolio.run(sims, {s: bars() for s in sims.symbol}, DAYS)
    assert len(trades) == 5 and (skipped.reason == "max 5 open positions").sum() == 2
    assert list(trades.columns) == portfolio.JOURNAL_COLUMNS
    assert curve.equity.iloc[-1] == pytest.approx(10_000 + trades.pnl_usd.sum())


def test_candidate_columns_match_simulator_inputs():
    assert set(vars(cand())) == set(CANDIDATE_COLUMNS)


def test_r_multiple_uses_planned_risk_when_fill_is_below_limit():
    # opens at 96.5, just above the 96 stop: actual risk 0.5, planned 4.5
    df = bars({DAYS[1]: {"open": 96.5, "low": 96.2, "high": 97}, DAYS[2]: {"high": 120}})
    out = simulate(cand(target=110.0), df, END, slip=0)
    assert out["r_multiple"] == pytest.approx((110 - 96.5) / 4.5)  # 3.0R, not 27R
