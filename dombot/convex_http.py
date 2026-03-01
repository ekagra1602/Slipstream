"""Minimal Convex HTTP helpers.

Uses Convex's public HTTP API endpoints directly so we don't depend on a
Python Convex SDK being installed or importable at runtime.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dombot.config import CONVEX_URL

logger = logging.getLogger("dombot.convex_http")


def is_convex_configured() -> bool:
    return bool(CONVEX_URL and CONVEX_URL.strip())


def _base_url() -> str:
    if not is_convex_configured():
        raise RuntimeError("CONVEX_URL is not configured")
    return str(CONVEX_URL).rstrip("/")


def _call(endpoint: str, function_name: str, args: dict[str, Any] | None = None) -> Any:
    payload = {
        "path": function_name,
        "format": "convex_encoded_json",
        "args": [args or {}],
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url=f"{_base_url()}/api/{endpoint}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Convex-Client": "dombot-python-http",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=8.0) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Convex HTTP {exc.code} for {function_name}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Convex connection error for {function_name}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Convex returned non-JSON for {function_name}: {raw}") from exc

    status = data.get("status")
    if status == "success":
        return data.get("value")
    if status == "error":
        raise RuntimeError(
            f"Convex function error for {function_name}: {data.get('errorMessage', 'unknown error')}"
        )
    raise RuntimeError(f"Unexpected Convex response for {function_name}: {data}")


def convex_query(function_name: str, args: dict[str, Any] | None = None) -> Any:
    return _call("query", function_name, args)


def convex_mutation(function_name: str, args: dict[str, Any] | None = None) -> Any:
    return _call("mutation", function_name, args)
