"""Earnings history from Yahoo Finance via ``yfinance`` (backtest source).

Why: one request per symbol returns ~100 quarters (EPS estimate, reported EPS,
surprise) with the announcement **timestamp**, so before/after-close timing comes
from an actual time of day rather than a label. No daily cap, unlike Alpha Vantage's
free 25/day.

Caveats: yfinance is unofficial (it reads Yahoo's site), can be throttled or break
without notice, and Yahoo's terms are aimed at personal use. It's used for the
research backtest only; raw data stays in the gitignored cache and the live loop
doesn't depend on it.

Timing from the New York local time of the timestamp:

* 04:00-09:29 -> ``bmo``
* 09:30-15:59 -> ``dmh`` (during market hours)
* 16:00-23:59 -> ``amc``
* 00:00-03:59 -> ``unknown`` (midnight-ish stamps look like "date only")
"""

from __future__ import annotations

import logging
import time as _time

import numpy as np
import pandas as pd

from earnings_bot.data.cache import RAW_DIR, age_hours, read_parquet, write_parquet
from earnings_bot.data.earnings import COLUMNS, _frame, surprise_pct

log = logging.getLogger(__name__)

YAHOO_DIR = RAW_DIR / "yahoo"
NY = "America/New_York"
QUARTERS = 100
REFRESH_AFTER_DAYS = 30  # pick up newly reported quarters at most monthly
PAUSE_SECONDS = 0.8


def yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")  # BRK.B -> BRK-B


def raw_path(symbol: str):
    return YAHOO_DIR / f"{yahoo_symbol(symbol)}.parquet"


def classify_time(ts: pd.Timestamp) -> str:
    minutes = ts.hour * 60 + ts.minute
    if minutes < 4 * 60:
        return "unknown"
    if minutes < 9 * 60 + 30:
        return "bmo"
    if minutes < 16 * 60:
        return "dmh"
    return "amc"


def fetch_yahoo(symbol: str, refresh: bool = False, ticker_factory=None) -> pd.DataFrame | None:
    """Raw yfinance earnings-dates frame (cached). None if Yahoo has nothing."""
    path = raw_path(symbol)
    if path.exists() and not refresh and age_hours(path) < REFRESH_AFTER_DAYS * 24:
        return read_parquet(path)
    if ticker_factory is None:
        import yfinance as yf

        ticker_factory = yf.Ticker
    df = ticker_factory(yahoo_symbol(symbol)).get_earnings_dates(limit=QUARTERS)
    if df is None or df.empty:
        return None
    df = df.reset_index()
    df.columns = [str(c) for c in df.columns]
    write_parquet(df, path)
    return df


def normalize_yahoo(symbol: str, raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return _frame([])
    ts = pd.to_datetime(raw["Earnings Date"])
    ts = ts.dt.tz_convert(NY) if ts.dt.tz is not None else ts.dt.tz_localize(NY)
    rows = []
    for t, est, act in zip(ts, raw.get("EPS Estimate"), raw.get("Reported EPS")):
        est, act = float(est) if pd.notna(est) else np.nan, float(act) if pd.notna(act) else np.nan
        rows.append(
            {
                "symbol": symbol,
                "report_date": t.tz_localize(None).normalize(),
                "report_time": classify_time(t),
                "report_time_raw": t.strftime("%H:%M"),
                "fiscal_date_ending": None,
                "eps_actual": act,
                "eps_estimate": est,
                "surprise_pct": surprise_pct(act, est),
                "revenue_actual": np.nan,
                "revenue_estimate": np.nan,
                "source": "yahoo",
            }
        )
    df = _frame(rows)
    df = df[df.eps_actual.notna()]  # drop upcoming (not yet reported) rows
    return df.drop_duplicates(["symbol", "report_date"]).sort_values("report_date").reset_index(drop=True)[COLUMNS]


def backfill_yahoo(symbols: list[str], refresh: bool = False, max_retries: int = 3) -> dict[str, str]:
    """Fetch any symbols missing (or >30 days old) from the cache."""
    status = {}
    for i, sym in enumerate(symbols):
        path = raw_path(sym)
        if path.exists() and not refresh and age_hours(path) < REFRESH_AFTER_DAYS * 24:
            status[sym] = "cached"
            continue
        for attempt in range(1, max_retries + 1):
            try:
                df = fetch_yahoo(sym, refresh=True)
                status[sym] = "fetched" if df is not None else "no data"
                break
            except Exception as exc:  # throttling / transient: back off and retry
                wait = 5 * attempt**2
                log.warning("Yahoo %s attempt %d failed (%s); retrying in %ds", sym, attempt, exc, wait)
                status[sym] = f"error: {type(exc).__name__}"
                _time.sleep(wait)
        _time.sleep(PAUSE_SECONDS)
        if (i + 1) % 50 == 0:
            log.info("Yahoo backfill: %d/%d", i + 1, len(symbols))
    return status


def load_yahoo_history(symbols: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for path in sorted(YAHOO_DIR.glob("*.parquet")):
        sym = path.stem.replace("-", ".")
        if symbols is None or sym in symbols:
            frames.append(normalize_yahoo(sym, read_parquet(path)))
    return pd.concat(frames, ignore_index=True) if frames else _frame([])
