"""Setup G: PEAD v2, a challenger to Setup A (research addendum, Nov 2026).

Rules as written, with one change forced by ground rule 4:

* Signal (day 1 = first full session after the release): EPS surprise >= 5% [and revenue beat:
  variants blocked until revenue-consensus history exists], and the day-1 close-to-close return
  is positive.
* Entry: the addendum says "at the close of day 1", but the signal needs that same close, and
  rule 4 only allows a close fill when the signal uses data available *before* it. So entry is a
  market order at the **next open (day 2)**, sized on the day-1 close.
* Stop: the day-1 low. No profit target.
* Exit: the close of day +10 (or +20) after entry, unless stopped first; flat before the next
  report (project rule).
* Sizing: 0.5% of equity at risk, max 10% of equity per name (other limits as Setup A).
* Universe/liquidity: point-in-time S&P 500, price > $10, 20-day ADV > $50m (same as A, so the
  two are compared on identical announcements).
"""

from __future__ import annotations

from collections import OrderedDict

import numpy as np
import pandas as pd

from earnings_bot.config import UNIVERSE, UniverseParams
from earnings_bot.data.calendar import day1_session, next_session, previous_session
from earnings_bot.signals import CANDIDATE_COLUMNS

MIN_EPS_SURPRISE = 5.0


def generate(hist, px, sessions, universe, start, end, hold_days: int, require_revenue_beat: bool = False,
             u: UniverseParams = UNIVERSE, rejected: list | None = None):
    if require_revenue_beat and "revenue_surprise_pct" not in hist.columns:
        raise ValueError("revenue-beat variants need revenue consensus history (not available yet)")
    variant = f"{'eps+rev' if require_revenue_beat else 'eps'}+{hold_days}d"
    meta = universe.set_index("symbol")
    funnel = OrderedDict((k, 0) for k in [
        "reports in period", "timing known (bmo/amc)", "price data on day 1", "EPS surprise >= 5%",
        "revenue beat" if require_revenue_beat else "revenue condition off", "day-1 return > 0",
        "liquid (price > $10, ADV > $50m)", "next session exists"])
    next_report = hist.groupby("symbol").report_date.shift(-1)
    rows = []
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)

    def reject(r, reason):
        if rejected is not None:
            rejected.append({"symbol": r.symbol, "report_date": r.report_date, "reason": reason})

    for r, nxt in zip(hist.itertuples(), next_report):
        if not (t0 <= r.report_date <= t1) or r.symbol not in meta.index:
            continue
        funnel["reports in period"] += 1
        d1 = day1_session(r.report_date, r.report_time, sessions)
        if d1 is None:
            reject(r, "timing unknown")
            continue
        funnel["timing known (bmo/amc)"] += 1
        df = px.get(r.symbol)
        if df is None or d1 not in df.index or d1 > t1:
            reject(r, "no day-1 bar")
            continue
        b = df.loc[d1]
        if not np.isfinite(b.prev_close):
            reject(r, "no previous close")
            continue
        funnel["price data on day 1"] += 1
        if not (r.surprise_pct >= MIN_EPS_SURPRISE):
            reject(r, "EPS surprise < 5%")
            continue
        funnel["EPS surprise >= 5%"] += 1
        if require_revenue_beat:
            if not (getattr(r, "revenue_surprise_pct", np.nan) > 0):
                reject(r, "no revenue beat")
                continue
        funnel["revenue beat" if require_revenue_beat else "revenue condition off"] += 1
        day1_ret = b.close / b.prev_close - 1
        if not day1_ret > 0:
            reject(r, "day-1 return <= 0")
            continue
        funnel["day-1 return > 0"] += 1
        if not (b.close > u.min_price and b.adv > u.min_avg_dollar_volume):
            reject(r, "not liquid")
            continue
        funnel["liquid (price > $10, ADV > $50m)"] += 1
        d2 = next_session(d1, sessions, inclusive=False)
        if d2 is None or d2 not in df.index:
            reject(r, "no next session")
            continue
        funnel["next session exists"] += 1
        if not b.low < b.close:
            reject(r, "day-1 low not below close")
            continue
        rows.append({
            "setup": "G", "variant": variant, "symbol": r.symbol, "sector": meta.at[r.symbol, "sector"],
            "date_added": meta.at[r.symbol, "date_added"], "signal_date": d1, "entry_date": d2,
            "entry_type": "open_market", "ref_price": b.close, "stop": b.low, "target": np.nan, "atr": b.atr,
            "exit_by": previous_session(nxt, sessions) if pd.notna(nxt) else pd.NaT, "max_hold_days": hold_days,
            "trail": False, "eps_surprise_pct": r.surprise_pct,
            "gap_pct": (b.open / b.prev_close - 1) * 100, "rank": r.surprise_pct,
            "notes": f"day-1 return {day1_ret:+.1%}; timing {r.report_time}",
        })
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS), funnel
