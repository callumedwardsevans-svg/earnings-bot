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
