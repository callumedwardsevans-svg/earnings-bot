# Post-hoc controls for the out-of-sample result

Post-hoc controls for the 2002-2015 out-of-sample result (NOT part of the pre-registration).

Question: is Setup A's market-adjusted excess return a PEAD effect, or just that today's
S&P 500 members (the survivors) beat SPY whatever you do with them?

Control: every report with known timing in the same stocks, entered and exited with the
same machinery (day-2 open limit, stop = max(day-1 low, limit - 2 ATR), 3R target, 20-day
time exit, flat before next report) but with none of the PEAD filters (surprise, gap,
close-in-range, volume, EMA). Liquidity filter kept. Its market-adjusted R is the
"anything in these stocks" baseline; Setup A's edge is its excess over that baseline.

## 2002-2015 (Yahoo prices)

| group                                 |   trades |   expectancy R |   market-adjusted R |    se |   t (weekly) |
|:--------------------------------------|---------:|---------------:|--------------------:|------:|-------------:|
| Setup A (ema+fixed)                   |      515 |          0.115 |               0.125 | 0.05  |         2.47 |
| Control: all reports, no PEAD filters |    10086 |         -0.017 |              -0.058 | 0.013 |        -2.85 |
| Setup A, already in S&P 500           |      380 |          0.167 |               0.174 | 0.06  |         2.81 |
| Control, already in S&P 500           |     8560 |         -0.009 |              -0.054 | 0.014 |        -1.37 |

**Setup A minus control (market-adjusted): +0.183R (se 0.052, t ≈ 3.51).**

## 2016-2025 (Alpaca prices)

| group                                 |   trades |   expectancy R |   market-adjusted R |    se |   t (weekly) |
|:--------------------------------------|---------:|---------------:|--------------------:|------:|-------------:|
| Setup A (ema+fixed)                   |      873 |          0.197 |               0.027 | 0.039 |         0.94 |
| Control: all reports, no PEAD filters |    15876 |          0.071 |              -0.038 | 0.011 |        -2.13 |
| Setup A, already in S&P 500           |      670 |          0.163 |              -0.029 | 0.044 |        -0.31 |
| Control, already in S&P 500           |    14189 |          0.067 |              -0.046 | 0.011 |        -1.94 |

**Setup A minus control (market-adjusted): +0.065R (se 0.040, t ≈ 1.59).**

