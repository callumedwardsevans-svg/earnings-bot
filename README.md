# bot-state

Written by the `Paper trading` GitHub Actions workflow after every run; not code. It holds the
live paper-trading state for this project:

- `journal/`: `state.json` (every trade the bot sent: status, prices, order ids), `trades.csv` (the
  trade journal), Setup E's state and daily log (`setup_e_*`), compared with a backtest shadow.
- `plans/`: the evening plan for each session (entries, exits, skipped signals with reasons) and Setup E's daily targets.
- `reports/`: daily Markdown reports.
- `logs/orders.jsonl`: every order sent or signal skipped, with the reason.

Paper (simulated) money only. No API keys or account numbers are stored here; raw market data
from Alpaca/Finnhub/Yahoo is kept out of this public branch.
