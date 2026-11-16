"""Setup E backtest: SPY and QQQ, trend + vol target + TOM, each component and combined.

Usage:
    python scripts/run_setup_e.py                          # development + walk-forward windows
    python scripts/run_setup_e.py --holdout --final-check  # 2023-2026 holdout, run once

Evaluation definitions, fixed before any E results were seen (2026-11-16):
* Periods: development 2000-2015; walk-forward validation 2016-2022 (no tunable parameters, so
  this is simply the next out-of-sample block); holdout 2023-01-01 to the latest data, run once.
  Also 2010-2019; 2020-2026 is reported only after the holdout run.
* Costs: Alpaca 2 bps per side (ETF); IG daily-funded index bet, 0.5 pt (S&P 500) / 1.0 pt
  (Nasdaq-100) round-trip spread, funding (fed funds + 3.4%) / 360 per night; each also x2.
  Cash earns the 3-month T-bill rate (FRED DTB3) in every version, including buy-and-hold on IG.
* Sharpe for the drop rules = excess over T-bills (rf=0 Sharpe is also shown).
* "Edge" = variant excess Sharpe minus buy-and-hold excess Sharpe over the same dates (Alpaca).
  "Edge disappears with costs doubled" = that difference <= 0 with x2 costs, 2000-2022.
* In-sample for the holdout rule and the DSR = 2000-2022, Alpaca costs.
* DSR: n_trials = the addendum's running variant count; trial-Sharpe variance = variance of the
  daily excess Sharpe across the E variants (both instruments), 2000-2022.
* Concentration: share of total profit from the best 5% of months.
* Correlation: daily returns vs Setup A's point-in-time Alpaca equity curve (Step 0), 2010-2026.
"""

from __future__ import annotations

import argparse
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from earnings_bot.backtest import allocation, metrics  # noqa: E402
from earnings_bot.backtest.costs import fed_funds, tbill_3m  # noqa: E402
from earnings_bot.config import PROJECT_ROOT  # noqa: E402
from earnings_bot.data import yahoo_prices  # noqa: E402
from earnings_bot.signals import setup_e  # noqa: E402

OUT = PROJECT_ROOT / "docs" / "research" / "setup_e"
INSTRUMENTS = {"SPY": ("^GSPC", 0.5), "QQQ": ("^NDX", 1.0)}
PRE = {"development 2000-2015": ("2000-01-01", "2015-12-31"), "validation 2016-2022": ("2016-01-01", "2022-12-31"),
       "2010-2019": ("2010-01-01", "2019-12-31"), "in-sample 2000-2022": ("2000-01-01", "2022-12-31")}
HOLD = {"holdout 2023-2026": ("2023-01-01", None), "2020-2026": ("2020-01-01", None)}
COSTS = [("Alpaca", "alpaca", 1.0), ("Alpaca x2", "alpaca", 2.0), ("IG", "ig", 1.0), ("IG x2", "ig", 2.0)]
ADDENDUM_TRIALS_BEFORE_E = 1
E_TRIALS = 2 * len(setup_e.VARIANTS)  # 5 rules x 2 instruments
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
GREY, SURFACE, INK, INK2, GRID = "#8c8b86", "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"


def window(res: pd.DataFrame, a, b) -> pd.DataFrame:
    w = res.loc[a:b].copy()
    w.iloc[0, w.columns.get_loc("ret")] = 0.0
    return w


