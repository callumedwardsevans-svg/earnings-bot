# Paper-trading runbook (milestone 4)

Strategy: **Setup A, 50-EMA filter, fixed exit**, no regime filter, as pre-registered in
[backtest/PREREGISTRATION.md](backtest/PREREGISTRATION.md). Paper account only.

## Where it runs: GitHub Actions (since 2026-11-18)

The scheduled runs moved from Windows Task Scheduler to GitHub Actions
([`.github/workflows/paper-trading.yml`](../.github/workflows/paper-trading.yml)): same scripts, same
trading logic, nothing depends on your PC being on. The local tasks were removed.

| UTC (weekdays) | New York (winter / summer) | Job |
|---|---|---|
| 12:05 | 07:05 / 08:05 | **morning**: `submit_orders.py --send` (A), then `e_live.py morning --send` (E) |
| 19:20 | 14:20 / 15:20, E waits to 15:35 | **close**: `e_live.py close --send` (E; only acts on turn-of-month entry/exit days) |
| 22:15 | 17:15 / 18:15 | **evening**: `evening.py --send` (A), then `e_live.py evening --send` (E) |
| 05:30 | 00:30 / 01:30 | **data**: `update_data.py` refresh and research backfill |

- **State** (journal, plans, reports, order log) lives on the public
  [`bot-state`](https://github.com/callumedwardsevans-svg/earnings-bot/tree/bot-state) branch; each run
  restores it first and commits it back afterwards. To read it locally:
  `git fetch origin bot-state` then `git checkout origin/bot-state -- journal plans reports`.
  The local `journal/`, `plans/` and `reports/` folders are no longer updated.
- **Market data** (prices, calendar, earnings caches, consensus log) stays out of the public branch: it's
  in a private Actions cache, and the consensus log is also kept as a 90-day private artifact.
- **Keys** are repository secrets (Settings → Secrets and variables → Actions), masked in the public logs.
  The workflow only runs on its schedule or a manual trigger, never on pull requests.
- **Manual runs / dry runs:** Actions tab → Paper trading → Run workflow (choose the job; "send"
  unticked = dry run), or `gh workflow run "Paper trading" -f job=evening -f send=false`.
- **Kill switch on Actions:** a `STOP` file only works where the scripts run. To stop orders, disable the
  workflow (`gh workflow disable "Paper trading"`, or the Actions tab), and re-enable it to resume.
- **Timing caveat:** GitHub can start scheduled runs 5-30 minutes late (rarely, skip one). The schedules
  leave room for that; a run that starts too late refuses to send, exactly as before, and the run is
  marked failed so it shows in the Actions tab and GitHub's failure email.

The Windows scripts in `scripts/windows/` are kept as an offline fallback but aren't registered.

## Daily cycle (what each job does)

| UK time | New York time | Task | What it does |
|---|---|---|---|
| 13:25 | 08:25 (09:25 in clock-change weeks) | `submit_orders.py` | Kill switch → account check → scheduled exits (cancel bracket legs, market-on-open sell) → daily-loss check → re-size each planned entry on live equity/cash, re-check limits → GTC bracket orders |
| 22:00 | 17:00 (18:00) | `evening.py` | Reconcile fills (cancel unfilled entries) → update journal → refresh prices + Finnhub/Yahoo earnings → plan tomorrow's entries/exits → write `reports/YYYY-MM-DD.md` |

Both scripts check New York time and the trading calendar themselves. The morning script refuses to
send anything at or after 09:28 NY, so a run delayed by sleep or a reboot can't send orders into a
live market.

## Safety

- **Paper-only guard** before any client is created (see `broker.py`).
- **Kill switch:** create a file named `STOP` in the project root. Nothing is sent and the reason is
  logged. Delete the file to resume. Existing stop/target orders stay at the broker.
- **Every position has its exits at the broker**: entries are bracket orders with GTC stop-loss and
  take-profit legs, so they keep working if the PC is off. The evening reconcile warns if any open
  position has no working stop.
- **No duplicates:** each order's `client_order_id` is the trade id (`A-YYYYMMDD-TICKER`); re-running
  the morning step can't double-submit.
- **No leverage:** sizing uses `min(cash, equity)`, never margin buying power.
- **Logged with a reason:** every order sent, every signal skipped (`plans/*.json`, `logs/orders.jsonl`,
  and the daily report).

## Files (all gitignored, kept locally)

| Path | Contents |
|---|---|
| `plans/YYYY-MM-DD.json` | Plan for that session: entries, exits, skipped signals with reasons, funnel, and the morning's `submission` results |
| `journal/state.json` | Source of truth for every trade the bot sent (submitted → open → closed / cancelled) |
| `journal/trades.csv` | One row per entered trade, with exactly the brief's columns (open trades have blank exit fields) |
| `reports/YYYY-MM-DD.md` | Daily report: open positions and unrealised P&L, trades opened/closed, skipped signals, running stats vs SPY, problems |
| `logs/orders.jsonl`, `logs/live_YYYY-MM.log` | Event log and raw run output |

## Differences from the backtest (by design)

- **Scheduled exits happen at the open, not the close.** The time exit and flat-before-report exit
  are market-on-open sells on the day they fall due. In the 2016-2025 backtest this costs about
  0.01R per trade (0.185R vs 0.197R) and avoids a third, timing-sensitive scheduled task.
- **The next report date comes from Finnhub's forward calendar**, which can change. The backtest knew
  the actual date.
- **Timing comes from Finnhub's `hour` cross-checked with Yahoo's timestamp**, using the same
  reconciliation rule as the backtest history. Reports where they conflict, or where both are unknown,
  are skipped and logged.
- **Revenue surprise is recorded in the notes but not used**, since the backtest couldn't test it.
- **Partial fills:** the filled part is kept, and the rest is cancelled in the evening.

A replay of the planner on six busy signal days from the held-out year gave the same stocks and the
same limit/stop/target prices (to the cent) as the backtest. Every difference was a portfolio-limit
skip applied in the same priority order.

## Going from dry run to live paper orders

1. Run in dry-run mode for a few days and read the reports. Check that the plans make sense and
   `logs/live_*.log` shows no errors.
2. Re-register the tasks with `-Send`:
   `powershell -ExecutionPolicy Bypass -File scripts/windows/register_paper_tasks.ps1 -Send`
3. The first `--send` evening run records the starting equity and SPY close for the "since start"
   comparison.

## Review (milestone 5)

After 6-8 weeks and at least 30 closed trades: compare live R per trade, fill rate and exit-reason
mix with the backtest, and the return with SPY over the same dates. Expect a small sample: the
backtest averaged ~50 portfolio trades a year.

---

# Setup E (SPY combined) paper loop

Rules: month-end 200-day SMA trend x vol target min(1, 0.12/sigma20), plus the turn-of-month
window (-2..+3) at 1.0x. The only setup that passed the research addendum's drop rules
([results](research/ADDENDUM_RESULTS.md)). Code: `live/setup_e_live.py`, `scripts/e_live.py`.

## Separate paper account (recommended)

E holds up to 100% of its account in SPY; Setup A can use up to ~75% of its account. Sharing one
$10k account would make them compete for cash and mix up the results. Create a second Alpaca paper
account and put its keys in `.env` as `ALPACA_E_KEY_ID` / `ALPACA_E_SECRET_KEY`. Without them, E
runs only as a dry run with a virtual $10k book.

**Exception to the brief's 15% max-position rule:** E is an index-allocation strategy defined to hold
up to 1.0x, so in its own account it's capped at 100% exposure (no leverage), not 15%. The paper-only
guard, the kill switch and a daily loss rule (down 2% on the day: only exposure-reducing orders)
still apply. It sends nothing until you register the tasks with `-Send`. **Approved by the project
owner on 2026-11-16**, for Setup E in its own paper account only; every other setup keeps the 15% cap.

## Daily cycle

| UK time | New York | Job | What it does |
|---|---|---|---|
| 13:27 | 08:27 / 09:27 | `e_live.py morning` | Exposure for today = 1.0 on a TOM full day, else yesterday's base target -> market-on-open order for the change in whole shares |
| 19:35 | waits to 15:35 | `e_live.py close` | Only on TOM entry (day -2) and exit (day +3) days: market-on-close order |
| 22:05 | after the close | `e_live.py evening` | Settle fills (or virtual fills), journal, backtest shadow, report |

Files: `plans/setup_e/`, `reports/setup_e/`, `journal/setup_e_daily_{dry,live}.csv` (daily position,
equity, SPY, and a **backtest shadow**: the same rules run on the same prices from the start date,
so live-vs-backtest differences show up every day), `logs/setup_e_YYYY-MM.log`.

## Differences from the backtest

- **Whole shares:** with SPY around $760, one share is ~7.5% of a $10k account, so exposure moves in steps.
- **Cash earns 0%** on paper (the backtest used T-bills).
- Combined effect, re-run on the backtest: since 2016, 9.8% a year vs 10.4%, with the same Sharpe
  (0.87); since 2023, 11.3% vs 12.2%.
- A unit test checks that the live morning/close targets equal the backtest's positions day by day.

Register (dry run first):

    powershell -ExecutionPolicy Bypass -File scripts/windows/register_setup_e_tasks.ps1
