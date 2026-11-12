"""Reconcile fills against journal/state.json and rewrite journal/trades.csv (no planning).

Usage:  python scripts/reconcile.py [--send]   (--send also cancels unfilled entry orders)
"""
import argparse
import sys

import pandas as pd

from earnings_bot import journal
from earnings_bot.broker import AlpacaBroker, make_trading_client
from earnings_bot.config import load_settings
from earnings_bot.live.reconciler import reconcile

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    args = ap.parse_args()
    state = journal.load_state()
    out = reconcile(AlpacaBroker(make_trading_client(load_settings())), state,
                    pd.Timestamp(pd.Timestamp.now(tz="America/New_York").date()), send=args.send)
    journal.save_state(state)
    journal.write_journal(state)
    print(out)
    sys.exit(1 if out["errors"] else 0)
