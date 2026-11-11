"""Milestone 1: connect to the Alpaca paper account and print equity.

Usage:  python scripts/check_account.py
"""

from __future__ import annotations

import sys

from earnings_bot.broker import LiveTradingRefused, make_trading_client
from earnings_bot.config import EXPECTED_STARTING_EQUITY, RISK, load_settings


def main() -> int:
    settings = load_settings()
    try:
        client = make_trading_client(settings)
    except (LiveTradingRefused, RuntimeError) as exc:
        print(f"Refusing to start: {exc}", file=sys.stderr)
        return 1

    acct = client.get_account()
    equity = float(acct.equity)
    acct_no = str(acct.account_number)

    print("Connected to Alpaca PAPER account")
    print(f"  account       : ****{acct_no[-4:]}  (status {getattr(acct.status, 'value', acct.status)})")
    print(f"  equity        : ${equity:,.2f}")
    print(f"  cash          : ${float(acct.cash):,.2f}")
    print(f"  buying power  : ${float(acct.buying_power):,.2f}")
    print(f"  last equity   : ${float(acct.last_equity):,.2f}  (previous close)")
    print(f"  trading blocked: {acct.trading_blocked}")
    print()
    print("Risk limits at this equity:")
    print(f"  risk per trade (0.75%) : ${equity * RISK.risk_per_trade_pct:,.2f}")
    print(f"  max position  (15%)    : ${equity * RISK.max_position_pct:,.2f}")
    print(f"  daily loss stop (2%)   : ${equity * RISK.daily_loss_limit_pct:,.2f}")

    if abs(equity - EXPECTED_STARTING_EQUITY) / EXPECTED_STARTING_EQUITY > 0.10:
        print(
            f"\nNOTE: equity differs from the expected ~${EXPECTED_STARTING_EQUITY:,.0f}. "
            "Check you're using the right paper account's keys."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
