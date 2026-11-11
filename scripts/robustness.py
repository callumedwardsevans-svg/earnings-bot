"""Market-adjusted and clustered-error checks on the signal-level results (in-sample).

For each filled signal: excess return = stock return - SPY return over the same
entry-to-exit window, expressed in R (divided by initial risk as a % of entry).
t-stats use weekly clusters (mean R per entry week), since signals bunch in earnings
seasons and move with the market, so they aren't independent trades.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from earnings_bot.backtest.simulate import simulate_all
from earnings_bot.config import BACKTEST_END, BACKTEST_START, HOLDOUT_START, PROJECT_ROOT, SETUP_A, SETUP_B
from earnings_bot.data import calendar, history, prices, universe
from earnings_bot.indicators import add_indicators
from earnings_bot.signals import setup_a, setup_b

RUNS = [("A", "ema+fixed", dict(ema_filter=True, trailing=False)), ("A", "noema+fixed", dict(ema_filter=False, trailing=False)),
        ("A", "ema+trail", dict(ema_filter=True, trailing=True)), ("A", "noema+trail", dict(ema_filter=False, trailing=True)),
        ("B", "ema", dict(ema_filter=True)), ("B", "noema", dict(ema_filter=False))]


def clustered_t(r: pd.Series, dates: pd.Series) -> float:
    weekly = r.groupby(dates.dt.to_period("W")).mean()
    return float(weekly.mean() / (weekly.std(ddof=1) / np.sqrt(len(weekly))))


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--final-check", action="store_true")
    ap.add_argument("--only", help="e.g. A:ema+fixed")
    args = ap.parse_args()
    if args.holdout and not args.final_check:
        raise SystemExit("Use --holdout --final-check for the held-out period.")
    start = HOLDOUT_START if args.holdout else BACKTEST_START
    end = BACKTEST_END if args.holdout else str((pd.Timestamp(HOLDOUT_START) - pd.Timedelta(days=1)).date())
    runs = [r for r in RUNS if not args.only or f"{r[0]}:{r[1]}" == args.only]
    sessions = calendar.load_sessions()
    uni, hist = universe.load_sp500(), history.load_history()
    px = {s: add_indicators(d, SETUP_A.ema_trend_period, SETUP_A.atr_period, ema_rising_lookback=SETUP_B.ema_rising_lookback)
          for s in sorted(set(uni.symbol) | {"SPY"}) if (d := prices.load_prices(s)) is not None and len(d) > 60}
    spy = px["SPY"]
    rows = []
    for setup, variant, kw in runs:
        gen = setup_a.generate if setup == "A" else setup_b.generate
        cands, _ = gen(hist, px, sessions, uni, start, end, **kw)
        s = simulate_all(cands, px, end)
        s = s[s.filled].copy()
        # SPY over the same window: entry at the same price point (open for A, close for B) to exit close
        spy_in = np.where(s.entry_type == "open_limit", spy.open.reindex(s.entry_date).values, spy.close.reindex(s.entry_date).values)
        spy_out = spy.close.reindex(s.exit_date).values
        risk_pct = s.initial_risk / s.entry_price
        s["spy_r"] = (spy_out / spy_in - 1) / risk_pct
        s["excess_r"] = s.r_multiple - s.spy_r
        s["hold"] = [sessions.searchsorted(b) - sessions.searchsorted(a) for a, b in zip(s.entry_date, s.exit_date)]
        rows.append({"setup": setup, "variant": variant, "trades": len(s),
                     "avg hold (sessions)": round(s.hold.mean(), 1),
                     "expectancy R": round(s.r_multiple.mean(), 3), "t (naive)": round(s.r_multiple.mean() / (s.r_multiple.std() / np.sqrt(len(s))), 2),
                     "t (weekly clusters)": round(clustered_t(s.r_multiple, s.entry_date), 2),
                     "SPY over same window, R": round(s.spy_r.mean(), 3),
                     "market-adjusted R": round(s.excess_r.mean(), 3),
                     "t market-adj (weekly)": round(clustered_t(s.excess_r, s.entry_date), 2),
                     "exit reasons": ", ".join(f"{k} {v:.0%}" for k, v in s.exit_reason.value_counts(normalize=True).items())})
    df = pd.DataFrame(rows)
    period = "holdout" if args.holdout else "in_sample"
    out = PROJECT_ROOT / "docs" / "backtest" / period / "robustness.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# Robustness checks ({period.replace('_', '-')}, signal level)\n\n" + (__doc__ or "").strip() + "\n\n" + df.to_markdown(index=False) + "\n", encoding="utf-8")
    print(df.drop(columns=["exit reasons"]).to_string(index=False)); print(); print(df[["setup", "variant", "exit reasons"]].to_string(index=False))


if __name__ == "__main__":
    main()
