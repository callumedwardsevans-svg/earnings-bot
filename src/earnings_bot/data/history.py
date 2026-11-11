"""Combined earnings history for the backtest: Yahoo (primary) + Alpha Vantage (cross-check).

Matching: same symbol and report date, falling back to a date within 1 day (the
two sources occasionally differ by a day around midnight-stamped reports).

Timing reconciliation (``timing_source``):

* ``agree``      both sources give the same bmo/amc -> used
* ``yahoo only`` / ``av only``  one source has bmo/amc, the other is missing/unknown -> used
* ``conflict``   one says bmo, the other amc -> ``report_time = "conflict"``, so
  ``day1_session`` returns None and the backtest skips and counts it
* ``none``       neither source knows -> skipped and counted

Alpha Vantage labels before ~2014 default to "pre-market", so conflicts cluster in
old rows; the backtest window starts in 2016.

The volume-spike audit in ``quality.py`` stays a diagnostic. It is *not* used to
settle conflicts, because picking day 1 from the observed volume would use the
outcome to choose the entry.

EPS figures come from Yahoo, filled from Alpha Vantage where Yahoo is missing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from earnings_bot.data.cache import EARNINGS_DIR, read_parquet, write_parquet
from earnings_bot.data.earnings import COLUMNS, load_av_history, surprise_pct
from earnings_bot.data.yahoo import load_yahoo_history

HISTORY_PATH = EARNINGS_DIR / "history.parquet"
KNOWN = {"bmo", "amc"}


def _reconcile(y: str | float, a: str | float) -> tuple[str, str]:
    y = y if isinstance(y, str) else "missing"
    a = a if isinstance(a, str) else "missing"
    if y in KNOWN and a in KNOWN:
        return (y, "agree") if y == a else ("conflict", "conflict")
    if y in KNOWN:
        return y, "yahoo only"
    if a in KNOWN:
        return a, "av only"
    if y == "dmh" or a == "dmh":
        return "dmh", "yahoo only" if y == "dmh" else "av only"
    return "unknown", "none"


def combine(yahoo: pd.DataFrame, av: pd.DataFrame) -> pd.DataFrame:
    y = yahoo.copy().assign(_k=lambda d: np.arange(len(d)))
    a = av.copy()
    a = a.rename(columns={c: f"av_{c}" for c in a.columns if c not in ("symbol",)})

    # 1) exact date match, 2) +/-1 day for whatever's left.
    exact = y.merge(a, left_on=["symbol", "report_date"], right_on=["symbol", "av_report_date"], how="left")
    unmatched_y = exact[exact.av_report_date.isna()][y.columns]
    used_av = set(zip(exact.symbol, exact.av_report_date.dropna())) if len(exact) else set()
    a_left = a[[(s, d) not in used_av for s, d in zip(a.symbol, a.av_report_date)]]
    near = pd.merge_asof(
        unmatched_y.sort_values("report_date"),
        a_left.sort_values("av_report_date"),
        left_on="report_date",
        right_on="av_report_date",
        by="symbol",
        tolerance=pd.Timedelta(days=1),
        direction="nearest",
    )
    matched = pd.concat([exact[exact.av_report_date.notna()], near], ignore_index=True)

    # AV rows Yahoo doesn't have at all
    used_av = set(zip(matched.symbol, matched.av_report_date.dropna()))
    av_only = a[[(s, d) not in used_av for s, d in zip(a.symbol, a.av_report_date)]]
    av_only = av_only.assign(report_date=av_only.av_report_date)

    df = pd.concat([matched, av_only], ignore_index=True)
    rt = [_reconcile(yt, at) for yt, at in zip(df.get("report_time"), df.get("av_report_time"))]
    df["yahoo_report_time"] = df["report_time"]
    df["report_time"] = [r[0] for r in rt]
    df["timing_source"] = [r[1] for r in rt]

    df["eps_actual"] = df["eps_actual"].fillna(df["av_eps_actual"])
    df["eps_estimate"] = df["eps_estimate"].fillna(df["av_eps_estimate"])
    df["surprise_pct"] = [surprise_pct(a_, e_) for a_, e_ in zip(df.eps_actual, df.eps_estimate)]
    df["fiscal_date_ending"] = df["av_fiscal_date_ending"]
    df["source"] = np.where(df["_k"].notna(), np.where(df.av_report_date.notna(), "yahoo+av", "yahoo"), "av")
    for c in ("revenue_actual", "revenue_estimate"):
        df[c] = np.nan

    cols = COLUMNS + ["timing_source", "yahoo_report_time", "av_report_time", "av_eps_actual", "av_eps_estimate"]
    return df[cols].sort_values(["symbol", "report_date"]).reset_index(drop=True)


def build_history(symbols: list[str] | None = None) -> pd.DataFrame:
    df = combine(load_yahoo_history(symbols), load_av_history(symbols))
    write_parquet(df, HISTORY_PATH)
    return df


def load_history() -> pd.DataFrame | None:
    return read_parquet(HISTORY_PATH)
