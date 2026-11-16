"""Setup E: SPY/QQQ trend filter + volatility target + turn-of-the-month (TOM) tilt.

Rules (research addendum, Nov 2026), tested as written; no tunable parameters:

* Trend, checked at each month-end close: invested if close > 200-day SMA, else cash (T-bills).
* Exposure while invested: min(1, 0.12 / sigma20), sigma20 = annualised 20-day realised vol of
  daily returns. Interpretation fixed in advance: recomputed at every daily close.
* TOM: from the close of trading day -2 before month-end to the close of trading day +3 of the
  new month, hold 1.0x regardless of trend and vol target.
* Execution: targets decided at a close are filled at the next open. TOM entries/exits are filled
  at the stated closes (the calendar is known in advance). At the TOM exit close the position
  goes to the base target decided at the *previous* close; anything decided at that same close
  waits for the next open (no same-bar signal and fill).

Positions are expressed as two daily series of exposure (fraction of equity):
``p_open[t]`` held from the open to the close of day t, and ``p_close[t]`` held from the close of
day t to the next open.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SMA_DAYS = 200
VOL_DAYS = 20
VOL_TARGET = 0.12


def month_positions(index: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """(from_end, from_start): -1 = last session of the month, -2 = second-to-last ...;
    +1 = first session of the month, +2 = second ..."""
    m = index.to_period("M")
    s = pd.Series(1, index=index).groupby(m)
    from_start = s.cumcount().values + 1
    from_end = -(s.cumcount(ascending=False).values + 1)
    return from_end, from_start


def tom_masks(index: pd.DatetimeIndex, pre: int = 2, post: int = 3):
    """Masks for a TOM window held from the close of day -pre to the close of day +post.

    full_day[t]: TOM is held through the whole session t (days -(pre-1)..-1 and +1..+post).
    hold_overnight[t]: TOM is held from the close of t to the next open (days -pre..-1, +1..+post-1).
    """
    from_end, from_start = month_positions(index)
    full_day = ((from_end >= -(pre - 1)) & (from_end <= -1)) | ((from_start >= 1) & (from_start <= post))
    hold_overnight = ((from_end >= -pre) & (from_end <= -1)) | ((from_start >= 1) & (from_start <= post - 1))
    return full_day, hold_overnight


def trend_signal(close: pd.Series) -> pd.Series:
    """1/0 decided at each month-end close (close vs 200-day SMA), held until the next month end."""
    sma = close.rolling(SMA_DAYS).mean()
    from_end, _ = month_positions(close.index)
    at_month_end = pd.Series(from_end == -1, index=close.index)
    sig = pd.Series(np.where(close > sma, 1.0, 0.0), index=close.index).where(at_month_end & sma.notna())
    return sig.ffill().fillna(0.0)


def vol_scale(close: pd.Series) -> pd.Series:
    sigma = close.pct_change().rolling(VOL_DAYS).std() * np.sqrt(252)
    return np.minimum(1.0, VOL_TARGET / sigma).fillna(0.0)


def positions(close: pd.Series, trend: bool, vol: bool, tom: tuple[int, int] | None) -> tuple[pd.Series, pd.Series]:
    """Exposure held intraday (p_open) and overnight (p_close) for one variant."""
    idx = close.index
    if trend:
        base = trend_signal(close) * (vol_scale(close) if vol else 1.0)
    else:
        base = pd.Series(0.0, index=idx)  # TOM-only: cash outside the window
    base_prev = base.shift(1).fillna(0.0)  # decided at the previous close -> held from today's open
    p_open = base_prev.copy()
    p_close = base_prev.copy()  # no close trades outside TOM: hold the open position overnight
    if tom is not None:
        full_day, hold_on = tom_masks(idx, *tom)
        p_open[full_day] = 1.0
        p_close[hold_on] = 1.0
    return p_open, p_close


VARIANTS = {
    "trend only": dict(trend=True, vol=False, tom=None),
    "trend + vol target": dict(trend=True, vol=True, tom=None),
    "TOM only (-2..+3)": dict(trend=False, vol=False, tom=(2, 3)),
    "TOM only (-3..+3)": dict(trend=False, vol=False, tom=(3, 3)),
    "combined (trend + vol + TOM -2..+3)": dict(trend=True, vol=True, tom=(2, 3)),
}
