# TEST READINESS GATE — BTC DAILY RANGE PAPER 20

The system has three release states:

- `BLOCKED` — do not count forecasts toward PAPER 20.
- `DRY_RUN` — live data may be observed, but results do not count toward PAPER 20.
- `READY_FOR_PAPER` — immutable forecasts may start counting toward PAPER 20.

## Hard gate for READY_FOR_PAPER

All of the following must be true:

1. **Bug gate:** zero open `P0` and zero open `P1` bugs; no open bug with `blocks_paper_test=true`.
2. **Unit tests:** full test suite passes.
3. **Live API health:** Binance klines, Polymarket Gamma market discovery and Polymarket CLOB benchmark each return valid live data in recorded health runs.
4. **Anti-leakage:** a test proves that Polymarket probabilities are not fetched before `forecast.json` is immutably written.
5. **Immutable storage:** overwrite of an existing forecast is rejected.
6. **Rules verification:** source, trading pair, resolution candle/timezone and price-boundary convention are captured from/checked against the actual market rules before scoring.
7. **Timezone/DST:** exact timestamp tests pass for normal dates and the US/EU DST mismatch windows.
8. **Resolution:** the expected Binance 1-minute candle is fetched by exact timestamp and a known historical replay resolves correctly.
9. **Failure behavior:** missing Gemini/news context does not silently become `PASS`; it is recorded as `VERIFY/UNKNOWN` and does not alter historical numeric inputs.
10. **Observability:** the daily run exposes forecast hash, data-gate state, benchmark capture time, resolution state and open blocker count in the dashboard/logs.

## PAPER counting rule

A day counts toward `BTC DAILY RANGE PAPER 20` only when:

- readiness state was `READY_FOR_PAPER` **before the morning lock**;
- the day is eligible under the weekday/FOMC gates;
- the forecast was locked before the benchmark probabilities were read;
- all required artifacts exist and hashes verify;
- the authoritative resolution rule has `PASS` status.

If any of these fail, the run is retained as evidence but labelled `DRY_RUN`, `INVALID`, or `VERIFY`; it does not consume one of the 20 tests.

## Current state

`BLOCKED`

Current blockers are listed in `qa/bug-log.json` and `docs/BUG-LOG.md`.
