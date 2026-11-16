"""Setup E live (paper): SPY combined = month-end 200-day SMA trend x vol target + TOM -2..+3.

Same rules as the backtest (signals/setup_e.py), executed with three daily jobs:

* morning (pre-open): exposure for today's session = 1.0 on a TOM full day, else the base target
  decided at yesterday's close -> market-on-open order for the change in whole shares.
* close (~15:35 New York, before the 15:50 market-on-close cut-off): exposure to hold overnight =
  1.0 while the TOM window holds overnight (days -2..+2), else yesterday's base target -> a
  market-on-close order if that differs from the position (only on TOM entry/exit days).
* evening: settle fills, log the day, compare with a frictionless backtest shadow, write a report.

Base target at a close: trend (close > 200-day SMA at the most recent *calendar* month-end
session; a truncated price series can't tell month-ends) x min(1, 0.12 / sigma20).

Differences from the backtest (by necessity): whole shares (SPY ~ $650 -> one share ~ 6.5% of a
$10k account), so exposure moves in steps; paper cash earns 0%, not T-bills.

Limits: paper-only guard; kill switch (STOP file) -> no orders; exposure <= 1.0 (no leverage);
if equity is down 2% on the day, only orders that reduce exposure are sent.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from earnings_bot.config import LIVE_E_MAX_EXPOSURE, RISK
from earnings_bot.signals.setup_e import SMA_DAYS, VOL_DAYS, VOL_TARGET, tom_masks


def last_month_end_on_or_before(d, sessions: pd.DatetimeIndex) -> pd.Timestamp:
    """Most recent session <= d whose next calendar session is in a different month."""
    p = sessions.to_period("M")
    is_month_end = np.r_[p[:-1] != p[1:], False]
    return sessions[is_month_end & (sessions <= pd.Timestamp(d))][-1]


def base_target(closes: pd.Series, sessions: pd.DatetimeIndex) -> dict:
    """Base exposure decided at the last close in ``closes`` (trend x vol target)."""
    last = closes.index[-1]
    me = last_month_end_on_or_before(last, sessions)
    sma = closes.rolling(SMA_DAYS).mean()
    trend_in = bool(me in closes.index and closes.loc[me] > sma.loc[me]) if pd.notna(sma.get(me, np.nan)) else False
    sigma = float(closes.pct_change().iloc[-VOL_DAYS:].std() * np.sqrt(252))
    scale = min(1.0, VOL_TARGET / sigma) if sigma > 0 else 0.0
    return {"as_of": last, "trend_month_end": me, "trend_in": trend_in,
            "sma200_at_month_end": float(sma.loc[me]) if me in sma.index else np.nan,
            "close_at_month_end": float(closes.loc[me]) if me in closes.index else np.nan,
            "sigma20": sigma, "vol_scale": scale, "base": (1.0 if trend_in else 0.0) * scale}


def tom_flags(day, sessions: pd.DatetimeIndex) -> tuple[bool, bool]:
    """(held through the whole session, held overnight after the close) for the TOM -2..+3 window."""
    d = pd.Timestamp(day)
    win = sessions[(sessions >= d - pd.Timedelta(days=62)) & (sessions <= d + pd.Timedelta(days=62))]
    full, overnight = tom_masks(win, 2, 3)
    i = win.get_loc(d)
    return bool(full[i]), bool(overnight[i])


def targets_for(day, closes_to_prev: pd.Series, sessions: pd.DatetimeIndex) -> dict:
    """Exposure for ``day``'s session (open) and overnight after its close, from yesterday's base."""
    b = base_target(closes_to_prev, sessions)
    full_day, overnight = tom_flags(day, sessions)
    cap = LIVE_E_MAX_EXPOSURE
    return {**b, "day": pd.Timestamp(day), "tom_full_day": full_day, "tom_overnight": overnight,
            "target_open": min(cap, 1.0 if full_day else b["base"]),
            "target_close": min(cap, 1.0 if overnight else b["base"])}


def shares_for(exposure: float, equity: float, price: float) -> int:
    """Whole shares, rounded down so exposure never exceeds the target (no leverage)."""
    if price <= 0 or equity <= 0:
        return 0
    return max(0, math.floor(exposure * equity / price + 1e-9))


def order_for(target_shares: int, current_shares: int, equity: float, last_equity: float,
              kill_switch: bool) -> tuple[int, str | None]:
    """Signed share change to send, or 0 with the reason it was held back."""
    delta = target_shares - current_shares
    if delta == 0:
        return 0, "no change"
    if kill_switch:
        return 0, "kill switch (STOP file present)"
    if delta > 0 and equity <= last_equity * (1 - RISK.daily_loss_limit_pct):
        return 0, f"daily loss limit ({RISK.daily_loss_limit_pct:.0%}): no increases today"
    return delta, None
