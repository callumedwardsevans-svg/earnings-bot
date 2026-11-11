"""Refresh the local data cache.

Examples:
    python scripts/update_data.py                      # calendar + universe + prices (S&P 500 + SPY)
    python scripts/update_data.py --earnings-backfill  # also spend today's Alpha Vantage budget
    python scripts/update_data.py --symbols NVDA SPY   # just these symbols
    python scripts/update_data.py --finnhub-weeks 6    # forward/recent earnings calendar
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from collections import Counter
from datetime import date, timedelta

from earnings_bot.broker import make_trading_client
from earnings_bot.config import load_settings
from earnings_bot.data import calendar, earnings, prices, universe

BENCHMARK = "SPY"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", nargs="*", help="default: S&P 500 + SPY")
    ap.add_argument("--skip-prices", action="store_true")
    ap.add_argument("--earnings-backfill", action="store_true", help="fetch uncached AV histories (25/day)")
    ap.add_argument("--finnhub-weeks", type=int, default=0, help="fetch Finnhub calendar +/- N weeks")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()

    calendar.load_sessions(make_trading_client(settings))
    uni = universe.load_sp500()
    symbols = args.symbols or sorted(set(uni.symbol) | {BENCHMARK})

    if not args.skip_prices:
        status = prices.update_prices(prices.make_data_client(settings), symbols)
        counts = Counter(s.split(":")[0] for s in status.values())
        print(f"Prices: {dict(counts)}")
        for sym, s in status.items():
            if s.startswith(("error", "no data")):
                print(f"  {sym}: {s}")

    if args.earnings_backfill:
        if not settings.alphavantage_api_key:
            print("ALPHAVANTAGE_API_KEY missing", file=sys.stderr)
            return 1
        # Fixed-seed shuffle: while the 25/day backfill is incomplete, the cached
        # subset is a random sample of the index rather than just A-to-M tickers.
        targets = [s for s in symbols if s != BENCHMARK]
        random.Random(42).shuffle(targets)
        budget = earnings.AlphaVantageBudget()
        status = earnings.backfill_av(targets, settings.alphavantage_api_key, budget)
        cached = sum(earnings.av_raw_path(s).exists() for s in targets)
        print(
            f"Alpha Vantage: fetched {sum(v == 'fetched' for v in status.values())} today, "
            f"{cached}/{len(targets)} symbols cached, {budget.remaining()} calls left today"
        )
        hist = earnings.build_history()
        print(f"Earnings history: {len(hist)} reports, {hist.symbol.nunique()} symbols")

    if args.finnhub_weeks:
        if not settings.finnhub_api_key:
            print("FINNHUB_API_KEY missing", file=sys.stderr)
            return 1
        wk = timedelta(weeks=args.finnhub_weeks)
        cal = earnings.fetch_finnhub_calendar(date.today() - wk, date.today() + wk, settings.finnhub_api_key)
        print(f"Finnhub calendar: {len(cal)} rows, timing: {cal.report_time.value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
