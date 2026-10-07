from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def write_immutable(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Immutable artifact already exists: {path}")
    digest = sha256_payload(payload)
    envelope = {"sha256": digest, "payload": payload}
    path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")
    return digest


def read_envelope(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    digest = sha256_payload(data["payload"])
    if digest != data.get("sha256"):
        raise RuntimeError(f"Integrity check failed: {path}")
    return data
