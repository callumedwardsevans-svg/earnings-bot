"""Morning run (before the US open): re-check tonight's plan and send the orders.

Usage:
    python scripts/submit_orders.py              # dry run: prints/logs what it would send
    python scripts/submit_orders.py --send       # live paper orders
    python scripts/submit_orders.py --force-time # skip the "before 09:28 New York" check (testing;
                                                 # with --send it's refused, to avoid sending into a live market)

Scheduled at 13:25 UK = 08:25 New York normally, 09:25 in the weeks when the clocks change on
different dates. Orders sent pre-market queue for the open.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from earnings_bot import journal
from earnings_bot.broker import AlpacaBroker, LiveTradingRefused, make_trading_client
from earnings_bot.config import load_settings
from earnings_bot.data import calendar, universe
from earnings_bot.live.submitter import submit
from earnings_bot.risk import kill_switch_active

NY = "America/New_York"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--force-time", action="store_true")
    ap.add_argument("--session", help="dry run only: use the plan for this date (YYYY-MM-DD) instead of today")
    args = ap.parse_args()
    if args.send and (args.force_time or args.session):
        print("--force-time and --session are for dry runs only.", file=sys.stderr)
        return 2

    if kill_switch_active():
        journal.log_event("kill_switch", detail="STOP file present; no orders sent")
        print("Kill switch: STOP file present in the project root. No orders sent.")
        return 0
    settings = load_settings()
    try:
        client = make_trading_client(settings)
    except (LiveTradingRefused, RuntimeError) as exc:
        print(f"Refusing to start: {exc}", file=sys.stderr)
        return 1
    sessions = calendar.load_sessions(client)
    now = pd.Timestamp.now(tz=NY)
    today = pd.Timestamp(args.session) if args.session else pd.Timestamp(now.date())
    if today not in sessions:
        print(f"{today.date()} is not a trading session; nothing to do.")
        return 0
    if not args.force_time and now.time() >= pd.Timestamp("09:28").time():
        print(f"It's {now:%H:%M} in New York: too close to (or after) the open. Nothing sent.", file=sys.stderr)
        journal.log_event("late_start", detail=f"submit ran at {now:%H:%M} NY; skipped")
        return 1
    plan = journal.load_plan(today)
    if plan is None:
        print(f"No plan for {today.date()} (plans/{today.date()}.json). Nothing to do.")
        return 0

    state = journal.load_state()
    sectors = universe.load_sp500().set_index("symbol").sector.to_dict()
    out = submit(plan, AlpacaBroker(client), state, sectors, send=args.send, kill_switch=False)
    plan["submission"] = out
    journal.save_plan(plan)
    journal.save_state(state)
    journal.write_journal(state)
    print(f"[{out['mode']}] sent {len(out['sent'])}, skipped {len(out['skipped'])}, errors {len(out['errors'])}")
    for s in out["sent"]:
        print("  ", s)
    for s in out["skipped"]:
        print("   skipped:", s)
    for e in out["errors"]:
        print("   ERROR:", e)
    return 1 if out["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
