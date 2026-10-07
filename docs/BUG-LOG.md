# Daily Quant Screen — Bug Log

This log is part of the test gate. The machine-readable source of truth is `qa/bug-log.json`.

## Lifecycle

`OPEN → FIXING → VERIFY → CLOSED`

A bug is not closed merely because code changed. The original scenario must be verified again.

## Current status — 2026-10-07

| ID | Severity | Status | Area | PAPER blocker | Result |
|---|---:|---|---|---|---|
| DQS-BUG-001 | P1 | CLOSED | integrations | YES | Binance + Gamma + CLOB live health verified |
| DQS-BUG-002 | P1 | CLOSED | resolution rules | YES | Live rules parser verified source/pair/1m/Close/12:00 ET/boundary |
| DQS-BUG-003 | P1 | CLOSED | timezones | YES | DST vectors + exact historical Binance replay verified |
| DQS-BUG-004 | P2 | OPEN | hit scoring | NO | Range candidate can proceed; hit scoring is not yet counted |
| DQS-BUG-005 | P2 | VERIFY | Gemini context | NO | Missing-key fallback verified; full API failure test remains |
| DQS-BUG-006 | P3 | OPEN | Pages | NO | docs dashboard exists; public Pages still needs visual confirmation |
| DQS-BUG-007 | P2 | CLOSED | Binance runner access | NO | HTTP 451 handled with official market-data fallback |
| DQS-BUG-008 | P1 | CLOSED | resolution timestamp | YES | Fixed 12:00-close vs 12:00-open off-by-one; replay PASS |
| DQS-BUG-009 | P1 | CLOSED | market structure | YES | Open-ended range tails restored; live range coverage 11/11 |

## Verification evidence

- CI run #31: **18/18 tests PASS**.
- LIVE-DATA-001 run #22: **success**.
- Health state: **VERIFY**, because Gemini is currently `VERIFY`; there are **no red checks**.
- Binance: PASS via public market-data endpoint.
- Polymarket Gamma: PASS.
- Polymarket CLOB: PASS.
- Range coverage: PASS — 11 total brackets, including both open-ended tails.
- Market rules: PASS.
- FOMC calendar gate: PASS.
- Timezone mapping: PASS.
- Exact historical resolution replay: PASS.

## Current gate

`CANDIDATE_READY`

This allows **DQS-BTC-CANDIDATE-001**, which is stored separately and does **not** count toward PAPER 20.

Official `DQS-BTC-P001/20` remains locked until the candidate completes the full lifecycle:

`morning lock → immutable hash → post-lock benchmark → resolution → score → review`.
