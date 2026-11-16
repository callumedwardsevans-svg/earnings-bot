# Setup F data assessment: shares outstanding and point-in-time turnover

The addendum asks for the shares-outstanding source and its completeness **before** any Setup F
backtest, and to stop if it isn't good enough. No F backtest has been run. Script:
`scripts/f_data_assessment.py`; loader: `src/earnings_bot/data/sec_shares.py`; details in
`assessment.json` and `cik_map.csv`.

## Sources tried

| Source | History | Delisted names | Point-in-time | Verdict |
|---|---|---|---|---|
| **SEC EDGAR XBRL** (`companyconcept` API; cover-page `dei:EntityCommonStockSharesOutstanding`, fallback `WeightedAverageNumberOfSharesOutstandingBasic`) | from 2009 (XBRL start) | yes (filings are kept) | **yes: every value has its filing date**, used only after it | **chosen** |
| Yahoo (`yfinance get_shares_full`) | from Nov 2015 only | yes (CELG, SIVB found) | no filing dates | cross-check only |
| Alpha Vantage balance sheet | ~5 years, 25 calls/day | partly | no | not usable |

SEC access uses a generic User-Agent (no personal details) and at most 5 requests/second.

## Coverage (S&P 500 members since 2010; 827 tickers)

- **Company ID (CIK) found for 797 of 827 tickers:** 503 current members from Wikipedia's CIK
  column, 122 from SEC's ticker map, 172 delisted names by EDGAR company-name search; 30 unresolved.
- **Shares history for 747 tickers** (692 cover-page counts, 55 weighted-average fallback).
- **Member-months with a usable count** (filed before the month end, period ended within 200 days):

| Year | all members | past members only |
|---|---|---|
| 2010 | 68% | 48% |
| 2012 | 80% | 64% |
| 2014 | 82% | 66% |
| 2016 | 85% | 69% |
| 2018 | 89% | 75% |
| 2020 | 94% | 87% |
| 2022 | 94% | 88% |
| 2024 | 96% | 95% |
| 2026 | 96% | 99% |

Overall 88% (current members 93%, past members 70%). The gap is the same one as in Step 0:
companies that left the index before ~2016, which are also the ones with no free price history.

## Accuracy

- **SEC vs Yahoo share counts** (82 checks: 30 random current members x 2018/2021/2025): median
  ratio **1.000**, 98% within 5%. The SEC data is right where it can be checked.
- **Name matching for delisted companies needs fixing.** Of 172 name-search matches, 20 look
  doubtful on name similarity and several are clearly wrong: CA Technologies -> "Cavitation
  Technologies", XL Group -> "Destination XL", CR Bard -> "Bard & Hops Crux LLC", Chesapeake Energy
  -> a joint venture, Bed Bath & Beyond -> a Canadian L.P. A wrong match with share data would give
  a wrong turnover, so this must be fixed before any backtest.

## Fixes needed before a backtest (none applied yet)

1. **Verified CIK matching:** take EDGAR's top candidates for each delisted name and keep the one
   whose share count x unadjusted price gives an S&P 500-sized market cap (roughly $3bn+) during the
   membership spell. Review the remainder by hand and drop anything unverified (expected ~20-30 names).
2. **Split basis:** SEC counts are raw; Yahoo's volume is split-adjusted. Turnover must use the same
   basis, either un-adjusting volume with split records (Yahoo has split histories for 443 of the
   tickers; Alpaca's corporate-actions API for delisted names from 2016) or adjusting the share counts.
3. **Dual-class companies** (GOOG/GOOGL, BRK.B, FOX/FOXA, NWS/NWSA, UA/UAA, BF.B): turnover must
   use the share class actually traded, not the company total.

## Other limits on Setup F

- **Start date: 2010, not 1999.** Point-in-time membership is rebuilt only from 2009 (the Wikipedia
  change table is sparse before then), and SEC XBRL starts in 2009.
- **2010-2015 is weaker:** about 70-80% of member-months have usable turnover, and many delisted
  names also lack prices before 2016. Results for those years would still be partly survivorship-biased.
- With the data starting in 2010, the protocol's split would shift (as in Setup G) to development
  2010-2018, validation 2019-2022, holdout 2023-2026.

## Verdict

**Good enough to proceed, after the three fixes above**, with an honest label: 2016-2026 is
close to complete (85-99% coverage), while 2010-2015 has gaps concentrated in companies that left
the index. If the fixes leave the 2010-2015 coverage below about 80%, the safer choice is to start
Setup F in 2016 (development 2016-2020, validation 2021-2022, holdout 2023-2026) and say so.
