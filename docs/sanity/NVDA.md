# Earnings sanity report: NVDA

Generated 2026-11-11 from Yahoo Finance earnings dates (primary: EPS, announcement time) reconciled with Alpha Vantage `EARNINGS`, plus Alpaca SIP daily bars (split/dividend adjusted).

- `timing_source`: `agree` = Yahoo and Alpha Vantage give the same before/after-close timing.
- `day1` = first session after an after-close (amc) report, or the same session for a before-open (bmo) report.
- `day1_vol_x20d` = day-1 volume / average of the prior 20 sessions; `prev_day_vol_x20d` is the same for the session before day 1.
  If timing is right, the spike is on day 1, not the day before.
- `day1_close_pos` = where the close sits in the day's range (1 = high).

| report_date   | fiscal_q_end   | timing   | timing_source   | yahoo_time   | day1       |   eps_est |   eps_act |   surprise_% |   day1_gap_% |   day1_ret_% |   day1_close_pos |   day1_vol_x20d |   prev_day_vol_x20d | timing_check   |
|:--------------|:---------------|:---------|:----------------|:-------------|:-----------|----------:|----------:|-------------:|-------------:|-------------:|-----------------:|----------------:|--------------------:|:---------------|
| 2026-08-26    | 2026-07-31     | amc      | agree           | amc          | 2026-08-27 |      2.09 |      2.22 |         6.22 |         6.29 |         8.74 |             0.74 |            2.55 |                1.56 | agrees         |
| 2026-05-20    | 2026-04-30     | amc      | agree           | amc          | 2026-05-21 |      1.77 |      1.87 |         5.65 |        -0.53 |        -1.77 |             0.17 |            1.27 |                1.18 | no clear spike |
| 2026-02-25    | 2026-01-31     | amc      | agree           | amc          | 2026-02-26 |      1.54 |      1.62 |         5.19 |        -0.66 |        -5.45 |             0.06 |            2.02 |                1.45 | agrees         |
| 2025-11-19    | 2025-10-31     | amc      | agree           | amc          | 2025-11-20 |      1.26 |      1.30 |         3.17 |         5.06 |        -3.15 |             0.05 |            1.74 |                1.28 | agrees         |
| 2025-08-27    | 2025-07-31     | amc      | agree           | amc          | 2025-08-28 |      1.01 |      1.05 |         3.96 |        -0.43 |        -0.79 |             0.47 |            1.70 |                1.45 | agrees         |
| 2025-05-28    | 2025-04-30     | amc      | agree           | amc          | 2025-05-29 |      0.75 |      0.81 |         8.00 |         5.52 |         3.25 |             0.23 |            1.73 |                1.46 | agrees         |
| 2025-02-26    | 2025-01-31     | amc      | agree           | amc          | 2025-02-27 |      0.85 |      0.89 |         4.71 |         2.83 |        -8.48 |             0.01 |            1.71 |                1.19 | agrees         |
| 2024-11-20    | 2024-10-31     | amc      | agree           | amc          | 2024-11-21 |      0.75 |      0.81 |         8.00 |         2.37 |         0.54 |             0.49 |            1.95 |                1.50 | agrees         |

Volume spike on computed day 1 rather than the prior session: **8/8**. Reports with unknown timing (flagged, not guessed): **0**.
