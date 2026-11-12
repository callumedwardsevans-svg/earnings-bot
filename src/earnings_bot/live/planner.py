"""Evening plan for the next session (pure logic, no network).

Inputs are passed in by scripts/plan_orders.py. Output is the plan dict written to
plans/<next session>.json: planned entries (bracket orders), planned scheduled exits
(market-on-open sells) and every signal not acted on, with the reason.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from earnings_bot.config import LIVE_SETUP, LIVE_VARIANT, RISK, SETUP_A, RiskLimits
from earnings_bot.data.calendar import day1_session, previous_session
from earnings_bot.risk import check_limits, size_position
from earnings_bot.signals import setup_a


def floor_cent(x: float) -> float:
    return math.floor(x * 100 + 1e-9) / 100


def ceil_cent(x: float) -> float:
    return math.ceil(x * 100 - 1e-9) / 100


def sessions_between(a, b, sessions: pd.DatetimeIndex) -> int:
    """Number of sessions from a to b (b - a in session steps)."""
    return int(sessions.searchsorted(pd.Timestamp(b)) - sessions.searchsorted(pd.Timestamp(a)))


def build_plan(
    today: pd.Timestamp,
    next_session: pd.Timestamp,
    reports: pd.DataFrame,
    px: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    universe: pd.DataFrame,
    next_reports: dict[str, pd.Timestamp],
    account: dict,
    positions: dict[str, dict],
    state: dict,
    kill_switch: bool = False,
    limits: RiskLimits = RISK,
) -> dict:
    today, nxt = pd.Timestamp(today), pd.Timestamp(next_session)
    sectors = universe.set_index("symbol").sector.to_dict()
    plan = {"session": str(nxt.date()), "signal_date": str(today.date()), "setup": LIVE_SETUP,
            "variant": LIVE_VARIANT, "equity_at_plan": account["equity"], "entries": [], "exits": [],
            "skipped": [], "warnings": []}
    if kill_switch:
        plan["warnings"].append("Kill switch (STOP file) present: plan written for the record only.")

    # ---- scheduled exits for the next session --------------------------------------------
    open_trades = {tid: t for tid, t in state["trades"].items() if t["status"] == "open"}
    for tid, t in open_trades.items():
        qty = positions.get(t["symbol"], {}).get("qty", 0)
        if qty <= 0:
            continue  # closed today; the reconciler handles it
        held = sessions_between(t["entry_date"], nxt, sessions)
        reason = None
        nr = next_reports.get(t["symbol"])
        if nr is not None and previous_session(nr, sessions) is not None and previous_session(nr, sessions) <= nxt:
            reason = f"flat before report ({pd.Timestamp(nr).date()})"
        elif held >= SETUP_A.max_hold_days:
            reason = f"time exit ({held} sessions)"
        if reason:
            plan["exits"].append({"trade_id": tid, "symbol": t["symbol"], "qty": int(qty), "reason": reason})
    for sym in positions:
        if sym not in {t["symbol"] for t in open_trades.values()}:
            plan["warnings"].append(f"Position in {sym} is not managed by the bot (not in journal/state.json).")

    # ---- new Setup A signals with day 1 = today --------------------------------------------
    # Reports whose day 1 is today, plus reports with unusable timing dated since the last
    # session (logged as skipped, since day 1 can't be determined).
    prev = previous_session(today, sessions)
    rel = []
    for r in reports.itertuples():
        d1 = day1_session(r.report_date, r.report_time, sessions)
        if d1 == today or (d1 is None and prev is not None and prev <= r.report_date <= today):
            rel.append(r.Index)
    reports = reports.loc[rel]
    rejected: list[dict] = []
    cands, funnel = setup_a.generate(reports, px, sessions, universe, str((today - pd.Timedelta(days=7)).date()),
                                     str(today.date()), ema_filter=True, trailing=False, rejected=rejected,
                                     require_entry_bar=False)
    plan["funnel"] = dict(funnel)
    rev = reports.set_index("symbol").get("revenue_surprise_pct", pd.Series(dtype=float)).to_dict()
    for rj in rejected:
        plan["skipped"].append({"symbol": rj["symbol"], "report_date": str(pd.Timestamp(rj["report_date"]).date()),
                                "stage": "signal", "reason": rj["reason"]})
    cands = cands[cands.signal_date == today].sort_values("rank", ascending=False)

    # ---- sizing and portfolio limits (re-checked in the morning with live equity) ----------
    occupied = [sectors.get(t["symbol"], "?") for t in state["trades"].values() if t["status"] in ("open", "submitted")]
    cash = account["cash"]
    for c in cands.itertuples():
        limit = round(c.ref_price, 2)
        stop = floor_cent(c.stop)
        target = ceil_cent(c.target)
        trade_id = f"{LIVE_SETUP}-{nxt:%Y%m%d}-{c.symbol}"
        base = {"symbol": c.symbol, "report_date": None, "stage": "risk"}
        if trade_id in state["trades"]:
            plan["skipped"].append({**base, "reason": "already planned/submitted"})
            continue
        if any(t["symbol"] == c.symbol and t["status"] in ("open", "submitted") for t in state["trades"].values()):
            plan["skipped"].append({**base, "reason": "already holding this stock"})
            continue
        why = check_limits(c.sector, occupied, False, kill_switch=kill_switch, limits=limits)
        if why:
            plan["skipped"].append({**base, "reason": why})
            continue
        if not (stop <= limit - 0.01 and target >= limit + 0.01):
            plan["skipped"].append({**base, "reason": "stop/target too close to limit after rounding"})
            continue
        sz = size_position(account["equity"], limit, stop, cash, limits)
        if isinstance(sz, str):
            plan["skipped"].append({**base, "reason": sz})
            continue
        exit_by = None
        nr = next_reports.get(c.symbol)
        if nr is not None:
            exit_by = previous_session(nr, sessions)
            if exit_by is not None and exit_by <= nxt:
                plan["skipped"].append({**base, "reason": f"next report too soon ({pd.Timestamp(nr).date()})"})
                continue
        occupied.append(c.sector)
        cash -= sz.shares * limit
        rs = rev.get(c.symbol, np.nan)
        plan["entries"].append({
            "trade_id": trade_id, "symbol": c.symbol, "sector": c.sector, "signal_date": str(today.date()),
            "entry_date": str(nxt.date()), "limit": limit, "stop": stop, "target": target, "qty": sz.shares,
            "risk_usd": round(sz.risk_usd, 2), "size_limited_by": sz.limited_by,
            "eps_surprise_pct": round(float(c.eps_surprise_pct), 2), "gap_pct": round(float(c.gap_pct), 2),
            "exit_by": str(exit_by.date()) if exit_by is not None else None,
            "notes": f"{c.notes}; revenue surprise "
                     + (f"{rs:+.1f}%" if isinstance(rs, float) and np.isfinite(rs) else "n/a"),
        })
    return plan
