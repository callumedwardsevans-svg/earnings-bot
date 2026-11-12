"""Evening: match the broker's orders and positions against journal/state.json.

* Submitted entries: filled -> open trade (actual fill price/qty); not filled by the
  evening -> cancelled ("limit not reached"); partially filled -> the rest is cancelled.
* Open trades whose position has gone -> closed, with the exit price from the filled
  sell order and the reason from its type (stop leg, take-profit leg, or the bot's
  market-on-open exit).
* Safety check: every open position must have a working stop order at the broker.
"""

from __future__ import annotations

import pandas as pd

from earnings_bot.journal import log_event

OPEN = {"new", "accepted", "pending_new", "accepted_for_bidding", "partially_filled", "held", "pending_replace",
        "calculated"}
NY = "America/New_York"


def _ny_date(ts: str | None):
    return str(pd.Timestamp(ts).tz_convert(NY).date()) if ts else None


def _exit_reason(order: dict, trade: dict) -> str:
    if order.get("client_order_id", "").endswith("-exit"):
        return trade.get("planned_exit_reason", "scheduled exit").split(" (")[0]
    if order["type"] in ("stop", "stop_limit", "trailing_stop"):
        return "stop"
    if order["type"] == "limit":
        return "target"
    return "closed outside the bot"


def _filled_sells(orders: list[dict], symbol: str) -> list[dict]:
    flat = []
    for o in orders:
        flat.append(o)
        flat.extend(o.get("legs", []))
    return sorted([o for o in flat if o["symbol"] == symbol and o["side"] == "sell" and o["filled_qty"] > 0],
                  key=lambda o: o["filled_at"] or "")


def reconcile(broker, state: dict, today: pd.Timestamp, send: bool) -> dict:
    out = {"opened": [], "closed": [], "cancelled": [], "warnings": [], "errors": []}
    positions = broker.positions()

    for tid, t in state["trades"].items():
        if t["status"] != "submitted":
            continue
        o = broker.order_by_client_id(tid)
        if o is None:
            out["errors"].append(f"{tid}: order not found at the broker")
            continue
        if o["filled_qty"] > 0:
            if o["status"] in OPEN and send:  # partial fill: cancel the rest, keep what filled
                broker.cancel(o["id"])
            t.update(status="open", shares=int(o["filled_qty"]), entry_price=o["filled_avg_price"],
                     entry_date=_ny_date(o["filled_at"]) or t["entry_date"])
            out["opened"].append(tid)
            log_event("entry_filled", trade_id=tid, symbol=t["symbol"], qty=t["shares"], price=t["entry_price"])
        elif o["status"] in OPEN:
            if pd.Timestamp(t["entry_date"]) <= pd.Timestamp(today):
                if send:
                    broker.cancel(o["id"])
                t.update(status="cancelled", cancel_reason="limit not reached")
                out["cancelled"].append(tid)
                log_event("entry_cancelled", trade_id=tid, symbol=t["symbol"], reason="limit not reached")
        else:
            t.update(status="cancelled", cancel_reason=f"order {o['status']}")
            out["cancelled"].append(tid)
            log_event("entry_cancelled", trade_id=tid, symbol=t["symbol"], reason=f"order {o['status']}")

    open_trades = {tid: t for tid, t in state["trades"].items() if t["status"] == "open"}
    if open_trades:
        earliest = min(pd.Timestamp(t["entry_date"]) for t in open_trades.values()) - pd.Timedelta(days=1)
        orders = broker.orders(status="all", after=earliest.tz_localize(NY).to_pydatetime(),
                               symbols=sorted({t["symbol"] for t in open_trades.values()}))
    else:
        orders = []
    for tid, t in open_trades.items():
        pos = positions.get(t["symbol"])
        if pos and pos["qty"] > 0:
            if int(pos["qty"]) != int(t["shares"]):
                out["warnings"].append(f"{t['symbol']}: broker shows {pos['qty']:g} shares, journal {t['shares']}")
            working = [o for o in orders if o["symbol"] == t["symbol"]]
            legs = [x for o in working for x in [o, *o.get("legs", [])]]
            if not any(x["side"] == "sell" and x["type"] in ("stop", "stop_limit") and x["status"] in OPEN
                       for x in legs):
                out["warnings"].append(f"{t['symbol']}: NO working stop order at the broker")
            continue
        sells = _filled_sells(orders, t["symbol"])
        if not sells:
            out["errors"].append(f"{tid}: position gone but no filled sell order found")
            continue
        last = sells[-1]
        t.update(status="closed", exit_price=last["filled_avg_price"], exit_date=_ny_date(last["filled_at"]),
                 exit_reason=_exit_reason(last, t))
        out["closed"].append(tid)
        log_event("exit_filled", trade_id=tid, symbol=t["symbol"], price=t["exit_price"], reason=t["exit_reason"])
    return out
