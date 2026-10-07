from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ACTIVE_STATES = {"OPEN", "FIXING", "VERIFY"}
RED_STATES = {"OPEN", "FIXING"}


def load_bug_log(root: Path) -> dict[str, Any]:
    path = root / "qa" / "bug-log.json"
    if not path.exists():
        return {"schema_version": "missing", "bugs": []}
    return json.loads(path.read_text(encoding="utf-8"))


def load_candidate_gate(root: Path) -> dict[str, Any]:
    path = root / "qa" / "candidate-gate.json"
    if not path.exists():
        return {
            "schema_version": "missing",
            "candidate_id": "DQS-BTC-CANDIDATE-001",
            "state": "CANDIDATE_READY",
            "passed": False,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def readiness_report(root: Path) -> dict[str, Any]:
    log = load_bug_log(root)
    gate = load_candidate_gate(root)
    bugs = log.get("bugs", [])
    active = [b for b in bugs if str(b.get("status", "OPEN")).upper() in ACTIVE_STATES]

    red_blockers = [
        b
        for b in active
        if str(b.get("status", "")).upper() in RED_STATES
        and (bool(b.get("blocks_paper_test")) or str(b.get("severity", "")).upper() in {"P0", "P1"})
    ]
    verify_blockers = [
        b
        for b in active
        if str(b.get("status", "")).upper() == "VERIFY"
        and (bool(b.get("blocks_paper_test")) or str(b.get("severity", "")).upper() in {"P0", "P1"})
    ]

    counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for bug in active:
        sev = str(bug.get("severity", "")).upper()
        if sev in counts:
            counts[sev] += 1

    candidate_passed = gate.get("state") == "READY_FOR_PAPER" and gate.get("passed") is True

    if red_blockers:
        state = "BLOCKED"
    elif candidate_passed:
        state = "READY_FOR_PAPER"
    else:
        state = "CANDIDATE_READY"

    return {
        "schema_version": "dqs.qa.readiness.v0.3",
        "state": state,
        "candidate_ready": not red_blockers and not candidate_passed,
        "candidate_passed": candidate_passed,
        "ready_for_paper": not red_blockers and candidate_passed,
        "candidate_gate": gate,
        "open_bug_counts": counts,
        "blocker_count": len(red_blockers) + len(verify_blockers),
        "red_blocker_count": len(red_blockers),
        "verify_blocker_count": len(verify_blockers),
        "red_blockers": [
            {"id": b.get("id"), "severity": b.get("severity"), "status": b.get("status"), "title": b.get("title")}
            for b in red_blockers
        ],
        "verify_blockers": [
            {"id": b.get("id"), "severity": b.get("severity"), "status": b.get("status"), "title": b.get("title")}
            for b in verify_blockers
        ],
        "note": (
            "CANDIDATE_READY permits a non-counting candidate observation only. "
            "READY_FOR_PAPER requires a passing candidate lifecycle review."
        ),
    }
