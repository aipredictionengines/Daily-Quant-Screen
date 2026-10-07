# TEST READINESS GATE — BTC DAILY RANGE PAPER 20

The system uses four operational states:

- `BLOCKED` — one or more red P0/P1/source checks; do not lock a candidate.
- `CANDIDATE_READY` — no red blockers; a non-counting candidate may run.
- `CANDIDATE_COMPLETE` — candidate has completed lock → benchmark → resolution → score and passed review.
- `READY_FOR_PAPER` — official PAPER 20 may begin.

## Candidate gate

A candidate may run only when:

1. No active P0/P1 bug is `OPEN` or `FIXING`.
2. LIVE-DATA has no red checks.
3. Binance, Gamma, CLOB, rules, timezone, range coverage and resolution replay are PASS.
4. Any remaining supportive layer may be VERIFY only if it cannot alter the authoritative numerical/resolution inputs.
5. The lock occurs inside 05:00–08:00 Europe/Sofia.
6. Thursday and official FOMC meeting days are excluded.

Candidate artifacts are stored under:

`artifacts/candidates/YYYY-MM-DD/BTC/`

They never increment PAPER 20.

## Hard gate for READY_FOR_PAPER

After at least one clean candidate lifecycle, official PAPER 20 requires:

- candidate forecast written immutably before Polymarket probabilities are fetched;
- forecast SHA-256 verifies;
- market rules snapshot is PASS;
- authoritative Binance resolution replay/live resolution is PASS;
- candidate score is generated without manual mutation;
- no new P0/P1 defect was discovered during the candidate;
- monitoring/bug evidence is retained.

Official artifacts then use:

`artifacts/paper/YYYY-MM-DD/BTC/`

## Current state

**CANDIDATE_READY**

Verification on 2026-10-07:

- CI: 18/18 PASS.
- LIVE-DATA-001: PASS execution, overall health VERIFY only because Gemini is not configured in Actions.
- Red source/QA checks: 0.
- Official PAPER 20: 0/20.

The next step is `DQS-BTC-CANDIDATE-001`, not `P001/20`.
