# Research addendum, Setup G: PEAD v2 vs Setup A (EPS-only half of the grid)

Same point-in-time S&P 500 announcements as Setup A (Step 0), 2010-2026, price > $10 and 20-day ADV >
$50m for both. Code: `signals/setup_g.py`, `scripts/run_setup_g.py` (decisions fixed in its docstring
before results). Results: `portfolio_*.csv`, `signal_*.csv`, `drop_rules.csv`, `trades_*.csv`.
Pre-holdout results committed in `0e73342` before the one-time holdout run.

## What was run, and what wasn't

**Run (2 of the addendum's 4 variants):** EPS beat >= 5% alone, exit at day +10 and day +20.

**Not run yet: the "EPS beat and revenue beat" pair.** It needs revenue consensus history. The only free
source found is Alpha Vantage's `EARNINGS_ESTIMATES` endpoint, which has quarterly revenue estimates
(NVDA's go back to mid-2017, with analyst counts). It also needs *actual* revenue per quarter, and with
the free key's 25 calls a day that's about 1,300 calls for ~650 stocks (**about 7 weeks**), or about an
hour with a premium month. Coverage would also start around 2017, not 2010. Yahoo only has forward
revenue estimates; Finnhub's free calendar goes back about a month. The live bot has logged Finnhub's
pre-report revenue consensus since 2026-11-12. These two variants will get their own one-time holdout
run when the data exists.

**One change to the rules as written, forced by ground rule 4.** G says "enter at the close of day 1", but
its signal (day-1 close-to-close return > 0) needs that same close, and rule 4 only allows a close fill
when the signal uses data available *before* the close. So G enters with a **market order at the next
open (day 2)**, sized on the day-1 close. A live version could get close to the day-1 close with a
market-on-close order sent at ~15:45 New York using the price then; testing that would need intraday
bars (Alpaca's start in 2016) and would be a new variant.

**Periods:** data starts in 2010, so the split is shifted as the protocol asks: development 2010-2018,
validation 2019-2022 (no tunable parameters), **holdout 2023-01-01 to 2026-11-10, run once**. The
holdout overlaps announcements already seen in Setup A's tests (Step 0 and A's held-out year); G's
rules came from the addendum, not from those results.

**Sizing:** G 0.5% risk / 10% cap; A 0.75% / 15% (as live). Both 5 positions, 2 per sector, 2% daily
loss limit, $10k fresh account per window. Signals (G): 29,547 member reports, of
which 13,417 beat EPS by 5%+, 8,174 also rose on day 1, and
7,340 pass the liquidity filter. A takes 1,267 of the same reports.

## Portfolio results: CAGR / max drawdown / Sharpe

### Alpaca

| setup                 | development 2010-2018   | validation 2019-2022   | in-sample 2010-2022   | 2010-2019          | 2020-2026           | holdout 2023-2026    |
|:----------------------|:------------------------|:-----------------------|:----------------------|:-------------------|:--------------------|:---------------------|
| G eps>=5% +10d        | +2.3% / -9% / 0.46      | +6.3% / -8% / 0.93     | +3.5% / -9% / 0.63    | +2.6% / -9% / 0.52 | +3.9% / -9% / 0.62  | +1.1% / -10% / 0.23  |
| G eps>=5% +20d        | +3.1% / -9% / 0.56      | +6.5% / -7% / 0.91     | +4.1% / -9% / 0.68    | +3.6% / -9% / 0.65 | +4.1% / -13% / 0.62 | +3.3% / -13% / 0.55  |
| A ema+fixed (as live) | +3.8% / -9% / 0.69      | +6.9% / -10% / 1.00    | +4.8% / -10% / 0.80   | +4.0% / -9% / 0.71 | +2.6% / -13% / 0.41 | -1.2% / -12% / -0.14 |

### IG (daily-funded spread bet)

| setup                 | development 2010-2018   | validation 2019-2022   | in-sample 2010-2022   | 2010-2019           | 2020-2026           | holdout 2023-2026    |
|:----------------------|:------------------------|:-----------------------|:----------------------|:--------------------|:--------------------|:---------------------|
| G eps>=5% +10d        | +1.1% / -11% / 0.24     | +4.8% / -9% / 0.73     | +2.3% / -11% / 0.42   | +1.3% / -11% / 0.28 | +2.0% / -13% / 0.34 | -1.1% / -12% / -0.16 |
| G eps>=5% +20d        | +1.7% / -10% / 0.33     | +5.0% / -8% / 0.71     | +2.8% / -10% / 0.46   | +2.2% / -10% / 0.41 | +2.4% / -15% / 0.38 | +0.2% / -14% / 0.06  |
| A ema+fixed (as live) | +2.6% / -10% / 0.49     | +5.6% / -12% / 0.81    | +3.6% / -12% / 0.60   | +2.7% / -10% / 0.49 | +0.7% / -20% / 0.14 | -3.3% / -18% / -0.47 |

### Detail, 2010-2022 (Alpaca)

| setup                 |   trades | CAGR   | volatility   | max DD   |   Sharpe | win rate   |   avg win R |   avg loss R |   expectancy R | exposure   | top-5% share of profit   |
|:----------------------|---------:|:-------|:-------------|:---------|---------:|:-----------|------------:|-------------:|---------------:|:-----------|:-------------------------|
| G eps>=5% +10d        |     1466 | +3.5%  | 5.8%         | -8.7%    |     0.63 | 36%        |        2.39 |        -1.27 |          0.06  | 82%        | 175%                     |
| G eps>=5% +20d        |     1091 | +4.1%  | 6.3%         | -9.3%    |     0.68 | 31%        |        3.46 |        -1.45 |          0.086 | 93%        | 154%                     |
| A ema+fixed (as live) |      558 | +4.8%  | 6.2%         | -10.2%   |     0.8  | 41%        |        1.59 |        -0.76 |          0.203 | 72%        | 97%                      |

### Detail, holdout 2023-2026 (Alpaca)

| setup                 |   trades | CAGR   | volatility   | max DD   |   Sharpe | win rate   |   avg win R |   avg loss R |   expectancy R | exposure   | top-5% share of profit   |
|:----------------------|---------:|:-------|:-------------|:---------|---------:|:-----------|------------:|-------------:|---------------:|:-----------|:-------------------------|
| G eps>=5% +10d        |      467 | +1.1%  | 5.6%         | -9.5%    |     0.23 | 34%        |        2.35 |        -1.09 |          0.076 | 87%        | 723%                     |
| G eps>=5% +20d        |      342 | +3.3%  | 6.2%         | -12.6%   |     0.55 | 28%        |        4.24 |        -1.14 |          0.385 | 94%        | 273%                     |
| A ema+fixed (as live) |      220 | -1.2%  | 6.6%         | -12.1%   |    -0.14 | 33%        |        1.61 |        -0.81 |         -0.007 | 82%        | n/a (no profit)          |

## Signal level (every filled signal, Alpaca)

| setup                 | period              |   signals filled | win rate   |   median R |   expectancy R (capped +-5) |   t (weekly) |   median stop distance % |   avg return % per trade |   avg hold (sessions) |
|:----------------------|:--------------------|-----------------:|:-----------|-----------:|----------------------------:|-------------:|-------------------------:|-------------------------:|----------------------:|
| G eps>=5% +10d        | in-sample 2010-2022 |             5133 | 37%        |     -0.516 |                      -0.034 |       -0.671 |                    2.419 |                    0.343 |                 5.636 |
| G eps>=5% +20d        | in-sample 2010-2022 |             5133 | 33%        |     -0.758 |                      -0.07  |       -0.336 |                    2.419 |                    0.488 |                 9.646 |
| A ema+fixed (as live) | in-sample 2010-2022 |              756 | 40%        |     -0.521 |                       0.172 |        2.8   |                    3.885 |                    0.693 |                10.766 |
| G eps>=5% +10d        | holdout 2023-2026   |             2192 | 34%        |     -0.54  |                      -0.148 |        0.056 |                    2.845 |                    0.116 |                 5.492 |
| G eps>=5% +20d        | holdout 2023-2026   |             2192 | 30%        |     -0.757 |                      -0.163 |        0.298 |                    2.845 |                    0.35  |                 9.289 |
| A ema+fixed (as live) | holdout 2023-2026   |              431 | 35%        |     -0.666 |                       0.049 |        0.576 |                    4.507 |                    0.025 |                10.585 |

G's R multiples are hard to read: its stop is the day-1 low, which is often very close to the day-1
close (median 2.4% below it), so a gap through the stop can produce losses of several R, and a normal
up-move can produce wins of 10R+. The typical G trade loses about half its planned risk (median R about
-0.5); the average is positive only because of a minority of large winners. The dollar-based portfolio
results above are the reliable comparison.

## Drop rules

DSR: 13 trials (the addendum's running count: Step 0, 10 E variants, 2 G variants), trial-Sharpe variance
from every earnings variant run in the project, in-sample 2010-2022 daily portfolio returns. Correlation:
daily portfolio returns vs A, 2010-2022.

| setup          | platform   |   in-sample Sharpe |   holdout Sharpe |   x2-cost Sharpe (in-sample) |   DSR | top-5% share   |   corr with A | verdict                                                                                                                                 |
|:---------------|:-----------|-------------------:|-----------------:|-----------------------------:|------:|:---------------|--------------:|:----------------------------------------------------------------------------------------------------------------------------------------|
| G eps>=5% +10d | Alpaca     |               0.63 |             0.23 |                         0.52 |  0.87 | 175%           |          0.59 | drop: holdout Sharpe 0.23 (in-sample 0.63); DSR 0.87; best 5% of trades = 175% of profit                                                |
| G eps>=5% +10d | IG         |               0.42 |            -0.16 |                         0.09 |  0.87 | 260%           |          0.59 | drop: holdout Sharpe -0.16 (in-sample 0.42); DSR 0.87; best 5% of trades = 260% of profit                                               |
| G eps>=5% +20d | Alpaca     |               0.68 |             0.55 |                         0.61 |  0.91 | 154%           |          0.61 | drop: best 5% of trades = 154% of profit; corr with A 0.61 without higher Sharpe (0.68 vs A 0.80)                                       |
| G eps>=5% +20d | IG         |               0.46 |             0.06 |                         0.16 |  0.91 | 221%           |          0.61 | drop: holdout Sharpe 0.06 (in-sample 0.46); best 5% of trades = 221% of profit; corr with A 0.61 without higher Sharpe (0.46 vs A 0.60) |

**No G variant passes.** The +20-day version comes closest: it passes the holdout, DSR (0.91) and
doubled-cost rules, but fails on profit concentration (its best 5% of trades produce about 150% of the
profit, like A) and on correlation with A (0.61) without a higher in-sample Sharpe.

## Verdict: should the live bot switch from A to G?

**Not on this evidence.** Over 2010-2022, A had the better risk-adjusted return (Sharpe 0.80 vs 0.68 for
G +20d and 0.63 for G +10d). G +20d did better since 2020 (0.62 vs 0.41) and much better in the
2023-26 holdout (0.55 vs -0.15), where A lost money. That's the one encouraging result: it suggests a
simpler, broader PEAD rule (any 5% beat that the market confirms on day 1, held ~20 days) has decayed
less than A's narrower gap-and-volume filter. But G +20d fails two drop rules, its edge per trade is
small and driven by a few big winners, and the +10d version collapsed in the holdout (0.23). Both
would need the revenue-beat variants and more live data before switching.

**Platform:** Alpaca. On IG, funding and spread at a ~10-20 day hold take most of the edge: G +20d's
in-sample Sharpe drops from 0.68 to 0.46, its holdout Sharpe to 0.06, and with IG costs doubled to
0.16 in-sample and -0.36 in the holdout.

As the addendum says, switching the live bot is your decision. I haven't changed anything live.

## Variants counted

2 run (G, EPS-only, +10d and +20d). Addendum running total: **13**. The 2 revenue-beat variants will
be added when run. See [VARIANT_LEDGER.md](../VARIANT_LEDGER.md).
