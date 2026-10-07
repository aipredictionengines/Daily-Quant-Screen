# BTC DAILY RANGE — PAPER 20

## Gate

Count only eligible immutable forecasts.

- Thursday: `SKIP`.
- Official scheduled FOMC meeting day: `SKIP`.
- A Fed speech, FOMC minutes release, or other Fed publication is **not** automatically a meeting-day skip.
- No live trading is part of BUILD-001.

## Anti-leakage rule

1. Discover Polymarket **market structure** (questions/ranges/token IDs).
2. Read Binance history and Gemini context.
3. Generate Quant forecast.
4. Write `forecast.json` immutably and compute SHA-256.
5. Only then read Polymarket CLOB midpoints and write `benchmark.json`.

The market benchmark can therefore be compared with the model without contaminating the forecast.

## Required artifacts per day

- `forecast.json`
- `benchmark.json`
- `resolution.json`
- `score.json`
- optional `screen.html`

## PAPER 20 scoreboard

Primary metrics:

- Exact primary range hit rate.
- Top-2 range hit rate.
- Multi-class Brier score over discovered brackets.
- Calibration by confidence bucket.
- Quant vs Polymarket probability benchmark.

Secondary metrics for later revisions:

- Hit-price Brier score.
- Intraday high/low interval coverage.
- Accuracy by weekday and volatility regime.
- Whether Gemini context improves out-of-sample performance.
