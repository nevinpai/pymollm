"""HTTP helpers (httpx if installed, otherwise urllib)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def request_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Any = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """HTTP request returning parsed JSON (or {"_empty": True} for 204)."""
    headers = dict(headers or {})
    body_bytes = None
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    try:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            r = client.request(method.upper(), url, headers=headers, content=body_bytes)
            if r.status_code == 204:
                return {"_empty": True, "_status": 204}
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:800]}")
            if not r.content:
                return {"_empty": True, "_status": r.status_code}
            return r.json()
    except ImportError:
        pass

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read()
            if status == 204 or not raw:
                return {"_empty": True, "_status": status}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HTTP {exc.code}: {err_body}") from exc
