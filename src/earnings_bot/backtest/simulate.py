"""Per-signal trade simulation on daily bars.

Exits depend only on the signal (not on the portfolio), so each candidate's outcome is
simulated once. The portfolio layer then decides which candidates to take and sizes them.

Fill rules (daily bars, so the intraday path is unknown; ambiguity resolved against us):

* ``open_limit`` entry: filled at the open if open <= limit, else at the limit if the
  day's low reaches it, else not filled.
* ``close`` entry: filled at the close.
* Every fill gets ``SLIPPAGE_BPS`` against us, including limit fills.
* Stop: if a bar's low <= stop, exit at min(open, stop), so a gap through the stop fills at the open.
* Target: if a bar's high >= target, exit at max(open, target).
* Stop and target touched on the same bar -> assume the stop was hit first.
* On the entry bar of an open entry, the stop/target can trigger the same day.
* Scheduled exits (time exit, flat-before-next-report) execute at that session's close.
* R (for r_multiple and the +1R trailing trigger) = planned risk, ref price - stop, which is
  what the position was sized on.
* Trailing variant: after each close, once the highest high since entry >= entry + 1R,
  stop = max(stop, highest high - 2 * ATR14); it takes effect from the next bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from earnings_bot.config import SETUP_A, SLIPPAGE_BPS

SLIP = SLIPPAGE_BPS / 10_000


def simulate(c, df: pd.DataFrame, end: pd.Timestamp, slip: float = SLIP,
             trail_activate_r: float = SETUP_A.trail_activate_r,
             trail_atr_mult: float = SETUP_A.trail_atr_multiple,
             scheduled_exit_at: str = "close") -> dict:
    """Simulate one candidate (a row/namedtuple with CANDIDATE_COLUMNS) on its symbol's bars.

    ``scheduled_exit_at``: "close" (backtest default: time / pre-report exits at that
    session's close) or "open" (the live loop's rule: a market-on-open sell that day).
    """
    out = {"filled": False, "fill_reason": "", "entry_price": np.nan, "exit_date": pd.NaT,
           "exit_price": np.nan, "exit_reason": "", "r_multiple": np.nan, "initial_risk": np.nan}
    if c.entry_date not in df.index:
        out["fill_reason"] = "no bar on entry date"
        return out
    i0 = df.index.get_loc(c.entry_date)
    bar = df.iloc[i0]

    if c.entry_type == "open_limit":
        if bar.open <= c.ref_price:
            raw = bar.open
        elif bar.low <= c.ref_price:
            raw = c.ref_price
        else:
            out["fill_reason"] = "limit not reached"
            return out
        first_check = i0  # bracket legs are live from the fill
    else:  # close
        raw = bar.close
        first_check = i0 + 1
    entry = raw * (1 + slip)
    stop = c.stop
    # R = the risk the position was sized on (planned entry - stop). Using the actual fill
    # instead would blow up R when an open fills far below the limit, close to the stop.
    initial_risk = c.ref_price - c.stop
    target = c.target
    exit_by = c.exit_by if pd.notna(c.exit_by) else None
    max_hold = int(c.max_hold_days) if pd.notna(c.max_hold_days) else None
    out.update(filled=True, entry_price=entry, initial_risk=initial_risk)

    highest = bar.high if c.entry_type == "open_limit" else bar.close
    stop_moved = False
    exit_price, reason, exit_date = None, None, None
    last = min(df.index.searchsorted(end, side="right") - 1, len(df) - 1)

    if c.entry_type == "close" and exit_by is not None and c.entry_date >= exit_by:
        exit_price, reason, exit_date = bar.close * (1 - slip), "scheduled exit", c.entry_date

    j = first_check
    while exit_price is None and j <= last:
        b = df.iloc[j]
        d = df.index[j]
        due = (exit_by is not None and d >= exit_by) or (max_hold is not None and j - i0 >= max_hold)
        if scheduled_exit_at == "open" and due and j > i0:
            # live rule: scheduled exits are market-on-open orders on the day they fall due
            exit_price = b.open * (1 - slip)
            reason = "flat before report" if exit_by is not None and d >= exit_by else "time exit"
        elif b.low <= stop:
            exit_price, reason = min(b.open, stop) * (1 - slip), "trailing stop" if stop_moved else "stop"
        elif pd.notna(target) and b.high >= target:
            exit_price, reason = max(b.open, target) * (1 - slip), "target"
        elif exit_by is not None and d >= exit_by:
            exit_price, reason = b.close * (1 - slip), "flat before report"
        elif max_hold is not None and j - i0 >= max_hold:
            exit_price, reason = b.close * (1 - slip), "time exit"
        if exit_price is not None:
            exit_date = d
            break
        highest = max(highest, b.high)
        if c.trail and highest >= entry + trail_activate_r * initial_risk and np.isfinite(b.atr):
            new_stop = highest - trail_atr_mult * b.atr
            if new_stop > stop:
                stop, stop_moved = new_stop, True
        j += 1

    if exit_price is None:  # still open at the end of the period/data
        exit_date = df.index[last]
        exit_price, reason = df.close.iloc[last] * (1 - slip), "open at period end"

    out.update(exit_date=exit_date, exit_price=exit_price, exit_reason=reason,
               r_multiple=(exit_price - entry) / initial_risk if initial_risk > 0 else np.nan)
    return out


def simulate_all(candidates: pd.DataFrame, px: dict[str, pd.DataFrame], end,
                 scheduled_exit_at: str = "close") -> pd.DataFrame:
    end = pd.Timestamp(end)
    res = [simulate(c, px[c.symbol], end, scheduled_exit_at=scheduled_exit_at) for c in candidates.itertuples()]
    return pd.concat([candidates.reset_index(drop=True), pd.DataFrame(res)], axis=1)
