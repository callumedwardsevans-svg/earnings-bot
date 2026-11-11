# Backtest results: in-sample (2016-04-01 to 2025-11-10)

Starting equity $10,000; risk 0.75%/trade, max 15% per position, max 5 positions (2 per sector), 2% daily loss limit; whole shares; 5 bps slippage per fill; $0 commission.

## 1. Signal level (every filled signal, no portfolio limits)

This is the cleanest test of whether the setup has an edge, because it isn't affected by account size or which signals happened to overlap. `se` = standard error of the mean R; an expectancy within about 2 se of zero isn't distinguishable from no edge.

| setup   | variant     |   signals | fill rate   |   trades | win rate   |   avg win R |   avg loss R |   expectancy R |    se |   t-stat |
|:--------|:------------|----------:|:------------|---------:|:-----------|------------:|-------------:|---------------:|------:|---------:|
| A       | ema+fixed   |       931 | 94%         |      873 | 41%        |        1.59 |        -0.79 |          0.197 | 0.046 |     4.25 |
| A       | noema+fixed |       989 | 94%         |      926 | 40%        |        1.6  |        -0.79 |          0.175 | 0.045 |     3.9  |
| A       | ema+trail   |       931 | 94%         |      873 | 45%        |        1.24 |        -0.76 |          0.137 | 0.044 |     3.11 |
| A       | noema+trail |       989 | 94%         |      926 | 44%        |        1.24 |        -0.76 |          0.115 | 0.042 |     2.72 |
| B       | ema         |      9902 | 100%        |     9902 | 49%        |        0.86 |        -0.82 |         -0.001 | 0.01  |    -0.05 |
| B       | noema       |     16994 | 100%        |    16994 | 51%        |        0.88 |        -0.8  |          0.047 | 0.008 |     6.02 |

## 2. Portfolio ($10k account, all limits applied) vs SPY

| setup   | variant     |   trades | win rate   |   avg win R |   avg loss R |   expectancy R | total return   | CAGR   | max DD   |   Sharpe | exposure (time)   | avg capital deployed   |
|:--------|:------------|---------:|:-----------|------------:|-------------:|---------------:|:---------------|:-------|:---------|---------:|:------------------|:-----------------------|
| A       | ema+fixed   |      506 | 41%        |        1.57 |        -0.79 |          0.163 | +59.1%         | +4.9%  | -12.0%   |     0.72 | 80%               | 31%                    |
| A       | noema+fixed |      527 | 39%        |        1.56 |        -0.79 |          0.127 | +46.8%         | +4.1%  | -12.8%   |     0.59 | 80%               | 31%                    |
| A       | ema+trail   |      515 | 46%        |        1.28 |        -0.77 |          0.166 | +64.9%         | +5.3%  | -13.0%   |     0.81 | 77%               | 28%                    |
| A       | noema+trail |      539 | 44%        |        1.26 |        -0.76 |          0.138 | +56.6%         | +4.8%  | -11.1%   |     0.72 | 78%               | 29%                    |
| B       | ema         |     1601 | 48%        |        0.94 |        -0.81 |          0.024 | +25.6%         | +2.4%  | -15.4%   |     0.31 | 89%               | 47%                    |
| B       | noema       |     1897 | 50%        |        0.94 |        -0.81 |          0.058 | +92.5%         | +7.1%  | -23.1%   |     0.67 | 97%               | 55%                    |

**SPY buy & hold:** total return +283.7%, CAGR +15.0%, max DD -33.8%, Sharpe 0.88, exposure 100%.

![Setup A](equity_setup_A.png)

![Setup B](equity_setup_B.png)

## 3. Robustness: only signals after the stock joined the S&P 500

Partly addresses survivorship bias: drops signals from before a stock was in the index (using today's list's 'date added'). It can't add back the ~22% of names that left the index.

| setup   | variant     |   trades |   expectancy R | total return   | max DD   |   Sharpe |
|:--------|:------------|---------:|---------------:|:---------------|:---------|---------:|
| A       | ema+fixed   |      432 |          0.142 | +38.0%         | -9.3%    |     0.59 |
| A       | noema+fixed |      448 |          0.119 | +31.7%         | -10.8%   |     0.49 |
| A       | ema+trail   |      443 |          0.111 | +28.8%         | -8.6%    |     0.48 |
| A       | noema+trail |      458 |          0.097 | +27.5%         | -10.1%   |     0.45 |
| B       | ema         |     1537 |          0.017 | +15.1%         | -14.7%   |     0.22 |
| B       | noema       |     1841 |          0.048 | +66.2%         | -24.3%   |     0.56 |

## 4. Expectancy by year (signal level, R per trade; trade count in brackets)

