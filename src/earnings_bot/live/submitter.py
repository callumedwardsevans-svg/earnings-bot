"""Morning: re-check the plan against live equity and the risk limits, then send orders.

Order of work:
1. Kill switch -> nothing is sent; the reason is logged.
2. Account must be ACTIVE and not trading-blocked.
3. Scheduled exits: cancel the position's open bracket legs, wait until they're gone, then
   send a market-on-open sell. (Pre-market a stop can't trigger anyway.)
4. Entries: skipped if equity is already down 2% on the day; otherwise each is re-sized
   with live equity/cash and re-checked against the position and sector limits, then sent
   as a GTC bracket (limit entry, stop-loss leg, take-profit leg). client_order_id = trade_id,
   so a re-run can't create duplicates.

``send=False`` (dry run) does everything except call the broker's write methods.
"""

from __future__ import annotations

import time

from earnings_bot.config import LIVE_SETUP, LIVE_VARIANT, RISK, RiskLimits
from earnings_bot.journal import log_event
from earnings_bot.risk import check_limits, daily_loss_hit, size_position

OPEN = {"new", "accepted", "pending_new", "accepted_for_bidding", "partially_filled", "held", "pending_replace",
        "calculated"}


def working_orders(broker, symbol: str) -> list[dict]:
    """Every still-working order for a symbol, including bracket legs nested under a filled parent."""
    flat = []
    for o in broker.orders(status="all", symbols=[symbol]):
        flat.extend([o, *o.get("legs", [])])
    return [o for o in flat if o["status"] in OPEN]


def _wait_until_no_open_orders(broker, symbol: str, tries: int = 15, pause: float = 1.0) -> bool:
    for _ in range(tries):
        if not working_orders(broker, symbol):
            return True
        time.sleep(pause)
    return False


def submit(plan: dict, broker, state: dict, sectors: dict[str, str], send: bool, kill_switch: bool,
           limits: RiskLimits = RISK) -> dict:
    out = {"mode": "send" if send else "dry run", "sent": [], "skipped": [], "errors": []}

    def skip(item, reason):
        out["skipped"].append({"symbol": item["symbol"], "trade_id": item.get("trade_id"), "reason": reason})
        log_event("skipped", symbol=item["symbol"], trade_id=item.get("trade_id"), reason=reason, mode=out["mode"])

    if kill_switch:
        for item in plan["exits"] + plan["entries"]:
            skip(item, "kill switch (STOP file present)")
        return out
    acct = broker.account()
    out["equity"] = acct["equity"]
    if acct["trading_blocked"] or acct["status"] != "ACTIVE":
        for item in plan["exits"] + plan["entries"]:
            skip(item, f"account not tradeable (status {acct['status']}, blocked={acct['trading_blocked']})")
        return out
    positions = broker.positions()

    # ---- scheduled exits -------------------------------------------------------------------
    for x in plan["exits"]:
        pos = positions.get(x["symbol"])
        if not pos or pos["qty"] <= 0:
            skip(x, "no position any more (already closed)")
            continue
        try:
            if send:
                for o in working_orders(broker, x["symbol"]):
                    broker.cancel(o["id"])
                if not _wait_until_no_open_orders(broker, x["symbol"]):
                    raise RuntimeError("bracket legs still open after cancel; exit not sent")
                o = broker.submit_market_on_open_sell(x["symbol"], int(pos["qty"]), f"{x['trade_id']}-exit")
                state["trades"][x["trade_id"]]["exit_order_id"] = o["id"]
            state["trades"].get(x["trade_id"], {})["planned_exit_reason"] = x["reason"]
            out["sent"].append({"kind": "exit (market on open)", "symbol": x["symbol"], "qty": int(pos["qty"]),
                                "reason": x["reason"]})
            log_event("exit_sent" if send else "exit_dry_run", symbol=x["symbol"], qty=int(pos["qty"]),
                      reason=x["reason"], trade_id=x["trade_id"])
        except Exception as exc:
            out["errors"].append(f"exit {x['symbol']}: {exc}")
            log_event("error", symbol=x["symbol"], action="exit", error=str(exc))

    # ---- entries ---------------------------------------------------------------------------
    if daily_loss_hit(acct["equity"], acct["last_equity"], limits):
        for e in plan["entries"]:
            skip(e, f"daily loss limit ({limits.daily_loss_limit_pct:.0%}) hit before the open")
        return out
    occupied = [sectors.get(s, "?") for s in positions]
    occupied += [t["sector"] for t in state["trades"].values()
                 if t["status"] == "submitted" and t["symbol"] not in positions]
    cash = min(acct["cash"], acct["equity"])  # no leverage: never use margin buying power
    for e in plan["entries"]:
        if e["trade_id"] in state["trades"] or broker.order_by_client_id(e["trade_id"]) is not None:
            skip(e, "already submitted")
            continue
        if e["symbol"] in positions:
            skip(e, "already holding this stock")
            continue
        why = check_limits(e["sector"], occupied, False, limits=limits)
        if why:
            skip(e, why)
            continue
        sz = size_position(acct["equity"], e["limit"], e["stop"], cash, limits)
        if isinstance(sz, str):
            skip(e, sz)
            continue
        try:
            order_id = None
            if send:
                o = broker.submit_bracket(e["symbol"], sz.shares, e["limit"], e["target"], e["stop"], e["trade_id"])
                order_id = o["id"]
                state["trades"][e["trade_id"]] = {
                    "setup": LIVE_SETUP, "variant": LIVE_VARIANT, "status": "submitted", "symbol": e["symbol"],
                    "sector": e["sector"], "signal_date": e["signal_date"], "entry_date": e["entry_date"],
                    "ref_price": e["limit"], "stop": e["stop"], "target": e["target"], "qty_ordered": sz.shares,
                    "order_id": order_id, "eps_surprise_pct": e["eps_surprise_pct"], "gap_pct": e["gap_pct"],
                    "exit_by": e.get("exit_by"), "notes": e["notes"],
                }
            occupied.append(e["sector"])
            cash -= sz.shares * e["limit"]
            out["sent"].append({"kind": "entry (bracket)", "symbol": e["symbol"], "qty": sz.shares,
                                "limit": e["limit"], "stop": e["stop"], "target": e["target"],
                                "risk_usd": round(sz.risk_usd, 2)})
            log_event("entry_sent" if send else "entry_dry_run", trade_id=e["trade_id"], symbol=e["symbol"],
                      qty=sz.shares, limit=e["limit"], stop=e["stop"], target=e["target"], order_id=order_id)
        except Exception as exc:  # rejected order etc.: logged, reported, and the run carries on
            out["errors"].append(f"entry {e['symbol']}: {exc}")
            log_event("error", symbol=e["symbol"], action="entry", error=str(exc))
    return out
