"""Day-by-day portfolio: which simulated signals get taken, at what size, and the equity curve.

Order of events in each session ``d``:

1. Open: ``open_limit`` orders for ``d`` are checked against the limits in rank order
   (highest EPS surprise first) and sized from the previous close's equity and the cash
   available at the start of the day. Orders count towards capacity when sent, whether
   or not they fill, as they would live.
2. During the day: exits recorded by the simulator for ``d`` return cash.
3. Close: ``close`` entries for ``d`` (setup B) are checked and sized the same way.
4. Mark to market at the close. If equity fell >= 2% vs the previous close, no new
   entries are taken the next session (the daily-bar version of the daily loss limit).

Whole shares only, no leverage, no shorting.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from earnings_bot.config import BACKTEST_START_EQUITY, RISK, RiskLimits
from earnings_bot.risk import check_limits, daily_loss_hit, size_position

JOURNAL_COLUMNS = [
    "trade_id", "setup", "variant", "ticker", "signal_date", "entry_date", "entry_price", "stop_price",
    "target_price", "shares", "exit_date", "exit_price", "exit_reason", "pnl_usd", "r_multiple",
    "eps_surprise_pct", "gap_pct", "notes",
]


def run(
    sims: pd.DataFrame,
    px: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    start_equity: float = BACKTEST_START_EQUITY,
    limits: RiskLimits = RISK,
    membership_filter: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (trades in journal format, skipped signals with reasons, daily equity)."""
    by_day = {d: g.sort_values("rank", ascending=False) for d, g in sims.groupby("entry_date")}
    closes = {s: px[s].close for s in sims.symbol.unique()}
    ids = itertools.count(1)

    cash = start_equity
    open_pos: list[dict] = []
    trades, skipped, curve = [], [], []
    prev_equity = start_equity
    block_next = False

    def try_enter(c, d, equity_for_sizing):
        nonlocal cash
        if membership_filter and pd.notna(c.date_added) and c.date_added > c.signal_date:
            skipped.append((c, "not yet in S&P 500 on signal date"))
            return
        reason = check_limits(c.sector, [p["sector"] for p in open_pos] + pending_sectors, block_next,
                              limits=limits)
        if reason:
            skipped.append((c, reason))
            return
        sz = size_position(equity_for_sizing, c.ref_price, c.stop, cash, limits)
        if isinstance(sz, str):
            skipped.append((c, sz))
            return
        if not c.filled:
            pending_sectors.append(c.sector)  # an unfilled order still used a slot today
            skipped.append((c, c.fill_reason))
            return
        cash -= sz.shares * c.entry_price
        open_pos.append({"c": c, "shares": sz.shares, "sector": c.sector, "id": next(ids),
                         "limited_by": sz.limited_by})

    for d in sessions:
        pending_sectors: list[str] = []
        todays = by_day.get(d)
        if todays is not None:
            for c in todays[todays.entry_type == "open_limit"].itertuples():
                try_enter(c, d, prev_equity)

        open_pos, cash = _process_exits(open_pos, d, cash, trades)

        if todays is not None:
            for c in todays[todays.entry_type == "close"].itertuples():
                try_enter(c, d, prev_equity)
            open_pos, cash = _process_exits(open_pos, d, cash, trades)  # same-day scheduled exits

        mtm = 0.0
        for p in open_pos:
            s = closes[p["c"].symbol]
            px_d = s.loc[d] if d in s.index else s.loc[:d].iloc[-1]
            mtm += p["shares"] * px_d
        equity = cash + mtm
        curve.append({"date": d, "equity": equity, "cash": cash, "positions": len(open_pos),
                      "gross_exposure": mtm / equity if equity > 0 else np.nan})
        block_next = daily_loss_hit(equity, prev_equity, limits)
        prev_equity = equity

    for p in open_pos:  # anything still open (exit after the last session) is closed at its sim exit
        trades.append(_journal_row(p))

    trades_df = pd.DataFrame(trades, columns=JOURNAL_COLUMNS)
    skipped_df = pd.DataFrame(
        [{"setup": c.setup, "variant": c.variant, "ticker": c.symbol, "signal_date": c.signal_date,
          "entry_date": c.entry_date, "reason": r, "eps_surprise_pct": c.eps_surprise_pct} for c, r in skipped]
    )
    return trades_df, skipped_df, pd.DataFrame(curve).set_index("date")


def _process_exits(open_pos: list[dict], d, cash: float, trades: list) -> tuple[list[dict], float]:
    still_open = []
    for p in open_pos:
        if p["c"].exit_date <= d:
            cash += p["shares"] * p["c"].exit_price
            trades.append(_journal_row(p))
        else:
            still_open.append(p)
    return still_open, cash


def _journal_row(p: dict) -> dict:
    c, n = p["c"], p["shares"]
    return {
        "trade_id": f"{c.setup}-{c.variant}-{p['id']:04d}", "setup": c.setup, "variant": c.variant,
        "ticker": c.symbol, "signal_date": c.signal_date.date(), "entry_date": c.entry_date.date(),
        "entry_price": round(c.entry_price, 4), "stop_price": round(c.stop, 4),
        "target_price": round(c.target, 4) if pd.notna(c.target) else np.nan, "shares": n,
        "exit_date": c.exit_date.date(), "exit_price": round(c.exit_price, 4), "exit_reason": c.exit_reason,
        "pnl_usd": round(n * (c.exit_price - c.entry_price), 2), "r_multiple": round(c.r_multiple, 3),
        "eps_surprise_pct": round(c.eps_surprise_pct, 2) if pd.notna(c.eps_surprise_pct) else np.nan,
        "gap_pct": round(c.gap_pct, 2) if pd.notna(c.gap_pct) else np.nan,
        "notes": f"{c.notes}; size limited by {p['limited_by']}",
    }
