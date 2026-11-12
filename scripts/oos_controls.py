"""Post-hoc controls for the 2002-2015 out-of-sample result (NOT part of the pre-registration).

Question: is Setup A's market-adjusted excess return a PEAD effect, or just that today's
S&P 500 members (the survivors) beat SPY whatever you do with them?

Control: every report with known timing in the same stocks, entered and exited with the
same machinery (day-2 open limit, stop = max(day-1 low, limit - 2 ATR), 3R target, 20-day
time exit, flat before next report) but with none of the PEAD filters (surprise, gap,
close-in-range, volume, EMA). Liquidity filter kept. Its market-adjusted R is the
"anything in these stocks" baseline; Setup A's edge is its excess over that baseline.

Usage:  python scripts/oos_controls.py
"""

from __future__ import annotations

import dataclasses
import sys

import numpy as np
import pandas as pd

from earnings_bot.backtest import metrics
from earnings_bot.backtest.simulate import simulate_all
from earnings_bot.config import PROJECT_ROOT, SETUP_A, SETUP_B
from earnings_bot.data import calendar, history, prices, universe, yahoo_prices
from earnings_bot.indicators import add_indicators
from earnings_bot.signals import setup_a

NO_FILTERS = dataclasses.replace(SETUP_A, min_eps_surprise_pct=-1e9, min_gap_pct=-1e9, min_close_in_range=0.0,
                                 min_volume_multiple=0.0)
PERIODS = {
    "2002-2015 (Yahoo prices)": ("2002-01-01", "2015-12-31", "2016-03-31", "yahoo"),
    "2016-2025 (Alpaca prices)": ("2016-04-01", "2025-11-10", "2025-11-10", "alpaca"),
}


def ind(df):
    return add_indicators(df, SETUP_A.ema_trend_period, SETUP_A.atr_period,
                          ema_rising_lookback=SETUP_B.ema_rising_lookback)


def summarise(name, sims, spy):
    f = metrics.market_adjust(sims[sims.filled], spy)
    se = f.excess_r.std(ddof=1) / np.sqrt(len(f))
    return f, {"group": name, "trades": len(f), "expectancy R": round(f.r_multiple.mean(), 3),
               "market-adjusted R": round(f.excess_r.mean(), 3), "se": round(se, 3),
               "t (weekly)": round(metrics.clustered_t(f.excess_r, f.entry_date), 2)}


def main() -> int:
    sessions = calendar.load_sessions()
    uni, hist = universe.load_sp500(), history.load_history()
    L = ["# Post-hoc controls for the out-of-sample result", "", (__doc__ or "").split("Usage:")[0].strip(), ""]
    for label, (start, end, last, src) in PERIODS.items():
        px = {}
        for s in sorted(set(uni.symbol) | {"SPY"}):
            df = (yahoo_prices.load_history_range(s, "2001-01-01", "2016-04-01") if src == "yahoo"
                  else prices.load_prices(s))
            if df is not None and len(df) > 60:
                px[s] = ind(df)
        spy = px["SPY"]
        a, _ = setup_a.generate(hist, px, sessions, uni, start, end, ema_filter=True, trailing=False)
        c, _ = setup_a.generate(hist, px, sessions, uni, start, end, ema_filter=False, trailing=False, p=NO_FILTERS)
        fa, ra = summarise("Setup A (ema+fixed)", simulate_all(a, px, last), spy)
        fc, rc = summarise("Control: all reports, no PEAD filters", simulate_all(c, px, last), spy)
        rows = [ra, rc]
        # Only signals where the stock was already in the index (removes 'future joiners')
        for name, f in (("Setup A, already in S&P 500", fa), ("Control, already in S&P 500", fc)):
            g = f[f.date_added.notna() & (f.date_added <= f.signal_date)]
            rows.append({"group": name, "trades": len(g), "expectancy R": round(g.r_multiple.mean(), 3),
                         "market-adjusted R": round(g.excess_r.mean(), 3),
                         "se": round(g.excess_r.std(ddof=1) / np.sqrt(len(g)), 3),
                         "t (weekly)": round(metrics.clustered_t(g.excess_r, g.entry_date), 2)})
        diff = fa.excess_r.mean() - fc.excess_r.mean()
        se_diff = np.sqrt(fa.excess_r.var(ddof=1) / len(fa) + fc.excess_r.var(ddof=1) / len(fc))
        L += [f"## {label}", "", pd.DataFrame(rows).to_markdown(index=False), "",
              f"**Setup A minus control (market-adjusted): {diff:+.3f}R (se {se_diff:.3f}, t ≈ {diff / se_diff:.2f}).**",
              ""]
        print(label, f"A-minus-control {diff:+.3f}R (t~{diff / se_diff:.2f})")
    out = PROJECT_ROOT / "docs" / "backtest" / "oos_2002_2015" / "controls.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out.relative_to(PROJECT_ROOT), "written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
