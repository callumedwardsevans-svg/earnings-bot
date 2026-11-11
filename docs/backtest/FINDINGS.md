# Milestone 3 findings: is there an edge worth paper trading?

**Short answer: not a convincing one.** Setup A (post-earnings drift) makes money, but almost all of
it is the stock market rising while the trades are open. Setup B (pre-earnings run-up) shows no edge
at all. Neither beats simply holding SPY. Details are in [summary.md](in_sample/summary.md) and
[robustness.md](in_sample/robustness.md).

Period: in-sample, Apr 2016 to 10 Nov 2025. The last 12 months (11 Nov 2025 onwards) are **held
out and haven't been run**. All parameters are the brief's hypotheses as written; nothing was tuned.

## What the numbers say

| | Setup A (4 variants) | Setup B (2 variants) |
|---|---|---|
| Signals | 931-989 | 9,902-16,994 |
| Expectancy per trade (signal level) | +0.12 to +0.20R | 0.00 to +0.05R |
| t-stat, signals grouped by week | 2.3 to 3.2 | -0.3 to 2.2 |
| SPY's return over the same holding windows | +0.10 to +0.17R | +0.05 to +0.08R |
| **Market-adjusted expectancy** | **+0.01 to +0.03R (t ≈ 0.7-1.2)** | **-0.05 to -0.03R** |
| $10k portfolio CAGR | 4.1-5.3% | 2.4-7.1% |
| Portfolio Sharpe | 0.59-0.81 | 0.31-0.67 |
| Max drawdown | -11% to -13% | -15% to -23% |

SPY buy and hold over the same period: CAGR 15.0%, Sharpe 0.88, max drawdown -34%.

## How to read it

1. **Setup A's raw edge is mostly market beta.** On its own, +0.20R per trade with a t-stat of about 3
   looks significant. But the average trade lasts ~11 sessions, during which SPY rose by the equivalent
   of +0.17R. Subtracting that leaves about +0.03R, which can't be told apart from zero. This matches
   the research literature: post-earnings drift has weakened a lot since it was first documented and is
   mostly found in small, less-followed stocks, not the S&P 500.
2. **Setup B has no edge.** With the EMA filter, expectancy is exactly 0R. Without it, +0.05R looks
   "significant" on 17,000 signals (naive t = 6), but those signals are heavily overlapping and move
   together. Grouped by week, t falls to 2.2, and after subtracting the market it is negative.
3. **The portfolio lags SPY because it's mostly in cash.** Setup A has a position open 80% of the
   time but only uses ~30% of capital on average (0.75% risk per trade, 15% cap, 5 positions). Lower
   drawdown (-12% vs -34%) is the upside, but the Sharpe ratio is still below SPY's.
4. **Robustness cuts the results further.** Dropping signals from before a stock joined the S&P 500
   lowers Setup A's portfolio expectancy from 0.13-0.17R to 0.10-0.14R, and total returns by about
   40%.
   That is only a partial survivorship-bias correction; the ~22% of names that left the index can't be
   added back with free data.
5. **Year by year, Setup A is mostly positive (9 of 10 years for the fixed-exit variants), but 2022
   was negative for every A variant.** That's consistent with an edge that mainly rides a rising market.

## Overfitting and multiple-testing caveats

- Six variants were tested. The best-looking one (A, EMA filter, trailing or fixed) will look better
  in-sample than it really is by chance. The gap between A's best and worst variants (0.12 vs 0.20R)
  is within about 2 standard errors, so the data doesn't really prefer one.
- The parameters (5% surprise, 3% gap, 2x volume, 3R target, 20-day hold) weren't optimised here, which
  helps. But they come from public descriptions of a strategy that has been widely studied, so there's
  publication bias upstream.
- Signals cluster in earnings season and share market exposure, so naive t-stats overstate certainty.
  The weekly-clustered t-stats above are more realistic.
- Data limits: Yahoo EPS estimates aren't guaranteed to be the consensus as it stood at the time;
  today's index membership (survivorship); no revenue history, so the "revenue also beat" condition
  isn't tested; B uses actual report dates, which wouldn't always have been confirmed 7 sessions ahead.

## Recommendation

- **Don't expect to make money from these rules as specified.** If paper trading goes ahead, treat it
  as testing the execution pipeline and checking that live behaviour matches the backtest, not as a
  test of profitability.
- If one variant is chosen for paper trading, **pick it now, before looking at the held-out year**, and
  write down why. The natural candidate is **Setup A, EMA filter, fixed exit**: it is the brief's base
  case, not chosen for being the top result. Then run the held-out check once:
  `python scripts/run_backtest.py --holdout --final-check`.
- Drop Setup B from live trading; there's nothing to trade.
- The interesting follow-up question is whether **market-adjusted** drift exists in a narrower set:
  bigger surprises, revenue beats (from Finnhub, going forward only), or smaller caps outside the
  S&P 500. Any such test is a new hypothesis and needs its own held-out data.
