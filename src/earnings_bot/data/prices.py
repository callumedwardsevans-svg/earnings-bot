"""Daily bars from Alpaca, cached per symbol as Parquet.

* Feed: **SIP** (consolidated). The free plan allows historical SIP bars as long as
  the request ends >15 minutes ago. IEX-only volume is ~3% of consolidated volume,
  which would break the dollar-volume and volume-spike filters.
* Adjustment: ``all`` (splits + dividends), so returns are total-return-ish and
  gaps aren't distorted by splits.
* Incremental updates re-fetch a few overlapping days. If those overlapping closes
  no longer match the cache (a new split/dividend changed the adjustment), the whole
  history for that symbol is re-downloaded rather than mixing adjustment bases.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

import pandas as pd

from earnings_bot.config import Settings
from earnings_bot.data.cache import PRICES_DIR, read_parquet, write_parquet

log = logging.getLogger(__name__)

NY = "America/New_York"
HISTORY_START = date(2016, 1, 1)
OVERLAP_DAYS = 7
ADJ_TOLERANCE = 0.002  # 0.2% close mismatch on overlap => adjustment changed
BAR_FINAL_AFTER = time(16, 30)  # NY time after which today's daily bar is treated as final
COLUMNS = ["open", "high", "low", "close", "volume", "vwap", "trade_count"]


def make_data_client(settings: Settings):
    from alpaca.data.historical import StockHistoricalDataClient

    if not settings.alpaca_key_id or not settings.alpaca_secret_key:
        raise RuntimeError("ALPACA_KEY_ID / ALPACA_SECRET_KEY are missing. Fill them in .env.")
    return StockHistoricalDataClient(settings.alpaca_key_id, settings.alpaca_secret_key)


def price_path(symbol: str):
    return PRICES_DIR / f"{symbol.replace('/', '_')}.parquet"


def load_prices(symbol: str) -> pd.DataFrame | None:
    """Cached daily bars indexed by session date (tz-naive)."""
    return read_parquet(price_path(symbol))


def _last_final_date(now_ny: pd.Timestamp) -> date:
    """Latest date whose daily bar is complete."""
    today = now_ny.date()
    return today if now_ny.time() >= BAR_FINAL_AFTER else today - timedelta(days=1)


def _fetch(client, symbols: list[str], start: date, end_dt: datetime) -> dict[str, pd.DataFrame]:
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=datetime.combine(start, time()),
        end=end_dt,
        feed=DataFeed.SIP,
        adjustment=Adjustment.ALL,
    )
    df = client.get_stock_bars(req).df
    out: dict[str, pd.DataFrame] = {}
    if df.empty:
        return out
    for sym, g in df.groupby(level="symbol"):
        g = g.droplevel("symbol")
        g.index = pd.DatetimeIndex(g.index.tz_convert(NY).date, name="date")
        out[sym] = g[COLUMNS].astype(float)
    return out


def merge_bars(cached: pd.DataFrame | None, new: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Append new bars. Returns (merged, needs_full_refetch)."""
    if cached is None or cached.empty:
        return new.sort_index(), False
    overlap = cached.index.intersection(new.index)
    if len(overlap):
        rel = (new.loc[overlap, "close"] / cached.loc[overlap, "close"] - 1).abs()
        if (rel > ADJ_TOLERANCE).any():
            return cached, True
    merged = pd.concat([cached[~cached.index.isin(new.index)], new]).sort_index()
    return merged, False


def update_prices(
    client,
    symbols: list[str],
    start: date = HISTORY_START,
    batch_size: int = 50,
    now: pd.Timestamp | None = None,
) -> dict[str, str]:
    """Bring the cache up to date for ``symbols``. Returns a status per symbol."""
    now_ny = (now or pd.Timestamp.now(tz=NY)).tz_convert(NY)
    last_final = _last_final_date(now_ny)
    # SIP on the free plan must end >15 min ago; 20 min for safety.
    end_dt = (now_ny - pd.Timedelta(minutes=20)).tz_convert("UTC").to_pydatetime()
    status: dict[str, str] = {}

    # Group symbols by the start date they need so one request can serve many symbols.
    groups: dict[date, list[str]] = {}
    cached_map: dict[str, pd.DataFrame | None] = {}
    for sym in symbols:
        cached = load_prices(sym)
        cached_map[sym] = cached
        if cached is not None and not cached.empty:
            if cached.index.max().date() >= last_final:
                status[sym] = "up to date"
                continue
            s = (cached.index.max() - pd.Timedelta(days=OVERLAP_DAYS)).date()
        else:
            s = start
        groups.setdefault(s, []).append(sym)

    for s, syms in groups.items():
        for i in range(0, len(syms), batch_size):
            batch = syms[i : i + batch_size]
            try:
                fetched = _fetch(client, batch, s, end_dt)
            except Exception as exc:  # network / API error: record and move on
                log.error("Bar fetch failed for %s..: %s", batch[0], exc)
                status.update({sym: f"error: {exc}" for sym in batch})
                continue
            for sym in batch:
                new = fetched.get(sym)
                if new is None or new.empty:
                    status[sym] = "no data"
                    continue
                new = new[new.index <= pd.Timestamp(last_final)]  # drop an unfinished bar
                merged, refetch = merge_bars(cached_map[sym], new)
                if refetch:
                    log.info("%s: adjustment changed, re-downloading full history", sym)
                    merged = _fetch(client, [sym], start, end_dt).get(sym, new)
                    merged = merged[merged.index <= pd.Timestamp(last_final)]
                    status[sym] = "refetched (adjustment changed)"
                else:
                    status[sym] = "updated"
                write_parquet(merged, price_path(sym))
    return status
