"""Sizing and limit checks (these gate every order, backtest and live)."""

import pytest

from earnings_bot.config import RiskLimits
from earnings_bot.risk import Sizing, check_limits, daily_loss_hit, size_position

L = RiskLimits()


def test_risk_rule_sizes_position():
    # $10k equity -> $75 risk; $2/share risk -> 37 shares ($1,850 > 15% cap of $1,500!)
    sz = size_position(10_000, entry=50.0, stop=48.0, cash=10_000, limits=L)
    assert isinstance(sz, Sizing)
    assert sz.limited_by == "max position" and sz.shares == 30  # 1,500 / 50


def test_risk_limited_when_stop_is_wide():
    sz = size_position(10_000, entry=50.0, stop=40.0, cash=10_000, limits=L)
    assert sz.limited_by == "risk" and sz.shares == 7  # 75 / 10
    assert sz.risk_usd <= 75


def test_cash_limits_size():
    sz = size_position(10_000, entry=50.0, stop=40.0, cash=200, limits=L)
    assert sz.limited_by == "cash" and sz.shares == 4


def test_expensive_stock_cannot_be_bought():
    reason = size_position(10_000, entry=1_800.0, stop=1_750.0, cash=10_000, limits=L)
    assert isinstance(reason, str) and "too small" in reason


@pytest.mark.parametrize("stop", [50.0, 51.0])
def test_stop_must_be_below_entry(stop):
    assert size_position(10_000, 50.0, stop, 10_000, L) == "stop not below entry"


def test_limits():
    assert check_limits("Tech", [], False, limits=L) is None
    assert "max 5" in check_limits("Tech", ["A", "B", "C", "D", "E"], False, limits=L)
    assert "max 2 positions in Tech" in check_limits("Tech", ["Tech", "Tech"], False, limits=L)
    assert "daily loss" in check_limits("Tech", [], True, limits=L)
    assert "kill switch" in check_limits("Tech", [], False, kill_switch=True, limits=L)


def test_daily_loss_threshold():
    assert daily_loss_hit(9_800, 10_000, L)
    assert not daily_loss_hit(9_801, 10_000, L)
