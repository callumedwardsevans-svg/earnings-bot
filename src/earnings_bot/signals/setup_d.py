"""Setup D: index trend filter. Hold the index while it's above its moving average, else cash.

Signal at each daily close; the switch happens at the next session's open. Variants:

* EMA length N in {20, 50, 100, 200} on daily closes
* 10-month simple moving average on month-end closes (signal changes only at month ends)
* Whipsaw band: switch only when the close is at least ``band`` (1%) beyond the average.
  While in cash, buy when close > MA*(1+band); while invested, sell when close < MA*(1-band).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from earnings_bot.indicators import ema


def _hysteresis(close: np.ndarray, ma: np.ndarray, band: float) -> np.ndarray:
    """1 = invested, 0 = cash, decided at each close. NaN MA -> cash."""
    out = np.zeros(len(close))
    state = 0.0
    for i, (c, m) in enumerate(zip(close, ma)):
        if np.isnan(m):
            state = 0.0
        elif state == 0.0 and c > m * (1 + band):
            state = 1.0
        elif state == 1.0 and c < m * (1 - band):
            state = 0.0
        out[i] = state
    return out


def signal_ema(close: pd.Series, n: int, band: float = 0.0) -> pd.Series:
    return pd.Series(_hysteresis(close.values, ema(close, n).values, band), index=close.index, name=f"ema{n}")


def signal_monthly_sma(close: pd.Series, months: int = 10, band: float = 0.0) -> pd.Series:
    """Signal from month-end closes vs their N-month SMA, held until the next month end."""
    month_end = close.groupby(close.index.to_period("M")).tail(1)
    ma = month_end.rolling(months).mean()
    sig_m = pd.Series(_hysteresis(month_end.values, ma.values, band), index=month_end.index)
    return sig_m.reindex(close.index).ffill().fillna(0.0).rename(f"sma{months}m")


def variants(close: pd.Series) -> dict[str, pd.Series]:
    out = {}
    for band in (0.0, 0.01):
        tag = "" if band == 0 else " +1% band"
        for n in (20, 50, 100, 200):
            out[f"EMA {n}{tag}"] = signal_ema(close, n, band)
        out[f"10-month SMA{tag}"] = signal_monthly_sma(close, 10, band)
    return out