|      | A ema+fixed   | A noema+fixed   | A ema+trail   | A noema+trail   | B ema        | B noema      |
|-----:|:--------------|:----------------|:--------------|:----------------|:-------------|:-------------|
| 2016 | +0.35 (46)    | +0.27 (49)      | +0.30 (46)    | +0.23 (49)      | -0.01 (671)  | +0.04 (1031) |
| 2017 | +0.26 (80)    | +0.25 (81)      | +0.12 (80)    | +0.10 (81)      | +0.20 (1069) | +0.21 (1456) |
| 2018 | +0.24 (86)    | +0.22 (90)      | +0.17 (86)    | +0.16 (90)      | -0.09 (812)  | -0.09 (1624) |
| 2019 | +0.24 (96)    | +0.22 (99)      | +0.24 (96)    | +0.22 (99)      | +0.01 (1111) | +0.09 (1687) |
| 2020 | +0.18 (73)    | +0.19 (77)      | -0.06 (73)    | -0.06 (77)      | -0.00 (1108) | +0.05 (1746) |
| 2021 | +0.18 (59)    | +0.12 (64)      | +0.12 (59)    | +0.07 (64)      | +0.03 (1252) | +0.09 (1847) |
| 2022 | -0.11 (66)    | -0.18 (85)      | -0.08 (66)    | -0.14 (85)      | -0.16 (677)  | +0.03 (1878) |
| 2023 | +0.24 (113)   | +0.28 (120)     | +0.27 (113)   | +0.27 (120)     | -0.07 (1059) | -0.07 (1877) |
| 2024 | +0.24 (133)   | +0.25 (135)     | +0.15 (133)   | +0.15 (135)     | +0.06 (1215) | +0.10 (1942) |
| 2025 | +0.13 (121)   | +0.10 (126)     | +0.09 (121)   | +0.08 (126)     | -0.08 (928)  | +0.04 (1906) |

## 5. Signal funnel (how many reports survive each filter)

**Setup A (ema+fixed)**: reports in period **18,606** → timing known (bmo/amc) **18,396** → price data on day 1 **18,276** → EPS surprise >= 5% **9,124** → gap >= 3% **2,642** → close in upper half **1,324** → volume >= 2x avg **1,074** → liquid (price > $10, ADV > $50m) **989** → above 50 EMA **931** → next session exists **931**

**Setup A (noema+fixed)**: reports in period **18,606** → timing known (bmo/amc) **18,396** → price data on day 1 **18,276** → EPS surprise >= 5% **9,124** → gap >= 3% **2,642** → close in upper half **1,324** → volume >= 2x avg **1,074** → liquid (price > $10, ADV > $50m) **989** → EMA filter off **989** → next session exists **989**

**Setup B (ema)**: reports in period **18,616** → price data at entry **18,463** → liquid (price > $10, ADV > $50m) **16,994** → above rising 50 EMA **9,902**

**Setup B (noema)**: reports in period **18,616** → price data at entry **18,463** → liquid (price > $10, ADV > $50m) **16,994** → EMA filter off **16,994**

## 6. Why portfolio signals were skipped

- **A ema+fixed**: max 5 open positions (319), limit not reached (33), max 2 positions in Industrials (26), max 2 positions in Information Technology (17), max 2 positions in Consumer Discretionary (11), max 2 positions in Financials (9), max 2 positions in Health Care (5), position too small (< 1 share; limited by max position) (2), max 2 positions in Consumer Staples (2), max 2 positions in Materials (1)
- **A noema+fixed**: max 5 open positions (351), limit not reached (35), max 2 positions in Industrials (26), max 2 positions in Information Technology (19), max 2 positions in Consumer Discretionary (11), max 2 positions in Financials (9), max 2 positions in Health Care (4), max 2 positions in Consumer Staples (3), position too small (< 1 share; limited by max position) (2), max 2 positions in Materials (1), daily loss limit (2%) hit (1)
- **A ema+trail**: max 5 open positions (312), limit not reached (37), max 2 positions in Industrials (25), max 2 positions in Information Technology (20), max 2 positions in Financials (9), max 2 positions in Consumer Discretionary (5), max 2 positions in Health Care (4), position too small (< 1 share; limited by max position) (2), max 2 positions in Consumer Staples (2)
- **A noema+trail**: max 5 open positions (340), limit not reached (37), max 2 positions in Industrials (25), max 2 positions in Information Technology (22), max 2 positions in Financials (9), max 2 positions in Health Care (6), max 2 positions in Consumer Discretionary (5), max 2 positions in Consumer Staples (3), position too small (< 1 share; limited by max position) (2), daily loss limit (2%) hit (1)
- **B ema**: max 5 open positions (7973), max 2 positions in Information Technology (118), max 2 positions in Financials (110), daily loss limit (2%) hit (33), max 2 positions in Health Care (19), max 2 positions in Consumer Discretionary (16), max 2 positions in Consumer Staples (10), position too small (< 1 share; limited by max position) (6), max 2 positions in Communication Services (5), max 2 positions in Industrials (5), max 2 positions in Utilities (4), max 2 positions in Energy (2)
- **B noema**: max 5 open positions (14533), max 2 positions in Information Technology (191), daily loss limit (2%) hit (158), max 2 positions in Financials (143), max 2 positions in Consumer Discretionary (28), max 2 positions in Consumer Staples (13), max 2 positions in Health Care (11), max 2 positions in Industrials (8), position too small (< 1 share; limited by max position) (6), max 2 positions in Communication Services (4), max 2 positions in Energy (1), max 2 positions in Utilities (1)
