"""Backtest for a single asset switched between invested (1) and cash (0).

The signal ``s[t]`` is decided at the close of day t and executed at the open of t+1:

* overnight (close t -> open t+1) the position is still ``s[t-1]``
* intraday (open t+1 -> close t+1) the position is ``s[t]``
* cash earns the T-bill rate, credited once per day
* each switch costs ``slippage_bps`` of the traded value

When open == close in the data (^GSPC before 1962), this is the same as acting at the
next close.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from earnings_bot.backtest.metrics import TRADING_DAYS, _cagr, _drawdown


def run(px: pd.DataFrame, signal: pd.Series, cash: pd.Series | None = None,
        slippage_bps: float = 5.0) -> pd.DataFrame:
    """Returns a frame with daily strategy return, equity (start 1.0) and position."""
    s = signal.reindex(px.index).fillna(0.0)
    held_overnight = s.shift(2).fillna(0.0)  # position at close t is the one decided at t-1
    held_intraday = s.shift(1).fillna(0.0)
    overnight = px.open / px.close.shift(1) - 1
    intraday = px.close / px.open - 1
    c = (cash.reindex(px.index).fillna(0.0) if cash is not None else pd.Series(0.0, index=px.index))
    switched = (held_intraday != held_overnight).astype(float)
    ret = ((1 + held_overnight * overnight.fillna(0)) * (1 + held_intraday * intraday.fillna(0)) - 1
           + (1 - held_intraday) * c - switched * slippage_bps / 10_000)
    ret.iloc[0] = 0.0
    return pd.DataFrame({"ret": ret, "equity": (1 + ret).cumprod(), "position": held_intraday,
                         "switch": switched})


def buy_and_hold(px: pd.DataFrame) -> pd.DataFrame:
    ret = px.close.pct_change().fillna(0.0)
    return pd.DataFrame({"ret": ret, "equity": (1 + ret).cumprod(), "position": 1.0, "switch": 0.0})


def stats(res: pd.DataFrame) -> dict:
    eq, r = res.equity, res.ret
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    vol = r.std() * np.sqrt(TRADING_DAYS)
    return {
        "CAGR": _cagr(eq),
        "volatility": float(vol),
        "max_drawdown": _drawdown(eq),
        "sharpe": float(r.mean() * TRADING_DAYS / vol) if vol > 0 else np.nan,
        "switches_per_year": float(res.switch.sum() / years) if years > 0 else np.nan,
        "time_invested": float(res.position.mean()),
    }
