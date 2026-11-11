"""Causal indicators on daily bars. Every value at row t uses only rows <= t."""

from __future__ import annotations

import pandas as pd


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ATR."""
    prev_close = df.close.shift(1)
    tr = pd.concat([df.high - df.low, (df.high - prev_close).abs(), (df.low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def add_indicators(df: pd.DataFrame, ema_period: int = 50, atr_period: int = 14, window: int = 20,
                   ema_rising_lookback: int = 5) -> pd.DataFrame:
    out = df.copy()
    out["ema"] = ema(out.close, ema_period)
    out["ema_rising"] = out.ema > out.ema.shift(ema_rising_lookback)
    out["atr"] = atr(out, atr_period)
    out["adv"] = (out.close * out.volume).rolling(window).mean()  # includes today
    out["vol_avg_prior"] = out.volume.shift(1).rolling(window).mean()  # excludes today
    out["prev_close"] = out.close.shift(1)
    return out
