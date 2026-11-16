# Research addendum, Setup F: short-term momentum in high-turnover large caps (long-only)

Medhat & Schmeling (2022) rule, point-in-time S&P 500, **from 2016** (your choice after the data
assessment). Code: `research/setup_f.py`, `scripts/run_setup_f.py` (decisions fixed in its docstring
before results), `scripts/f_verify_ciks.py`. Results: `results_*.csv`, `picks_log.csv`, `drop_rules.csv`.
Pre-holdout results committed in `722e72a` before the one-time holdout run.

## Data: how the three fixes were applied

- **Turnover basis and splits:** raw consolidated (SIP) volume from Alpaca divided by raw share counts,
  moved to the month-end split basis with the split factor (raw close / split-adjusted close; e.g.
  AAPL 4.0 before its 2020 split, 1.0 after). Tested in `tests/test_setup_f.py`.
- **Company IDs:** the market-cap check in `f_verify_ciks.py` showed that name-search matches can't
  be trusted. Replacements it "found" were wrong companies (ADT -> ADTRAN, Carrier -> Star Bulk
  Carriers, TripAdvisor -> Liberty TripAdvisor). So SEC counts are used **only** where the company ID
  comes from Wikipedia's CIK column or SEC's own ticker map; everything else uses **Yahoo's
  per-ticker share history** (from Nov 2015, delisted names included), used only 45 days after its
  date because Yahoo has no filing dates. Where both exist and differ by >25%, Yahoo's
  ticker-specific count wins. SEC also misses multi-class companies (V, STZ, TSN) and has gaps for
  some large names (XOM, DIS, MA); Yahoo covers these.
- **Dual-class lines excluded:** GOOG/GOOGL, FOX/FOXA, NWS/NWSA, UA/UAA, BF.B, BRK.B, DISCA/DISCK.

**Coverage:** 62,090 of 63,327
member-months (98%)
have a point-in-time turnover figure. Sources: SEC 55,246, Yahoo 6,155,
Yahoo because SEC disagreed 689, none 1,237. On average
466 eligible names a month and 19.2 picks.

## Results: CAGR / max drawdown / excess Sharpe (monthly, over T-bills)

### Alpaca (3 bps per side per name per month)

| book                   | development 2016-2020   | validation 2021-2022   | in-sample 2016-2022   | 2016-2019            | 2020-2026            | holdout 2023-2026    |
|:-----------------------|:------------------------|:-----------------------|:----------------------|:---------------------|:---------------------|:---------------------|
| F base                 | +12.3% / -34% / 0.62    | -5.5% / -25% / -0.18   | +6.8% / -34% / 0.37   | +10.2% / -24% / 0.57 | +13.3% / -25% / 0.50 | +22.4% / -22% / 0.73 |
| F crash guard          | +9.1% / -37% / 0.49     | -3.3% / -22% / -0.17   | +5.3% / -37% / 0.31   | +7.9% / -25% / 0.45  | +13.1% / -22% / 0.51 | +22.4% / -22% / 0.73 |
| F skip early reporters | +12.8% / -36% / 0.63    | -3.1% / -26% / -0.06   | +8.0% / -36% / 0.41   | +9.6% / -25% / 0.54  | +14.3% / -26% / 0.54 | +21.5% / -24% / 0.72 |
| EW universe            | +12.8% / -29% / 0.68    | +1.4% / -20% / 0.11    | +9.3% / -29% / 0.52   | +13.0% / -15% / 0.92 | +10.0% / -27% / 0.45 | +14.3% / -12% / 0.74 |
| 12-1 momentum          | +11.5% / -21% / 0.69    | -1.5% / -19% / -0.06   | +7.6% / -21% / 0.46   | +10.7% / -18% / 0.78 | +12.6% / -21% / 0.59 | +20.1% / -13% / 0.94 |
| SPY buy & hold         | +16.6% / -19% / 1.02    | +2.6% / -24% / 0.18    | +12.4% / -24% / 0.74  | +16.1% / -14% / 1.28 | +14.9% / -24% / 0.75 | +20.9% / -8% / 1.24  |

### IG daily-funded spread bets

