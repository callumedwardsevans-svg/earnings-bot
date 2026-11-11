"""Position sizing and portfolio limit checks, shared by the backtest and the live loop.

Every check returns a reason string when it blocks, so skipped signals can be logged.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from earnings_bot.config import RISK, RiskLimits


@dataclass(frozen=True)
class Sizing:
    shares: int
    risk_usd: float
    position_usd: float
    limited_by: str  # "risk" | "max position" | "cash"


def size_position(equity: float, entry: float, stop: float, cash: float,
                  limits: RiskLimits = RISK) -> Sizing | str:
    """Whole-share size from the 0.75% risk rule, capped by 15% of equity and by cash.

    Returns a Sizing, or a reason string if no valid position is possible.
    """
    if not (entry > 0 and math.isfinite(entry) and math.isfinite(stop)):
        return "invalid prices"
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return "stop not below entry"
    caps = {
        "risk": equity * limits.risk_per_trade_pct / risk_per_share,
        "max position": equity * limits.max_position_pct / entry,
        "cash": max(cash, 0.0) / entry,
    }
    limited_by = min(caps, key=caps.get)
    shares = math.floor(caps[limited_by])
    if shares < 1:
        return f"position too small (< 1 share; limited by {limited_by})"
    return Sizing(shares, shares * risk_per_share, shares * entry, limited_by)


def check_limits(
    sector: str,
    open_sectors: Iterable[str],
    daily_loss_hit: bool,
    kill_switch: bool = False,
    limits: RiskLimits = RISK,
) -> str | None:
    """Portfolio-level checks before a new entry. None means OK."""
    if kill_switch:
        return "kill switch (STOP file present)"
    if daily_loss_hit:
        return f"daily loss limit ({limits.daily_loss_limit_pct:.0%}) hit"
    open_sectors = list(open_sectors)
    if len(open_sectors) >= limits.max_open_positions:
        return f"max {limits.max_open_positions} open positions"
    if open_sectors.count(sector) >= limits.max_positions_per_sector:
        return f"max {limits.max_positions_per_sector} positions in {sector}"
    return None


def daily_loss_hit(equity_now: float, equity_prev_close: float, limits: RiskLimits = RISK) -> bool:
    return equity_now <= equity_prev_close * (1 - limits.daily_loss_limit_pct)


def kill_switch_active(limits: RiskLimits = RISK) -> bool:
    return limits.kill_switch_file.exists()
