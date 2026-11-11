"""Earnings day-1 timing: the most common backtest bug, so it gets explicit cases."""

import pandas as pd
import pytest

from earnings_bot.data.calendar import day1_session, next_session, previous_session, sessions_before
from earnings_bot.data.quality import check_one

# Nov 2026: Thanksgiving Thu 26th closed. Mon 23, Tue 24, Wed 25, Fri 27, Mon 30.
SESSIONS = pd.DatetimeIndex(
    ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20",
     "2026-11-23", "2026-11-24", "2026-11-25", "2026-11-27", "2026-11-30"]
)
T = pd.Timestamp


@pytest.mark.parametrize(
    "report_date, timing, expected",
    [
        ("2026-11-18", "bmo", "2026-11-18"),  # before open -> same session
        ("2026-11-18", "amc", "2026-11-19"),  # after close -> next session
        ("2026-11-20", "amc", "2026-11-23"),  # Friday after close -> Monday
        ("2026-11-25", "amc", "2026-11-27"),  # before a holiday -> skips Thanksgiving
        ("2026-11-26", "bmo", "2026-11-27"),  # dated on the holiday itself
        ("2026-11-22", "bmo", "2026-11-23"),  # dated on a Sunday
        ("2026-11-22", "amc", "2026-11-23"),
    ],
)
def test_day1(report_date, timing, expected):
    assert day1_session(report_date, timing, SESSIONS) == T(expected)


@pytest.mark.parametrize("timing", ["dmh", "unknown", "", None])
def test_day1_never_guesses_unclear_timing(timing):
    assert day1_session("2026-11-18", timing, SESSIONS) is None


def test_dates_outside_calendar_return_none():
    assert day1_session("1999-05-18", "bmo", SESSIONS) is None  # no snapping to the first session
    assert day1_session("2026-11-30", "amc", SESSIONS) is None  # beyond the last session


def test_session_helpers():
    assert previous_session("2026-11-27", SESSIONS) == T("2026-11-25")
    assert next_session("2026-11-26", SESSIONS, inclusive=True) == T("2026-11-27")
    # Setup B: entry at the close of the 7th session before the report
    assert sessions_before("2026-11-30", 7, SESSIONS) == T("2026-11-18")  # 27,25,24,23,20,19,18
    assert sessions_before("2026-11-30", 1, SESSIONS) == T("2026-11-27")


def _px_with_spike(spike_day: str) -> pd.DataFrame:
    idx = pd.bdate_range("2026-10-01", "2026-11-30")
    idx = idx[idx != T("2026-11-26")]
    px = pd.DataFrame({"volume": 1_000_000.0}, index=idx)
    px.loc[T(spike_day), "volume"] = 5_000_000.0
    return px


def test_timing_audit_agrees_and_disagrees():
    sessions = _px_with_spike("2026-11-19").index
    px = _px_with_spike("2026-11-19")  # spike the day after an 18th report => after close
    assert check_one(T("2026-11-18"), "amc", px, sessions)["timing_check"] == "agrees"
    assert check_one(T("2026-11-18"), "bmo", px, sessions)["timing_check"] == "disagrees"


def test_timing_audit_other_states():
    px = _px_with_spike("2026-11-02")
    sessions = px.index
    assert check_one(T("2026-11-18"), "amc", px, sessions)["timing_check"] == "no clear spike"
    assert check_one(T("2026-11-22"), "amc", px, sessions)["timing_check"] == "non-trading report date"
    assert check_one(T("2026-11-18"), "unknown", px, sessions)["timing_check"] == "unknown timing"
