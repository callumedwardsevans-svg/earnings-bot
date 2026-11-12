"""Evening run (after the US close): reconcile -> journal -> refresh data -> plan -> daily report.

Usage:
    python scripts/evening.py                  # dry run: reads the broker, cancels nothing
    python scripts/evening.py --send           # live paper: also cancels unfilled entry orders
    python scripts/evening.py --force-time     # skip the "after 16:20 New York" check (testing)

Scheduled by Windows Task Scheduler at 22:00 UK (always after the US close, including the
weeks when UK and US clocks change on different dates).
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback

import pandas as pd

from earnings_bot import journal
from earnings_bot.broker import AlpacaBroker, LiveTradingRefused, make_trading_client
from earnings_bot.config import load_settings
from earnings_bot.data import calendar, universe
from earnings_bot.live import inputs, planner, reconciler
from earnings_bot.report import write_daily_report
from earnings_bot.risk import kill_switch_active

NY = "America/New_York"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--force-time", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    settings = load_settings()
    try:
        client = make_trading_client(settings)
    except (LiveTradingRefused, RuntimeError) as exc:
        print(f"Refusing to start: {exc}", file=sys.stderr)
        return 1
    broker = AlpacaBroker(client)
    sessions = calendar.load_sessions(client)
    now = pd.Timestamp.now(tz=NY)
    today = pd.Timestamp(now.date())
    if today not in sessions:
        print(f"{today.date()} is not a trading session; nothing to do.")
        return 0
    if not args.force_time and now.time() < pd.Timestamp("16:20").time():
        print(f"It's {now:%H:%M} in New York; the evening run waits for the close (use --force-time to override).")
        return 0
    nxt = calendar.next_session(today, sessions, inclusive=False)
    problems: list[str] = []

    state = journal.load_state()
    state.setdefault("setup", "A")
    state.setdefault("variant", "ema+fixed")
    morning = (journal.load_plan(today) or {}).get("submission")

    # 1. reconcile
    recon = {"opened": [], "closed": [], "cancelled": [], "warnings": [], "errors": []}
    try:
        recon = reconciler.reconcile(broker, state, today, send=args.send)
    except Exception as exc:
        problems.append(f"reconcile failed: {exc}")
        traceback.print_exc()
    journal.save_state(state)
    journal.write_journal(state)

    # 2. data + plan for the next session
    uni = universe.load_sp500()
    plan = None
    spy_close = None
    try:
        symbols = sorted(set(uni.symbol) | {"SPY"})
        px, status = inputs.load_price_panel(settings, symbols)
        errs = [s for s, v in status.items() if v.startswith("error")]
        if errs:
            problems.append(f"price update errors for {len(errs)} symbols: {', '.join(errs[:10])}")
        spy_close = float(px["SPY"].close.loc[:today].iloc[-1])
        if today not in px["SPY"].index:
            problems.append(f"today's SPY bar is missing; the plan may be using stale prices")
        account, positions = broker.account(), broker.positions()
        if state.get("start") is None and args.send:  # performance baseline starts with live paper orders
            state["start"] = {"date": str(today.date()), "equity": account["equity"], "spy_close": spy_close}
        reports = inputs.recent_reports(settings, today, set(uni.symbol))
        next_reports = inputs.next_report_dates(settings, today, log_universe=set(uni.symbol))
        plan = planner.build_plan(today, nxt, reports, px, sessions, uni, next_reports, account, positions, state,
                                  kill_switch=kill_switch_active())
        plan["mode_tonight"] = "send" if args.send else "dry run"
        journal.save_plan(plan)
        print(f"Plan for {nxt.date()}: {len(plan['entries'])} entries, {len(plan['exits'])} exits, "
              f"{len(plan['skipped'])} skipped")
    except Exception as exc:
        problems.append(f"planning failed: {exc}")
        traceback.print_exc()
        account, positions = broker.account(), broker.positions()

    journal.save_state(state)
    path = write_daily_report(today, state, account, positions, recon, morning, plan, spy_close, problems)
    print(f"Report: {path}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
