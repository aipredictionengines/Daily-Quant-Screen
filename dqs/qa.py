from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OPEN_STATES = {"OPEN", "FIXING", "VERIFY"}


def load_bug_log(root: Path) -> dict[str, Any]:
    path = root / "qa" / "bug-log.json"
    if not path.exists():
        return {"schema_version": "missing", "bugs": []}
    return json.loads(path.read_text(encoding="utf-8"))


def readiness_report(root: Path) -> dict[str, Any]:
    log = load_bug_log(root)
    bugs = log.get("bugs", [])
    open_bugs = [b for b in bugs if str(b.get("status", "OPEN")).upper() in OPEN_STATES]
    blockers = [b for b in open_bugs if bool(b.get("blocks_paper_test")) or str(b.get("severity", "")).upper() in {"P0", "P1"}]
    counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for bug in open_bugs:
        sev = str(bug.get("severity", "")).upper()
        if sev in counts:
            counts[sev] += 1

    state = "BLOCKED" if blockers else "DRY_RUN"
    return {
        "schema_version": "dqs.qa.readiness.v0.1",
        "state": state,
        "ready_for_paper": False,
        "open_bug_counts": counts,
        "blocker_count": len(blockers),
        "blockers": [
            {
                "id": b.get("id"),
                "severity": b.get("severity"),
                "status": b.get("status"),
                "title": b.get("title"),
            }
            for b in blockers
        ],
        "note": "Closing blockers is necessary but not sufficient; run the full TEST-READINESS hard gate before setting READY_FOR_PAPER.",
    }