def month_concentration(res: pd.DataFrame) -> float:
    r = res.ret.iloc[1:]
    eq_gain = (1 + r).groupby(r.index.to_period("M")).prod() - 1
    return metrics.profit_concentration(eq_gain)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--final-check", action="store_true")
    args = ap.parse_args()
    if args.holdout and not args.final_check:
        print("Use --holdout --final-check for the one-time holdout run.", file=sys.stderr)
        return 2
    windows = HOLD if args.holdout else PRE
    OUT.mkdir(parents=True, exist_ok=True)
    cash, ff = tbill_3m(), fed_funds()
    rows, curves, daily = [], {}, {}
    for sym, (index_sym, pts) in INSTRUMENTS.items():
        px = yahoo_prices.load(sym)
        lvl = yahoo_prices.load(index_sym).close
        last = px.index[-1]
        bh_p = pd.Series(1.0, index=px.index)
        runs = {"buy & hold": (bh_p, bh_p)}
        for name, kw in setup_e.VARIANTS.items():
            runs[name] = setup_e.positions(px.close, **kw)
        for name, (po, pc) in runs.items():
            for cname, model, mult in COSTS:
                if name == "buy & hold" and model == "alpaca":
                    res = allocation.run(px, po, pc, cash, model="none")  # buy once, hold
                else:
                    res = allocation.run(px, po, pc, cash, model=model, mult=mult, bps=2.0, index_level=lvl,
                                         index_spread_pts=pts, fed_funds=ff)
                daily[(sym, name, cname)] = res
                for wname, (a, b) in windows.items():
                    w = window(res, a, b or last)
                    rows.append({"instrument": sym, "variant": name, "costs": cname, "period": wname,
                                 **allocation.stats(w), "top-5% months share of profit": month_concentration(w)})
                    if cname == "Alpaca":
                        curves[(sym, name, wname)] = (1 + w.ret).cumprod()
    df = pd.DataFrame(rows)
    tag = "holdout" if args.holdout else "pre_holdout"
    df.to_csv(OUT / f"results_{tag}.csv", index=False)

    # charts: Alpaca costs, all variants vs buy & hold, longest window
    main_w = "holdout 2023-2026" if args.holdout else "in-sample 2000-2022"
    for sym in INSTRUMENTS:
        fig, ax = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.tick_params(colors=INK2, labelsize=9)
        bh = curves[(sym, "buy & hold", main_w)]
        ax.plot(bh.index, bh.values, color=GREY, linestyle="--", linewidth=1.6, label="buy & hold")
        for name, color in zip(setup_e.VARIANTS, SERIES):
            c = curves[(sym, name, main_w)]
            ax.plot(c.index, c.values, color=color, linewidth=1.8, label=name)
        if not args.holdout:
            ax.set_yscale("log")
            ax.yaxis.set_major_locator(mtick.LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:,.2g}"))
        ax.yaxis.set_minor_formatter(mtick.NullFormatter())
        ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
        ax.set_title(f"Setup E on {sym}, {main_w} (Alpaca costs, growth of $1)", loc="left", color=INK,
                     fontsize=12, fontweight="bold")
        fig.tight_layout()
        fig.savefig(OUT / f"equity_{sym}_{tag}.png", dpi=130, facecolor=SURFACE)
        plt.close(fig)

    extra = {}
    if not args.holdout:
        # DSR on 2000-2022, Alpaca, daily excess returns
        srs, exc = {}, {}
        for sym in INSTRUMENTS:
            for name in setup_e.VARIANTS:
                w = window(daily[(sym, name, "Alpaca")], *PRE["in-sample 2000-2022"]).iloc[1:]
                e = w.ret - w.rf
                exc[(sym, name)] = e
                srs[(sym, name)] = e.mean() / e.std()
        n = ADDENDUM_TRIALS_BEFORE_E + E_TRIALS
        var = float(np.var(list(srs.values()), ddof=1))
        extra["dsr"] = {f"{s} | {v}": metrics.deflated_sharpe(e, n, var) for (s, v), e in exc.items()}
        # correlation with Setup A (Step 0, point-in-time, Alpaca), 2010-2026
        a_path = PROJECT_ROOT / "docs" / "research" / "step0" / "equity_alpaca_2010_2026.csv"
        if a_path.exists():
            a_ret = pd.read_csv(a_path, index_col=0, parse_dates=True).equity.pct_change()
            corr = {}
            for sym in INSTRUMENTS:
                for name in ["buy & hold", *setup_e.VARIANTS]:
                    r = daily[(sym, name, "Alpaca")].ret
                    j = pd.concat([r, a_ret], axis=1, join="inner").dropna()
                    corr[f"{sym} | {name}"] = float(j.corr().iloc[0, 1])
            extra["correlation_with_A_2010_2026"] = corr
        (OUT / "pre_holdout_extra.json").write_text(json.dumps(extra, indent=2, default=float))
    print(f"written {OUT.relative_to(PROJECT_ROOT)} ({tag})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
