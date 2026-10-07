from pathlib import Path
import pytest

from dqs.storage import read_envelope, write_immutable


def test_immutable(tmp_path: Path):
    p = tmp_path / "x.json"
    digest = write_immutable(p, {"a": 1})
    assert read_envelope(p)["sha256"] == digest
    with pytest.raises(FileExistsError):
        write_immutable(p, {"a": 2})
