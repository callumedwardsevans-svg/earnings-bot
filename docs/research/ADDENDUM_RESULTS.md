# Research addendum (Setups E, G, F): final results

Everything below follows the addendum's protocol: point-in-time S&P 500, adjusted prices, consolidated
volume, no same-bar signal and fill, Alpaca and IG costs (each also doubled), pre-committed drop rules,
and a 2023-2026 holdout run once per setup after the pre-holdout results were committed.
Details: [Step 0](step0/STEP0.md), [Setup E](setup_e/SETUP_E.md), [Setup G](setup_g/SETUP_G.md),
[Setup F data](setup_f/DATA_ASSESSMENT.md), [Setup F](setup_f/SETUP_F.md), [variant ledger](VARIANT_LEDGER.md).

## 1. Results table (after costs)

Sharpe columns: E and F use excess Sharpe over T-bills (they hold cash or T-bills part of the time);
A and G use the $10k portfolio's Sharpe, where idle cash earns 0%. In-sample periods differ because
the data does: E 2000-2022, A/G 2010-2022, F 2016-2022 (user's choice). Holdout: 2023-01 to Nov 2026
for all. *A's 2023-2026 isn't a clean holdout (those years were used in earlier A tests).

| setup                        | variant                             | in-sample period   | Sharpe measure                |   Alpaca in-sample |   Alpaca holdout |   IG in-sample |   IG holdout | holdout CAGR (Alpaca)   | drop rules                                                                                                                                                                                                                                               |
|:-----------------------------|:------------------------------------|:-------------------|:------------------------------|-------------------:|-----------------:|---------------:|-------------:|:------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| A (benchmark, live on paper) | ema+fixed, as live                  | 2010-2022*         | portfolio (idle cash 0%)      |               0.8  |            -0.14 |           0.6  |        -0.47 | -1.2%                   | fails: DSR 0.84 (Step 0), best 5% of trades = 153% of profit; not a clean holdout                                                                                                                                                                        |
| E (SPY)                      | buy & hold                          | 2000-2022          | excess over T-bills           |               0.33 |             1.03 |           0.07 |         0.5  | +20.9%                  | benchmark                                                                                                                                                                                                                                                |
| E (SPY)                      | trend only                          | 2000-2022          | excess over T-bills           |               0.55 |             0.65 |           0.25 |         0.06 | +12.4%                  | Alpaca: fails: best 5% of months = 52% of profit; IG: fails: holdout Sharpe 0.06 (in-sample 0.25); best 5% of months = 89% of profit                                                                                                                     |
| E (SPY)                      | trend + vol target                  | 2000-2022          | excess over T-bills           |               0.55 |             0.56 |           0.22 |        -0.03 | +10.7%                  | Alpaca: PASS; IG: fails: holdout Sharpe -0.03 (in-sample 0.22); best 5% of months = 83% of profit                                                                                                                                                        |
| E (SPY)                      | TOM only (-2..+3)                   | 2000-2022          | excess over T-bills           |               0.28 |             0.42 |           0.16 |         0.24 | +7.4%                   | Alpaca: fails: DSR 0.65; edge gone at x2 costs (-0.11); best 5% of months = 77% of profit; IG: fails: holdout Sharpe 0.24 (in-sample 0.16); DSR 0.65; best 5% of months = 100% of profit                                                                 |
| E (SPY)                      | TOM only (-3..+3)                   | 2000-2022          | excess over T-bills           |               0.38 |             0.49 |           0.26 |         0.26 | +8.0%                   | Alpaca: fails: DSR 0.81; best 5% of months = 73% of profit; IG: fails: holdout Sharpe 0.26 (in-sample 0.26); DSR 0.81; best 5% of months = 94% of profit                                                                                                 |
| E (SPY)                      | combined (trend + vol + TOM -2..+3) | 2000-2022          | excess over T-bills           |               0.59 |             0.65 |           0.29 |         0.07 | +12.2%                  | Alpaca: PASS; IG: fails: holdout Sharpe 0.07 (in-sample 0.29); best 5% of months = 73% of profit                                                                                                                                                         |
| E (QQQ)                      | buy & hold                          | 2000-2022          | excess over T-bills           |               0.27 |             1.1  |           0.08 |         0.71 | +28.4%                  | benchmark                                                                                                                                                                                                                                                |
| E (QQQ)                      | trend only                          | 2000-2022          | excess over T-bills           |               0.46 |             0.75 |           0.27 |         0.33 | +17.7%                  | Alpaca: fails: DSR 0.89; best 5% of months = 62% of profit; IG: fails: DSR 0.89; best 5% of months = 94% of profit                                                                                                                                       |
| E (QQQ)                      | trend + vol target                  | 2000-2022          | excess over T-bills           |               0.51 |             0.8  |           0.27 |         0.38 | +14.6%                  | Alpaca: PASS; IG: fails: best 5% of months = 75% of profit                                                                                                                                                                                               |
| E (QQQ)                      | TOM only (-2..+3)                   | 2000-2022          | excess over T-bills           |               0.26 |             0.45 |           0.17 |         0.32 | +8.5%                   | Alpaca: fails: DSR 0.62; edge gone at x2 costs (-0.05); best 5% of months = 113% of profit; IG: fails: DSR 0.62; best 5% of months = 143% of profit                                                                                                      |
| E (QQQ)                      | TOM only (-3..+3)                   | 2000-2022          | excess over T-bills           |               0.32 |             0.38 |           0.23 |         0.22 | +8.1%                   | Alpaca: fails: DSR 0.73; best 5% of months = 97% of profit; IG: fails: holdout Sharpe 0.22 (in-sample 0.23); DSR 0.73; best 5% of months = 122% of profit                                                                                                |
| E (QQQ)                      | combined (trend + vol + TOM -2..+3) | 2000-2022          | excess over T-bills           |               0.49 |             0.8  |           0.29 |         0.41 | +16.1%                  | Alpaca: fails: best 5% of months = 63% of profit; IG: fails: best 5% of months = 94% of profit                                                                                                                                                           |
| G (PEAD v2)                  | eps>=5% +10d (EPS only)             | 2010-2022          | portfolio (idle cash 0%)      |               0.63 |             0.23 |           0.42 |        -0.16 | +1.1%                   | Alpaca: fails: holdout Sharpe 0.23 (in-sample 0.63); DSR 0.87; best 5% of trades = 175% of profit; IG: fails: holdout Sharpe -0.16 (in-sample 0.42); DSR 0.87; best 5% of trades = 260% of profit                                                        |
| G (PEAD v2)                  | eps>=5% +20d (EPS only)             | 2010-2022          | portfolio (idle cash 0%)      |               0.68 |             0.55 |           0.46 |         0.06 | +3.3%                   | Alpaca: fails: best 5% of trades = 154% of profit; corr with A 0.61 without higher Sharpe (0.68 vs A 0.80); IG: fails: holdout Sharpe 0.06 (in-sample 0.46); best 5% of trades = 221% of profit; corr with A 0.61 without higher Sharpe (0.46 vs A 0.60) |
| F (high-turnover momentum)   | F base                              | 2016-2022          | excess over T-bills (monthly) |               0.37 |             0.73 |           0.15 |         0.43 | +22.4%                  | fails: DSR 0.72; no edge over equal-weight at x2 costs (0.33 vs 0.48; at x1 0.37 vs 0.52); best 5% of months = 107% of profit                                                                                                                            |
| F (high-turnover momentum)   | F crash guard                       | 2016-2022          | excess over T-bills (monthly) |               0.31 |             0.73 |           0.08 |         0.43 | +22.4%                  | fails: DSR 0.67; no edge over equal-weight at x2 costs (0.28 vs 0.48; at x1 0.31 vs 0.52); best 5% of months = 115% of profit                                                                                                                            |
| F (high-turnover momentum)   | F skip early reporters              | 2016-2022          | excess over T-bills (monthly) |               0.41 |             0.72 |           0.2  |         0.41 | +21.5%                  | fails: DSR 0.75; no edge over equal-weight at x2 costs (0.38 vs 0.48; at x1 0.41 vs 0.52); best 5% of months = 98% of profit                                                                                                                             |
| F (high-turnover momentum)   | EW universe                         | 2016-2022          | excess over T-bills (monthly) |               0.52 |             0.74 |           0.27 |         0.16 | +14.3%                  | benchmark                                                                                                                                                                                                                                                |
| F (high-turnover momentum)   | 12-1 momentum                       | 2016-2022          | excess over T-bills (monthly) |               0.46 |             0.94 |           0.19 |         0.47 | +20.1%                  | benchmark                                                                                                                                                                                                                                                |
| F (high-turnover momentum)   | SPY buy & hold                      | 2016-2022          | excess over T-bills (monthly) |               0.74 |             1.24 |                |              | +20.9%                  | benchmark                                                                                                                                                                                                                                                |

## 2. Pass / fail

**Passes (Alpaca only): three Setup E variants**: SPY trend + vol target, SPY combined (trend + vol
target + turn-of-month), QQQ trend + vol target.

**Fails:**
- **Setup A** (the live benchmark): DSR 0.84, profit concentration (best 5% of trades = 153% of profit),
  no edge left on IG. Positive but weak edge, mostly before 2020.
- **Setup E, the rest:** turn-of-month on its own (low DSR, concentration, the -2..+3 window loses its
  edge with doubled costs); trend-only versions and QQQ combined (concentration); everything on IG
  (funding).
- **Setup G (EPS-only):** +10d collapsed in the holdout (0.23); +20d held up in the holdout (0.55 vs A's
  -0.15) but fails on concentration and on correlation with A without a higher in-sample Sharpe. The
  two revenue-beat variants were not run (no free revenue-consensus history; you chose to skip them).
- **Setup F:** low DSR, profit concentration, and no edge over equal-weighting the same stocks.

## 3. Verdict on the setups that pass

**Setup E (SPY trend + vol target, SPY combined, QQQ trend + vol target).** These are literature
rules tested exactly as written, with no parameter search, DSR 0.92-0.97, and the same behaviour in
development, validation and the holdout. I think the effect is real, but it's **drawdown insurance,
not extra return**. Over 2000-2022 they roughly halved buy-and-hold's maximum drawdown and improved
risk-adjusted return, thanks to 2000-02, 2008 and 2022. In the 2023-26 bull market every variant
trailed buy-and-hold (SPY combined 12.2% a year vs 20.9%, excess Sharpe 0.65 vs 1.03). Whether it
"beats" the market depends on whether a long bear market comes along. **It belongs on Alpaca,
automated**: month-end trend checks, daily vol-target rebalancing (~50 small trades a year) and
orders at specific closes for the turn-of-month window. On IG, overnight funding (fed funds + 3.4%
on the full notional) takes the 2023-26 excess Sharpe for SPY to about zero.

Compared with Setup A, the current live bot, SPY combined has a much better Sharpe since 2010
(0.88 in 2010-19 and 0.83 in 2020-26 vs A's 0.71 and 0.41), low correlation with A (~0.4), and uses
~85% of capital rather than ~30%.

## 4. Variants tested in this addendum: **16**

Step 0: 1. Setup E: 10 (5 rules x SPY, QQQ). Setup G: 2 (EPS-only; the 2 revenue-beat variants were
never run). Setup F: 3. Benchmarks (buy-and-hold, equal-weight, 12-1 momentum) aren't counted.
Before the addendum, the project had also tried 13 earnings variants and 30 Setup D trend-filter
variants. The DSR figures above use the running addendum count at each step.

## Data limits that apply throughout

- **Survivorship:** about 15% of point-in-time member reports couldn't be tested (companies delisted
  before 2016 have no free prices or earnings history); 2010-2015 results for A and G are still
  partly biased. F starts in 2016 to avoid most of this.
- **Consensus estimates** come from vendors whose history may be revised; Yahoo and Alpha Vantage agree
  on 96% of beat/miss calls. The live bot has saved the pre-report consensus since 2026-11-12.
- **Holdouts aren't fully independent:** E's 2023-26 overlaps the Setup D results I'd already seen;
  G's overlaps the announcements seen in A's tests.

No new setup is being paper-traded. Switching or adding anything live is your decision.
