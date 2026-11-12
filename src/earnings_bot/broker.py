"""Alpaca wrapper with a paper-only guard.

The guard runs before any client is created. Rules:

* ``https://paper-api.alpaca.markets`` (optionally with a trailing ``/`` or ``/v2``)
  is allowed.
* ``https://api.alpaca.markets`` (live money) is refused unless ``ALLOW_LIVE=true``
  is set *and* a human types the confirmation phrase at an interactive prompt.
  Non-interactive runs (Task Scheduler, CI) can never go live.
* Any other URL (typos, look-alike hosts, plain http) is refused outright.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from urllib.parse import urlparse

from earnings_bot.config import Settings

log = logging.getLogger(__name__)

PAPER_HOST = "paper-api.alpaca.markets"
LIVE_HOST = "api.alpaca.markets"
LIVE_CONFIRM_PHRASE = "I ACCEPT REAL MONEY RISK"


class LiveTradingRefused(RuntimeError):
    """Raised when the configured endpoint is not allowed."""


def _host_of(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme != "https":
        raise LiveTradingRefused(f"Refusing non-https Alpaca URL (scheme={parsed.scheme!r}).")
    if parsed.path.rstrip("/") not in ("", "/v2"):
        raise LiveTradingRefused(f"Unexpected path in Alpaca URL: {parsed.path!r}.")
    return (parsed.hostname or "").lower()


def _interactive_confirm() -> bool:
    if not sys.stdin.isatty():
        return False
    answer = input(
        "\n*** LIVE TRADING REQUESTED: real money will be at risk. ***\n"
        f"Type '{LIVE_CONFIRM_PHRASE}' to continue, anything else to abort: "
    )
    return answer.strip() == LIVE_CONFIRM_PHRASE


def check_endpoint(
    base_url: str,
    allow_live: bool,
    confirm: Callable[[], bool] = _interactive_confirm,
) -> bool:
    """Validate the endpoint. Returns True for paper; raises unless explicitly cleared for live."""
    host = _host_of(base_url)

    if host == PAPER_HOST:
        return True

    if host != LIVE_HOST:
        raise LiveTradingRefused(f"Unrecognised Alpaca host {host!r}; only {PAPER_HOST} is allowed.")

    if not allow_live:
        raise LiveTradingRefused(
            "ALPACA_BASE_URL points at the LIVE endpoint and ALLOW_LIVE is not 'true'. "
            "This project is paper-only; refusing to start."
        )
    if not confirm():
        raise LiveTradingRefused("Live trading confirmation not given; refusing to start.")

    log.warning("LIVE endpoint confirmed by operator. Real money is at risk.")
    return False


def make_trading_client(settings: Settings, confirm: Callable[[], bool] = _interactive_confirm):
    """Build an alpaca-py TradingClient after the paper-only guard passes."""
    is_paper = check_endpoint(settings.alpaca_base_url, settings.allow_live, confirm)
    if not settings.alpaca_key_id or not settings.alpaca_secret_key:
        raise RuntimeError("ALPACA_KEY_ID / ALPACA_SECRET_KEY are missing. Fill them in .env.")

    from alpaca.trading.client import TradingClient  # imported late so tests don't need network

    return TradingClient(settings.alpaca_key_id, settings.alpaca_secret_key, paper=is_paper)


# --------------------------------------------------------------------------- #
# Thin wrapper used by the live loop. Everything returns plain dicts so the loop's
# logic can be tested against a fake broker without network access.
# --------------------------------------------------------------------------- #
def _order_dict(o) -> dict:
    def val(x):
        return getattr(x, "value", x)

    return {
        "id": str(o.id), "client_order_id": o.client_order_id, "symbol": o.symbol, "side": val(o.side),
        "type": val(o.order_type or o.type), "time_in_force": val(o.time_in_force), "status": val(o.status),
        "order_class": val(o.order_class), "qty": float(o.qty or 0), "filled_qty": float(o.filled_qty or 0),
        "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price is not None else None,
        "limit_price": float(o.limit_price) if o.limit_price is not None else None,
        "stop_price": float(o.stop_price) if o.stop_price is not None else None,
        "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
        "filled_at": o.filled_at.isoformat() if o.filled_at else None,
        "legs": [_order_dict(leg) for leg in (o.legs or [])],
    }


class AlpacaBroker:
    """The only place the live loop talks to Alpaca. Construct via ``make_trading_client``."""

    OPEN_STATUSES = {"new", "accepted", "pending_new", "accepted_for_bidding", "partially_filled", "held",
                     "pending_replace", "calculated"}

    def __init__(self, client):
        self.client = client

    def account(self) -> dict:
        a = self.client.get_account()
        return {"equity": float(a.equity), "last_equity": float(a.last_equity), "cash": float(a.cash),
                "status": getattr(a.status, "value", str(a.status)), "trading_blocked": bool(a.trading_blocked)}

    def positions(self) -> dict[str, dict]:
        return {p.symbol: {"qty": float(p.qty), "avg_entry_price": float(p.avg_entry_price),
                           "current_price": float(p.current_price or 0), "unrealized_pl": float(p.unrealized_pl or 0)}
                for p in self.client.get_all_positions()}

    def orders(self, status: str = "all", after=None, symbols=None) -> list[dict]:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        req = GetOrdersRequest(status=QueryOrderStatus(status), after=after, nested=True, limit=500, symbols=symbols)
        return [_order_dict(o) for o in self.client.get_orders(req)]

    def order_by_client_id(self, client_order_id: str) -> dict | None:
        try:
            return _order_dict(self.client.get_order_by_client_id(client_order_id))
        except Exception as exc:  # 404 when the id was never used
            if "404" in str(exc) or "not found" in str(exc).lower():
                return None
            raise

    def submit_bracket(self, symbol: str, qty: int, limit: float, take_profit: float, stop: float,
                       client_order_id: str) -> dict:
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, StopLossRequest, TakeProfitRequest

        req = LimitOrderRequest(
            symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC, limit_price=limit,
            order_class=OrderClass.BRACKET, take_profit=TakeProfitRequest(limit_price=take_profit),
            stop_loss=StopLossRequest(stop_price=stop), client_order_id=client_order_id)
        return _order_dict(self.client.submit_order(req))

    def submit_market_on_open_sell(self, symbol: str, qty: int, client_order_id: str) -> dict:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        req = MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.OPG,
                                 client_order_id=client_order_id)
        return _order_dict(self.client.submit_order(req))

    def cancel(self, order_id: str) -> None:
        self.client.cancel_order_by_id(order_id)
