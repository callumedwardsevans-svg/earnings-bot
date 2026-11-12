"""Live loop logic (planner, submitter, reconciler, journal) against a fake broker."""

import numpy as np
import pandas as pd
import pytest

from earnings_bot import journal
from earnings_bot.backtest.portfolio import JOURNAL_COLUMNS
from earnings_bot.indicators import add_indicators
from earnings_bot.live import planner, reconciler, submitter

SESSIONS = pd.bdate_range("2026-07-01", "2026-12-31")
TODAY = pd.Timestamp("2026-11-12")
NEXT = pd.Timestamp("2026-11-13")
UNI = pd.DataFrame({"symbol": ["AAA", "BBB", "CCC"], "sector": ["Tech", "Tech", "Energy"],
                    "date_added": pd.to_datetime(["2000-01-01"] * 3)})


@pytest.fixture(autouse=True)
def _no_real_files(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "ORDER_LOG", tmp_path / "orders.jsonl")
    monkeypatch.setattr(submitter, "_wait_until_no_open_orders", lambda *a, **k: True)


def price_panel(gap=5.0, close_pos=0.9, vol_x=3.0):
    idx = SESSIONS[SESSIONS <= TODAY]
    close = pd.Series(np.linspace(80, 100, len(idx)), index=idx)
    df = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1e6})
    prev = df.close.iloc[-2]
    o = prev * (1 + gap / 100)
    lo, hi = o - 1, o + 4
    df.iloc[-1] = [o, hi, lo, lo + close_pos * (hi - lo), 1e6 * vol_x]
    return add_indicators(df)


def reports(symbol="AAA", surprise=12.0, timing="amc", date="2026-11-11"):
    return pd.DataFrame([{"symbol": symbol, "report_date": pd.Timestamp(date), "report_time": timing,
                          "timing_source": "agree", "surprise_pct": surprise, "revenue_surprise_pct": 2.0}])


ACCOUNT = {"equity": 10_000.0, "last_equity": 10_000.0, "cash": 10_000.0, "status": "ACTIVE",
           "trading_blocked": False}


def empty_state():
    return {"start": None, "trades": {}}


# ---------------------------------------------------------------- planner
def test_planner_creates_entry_with_rounded_prices():
    plan = planner.build_plan(TODAY, NEXT, reports(), {"AAA": price_panel()}, SESSIONS, UNI, {}, ACCOUNT, {},
                              empty_state())
    assert len(plan["entries"]) == 1, plan["skipped"]
    e = plan["entries"][0]
    assert e["trade_id"] == "A-20261113-AAA" and e["entry_date"] == "2026-11-13"
    assert e["stop"] < e["limit"] < e["target"]
    assert all(round(v, 2) == v for v in (e["limit"], e["stop"], e["target"]))
    assert e["qty"] * e["limit"] <= 1_500 + 1e-6  # 15% cap


@pytest.mark.parametrize("kw, reason", [
    (dict(surprise=2.0), "EPS surprise"), (dict(timing="unknown"), "timing not usable"),
])
def test_planner_logs_rejected_signals(kw, reason):
    plan = planner.build_plan(TODAY, NEXT, reports(**kw), {"AAA": price_panel()}, SESSIONS, UNI, {}, ACCOUNT, {},
                              empty_state())
    assert not plan["entries"] and any(reason in s["reason"] for s in plan["skipped"])


def test_planner_skips_when_next_report_is_too_soon():
    plan = planner.build_plan(TODAY, NEXT, reports(), {"AAA": price_panel()}, SESSIONS, UNI,
                              {"AAA": pd.Timestamp("2026-11-16")}, ACCOUNT, {}, empty_state())
    assert not plan["entries"] and "next report too soon" in plan["skipped"][0]["reason"]


def open_trade(sym="BBB", entry="2026-10-16", **kw):
    return {"setup": "A", "variant": "ema+fixed", "status": "open", "symbol": sym, "sector": "Tech",
            "signal_date": "2026-10-15", "entry_date": entry, "ref_price": 50.0, "stop": 48.0, "target": 56.0,
            "shares": 10, "entry_price": 49.9, "eps_surprise_pct": 9.0, "gap_pct": 4.0, "notes": "", **kw}


