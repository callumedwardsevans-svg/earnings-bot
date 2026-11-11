"""Earnings dates and surprises.

Two sources, each used where its free tier is actually good (checked Nov 2026):

* **Alpha Vantage ``EARNINGS``** - full quarterly history per symbol (NVDA back to
  1999) with reported/estimated EPS and ``reportTime`` (pre-/post-market). No revenue.
  Free key: 25 requests/day, so raw responses are cached forever and a daily budget
  is enforced locally. This is the backtest source.
* **Finnhub ``calendar/earnings``** - forward calendar plus recent actuals with
  ``hour`` (bmo/amc/dmh) and revenue estimate/actual. The free tier only returns
  roughly the last few months and the next few, capped at 1,500 rows per call, so it
  is fetched week by week. This is the live-loop source.

Normalised schema (both sources):
``symbol, report_date, report_time, report_time_raw, fiscal_date_ending, eps_actual,
eps_estimate, surprise_pct, revenue_actual, revenue_estimate, source``

``report_time`` is one of ``bmo`` / ``amc`` / ``dmh`` / ``unknown``. Unknown timing is
kept and flagged, never guessed.
"""

from __future__ import annotations

import logging
import time as _time
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests

from earnings_bot.data.cache import (
    EARNINGS_DIR,
    RAW_DIR,
    age_hours,
    read_json,
    write_json,
    write_parquet,
)

log = logging.getLogger(__name__)

AV_URL = "https://www.alphavantage.co/query"
FINNHUB_URL = "https://finnhub.io/api/v1/calendar/earnings"
AV_DIR = RAW_DIR / "alphavantage"
FINNHUB_DIR = RAW_DIR / "finnhub"
AV_DAILY_LIMIT = 25
MIN_ABS_ESTIMATE = 0.01  # surprise % is meaningless when the estimate is ~0
USER_AGENT = "earnings-bot research script"

COLUMNS = [
    "symbol",
    "report_date",
    "report_time",
    "report_time_raw",
    "fiscal_date_ending",
    "eps_actual",
    "eps_estimate",
    "surprise_pct",
    "revenue_actual",
    "revenue_estimate",
    "source",
]

_AV_TIME = {"pre-market": "bmo", "post-market": "amc"}
_FH_TIME = {"bmo": "bmo", "amc": "amc", "dmh": "dmh"}


