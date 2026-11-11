"""Setup D: index trend filter (hold above the moving average, else T-bills) vs buy-and-hold.

Usage:
    python scripts/run_setup_d.py                          # in-sample (up to 2024-11-10)
    python scripts/run_setup_d.py --holdout --final-check  # last 2 years, run once

Pre-registered regime-filter rule (fixed before any results were seen):
    Candidates in order: "EMA 200", then "10-month SMA" (the standard versions; no
    band variants, no picking the best performer). The first candidate that, on SPY
    with T-bill cash, in BOTH the full in-sample period and the recent window
    (2016-04-01 to 2024-11-10):
      * cuts max drawdown by >= 1/3 vs buy-and-hold,
      * gives up <= 1.5 percentage points of CAGR, and
      * has a Sharpe ratio >= buy-and-hold's,
    becomes the market regime filter for setups A/B. If none passes: no filter.
"""

from __future__ import annotations

import argparse
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import pandas as pd  # noqa: E402

from earnings_bot.backtest import switching  # noqa: E402
from earnings_bot.config import PROJECT_ROOT  # noqa: E402
from earnings_bot.data import yahoo_prices  # noqa: E402
from earnings_bot.signals import setup_d  # noqa: E402

HOLDOUT_START = "2024-11-11"
END = "2026-11-10"
RECENT_START = "2016-04-01"
INSTRUMENTS = {"SPY": "SPY (total return)", "QQQ": "QQQ (total return)", "^GSPC": "S&P 500 index (price only)"}
CANDIDATES = ["EMA 200", "10-month SMA"]
EPISODES = {  # SPY peak-to-trough sell-offs
    "2000-02 dot-com": ("2000-03-24", "2002-10-09"),
    "2007-09 GFC": ("2007-10-09", "2009-03-09"),
    "2018 Q4": ("2018-09-20", "2018-12-24"),
    "2020 Covid": ("2020-02-19", "2020-03-23"),
    "2022 bear": ("2022-01-03", "2022-10-12"),
}
SERIES, BH_GREY = ["#2a78d6", "#eb6834"], "#8c8b86"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"


def evaluate(px, sigs, cash, start, end):
    """Stats for buy-and-hold and every variant on [start, end], equity rebased to 1."""
    window = px.loc[start:end]
    rows, curves = [], {}
    bh = switching.buy_and_hold(window)
    rows.append({"variant": "Buy & hold", **switching.stats(bh)})
    curves["Buy & hold"] = bh.equity
    for name, sig in sigs.items():
        # run on the full history so the position entering the window is real, then slice
        res = switching.run(px, sig, cash).loc[start:end].copy()
        res["equity"] = (1 + res.ret.iloc[1:]).cumprod().reindex(res.index).fillna(1.0)
        rows.append({"variant": name, **switching.stats(res)})
        curves[name] = res.equity
    return pd.DataFrame(rows), curves


def fmt(df: pd.DataFrame) -> str:
    return df.assign(
        CAGR=df.CAGR.map("{:+.1%}".format), volatility=df.volatility.map("{:.1%}".format),
        max_drawdown=df.max_drawdown.map("{:.1%}".format), sharpe=df.sharpe.round(2),
        switches_per_year=df.switches_per_year.round(1), time_invested=df.time_invested.map("{:.0%}".format),
    ).rename(columns={"max_drawdown": "max DD", "switches_per_year": "switches/yr",
                      "time_invested": "% invested"}).to_markdown(index=False)


def plot(curves: dict, title: str, path):
    lengths = ["EMA 20", "EMA 50", "EMA 100", "EMA 200", "10-month SMA"]
    fig, axes = plt.subplots(1, 5, figsize=(18, 4), sharey=True, facecolor=SURFACE)
    for ax, base in zip(axes, lengths):
        ax.set_facecolor(SURFACE)
        ax.set_yscale("log")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.grid(axis="y", color=GRID, linewidth=0.8, which="both")
        ax.tick_params(colors=INK2, labelsize=8)
        bh = curves["Buy & hold"]
        ax.plot(bh.index, bh.values, color=BH_GREY, linestyle="--", linewidth=1.4, label="Buy & hold")
        for name, color in zip([base, f"{base} +1% band"], SERIES):
            ax.plot(curves[name].index, curves[name].values, color=color, linewidth=1.6,
                    label="no band" if "band" not in name else "+1% band")
        ax.set_title(base, loc="left", color=INK, fontsize=10, fontweight="bold")
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.2g}"))
        ax.yaxis.set_minor_formatter(mtick.NullFormatter())
    axes[0].set_ylabel("Growth of $1 (log scale)", color=INK2, fontsize=9)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=SURFACE)
    plt.close(fig)


