import json
from pathlib import Path

from dqs.qa import readiness_report


def test_readiness_is_blocked_by_open_p1(tmp_path: Path):
    qa = tmp_path / "qa"
    qa.mkdir()
    (qa / "bug-log.json").write_text(
        json.dumps(
            {
                "bugs": [
                    {
                        "id": "DQS-BUG-999",
                        "severity": "P1",
                        "status": "OPEN",
                        "blocks_paper_test": True,
                        "title": "test blocker",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    report = readiness_report(tmp_path)
    assert report["state"] == "BLOCKED"
    assert report["blocker_count"] == 1
    assert report["ready_for_paper"] is False
