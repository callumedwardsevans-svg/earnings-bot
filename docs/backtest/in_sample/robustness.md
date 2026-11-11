# Robustness checks (in-sample, signal level)

Market-adjusted and clustered-error checks on the signal-level results (in-sample).

For each filled signal: excess return = stock return - SPY return over the same
entry-to-exit window, expressed in R (divided by initial risk as a % of entry).
t-stats use weekly clusters (mean R per entry week), since signals bunch in earnings
seasons and move with the market, so they aren't independent trades.

| setup   | variant     |   trades |   avg hold (sessions) |   expectancy R |   t (naive) |   t (weekly clusters) |   SPY over same window, R |   market-adjusted R |   t market-adj (weekly) | exit reasons                                                                             |
|:--------|:------------|---------:|----------------------:|---------------:|------------:|----------------------:|--------------------------:|--------------------:|------------------------:|:-----------------------------------------------------------------------------------------|
| A       | ema+fixed   |      873 |                  10.8 |          0.197 |        4.25 |                  3.17 |                     0.17  |               0.027 |                    0.94 | stop 53%, time exit 35%, target 9%, open at period end 2%, flat before report 0%         |
| A       | noema+fixed |      926 |                  10.5 |          0.175 |        3.9  |                  2.86 |                     0.156 |               0.018 |                    0.73 | stop 54%, time exit 34%, target 9%, open at period end 2%, flat before report 0%         |
| A       | ema+trail   |      873 |                   9.5 |          0.137 |        3.11 |                  2.65 |                     0.113 |               0.024 |                    1.23 | stop 47%, trailing stop 31%, time exit 19%, open at period end 2%, flat before report 0% |
| A       | noema+trail |      926 |                   9.3 |          0.115 |        2.72 |                  2.33 |                     0.103 |               0.012 |                    0.9  | stop 48%, trailing stop 31%, time exit 19%, open at period end 2%, flat before report 0% |
| B       | ema         |     9902 |                   5.1 |         -0.001 |       -0.05 |                 -0.34 |                     0.048 |              -0.048 |                   -2.27 | flat before report 66%, stop 34%, open at period end 0%                                  |
| B       | noema       |    16994 |                   5.2 |          0.047 |        6.02 |                  2.19 |                     0.077 |              -0.03  |                   -1.25 | flat before report 68%, stop 32%, open at period end 0%                                  |
