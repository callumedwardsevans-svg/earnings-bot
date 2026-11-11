"""S&P 500 universe (today's constituents) with GICS sectors, from Wikipedia.

Survivorship bias: a backtest on *today's* list only includes companies that
survived and grew enough to be in the index now. ``survivorship_summary`` counts how
many names left the index over the backtest window, as a rough guide to its size.
"""

from __future__ import annotations

import io
import logging

import pandas as pd
import requests

from earnings_bot.data.cache import UNIVERSE_DIR, age_hours, read_parquet, write_parquet

log = logging.getLogger(__name__)

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
# The index-changes table moved off the main list page in 2026.
WIKI_CHANGES_URL = "https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500"
CONSTITUENTS_PATH = UNIVERSE_DIR / "sp500.parquet"
CHANGES_PATH = UNIVERSE_DIR / "sp500_changes.parquet"
USER_AGENT = "earnings-bot research script (python-requests)"


def _first_table_with(url: str, column: str) -> pd.DataFrame:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    for t in pd.read_html(io.StringIO(r.text)):
        flat = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in t.columns]
        if any(column in c for c in flat):
            return t
    raise ValueError(f"No table with a {column!r} column at {url}; the page layout changed.")


def _download_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    cons = _first_table_with(WIKI_URL, "GICS Sector")
    changes = _first_table_with(WIKI_CHANGES_URL, "Effective Date")

    cons = cons.rename(
        columns={
            "Symbol": "symbol",
            "Security": "name",
            "GICS Sector": "sector",
            "GICS Sub-Industry": "sub_industry",
            "Date added": "date_added",
        }
    )[["symbol", "name", "sector", "sub_industry", "date_added"]]
    cons["symbol"] = cons["symbol"].str.strip()
    cons["date_added"] = pd.to_datetime(cons["date_added"], errors="coerce")

    changes.columns = ["_".join(dict.fromkeys(c)).strip().lower().replace(" ", "_") for c in changes.columns]
    changes = changes.rename(columns={"effective_date": "date"})
    changes["date"] = pd.to_datetime(changes["date"], errors="coerce", format="mixed")
    return cons.sort_values("symbol").reset_index(drop=True), changes


def load_sp500(max_age_days: float = 7.0) -> pd.DataFrame:
    """Current constituents, refreshed weekly."""
    if age_hours(CONSTITUENTS_PATH) > max_age_days * 24:
        cons, changes = _download_tables()
        write_parquet(cons, CONSTITUENTS_PATH)
        write_parquet(changes.astype({c: "string" for c in changes.columns if c != "date"}), CHANGES_PATH)
        log.info("Refreshed S&P 500 list: %d constituents", len(cons))
    return read_parquet(CONSTITUENTS_PATH)


def survivorship_summary(since: str) -> dict:
    """How many names were removed from / added to the index since a date."""
    load_sp500()
    ch = read_parquet(CHANGES_PATH)
    ch = ch[ch["date"] >= pd.Timestamp(since)]
    removed_col = next(c for c in ch.columns if c.startswith("removed") and "ticker" in c)
    added_col = next(c for c in ch.columns if c.startswith("added") and "ticker" in c)
    return {
        "since": since,
        "removed": int(ch[removed_col].notna().sum()),
        "added": int(ch[added_col].notna().sum()),
        "current_size": len(read_parquet(CONSTITUENTS_PATH)),
    }
