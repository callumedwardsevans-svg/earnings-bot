"""Setup E (SPY combined) paper loop: morning / close / evening jobs.

Usage:
    python scripts/e_live.py morning [--send]   # pre-open: market-on-open order for today's exposure
    python scripts/e_live.py close   [--send]   # ~15:35 NY: market-on-close order on TOM entry/exit days
    python scripts/e_live.py evening [--send]   # after the close: settle, journal, shadow, report
Testing (dry run only): --force-time skips the time-of-day checks; --session YYYY-MM-DD acts as that day.

Dry run (default): no orders; a virtual $10k book is filled at the real open/close prices (+2 bps),
so the dry run can be compared with the backtest. --send uses Setup E's own paper account
(ALPACA_E_* keys in .env) and the same paper-only guard as Setup A.
"""

from __future__ import annotations

import argparse
import json
import sys
import time as _time

import pandas as pd

from earnings_bot import journal
from earnings_bot.backtest import allocation
from earnings_bot.broker import AlpacaBroker, LiveTradingRefused, make_trading_client, make_trading_client_e
from earnings_bot.config import LIVE_E_DRY_RUN_EQUITY, LIVE_E_SYMBOL, PROJECT_ROOT, load_settings
from earnings_bot.data import calendar, prices
from earnings_bot.live import setup_e_live as E
from earnings_bot.risk import kill_switch_active
from earnings_bot.signals import setup_e

NY = "America/New_York"
SLIP = 2 / 10_000
STATE_DIR = PROJECT_ROOT / "journal"
PLAN_DIR = PROJECT_ROOT / "plans" / "setup_e"
REPORT_DIR = PROJECT_ROOT / "reports" / "setup_e"


def state_path(send: bool):
    return STATE_DIR / f"setup_e_state_{'live' if send else 'dry'}.json"


def load_state(send: bool) -> dict:
    p = state_path(send)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"book": {"shares": 0, "cash": LIVE_E_DRY_RUN_EQUITY}, "start": None, "pending": []}


def save_state(state: dict, send: bool) -> None:
    p = state_path(send)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def spy_closes(settings) -> pd.DataFrame:
    prices.update_prices(prices.make_data_client(settings), [LIVE_E_SYMBOL])
    return prices.load_prices(LIVE_E_SYMBOL)


def account_view(send: bool, state: dict, broker, price: float) -> tuple[float, float, int]:
    """(equity, last_equity, current shares)."""
    if send:
        a = broker.account()
        pos = broker.positions().get(LIVE_E_SYMBOL, {})
        return a["equity"], a["last_equity"], int(pos.get("qty", 0))
    b = state["book"]
    eq = b["cash"] + b["shares"] * price
    return eq, eq, int(b["shares"]) + sum(p["delta"] for p in state["pending"])


