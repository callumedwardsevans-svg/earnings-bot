"""Daily Markdown report: reports/YYYY-MM-DD.md."""

from __future__ import annotations

import pandas as pd

from earnings_bot.journal import REPORTS_DIR, journal_frame


def _table(rows: list[dict]) -> str:
    return pd.DataFrame(rows).to_markdown(index=False) if rows else "_none_"


def write_daily_report(today, state: dict, account: dict, positions: dict, recon: dict, morning: dict | None,
                       plan: dict | None, spy_close: float | None, problems: list[str]) -> str:
    d = pd.Timestamp(today).date()
    j = journal_frame(state)
    closed = j[j.exit_date.notna()]
    L = [f"# Daily report {d}", "", f"Mode: **{(morning or {}).get('mode', 'n/a')}** this morning. "
         f"Setup {state.get('setup', 'A')} ({state.get('variant', 'ema+fixed')}).", ""]

    # open positions
    trades_by_sym = {t["symbol"]: t for t in state["trades"].values() if t["status"] == "open"}
    rows = []
    for sym, p in sorted(positions.items()):
        t = trades_by_sym.get(sym, {})
        rows.append({"ticker": sym, "shares": int(p["qty"]), "entry": round(p["avg_entry_price"], 2),
                     "last": round(p["current_price"], 2), "unrealised P&L $": round(p["unrealized_pl"], 2),
                     "stop": t.get("stop"), "target": t.get("target"), "since": t.get("entry_date")})
    L += ["## Open positions", "", _table(rows), ""]

    # opened / closed today
    opened = [state["trades"][tid] for tid in recon.get("opened", [])]
    L += ["## Trades opened today", "", _table([{"ticker": t["symbol"], "shares": t["shares"],
                                                  "fill": t["entry_price"], "stop": t["stop"], "target": t["target"]}
                                                 for t in opened]), ""]
    closed_today = j[j.trade_id.isin(recon.get("closed", []))]
    L += ["## Trades closed today", "", closed_today[["ticker", "entry_price", "exit_price", "exit_reason", "pnl_usd",
                                                       "r_multiple"]].to_markdown(index=False)
          if len(closed_today) else "_none_", ""]

    # skipped
    skipped = []
    for s in (morning or {}).get("skipped", []):
        skipped.append({"when": "this morning", "ticker": s["symbol"], "reason": s["reason"]})
    for tid in recon.get("cancelled", []):
        t = state["trades"][tid]
        skipped.append({"when": "entry order", "ticker": t["symbol"], "reason": t.get("cancel_reason", "cancelled")})
    for s in (plan or {}).get("skipped", []):
        skipped.append({"when": "tonight's plan", "ticker": s["symbol"], "reason": s["reason"]})
    L += ["## Signals skipped and why", "", _table(skipped), ""]

    if plan:
        L += [f"## Plan for {plan['session']}", "",
              "Entries:", "", _table([{k: e[k] for k in ("symbol", "qty", "limit", "stop", "target", "risk_usd",
                                                         "eps_surprise_pct", "gap_pct")} for e in plan["entries"]]),
              "", "Scheduled exits (market on open):", "",
              _table([{k: x[k] for k in ("symbol", "qty", "reason")} for x in plan["exits"]]), ""]

    # running stats
    start = state.get("start") or {}
    stats = {"closed trades": len(closed)}
    if len(closed):
        r = closed.r_multiple.astype(float)
        stats.update({"win rate": f"{(r > 0).mean():.0%}", "expectancy (R)": round(r.mean(), 3),
                      "realised P&L $": round(closed.pnl_usd.astype(float).sum(), 2)})
    if start.get("equity"):
        stats["return since start"] = f"{account['equity'] / start['equity'] - 1:+.2%}"
    if start.get("spy_close") and spy_close:
        stats["SPY since start"] = f"{spy_close / start['spy_close'] - 1:+.2%}"
    stats["equity"] = f"${account['equity']:,.2f}"
    L += [f"## Running stats (since {start.get('date', 'n/a')})", "",
          pd.DataFrame([stats]).to_markdown(index=False), ""]

    issues = problems + recon.get("errors", []) + recon.get("warnings", []) + (morning or {}).get("errors", []) \
        + ((plan or {}).get("warnings", []))
    L += ["## Problems", ""] + ([f"- {p}" for p in issues] or ["_none_"]) + [""]
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{d}.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(path)
