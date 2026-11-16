"""Daily backtest for a single index ETF held at a fractional exposure, with open and close fills.

Inputs per day t: ``p_open[t]`` (exposure from the open to the close) and ``p_close[t]``
(exposure from the close to the next open). Return on day t:

    (1 + p_close[t-1] * overnight_t) * (1 + p_open[t] * intraday_t) - 1
    + cash earned on (1 - p_close[t-1]) over the calendar days since the last session
    - trading costs - funding (IG)

Cost models:
* "alpaca": ``bps`` per side on the traded fraction of equity (2 bps for SPY/QQQ).
* "ig": daily-funded index bet. Spread = ``index_spread_pts`` per round trip on the underlying
  index (half per side, as a fraction of the index level). Funding (fed funds + 3.4%) / 360 per
  calendar night on the exposure held at the close (US close is 21:00 UK, before the 22:00 cut-off).
  Daily-funded bets are dividend-adjusted, so the ETF's total return is used for the price move.
* "none": frictionless.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from earnings_bot.backtest.costs import IG_FUNDING_SPREAD


def run(px: pd.DataFrame, p_open: pd.Series, p_close: pd.Series, cash_rate: pd.Series, model: str = "alpaca",
        mult: float = 1.0, bps: float = 2.0, index_level: pd.Series | None = None, index_spread_pts: float = 0.5,
        fed_funds: pd.Series | None = None) -> pd.DataFrame:
    idx = px.index
    p_open = p_open.reindex(idx).fillna(0.0)
    p_close = p_close.reindex(idx).fillna(0.0)
    prev_close_pos = p_close.shift(1).fillna(0.0)
    overnight = (px.open / px.close.shift(1) - 1).fillna(0.0)
    intraday = (px.close / px.open - 1).fillna(0.0)
    gross = (1 + prev_close_pos * overnight) * (1 + p_open * intraday) - 1

    days = pd.Series(idx, index=idx).diff().dt.days.fillna(0).astype(float)  # calendar days since last session
    rate_prev = cash_rate.reindex(idx, method="ffill").shift(1).fillna(0.0) / 100
    cash = (1 - prev_close_pos).clip(lower=0) * rate_prev * days / 360

    traded_open = (p_open - prev_close_pos).abs()
    traded_close = (p_close - p_open).abs()
    traded = traded_open + traded_close
    if model == "alpaca":
        cost = traded * bps / 10_000 * mult
        funding = pd.Series(0.0, index=idx)
    elif model == "ig":
        lvl = index_level.reindex(idx, method="ffill")
        cost = traded * (index_spread_pts / 2) / lvl * mult
        ff = fed_funds.reindex(idx, method="ffill").shift(1).fillna(0.0) / 100
        funding = prev_close_pos * (ff + IG_FUNDING_SPREAD) / 360 * days * mult
    elif model == "none":
        cost = funding = pd.Series(0.0, index=idx)
    else:
        raise ValueError(model)
    ret = gross + cash - cost - funding
    ret.iloc[0] = 0.0
    return pd.DataFrame({"ret": ret, "equity": (1 + ret).cumprod(), "p_open": p_open, "p_close": p_close,
                         "traded": traded, "cost": cost, "funding": funding, "cash_ret": cash,
                         "rf": rate_prev * days / 360})


def stats(res: pd.DataFrame) -> dict:
    r = res.ret.iloc[1:]
    eq = (1 + r).cumprod()
    years = (r.index[-1] - r.index[0]).days / 365.25
    vol = r.std() * np.sqrt(252)
    excess = r - res.rf.iloc[1:]
    monthly = (1 + r).groupby(r.index.to_period("M")).prod() - 1
    wins, losses = monthly[monthly > 0], monthly[monthly <= 0]
    trades = (res.traded.iloc[1:] > 0.01).sum()
    return {
        "CAGR": float(eq.iloc[-1] ** (1 / years) - 1),
        "volatility": float(vol),
        "max DD": float((eq / eq.cummax() - 1).min()),
        "Sharpe": float(r.mean() / r.std() * np.sqrt(252)),
        "excess Sharpe": float(excess.mean() / excess.std() * np.sqrt(252)),
        "months": int(len(monthly)),
        "win rate (months)": float((monthly > 0).mean()),
        "avg win month": float(wins.mean()) if len(wins) else np.nan,
        "avg loss month": float(losses.mean()) if len(losses) else np.nan,
        "time invested": float((res.p_open.iloc[1:] > 0).mean()),
        "avg exposure": float(res.p_open.iloc[1:].mean()),
        "trades/yr": float(trades / years),
        "costs+funding %/yr": float((res.cost.iloc[1:].sum() + res.funding.iloc[1:].sum()) / years * 100),
    }
