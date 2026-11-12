# Pre-registration: configuration locked before the held-out check

Written 2026-11-11, **before** running Setup A on the held-out period (2025-11-11 to 2026-11-10).
Nothing below changes after seeing the held-out results.

## Setup A configuration for the final check and paper trading

- **Variant: Setup A, 50 EMA filter on, fixed exit** (`A:ema+fixed`): stop = max(day-1 low − 1c,
  limit − 2 × ATR14), target +3R, time exit at the close of the 20th session, flat before the next report.
- **No market regime filter.**

## Why this variant

- It is the brief's base case: the trend filter it describes as standard, plus the fixed 3R exit.
- It was proposed as the natural candidate in [FINDINGS.md](FINDINGS.md) *before* the regime-filter
  work, not chosen afterwards for scoring best. In-sample, the four A variants are within about 2
  standard errors of each other, so the data doesn't really favour any of them.

## Why no regime filter

- Setup D's pre-registered rule (in `scripts/run_setup_d.py`): neither the 200-day EMA nor the
  10-month SMA met the bar on SPY in both the full in-sample period and the 2016-2024 window. The
  10-month SMA passed on 1994-2024 but gave up 5.6 points of CAGR in 2016-2024.
- For information only: applying a SPY 200-EMA filter to A and B in-sample made every variant worse
  (A ema+fixed: expectancy 0.163 → 0.147R, CAGR 4.9% → 3.6%, Sharpe 0.72 → 0.59).

## What the held-out check reports

Signal-level expectancy (R), market-adjusted expectancy, and the $10k portfolio vs SPY, for `A:ema+fixed`
only. The in-sample market-adjusted expectancy was +0.027R (weekly-clustered t ≈ 0.9). With about
one year of signals (~100), the held-out check can't confirm a small edge; it can only reveal a
broken one (for example, a large negative expectancy).

---

# Addendum (2026-11-12): out-of-sample test on 2002-2015

Written **before** any 2002-2015 prices were downloaded or any results seen.

- **Configuration: unchanged.** `A:ema+fixed`, no regime filter, every parameter as above. Same
  costs (5 bps per fill), $10k start, same risk limits, whole shares.
- **Period:** signals with day 1 from 2002-01-01 to 2015-12-31. This data has never been used in
  this project (earlier backtests start in April 2016).
- **Data:** Yahoo daily prices (split- and dividend-adjusted) for today's S&P 500 names plus SPY,
  because Alpaca's history starts in 2016. Earnings dates and timing come from the existing
  Yahoo + Alpha Vantage history. Survivorship bias is larger this far back (today's index list), which
  flatters results.
- **Primary measure:** signal-level **market-adjusted** expectancy (R minus SPY's move over the
  same holding window), with weekly-clustered t-stat.
- **Decision rule:**
  - market-adjusted expectancy > 0 with clustered t >= 2 → evidence of a real (stock-specific)
    edge; worth keeping A as a candidate strategy, not just a pipeline test;
  - otherwise → A is settled as market exposure. Paper trading A continues only as an
    execution/pipeline test, and research moves on (next: ETF momentum rotation).
- Also reported, not used for the decision: raw expectancy, the $10k portfolio vs SPY, the
  "already in the S&P 500 on the signal date" robustness run, and results by year.
