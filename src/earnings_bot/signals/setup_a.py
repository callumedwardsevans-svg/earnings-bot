"""Setup A: post-earnings drift (PEAD), long only.

Day 1 = first session after the report (see data/calendar.py). Conditions on day 1:
EPS surprise >= +5%, gap open vs previous close >= +3%, close in the upper half of the
range, volume >= 2x the prior 20-session average, price > $10 and 20-day average
dollar volume > $50m, optionally close > 50-day EMA.

Order (sent before the day-2 open, so it may use day-1 data only):
limit buy at day-1 close * 1.005; stop = max(day-1 low - 1c, limit - 2 * ATR14);
target = limit + 3R (fixed variant) or none (trailing variant); time exit at the
close of the 20th session after entry; always flat before the next report.

Not testable here: "revenue also beat" (no revenue history in the free sources).
"""

from __future__ import annotations

from collections import OrderedDict

import numpy as np
import pandas as pd

from earnings_bot.config import SETUP_A, UNIVERSE, SetupAParams, UniverseParams
from earnings_bot.data.calendar import day1_session, next_session, previous_session
from earnings_bot.signals import CANDIDATE_COLUMNS


def generate(
    hist: pd.DataFrame,
    px: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    universe: pd.DataFrame,
    start: str,
    end: str,
    ema_filter: bool,
    trailing: bool,
    regime: pd.Series | None = None,
    p: SetupAParams = SETUP_A,
    u: UniverseParams = UNIVERSE,
) -> tuple[pd.DataFrame, OrderedDict]:
    variant = f"{'ema' if ema_filter else 'noema'}+{'trail' if trailing else 'fixed'}"
    meta = universe.set_index("symbol")
    funnel = OrderedDict((k, 0) for k in [
        "reports in period", "timing known (bmo/amc)", "price data on day 1", f"EPS surprise >= {p.min_eps_surprise_pct:g}%",
        f"gap >= {p.min_gap_pct:g}%", "close in upper half", f"volume >= {p.min_volume_multiple:g}x avg",
        "liquid (price > $10, ADV > $50m)", "above 50 EMA" if ema_filter else "EMA filter off",
        "market regime on" if regime is not None else "no market regime filter", "next session exists",
    ])
    next_report = hist.groupby("symbol").report_date.shift(-1)
    rows = []
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)

    for r, nxt in zip(hist.itertuples(), next_report):
        if not (t0 <= r.report_date <= t1) or r.symbol not in meta.index:
            continue
        funnel["reports in period"] += 1
        d1 = day1_session(r.report_date, r.report_time, sessions)
        if d1 is None:
            continue
        funnel["timing known (bmo/amc)"] += 1
        df = px.get(r.symbol)
        if df is None or d1 not in df.index or d1 > t1:
            continue
        b = df.loc[d1]
        if not np.isfinite(b.prev_close) or not np.isfinite(b.atr):
            continue
        funnel["price data on day 1"] += 1
        if not (r.surprise_pct >= p.min_eps_surprise_pct):
            continue
        funnel[f"EPS surprise >= {p.min_eps_surprise_pct:g}%"] += 1
        gap = (b.open / b.prev_close - 1) * 100
        if gap < p.min_gap_pct:
            continue
        funnel[f"gap >= {p.min_gap_pct:g}%"] += 1
        rng = b.high - b.low
        if rng <= 0 or (b.close - b.low) / rng < p.min_close_in_range:
            continue
        funnel["close in upper half"] += 1
        if not (b.volume >= p.min_volume_multiple * b.vol_avg_prior):
            continue
        funnel[f"volume >= {p.min_volume_multiple:g}x avg"] += 1
        if not (b.close > u.min_price and b.adv > u.min_avg_dollar_volume):
            continue
        funnel["liquid (price > $10, ADV > $50m)"] += 1
        if ema_filter and not (b.close > b.ema):
            continue
        funnel["above 50 EMA" if ema_filter else "EMA filter off"] += 1
        if regime is not None and not regime.get(d1, False):  # SPY trend at the day-1 close
            continue
        funnel["market regime on" if regime is not None else "no market regime filter"] += 1
        d2 = next_session(d1, sessions, inclusive=False)
        if d2 is None or d2 not in df.index:
            continue
        funnel["next session exists"] += 1

        limit = b.close * (1 + p.entry_limit_buffer_pct / 100)
        stop = max(b.low - 0.01, limit - p.atr_stop_multiple * b.atr)
        target = np.nan if trailing else limit + p.take_profit_r * (limit - stop)
        exit_by = previous_session(nxt, sessions) if pd.notna(nxt) else pd.NaT
        rows.append({
            "setup": "A", "variant": variant, "symbol": r.symbol, "sector": meta.at[r.symbol, "sector"],
            "date_added": meta.at[r.symbol, "date_added"], "signal_date": d1, "entry_date": d2,
            "entry_type": "open_limit", "ref_price": limit, "stop": stop, "target": target, "atr": b.atr,
            "exit_by": exit_by, "max_hold_days": p.max_hold_days, "trail": trailing,
            "eps_surprise_pct": r.surprise_pct, "gap_pct": gap, "rank": r.surprise_pct,
            "notes": f"timing {r.report_time} ({r.timing_source})",
        })
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS), funnel
