"""Long daily histories from Yahoo (via yfinance) for Setup D and the market regime filter.

Alpaca's history starts in 2016, which only contains three real sell-offs. Yahoo gives:

* SPY from 1993 and QQQ from 1999, split- and dividend-adjusted (total return)
* ^GSPC (S&P 500 index) from 1927: **price only, no dividends**. Before 1962 Yahoo's
  open equals the close, so "act at the next open" becomes "act at the next close" there.
* ^IRX (13-week T-bill yield, %) from 1960, used for the return on cash

Research use only (unofficial source); cached under data/prices_yahoo/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from earnings_bot.data.cache import DATA_DIR, age_hours, read_parquet, write_parquet

CACHE = DATA_DIR / "prices_yahoo"
MAX_AGE_HOURS = 24.0


def _path(symbol: str):
    return CACHE / f"{symbol.replace('^', 'IDX_')}.parquet"


def load(symbol: str, refresh: bool = False) -> pd.DataFrame:
    """Daily OHLC (adjusted where Yahoo adjusts), tz-naive date index."""
    path = _path(symbol)
    if not refresh and age_hours(path) < MAX_AGE_HOURS:
        return read_parquet(path)
    import yfinance as yf

    df = yf.Ticker(symbol).history(period="max", auto_adjust=True)
    if df.empty:
        raise RuntimeError(f"Yahoo returned no data for {symbol}")
    df.index = pd.DatetimeIndex(df.index.tz_localize(None).normalize(), name="date")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    write_parquet(df, path)
    return df


def tbill_daily_return(index: pd.DatetimeIndex) -> pd.Series:
    """Daily return on cash from the 13-week T-bill yield (previous day's yield, 252 days/yr).

    Zero before 1960, when the series starts.
    """
    irx = load("^IRX").close.clip(lower=0).reindex(index).ffill().shift(1)
    return ((1 + irx / 100) ** (1 / 252) - 1).fillna(0.0).rename("cash")


HIST_CACHE = DATA_DIR / "prices_yahoo_hist"


def load_history_range(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    """Adjusted daily OHLCV for a stock over a fixed past window (cached; fetched once).

    Used for the 2002-2015 out-of-sample test, where Alpaca has no data. Same column
    layout as the Alpaca price cache. Returns None if Yahoo has nothing for the window.
    """
    path = HIST_CACHE / f"{symbol.replace('.', '-')}_{start}_{end}.parquet"
    if path.exists():
        df = read_parquet(path)
        return df if len(df) else None
    import yfinance as yf

    df = yf.Ticker(symbol.replace(".", "-")).history(start=start, end=end, auto_adjust=True)
    if not df.empty:
        df.index = pd.DatetimeIndex(df.index.tz_localize(None).normalize(), name="date")
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].astype(float)
        df = df[(df.open > 0) & (df.high >= df.low)]
    else:
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"], dtype=float)
    write_parquet(df, path)  # cache empties too, so missing symbols aren't re-requested
    return df if len(df) else None


SHARES_CACHE = DATA_DIR / "shares_yahoo"


def shares_history(symbol: str) -> pd.Series | None:
    """Yahoo shares-outstanding history (raw counts, from Nov 2015), cached once.

    Yahoo gives no filing dates, so callers should lag these values before using them.
    """
    path = SHARES_CACHE / f"{symbol.replace('.', '-')}.parquet"
    if path.exists():
        df = read_parquet(path)
        return df.shares if len(df) else None
    import yfinance as yf

    try:
        s = yf.Ticker(symbol.replace(".", "-")).get_shares_full(start="2015-01-01", end="2026-11-15")
    except Exception:
        s = None
    if s is None or len(s) == 0:
        write_parquet(pd.DataFrame({"shares": pd.Series(dtype=float)}), path)
        return None
    s = s[~s.index.duplicated(keep="last")]
    s.index = pd.DatetimeIndex(s.index.tz_localize(None).normalize(), name="date")
    df = pd.DataFrame({"shares": s.astype(float)}).sort_index()
    write_parquet(df, path)
    return df.shares
