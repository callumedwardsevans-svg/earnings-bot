"""Data-quality checks on earnings timing.

Alpha Vantage's ``reportTime`` is not always right: for NVDA every report before
Nov 2014 is labelled "pre-market" although NVDA reports after the close, which
looks like a default value. Getting day 1 wrong is the most common earnings-backtest
bug, so each report's label is checked against where the volume spike landed:

* bmo -> the spike should be on the report-date session
* amc -> the spike should be on the next session

``timing_check`` is one of:
``agrees`` | ``disagrees`` | ``no clear spike`` (neither day >= 1.5x the 20-day
average) | ``non-trading report date`` (both rules give the same day 1, so the label
doesn't matter) | ``unknown timing`` | ``no price data``.

In the backtest, ``disagrees`` rows are excluded and counted rather than re-labelled.
Re-labelling from the volume would quietly use the outcome to pick the entry day.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from earnings_bot.data.calendar import next_session

SPIKE_MIN = 1.5
AVG_WINDOW = 20


def _vol_multiple(px: pd.DataFrame, day: pd.Timestamp, base_end: pd.Timestamp) -> float:
    """Volume on ``day`` / mean volume of the AVG_WINDOW sessions before ``base_end``."""
    if day not in px.index or base_end not in px.index:
        return np.nan
    i = px.index.get_loc(base_end)
    if i < AVG_WINDOW:
        return np.nan
    return px.volume.loc[day] / px.volume.iloc[i - AVG_WINDOW : i].mean()


def check_one(report_date, report_time: str, px: pd.DataFrame | None, sessions: pd.DatetimeIndex) -> dict:
    out = {"vol_x_on": np.nan, "vol_x_after": np.nan, "timing_check": "unknown timing"}
    if report_time not in ("bmo", "amc"):
        return out
    on = next_session(report_date, sessions, inclusive=True)
    after = next_session(report_date, sessions, inclusive=False)
    if on is None or after is None or px is None:
        out["timing_check"] = "no price data"
        return out
    if on == after:  # report dated on a weekend/holiday
        out["timing_check"] = "non-trading report date"
        return out
    v_on, v_after = _vol_multiple(px, on, on), _vol_multiple(px, after, on)
    out.update(vol_x_on=v_on, vol_x_after=v_after)
    if np.isnan(v_on) or np.isnan(v_after):
        out["timing_check"] = "no price data"
    elif max(v_on, v_after) < SPIKE_MIN:
        out["timing_check"] = "no clear spike"
    else:
        observed = "bmo" if v_on > v_after else "amc"
        out["timing_check"] = "agrees" if observed == report_time else "disagrees"
    return out


def timing_audit(reports: pd.DataFrame, prices_by_symbol: dict, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    """Add vol_x_on / vol_x_after / timing_check columns to an earnings table."""
    checks = [
        check_one(r.report_date, r.report_time, prices_by_symbol.get(r.symbol), sessions)
        for r in reports.itertuples()
    ]
    return pd.concat([reports.reset_index(drop=True), pd.DataFrame(checks)], axis=1)
