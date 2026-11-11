# Backtest results: in-sample-regime-ema200 (2016-04-01 to 2025-11-10)

Starting equity $10,000; risk 0.75%/trade, max 15% per position, max 5 positions (2 per sector), 2% daily loss limit; whole shares; 5 bps slippage per fill; $0 commission.

## 1. Signal level (every filled signal, no portfolio limits)

This is the cleanest test of whether the setup has an edge, because it isn't affected by account size or which signals happened to overlap. `se` = standard error of the mean R; an expectancy within about 2 se of zero isn't distinguishable from no edge.

| setup   | variant     |   signals | fill rate   |   trades | win rate   |   avg win R |   avg loss R |   expectancy R |    se |   t-stat |
|:--------|:------------|----------:|:------------|---------:|:-----------|------------:|-------------:|---------------:|------:|---------:|
| A       | ema+fixed   |       833 | 94%         |      782 | 41%        |        1.6  |        -0.79 |          0.18  | 0.049 |     3.7  |
| A       | noema+fixed |       866 | 94%         |      812 | 40%        |        1.6  |        -0.79 |          0.167 | 0.048 |     3.49 |
| A       | ema+trail   |       833 | 94%         |      782 | 44%        |        1.22 |        -0.76 |          0.11  | 0.046 |     2.41 |
| A       | noema+trail |       866 | 94%         |      812 | 43%        |        1.21 |        -0.76 |          0.093 | 0.044 |     2.1  |
| B       | ema         |      9109 | 100%        |     9109 | 48%        |        0.86 |        -0.82 |         -0.014 | 0.011 |    -1.28 |
| B       | noema       |     14342 | 100%        |    14342 | 48%        |        0.88 |        -0.81 |          0.001 | 0.008 |     0.12 |

## 2. Portfolio ($10k account, all limits applied) vs SPY

| setup   | variant     |   trades | win rate   |   avg win R |   avg loss R |   expectancy R | total return   | CAGR   | max DD   |   Sharpe | exposure (time)   | avg capital deployed   |
|:--------|:------------|---------:|:-----------|------------:|-------------:|---------------:|:---------------|:-------|:---------|---------:|:------------------|:-----------------------|
| A       | ema+fixed   |      461 | 39%        |        1.63 |        -0.79 |          0.147 | +40.2%         | +3.6%  | -10.7%   |     0.59 | 73%               | 27%                    |
| A       | noema+fixed |      477 | 37%        |        1.6  |        -0.79 |          0.102 | +26.0%         | +2.4%  | -13.3%   |     0.41 | 74%               | 28%                    |
| A       | ema+trail   |      468 | 43%        |        1.3  |        -0.77 |          0.131 | +38.9%         | +3.5%  | -13.4%   |     0.6  | 70%               | 25%                    |
| A       | noema+trail |      484 | 43%        |        1.26 |        -0.77 |          0.096 | +27.7%         | +2.6%  | -15.7%   |     0.45 | 71%               | 25%                    |
| B       | ema         |     1449 | 48%        |        0.93 |        -0.83 |          0.011 | +10.9%         | +1.1%  | -18.6%   |     0.17 | 80%               | 42%                    |
| B       | noema       |     1650 | 48%        |        0.95 |        -0.81 |          0.038 | +42.0%         | +3.7%  | -26.0%   |     0.44 | 85%               | 48%                    |

**SPY buy & hold:** total return +283.7%, CAGR +15.0%, max DD -33.8%, Sharpe 0.88, exposure 100%.

![Setup A](equity_setup_A.png)

![Setup B](equity_setup_B.png)

## 3. Robustness: only signals after the stock joined the S&P 500

Partly addresses survivorship bias: drops signals from before a stock was in the index (using today's list's 'date added'). It can't add back the ~22% of names that left the index.

| setup   | variant     |   trades |   expectancy R | total return   | max DD   |   Sharpe |
|:--------|:------------|---------:|---------------:|:---------------|:---------|---------:|
| A       | ema+fixed   |      390 |          0.099 | +14.3%         | -15.2%   |     0.29 |
| A       | noema+fixed |      400 |          0.082 | +10.4%         | -16.1%   |     0.22 |
| A       | ema+trail   |      399 |          0.066 | +8.4%          | -12.6%   |     0.19 |
| A       | noema+trail |      410 |          0.043 | +4.0%          | -13.5%   |     0.1  |
| B       | ema         |     1387 |          0.013 | +7.8%          | -15.8%   |     0.14 |
| B       | noema       |     1602 |          0.034 | +34.0%         | -27.1%   |     0.39 |

## 4. Expectancy by year (signal level, R per trade; trade count in brackets)

