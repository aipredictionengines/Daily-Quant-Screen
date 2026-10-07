import json
from datetime import date
from pathlib import Path

from dqs.calendar import is_official_fomc_meeting_day


def test_meeting_day_and_non_meeting_day(tmp_path: Path):
    p = tmp_path / "fomc.json"
    p.write_text(json.dumps({"meeting_days": ["2026-10-27", "2026-10-28"]}), encoding="utf-8")
    assert is_official_fomc_meeting_day(date(2026, 10, 27), p) == (True, "PASS")
    assert is_official_fomc_meeting_day(date(2026, 10, 7), p) == (False, "PASS")


def test_missing_calendar_is_verify(tmp_path: Path):
    assert is_official_fomc_meeting_day(date(2026, 10, 7), tmp_path / "missing.json") == (False, "VERIFY")
