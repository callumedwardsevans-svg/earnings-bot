"""Shares outstanding history from SEC EDGAR XBRL (free), for Setup F's turnover measure.

* Source: data.sec.gov "companyconcept" API. Primary tag: dei/EntityCommonStockSharesOutstanding
  (the cover-page count on every 10-Q/10-K, dated a few weeks after quarter end). Fallback:
  us-gaap/WeightedAverageNumberOfSharesOutstandingBasic.
* Point in time: every value carries its ``filed`` date, and a value is only used from the day
  after it was filed.
* Values are raw (not split-adjusted); callers must put volume on the same basis.
* Company IDs (CIKs): Wikipedia's constituents table for current members, SEC's ticker map for
  other listed names, EDGAR's company-name search for delisted ones (verified downstream).
* Polite access: generic User-Agent (no personal details), max ~5 requests/second, cached.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

from earnings_bot.data.cache import RAW_DIR, read_json, write_json

SEC_DIR = RAW_DIR / "sec"
HEADERS = {"User-Agent": "earnings-bot research script"}
TAGS = [("dei", "EntityCommonStockSharesOutstanding"), ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic")]
_last = [0.0]


def _get(url: str, params: dict | None = None):
    wait = 0.2 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def search_cik(name: str) -> tuple[int, str] | None:
    """Top EDGAR entity match for a company name: (CIK, EDGAR name)."""
    j = _get("https://efts.sec.gov/LATEST/search-index", {"keysTyped": name})
    hits = (j or {}).get("hits", {}).get("hits", [])
    return (int(hits[0]["_id"]), hits[0]["_source"]["entity"]) if hits else None


def concept(cik: int, ns: str, tag: str) -> pd.DataFrame | None:
    path = SEC_DIR / f"CIK{cik:010d}_{tag}.json"
    j = read_json(path)
    if j is None:
        j = _get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{ns}/{tag}.json") or {}
        write_json(j, path)
    units = j.get("units", {}).get("shares")
    if not units:
        return None
    d = pd.DataFrame(units)[["end", "val", "filed", "form"]]
    d["end"] = pd.to_datetime(d["end"])
    d["filed"] = pd.to_datetime(d["filed"])
    return d.sort_values(["filed", "end"]).drop_duplicates(["end", "val"])


def shares_history(cik: int) -> tuple[pd.DataFrame | None, str | None]:
    """Cover-page shares if there are enough of them, else weighted-average basic shares."""
    for ns, tag in TAGS:
        d = concept(cik, ns, tag)
        if d is not None and len(d) >= 4:
            return d, tag
    return None, None


def shares_known_on(hist: pd.DataFrame, date, max_age_days: int = 200) -> float | None:
    """Latest share count filed before ``date`` whose period ended within ``max_age_days``."""
    d = pd.Timestamp(date)
    h = hist[(hist.filed < d) & (hist.end >= d - pd.Timedelta(days=max_age_days))]
    return float(h.sort_values(["end", "filed"]).val.iloc[-1]) if len(h) else None
