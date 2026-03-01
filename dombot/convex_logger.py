"""Thin Convex logging layer.

Pushes completed run summaries to Convex for real-time analytics.
Fails silently if CONVEX_URL is not set or convex package is missing.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dombot.trace_pipeline import NormalizedTrace

logger = logging.getLogger("dombot.convex_logger")

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        from convex import ConvexClient

        from dombot.config import CONVEX_URL

        if not CONVEX_URL:
            return None

        _client = ConvexClient(CONVEX_URL)
        logger.info("Convex client initialized")
    except ImportError:
        pass

    return _client


def log_run_to_convex(trace: NormalizedTrace) -> None:
    """Push a run summary to Convex. No-ops if Convex is not configured."""
    client = _get_client()
    if client is None:
        return

    now_ms = int(time.time() * 1000)
    successful_steps = sum(1 for s in trace.steps if s.success)

    try:
        client.mutation(
            "runs:insertRun",
            {
                "traceId": trace.trace_id,
                "task": trace.task,
                "domain": trace.domain,
                "success": trace.success,
                "partial": trace.partial,
                "stepCount": len(trace.steps),
                "successfulSteps": successful_steps,
                "failedSteps": len(trace.steps) - successful_steps,
                "timestampMs": now_ms,
            },
        )

        client.mutation(
            "taskStats:upsertTaskStats",
            {
                "task": trace.task,
                "domain": trace.domain,
                "success": trace.success,
                "nowMs": now_ms,
            },
        )

        logger.info("Convex: logged run trace_id=%s", trace.trace_id)
    except Exception:
        logger.exception("Convex: failed to log run (non-fatal)")
