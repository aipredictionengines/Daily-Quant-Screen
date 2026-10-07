# Daily Quant Screen v0.1

Paper-only **Multi-Asset Daily Forecast Intelligence** foundation. BUILD-001 implements BTC first.

## What this build does

Each eligible morning it:

1. Discovers the day's BTC `price range` and `hit price` market structure from Polymarket Gamma.
2. Pulls ~30 days of Binance BTCUSDT 15-minute OHLCV.
3. Uses Gemini + Google Search for same-day event/news risk only (not price prediction).
4. Runs a deterministic empirical bootstrap model.
5. Locks the Quant forecast to immutable JSON + SHA-256.
6. **After the lock**, reads Polymarket CLOB midpoint probabilities as the benchmark.
7. Later resolves the official configured price from a Binance 1-minute candle and scores the paper forecast.

This separation is intentional: Polymarket probabilities cannot leak into the Quant forecast.

## First run

Python 3.11+.

```bash
cd daily-quant-screen
cp .env.example .env
# export GEMINI_API_KEY=...  # optional but recommended for full context layer
python -m pytest -q
python -m dqs.cli --root . morning --date 2026-10-07
python -m dqs.cli --root . render --date 2026-10-07
```

After the market's configured range resolution time:

```bash
python -m dqs.cli --root . resolve --date 2026-10-07
python -m dqs.cli --root . scoreboard
```

Artifacts appear under:

```text
artifacts/paper/YYYY-MM-DD/BTC/
  forecast.json
  benchmark.json
  resolution.json
  score.json
  screen.html
```

## Current model

`empirical_15m_bootstrap_v0.1`

Instead of asking an LLM for a price, the model resamples historical 15-minute candle shapes, volatility-scales them to the current regime, simulates thousands of paths, then computes:

- probability for each Polymarket range bracket;
- terminal-price quantiles;
- expected path low/high quantiles;
- probability of reaching discovered hit-price barriers;
- a heuristic confidence score.

Gemini is a **Context Analyst**, not the numerical forecaster.

## Important limitations

- This is a PAPER research instrument, not a promise of predictive accuracy.
- The bootstrap model is intentionally simple so PAPER 20 can tell us whether there is signal before adding complexity.
- Hit-price scoring is not yet persisted in `score.json`; v0.1 forecasts hit probabilities but the first gate focuses on the daily range.
- The exact resolution rule must remain market-specific. The configuration currently uses a BTC range close at `12:00 America/New_York`; verify the day's actual Polymarket rules before treating it as the authoritative scoring rule.
- Network calls cannot be integration-tested in this package's offline build environment; unit tests cover parsing, determinism, integrity, and scoring.

## Public API references used by the implementation

- Polymarket market discovery: https://docs.polymarket.com/market-data/discover-markets
- Polymarket prices/order books: https://docs.polymarket.com/market-data/prices-order-books
- Binance public Spot market data / klines: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- Gemini Google Search grounding: https://ai.google.dev/gemini-api/docs/google-search/
- Gemini structured outputs / Interactions API: https://ai.google.dev/gemini-api/docs/structured-output

## QA / Bug Gate

Before PAPER 20 starts, inspect the machine-readable bug log and readiness state:

```bash
python -m dqs.cli --root . buglog
python -m dqs.cli --root . readiness
```

The current build is intentionally `BLOCKED` until LIVE-DATA-001, market-rule verification and DST/timestamp checks close the P1 blockers. See `docs/BUG-LOG.md`, `docs/TEST-READINESS.md` and `qa/bug-log.json`.

## PAPER 20 rule

See `docs/PAPER-20.md`. A run does not count toward PAPER 20 unless the readiness gate was `READY_FOR_PAPER` before the morning lock.


## Candidate lifecycle

Before official PAPER 20, use the manual GitHub Actions workflow **DQS BTC Candidate**.

- `action=lock` must be run during **05:00–08:00 Europe/Sofia** on an eligible day.
- Thursday is rejected by the workflow/protocol.
- The lock runs LIVE-DATA health first, then stores a non-counting candidate under `artifacts/candidates/YYYY-MM-DD/BTC/`.
- After the market resolution time, run the same workflow with `action=resolve`.
- Candidate artifacts never increment the official PAPER 20 scoreboard.

Current QA state: **CANDIDATE_READY**. Official PAPER remains **0/20** until a clean candidate lifecycle is reviewed.

Gemini is currently optional for candidate readiness. To turn the context layer from VERIFY to PASS, add `GEMINI_API_KEY` as a GitHub Actions repository secret. The numerical forecast and FOMC hard gate do not depend on Gemini.
