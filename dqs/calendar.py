from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def load_calendar(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"meeting_days": [], "status": "MISSING"}
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "PASS"
    return data


def is_official_fomc_meeting_day(day: date, path: Path) -> tuple[bool, str]:
    data = load_calendar(path)
    if data.get("status") != "PASS":
        return False, "VERIFY"
    days = set(str(x) for x in data.get("meeting_days", []))
    return day.isoformat() in days, "PASS"
