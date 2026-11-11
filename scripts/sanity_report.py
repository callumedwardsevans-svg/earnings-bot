"""Milestone 2 sanity check: a symbol's last N reports with timing, surprise, and the day-1 reaction.

If the before/after-close timing is right, the big gap and volume spike should land
on the computed day 1, not the session before or after it.

Usage:  python scripts/sanity_report.py NVDA [-n 8]
Writes docs/sanity/<SYMBOL>.md as well as printing it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

from earnings_bot.broker import make_trading_client
from earnings_bot.config import PROJECT_ROOT, load_settings
from earnings_bot.data import calendar, earnings, prices, quality


def day_stats(px: pd.DataFrame, day: pd.Timestamp) -> dict:
    """Gap, close-in-range and volume multiple for one session."""
    if day not in px.index:
        return {}
    i = px.index.get_loc(day)
    row, prev_close = px.iloc[i], px.close.iloc[i - 1]
    avg_vol = px.volume.iloc[max(i - 20, 0) : i].mean()  # 20 sessions before, excludes the day
    rng = row.high - row.low
    return {
        "gap_pct": (row.open / prev_close - 1) * 100,
        "day_ret_pct": (row.close / prev_close - 1) * 100,
        "close_in_range": (row.close - row.low) / rng if rng else np.nan,
        "vol_x": row.volume / avg_vol,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("-n", type=int, default=8)
    args = ap.parse_args()
    sym = args.symbol.upper()

    settings = load_settings()
    sessions = calendar.load_sessions(make_trading_client(settings))
    prices.update_prices(prices.make_data_client(settings), [sym])
    px = prices.load_prices(sym)

    raw = earnings.fetch_av_earnings(sym, settings.alphavantage_api_key, earnings.AlphaVantageBudget())
    hist = earnings.normalize_av(sym, raw)
    hist = hist.sort_values("report_date")
    hist = hist[hist.report_date <= pd.Timestamp(px.index.max())].tail(args.n).iloc[::-1]

    # Finnhub cross-check for whichever recent reports its free tier still covers.
    fh = earnings.fetch_finnhub_calendar(
        date.today() - timedelta(days=100), date.today(), settings.finnhub_api_key
    )
    fh = fh[fh.symbol == sym].set_index("report_date")

    rows = []
    for r in hist.itertuples():
        d1 = calendar.day1_session(r.report_date, r.report_time, sessions)
        prev = calendar.previous_session(d1, sessions) if d1 is not None else None
        s1, s0 = (day_stats(px, d1) if d1 is not None else {}), (day_stats(px, prev) if prev is not None else {})
        f = fh.loc[r.report_date] if r.report_date in fh.index else None
        chk = quality.check_one(r.report_date, r.report_time, px, sessions)
        rows.append(
            {
                "report_date": r.report_date.date(),
                "fiscal_q_end": r.fiscal_date_ending.date(),
                "timing": r.report_time,
                "day1": d1.date() if d1 is not None else "FLAGGED",
                "eps_est": r.eps_estimate,
                "eps_act": r.eps_actual,
                "surprise_%": r.surprise_pct,
                "day1_gap_%": s1.get("gap_pct"),
                "day1_ret_%": s1.get("day_ret_pct"),
                "day1_close_pos": s1.get("close_in_range"),
                "day1_vol_x20d": s1.get("vol_x"),
                "prev_day_vol_x20d": s0.get("vol_x"),
                "timing_check": chk["timing_check"],
                "finnhub": "-" if f is None else f"{f.report_time}, eps {f.eps_actual} vs {f.eps_estimate}",
            }
        )
    df = pd.DataFrame(rows)

    flagged = (df.day1 == "FLAGGED").sum()
    peak_ok = (df.day1_vol_x20d > df.prev_day_vol_x20d).sum()
    md = [
        f"# Earnings sanity report: {sym}",
        "",
        f"Generated {date.today()} from Alpha Vantage `EARNINGS` (dates, timing, EPS), "
        "Alpaca SIP daily bars (split/dividend adjusted), and the Finnhub calendar as a cross-check.",
        "",
        "- `day1` = first session after an after-close (amc) report, or the same session for a before-open (bmo) report.",
        "- `day1_vol_x20d` = day-1 volume / average of the prior 20 sessions; `prev_day_vol_x20d` is the same for the session before day 1.",
        "  If timing is right, the spike is on day 1, not the day before.",
        "- `day1_close_pos` = where the close sits in the day's range (1 = high).",
        "",
        df.to_markdown(index=False, floatfmt=".2f"),
        "",
        f"Volume spike on computed day 1 rather than the prior session: **{peak_ok}/{len(df)}**. "
        f"Reports with unknown timing (flagged, not guessed): **{flagged}**.",
    ]
    text = "\n".join(md)
    out = PROJECT_ROOT / "docs" / "sanity" / f"{sym}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nWritten to {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