class RateLimited(RuntimeError):
    """The provider (or our local budget) says stop for today."""


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _num(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return np.nan
    return v if np.isfinite(v) else np.nan


def surprise_pct(actual: float, estimate: float) -> float:
    """(actual - estimate) / |estimate| in %; NaN when the estimate is missing or ~0."""
    if np.isnan(actual) or np.isnan(estimate) or abs(estimate) < MIN_ABS_ESTIMATE:
        return np.nan
    return (actual - estimate) / abs(estimate) * 100.0


def _frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["report_date"] = pd.to_datetime(df["report_date"])
    df["fiscal_date_ending"] = pd.to_datetime(df["fiscal_date_ending"])
    return df


def redact(text: str, *secrets: str) -> str:
    """Remove API keys from provider messages/URLs before they reach logs or exceptions.

    Alpha Vantage echoes the key back in its rate-limit message, and requests'
    HTTPError text includes the full URL with the key as a query parameter.
    """
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def _get_json(http, url: str, params: dict, secret: str):
    try:
        r = http.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        if getattr(r, "status_code", 200) == 429:
            raise RateLimited(f"{url}: HTTP 429 rate limit")
        r.raise_for_status()
        return r.json()
    except RateLimited:
        raise
    except Exception as exc:
        # Re-raise without the original (which may contain the key in its URL).
        raise RuntimeError(redact(f"{type(exc).__name__}: {exc}", secret)) from None


def av_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")  # BRK.B -> BRK-B


# --------------------------------------------------------------------------- #
# Alpha Vantage (history)
# --------------------------------------------------------------------------- #
class AlphaVantageBudget:
    """Counts AV requests per US/Eastern calendar day in a small JSON file."""

    def __init__(self, limit: int = AV_DAILY_LIMIT, path=None, today: date | None = None):
        self.limit = limit
        self.path = path or AV_DIR / "_usage.json"
        self._today = today

    @property
    def today(self) -> str:
        return str(self._today or pd.Timestamp.now(tz="America/New_York").date())

    def used(self) -> int:
        return (read_json(self.path) or {}).get(self.today, 0)

    def remaining(self) -> int:
        return max(self.limit - self.used(), 0)

    def spend(self) -> None:
        if self.remaining() <= 0:
            raise RateLimited(f"Alpha Vantage daily budget of {self.limit} used up.")
        usage = read_json(self.path) or {}
        usage = {self.today: usage.get(self.today, 0) + 1}  # keep only today's count
        write_json(usage, self.path)

    def exhaust(self) -> None:
        write_json({self.today: self.limit}, self.path)


def av_raw_path(symbol: str):
    return AV_DIR / f"EARNINGS_{av_symbol(symbol)}.json"


def fetch_av_earnings(
    symbol: str, api_key: str, budget: AlphaVantageBudget, refresh: bool = False, session=None
) -> dict:
    """Raw AV EARNINGS JSON for one symbol, from cache unless ``refresh``."""
    path = av_raw_path(symbol)
    cached = read_json(path)
    if cached is not None and not refresh:
        return cached
    budget.spend()  # raises RateLimited when the local budget is gone
    http = session or requests
    data = _get_json(http, AV_URL, {"function": "EARNINGS", "symbol": av_symbol(symbol), "apikey": api_key}, api_key)
    if "quarterlyEarnings" not in data:
        msg = data.get("Information") or data.get("Note") or data.get("Error Message") or str(data)[:200]
        msg = redact(msg, api_key)
        if "rate limit" in msg.lower() or "requests per day" in msg.lower() or "premium" in msg.lower():
            budget.exhaust()
            raise RateLimited(f"Alpha Vantage: {msg}")
        raise ValueError(f"Alpha Vantage returned no earnings for {symbol}: {msg}")
    write_json(data, path)
    _time.sleep(1.2)  # be polite between calls
    return data


def normalize_av(symbol: str, raw: dict) -> pd.DataFrame:
    rows = []
    for q in raw.get("quarterlyEarnings", []):
        actual, est = _num(q.get("reportedEPS")), _num(q.get("estimatedEPS"))
        raw_time = (q.get("reportTime") or "").strip().lower()
        rows.append(
            {
                "symbol": symbol,
                "report_date": q.get("reportedDate"),
                "report_time": _AV_TIME.get(raw_time, "unknown"),
                "report_time_raw": raw_time,
                "fiscal_date_ending": q.get("fiscalDateEnding"),
                "eps_actual": actual,
                "eps_estimate": est,
                "surprise_pct": surprise_pct(actual, est),
                "revenue_actual": np.nan,
                "revenue_estimate": np.nan,
                "source": "alphavantage",
            }
        )
    return _frame(rows)


def backfill_av(symbols: list[str], api_key: str, budget: AlphaVantageBudget | None = None) -> dict:
    """Fetch AV history for symbols not yet cached, until the daily budget runs out."""
    budget = budget or AlphaVantageBudget()
    status = {}
    for sym in symbols:
        if av_raw_path(sym).exists():
            status[sym] = "cached"
            continue
        try:
            fetch_av_earnings(sym, api_key, budget)
            status[sym] = "fetched"
        except RateLimited as exc:
            log.warning("%s - stopping backfill for today", exc)
            break
        except Exception as exc:
            log.error("AV fetch failed for %s: %s", sym, exc)
            status[sym] = f"error: {exc}"
    return status


def build_history(symbols: list[str] | None = None) -> pd.DataFrame:
    """Combine every cached AV response into ``data/earnings/history.parquet``."""
    frames = []
    for path in sorted(AV_DIR.glob("EARNINGS_*.json")):
        sym = path.stem.removeprefix("EARNINGS_").replace("-", ".")
        if symbols is None or sym in symbols:
            frames.append(normalize_av(sym, read_json(path)))
    df = pd.concat(frames, ignore_index=True) if frames else _frame([])
    df = df.sort_values(["symbol", "report_date"]).reset_index(drop=True)
    write_parquet(df, EARNINGS_DIR / "history.parquet")
    return df


# --------------------------------------------------------------------------- #
# Finnhub (forward calendar + recent actuals)
# --------------------------------------------------------------------------- #
def fetch_finnhub_calendar(
    start: date, end: date, api_key: str, max_age_hours: float = 12.0, session=None
) -> pd.DataFrame:
    """Finnhub calendar for [start, end], fetched and cached one day at a time.

    One busy earnings-season week exceeds the 1,500-row cap, so daily requests are
    used. Days that ended >7 days ago are settled and never refetched; recent/future
    days are refreshed after ``max_age_hours`` because dates and actuals change.
    Requests are spaced to stay under the free tier's 60/minute.
    """
    http = session or requests
    rows: list[dict] = []
    today = date.today()
    d = start
    while d <= end:
        path = FINNHUB_DIR / f"calendar_{d.isoformat()}.json"
        settled = d < today - timedelta(days=7)
        data = read_json(path)
        if data is None or (not settled and age_hours(path) > max_age_hours):
            params = {"from": d.isoformat(), "to": d.isoformat(), "token": api_key}
            data = _get_json(http, FINNHUB_URL, params, api_key).get("earningsCalendar", [])
            if len(data) >= 1500:
                log.warning("Finnhub %s hit the 1,500-row cap; some rows may be missing", d)
            write_json(data, path)
            _time.sleep(1.05)
        rows.extend(data)
        d += timedelta(days=1)
    df = normalize_finnhub(rows)
    return df[(df.report_date >= pd.Timestamp(start)) & (df.report_date <= pd.Timestamp(end))]


def normalize_finnhub(rows: list[dict]) -> pd.DataFrame:
    out = []
    for r in rows:
        actual, est = _num(r.get("epsActual")), _num(r.get("epsEstimate"))
        raw_time = (r.get("hour") or "").strip().lower()
        out.append(
            {
                "symbol": r.get("symbol"),
                "report_date": r.get("date"),
                "report_time": _FH_TIME.get(raw_time, "unknown"),
                "report_time_raw": raw_time,
                "fiscal_date_ending": None,
                "eps_actual": actual,
                "eps_estimate": est,
                "surprise_pct": surprise_pct(actual, est),
                "revenue_actual": _num(r.get("revenueActual")),
                "revenue_estimate": _num(r.get("revenueEstimate")),
                "source": "finnhub",
            }
        )
    return _frame(out).drop_duplicates(["symbol", "report_date"], keep="last")
