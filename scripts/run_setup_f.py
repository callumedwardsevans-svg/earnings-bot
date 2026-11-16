"""Setup F backtest (high-turnover short-term momentum), point-in-time S&P 500, from 2016.

Usage:
    python scripts/run_setup_f.py                          # development + validation
    python scripts/run_setup_f.py --holdout --final-check  # holdout 2023-2026, run once

Fixed before any F results were seen (2026-11-16):
* Start 2016 (user's choice): first formation 2016-01-29, first holding month Feb 2016.
  Development 2016-02..2020-12, validation 2021-2022 (no tunable parameters), holdout
  2023-01..2026-10 (last complete month), run once. 2016-2019 and 2020-2026 after the holdout.
* Variants (3): base; crash guard (exposure halved, the rest in T-bills, when SPY's 12-month return
  < 0 and its 21-day vol > its trailing-5-year 80th percentile); skip names whose earnings report
  falls in the holding month's first 5 sessions (report dates from the earnings history, which
  assumes the dates were known in advance).
* Benchmarks (not counted as variants): equal-weight eligible universe and 12-1 momentum top
  quintile, both with the same open-to-close monthly timing and costs; SPY buy-and-hold.
* Costs per name per month (full round trip, as written): Alpaca 3 bps/side; IG spread 0.05% of
  price per side capped at $0.05/share + funding (fed funds + 3.4%)/360 per calendar night held
  within the month. Each also x2. Idle cash (crash guard) earns the 3-month T-bill.
* Metrics on monthly returns. Sharpe for the drop rules = excess over T-bills.
  DSR: n_trials = addendum count (13 before F) + 3; trial-Sharpe variance = variance of monthly
  excess Sharpe across F's 3 variants and the 2 equal-weight/12-1 benchmarks, 2016-2022.
  Concentration = best 5% of months' share of profit. Correlation = monthly returns vs Setup A
  (Step 0 point-in-time Alpaca equity), 2016-2022.
"""

from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
import pandas as pd

from earnings_bot.backtest import metrics
from earnings_bot.backtest.costs import IG_FUNDING_SPREAD, fed_funds, tbill_3m
from earnings_bot.config import PROJECT_ROOT
from earnings_bot.data import calendar, history, membership, yahoo_prices
from earnings_bot.research import pit, setup_f

OUT = PROJECT_ROOT / "docs" / "research" / "setup_f"
PRE = {"development 2016-2020": ("2016-02", "2020-12"), "validation 2021-2022": ("2021-01", "2022-12"),
       "in-sample 2016-2022": ("2016-02", "2022-12")}
HOLD = {"holdout 2023-2026": ("2023-01", "2026-10"), "2016-2019": ("2016-02", "2019-12"),
        "2020-2026": ("2020-01", "2026-10")}
COSTS = [("Alpaca", "alpaca", 1.0), ("Alpaca x2", "alpaca", 2.0), ("IG", "ig", 1.0), ("IG x2", "ig", 2.0)]
ADDENDUM_TRIALS_BEFORE_F = 13
F_VARIANTS = ["F base", "F crash guard", "F skip early reporters"]


def month_sessions(sessions, period):
    s = sessions[(sessions >= period.start_time) & (sessions <= period.end_time)]
    return s[0], s[-1]


def hold_return(px, first, last):
    if first not in px.index or last not in px.index:
        return np.nan
    return float(px.close.loc[last] / px.open.loc[first] - 1)


