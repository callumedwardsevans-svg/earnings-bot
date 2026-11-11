# Robustness checks (holdout, signal level)

Market-adjusted and clustered-error checks on the signal-level results (in-sample).

For each filled signal: excess return = stock return - SPY return over the same
entry-to-exit window, expressed in R (divided by initial risk as a % of entry).
t-stats use weekly clusters (mean R per entry week), since signals bunch in earnings
seasons and move with the market, so they aren't independent trades.

| setup   | variant   |   trades |   avg hold (sessions) |   expectancy R |   t (naive) |   t (weekly clusters) |   SPY over same window, R |   market-adjusted R |   t market-adj (weekly) | exit reasons                                              |
|:--------|:----------|---------:|----------------------:|---------------:|------------:|----------------------:|--------------------------:|--------------------:|------------------------:|:----------------------------------------------------------|
| A       | ema+fixed |      112 |                     9 |         -0.015 |       -0.12 |                  0.53 |                     0.025 |              -0.039 |                    0.57 | stop 60%, time exit 25%, open at period end 8%, target 7% |
