# Earnings Bot

A rules-based **earnings-play** strategy for US stocks, backtested on daily data and then run on an **Alpaca paper account** (~$10k). The goal is to find out, honestly, whether post-earnings drift or pre-earnings run-up setups make money after costs before any real money is involved.

> **Paper trading only.** The code refuses to start against Alpaca's live endpoint (see [Safety](#safety)).

## Status

| Milestone | State |
|---|---|
| 1. Setup: repo, environment, Alpaca paper connection, live-endpoint guard | done |
| 2. Data: price + earnings fetchers with caching | not started |
| 3. Backtest: setups A and B with variants vs SPY | not started |
| 4. Paper loop: plan → submit → reconcile, journal, daily report | not started |
| 5. Review after 6–8 weeks of paper trading | not started |

## Strategy (hypotheses to test, not proven rules)

- **Setup A, post-earnings drift:** after a strong EPS beat with a gap up on heavy volume, buy the next session and hold up to 20 days with a stop and a +3R target.
- **Setup B, pre-earnings run-up:** buy 7 trading days before a confirmed report when the stock is in an uptrend; always flat before the report.

All parameters live in [`src/earnings_bot/config.py`](src/earnings_bot/config.py).

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

## Usage

```bash
python scripts/check_account.py   # connect to paper account, print equity and risk limits
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
  data/          price + earnings fetchers with caching       (milestone 2)
  signals/       setup A, setup B                             (milestone 3)
  backtest/      engine + metrics                             (milestone 3)
scripts/         command-line entry points
tests/           pytest suite
data/ plans/ journal/ reports/   runtime output (gitignored)
```

## Not in scope

Live-money trading, options, leverage, short selling, and machine-learning models.
