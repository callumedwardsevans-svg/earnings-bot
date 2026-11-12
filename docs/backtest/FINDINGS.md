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

---

# Update: Setup D (index trend filter) and the Setup A held-out check

## Setup D: does a moving-average filter on SPY/QQQ beat buy-and-hold?

Full tables: [in-sample](setup_d/in_sample/summary.md), [held-out last 2 years](setup_d/holdout/summary.md).
Hold the index above its average, T-bills below; switch at the next open; 5 bps per switch.

| SPY, T-bill cash | 1994-2024 CAGR | max DD | Sharpe | 2016-2024 CAGR | Held-out 2024-26 CAGR |
|---|---|---|---|---|---|
| Buy & hold | 10.5% | -55% | 0.62 | 15.1% | 13.2% |
| EMA 200 | 8.0% | -29% | 0.68 | 9.1% | 10.0% |
| 10-month SMA | 9.6% | -25% | 0.78 | 9.5% | 5.4% |
| EMA 50 | 7.0% | -29% | 0.66 | 8.7% | 9.3% |

- **The research expectation holds over 30 years, not recently.** Over 1994-2024 the slower filters
  roughly halved the max drawdown (-55% → -25 to -29%), with similar or better Sharpe, and avoided most
  of the dot-com and 2008 crashes (the 10-month SMA lost 5% in each vs -48% / -55%).
- **Since 2016 they cost a lot of return.** Sell-offs were short and recovered fast (2018 Q4, 2020,
  April 2025), so the filters sold late and bought back late: 6 points of CAGR given up in 2016-2024, and
  in the held-out two years the 10-month SMA made 5.4% vs 13.2% (SPY) and 2.5% vs 15.2% (QQQ).
- **Fast EMAs (20) are poor everywhere**: 30+ switches a year and worse than buy-and-hold on every
  measure except volatility. The 1% band helps cut switches but doesn't fix the results.
- **The T-bill yield matters**: on 0% cash every SPY variant loses another ~0.5-0.8 points of CAGR.
- The S&P 500 index back to 1928 (price only) shows the same pattern: better Sharpe and much smaller
  drawdowns than holding through 1929-32, but the 10-month SMA still fell 54% in the early 1930s.

**Regime filter decision (pre-registered rule): none.** Neither the 200-EMA nor the 10-month SMA met
the bar on SPY in both the full period and 2016-2024. For information, a SPY 200-EMA filter applied to
setups A and B made every variant worse (A ema+fixed: CAGR 4.9% → 3.6%, Sharpe 0.72 → 0.59);
see [in_sample_regime_ema200](in_sample_regime_ema200/summary.md).

## Setup A held-out check (2025-11-11 to 2026-11-10), run once

Configuration locked beforehand in [PREREGISTRATION.md](PREREGISTRATION.md) (committed before the run):
A, 50-EMA filter, fixed exit, no regime filter. Results: [holdout/summary.md](holdout/summary.md),
[holdout/robustness.md](holdout/robustness.md).

| | In-sample 2016-2025 | Held-out 2025-26 |
|---|---|---|
| Signals filled (signal level) | 873 | 112 |
| Win rate | 41% | 30% |
| Expectancy per trade | +0.20R (se 0.05) | **-0.02R (se 0.12)** |
| Market-adjusted expectancy | +0.03R | -0.04R |
| $10k portfolio: trades / return / max DD / Sharpe | 506 / +4.9% CAGR / -12% / 0.72 | 53 / +7.9% / -3.0% / 1.06 |
| SPY over the same period | 15.0% CAGR / -34% / 0.88 | +11.0% / -8.9% / 0.84 |

- **At the signal level, the held-out year shows no edge** (-0.02R ± 0.12), consistent with the
  in-sample conclusion that A's profit was market drift. One year of ~110 signals can't confirm or rule
  out a small edge, but it gives no support for one.
