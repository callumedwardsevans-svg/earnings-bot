"""Setup G (PEAD v2) vs Setup A on identical point-in-time S&P 500 announcements.

Usage:
    python scripts/run_setup_g.py                          # development + validation windows
    python scripts/run_setup_g.py --holdout --final-check  # 2023-2026 holdout, run once

Fixed before any G results were seen (2026-11-16):
* Variants run now: EPS beat >= 5% alone, exit at day +10 and +20 (2 of the addendum's 4).
  The "EPS and revenue beat" pair is blocked until revenue-consensus history exists; it will
  get its own one-time holdout run later.
* Entry at the next open after day 1 (ground rule 4; see signals/setup_g.py).
* Periods (data starts 2010, split shifted as the protocol asks): development 2010-2018,
  validation 2019-2022 (no tunable parameters), holdout 2023-01-01 to 2026-11-10, run once.
  2010-2019 and 2020-2026 are reported after the holdout.
* Costs: Alpaca 3 bps/side; IG spread 0.10% round trip capped at $0.10/share + funding
  (fed funds + 3.4%)/360 per night; each also x2.
* G sizing: 0.5% risk, 10% cap; A: 0.75% risk, 15% cap (as live). Both: 5 positions, 2/sector,
  2% daily loss limit, whole shares, $10k fresh account per window.
* Drop-rule definitions: holdout Sharpe = portfolio Sharpe (rf=0, the portfolio holds idle
  cash at 0%) in 2023-26 vs in-sample 2010-2022; DSR on in-sample daily portfolio returns with
  n_trials = the addendum's running count; concentration = share of profit from the best 5%
  of trades; correlation = daily portfolio returns vs A, in-sample.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

import numpy as np
import pandas as pd

from earnings_bot.backtest import metrics, portfolio
from earnings_bot.backtest.costs import apply_costs
from earnings_bot.backtest.simulate import simulate
from earnings_bot.config import PROJECT_ROOT, RISK
from earnings_bot.research import pit
from earnings_bot.signals import setup_a, setup_g

OUT = PROJECT_ROOT / "docs" / "research" / "setup_g"
END = "2026-11-10"
PRE = {"development 2010-2018": ("2010-01-01", "2018-12-31"), "validation 2019-2022": ("2019-01-01", "2022-12-31"),
       "in-sample 2010-2022": ("2010-01-01", "2022-12-31")}
HOLD = {"holdout 2023-2026": ("2023-01-01", END), "2010-2019": ("2010-01-01", "2019-12-31"),
        "2020-2026": ("2020-01-01", END)}
COSTS = [("Alpaca", "alpaca", 1.0), ("Alpaca x2", "alpaca", 2.0), ("IG", "ig", 1.0), ("IG x2", "ig", 2.0)]
G_LIMITS = dataclasses.replace(RISK, risk_per_trade_pct=0.005, max_position_pct=0.10)
ADDENDUM_TRIALS_BEFORE_G = 11
G_TRIALS_RUN = 2


def frictionless(cands, px, scheduled_exit_at):
    res = [simulate(c, px[c.symbol], pd.Timestamp(END), slip=0.0, scheduled_exit_at=scheduled_exit_at)
           for c in cands.itertuples()]
    return pd.concat([cands.reset_index(drop=True), pd.DataFrame(res)], axis=1)


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
    inp = pit.load_inputs()
    spy = inp.px["SPY"]

    setups = {}
    for hold in (10, 20):
        c, f = setup_g.generate(inp.hist_pit, inp.px, inp.sessions, inp.universe, pit.START, END, hold)
        setups[f"G eps>=5% +{hold}d"] = (frictionless(c, inp.px, "close"), f, G_LIMITS)
    c, f = setup_a.generate(inp.hist_pit, inp.px, inp.sessions, inp.universe, pit.START, END,
                            ema_filter=True, trailing=False)
    setups["A ema+fixed (as live)"] = (frictionless(c, inp.px, "open"), f, RISK)

    sig_rows, port_rows, curves = [], [], {}
    for name, (frict, funnel, limits) in setups.items():
        for cname, model, mult in COSTS:
            sims = apply_costs(frict, model, mult)
            filled = metrics.market_adjust(sims[sims.filled], spy)
            for wname, (a, b) in windows.items():
                fw = filled[(filled.signal_date >= a) & (filled.signal_date <= b)]
                st = metrics.trade_stats(fw.r_multiple)
                sig_rows.append({"setup": name, "costs": cname, "period": wname, "signals filled": len(fw),
                                 "win rate": st["win_rate"], "avg win R": st["avg_win_r"],
                                 "avg loss R": st["avg_loss_r"], "expectancy R": st["expectancy_r"],
                                 "t (weekly)": metrics.clustered_t(fw.r_multiple, fw.entry_date),
                                 "market-adj R": fw.excess_r.mean(),
                                 # G's stop (day-1 low) can sit very close to the day-1 close, so R
                                 # can explode; these show the typical trade and a winsorised mean
                                 "median R": fw.r_multiple.median(),
                                 "expectancy R (capped +-5)": fw.r_multiple.clip(-5, 5).mean(),
                                 "median stop distance %": float(((fw.ref_price - fw.stop) / fw.ref_price).median() * 100),
                                 "avg return % per trade": float(((fw.exit_price / fw.entry_price) - 1).mean() * 100),
                                 "avg hold (sessions)": float(np.mean([
                                     inp.sessions.searchsorted(y) - inp.sessions.searchsorted(x)
                                     for x, y in zip(fw.entry_date, fw.exit_date)])) if len(fw) else np.nan})
                sw = sims[(sims.signal_date >= a) & (sims.signal_date <= b)]
                ses = inp.sessions[(inp.sessions >= pd.Timestamp(a))
                                   & (inp.sessions <= min(pd.Timestamp(b) + pd.Timedelta(days=45), pd.Timestamp(END)))]
                trades, skipped, curve = portfolio.run(sw, inp.px, ses, limits=limits)
                pm = metrics.portfolio_metrics(trades, curve)
                port_rows.append({"setup": name, "costs": cname, "period": wname, "trades": pm["trades"],
                                  "CAGR": pm["cagr"], "volatility": curve.equity.pct_change().std() * np.sqrt(252),
                                  "max DD": pm["max_drawdown"], "Sharpe": pm["sharpe"], "win rate": pm["win_rate"],
                                  "avg win R": pm["avg_win_r"], "avg loss R": pm["avg_loss_r"],
                                  "expectancy R": pm["expectancy_r"], "exposure": pm["exposure_time"],
                                  "top-5% share of profit": metrics.profit_concentration(trades.pnl_usd)})
                curves[(name, cname, wname)] = curve.equity
                if cname == "Alpaca" and wname in ("in-sample 2010-2022", "holdout 2023-2026"):
                    tag = name.split(" (")[0].replace(" ", "_").replace(">=", "ge").replace("%", "pct").replace("+", "")
                    trades.to_csv(OUT / f"trades_{tag}_{wname.split()[0]}.csv", index=False)

    tag = "holdout" if args.holdout else "pre_holdout"
    pd.DataFrame(sig_rows).to_csv(OUT / f"signal_{tag}.csv", index=False)
    pd.DataFrame(port_rows).to_csv(OUT / f"portfolio_{tag}.csv", index=False)
    extra = {"funnels": {k: v[1] for k, v in setups.items()}}
    if not args.holdout:
        # DSR: trial-Sharpe variance from every earnings variant run so far (A/B in-sample
        # curves from milestone 3 plus the G and A portfolio curves here)
        srs = []
        for p in (PROJECT_ROOT / "docs" / "backtest").glob("in_sample*/*/equity.csv"):
            r = pd.read_csv(p, index_col=0).equity.pct_change().dropna()
            srs.append(r.mean() / r.std())
        rets = {}
        for name in setups:
            r = curves[(name, "Alpaca", "in-sample 2010-2022")].pct_change().dropna()
            rets[name] = r
            srs.append(r.mean() / r.std())
        n = ADDENDUM_TRIALS_BEFORE_G + G_TRIALS_RUN
        var = float(np.var(srs, ddof=1))
        extra["dsr"] = {k: metrics.deflated_sharpe(v, n, var) for k, v in rets.items()}
        a = rets["A ema+fixed (as live)"]
        extra["correlation_with_A"] = {k: float(pd.concat([v, a], axis=1, join="inner").corr().iloc[0, 1])
                                       for k, v in rets.items()}
    (OUT / f"extra_{tag}.json").write_text(json.dumps(extra, indent=2, default=float))
    print(f"written {OUT.relative_to(PROJECT_ROOT)} ({tag})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
