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


def clustered_t(r: pd.Series, dates: pd.Series) -> float:
    """t-stat of the mean using weekly clusters (mean R per entry week).

    Earnings signals bunch in reporting season and share market moves, so treating
    them as independent overstates significance.
    """
    weekly = r.groupby(pd.to_datetime(dates).dt.to_period("W")).mean()
    return float(weekly.mean() / (weekly.std(ddof=1) / np.sqrt(len(weekly)))) if len(weekly) > 1 else np.nan


def market_adjust(sims: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    """Add spy_r (SPY's move over each trade's window, in the trade's R units) and excess_r.

    SPY is entered at the same price point as the trade (open for open-limit entries,
    close for close entries) and exited at the trade's exit-date close. Assumes beta 1.
    """
    s = sims.copy()
    spy_in = np.where(s.entry_type == "open_limit", spy.open.reindex(s.entry_date).values,
                      spy.close.reindex(s.entry_date).values)
    spy_out = spy.close.reindex(s.exit_date).values
    s["spy_r"] = (spy_out / spy_in - 1) / (s.initial_risk / s.entry_price)
    s["excess_r"] = s.r_multiple - s.spy_r
    return s


EULER_GAMMA = 0.5772156649


def deflated_sharpe(returns: pd.Series, n_trials: int, sr_trials_var: float) -> dict:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014), on per-period (daily) returns.

    ``n_trials``: number of variants tried; ``sr_trials_var``: variance of the per-period
    Sharpe ratios across those trials. Returns the expected maximum Sharpe under the null
    (SR0) and the probability that the true Sharpe exceeds it (the DSR).
    """
    from scipy.stats import kurtosis, norm, skew

    r = returns.dropna()
    sr = r.mean() / r.std(ddof=1)
    t = len(r)
    g3, g4 = skew(r), kurtosis(r, fisher=False)
    n = max(int(n_trials), 1)
    if n > 1:
        sr0 = np.sqrt(sr_trials_var) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n)
                                        + EULER_GAMMA * norm.ppf(1 - 1 / (n * np.e)))
    else:
        sr0 = 0.0
    z = (sr - sr0) * np.sqrt(t - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    return {"sr_daily": float(sr), "sr0_daily": float(sr0), "dsr": float(norm.cdf(z)), "n_trials": n,
            "skew": float(g3), "kurtosis": float(g4)}


def profit_concentration(pnl: pd.Series, top: float = 0.05) -> float:
    """Share of total profit from the best ``top`` fraction of trades (NaN if total <= 0)."""
    pnl = pnl.dropna().sort_values(ascending=False)
    total = pnl.sum()
    if total <= 0 or len(pnl) == 0:
        return float("nan")
    k = max(1, int(np.ceil(top * len(pnl))))
    return float(pnl.iloc[:k].sum() / total)
