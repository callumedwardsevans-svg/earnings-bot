"""Performance metrics for a run, and the SPY buy-and-hold benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def _sharpe(equity: pd.Series) -> float:
    r = equity.pct_change().dropna()
    return float(r.mean() / r.std() * np.sqrt(TRADING_DAYS)) if r.std() > 0 else np.nan


def _cagr(equity: pd.Series) -> float:
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1) if years > 0 else np.nan


def trade_stats(r: pd.Series) -> dict:
    r = r.dropna()
    wins, losses = r[r > 0], r[r <= 0]
    return {
        "trades": int(len(r)),
        "win_rate": float(len(wins) / len(r)) if len(r) else np.nan,
        "avg_win_r": float(wins.mean()) if len(wins) else np.nan,
        "avg_loss_r": float(losses.mean()) if len(losses) else np.nan,
        "expectancy_r": float(r.mean()) if len(r) else np.nan,
        # standard error of the mean R: how far expectancy could plausibly be from 0
        "expectancy_se": float(r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 1 else np.nan,
    }


def portfolio_metrics(trades: pd.DataFrame, curve: pd.DataFrame) -> dict:
    eq = curve.equity
    return {
        **trade_stats(trades.r_multiple),
        "total_return": float(eq.iloc[-1] / eq.iloc[0] - 1),
        "cagr": _cagr(eq),
        "max_drawdown": _drawdown(eq),
        "sharpe": _sharpe(eq),
        "exposure_time": float((curve.positions > 0).mean()),
        "avg_gross_exposure": float(curve.gross_exposure.mean()),
        "pnl_usd": float(trades.pnl_usd.sum()),
    }


def benchmark(spy: pd.DataFrame, start, end, start_equity: float) -> tuple[dict, pd.Series]:
    c = spy.close.loc[pd.Timestamp(start):pd.Timestamp(end)]
    eq = start_equity * c / c.iloc[0]
    return {"total_return": float(eq.iloc[-1] / eq.iloc[0] - 1), "cagr": _cagr(eq),
            "max_drawdown": _drawdown(eq), "sharpe": _sharpe(eq), "exposure_time": 1.0}, eq
