"""Research addendum, Step 0: re-baseline Setup A exactly as live, on point-in-time S&P 500 data.

* Universe: point-in-time membership (data/membership.py); a report counts only if the
  company was in the index on that date.
* Rules: A ema+fixed, scheduled exits at the next open (the live rule), no regime filter.
* Data: Yahoo adjusted daily prices 2009-2026 (consolidated volume) for every ticker that was a
  member since 2010; earnings from the Yahoo + Alpha Vantage history.
* Costs: Alpaca (3 bps/side) and IG (0.10% round-trip spread capped at $0.10/share, funding
  fed funds + 3.4% per night), each also with costs doubled.
* Periods: 2010-2019, 2020-2026 and the full span, each run as a fresh $10k account.
* Comparison: the same run on today's list (the earlier survivorship-biased universe).

Usage:  python scripts/step0_rebaseline_a.py
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from earnings_bot.backtest import metrics, portfolio
from earnings_bot.backtest.costs import apply_costs
from earnings_bot.backtest.simulate import simulate
from earnings_bot.config import PROJECT_ROOT, SETUP_A, SETUP_B
from earnings_bot.data import calendar, history, membership, universe, yahoo_prices
from earnings_bot.indicators import add_indicators
from earnings_bot.signals import setup_a

OUT = PROJECT_ROOT / "docs" / "research" / "step0"
START, END = "2010-01-01", "2026-11-10"
WINDOWS = {"2010-2019": ("2010-01-01", "2019-12-31"), "2020-2026": ("2020-01-01", END), "2010-2026": (START, END),
           "2023-2026 (not a clean holdout for A)": ("2023-01-01", END)}
COSTS = [("Alpaca", "alpaca", 1.0), ("Alpaca x2 costs", "alpaca", 2.0), ("IG", "ig", 1.0), ("IG x2 costs", "ig", 2.0)]
# Every earnings-setup variant tried in this project before the addendum (for the DSR):
# A: {ema,noema} x {fixed,trail} x {no regime, 200-EMA regime} = 8, + A with the open-exit rule = 9;
# B: {ema,noema} x {no regime, regime} = 4.  Total 13.
PRIOR_EARNINGS_TRIALS = 13


def ind(df):
    return add_indicators(df, SETUP_A.ema_trend_period, SETUP_A.atr_period,
                          ema_rising_lookback=SETUP_B.ema_rising_lookback)


def load_prices(symbols):
    """Yahoo 2009-2026 first; for names Yahoo has dropped (delisted), Alpaca SIP from 2016."""
    from earnings_bot.config import load_settings
    from earnings_bot.data import prices as alpaca_prices

    px, missing, source = {}, [], {}
    need_alpaca = []
    for s in symbols:
        df = yahoo_prices.load_history_range(s, "2009-01-01", "2026-11-12")
        if df is None or len(df) < 60:
            need_alpaca.append(s)
            continue
        px[s], source[s] = ind(df), "yahoo"
    if need_alpaca:
        alpaca_prices.update_prices(alpaca_prices.make_data_client(load_settings()), need_alpaca)
        for s in need_alpaca:
            df = alpaca_prices.load_prices(s)
            if df is None or len(df) < 60:
                missing.append(s)
            else:
                px[s], source[s] = ind(df), "alpaca (2016+)"
    return px, missing, source


def pit_filter(hist: pd.DataFrame, iv: pd.DataFrame) -> pd.DataFrame:
    """Keep reports where the ticker was an index member on the report date."""
    m = hist.merge(iv, left_on="symbol", right_on="ticker", how="inner")
    ok = (m.start.isna() | (m.start <= m.report_date)) & (m.end.isna() | (m.end > m.report_date))
    return m[ok].drop(columns=["ticker", "start", "end"]).drop_duplicates(["symbol", "report_date"])


def run_all(label, hist, px, sessions, uni, spy):
    cands, funnel = setup_a.generate(hist, px, sessions, uni, START, END, ema_filter=True, trailing=False)
    # frictionless simulation (slip=0); each platform's costs are applied afterwards
    frict = [simulate(c, px[c.symbol], pd.Timestamp(END), slip=0.0, scheduled_exit_at="open")
             for c in cands.itertuples()]
    frict = pd.concat([cands.reset_index(drop=True), pd.DataFrame(frict)], axis=1)
    rows, sig_rows, curves, trades_out = [], [], {}, {}
    sessions_all = sessions
    for cname, model, mult in COSTS:
        sims = apply_costs(frict, model, mult)
        f = metrics.market_adjust(sims[sims.filled], spy)
        for wname, (a, b) in WINDOWS.items():
            fw = f[(f.signal_date >= a) & (f.signal_date <= b)]
            st = metrics.trade_stats(fw.r_multiple)
            sig_rows.append({"universe": label, "costs": cname, "period": wname, "signals filled": len(fw),
                             "win rate": st["win_rate"], "avg win R": st["avg_win_r"], "avg loss R": st["avg_loss_r"],
                             "expectancy R": st["expectancy_r"],
                             "t (weekly)": metrics.clustered_t(fw.r_multiple, fw.entry_date),
                             "market-adj R": fw.excess_r.mean()})
            sw = sims[(sims.signal_date >= a) & (sims.signal_date <= b)]
            ses = sessions_all[(sessions_all >= pd.Timestamp(a)) & (sessions_all <= pd.Timestamp(b) + pd.Timedelta(days=45))]
            ses = ses[ses <= pd.Timestamp(END)]
            trades, skipped, curve = portfolio.run(sw, px, ses)
            pm = metrics.portfolio_metrics(trades, curve)
            rows.append({"universe": label, "costs": cname, "period": wname, "trades": pm["trades"],
                         "CAGR": pm["cagr"], "volatility": curve.equity.pct_change().std() * np.sqrt(252),
                         "max DD": pm["max_drawdown"], "Sharpe": pm["sharpe"], "win rate": pm["win_rate"],
                         "avg win R": pm["avg_win_r"], "avg loss R": pm["avg_loss_r"],
                         "expectancy R": pm["expectancy_r"], "exposure": pm["exposure_time"],
                         "top-5% share of profit": metrics.profit_concentration(trades.pnl_usd)})
            curves[(cname, wname)] = curve
            trades_out[(cname, wname)] = trades
    return pd.DataFrame(rows), pd.DataFrame(sig_rows), funnel, curves, trades_out, frict


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sessions = calendar.load_sessions()
    iv = membership.load_intervals()
    tickers = membership.all_tickers_since(START, iv)
    data_syms = sorted({membership.data_symbol(t) for t in tickers} - {None})
    px, missing, source = load_prices(sorted(set(data_syms) | {"SPY"}))
    spy = px["SPY"]

    # Ticker reuse diagnostic: a past member whose price history starts well after its
    # membership spell began now belongs to a different company (e.g. ADT, DOW, SNDK). Not
    # excluded: the old company's reports predate the new price history, so they get no price
    # bar and drop out; the new company's reports only count inside its own membership spell.
    reuse = []
    for r in iv[iv.end.notna() & (iv.end > pd.Timestamp(START))].itertuples():
        s = membership.data_symbol(r.ticker)
        if s in px and s not in reuse:
            spell_start = r.start if pd.notna(r.start) else pd.Timestamp(START)
            source_start = pd.Timestamp("2016-01-04") if source[s].startswith("alpaca") else pd.Timestamp("2009-01-02")
            expected_first = max(spell_start, source_start)
            if r.end > source_start and px[s].index[0] > expected_first + pd.Timedelta(days=90):
                reuse.append(s)

    cur = universe.load_sp500()
    sectors = cur.set_index("symbol").sector.to_dict()
    uni_pit = pd.DataFrame({"symbol": sorted(px), "sector": [sectors.get(s, f"Unknown:{s}") for s in sorted(px)],
                            "date_added": pd.NaT})
    hist = history.build_history()
    hist_pit = pit_filter(hist, iv)

    # coverage table
    removed = {membership.data_symbol(t) for t in tickers} - set(cur.symbol) - {None}
    with_hist = set(hist.symbol)
    cov = {
        "tickers that were members at some point 2010-2026": len(tickers),
        "  of which still members today": len(tickers & set(cur.symbol)),
        "  of which left the index": len(tickers - set(cur.symbol)),
        "left the index: with prices (Yahoo 2009+)": sum(1 for s in removed if source.get(s) == "yahoo"),
        "left the index: with prices (Alpaca 2016+ only)": sum(1 for s in removed if source.get(s, "").startswith("alpaca")),
        "left the index: with earnings history": len(removed & with_hist),
        "left the index: with both (usable)": len(removed & set(px) & with_hist),
        "no free price history at all": len(missing),
        "reused tickers (old company's spell has no price data)": len(reuse),
        "removed names with unknown sector (own sector bucket)": sum(1 for s in px if s not in sectors),
    }
    # report-level coverage: reports by members 2010-2026 that we can actually evaluate
    pit_reports_all = pit_filter(hist, iv)
    member_days = sum((min(r.end if pd.notna(r.end) else pd.Timestamp(END), pd.Timestamp(END))
                       - max(r.start if pd.notna(r.start) else pd.Timestamp(START), pd.Timestamp(START))).days
                      for r in iv.itertuples() if (r.end if pd.notna(r.end) else pd.Timestamp(END)) > pd.Timestamp(START))
    cov["expected member-quarters 2010-2026 (member-days / 91)"] = int(member_days / 91)
    cov["member reports found in earnings history (2010-2026)"] = int(
        ((pit_reports_all.report_date >= START) & (pit_reports_all.report_date <= END)).sum())

    port_pit, sig_pit, funnel_pit, curves, trades, frict = run_all("point-in-time", hist_pit, px, sessions, uni_pit, spy)
    uni_today = cur[cur.symbol.isin(px)][["symbol", "sector", "date_added"]]
    hist_today = hist[hist.symbol.isin(set(cur.symbol))]
    port_tod, sig_tod, funnel_tod, _, _, _ = run_all("today's list", hist_today, px, sessions, uni_today, spy)

    # SPY buy & hold per window
    spy_rows = []
    for wname, (a, b) in WINDOWS.items():
        st, eq = metrics.benchmark(spy, a, b, 10_000)
        spy_rows.append({"period": wname, "CAGR": st["cagr"], "volatility": eq.pct_change().std() * np.sqrt(252),
                         "max DD": st["max_drawdown"], "Sharpe": st["sharpe"]})

    # DSR on the full-period Alpaca run; trial-Sharpe variance from the earlier A/B backtests
    sr_trials = []
    for p in (PROJECT_ROOT / "docs" / "backtest").glob("in_sample*/*/equity.csv"):
        e = pd.read_csv(p, index_col=0).equity
        r = e.pct_change().dropna()
        sr_trials.append(r.mean() / r.std())
    n_trials = PRIOR_EARNINGS_TRIALS + 1
    r_full = curves[("Alpaca", "2010-2026")].equity.pct_change().dropna()
    dsr = metrics.deflated_sharpe(r_full, n_trials, float(np.var(sr_trials, ddof=1)))

    pd.concat([port_pit, port_tod]).to_csv(OUT / "portfolio_results.csv", index=False)
    pd.concat([sig_pit, sig_tod]).to_csv(OUT / "signal_results.csv", index=False)
    trades[("Alpaca", "2010-2026")].to_csv(OUT / "trades_alpaca_2010_2026.csv", index=False)
    (OUT / "coverage.json").write_text(json.dumps({**cov, "dsr": dsr, "funnel_pit": funnel_pit,
                                                   "funnel_today": funnel_tod,
                                                   "excluded_reuse": reuse, "no_prices": missing}, indent=2, default=str))
    pd.DataFrame(spy_rows).to_csv(OUT / "spy.csv", index=False)
    print(json.dumps(cov, indent=1))
    print("DSR:", dsr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
