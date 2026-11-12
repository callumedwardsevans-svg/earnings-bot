"""Gather the live inputs the planner needs (network: Alpaca, Finnhub, Yahoo).

* Prices: Alpaca SIP daily bars for the universe + SPY, up to today's close.
* Today's reporters: Finnhub calendar (EPS actual/estimate, revenue, hour) for the last
  few days, with the before/after-close timing cross-checked against Yahoo's
  announcement timestamp using the same rule as the backtest history (data/history.py).
* Next report dates: Finnhub forward calendar, for the flat-before-report rule.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import numpy as np
import pandas as pd

from earnings_bot.config import LIVE_FORWARD_CALENDAR_DAYS, SETUP_A, SETUP_B, Settings
from earnings_bot.data import earnings, prices, yahoo
from earnings_bot.data.cache import DATA_DIR, write_parquet
from earnings_bot.data.earnings import surprise_pct
from earnings_bot.data.history import _reconcile
from earnings_bot.indicators import add_indicators

log = logging.getLogger(__name__)


def load_price_panel(settings: Settings, symbols: list[str], refresh: bool = True) -> tuple[dict, dict]:
    """Returns (px with indicators, update status per symbol)."""
    status = prices.update_prices(prices.make_data_client(settings), symbols) if refresh else {}
    px = {}
    for s in symbols:
        df = prices.load_prices(s)
        if df is not None and len(df) > 60:
            px[s] = add_indicators(df, SETUP_A.ema_trend_period, SETUP_A.atr_period,
                                   ema_rising_lookback=SETUP_B.ema_rising_lookback)
    return px, status


def _yahoo_timing(symbol: str, report_date: pd.Timestamp) -> tuple[str | float, float, float]:
    """(timing, eps_actual, eps_estimate) from Yahoo for a report on/near report_date."""
    try:
        y = yahoo.normalize_yahoo(symbol, yahoo.fetch_yahoo(symbol, refresh=True))
    except Exception as exc:
        log.warning("Yahoo lookup failed for %s: %s", symbol, exc)
        return np.nan, np.nan, np.nan
    near = y[(y.report_date - report_date).abs() <= pd.Timedelta(days=1)]
    if near.empty:
        return np.nan, np.nan, np.nan
    row = near.iloc[0]
    return row.report_time, row.eps_actual, row.eps_estimate


def recent_reports(settings: Settings, today: pd.Timestamp, universe_symbols: set[str],
                   lookback_days: int = 6) -> pd.DataFrame:
    """Reports from the last few days in the universe, with reconciled timing and EPS surprise."""
    cal = earnings.fetch_finnhub_calendar((today - timedelta(days=lookback_days)).date(), today.date(),
                                          settings.finnhub_api_key, max_age_hours=0.5)
    cal = cal[cal.symbol.isin(universe_symbols)].copy()
    rows = []
    for r in cal.itertuples():
        y_time, y_act, y_est = _yahoo_timing(r.symbol, r.report_date)
        timing, source = _reconcile(y_time, r.report_time)  # same rule as the backtest history
        source = source.replace("av", "finnhub")
        act = r.eps_actual if np.isfinite(r.eps_actual) else y_act
        est = r.eps_estimate if np.isfinite(r.eps_estimate) else y_est
        rev_s = surprise_pct(r.revenue_actual, r.revenue_estimate)
        rows.append({"symbol": r.symbol, "report_date": r.report_date, "report_time": timing,
                     "timing_source": source, "eps_actual": act, "eps_estimate": est,
                     "surprise_pct": surprise_pct(act, est), "revenue_surprise_pct": rev_s,
                     "finnhub_time": r.report_time, "yahoo_time": y_time})
    return pd.DataFrame(rows, columns=["symbol", "report_date", "report_time", "timing_source", "eps_actual",
                                       "eps_estimate", "surprise_pct", "revenue_surprise_pct", "finnhub_time",
                                       "yahoo_time"])


CONSENSUS_LOG_DIR = DATA_DIR / "consensus_log"


def next_report_dates(settings: Settings, today: pd.Timestamp,
                      log_universe: set[str] | None = None) -> dict[str, pd.Timestamp]:
    """Earliest scheduled report date after today, per symbol (Finnhub forward calendar).

    If ``log_universe`` is given, also saves tonight's consensus (EPS and revenue estimates)
    for every upcoming report in it to data/consensus_log/YYYY-MM-DD.parquet. The last
    snapshot before a report is the consensus as it stood before the release, which free
    APIs can't guarantee historically (research addendum, ground rule 6).
    """
    cal = earnings.fetch_finnhub_calendar((today + timedelta(days=1)).date(),
                                          (today + timedelta(days=LIVE_FORWARD_CALENDAR_DAYS)).date(),
                                          settings.finnhub_api_key)
    if log_universe is not None:
        snap = cal[cal.symbol.isin(log_universe)][["symbol", "report_date", "report_time", "eps_estimate",
                                                    "revenue_estimate"]].copy()
        snap.insert(0, "snapshot_date", pd.Timestamp(today).normalize())
        snap["source"] = "finnhub"
        write_parquet(snap.reset_index(drop=True), CONSENSUS_LOG_DIR / f"{pd.Timestamp(today).date()}.parquet")
    return cal.groupby("symbol").report_date.min().to_dict()
