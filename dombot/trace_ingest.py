"""Shared trace ingest path for DB persistence + Convex logging."""

from __future__ import annotations

import time
import uuid
from typing import Any, Mapping

from dombot.convex_logger import log_run_summary_to_convex
from dombot.db import store_trace
from dombot.domain_utils import canonicalize_domain


def _normalize_step(step: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(step, Mapping):
        action = step.get("action")
        target = step.get("target")
        value = step.get("value")
        success = step.get("success", True)
    else:
        action = getattr(step, "action", None)
        target = getattr(step, "target", None)
        value = getattr(step, "value", None)
        success = getattr(step, "success", True)

    if not isinstance(action, str) or not action.strip():
        raise ValueError("each step action must be a non-empty string")
    if not isinstance(target, str) or not target.strip():
        raise ValueError("each step target must be a non-empty string")

    normalized: dict[str, Any] = {
        "action": action.strip(),
        "target": target.strip(),
        "value": value if value is None or isinstance(value, str) else str(value),
        "success": bool(success),
    }
    return normalized


def ingest_trace(
    *,
    task: str,
    domain: str,
    steps: list[Mapping[str, Any] | Any],
    success: bool,
    partial: bool = False,
    trace_id: str | None = None,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    if not task or not task.strip():
        raise ValueError("task must be a non-empty string")
    if not domain or not domain.strip():
        raise ValueError("domain must be a non-empty string")
    if not steps:
        raise ValueError("steps must be a non-empty list")

    normalized_steps = [_normalize_step(step) for step in steps]
    normalized_domain = canonicalize_domain(domain) or domain.strip().lower()
    resolved_trace_id = trace_id.strip() if trace_id and trace_id.strip() else f"trace-{uuid.uuid4().hex}"
    resolved_timestamp = int(timestamp_ms if timestamp_ms is not None else time.time() * 1000)
    successful_steps = sum(1 for step in normalized_steps if step["success"])
    failed_steps = max(0, len(normalized_steps) - successful_steps)

    store_trace(
        task=task.strip(),
        domain=normalized_domain,
        trace=normalized_steps,
        success=bool(success),
    )

    log_run_summary_to_convex(
        trace_id=resolved_trace_id,
        task=task.strip(),
        domain=normalized_domain,
        success=bool(success),
        partial=bool(partial),
        step_count=len(normalized_steps),
        successful_steps=successful_steps,
        failed_steps=failed_steps,
        timestamp_ms=resolved_timestamp,
    )

    return {
        "trace_id": resolved_trace_id,
        "task": task.strip(),
        "domain": normalized_domain,
        "success": bool(success),
        "partial": bool(partial),
        "step_count": len(normalized_steps),
        "timestamp_ms": resolved_timestamp,
    }