def test_planner_schedules_time_exit_and_pre_report_exit():
    state = {"start": None, "trades": {"A-20261016-BBB": open_trade("BBB", "2026-10-16"),
                                       "A-20261110-CCC": open_trade("CCC", "2026-11-10")}}
    pos = {"BBB": {"qty": 10}, "CCC": {"qty": 10}}
    plan = planner.build_plan(TODAY, NEXT, reports(surprise=1.0), {"AAA": price_panel()}, SESSIONS, UNI,
                              {"CCC": pd.Timestamp("2026-11-16")}, ACCOUNT, pos, state)
    reasons = {x["symbol"]: x["reason"] for x in plan["exits"]}
    assert reasons["BBB"].startswith("time exit")  # 2026-10-16 -> 2026-11-13 is 20 sessions
    assert reasons["CCC"].startswith("flat before report")


# ---------------------------------------------------------------- fake broker
class FakeBroker:
    def __init__(self, account=None, positions=None, orders=None):
        self.acct = dict(account or ACCOUNT)
        self.pos = positions or {}
        self._orders = orders or []
        self.sent, self.cancelled = [], []

    def account(self):
        return self.acct

    def positions(self):
        return self.pos

    def orders(self, status="all", after=None, symbols=None):
        return [o for o in self._orders if symbols is None or o["symbol"] in symbols]

    def order_by_client_id(self, cid):
        return next((o for o in self._orders if o["client_order_id"] == cid), None)

    def submit_bracket(self, symbol, qty, limit, take_profit, stop, client_order_id):
        o = order(symbol, "buy", "limit", "new", client_order_id=client_order_id, qty=qty)
        self.sent.append(("bracket", symbol, qty, limit, take_profit, stop, client_order_id))
        self._orders.append(o)
        return o

    def submit_market_on_open_sell(self, symbol, qty, client_order_id):
        self.sent.append(("moo_sell", symbol, qty, client_order_id))
        return order(symbol, "sell", "market", "accepted", client_order_id=client_order_id, qty=qty)

    def cancel(self, order_id):
        self.cancelled.append(order_id)


def order(symbol, side, type_, status, client_order_id="", qty=10, filled_qty=0, price=None, filled_at=None,
          legs=None, id_=None):
    return {"id": id_ or f"{symbol}-{type_}-{status}", "client_order_id": client_order_id, "symbol": symbol,
            "side": side, "type": type_, "status": status, "qty": qty, "filled_qty": filled_qty,
            "filled_avg_price": price, "filled_at": filled_at, "legs": legs or []}


PLAN = {"session": "2026-11-13", "exits": [], "entries": [
    {"trade_id": "A-20261113-AAA", "symbol": "AAA", "sector": "Tech", "signal_date": "2026-11-12",
     "entry_date": "2026-11-13", "limit": 100.5, "stop": 96.0, "target": 114.0, "qty": 14,
     "eps_surprise_pct": 12.0, "gap_pct": 5.0, "notes": "", "exit_by": None}]}


# ---------------------------------------------------------------- submitter
def test_submit_sends_bracket_with_trade_id():
    b, state = FakeBroker(), empty_state()
    out = submitter.submit(PLAN, b, state, {}, send=True, kill_switch=False)
    assert b.sent == [("bracket", "AAA", 14, 100.5, 114.0, 96.0, "A-20261113-AAA")]
    assert state["trades"]["A-20261113-AAA"]["status"] == "submitted" and not out["errors"]


def test_dry_run_and_kill_switch_send_nothing():
    b = FakeBroker()
    out = submitter.submit(PLAN, b, empty_state(), {}, send=False, kill_switch=False)
    assert b.sent == [] and out["sent"]  # dry run reports what it would do
    b2 = FakeBroker()
    out2 = submitter.submit(PLAN, b2, empty_state(), {}, send=True, kill_switch=True)
    assert b2.sent == [] and "kill switch" in out2["skipped"][0]["reason"]


def test_daily_loss_limit_blocks_entries():
    b = FakeBroker(account={**ACCOUNT, "equity": 9_790.0})
    out = submitter.submit(PLAN, b, empty_state(), {}, send=True, kill_switch=False)
    assert b.sent == [] and "daily loss" in out["skipped"][0]["reason"]


