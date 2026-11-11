"""Setup B: pre-earnings run-up, long only.

Entry at the close of the 7th session before the report, if (variant) close > 50-day EMA
and the EMA is rising (above its value 5 sessions earlier). Stop = entry - 1.5 * ATR14.
Exit at the close of the last session before the report date, for both before-open and
after-close reports, so the position is always flat into the report.

Backtest caveats:
* Report dates are the actual historical dates; live, the date must be confirmed in
  advance, and dates that move would be missed or mistimed.
* The entry decision uses the exact closing price. Live, a market-on-close order is
  sent a few minutes before the close using the price at that time.
"""

from __future__ import annotations

from collections import OrderedDict

import numpy as np
import pandas as pd

from earnings_bot.config import SETUP_B, UNIVERSE, SetupBParams, UniverseParams
from earnings_bot.data.calendar import next_session, sessions_before
from earnings_bot.signals import CANDIDATE_COLUMNS


def generate(
    hist: pd.DataFrame,
    px: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    universe: pd.DataFrame,
    start: str,
    end: str,
    ema_filter: bool,
    regime: pd.Series | None = None,
    p: SetupBParams = SETUP_B,
    u: UniverseParams = UNIVERSE,
) -> tuple[pd.DataFrame, OrderedDict]:
    variant = "ema" if ema_filter else "noema"
    meta = universe.set_index("symbol")
    funnel = OrderedDict((k, 0) for k in [
        "reports in period", "price data at entry", "liquid (price > $10, ADV > $50m)",
        "above rising 50 EMA" if ema_filter else "EMA filter off",
        "market regime on" if regime is not None else "no market regime filter",
    ])
    rows = []
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    for r in hist.itertuples():
        if r.symbol not in meta.index:
            continue
        report_session = next_session(r.report_date, sessions, inclusive=True)
        if report_session is None:
            continue
        entry = sessions_before(report_session, p.entry_days_before_report, sessions)
        exit_day = sessions_before(report_session, 1, sessions)
        if entry is None or not (t0 <= entry <= t1):
            continue
        funnel["reports in period"] += 1
        df = px.get(r.symbol)
        if df is None or entry not in df.index or exit_day not in df.index:
            continue
        b = df.loc[entry]
        if not np.isfinite(b.atr) or not np.isfinite(b.ema):
            continue
        funnel["price data at entry"] += 1
        if not (b.close > u.min_price and b.adv > u.min_avg_dollar_volume):
            continue
        funnel["liquid (price > $10, ADV > $50m)"] += 1
        if ema_filter and not (b.close > b.ema and b.ema_rising):
            continue
        funnel["above rising 50 EMA" if ema_filter else "EMA filter off"] += 1
        if regime is not None and not regime.get(entry, False):
            continue
        funnel["market regime on" if regime is not None else "no market regime filter"] += 1
        rows.append({
            "setup": "B", "variant": variant, "symbol": r.symbol, "sector": meta.at[r.symbol, "sector"],
            "date_added": meta.at[r.symbol, "date_added"], "signal_date": entry, "entry_date": entry,
            "entry_type": "close", "ref_price": b.close, "stop": b.close - p.atr_stop_multiple * b.atr,
            "target": np.nan, "atr": b.atr, "exit_by": exit_day, "max_hold_days": np.nan, "trail": False,
            "eps_surprise_pct": np.nan, "gap_pct": np.nan, "rank": b.adv,
            "notes": f"report {r.report_date.date()} ({r.report_time})",
        })
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS), funnel