|      | A ema+fixed   | A noema+fixed   | A ema+trail   | A noema+trail   | B ema        | B noema      |
|-----:|:--------------|:----------------|:--------------|:----------------|:-------------|:-------------|
| 2016 | +0.35 (46)    | +0.27 (49)      | +0.30 (46)    | +0.23 (49)      | -0.01 (670)  | +0.03 (1026) |
| 2017 | +0.26 (80)    | +0.25 (81)      | +0.12 (80)    | +0.10 (81)      | +0.20 (1069) | +0.21 (1456) |
| 2018 | +0.33 (77)    | +0.31 (80)      | +0.23 (77)    | +0.22 (80)      | -0.09 (787)  | -0.13 (1481) |
| 2019 | +0.18 (88)    | +0.16 (91)      | +0.17 (88)    | +0.15 (91)      | -0.05 (980)  | +0.02 (1438) |
| 2020 | +0.14 (66)    | +0.18 (68)      | -0.07 (66)    | -0.05 (68)      | +0.00 (974)  | +0.03 (1341) |
| 2021 | +0.18 (59)    | +0.12 (64)      | +0.12 (59)    | +0.07 (64)      | +0.03 (1252) | +0.09 (1847) |
| 2022 | -0.46 (18)    | -0.53 (21)      | -0.48 (18)    | -0.53 (21)      | -0.49 (322)  | -0.45 (665)  |
| 2023 | +0.14 (102)   | +0.15 (107)     | +0.14 (102)   | +0.12 (107)     | -0.09 (1007) | -0.12 (1680) |
| 2024 | +0.24 (133)   | +0.25 (135)     | +0.15 (133)   | +0.15 (135)     | +0.06 (1215) | +0.10 (1942) |
| 2025 | +0.05 (113)   | +0.04 (116)     | +0.02 (113)   | +0.01 (116)     | -0.10 (833)  | -0.04 (1466) |

## 5. Signal funnel (how many reports survive each filter)

**Setup A (ema+fixed)**: reports in period **18,606** → timing known (bmo/amc) **18,396** → price data on day 1 **18,276** → EPS surprise >= 5% **9,124** → gap >= 3% **2,642** → close in upper half **1,324** → volume >= 2x avg **1,074** → liquid (price > $10, ADV > $50m) **989** → above 50 EMA **931** → market regime on **833** → next session exists **833**

**Setup A (noema+fixed)**: reports in period **18,606** → timing known (bmo/amc) **18,396** → price data on day 1 **18,276** → EPS surprise >= 5% **9,124** → gap >= 3% **2,642** → close in upper half **1,324** → volume >= 2x avg **1,074** → liquid (price > $10, ADV > $50m) **989** → EMA filter off **989** → market regime on **866** → next session exists **866**

**Setup B (ema)**: reports in period **18,616** → price data at entry **18,463** → liquid (price > $10, ADV > $50m) **16,994** → above rising 50 EMA **9,902** → market regime on **9,109**

**Setup B (noema)**: reports in period **18,616** → price data at entry **18,463** → liquid (price > $10, ADV > $50m) **16,994** → EMA filter off **16,994** → market regime on **14,342**

## 6. Why portfolio signals were skipped

- **A ema+fixed**: max 5 open positions (269), limit not reached (32), max 2 positions in Industrials (26), max 2 positions in Information Technology (14), max 2 positions in Consumer Discretionary (11), max 2 positions in Financials (9), max 2 positions in Health Care (4), daily loss limit (2%) hit (3), position too small (< 1 share; limited by max position) (2), max 2 positions in Materials (1), max 2 positions in Consumer Staples (1)
- **A noema+fixed**: max 5 open positions (287), limit not reached (32), max 2 positions in Industrials (26), max 2 positions in Information Technology (14), max 2 positions in Consumer Discretionary (11), max 2 positions in Financials (9), max 2 positions in Health Care (4), max 2 positions in Consumer Staples (3), position too small (< 1 share; limited by max position) (2), max 2 positions in Materials (1)
- **A ema+trail**: max 5 open positions (266), limit not reached (33), max 2 positions in Industrials (25), max 2 positions in Information Technology (19), max 2 positions in Financials (9), max 2 positions in Consumer Discretionary (5), max 2 positions in Health Care (4), position too small (< 1 share; limited by max position) (2), max 2 positions in Consumer Staples (2)
- **A noema+trail**: max 5 open positions (279), limit not reached (34), max 2 positions in Industrials (25), max 2 positions in Information Technology (19), max 2 positions in Financials (9), max 2 positions in Health Care (6), max 2 positions in Consumer Discretionary (5), max 2 positions in Consumer Staples (3), position too small (< 1 share; limited by max position) (2)
- **B ema**: max 5 open positions (7381), max 2 positions in Information Technology (111), max 2 positions in Financials (105), max 2 positions in Consumer Discretionary (15), daily loss limit (2%) hit (10), max 2 positions in Health Care (9), max 2 positions in Consumer Staples (9), position too small (< 1 share; limited by max position) (6), max 2 positions in Communication Services (5), max 2 positions in Industrials (5), max 2 positions in Energy (2), max 2 positions in Utilities (2)
- **B noema**: max 5 open positions (12289), max 2 positions in Information Technology (155), max 2 positions in Financials (126), daily loss limit (2%) hit (57), max 2 positions in Consumer Discretionary (22), max 2 positions in Consumer Staples (11), max 2 positions in Health Care (10), max 2 positions in Industrials (8), position too small (< 1 share; limited by max position) (5), max 2 positions in Communication Services (4), max 2 positions in Utilities (4), max 2 positions in Energy (1)