def test_no_duplicate_submission_and_sector_limit():
    b = FakeBroker(orders=[order("AAA", "buy", "limit", "new", client_order_id="A-20261113-AAA")])
    out = submitter.submit(PLAN, b, empty_state(), {}, send=True, kill_switch=False)
    assert b.sent == [] and out["skipped"][0]["reason"] == "already submitted"
    b2 = FakeBroker(positions={"X1": {"qty": 5}, "X2": {"qty": 5}})
    out2 = submitter.submit(PLAN, b2, empty_state(), {"X1": "Tech", "X2": "Tech"}, send=True, kill_switch=False)
    assert b2.sent == [] and "max 2 positions in Tech" in out2["skipped"][0]["reason"]


def test_exit_cancels_legs_then_sends_market_on_open():
    leg = order("BBB", "sell", "stop", "held", id_="leg-stop")
    parent = order("BBB", "buy", "limit", "filled", filled_qty=10, legs=[leg], id_="parent")
    b = FakeBroker(positions={"BBB": {"qty": 10}}, orders=[parent])
    state = {"start": None, "trades": {"A-20261016-BBB": open_trade()}}
    plan = {"session": "2026-11-13", "entries": [],
            "exits": [{"trade_id": "A-20261016-BBB", "symbol": "BBB", "qty": 10, "reason": "time exit (20 sessions)"}]}
    submitter.submit(plan, b, state, {}, send=True, kill_switch=False)
    assert b.cancelled == ["leg-stop"]
    assert b.sent == [("moo_sell", "BBB", 10, "A-20261016-BBB-exit")]


# ---------------------------------------------------------------- reconciler
def submitted(tid="A-20261113-AAA", sym="AAA"):
    return {"setup": "A", "variant": "ema+fixed", "status": "submitted", "symbol": sym, "sector": "Tech",
            "signal_date": "2026-11-12", "entry_date": "2026-11-13", "ref_price": 100.5, "stop": 96.0,
            "target": 114.0, "qty_ordered": 14, "order_id": "x", "eps_surprise_pct": 12.0, "gap_pct": 5.0,
            "notes": ""}


def test_reconcile_fill_and_unfilled_cancel():
    filled = order("AAA", "buy", "limit", "filled", client_order_id="A-20261113-AAA", filled_qty=14, price=100.2,
                   filled_at="2026-11-13T14:30:05+00:00",
                   legs=[order("AAA", "sell", "stop", "new", id_="s1")])
    unfilled = order("CCC", "buy", "limit", "new", client_order_id="A-20261113-CCC", id_="c1")
    state = {"start": None, "trades": {"A-20261113-AAA": submitted(), "A-20261113-CCC": submitted("A-20261113-CCC", "CCC")}}
    b = FakeBroker(positions={"AAA": {"qty": 14}}, orders=[filled, unfilled])
    out = reconciler.reconcile(b, state, pd.Timestamp("2026-11-13"), send=True)
    assert state["trades"]["A-20261113-AAA"]["status"] == "open"
    assert state["trades"]["A-20261113-AAA"]["entry_price"] == 100.2
    assert state["trades"]["A-20261113-CCC"]["status"] == "cancelled" and b.cancelled == ["c1"]
    assert not out["warnings"]  # AAA has a working stop


def test_reconcile_closes_trade_on_stop_and_warns_when_no_stop():
    t = {**submitted(), "status": "open", "shares": 14, "entry_price": 100.2}
    stop_fill = order("AAA", "sell", "stop", "filled", filled_qty=14, price=95.9, filled_at="2026-11-17T15:00:00+00:00")
    parent = order("AAA", "buy", "limit", "filled", filled_qty=14, legs=[stop_fill])
    state = {"start": None, "trades": {"A-20261113-AAA": t, "A-20261110-BBB": open_trade("BBB", "2026-11-10")}}
    b = FakeBroker(positions={"BBB": {"qty": 10}}, orders=[parent])
    out = reconciler.reconcile(b, state, pd.Timestamp("2026-11-17"), send=True)
    closed = state["trades"]["A-20261113-AAA"]
    assert closed["status"] == "closed" and closed["exit_reason"] == "stop" and closed["exit_date"] == "2026-11-17"
    assert any("NO working stop" in w and "BBB" in w for w in out["warnings"])
    df = journal.journal_frame(state)
    assert list(df.columns) == JOURNAL_COLUMNS
    row = df[df.trade_id == "A-20261113-AAA"].iloc[0]
    assert row.r_multiple == pytest.approx((95.9 - 100.2) / (100.5 - 96.0), abs=1e-3)
    assert row.pnl_usd == pytest.approx((95.9 - 100.2) * 14)
