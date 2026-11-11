"""Backtest setups A and B, every variant, against SPY buy-and-hold.

Usage:
    python scripts/run_backtest.py              # in-sample period only (default)
    python scripts/run_backtest.py --holdout --final-check
        # the held-out last 12 months. Run this once, after the variants to trade
        # have been chosen from the in-sample results, and don't tune afterwards.

Outputs under docs/backtest/<period>/: summary.md, per-run trades.csv / skipped.csv /
equity.png, and one equity chart per setup comparing all variants with SPY.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import pandas as pd  # noqa: E402

from earnings_bot.backtest import metrics, portfolio  # noqa: E402
from earnings_bot.backtest.simulate import simulate_all  # noqa: E402
from earnings_bot.config import (  # noqa: E402
    BACKTEST_END, BACKTEST_START, BACKTEST_START_EQUITY, HOLDOUT_START, PROJECT_ROOT, SETUP_A, SETUP_B,
)
from earnings_bot.data import calendar, history, prices, universe  # noqa: E402
from earnings_bot.indicators import add_indicators  # noqa: E402
from earnings_bot.signals import setup_a, setup_b  # noqa: E402

# Reference palette (light mode), fixed order; SPY is a neutral benchmark, not a series hue.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SPY_GREY = "#8c8b86"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"

RUNS = [
    ("A", "ema+fixed", dict(ema_filter=True, trailing=False)),
    ("A", "noema+fixed", dict(ema_filter=False, trailing=False)),
    ("A", "ema+trail", dict(ema_filter=True, trailing=True)),
    ("A", "noema+trail", dict(ema_filter=False, trailing=True)),
    ("B", "ema", dict(ema_filter=True)),
    ("B", "noema", dict(ema_filter=False)),
]


def style_axes(ax, title: str):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")


def plot_curves(curves: dict[str, pd.Series], spy: pd.Series, title: str, path):
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
    style_axes(ax, title)
    ax.plot(spy.index, spy.values, color=SPY_GREY, linewidth=1.6, linestyle="--", label="SPY buy & hold")
    for (name, s), color in zip(curves.items(), SERIES):
        ax.plot(s.index, s.values, color=color, linewidth=2, label=name)
    # End-of-line labels, nudged apart vertically so they never overlap.
    labels = sorted([(s.iloc[-1], f"{n}  ${s.iloc[-1]:,.0f}", s.index[-1])
                     for n, s in [("SPY", spy), *curves.items()]])
    lo, hi = ax.get_ylim()
    gap, placed = (hi - lo) * 0.045, []
    for y, text, x in labels:
        y_text = max(y, placed[-1] + gap) if placed else y
        placed.append(y_text)
        ax.annotate(text, (x, y), xytext=(x + pd.Timedelta(days=40), y_text), textcoords="data",
                    va="center", fontsize=8, color=INK2, annotation_clip=False)
    ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=INK2)
    fig.tight_layout()
    fig.subplots_adjust(right=0.86)
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def fmt_pct(x):
    return "n/a" if pd.isna(x) else f"{x:+.1%}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--final-check", action="store_true", help="required with --holdout")
    args = ap.parse_args()
    if args.holdout and not args.final_check:
        print("The held-out period is for the final check only. Re-run with --holdout --final-check "
              "once the variants are chosen.", file=sys.stderr)
        return 2
    period = "holdout" if args.holdout else "in_sample"
    start = HOLDOUT_START if args.holdout else BACKTEST_START
    end = BACKTEST_END if args.holdout else str((pd.Timestamp(HOLDOUT_START) - pd.Timedelta(days=1)).date())
    out_dir = PROJECT_ROOT / "docs" / "backtest" / period
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions_all = calendar.load_sessions()
    sessions = sessions_all[(sessions_all >= pd.Timestamp(start)) & (sessions_all <= pd.Timestamp(end))]
    uni = universe.load_sp500()
    hist = history.load_history()
    px = {}
    for s in sorted(set(uni.symbol) | {"SPY"}):
        df = prices.load_prices(s)
        if df is not None and len(df) > 60:
            px[s] = add_indicators(df, SETUP_A.ema_trend_period, SETUP_A.atr_period,
                                   ema_rising_lookback=SETUP_B.ema_rising_lookback)
    spy_stats, spy_eq = metrics.benchmark(px["SPY"], sessions[0], sessions[-1], BACKTEST_START_EQUITY)

    rows, signal_rows, funnels, yearly, curves = [], [], {}, {}, {"A": {}, "B": {}}
    skip_reasons = {}
    for setup, variant, kw in RUNS:
        gen = setup_a.generate if setup == "A" else setup_b.generate
        cands, funnel = gen(hist, px, sessions_all, uni, start, end, **kw)
        sims = simulate_all(cands, px, end)
        funnels[(setup, variant)] = funnel

        # Signal level: every filled signal, ignoring portfolio limits and account size.
        filled = sims[sims.filled]
        signal_rows.append({"setup": setup, "variant": variant, "signals": len(sims),
                            "fill_rate": len(filled) / len(sims) if len(sims) else float("nan"),
                            **metrics.trade_stats(filled.r_multiple)})
        yearly[(setup, variant)] = filled.groupby(filled.entry_date.dt.year).r_multiple.agg(["count", "mean"])

        for mf in (False, True):
            trades, skipped, curve = portfolio.run(sims, px, sessions, membership_filter=mf)
            m = portfolio_metrics = metrics.portfolio_metrics(trades, curve)
            rows.append({"setup": setup, "variant": variant, "membership_filter": mf, **portfolio_metrics})
            if not mf:
                run_dir = out_dir / f"{setup}_{variant.replace('+', '_')}"
                run_dir.mkdir(exist_ok=True)
                trades.to_csv(run_dir / "trades.csv", index=False)
                skipped.to_csv(run_dir / "skipped.csv", index=False)
                curve.to_csv(run_dir / "equity.csv")
                (run_dir / "metrics.json").write_text(json.dumps({**m, "funnel": funnel}, indent=2, default=str))
                plot_curves({f"{setup} {variant}": curve.equity}, spy_eq,
                            f"Setup {setup} ({variant}) vs SPY, {period.replace('_', '-')}", run_dir / "equity.png")
                curves[setup][variant] = curve.equity
                skip_reasons[(setup, variant)] = Counter(skipped.reason) if len(skipped) else Counter()
        print(f"{setup} {variant}: {len(sims)} signals, {rows[-2]['trades']} portfolio trades, "
              f"expectancy {rows[-2]['expectancy_r']:.2f}R")

    for setup in ("A", "B"):
        plot_curves(curves[setup], spy_eq, f"Setup {setup}: all variants vs SPY, {period.replace('_', '-')}",
                    out_dir / f"equity_setup_{setup}.png")

    write_summary(out_dir, period, start, end, pd.DataFrame(rows), pd.DataFrame(signal_rows), funnels,
                  yearly, skip_reasons, spy_stats)
    print(f"Written to {out_dir.relative_to(PROJECT_ROOT)}")
    return 0


def write_summary(out_dir, period, start, end, port, sig, funnels, yearly, skip_reasons, spy):
    L = [f"# Backtest results: {period.replace('_', '-')} ({start} to {end})", ""]
    L += ["Starting equity $10,000; risk 0.75%/trade, max 15% per position, max 5 positions (2 per sector), "
          "2% daily loss limit; whole shares; 5 bps slippage per fill; $0 commission.", ""]

    L += ["## 1. Signal level (every filled signal, no portfolio limits)", "",
          "This is the cleanest test of whether the setup has an edge, because it isn't affected by account size "
          "or which signals happened to overlap. `se` = standard error of the mean R; an expectancy within about "
          "2 se of zero isn't distinguishable from no edge.", ""]
    t = sig.assign(**{
        "fill rate": sig.fill_rate.map("{:.0%}".format), "win rate": sig.win_rate.map("{:.0%}".format),
        "avg win R": sig.avg_win_r.round(2), "avg loss R": sig.avg_loss_r.round(2),
        "expectancy R": sig.expectancy_r.round(3), "se": sig.expectancy_se.round(3),
        "t-stat": (sig.expectancy_r / sig.expectancy_se).round(2)})
    L += [t[["setup", "variant", "signals", "fill rate", "trades", "win rate", "avg win R", "avg loss R",
             "expectancy R", "se", "t-stat"]].to_markdown(index=False), ""]

    L += ["## 2. Portfolio ($10k account, all limits applied) vs SPY", ""]
    p = port[~port.membership_filter]
    pt = p.assign(**{
        "win rate": p.win_rate.map("{:.0%}".format), "avg win R": p.avg_win_r.round(2),
        "avg loss R": p.avg_loss_r.round(2), "expectancy R": p.expectancy_r.round(3),
        "total return": p.total_return.map(fmt_pct), "CAGR": p.cagr.map(fmt_pct),
        "max DD": p.max_drawdown.map(fmt_pct), "Sharpe": p.sharpe.round(2),
        "exposure (time)": p.exposure_time.map("{:.0%}".format),
        "avg capital deployed": p.avg_gross_exposure.map("{:.0%}".format)})
    L += [pt[["setup", "variant", "trades", "win rate", "avg win R", "avg loss R", "expectancy R", "total return",
              "CAGR", "max DD", "Sharpe", "exposure (time)", "avg capital deployed"]].to_markdown(index=False), ""]
    L += [f"**SPY buy & hold:** total return {fmt_pct(spy['total_return'])}, CAGR {fmt_pct(spy['cagr'])}, "
          f"max DD {fmt_pct(spy['max_drawdown'])}, Sharpe {spy['sharpe']:.2f}, exposure 100%.", "",
          "![Setup A](equity_setup_A.png)", "", "![Setup B](equity_setup_B.png)", ""]

    L += ["## 3. Robustness: only signals after the stock joined the S&P 500", "",
          "Partly addresses survivorship bias: drops signals from before a stock was in the index (using today's "
          "list's 'date added'). It can't add back the ~22% of names that left the index.", ""]
    m = port[port.membership_filter]
    L += [m.assign(**{"expectancy R": m.expectancy_r.round(3), "total return": m.total_return.map(fmt_pct),
                      "Sharpe": m.sharpe.round(2), "max DD": m.max_drawdown.map(fmt_pct)})
          [["setup", "variant", "trades", "expectancy R", "total return", "max DD", "Sharpe"]].to_markdown(index=False), ""]

    L += ["## 4. Expectancy by year (signal level, R per trade; trade count in brackets)", ""]
    years = sorted({y for v in yearly.values() for y in v.index})
    yt = pd.DataFrame({f"{s} {v}": {y: (f"{g.loc[y, 'mean']:+.2f} ({int(g.loc[y, 'count'])})" if y in g.index else "")
                                    for y in years} for (s, v), g in yearly.items()})
    L += [yt.to_markdown(), ""]

    L += ["## 5. Signal funnel (how many reports survive each filter)", ""]
    for key in [("A", "ema+fixed"), ("A", "noema+fixed"), ("B", "ema"), ("B", "noema")]:
        f = funnels[key]
        L += [f"**Setup {key[0]} ({key[1]})**: " + " → ".join(f"{k} **{v:,}**" for k, v in f.items()), ""]

    L += ["## 6. Why portfolio signals were skipped", ""]
    for (s, v), c in skip_reasons.items():
        L += [f"- **{s} {v}**: " + (", ".join(f"{r} ({n})" for r, n in c.most_common()) or "none")]
    (out_dir / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
