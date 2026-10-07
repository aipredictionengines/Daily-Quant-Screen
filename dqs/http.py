from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


class HttpError(RuntimeError):
    pass


def get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 20) -> Any:
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "DailyQuantScreen/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network dependent
        raise HttpError(f"GET failed: {url}: {exc}") from exc


def post_json(
    url: str,
    payload: Any,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", "User-Agent": "DailyQuantScreen/0.1"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network dependent
        raise HttpError(f"POST failed: {url}: {exc}") from exc
