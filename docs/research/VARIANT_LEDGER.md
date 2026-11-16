# Variant ledger: research addendum (Setups E, F, G; Nov 2026)

Every variant run for the addendum is counted here, including abandoned ones. Cost settings
(Alpaca / IG / ×2) and data-universe comparisons of the same rule aren't counted as separate variants.

| # | Step | Variant | Date | Notes |
|---|---|---|---|---|
| 1 | Step 0 | Setup A as live (ema+fixed, next-open scheduled exits), point-in-time S&P 500, 2010-2026 | 2026-11-12 | Also run on today's list for the before/after comparison |

**Addendum total after Step 0: 1**

Earlier in the project (before the addendum), for context in Deflated Sharpe calculations:
13 earnings variants (Setup A: 8 in-sample + the open-exit rule; Setup B: 4) and 30 Setup D
trend-filter variants (10 rules × SPY, QQQ, S&P 500 index).

| 2-11 | Setup E | 5 rules × 2 instruments (SPY, QQQ): trend only; trend + vol target; TOM only −2..+3; TOM only −3..+3; combined (trend + vol + TOM −2..+3) | 2026-11-16 | Rules as written; no tunable parameters; interpretation choices fixed in `scripts/run_setup_e.py` before results |

**Addendum total after Setup E: 11**