def stats(r: pd.Series, rf: pd.Series) -> dict:
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    ex = r - rf.reindex(r.index).fillna(0)
    wins, losses = r[r > 0], r[r <= 0]
    return {"months": len(r), "CAGR": float(eq.iloc[-1] ** (1 / yrs) - 1), "volatility": float(r.std() * np.sqrt(12)),
            "max DD": float((eq / eq.cummax() - 1).min()), "Sharpe": float(r.mean() / r.std() * np.sqrt(12)),
            "excess Sharpe": float(ex.mean() / ex.std() * np.sqrt(12)), "win rate (months)": float((r > 0).mean()),
            "avg win month": float(wins.mean()) if len(wins) else np.nan,
            "avg loss month": float(losses.mean()) if len(losses) else np.nan,
            "top-5% months share of profit": metrics.profit_concentration(r)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--final-check", action="store_true")
    args = ap.parse_args()
    if args.holdout and not args.final_check:
        print("Use --holdout --final-check for the one-time holdout run.", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    sessions = calendar.load_sessions()
    iv = membership.load_intervals()
    iv = iv[iv.end.isna() | (iv.end > pd.Timestamp("2015-12-01"))]
    syms = sorted({membership.data_symbol(t) for t in iv.ticker} - {None} | {"SPY"})
    px, _, _ = pit.load_prices(syms)
    ysh = {s: yahoo_prices.shares_history(s) for s in syms}
    periods = pd.period_range("2016-01", "2026-10", freq="M")
    month_ends = pd.DatetimeIndex([month_sessions(sessions, p)[1] for p in periods])

    panel_path = OUT / "panel.parquet"
    panel = pd.read_parquet(panel_path) if panel_path.exists() else setup_f.build_panel(month_ends, px, iv, ysh)
    panel.to_parquet(panel_path)

    hist = history.load_history()
    hist = hist[hist.report_date >= "2016-01-01"]
    spy = px["SPY"]
    tb = tbill_3m()
    ff = fed_funds()

    picks_log, monthly = [], {}
    for k, p in enumerate(periods[:-1]):
        me = month_ends[k]
        hp = periods[k + 1]
        first, last = month_sessions(sessions, hp)
        month = panel[panel.month_end == me]
        elig = month[(month.raw_close > 10) & month.turnover.notna() & month.r1.notna()]
        f = setup_f.select_f(month)
        early = set(hist[(hist.report_date >= first) & (hist.report_date <= sessions[sessions >= first][4])].symbol)
        f_skip = setup_f.select_f(month[~month.symbol.isin(early)])
        mom = setup_f.top_quintile(elig[elig.r_12_1.notna()], "r_12_1")
        guard = setup_f.crash_guard_on(spy.close, me)
        nights = (last - first).days
        rf_m = float(tb.loc[:first].iloc[-1]) / 100 * nights / 360
        ff_m = float(ff.loc[:first].iloc[-1]) / 100
        books = {"F base": (f, 1.0), "F crash guard": (f, 0.5 if guard else 1.0), "F skip early reporters": (f_skip, 1.0),
                 "EW universe": (elig, 1.0), "12-1 momentum": (mom, 1.0)}
        for name, (book, expo) in books.items():
            rets, cost_a, cost_ig = [], [], []
            for r in book.itertuples():
                hr = hold_return(px[r.symbol], first, last)
                if np.isnan(hr):
                    continue
                rets.append(hr)
                o = px[r.symbol].open.loc[first]
                c = px[r.symbol].close.loc[last]
                cost_a.append(2 * 3 / 10_000)
                cost_ig.append(min(0.0005 * o, 0.05) / o + min(0.0005 * c, 0.05) / c)
            if not rets:
                continue
            gross = float(np.mean(rets))
            for cname, model, mult in COSTS:
                if model == "alpaca":
                    c = float(np.mean(cost_a)) * mult
                    fund = 0.0
                else:
                    c = float(np.mean(cost_ig)) * mult
                    fund = (ff_m + IG_FUNDING_SPREAD) / 360 * nights * mult
                net = expo * (gross - c - fund) + (1 - expo) * rf_m
                monthly.setdefault((name, cname), {})[hp] = net
        monthly.setdefault(("SPY buy & hold", "Alpaca"), {})[hp] = float(
            spy.close.loc[:last].iloc[-1] / spy.close.loc[:me].iloc[-1] - 1)
        picks_log.append({"holding_month": str(hp), "n_eligible": len(elig), "n_picks": len(f), "crash_guard": guard,
                          "picks": ",".join(f.ticker), "shares_sources": f.shares_source.value_counts().to_dict(),
                          "picks_with_eps_beat_in_formation_month": int(hist[(hist.report_date.dt.to_period("M") == p)
                                                                             & (hist.surprise_pct > 0)
                                                                             & hist.symbol.isin(set(f.symbol))].symbol.nunique())})
    rf_series = pd.Series({p: float(tb.loc[:month_sessions(sessions, p)[0]].iloc[-1]) / 100 / 12 for p in periods})
    windows = HOLD if args.holdout else PRE
    rows = []
    for (name, cname), d in monthly.items():
        s = pd.Series(d).sort_index()
        for wname, (a, b) in windows.items():
            w = s[(s.index >= pd.Period(a)) & (s.index <= pd.Period(b))]
            if len(w) > 3:
                rows.append({"book": name, "costs": cname, "period": wname, **stats(w, rf_series)})
    tag = "holdout" if args.holdout else "pre_holdout"
    pd.DataFrame(rows).to_csv(OUT / f"results_{tag}.csv", index=False)
    if not args.holdout:
        pl = pd.DataFrame(picks_log)
        pl.to_csv(OUT / "picks_log.csv", index=False)
        extra = {}
        ins = {n: pd.Series(monthly[(n, "Alpaca")]).sort_index() for n in F_VARIANTS + ["EW universe", "12-1 momentum"]}
        ins = {n: s[(s.index >= pd.Period("2016-02")) & (s.index <= pd.Period("2022-12"))] for n, s in ins.items()}
        ex = {n: s - rf_series.reindex(s.index) for n, s in ins.items()}
        srs = [e.mean() / e.std() for e in ex.values()]
        extra["dsr"] = {n: metrics.deflated_sharpe(ex[n], ADDENDUM_TRIALS_BEFORE_F + 3, float(np.var(srs, ddof=1)))
                        for n in F_VARIANTS}
        a_eq = pd.read_csv(PROJECT_ROOT / "docs/research/step0/equity_alpaca_2010_2026.csv", index_col=0,
                           parse_dates=True).equity
        a_m = a_eq.groupby(a_eq.index.to_period("M")).last().pct_change()
        extra["correlation_with_A_monthly"] = {n: float(pd.concat([ins[n], a_m], axis=1, join="inner").corr().iloc[0, 1])
                                               for n in F_VARIANTS}
        spy_m = pd.Series(monthly[("SPY buy & hold", "Alpaca")]).sort_index()
        after_falls = spy_m[spy_m <= -0.05].index + 1
        extra["after_spy_falls_of_5pct"] = {"months": [str(m) for m in after_falls if m <= pd.Period("2022-12")]}
        for n in F_VARIANTS + ["EW universe", "12-1 momentum"]:
            s = pd.Series(monthly[(n, "Alpaca")])
            extra["after_spy_falls_of_5pct"][n] = float(s.reindex([m for m in after_falls if m <= pd.Period("2022-12")]).mean())
        pre = pl[pl.holding_month <= "2022-12"]
        extra["diagnostics"] = {
            "avg picks per month": float(pre.n_picks.mean()), "avg eligible names": float(pre.n_eligible.mean()),
            "share of picks with an EPS beat in the formation month": float(pre.picks_with_eps_beat_in_formation_month.sum()
                                                                            / pre.n_picks.sum()),
            "months crash guard on": int(pre.crash_guard.sum()),
            "shares source (panel, all months)": panel.shares_source.value_counts().to_dict(),
            "panel rows with turnover / all member rows": [int(panel.turnover.notna().sum()), int(len(panel))]}
        (OUT / "extra_pre_holdout.json").write_text(json.dumps(extra, indent=2, default=float))
    print(f"written ({tag})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
