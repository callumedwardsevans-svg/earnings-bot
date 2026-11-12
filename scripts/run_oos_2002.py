"""Pre-registered out-of-sample test: Setup A (ema+fixed) on 2002-2015.

See docs/backtest/PREREGISTRATION.md (addendum dated 2026-11-12). Configuration is
unchanged from the main backtest; prices come from Yahoo because Alpaca starts in 2016.

Usage:  python scripts/run_oos_2002.py
"""

from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import pandas as pd  # noqa: E402

from earnings_bot.backtest import metrics, portfolio  # noqa: E402
from earnings_bot.backtest.simulate import simulate_all  # noqa: E402
from earnings_bot.config import BACKTEST_START_EQUITY, PROJECT_ROOT, SETUP_A, SETUP_B  # noqa: E402
from earnings_bot.data import calendar, history, prices, quality, universe, yahoo_prices  # noqa: E402
from earnings_bot.indicators import add_indicators  # noqa: E402
from earnings_bot.signals import setup_a  # noqa: E402

START, END = "2002-01-01", "2015-12-31"  # signal (day 1) window
PX_START, PX_END = "2001-01-01", "2016-04-01"  # price window (warm-up before, exits after)
LAST_SESSION = "2016-03-31"
OUT = PROJECT_ROOT / "docs" / "backtest" / "oos_2002_2015"
BLUE, GREY = "#2a78d6", "#8c8b86"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"


def ind(df):
    return add_indicators(df, SETUP_A.ema_trend_period, SETUP_A.atr_period,
                          ema_rising_lookback=SETUP_B.ema_rising_lookback)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sessions_all = calendar.load_sessions()
    sessions = sessions_all[(sessions_all >= pd.Timestamp(START)) & (sessions_all <= pd.Timestamp(LAST_SESSION))]
    uni, hist = universe.load_sp500(), history.load_history()
    px = {}
    for s in sorted(set(uni.symbol) | {"SPY"}):
        df = yahoo_prices.load_history_range(s, PX_START, PX_END)
        if df is not None and len(df) > 60:
            px[s] = ind(df)
    spy = px["SPY"]
    L = ["# Out-of-sample test: Setup A (ema+fixed), 2002-2015", "",
         "Pre-registered in [PREREGISTRATION.md](../PREREGISTRATION.md) (addendum 2026-11-12) before any of "
         "this data was downloaded. Configuration unchanged. Yahoo adjusted daily prices for today's S&P 500 "
         f"names ({len(px) - 1} with data in the window) plus SPY. Signals with day 1 in {START}..{END}; "
         f"trades opened late in 2015 are allowed to finish by {LAST_SESSION}.", ""]

    # ---- timing-label quality, this window vs 2016+ --------------------------------------
    old = hist[(hist.report_date >= START) & (hist.report_date <= END)]
    new = hist[(hist.report_date >= "2016-04-01") & (hist.report_date <= "2025-11-10")]
    a_old = quality.timing_audit(old, px, sessions_all).timing_check.value_counts(normalize=True)
    new_px = {s: prices.load_prices(s) for s in new.symbol.unique()}
    a_new = quality.timing_audit(new, {k: v for k, v in new_px.items() if v is not None},
                                 sessions_all).timing_check.value_counts(normalize=True)
    tq = pd.DataFrame({"2002-2015": a_old, "2016-2025": a_new}).fillna(0).map("{:.1%}".format)
    L += ["## Data check: do the before/after-close labels still match the volume spike?", "",
          "If the timing labels were much worse before 2016, day 1 would often be wrong and the test unfair.", "",
          tq.to_markdown(), ""]

    # ---- signals, simulation ------------------------------------------------------------
    cands, funnel = setup_a.generate(hist, px, sessions_all, uni, START, END, ema_filter=True, trailing=False)
    sims = simulate_all(cands, px, LAST_SESSION)
    filled = metrics.market_adjust(sims[sims.filled], spy)
    st = metrics.trade_stats(filled.r_multiple)
    t_raw = metrics.clustered_t(filled.r_multiple, filled.entry_date)
    t_adj = metrics.clustered_t(filled.excess_r, filled.entry_date)
    adj = filled.excess_r.mean()
    verdict = ("evidence of a stock-specific edge (market-adjusted > 0 with clustered t >= 2)"
               if adj > 0 and t_adj >= 2 else "no evidence of a stock-specific edge: A is market exposure")
    L += ["## Primary result (signal level, every filled signal)", "",
          pd.DataFrame([{
              "signals": len(sims), "filled": len(filled), "win rate": f"{st['win_rate']:.0%}",
              "avg win R": round(st["avg_win_r"], 2), "avg loss R": round(st["avg_loss_r"], 2),
              "expectancy R": round(st["expectancy_r"], 3), "t (weekly clusters)": round(t_raw, 2),
              "SPY over same windows, R": round(filled.spy_r.mean(), 3),
              "**market-adjusted R**": round(adj, 3), "**t market-adj (weekly)**": round(t_adj, 2),
          }]).to_markdown(index=False), "",
          f"**Pre-registered decision: {verdict}.**", ""]

    # ---- portfolio ------------------------------------------------------------------------
    rows, curves = [], {}
    for mf in (False, True):
        trades, skipped, curve = portfolio.run(sims, px, sessions, membership_filter=mf)
        m = metrics.portfolio_metrics(trades, curve)
        rows.append({"run": "already in S&P 500 on signal date only" if mf else "all signals",
                     "trades": m["trades"], "expectancy R": round(m["expectancy_r"], 3),
                     "CAGR": f"{m['cagr']:+.1%}", "max DD": f"{m['max_drawdown']:.1%}",
                     "Sharpe": round(m["sharpe"], 2), "avg capital deployed": f"{m['avg_gross_exposure']:.0%}"})
        if not mf:
            trades.to_csv(OUT / "trades.csv", index=False)
            skipped.to_csv(OUT / "skipped.csv", index=False)
            curves["Setup A ema+fixed"] = curve.equity
    spy_stats, spy_eq = metrics.benchmark(spy, sessions[0], sessions[-1], BACKTEST_START_EQUITY)
    L += ["## $10k portfolio (all risk limits) vs SPY", "", pd.DataFrame(rows).to_markdown(index=False), "",
          f"SPY buy & hold, same period: CAGR {spy_stats['cagr']:+.1%}, max DD {spy_stats['max_drawdown']:.1%}, "
          f"Sharpe {spy_stats['sharpe']:.2f}.", "", "![equity](equity.png)", ""]

    # ---- by year, funnel ------------------------------------------------------------------
    by_year = filled.groupby(filled.entry_date.dt.year).agg(
        trades=("r_multiple", "size"), expectancy_R=("r_multiple", "mean"), market_adj_R=("excess_r", "mean"))
    L += ["## By year (signal level)", "", by_year.round(3).to_markdown(), "",
          "## Signal funnel", "", " → ".join(f"{k} **{v:,}**" for k, v in funnel.items()), ""]
    (OUT / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    fig, ax = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax.plot(spy_eq.index, spy_eq.values, color=GREY, linestyle="--", linewidth=1.6, label="SPY buy & hold")
    eq = curves["Setup A ema+fixed"]
    ax.plot(eq.index, eq.values, color=BLUE, linewidth=2, label="Setup A ema+fixed")
    ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=INK2)
    ax.set_title("Setup A out-of-sample, 2002-2015 ($10k start)", loc="left", color=INK, fontsize=12,
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "equity.png", dpi=130, facecolor=SURFACE)
    plt.close(fig)
    print("\n".join(L[:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