def passes(row, bh) -> bool:
    return (row.max_drawdown >= bh.max_drawdown * 2 / 3 and row.CAGR >= bh.CAGR - 0.015
            and row.sharpe >= bh.sharpe)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--final-check", action="store_true")
    args = ap.parse_args()
    if args.holdout and not args.final_check:
        print("Held-out years are for the final check: use --holdout --final-check.", file=sys.stderr)
        return 2
    period = "holdout" if args.holdout else "in_sample"
    out = PROJECT_ROOT / "docs" / "backtest" / "setup_d" / period
    out.mkdir(parents=True, exist_ok=True)
    end_is = str((pd.Timestamp(HOLDOUT_START) - pd.Timedelta(days=1)).date())

    L = [f"# Setup D: index trend filter, {period.replace('_', '-')}", "",
         "Hold the index while its close is above the moving average, otherwise hold T-bills (13-week "
         "yield). Signals at the close, switches at the next open, 5 bps per switch. No leverage, no "
         "shorting. Sharpe uses total returns (rf = 0) for every row, so it's comparable across rows.", ""]
    regime = {}
    for sym, label in INSTRUMENTS.items():
        px = yahoo_prices.load(sym).loc[:END]
        cash = yahoo_prices.tbill_daily_return(px.index)
        sigs = setup_d.variants(px.close)
        # skip the first year of each series: the long averages are still warming up
        start = HOLDOUT_START if args.holdout else str((px.index[0] + pd.DateOffset(years=1)).date())
        end = END if args.holdout else end_is
        table, curves = evaluate(px, sigs, cash, start, end)
        L += [f"## {label}: {start} to {end}", "", fmt(table), "",
              f"![{sym}](equity_{sym.replace('^', '')}.png)", ""]
        plot(curves, f"{label}: trend filter vs buy & hold ({start[:4]}-{end[:4]})",
             out / f"equity_{sym.replace('^', '')}.png")

        if not args.holdout and sym in ("SPY", "QQQ"):
            rt, _ = evaluate(px, sigs, cash, RECENT_START, end_is)
            L += [f"### {sym}, recent window only ({RECENT_START} to {end_is})", "", fmt(rt), ""]
            if sym == "SPY":
                regime = {"full": table.set_index("variant"), "recent": rt.set_index("variant")}
                ep = {}
                for name in ["Buy & hold", *sigs]:
                    res = (switching.buy_and_hold(px) if name == "Buy & hold"
                           else switching.run(px, sigs[name], cash))
                    ep[name] = {k: (1 + res.ret.loc[a:b].iloc[1:]).prod() - 1 for k, (a, b) in EPISODES.items()}
                L += ["### SPY return during each major sell-off (peak to trough)", "",
                      pd.DataFrame(ep).T.map("{:+.0%}".format).to_markdown(), ""]
        if not args.holdout and sym == "SPY":
            zero, _ = evaluate(px, sigs, None, start, end)
            L += ["### SPY with 0% on cash (to show how much the T-bill yield matters)", "", fmt(zero), ""]

    if not args.holdout:
        L += ["## Pre-registered regime filter decision", "",
              "Rule (fixed before results): first of " + ", ".join(CANDIDATES) + " that, on SPY in both the "
              "full in-sample period and the recent window, cuts max drawdown by >= 1/3, gives up <= 1.5pp "
              "CAGR, and has Sharpe >= buy-and-hold.", ""]
        chosen = None
        for c in CANDIDATES:
            checks = {w: passes(regime[w].loc[c], regime[w].loc["Buy & hold"]) for w in ("full", "recent")}
            L.append(f"- {c}: full period {'PASS' if checks['full'] else 'fail'}, "
                     f"recent window {'PASS' if checks['recent'] else 'fail'}")
            if chosen is None and all(checks.values()):
                chosen = c
        L += ["", f"**Decision: {chosen or 'no regime filter'}.**", ""]
        (out.parent / "regime_decision.json").write_text(json.dumps({"regime_filter": chosen}, indent=2))
        print("Regime filter decision:", chosen)

    (out / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Written to {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
