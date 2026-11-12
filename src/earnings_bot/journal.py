"""Live trade state and the trade journal.

``journal/state.json`` is the source of truth for every trade the bot has planned or sent:
its status (submitted -> open -> closed, or cancelled), prices, order ids and notes.
``journal/trades.csv`` is regenerated from it after every run, one row per trade that was
actually entered (open trades have blank exit fields), with exactly the columns the
dashboard expects.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from earnings_bot.backtest.portfolio import JOURNAL_COLUMNS
from earnings_bot.config import PROJECT_ROOT

JOURNAL_DIR = PROJECT_ROOT / "journal"
STATE_PATH = JOURNAL_DIR / "state.json"
TRADES_PATH = JOURNAL_DIR / "trades.csv"
PLANS_DIR = PROJECT_ROOT / "plans"
REPORTS_DIR = PROJECT_ROOT / "reports"
ORDER_LOG = PROJECT_ROOT / "logs" / "orders.jsonl"


def load_state(path=STATE_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"start": None, "trades": {}}


def save_state(state: dict, path=STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def log_event(kind: str, **fields) -> None:
    """Append one JSON line per order sent / skipped / cancelled (brief rule 5)."""
    ORDER_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": kind, **fields}
    with ORDER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def r_multiple(t: dict) -> float | None:
    risk = t["ref_price"] - t["stop"]  # R on the planned risk, as in the backtest
    if t.get("exit_price") is None or t.get("entry_price") is None or risk <= 0:
        return None
    return (t["exit_price"] - t["entry_price"]) / risk


def journal_frame(state: dict) -> pd.DataFrame:
    rows = []
    for tid, t in sorted(state["trades"].items()):
        if t["status"] not in ("open", "closed"):
            continue
        closed = t["status"] == "closed"
        r = r_multiple(t) if closed else None
        rows.append({
            "trade_id": tid, "setup": t["setup"], "variant": t["variant"], "ticker": t["symbol"],
            "signal_date": t["signal_date"], "entry_date": t["entry_date"],
            "entry_price": round(t["entry_price"], 4), "stop_price": t["stop"], "target_price": t["target"],
            "shares": int(t["shares"]), "exit_date": t.get("exit_date") if closed else None,
            "exit_price": round(t["exit_price"], 4) if closed else None,
            "exit_reason": t.get("exit_reason") if closed else None,
            "pnl_usd": round((t["exit_price"] - t["entry_price"]) * t["shares"], 2) if closed else None,
            "r_multiple": round(r, 3) if r is not None else None,
            "eps_surprise_pct": t.get("eps_surprise_pct"), "gap_pct": t.get("gap_pct"), "notes": t.get("notes", ""),
        })
    return pd.DataFrame(rows, columns=JOURNAL_COLUMNS)


def write_journal(state: dict, path=TRADES_PATH) -> pd.DataFrame:
    df = journal_frame(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def plan_path(session) -> "Path":  # noqa: F821
    return PLANS_DIR / f"{pd.Timestamp(session).date()}.json"


def save_plan(plan: dict) -> None:
    p = plan_path(plan["session"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")


def load_plan(session) -> dict | None:
    p = plan_path(session)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
