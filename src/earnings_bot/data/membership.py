"""Point-in-time S&P 500 membership, rebuilt from Wikipedia.

Source: today's constituents ("List of S&P 500 companies") plus the index-change table
("Historical components of the S&P 500"), both cached by data/universe.py. Starting from
today's list, the change table is applied in reverse (undo each addition, restore each
removal), giving the members on every date back to 2009.

Fixes applied (found by checking that the reverse walk always finds the ticker it undoes):
* renames: the change table uses the ticker of the day, today's list the current one;
* a typo in the table ("ALLE |");
* a missing row: 21st Century Fox's FOX/FOXA left on 2019-03-19 (Disney deal) when the new
  Fox Corp took over those tickers; the old company is kept as 'FOX_21CF'/'FOXA_21CF'.

Validation (see scripts/build_membership.py): the member count stays at 500-506 every
day (some companies have two share classes), and a spot-check of known index changes.

Membership is by ticker. ``data_symbol`` maps an old ticker to the one that holds its price
history today (e.g. FB -> META).
"""

from __future__ import annotations

import pandas as pd

from earnings_bot.data.cache import UNIVERSE_DIR, read_parquet, write_parquet
from earnings_bot.data.universe import CHANGES_PATH, load_sp500

START = pd.Timestamp("2009-01-01")
INTERVALS_PATH = UNIVERSE_DIR / "sp500_membership_intervals.parquet"

# ticker in the change table -> ticker the same company uses today
RENAMES = {
    "FB": "META", "FLT": "CPAY", "RE": "EG", "PCLN": "BKNG", "DLPH": "APTV",
    "KORS": "CPRI", "JOYG": "JOY", "UA.C": "UA", "SATS": "ECHO",
}
# tickers reused by a different company later: (date, ticker in table) -> ticker for that company
DATED_ADD_RENAMES = {(pd.Timestamp("2014-05-01"), "UA"): "UAA",   # Under Armour class A (UA -> UAA in 2016)
                     (pd.Timestamp("2010-11-17"), "IR"): "TT"}    # Ingersoll-Rand plc, now Trane (new IR added 2020)
DATED_RM_RENAMES = {(pd.Timestamp("2015-03-23"), "AGN"): "AGN_OLD"}  # old Allergan; Actavis then took the AGN ticker
# rows missing from the change table: (date, removed tickers)
MISSING_REMOVALS = [(pd.Timestamp("2019-03-19"), ["FOX_21CF", "FOXA_21CF"])]
DATA_SYMBOL = {"FOX_21CF": None, "FOXA_21CF": None, "AGN_OLD": None}  # old 21st Century Fox: no free price history


def _clean(ticker: str) -> str:
    """Strip stray table formatting (e.g. 'ALLE |', 'ITT |')."""
    return ticker.replace("|", "").strip()


def data_symbol(ticker: str) -> str | None:
    return DATA_SYMBOL.get(ticker, ticker)


def build_intervals() -> pd.DataFrame:
    """One row per membership spell: ticker, start (NaT = member since before 2009), end (NaT = still in)."""
    current = load_sp500()
    ch = read_parquet(CHANGES_PATH)
    ch = ch[ch.date >= START]
    events: dict[pd.Timestamp, dict[str, list[str]]] = {}
    for r in ch.itertuples():
        e = events.setdefault(r.date, {"add": [], "rm": []})
        if pd.notna(r.added_ticker):
            t = _clean(r.added_ticker)
            e["add"].append(DATED_ADD_RENAMES.get((r.date, t), RENAMES.get(t, t)))
        if pd.notna(r.removed_ticker):
            t = _clean(r.removed_ticker)
            e["rm"].append(DATED_RM_RENAMES.get((r.date, t), t))
    for d, rm in MISSING_REMOVALS:
        events.setdefault(d, {"add": [], "rm": []})["rm"].extend(rm)
    # 2015 addition of 21st Century Fox class B was recorded as 'FOX'
    for d, e in events.items():
        if d.year == 2015 and "FOX" in e["add"]:
            e["add"] = ["FOX_21CF" if t == "FOX" else t for t in e["add"]]

    members = set(current.symbol)
    end_of = {t: pd.NaT for t in members}  # spell currently open (walking backwards)
    spells, problems = [], []
    for d in sorted(events, reverse=True):
        for t in events[d]["add"]:  # undo an addition: the spell started on d
            if t in members:
                members.discard(t)
                spells.append((t, d, end_of.pop(t)))
            else:
                problems.append(f"{d.date()}: added {t} not found")
        for t in events[d]["rm"]:  # undo a removal: a spell ended on d
            if t in members:
                problems.append(f"{d.date()}: removed {t} already a member")
                continue
            members.add(t)
            end_of[t] = d
    for t in members:
        spells.append((t, pd.NaT, end_of[t]))
    df = pd.DataFrame(spells, columns=["ticker", "start", "end"]).sort_values(["ticker", "start"])
    df.attrs["problems"] = problems
    write_parquet(df.reset_index(drop=True), INTERVALS_PATH)
    return df


def load_intervals() -> pd.DataFrame:
    df = read_parquet(INTERVALS_PATH)
    return df if df is not None else build_intervals()


def members_on(date, intervals: pd.DataFrame | None = None) -> set[str]:
    iv = intervals if intervals is not None else load_intervals()
    d = pd.Timestamp(date)
    m = (iv.start.isna() | (iv.start <= d)) & (iv.end.isna() | (iv.end > d))
    return set(iv.ticker[m])


def was_member(ticker: str, date, intervals: pd.DataFrame) -> bool:
    d = pd.Timestamp(date)
    iv = intervals[intervals.ticker == ticker]
    return bool(((iv.start.isna() | (iv.start <= d)) & (iv.end.isna() | (iv.end > d))).any())


def all_tickers_since(date, intervals: pd.DataFrame | None = None) -> set[str]:
    iv = intervals if intervals is not None else load_intervals()
    return set(iv.ticker[iv.end.isna() | (iv.end > pd.Timestamp(date))])
