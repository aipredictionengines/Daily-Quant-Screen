# Daily Quant Screen — Bug Log

This log is part of the **test gate**, not just a notes file. A PAPER 20 forecast must not be counted until the readiness gate says `READY_FOR_PAPER`.

The machine-readable source of truth is `qa/bug-log.json`. GitHub Issues can mirror these entries after the public repository is created.

## Severity

| Severity | Meaning | PAPER impact |
|---|---|---|
| `P0` | Data corruption, leakage, wrong resolution, or unsafe behavior | Immediate blocker |
| `P1` | Core forecast/resolution/integrity defect | Blocker |
| `P2` | Important defect with a safe workaround or non-core missing feature | Usually non-blocking |
| `P3` | UI/docs/observability issue | Non-blocking unless specifically promoted |

## Status

`OPEN → FIXING → VERIFY → CLOSED`

`DEFERRED` is allowed only for non-blocking P2/P3 issues with a written reason.

## Current known issues

| ID | Severity | Status | Area | Blocks PAPER? | Summary |
|---|---:|---|---|---|---|
| DQS-BUG-001 | P1 | OPEN | integrations | YES | Live Binance + Polymarket end-to-end integration not yet verified |
| DQS-BUG-002 | P1 | OPEN | resolution | YES | Market resolution rules not yet auto-verified against the day's rules text |
| DQS-BUG-003 | P1 | OPEN | timezones | YES | Sofia/New York DST edge cases need explicit integration tests |
| DQS-BUG-004 | P2 | OPEN | scoring | NO | Hit-price scoring not yet persisted |
| DQS-BUG-005 | P2 | OPEN | context | NO | Gemini failure/fallback path needs recorded test |
| DQS-BUG-006 | P3 | OPEN | dashboard | NO | GitHub Pages observability deployment not yet verified |

## Bug entry requirements

Every bug must record:

- stable ID (`DQS-BUG-NNN`);
- severity and status;
- affected module;
- whether it blocks PAPER testing;
- exact reproduction/evidence;
- expected vs actual behavior when applicable;
- next action;
- fix commit/PR once available;
- verification result before `CLOSED`.

## Rule

A bug is **not closed because code was changed**. It is closed only after a separate verification run reproduces the original scenario and passes.