- **The portfolio did better than the signals** (+0.21R per trade, Sharpe 1.06 vs SPY's 0.84) only
  because the 5-position cap took 53 of the 112 signals and those happened to include the winners.
  With 53 trades the standard error is about ±0.25R, so this is luck, not evidence. Don't read it as
  the strategy working.
- 8% of held-out trades were still open at the period end and are marked at the last close.

## Bottom line after milestone 3 + Setup D

- No setup tested so far has a market-adjusted edge: A ≈ 0, B ≤ 0, and D is a risk-reduction tool
  that has cost return in the last decade.
- **Paper trading A (as pre-registered) is still reasonable as an engineering and execution test**:
  plan → submit → reconcile, bracket orders, journal and daily report. Expect results close to the
  market's drift on ~30% of capital, with a lot of noise. Judge it on whether live fills and exits
  match the backtest, not on P&L.

---

# Update (2026-11-12): out-of-sample test on 2002-2015

Pre-registered (addendum in [PREREGISTRATION.md](PREREGISTRATION.md), committed before the data was
downloaded). Same `A:ema+fixed` configuration, never-used data from 2002-2015, Yahoo prices.
Details: [oos_2002_2015/summary.md](oos_2002_2015/summary.md) and
[oos_2002_2015/controls.md](oos_2002_2015/controls.md).

## Pre-registered result: passes

515 filled signals; market-adjusted expectancy **+0.125R, weekly-clustered t = 2.47**. Under the rule
set in advance, that counts as evidence of a stock-specific edge, so A stays a candidate strategy.
(Data check: the timing labels match the volume spike about as well as in 2016-2025, 66% vs 73%
agree and 9% vs 7% disagree, so the test isn't distorted by bad day-1 dates.)

## Post-hoc control (not pre-registered, but needed to read the result)

Today's S&P 500 names are survivors, so anything bought in them might beat SPY. The control enters
**every** report in the same stocks with the same entry/stop/target/time-exit machinery, but none of
the PEAD filters:

| Market-adjusted R per trade | 2002-2015 | 2016-2025 |
|---|---|---|
| Setup A (ema+fixed) | +0.125 (t 2.5) | +0.027 (t 0.9) |
| Control: all reports, no filters | -0.058 | -0.038 |
| **Setup A minus control** | **+0.18R (t ≈ 3.5)** | **+0.07R (t ≈ 1.6)** |
| Setup A, only stocks already in the index | +0.174 (t 2.8) | -0.029 (t -0.3) |

What this shows:

1. **Survivorship doesn't explain 2002-2015.** The control lost to SPY, so simply holding today's
   survivors after earnings wasn't the source. The PEAD filters picked genuinely better trades, and
   the effect is even stronger in stocks that were already index members.
2. **It corrects the earlier reading of 2016-2025.** The trade machinery itself (tight stops, costs,
   20-day cap) costs about -0.04 to -0.06R against SPY even with random entries. "Market-adjusted R ≈ 0"
   therefore understated A slightly; measured against the control, A's recent edge is about +0.07R,
   positive but not statistically significant.
3. **The effect looks much weaker since 2016**: about a third of its 2002-2015 size, and the 2025-26
   held-out year was negative. That fits academic work arguing post-earnings drift in large US stocks
   has faded as it became widely known and traded (e.g. Martineau, *Rest in Peace Post-Earnings
   Announcement Drift*). Decay, not a broken backtest, is the most likely explanation, but 2016-2025
   alone can't tell decay apart from noise.

$10k portfolio, 2002-2015: CAGR 2.5% vs SPY 6.2%, but Sharpe 0.46 vs 0.40 and max drawdown -14% vs
-55%. It uses only ~17% of capital on average, because of the 0.75% risk rule, the 15% position cap
and the small number of signals in the early years.

## Revised bottom line

- **Setup A has real historical evidence behind it** (2002-2015, robust to the survivorship control),
  but its edge in large caps appears to have shrunk a lot recently. Paper trading A is now a genuine
  (small) test of whether any edge remains, as well as a pipeline test. Fresh live data is the only
  clean evidence left, since all historical held-out periods are used.
- **Most promising research direction: the same PEAD rules on smaller caps** (S&P 400/600), where the
  literature says the drift has persisted longer. This now ranks above ETF momentum rotation, because
  this project has evidence the rules work when the effect is present.