| book                   | development 2016-2020   | validation 2021-2022   | in-sample 2016-2022   | 2016-2019           | 2020-2026           | holdout 2023-2026    |
|:-----------------------|:------------------------|:-----------------------|:----------------------|:--------------------|:--------------------|:---------------------|
| F base                 | +7.1% / -39% / 0.38     | -9.5% / -27% / -0.36   | +2.0% / -39% / 0.15   | +4.9% / -25% / 0.29 | +6.5% / -30% / 0.26 | +13.4% / -24% / 0.43 |
| F crash guard          | +4.2% / -42% / 0.25     | -6.8% / -23% / -0.39   | +0.9% / -42% / 0.08   | +2.9% / -28% / 0.18 | +6.5% / -26% / 0.26 | +13.4% / -24% / 0.43 |
| F skip early reporters | +7.6% / -41% / 0.40     | -7.2% / -28% / -0.24   | +3.1% / -41% / 0.20   | +4.4% / -26% / 0.26 | +7.5% / -30% / 0.30 | +12.5% / -26% / 0.41 |
| EW universe            | +7.6% / -30% / 0.42     | -2.8% / -23% / -0.13   | +4.5% / -30% / 0.27   | +7.6% / -17% / 0.54 | +3.5% / -27% / 0.12 | +5.9% / -14% / 0.16  |
| 12-1 momentum          | +6.5% / -27% / 0.40     | -5.5% / -23% / -0.30   | +2.9% / -27% / 0.19   | +5.4% / -20% / 0.38 | +6.1% / -27% / 0.26 | +11.4% / -15% / 0.47 |

Holding months run from the first open to the last close (as written), so F and the two benchmarks
miss the one overnight between months; SPY buy-and-hold doesn't. The crash guard was on in
10 of the 83 in-sample months and never during the holdout, so its holdout
result is identical to the base.

## Diagnostics

- **Overlap with Setup A:** 32% of F's picks
  reported an EPS beat in the formation month. Monthly correlation with A: ~0.5.
- **After big market falls** (months after SPY fell 5%+; 9 months in 2016-2022): F base
  averaged +4.9%, equal-weight +4.2%, 12-1 momentum +4.0%.
  No momentum crash showed up in this sample: F did best in those rebounds. The
  2021-2022 validation block was its weak spot (excess Sharpe -0.18).

## Drop rules

DSR: 16 trials (addendum count), trial-Sharpe variance across F's variants and the two
same-timing benchmarks, 2016-2022 monthly excess returns. "Edge" is measured against the equal-weight
universe benchmark (same names, timing and costs), the comparison the addendum asks for.

| variant                |   in-sample excess Sharpe |   holdout excess Sharpe |   DSR | top-5% months   |   corr with A (monthly) | verdict                                                                                                                      |
|:-----------------------|--------------------------:|------------------------:|------:|:----------------|------------------------:|:-----------------------------------------------------------------------------------------------------------------------------|
| F base                 |                      0.37 |                    0.73 |  0.72 | 107%            |                    0.5  | drop: DSR 0.72; no edge over equal-weight at x2 costs (0.33 vs 0.48; at x1 0.37 vs 0.52); best 5% of months = 107% of profit |
| F crash guard          |                      0.31 |                    0.73 |  0.67 | 115%            |                    0.49 | drop: DSR 0.67; no edge over equal-weight at x2 costs (0.28 vs 0.48; at x1 0.31 vs 0.52); best 5% of months = 115% of profit |
| F skip early reporters |                      0.41 |                    0.72 |  0.75 | 98%             |                    0.53 | drop: DSR 0.75; no edge over equal-weight at x2 costs (0.38 vs 0.48; at x1 0.41 vs 0.52); best 5% of months = 98% of profit  |

## Verdict

**F doesn't pass.** In-sample (2016-2022) it trailed simply equal-weighting the same universe even
before costs (excess Sharpe 0.37 vs 0.52), its DSR is 0.67-0.75, and a handful of months drive the
profit. It did well in the 2023-26 holdout (22% a year), but no better than equal-weighting (0.73 vs
0.74), and behind 12-1 momentum (0.94) and SPY (1.24), with twice SPY's volatility. The high-turnover
short-term momentum effect from the paper doesn't show up as a usable edge in large caps since 2016.
On IG, funding on 100% of the notional all month takes it to roughly zero once costs double.
