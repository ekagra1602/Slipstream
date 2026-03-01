"""Thin Convex logging layer.

Pushes completed run summaries to Convex for real-time analytics.
Fails silently if CONVEX_URL is not configured or Convex is unreachable.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from dombot.convex_http import convex_mutation, is_convex_configured

if TYPE_CHECKING:
    from dombot.trace_pipeline import NormalizedTrace

logger = logging.getLogger("dombot.convex_logger")


def log_run_summary_to_convex(
    *,
    trace_id: str,
    task: str,
    domain: str,
    success: bool,
    partial: bool,
    step_count: int,
    successful_steps: int,
    failed_steps: int,
    timestamp_ms: int | None = None,
) -> None:
    """Push a run summary to Convex. No-ops if Convex is not configured."""
    if not is_convex_configured():
        return

    now_ms = int(timestamp_ms if timestamp_ms is not None else time.time() * 1000)

    try:
        convex_mutation(
            "runs:insertRun",
            {
                "traceId": trace_id,
                "task": task,
                "domain": domain,
                "success": success,
                "partial": partial,
                "stepCount": step_count,
                "successfulSteps": successful_steps,
                "failedSteps": failed_steps,
                "timestampMs": now_ms,
            },
        )

        convex_mutation(
            "taskStats:upsertTaskStats",
            {
                "task": task,
                "domain": domain,
                "success": success,
                "nowMs": now_ms,
            },
        )

        logger.info("Convex: logged run trace_id=%s", trace_id)
    except Exception:
        logger.exception("Convex: failed to log run (non-fatal)")


def log_run_to_convex(trace: NormalizedTrace) -> None:
    """Backward-compatible trace logger entrypoint."""
    successful_steps = sum(1 for s in trace.steps if s.success)
    failed_steps = max(0, len(trace.steps) - successful_steps)
    log_run_summary_to_convex(
        trace_id=trace.trace_id,
        task=trace.task,
        domain=trace.domain,
        success=trace.success,
        partial=trace.partial,
        step_count=len(trace.steps),
        successful_steps=successful_steps,
        failed_steps=failed_steps,
    )
