"""Cost models: Alpaca bps, IG spread cap and overnight funding."""

import numpy as np
import pandas as pd
import pytest

from earnings_bot.backtest.costs import apply_costs, funding_per_unit

FF = pd.Series(4.0, index=pd.date_range("2026-01-01", "2026-12-31"))  # flat 4% fed funds


def sims(entry=100.0, exit_=110.0, d0="2026-03-02", d1="2026-03-12"):
    return pd.DataFrame([{"filled": True, "entry_price": entry, "exit_price": exit_, "initial_risk": 5.0,
                          "entry_date": pd.Timestamp(d0), "exit_date": pd.Timestamp(d1), "r_multiple": 2.0}])


def test_alpaca_bps_and_stress():
    s = apply_costs(sims(), "alpaca", ff=FF)
    assert s.entry_price[0] == pytest.approx(100.03) and s.exit_price[0] == pytest.approx(110 * 0.9997)
    s2 = apply_costs(sims(), "alpaca", mult=2, ff=FF)
    assert s2.entry_price[0] == pytest.approx(100.06)


def test_ig_spread_is_capped_at_ten_cents_round_trip():
    s = apply_costs(sims(entry=500.0, exit_=500.0, d1="2026-03-02"), "ig", ff=FF)  # same day: no funding
    assert s.entry_price[0] - 500 == pytest.approx(0.05) and 500 - s.exit_price[0] == pytest.approx(0.05)
    s2 = apply_costs(sims(entry=20.0, exit_=20.0, d1="2026-03-02"), "ig", ff=FF)
    assert s2.entry_price[0] - 20 == pytest.approx(0.01)  # 0.05% of $20


def test_ig_funding_per_night():
    nights = 10
    f = funding_per_unit(pd.Series([pd.Timestamp("2026-03-02")]), pd.Series([pd.Timestamp("2026-03-12")]), FF)
    assert f[0] == pytest.approx(nights * (0.04 + 0.034) / 360)
    s = apply_costs(sims(), "ig", ff=FF)
    assert s.funding_per_share[0] == pytest.approx(100 * f[0])
    assert s.r_multiple[0] < 2.0


def test_deflated_sharpe_penalises_many_trials_and_concentration():
    from earnings_bot.backtest.metrics import deflated_sharpe, profit_concentration

    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0.0004, 0.01, 2500))  # ~0.6 annual Sharpe
    one = deflated_sharpe(r, 1, 0.0)
    many = deflated_sharpe(r, 100, 0.03 ** 2)
    assert many["dsr"] < one["dsr"] and many["sr0_daily"] > 0
    assert profit_concentration(pd.Series([100.0] + [1.0] * 19)) == pytest.approx(100 / 119)
