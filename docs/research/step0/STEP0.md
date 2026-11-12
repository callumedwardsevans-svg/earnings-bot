# Research addendum, Step 0: Setup A re-baselined on point-in-time data

Setup A exactly as it runs live (50-EMA filter, fixed 3R target, scheduled exits at the next
open, no regime filter), signals 2010-01-01 to 2026-11-10, $10k per window, 0.75% risk, 15% cap,
5 positions, 2 per sector. Script: `scripts/step0_rebaseline_a.py`. Raw results: `portfolio_results.csv`,
`signal_results.csv`, `coverage.json`, `trades_alpaca_2010_2026.csv`.

## 1. Ground-rule checks

**Volume (rule 3): no change needed.** Setup A's live code and every backtest fetch Alpaca bars with
`feed=DataFeed.SIP` (consolidated), the only price path in the code (`data/prices.py`). IEX volume
was checked in milestone 2 at ~3% of SIP for NVDA and was never used. The 2010-2015 part of this
re-baseline uses Yahoo daily volume, which is consolidated (Jan-Mar 2016 overlap with Alpaca SIP:
same closes, volume within 5%). **So the volume fix changes no trades**; the trade-count changes
in section 5 come from the universe fix.

**Point-in-time universe (rule 1): built, with known gaps.** See section 2.

**No same-bar signal and fill (rule 4):** day-1 signals use the day-1 close; entries are limit orders
at the day-2 open; scheduled exits are market-on-open on the due day.

**Earnings timing (rule 5):** before-open / after-close from Yahoo timestamps reconciled with Alpha
Vantage labels (milestone 2). 383 of 29,503 member reports (1.3%)
have unknown or conflicting timing and are flagged and skipped, not guessed.

**Point-in-time estimates (rule 6):** free APIs can't prove an estimate is the consensus as it
stood before the report. What I checked: on 2,277 reports where Yahoo and Alpha Vantage both give an
estimate, about 93% agree within 5% in both 2002-2015 and 2016-2026, and they agree on whether a report
was a 5%+ beat 96% of the time (1,628 reports since 2010). Finnhub's estimates differ more (63%
within 2% of Yahoo's on 425 recent reports), so it likely uses a different consensus provider.
Agreement between vendors is evidence, not proof (they may share an upstream source).
**From 2026-11-12 the live bot saves the Finnhub consensus (EPS and revenue) for every upcoming
S&P 500 report each evening** to `data/consensus_log/YYYY-MM-DD.parquet`; the last snapshot before a
report is the clean pre-report consensus for future tests.

## 2. Point-in-time S&P 500 membership

**Source:** Wikipedia's current constituents list plus its "Historical components of the S&P 500"
change table (dates, tickers added/removed, reasons), the same free source used throughout the
project. **Method:** start from today's 503 members and apply the change table backwards to 2009
(undo additions, restore removals), giving membership spells per ticker (`data/membership.py`).

