"""Platform cost models (research addendum, Nov 2026), applied to frictionless simulated trades.

Simulate with ``slip=0`` and then apply one of:

* **Alpaca:** $0 commission; slippage per side, 3 bps for S&P 500 stocks, 2 bps for SPY/QQQ.
* **IG daily-funded spread bet, US shares:** spread 0.10% of price per round trip, capped at
  $0.10/share (half on entry, half on exit); funding (fed funds + 3.4%) / 360 per calendar
  night held past 22:00 UK, on the full notional. US stock trades open/close by 21:00 UK, so
  the nights charged = calendar days from the entry date to the exit date.

``mult`` scales every cost (2.0 = the cost-stress test). R stays measured on planned risk.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import requests

from earnings_bot.data.cache import DATA_DIR, age_hours, read_parquet, write_parquet

IG_FUNDING_SPREAD = 0.034
ALPACA_BPS = {"stock": 3.0, "etf": 2.0}


def fred_series(series_id: str) -> pd.Series:
    """A FRED daily series in %, calendar-daily (forward-filled), cached for a week."""
    path = DATA_DIR / "rates" / f"fred_{series_id}.parquet"
    if age_hours(path) > 24 * 7:
        r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
                         headers={"User-Agent": "earnings-bot research script"}, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = ["date", "rate"]
        df["date"] = pd.to_datetime(df["date"])
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
        write_parquet(df.dropna().set_index("date"), path)
    s = read_parquet(path).rate
    return s.reindex(pd.date_range(s.index.min(), pd.Timestamp.today().normalize())).ffill()


def fed_funds() -> pd.Series:
    """Daily effective fed funds rate in % (FRED DFF): IG's funding benchmark."""
    return fred_series("DFF")


def tbill_3m() -> pd.Series:
    """3-month T-bill secondary-market rate in % (FRED DTB3): the return on cash."""
    return fred_series("DTB3")


def funding_per_unit(entry_dates: pd.Series, exit_dates: pd.Series, ff: pd.Series | None = None) -> np.ndarray:
    """Sum over nights held of (ff + 3.4%)/360, per $1 of notional."""
    ff = fed_funds() if ff is None else ff
    daily = (ff / 100 + IG_FUNDING_SPREAD) / 360
    cum = daily.cumsum()
    a = pd.DatetimeIndex(entry_dates)
    b = pd.DatetimeIndex(exit_dates)
    ca = cum.reindex(a - pd.Timedelta(days=1)).fillna(0).values  # nights from entry date
    cb = cum.reindex(b - pd.Timedelta(days=1)).fillna(0).values  # up to the night before exit
    return np.maximum(cb - ca, 0.0)


def apply_costs(sims: pd.DataFrame, model: str, mult: float = 1.0, asset: str = "stock",
                ff: pd.Series | None = None) -> pd.DataFrame:
    """Return a copy of frictionless ``sims`` with entry/exit prices and R net of costs."""
    s = sims.copy()
    filled = s["filled"].fillna(False).astype(bool)
    e, x = s.loc[filled, "entry_price"], s.loc[filled, "exit_price"]
    if model == "alpaca":
        bps = ALPACA_BPS[asset] * mult / 10_000
        e_net, x_net = e * (1 + bps), x * (1 - bps)
        s.loc[filled, "funding_per_share"] = 0.0
    elif model == "ig":
        half_e = np.minimum(0.0005 * e, 0.05) * mult
        half_x = np.minimum(0.0005 * x, 0.05) * mult
        fund = funding_per_unit(s.loc[filled, "entry_date"], s.loc[filled, "exit_date"], ff) * e.values * mult
        e_net, x_net = e + half_e, x - half_x - fund
        s.loc[filled, "funding_per_share"] = fund
    else:
        raise ValueError(model)
    s.loc[filled, "entry_price"] = e_net
    s.loc[filled, "exit_price"] = x_net
    s.loc[filled, "r_multiple"] = (x_net - e_net) / s.loc[filled, "initial_risk"]
    return s
