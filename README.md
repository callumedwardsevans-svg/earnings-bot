# Earnings Bot

A rules-based **earnings-play** strategy for US stocks, backtested on daily data and then run on an **Alpaca paper account** (~$10k). The goal is to find out, honestly, whether post-earnings drift or pre-earnings run-up setups make money after costs before any real money is involved.

> **Paper trading only.** The code refuses to start against Alpaca's live endpoint (see [Safety](#safety)).

## Status

| Milestone | State |
|---|---|
| 1. Setup: repo, environment, Alpaca paper connection, live-endpoint guard | done |
| 2. Data: price + earnings fetchers with caching, NVDA sanity report | done |
| 3. Backtest: setups A and B with variants vs SPY | not started |
| 4. Paper loop: plan → submit → reconcile, journal, daily report | not started |
| 5. Review after 6–8 weeks of paper trading | not started |

## Strategy (hypotheses to test, not proven rules)

- **Setup A, post-earnings drift:** after a strong EPS beat with a gap up on heavy volume, buy the next session and hold up to 20 days with a stop and a +3R target.
- **Setup B, pre-earnings run-up:** buy 7 trading days before a confirmed report when the stock is in an uptrend; always flat before the report.

All parameters live in [`src/earnings_bot/config.py`](src/earnings_bot/config.py).

## Data

| What | Source | Why | Cache |
|---|---|---|---|
| Daily bars | Alpaca, **SIP** feed, split + dividend adjusted, 2016 onwards | The free plan allows historical consolidated bars. IEX-only volume is ~3% of consolidated, which would break the volume filters. | `data/prices/<SYM>.parquet` |
| Earnings history (backtest, primary) | Yahoo Finance via `yfinance` | ~100 quarters per symbol with EPS estimate/actual and the announcement **timestamp**, so before/after-close timing comes from a time of day, not a label. No daily cap. Unofficial and can break or throttle; research use only, never committed, and the live loop doesn't depend on it. | `data/raw/yahoo/` |
| Earnings history (cross-check) | Alpha Vantage `EARNINGS` | Independent second source for dates and timing. Free key is 25 requests/day, so it fills in over ~20 days via the daily task; raw JSON cached forever with a local budget. | `data/raw/alphavantage/` |
| Combined history | Yahoo + AV, reconciled | See [`history.py`](src/earnings_bot/data/history.py): timing used where the sources agree or only one knows; bmo-vs-amc **conflicts are skipped and counted**. | `data/earnings/history.parquet` |
| Earnings calendar (live) | Finnhub `calendar/earnings` | Forward dates, bmo/amc, EPS **and revenue** estimates/actuals. Free tier only looks back ~1 month and caps a response at 1,500 rows, so it's fetched day by day. | `data/raw/finnhub/` |
| Universe + sectors | Wikipedia S&P 500 list (+ historical changes page) | Today's constituents and GICS sectors (for the 2-per-sector limit). | `data/universe/` |
| Trading calendar | Alpaca market calendar | Holidays and half days for the day-1 rule. | `data/calendar/` |

**Day 1 rule:** before-open report → same session; after-close → next session; weekend/holiday dates roll forward; during-market or unknown timing → flagged, never guessed. Tested in [`tests/test_timing.py`](tests/test_timing.py).

**Known data issues**

- *Alpha Vantage timing labels are wrong on older rows.* NVDA always reports after the close, but every report before Nov 2014 is labelled "pre-market" (apparently a default). That's why Yahoo's timestamps are primary and AV is the cross-check.
- *A volume-spike timing check is too noisy to filter on.* [`quality.py`](src/earnings_bot/data/quality.py) compares each label with the day the volume spike landed. On 29 reports it flagged, Yahoo and AV agreed with each other 26 times, so the check stays a diagnostic. It's also never used to pick day 1, because that would use the outcome to choose the entry.
- *Finnhub often has no timing for upcoming reports* (~70% of next-3-weeks rows are blank, including large caps such as WMT and TGT). The live loop has to handle this; see milestone 4.
- *Survivorship bias:* the universe is today's S&P 500. 109 names were removed from the index between Jan 2021 and Nov 2026 (~22% of it), and the backtest can't see any of them. Removed names skew towards decliners and acquired companies, so results on today's list are likely flattered; treat any edge as an upper bound.
- *No revenue history:* the "revenue also beat" condition can only be applied in the live loop (Finnhub), not in the backtest.

Sanity check: [`docs/sanity/NVDA.md`](docs/sanity/NVDA.md). The volume spike lands on the computed day 1 for 8 of 8 recent reports.

## Setup

### Conda (local development)

```bash
conda create -n earnings-bot python=3.12 pip -y
conda activate earnings-bot
pip install -r requirements.txt
```

### Plain pip (GitHub Actions, any machine without conda)

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` pins the direct dependencies and installs the package itself (`-e .`). Keep it in step with the conda env whenever a dependency is added.

### Keys

```bash
cp .env.example .env
```

Fill in your Alpaca **paper** API key and secret. `.env` is gitignored and the keys are never printed or logged.

## Scheduled data refresh (Windows)

The Alpha Vantage earnings backfill takes ~20 days at 25 symbols/day. A daily task at 06:00 UK refreshes prices and spends that day's budget; output goes to `logs/` (gitignored, keys never logged).

```bash
powershell -ExecutionPolicy Bypass -File scripts/windows/register_daily_task.ps1
```

## Usage

```bash
python scripts/check_account.py   # connect to paper account, print equity and risk limits
python scripts/update_data.py --earnings-backfill   # refresh prices/universe, spend today's AV budget
python scripts/sanity_report.py NVDA               # last 8 reports with timing + day-1 reaction
python -m pytest                  # run the tests
```

## Safety

- **Paper-only guard** ([`broker.py`](src/earnings_bot/broker.py)): only `https://paper-api.alpaca.markets` is accepted. The live endpoint needs `ALLOW_LIVE=true` *and* a typed confirmation at an interactive terminal, so scheduled or CI runs can never trade live. Any other URL is refused. Covered by [`tests/test_broker_guard.py`](tests/test_broker_guard.py).
- **Risk limits** checked before every order: 0.75% equity risk per trade, 15% max position, max 5 open positions (2 per sector), 2% daily loss limit.
- **Kill switch:** create a file named `STOP` in the project root and the bot places no orders.
- **Secrets:** `.env` is gitignored, the repo is scanned with gitleaks in CI, and GitHub secret-scanning push protection is enabled.

## Layout

```
src/earnings_bot/
  config.py      risk limits, strategy parameters, settings from .env
  broker.py      Alpaca client factory + paper-only guard
  data/          prices, earnings, universe, calendar, timing quality checks
  signals/       setup A, setup B                             (milestone 3)
  backtest/      engine + metrics                             (milestone 3)
scripts/         command-line entry points
docs/sanity/     committed data sanity reports
tests/           pytest suite
data/ plans/ journal/ reports/   runtime output (gitignored)
```

## Not in scope

Live-money trading, options, leverage, short selling, and machine-learning models.
