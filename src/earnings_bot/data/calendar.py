"""NYSE trading sessions and the earnings "day 1" rule.

Day 1 is the first regular session in which the market can react to the report:

* before the open  (``bmo``) -> the first session on or after the report date
* after the close  (``amc``) -> the first session strictly after the report date
* during market hours (``dmh``) or unknown timing -> ``None`` (flagged, never guessed)

A report dated on a weekend/holiday rolls to the next session either way.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from earnings_bot.data.cache import CALENDAR_DIR, read_parquet, write_parquet

log = logging.getLogger(__name__)

SESSIONS_PATH = CALENDAR_DIR / "nyse_sessions.parquet"
CAL_START = date(2015, 1, 1)


def fetch_sessions(trading_client, start: date = CAL_START, end: date | None = None) -> pd.DataFrame:
    """Download the market calendar from Alpaca (includes half days)."""
    from alpaca.trading.requests import GetCalendarRequest

    end = end or date(pd.Timestamp.today().year + 1, 12, 31)
    rows = trading_client.get_calendar(GetCalendarRequest(start=start, end=end))
    df = pd.DataFrame(
        {
            "session": [pd.Timestamp(r.date) for r in rows],
            "open": [pd.Timestamp(r.open) for r in rows],
            "close": [pd.Timestamp(r.close) for r in rows],
        }
    )
    write_parquet(df, SESSIONS_PATH)
    log.info("Cached %d sessions %s..%s", len(df), df.session.min().date(), df.session.max().date())
    return df


def load_sessions(trading_client=None, min_end: date | None = None) -> pd.DatetimeIndex:
    """Session dates from cache, refreshed via Alpaca if the cache doesn't reach ``min_end``."""
    df = read_parquet(SESSIONS_PATH)
    need = pd.Timestamp(min_end or pd.Timestamp.today().normalize() + pd.Timedelta(days=120))
    if df is None or df.session.max() < need:
        if trading_client is None:
            raise RuntimeError("Session calendar missing/stale; pass a trading client to refresh it.")
        df = fetch_sessions(trading_client)
    return pd.DatetimeIndex(df.session).normalize()


def next_session(d, sessions: pd.DatetimeIndex, inclusive: bool) -> pd.Timestamp | None:
    """First session >= d (inclusive) or > d (exclusive)."""
    ts = pd.Timestamp(d).normalize()
    if len(sessions) == 0 or ts < sessions[0] - pd.Timedelta(days=7):
        return None  # outside the calendar we hold: don't snap to its first day
    i = sessions.searchsorted(ts, side="left" if inclusive else "right")
    return sessions[i] if i < len(sessions) else None


def previous_session(d, sessions: pd.DatetimeIndex) -> pd.Timestamp | None:
    """Last session strictly before d."""
    i = sessions.searchsorted(pd.Timestamp(d).normalize(), side="left")
    return sessions[i - 1] if i > 0 else None


def day1_session(report_date, report_time: str, sessions: pd.DatetimeIndex) -> pd.Timestamp | None:
    if report_time == "bmo":
        return next_session(report_date, sessions, inclusive=True)
    if report_time == "amc":
        return next_session(report_date, sessions, inclusive=False)
    return None  # dmh / unknown: don't guess


def sessions_before(d, n: int, sessions: pd.DatetimeIndex) -> pd.Timestamp | None:
    """The session n trading days before d (n=1 is the last session before d)."""
    i = sessions.searchsorted(pd.Timestamp(d).normalize(), side="left") - n
    return sessions[i] if i >= 0 else None
