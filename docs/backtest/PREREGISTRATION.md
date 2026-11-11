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
