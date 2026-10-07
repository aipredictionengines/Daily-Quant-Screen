# BUILD-001 — BTC Daily Quant Screen v0.1

## Goal

Build one end-to-end paper system before adding ETH/SOL/XRP, equities, metals, or energy.

`Polymarket structure → Binance data → Gemini context → Quant model → immutable lock → Polymarket benchmark → Binance resolution → score`

## Implemented in v0.1

- Binance public 15-minute OHLCV adapter with pagination.
- Polymarket Gamma daily BTC range/hit market discovery.
- Polymarket CLOB midpoint benchmark.
- Gemini Interactions API adapter using Google Search + structured JSON.
- 15-minute empirical bootstrap forecast model.
- Range probabilities, path high/low estimates and hit-level probabilities.
- Thursday + official-FOMC-day gates.
- Immutable SHA-256 paper snapshots.
- Binance 1-minute range-resolution fetch.
- Exact range, Top-2 and Brier scoring.
- Static HTML screen renderer.

## Deliberately not in v0.1

- Money execution / wallet / order placement.
- ETH/SOL/XRP adapters.
- Massive/CME adapters.
- Learned ML model or neural net.
- Automatic strategy optimization after every miss.

Those wait until PAPER 20 gives evidence that the base signal is useful.

## QA observability added

- `qa/bug-log.json` — machine-readable source of truth for defects and blockers.
- `docs/BUG-LOG.md` — human-readable bug register.
- `docs/TEST-READINESS.md` — hard gate for moving from BUILD/DRY_RUN to PAPER 20.
- `python -m dqs.cli --root . buglog` — current bug inventory.
- `python -m dqs.cli --root . readiness` — current release state and blocker list.
- `.github/ISSUE_TEMPLATE/bug_report.yml` — standard bug report when the public GitHub repository is active.