def send_order(broker, delta: int, tif: str, cid: str) -> dict:
    side = "buy" if delta > 0 else "sell"
    return broker.submit_market(LIVE_E_SYMBOL, abs(delta), side, tif, cid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["morning", "close", "evening"])
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--force-time", action="store_true")
    ap.add_argument("--session")
    args = ap.parse_args()
    if args.send and (args.force_time or args.session):
        print("--force-time and --session are for dry runs only.", file=sys.stderr)
        return 2
    settings = load_settings()
    try:
        main_client = make_trading_client(settings)  # calendar + paper-only guard
        broker = AlpacaBroker(make_trading_client_e(settings)) if args.send else None
    except (LiveTradingRefused, RuntimeError) as exc:
        print(f"Refusing to start: {exc}", file=sys.stderr)
        return 1
    sessions = calendar.load_sessions(main_client)
    now = pd.Timestamp.now(tz=NY)
    today = pd.Timestamp(args.session) if args.session else pd.Timestamp(now.date())
    if today not in sessions:
        print(f"{today.date()} is not a trading session.")
        return 0
    prev = calendar.previous_session(today, sessions)
    state = load_state(args.send)
    mode = "send" if args.send else "dry run"
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    plan_file = PLAN_DIR / f"{today.date()}.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8")) if plan_file.exists() else {"session": str(today.date())}

    if args.job in ("morning", "close"):
        if args.job == "morning" and not args.force_time and now.time() >= pd.Timestamp("09:28").time():
            print(f"{now:%H:%M} NY: too late for market-on-open orders. Nothing sent.", file=sys.stderr)
            journal.log_event("e_late", job="morning", at=f"{now:%H:%M}")
            return 1
        if args.job == "close" and not args.force_time:
            start, cutoff = pd.Timestamp("15:35").time(), pd.Timestamp("15:48").time()
            if now.time() < start:
                wait = (pd.Timestamp.combine(now.date(), start).tz_localize(NY) - now).total_seconds()
                if wait > 75 * 60:
                    print(f"{now:%H:%M} NY: more than 75 minutes before 15:35; not waiting.", file=sys.stderr)
                    return 1
                _time.sleep(wait)
            elif now.time() > cutoff:
                print(f"{now:%H:%M} NY: past the market-on-close window. Nothing sent.", file=sys.stderr)
                journal.log_event("e_late", job="close", at=f"{now:%H:%M}")
                return 1
        bars = spy_closes(settings)
        closes = bars.close.loc[:prev]
        if closes.index[-1] != prev:
            print(f"SPY bar for {prev.date()} missing; not trading on stale data.", file=sys.stderr)
            return 1
        t = E.targets_for(today, closes, sessions)
        price = float(closes.iloc[-1])
        equity, last_equity, current = account_view(args.send, state, broker, price)
        target = t["target_open"] if args.job == "morning" else t["target_close"]
        if args.job == "close" and abs(t["target_close"] - t["target_open"]) < 1e-12:
            plan["close"] = {"note": "not a TOM entry/exit day: nothing to do"}
            plan_file.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
            print("Not a TOM entry/exit day; nothing to do.")
            return 0
        tgt_shares = E.shares_for(target, equity, price)
        delta, reason = E.order_for(tgt_shares, current, equity, last_equity, kill_switch_active())
        rec = {"mode": mode, "exposure_target": target, "target_shares": tgt_shares, "current_shares": current,
               "equity": equity, "ref_price": price, "delta": delta, "held_back": reason,
               "trend_in": t["trend_in"], "sigma20": t["sigma20"], "vol_scale": t["vol_scale"], "base": t["base"],
               "tom_full_day": t["tom_full_day"], "tom_overnight": t["tom_overnight"]}
        if delta:
            tif = "opg" if args.job == "morning" else "cls"
            cid = f"E-{today:%Y%m%d}-{args.job}"
            if args.send:
                try:
                    rec["order"] = send_order(broker, delta, tif, cid)
                except Exception as exc:
                    rec["error"] = str(exc)
                    journal.log_event("error", setup="E", job=args.job, error=str(exc))
            else:
                state["pending"].append({"date": str(today.date()), "job": args.job, "delta": delta})
            journal.log_event("e_order_sent" if args.send else "e_order_dry_run", job=args.job, delta=delta, tif=tif,
                              exposure=target, client_order_id=cid)
        elif reason != "no change":
            journal.log_event("e_order_held", job=args.job, reason=reason)
        plan[args.job] = rec
        plan_file.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
        save_state(state, args.send)
        print(f"[{mode}] {args.job}: exposure {target:.2f} -> {tgt_shares} sh (have {current}); order {delta:+d}"
              + (f" (held back: {reason})" if reason and reason != "no change" else ""))
        return 1 if rec.get("error") else 0

    # ---------------- evening ----------------
    if not args.force_time and now.time() < pd.Timestamp("16:20").time():
        print("Evening job waits for the close (16:20 NY).")
        return 0
    bars = spy_closes(settings)
    if today not in bars.index:
        print(f"SPY bar for {today.date()} not available yet.", file=sys.stderr)
        return 1
    o, c = float(bars.open.loc[today]), float(bars.close.loc[today])
    fills, problems = [], []
    if args.send:
        for job, px_ref in (("morning", o), ("close", c)):
            od = broker.order_by_client_id(f"E-{today:%Y%m%d}-{job}")
            if od:
                fills.append({"job": job, "status": od["status"], "qty": od["filled_qty"], "price": od["filled_avg_price"],
                              "side": od["side"]})
                if od["status"] not in ("filled",):
                    problems.append(f"{job} order status {od['status']}")
        a = broker.account()
        equity = a["equity"]
        shares = int(broker.positions().get(LIVE_E_SYMBOL, {}).get("qty", 0))
    else:
        b = state["book"]
        for p in [p for p in state["pending"] if p["date"] == str(today.date())]:
            fpx = (o if p["job"] == "morning" else c) * (1 + SLIP if p["delta"] > 0 else 1 - SLIP)
            b["shares"] += p["delta"]
            b["cash"] -= p["delta"] * fpx
            fills.append({"job": p["job"], "qty": p["delta"], "price": round(fpx, 4), "status": "virtual fill"})
        state["pending"] = [p for p in state["pending"] if p["date"] != str(today.date())]
        shares, equity = b["shares"], b["cash"] + b["shares"] * c
    if state["start"] is None:
        state["start"] = {"date": str(today.date()), "equity": equity, "spy_close": c}
    # backtest shadow from the start date: same rules, 2 bps, cash at 0% (as on paper)
    full = bars.close
    po, pc = setup_e.positions(full, trend=True, vol=True, tom=(2, 3))
    zero = pd.Series(0.0, index=pd.date_range(full.index[0], full.index[-1]))
    res = allocation.run(bars, po, pc, zero, model="alpaca", bps=2.0).loc[state["start"]["date"]:]
    shadow = state["start"]["equity"] * (1 + res.ret.iloc[1:]).prod() if len(res) > 1 else state["start"]["equity"]
    nxt = E.base_target(bars.close.loc[:today], sessions)
    row = {"date": str(today.date()), "mode": mode, "shares": shares, "exposure": shares * c / equity if equity else 0,
           "equity": round(equity, 2), "spy_close": c, "shadow_equity": round(float(shadow), 2),
           "spy_since_start": c / state["start"]["spy_close"] - 1,
           "return_since_start": equity / state["start"]["equity"] - 1,
           "base_for_tomorrow": nxt["base"], "trend_in": nxt["trend_in"], "sigma20": round(nxt["sigma20"], 4),
           "fills": json.dumps(fills)}
    daily = STATE_DIR / f"setup_e_daily_{'live' if args.send else 'dry'}.csv"
    df = pd.read_csv(daily) if daily.exists() else pd.DataFrame()
    df = pd.concat([df[df.date != row["date"]] if len(df) else df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(daily, index=False)
    save_state(state, args.send)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    L = [f"# Setup E daily report {today.date()} ({mode})", "",
         f"- Position: {shares} SPY = {row['exposure']:.0%} of equity ${equity:,.2f}",
         f"- Fills today: {fills or 'none'}",
         f"- Since {state['start']['date']}: strategy {row['return_since_start']:+.2%}, SPY {row['spy_since_start']:+.2%}, "
         f"backtest shadow ${row['shadow_equity']:,.2f} (live minus shadow: ${equity - row['shadow_equity']:+,.2f})",
         f"- Tomorrow's base target: {nxt['base']:.2f} (trend {'in' if nxt['trend_in'] else 'out'} at the "
         f"{nxt['trend_month_end'].date()} month-end, sigma20 {nxt['sigma20']:.1%}, vol scale {nxt['vol_scale']:.2f})",
         f"- Plan/orders today: see plans/setup_e/{today.date()}.json", "", "## Problems", ""]
    L += [f"- {p}" for p in problems] or ["_none_"]
    (REPORT_DIR / f"{today.date()}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