**Fixes needed:** 11 ticker renames (FB to META, PCLN to BKNG, FLT to CPAY, RE to EG, DLPH to APTV,
KORS to CPRI, JOYG to JOY, UA.C to UA, SATS to ECHO, plus dated reuses: UA in 2014 is today's UAA,
IR in 2010 is today's TT), stray "|" characters in two tickers, the old Allergan vs Actavis "AGN",
and one missing row (21st Century Fox's FOX/FOXA leaving on 2019-03-19 when Disney bought it).

**Validation:**
- After the fixes, the reverse walk finds every ticker it needs to undo (0 inconsistencies), and the
  member count stays between **501 and 507 in every week from 2009 to 2026** (above 500 because of
  dual share classes).
- Spot-check of 14 index changes **against my own knowledge of S&P announcements** (not an
  independent dataset, so treat it as a sanity check): 12 match exactly (TSLA, META, UBER, ABNB,
  PLTR, DELL, SMCI and CRWD additions; SIVB, FRC, AAL and ETSY removals). NFLX: the table dates
  the addition to Fri 2010-12-17, the last session before it took effect at Monday's open, while
  other rows use the effective Monday, so dates can differ by one trading day. BBWI: I expected
  2024-09-23; the table says 2024-10-01 (BIO was the 2024-09-23 removal), and my recollection is
  more likely wrong than the table.

**Gaps (data for companies that left the index):**

| | count |
|---|---|
| Tickers that were members at some point 2010-2026 | 827 |
| still members today / left the index | 503 / 324 |
| left the index: prices from Yahoo (2009+) | 135 |
| left the index: prices from Alpaca SIP only (2016+, delisted names) | 142 |
| no free price history at all (mostly acquired/delisted before 2016) | 45 |
| left the index: with earnings history | 147 |
| tickers now used by a different company (old company has no data) | 34 |
| past members with no sector (each treated as its own sector for the 2-per-sector cap) | 278 |
| member reports found / expected (member-days / 91), 2010-2026 | 29,503 / 34,100 (87%) |
| ...of which with a price bar on day 1 | 28,671 |

So about **85% of member reports are tested**. The missing ~15% are concentrated in companies that
left the index, especially acquisitions and bankruptcies before 2016 (Yahoo drops delisted tickers;
Alpaca's history starts in 2016). The 2010-2019 results are therefore still partly survivorship-biased;
2020-2026 is much closer to clean. **Fix in progress:** the daily Alpha Vantage backfill now fetches
past members without earnings history first (about 170 names, a week at 25/day); Step 0 will be
re-run when that's done.

## 3. Cost models

Alpaca: 3 bps per side, $0 commission. IG daily-funded spread bet: 0.10% round-trip spread capped at
$0.10/share, funding (fed funds + 3.4%) / 360 per calendar night on the full notional (FRED DFF
history). Each also with every cost doubled. `backtest/costs.py`, tested in `tests/test_costs.py`.

## 4. Results: point-in-time universe

### Signal level (every filled signal, no portfolio limits)

| costs           | period                                |   signals filled | win rate   |   avg win R |   avg loss R |   expectancy R |   t (weekly) |   market-adj R |
|:----------------|:--------------------------------------|-----------------:|:-----------|------------:|-------------:|---------------:|-------------:|---------------:|
| Alpaca          | 2010-2019                             |              576 | 41%        |        1.54 |        -0.74 |          0.188 |         2.84 |          0.07  |
| Alpaca          | 2020-2026                             |              611 | 36%        |        1.65 |        -0.8  |          0.07  |         0.92 |         -0.057 |
| Alpaca          | 2010-2026                             |             1187 | 38%        |        1.6  |        -0.77 |          0.128 |         2.75 |          0.004 |
| Alpaca          | 2023-2026 (not a clean holdout for A) |              431 | 35%        |        1.6  |        -0.79 |          0.049 |         0.58 |         -0.095 |
| Alpaca x2 costs | 2010-2019                             |              576 | 40%        |        1.53 |        -0.75 |          0.171 |         2.58 |          0.053 |
| Alpaca x2 costs | 2020-2026                             |              611 | 35%        |        1.65 |        -0.81 |          0.056 |         0.73 |         -0.071 |
| Alpaca x2 costs | 2010-2026                             |             1187 | 38%        |        1.59 |        -0.79 |          0.112 |         2.44 |         -0.011 |
| Alpaca x2 costs | 2023-2026 (not a clean holdout for A) |              431 | 35%        |        1.58 |        -0.81 |          0.036 |         0.42 |         -0.109 |
| IG              | 2010-2019                             |              576 | 40%        |        1.49 |        -0.76 |          0.129 |         1.97 |          0.01  |
| IG              | 2020-2026                             |              611 | 34%        |        1.62 |        -0.82 |          0.003 |         0.03 |         -0.125 |
| IG              | 2010-2026                             |             1187 | 37%        |        1.55 |        -0.8  |          0.064 |         1.51 |         -0.059 |
| IG              | 2023-2026 (not a clean holdout for A) |              431 | 34%        |        1.53 |        -0.83 |         -0.03  |        -0.41 |         -0.174 |
| IG x2 costs     | 2010-2019                             |              576 | 38%        |        1.42 |        -0.8  |          0.052 |         0.8  |         -0.066 |
| IG x2 costs     | 2020-2026                             |              611 | 33%        |        1.53 |        -0.87 |         -0.079 |        -1.09 |         -0.207 |
| IG x2 costs     | 2010-2026                             |             1187 | 36%        |        1.48 |        -0.84 |         -0.015 |        -0.1  |         -0.139 |
| IG x2 costs     | 2023-2026 (not a clean holdout for A) |              431 | 33%        |        1.43 |        -0.88 |         -0.122 |        -1.62 |         -0.267 |

### $10k portfolio (all risk limits), each window a fresh account

| costs           | period                                |   trades | CAGR   | volatility   | max DD   |   Sharpe | win rate   |   avg win R |   avg loss R |   expectancy R | exposure   | top-5% share of profit   |
|:----------------|:--------------------------------------|---------:|:-------|:-------------|:---------|---------:|:-----------|------------:|-------------:|---------------:|:-----------|:-------------------------|
| Alpaca          | 2010-2019                             |      427 | +4.0%  | 5.8%         | -9.0%    |     0.71 | 41%        |        1.51 |        -0.74 |          0.183 | 73%        | 107%                     |
| Alpaca          | 2020-2026                             |      351 | +2.6%  | 6.9%         | -12.8%   |     0.41 | 36%        |        1.71 |        -0.81 |          0.095 | 77%        | 212%                     |
| Alpaca          | 2010-2026                             |      778 | +3.5%  | 6.3%         | -13.2%   |     0.58 | 39%        |        1.59 |        -0.77 |          0.144 | 75%        | 153%                     |
| Alpaca          | 2023-2026 (not a clean holdout for A) |      220 | -1.2%  | 6.6%         | -12.1%   |    -0.14 | 33%        |        1.61 |        -0.81 |         -0.007 | 82%        | n/a (no profit)          |
| Alpaca x2 costs | 2010-2019                             |      427 | +3.6%  | 5.8%         | -9.2%    |     0.65 | 41%        |        1.51 |        -0.75 |          0.167 | 73%        | 117%                     |
| Alpaca x2 costs | 2020-2026                             |      351 | +2.1%  | 6.9%         | -14.7%   |     0.34 | 36%        |        1.7  |        -0.82 |          0.08  | 77%        | 265%                     |
| Alpaca x2 costs | 2010-2026                             |      778 | +3.1%  | 6.3%         | -14.0%   |     0.52 | 38%        |        1.59 |        -0.78 |          0.128 | 75%        | 169%                     |
| Alpaca x2 costs | 2023-2026 (not a clean holdout for A) |      220 | -1.5%  | 6.6%         | -13.0%   |    -0.19 | 33%        |        1.59 |        -0.82 |         -0.022 | 82%        | n/a (no profit)          |
| IG              | 2010-2019                             |      427 | +2.7%  | 5.8%         | -9.6%    |     0.49 | 40%        |        1.47 |        -0.76 |          0.125 | 73%        | 156%                     |
| IG              | 2020-2026                             |      351 | +0.7%  | 6.9%         | -19.7%   |     0.14 | 35%        |        1.66 |        -0.83 |          0.031 | 77%        | 786%                     |
| IG              | 2010-2026                             |      778 | +1.9%  | 6.3%         | -19.7%   |     0.33 | 38%        |        1.55 |        -0.8  |          0.083 | 75%        | 263%                     |
| IG              | 2023-2026 (not a clean holdout for A) |      219 | -3.3%  | 6.7%         | -18.4%   |    -0.47 | 32%        |        1.52 |        -0.84 |         -0.079 | 82%        | n/a (no profit)          |
| IG x2 costs     | 2010-2019                             |      427 | +1.0%  | 5.8%         | -10.2%   |     0.2  | 38%        |        1.41 |        -0.8  |          0.051 | 73%        | 405%                     |
| IG x2 costs     | 2020-2026                             |      351 | -1.4%  | 7.0%         | -26.8%   |    -0.17 | 34%        |        1.59 |        -0.88 |         -0.047 | 77%        | n/a (no profit)          |
| IG x2 costs     | 2010-2026                             |      778 | -0.0%  | 6.4%         | -27.2%   |     0.03 | 36%        |        1.49 |        -0.84 |          0.007 | 75%        | n/a (no profit)          |
| IG x2 costs     | 2023-2026 (not a clean holdout for A) |      218 | -6.2%  | 6.7%         | -24.9%   |    -0.93 | 31%        |        1.42 |        -0.89 |         -0.17  | 81%        | n/a (no profit)          |

"Top-5% share of profit" above 100% means the best 5% of trades earned more than the total; the
other 95% lost money in aggregate.

### SPY buy & hold, same windows

| period                                | CAGR   | volatility   | max DD   |   Sharpe |
|:--------------------------------------|:-------|:-------------|:---------|---------:|
| 2010-2019                             | +13.3% | 14.7%        | -19.3%   |     0.92 |
| 2020-2026                             | +14.6% | 20.0%        | -33.7%   |     0.78 |
| 2010-2026                             | +13.8% | 17.1%        | -33.7%   |     0.85 |
| 2023-2026 (not a clean holdout for A) | +20.7% | 15.1%        | -18.8%   |     1.33 |

## 5. Before and after the universe fix (today's list = the earlier, survivorship-biased universe)

Signals reaching the end of the funnel: **1,385 with today's list, 1,267 point-in-time**.

### Signal level, today's list

| costs           | period                                |   signals filled | win rate   |   avg win R |   avg loss R |   expectancy R |   t (weekly) |   market-adj R |
|:----------------|:--------------------------------------|-----------------:|:-----------|------------:|-------------:|---------------:|-------------:|---------------:|
| Alpaca          | 2010-2019                             |              616 | 42%        |        1.52 |        -0.76 |          0.205 |         2.34 |          0.114 |
| Alpaca          | 2020-2026                             |              683 | 37%        |        1.64 |        -0.78 |          0.115 |         1.97 |         -0.026 |
| Alpaca          | 2010-2026                             |             1299 | 39%        |        1.58 |        -0.77 |          0.158 |         3.06 |          0.04  |
| Alpaca          | 2023-2026 (not a clean holdout for A) |              481 | 38%        |        1.62 |        -0.78 |          0.139 |         2.01 |         -0.019 |
| Alpaca x2 costs | 2010-2019                             |              616 | 42%        |        1.5  |        -0.77 |          0.189 |         2.09 |          0.098 |
| Alpaca x2 costs | 2020-2026                             |              683 | 37%        |        1.63 |        -0.79 |          0.101 |         1.78 |         -0.04  |
| Alpaca x2 costs | 2010-2026                             |             1299 | 39%        |        1.57 |        -0.78 |          0.143 |         2.75 |          0.025 |
| Alpaca x2 costs | 2023-2026 (not a clean holdout for A) |              481 | 38%        |        1.61 |        -0.79 |          0.126 |         1.86 |         -0.032 |
| IG              | 2010-2019                             |              616 | 41%        |        1.46 |        -0.78 |          0.147 |         1.51 |          0.057 |
| IG              | 2020-2026                             |              683 | 35%        |        1.6  |        -0.8  |          0.049 |         1.1  |         -0.093 |
| IG              | 2010-2026                             |             1299 | 38%        |        1.53 |        -0.79 |          0.095 |         1.86 |         -0.022 |
| IG              | 2023-2026 (not a clean holdout for A) |              481 | 37%        |        1.54 |        -0.81 |          0.061 |         1.11 |         -0.097 |
| IG x2 costs     | 2010-2019                             |              616 | 40%        |        1.41 |        -0.81 |          0.073 |         0.39 |         -0.017 |
| IG x2 costs     | 2020-2026                             |              683 | 34%        |        1.53 |        -0.85 |         -0.031 |         0.01 |         -0.173 |
| IG x2 costs     | 2010-2026                             |             1299 | 37%        |        1.47 |        -0.83 |          0.018 |         0.3  |         -0.099 |
| IG x2 costs     | 2023-2026 (not a clean holdout for A) |              481 | 36%        |        1.46 |        -0.85 |         -0.03  |         0    |         -0.188 |

### Portfolio, today's list

| costs           | period                                |   trades | CAGR   | volatility   | max DD   |   Sharpe | win rate   |   avg win R |   avg loss R |   expectancy R | exposure   | top-5% share of profit   |
|:----------------|:--------------------------------------|---------:|:-------|:-------------|:---------|---------:|:-----------|------------:|-------------:|---------------:|:-----------|:-------------------------|
| Alpaca          | 2010-2019                             |      436 | +4.2%  | 6.1%         | -9.4%    |     0.7  | 42%        |        1.49 |        -0.76 |          0.181 | 74%        | 104%                     |
| Alpaca          | 2020-2026                             |      369 | +4.3%  | 7.3%         | -11.2%   |     0.62 | 39%        |        1.58 |        -0.78 |          0.132 | 78%        | 136%                     |
| Alpaca          | 2010-2026                             |      805 | +4.3%  | 6.7%         | -11.2%   |     0.66 | 40%        |        1.53 |        -0.77 |          0.159 | 76%        | 129%                     |
| Alpaca          | 2023-2026 (not a clean holdout for A) |      228 | +5.0%  | 7.0%         | -7.2%    |     0.73 | 39%        |        1.6  |        -0.78 |          0.15  | 85%        | 131%                     |
| Alpaca x2 costs | 2010-2019                             |      436 | +3.8%  | 6.2%         | -9.6%    |     0.64 | 42%        |        1.48 |        -0.78 |          0.165 | 74%        | 113%                     |
| Alpaca x2 costs | 2020-2026                             |      369 | +3.9%  | 7.3%         | -11.4%   |     0.56 | 38%        |        1.57 |        -0.79 |          0.118 | 78%        | 150%                     |
| Alpaca x2 costs | 2010-2026                             |      805 | +3.9%  | 6.7%         | -11.7%   |     0.61 | 40%        |        1.52 |        -0.78 |          0.143 | 76%        | 138%                     |
| Alpaca x2 costs | 2023-2026 (not a clean holdout for A) |      228 | +4.7%  | 7.1%         | -7.4%    |     0.69 | 39%        |        1.59 |        -0.79 |          0.136 | 85%        | 138%                     |
| IG              | 2010-2019                             |      436 | +2.8%  | 6.2%         | -10.7%   |     0.48 | 41%        |        1.43 |        -0.79 |          0.125 | 74%        | 149%                     |
| IG              | 2020-2026                             |      369 | +2.2%  | 7.3%         | -13.5%   |     0.34 | 37%        |        1.55 |        -0.8  |          0.067 | 78%        | 252%                     |
| IG              | 2010-2026                             |      805 | +2.5%  | 6.7%         | -13.9%   |     0.41 | 39%        |        1.48 |        -0.79 |          0.098 | 76%        | 201%                     |
| IG              | 2023-2026 (not a clean holdout for A) |      228 | +2.3%  | 7.0%         | -8.4%    |     0.35 | 38%        |        1.51 |        -0.82 |          0.07  | 85%        | 277%                     |
| IG x2 costs     | 2010-2019                             |      436 | +1.1%  | 6.2%         | -12.8%   |     0.2  | 39%        |        1.39 |        -0.81 |          0.052 | 74%        | 374%                     |
| IG x2 costs     | 2020-2026                             |      369 | -0.2%  | 7.3%         | -17.6%   |     0.01 | 35%        |        1.51 |        -0.83 |         -0.012 | 78%        | n/a (no profit)          |
| IG x2 costs     | 2010-2026                             |      805 | +0.6%  | 6.7%         | -17.3%   |     0.12 | 37%        |        1.45 |        -0.82 |          0.023 | 76%        | 861%                     |
| IG x2 costs     | 2023-2026 (not a clean holdout for A) |      228 | -0.8%  | 7.1%         | -10.0%   |    -0.08 | 36%        |        1.47 |        -0.85 |         -0.023 | 85%        | n/a (no profit)          |

The difference is biggest in **2023-2026**: Alpaca Sharpe +0.73 on today's list vs -0.15 point-in-time.
Today's list includes stocks that joined the index *because* they had surged (e.g. PLTR, SMCI, APP)
and counts their earnings signals from before they joined. Point-in-time, those signals aren't
available. The earlier "recent" results for Setup A were inflated by this.

## 6. Setup A against the addendum's drop rules

| Rule | Result | Verdict |
|---|---|---|
| Holdout Sharpe < 0.3 or < half in-sample | 2023-2026 Sharpe -0.15 (Alpaca), but not a clean holdout for A (those years were used in earlier tests) | fails (informational) |
| DSR probability < 0.90 | DSR = **0.84** with 14 trials (13 earlier A/B variants + this run); daily SR 0.0363 vs expected max under the null 0.0207 | **fails** |
| Edge disappears with costs doubled | Alpaca x2: +0.11R/signal, survives. IG x2: -0.015R, disappears | passes on Alpaca, fails on IG |
| > 50% of profit from < 5% of trades | the best 5% of trades produce about 150% of total profit (Alpaca, 2010-2026) | **fails** |
| Correlation with A > 0.6 | n/a (this is A) | - |

**Verdict on A as the benchmark:** on point-in-time data, A has a positive but weak edge on Alpaca
(+0.13R per signal 2010-2026, t about 2.8; portfolio Sharpe 0.58 vs SPY 0.85), driven by 2010-2019
(+0.19R) and close to zero since 2020 (+0.07R, t about 0.9). It **fails two drop rules (DSR and profit
concentration) and doesn't survive IG costs**. Under the addendum's rules A wouldn't be kept; it
stays live on paper as instructed, as the benchmark and pipeline test. The new setups have to beat
**portfolio Sharpe 0.58 (Alpaca, 2010-2026), 0.41 since 2020.**

IG is clearly the wrong platform for A: at an ~11-day average hold, funding plus spread take about
0.06R per trade, roughly half of A's edge, and all of it since 2020.

## 7. Variant count (this addendum)

Step 0: **1 rule** (A as live), run on 2 universes (point-in-time and today's list, for the
before/after comparison) and 4 cost settings. Counted as **1 variant** (cost settings and the
universe comparison don't change the rule). Running total: [VARIANT_LEDGER.md](../VARIANT_LEDGER.md).

## 8. Flags before E, G and F

- **Setup E's holdout (2023-2026) isn't fully unseen.** Setup D already tested SPY/QQQ trend filters
  over 2024-11 to 2026-11 (D's holdout). E's rules differ (200-day SMA at month-end, vol target,
  turn-of-month tilt), but I've seen how trend filters did in those years. I'll keep E's 2023-2026
  holdout as specified and note the overlap next to the result.
- **G's holdout overlaps A's.** A's held-out year and A's point-in-time results above cover the same
  announcements G will be tested on. G's rules differ, but its 2023-2026 holdout isn't fully
  independent of what's been seen for A.
- **G needs revenue consensus history.** The free sources used so far have none (Yahoo and Alpha
  Vantage give EPS only; Finnhub's revenue goes back about a month). The "EPS and revenue beat"
  variants can't be backtested without another source. I'll look for one in the G step and stop if
  there isn't one, rather than approximate.
