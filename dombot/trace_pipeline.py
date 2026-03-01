"""Laminar trace processing pipeline.

Captures browser-use agent traces via Laminar, normalizes them into
canonical models, labels step/run outcomes, and hands off to the
data layer (Eric's store_trace) for persistence in MongoDB.

Trigger: called from register_done_callback inside an @observe() span.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field

from lmnr import Laminar, LaminarClient

from dombot.config import LAMINAR_API_KEY

logger = logging.getLogger("dombot.trace_pipeline")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_STEP_COUNT = 2  # runs shorter than this are marked partial

CONVERGENCE_MIN_RUNS = 5
CONVERGENCE_MIN_SUCCESS_RATE = 0.6
CONVERGENCE_PATH_CONSISTENCY = 0.5

# ---------------------------------------------------------------------------
# Canonical models
# ---------------------------------------------------------------------------


@dataclass
class NormalizedStep:
    step_idx: int
    action_type: str  # "click", "type", "navigate", etc.
    target: str  # selector or element description
    value: str | None  # typed value if applicable
    url: str
    latency_ms: int
    success: bool
    failure_reason: str | None  # "selector" | "navigation" | "auth" | "timeout" | "unknown"
    raw_input: str
    raw_output: str


@dataclass
class NormalizedTrace:
    trace_id: str
    task: str
    domain: str
    success: bool  # run-level gate
    partial: bool  # True if run ended mid-task without explicit completion
    steps: list[NormalizedStep] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

_initialized = False
_client: LaminarClient | None = None
_processed_trace_ids: set[str] = set()  # idempotency guard


def initialize_laminar() -> None:
    """Initialize Laminar instrumentation once at process startup.

    Disables BROWSER_USE_SESSION which is unstable with use_cloud=True.
    """
    global _initialized, _client

    if _initialized:
        return

    api_key = LAMINAR_API_KEY or os.getenv("LMNR_PROJECT_API_KEY")
    if not api_key:
        logger.warning("No Laminar API key found — trace pipeline disabled")
        return

    Laminar.initialize(
        project_api_key=api_key,
        disabled_instruments={"BROWSER_USE_SESSION"},
    )
    _client = LaminarClient(project_api_key=api_key)
    _initialized = True
    logger.info("Laminar initialized (BROWSER_USE_SESSION disabled)")


# ---------------------------------------------------------------------------
# Extraction — fetch spans from Laminar with retry
# ---------------------------------------------------------------------------


def _get_client() -> LaminarClient | None:
    return _client


def fetch_tool_spans(
    trace_id: str, retries: int = 3, delay: float = 2.0
) -> list[dict]:
    """Fetch TOOL spans for a trace.  Retries if spans are not yet available."""
    client = _get_client()
    if client is None:
        logger.warning("Laminar client not initialized — skipping span fetch")
        return []

    Laminar.flush()

    for attempt in range(retries):
        try:
            spans = client.sql.query(
                sql="""
                SELECT name, status, input, output, start_time, duration
                FROM spans
                WHERE trace_id = {trace_id:String}
                  AND span_type = 'TOOL'
                ORDER BY start_time ASC
                """,
                parameters={"trace_id": trace_id},
            )
            if spans:
                return spans
        except Exception:
            logger.exception("Laminar SQL query failed (attempt %d/%d)", attempt + 1, retries)

        if attempt < retries - 1:
            time.sleep(delay)

    logger.warning("No TOOL spans found for trace %s after %d retries", trace_id, retries)
    return []


def fetch_trace_status(trace_id: str) -> str | None:
    """Return the trace-level status ('ok' or 'error'), or None on failure."""
    client = _get_client()
    if client is None:
        return None

    try:
        rows = client.sql.query(
            sql="SELECT status FROM traces WHERE id = {trace_id:String}",
            parameters={"trace_id": trace_id},
        )
        return rows[0]["status"] if rows else None
    except Exception:
        logger.exception("Failed to fetch trace status for %s", trace_id)
        return None


# ---------------------------------------------------------------------------
# Labeling — step-level failure taxonomy
# ---------------------------------------------------------------------------


def _classify_failure(output: str) -> str:
    """Classify a failed step's output into a failure category."""
    output_lower = output.lower()
    if "selector" in output_lower or "element" in output_lower:
        return "selector"
    if "timeout" in output_lower:
        return "timeout"
    if "navigation" in output_lower or "navigate" in output_lower:
        return "navigation"
    if "auth" in output_lower or "login" in output_lower or "forbidden" in output_lower:
        return "auth"
    return "unknown"


def label_step(idx: int, span: dict) -> NormalizedStep:
    """Convert a raw Laminar TOOL span into a NormalizedStep."""
    success = span.get("status") in ("ok", "success")
    failure_reason = None if success else _classify_failure(span.get("output", ""))

    raw_input = span.get("input", "{}")
    try:
        parsed = json.loads(raw_input) if isinstance(raw_input, str) else raw_input
    except (json.JSONDecodeError, TypeError):
        parsed = {}

    params = parsed.get("params", {})
    action = span.get("name", "unknown")

    # Action-aware target extraction
    if action == "navigate":
        target = params.get("url", "unknown")
    elif action in ("input", "click"):
        target = params.get("selector") or str(params.get("index", "unknown"))
    elif action == "send_keys":
        target = params.get("keys", "unknown")
    elif action == "done":
        raw_out = span.get("output", "{}")
        try:
            out = json.loads(raw_out) if isinstance(raw_out, str) else raw_out
            target = (out.get("long_term_memory") or out.get("extracted_content") or "")[:80]
        except Exception:
            target = "unknown"
    else:
        target = (
            params.get("selector")
            or params.get("task_description")
            or params.get("index")
            or "unknown"
        )

    return NormalizedStep(
        step_idx=idx,
        action_type=action,
        target=str(target) if target is not None else "unknown",
        value=params.get("value") or params.get("text"),
        url=params.get("url", ""),
        latency_ms=int(float(span.get("duration", 0)) * 1000),
        success=success,
        failure_reason=failure_reason,
        raw_input=raw_input if isinstance(raw_input, str) else json.dumps(raw_input),
        raw_output=span.get("output", "{}"),
    )


# ---------------------------------------------------------------------------
# Run-level success gate
# ---------------------------------------------------------------------------


def determine_run_success(
    trace_status: str | None,
    steps: list[NormalizedStep],
) -> tuple[bool, bool]:
    """Determine (success, partial) for a completed run.

    Success requires:
      1. trace_status == "ok"
      2. at least one step output contains "is_done": true
      3. step count >= MIN_STEP_COUNT

    If 1 passes but 2 or 3 fail → partial=True.
    """
    if trace_status not in ("ok", "success"):
        return False, False

    if len(steps) < MIN_STEP_COUNT:
        return False, True

    completed = any('"is_done": true' in s.raw_output for s in steps)
    if not completed:
        # Also check for is_done as parsed JSON in case of formatting variance
        for s in steps:
            try:
                out = json.loads(s.raw_output) if isinstance(s.raw_output, str) else s.raw_output
                if isinstance(out, dict) and out.get("is_done") is True:
                    completed = True
                    break
            except (json.JSONDecodeError, TypeError):
                continue

    if not completed:
        return False, True

    return True, False


# ---------------------------------------------------------------------------
# Full pipeline: extract → label → gate → handoff
# ---------------------------------------------------------------------------


def build_step_data(step: NormalizedStep) -> dict:
    """Convert a NormalizedStep into the StepData dict for store_trace."""
    return {
        "action": step.action_type,
        "target": step.target,
        "value": step.value,
        "success": step.success,
    }


async def process_trace(
    history,
    trace_id: str | None,
    task: str,
    domain: str,
) -> NormalizedTrace | None:
    """Full pipeline: fetch Laminar spans → label → determine success → store.

    Called from register_done_callback while inside the @observe() span.
    Falls back to history-based extraction if Laminar spans aren't available.
    """
    from dombot.db import store_trace

    # --- idempotency guard ---
    if trace_id and trace_id in _processed_trace_ids:
        logger.info("Trace %s already processed — skipping", trace_id)
        return None
    if trace_id:
        _processed_trace_ids.add(trace_id)

    # --- try Laminar path first ---
    steps: list[NormalizedStep] = []
    trace_status: str | None = None

    if trace_id and _initialized:
        raw_spans = fetch_tool_spans(trace_id)
        trace_status = fetch_trace_status(trace_id)

        for idx, span in enumerate(raw_spans):
            steps.append(label_step(idx, span))

        logger.info(
            "Laminar extraction: %d steps from trace %s (status=%s)",
            len(steps), trace_id, trace_status,
        )

    # --- supplement: check browser-use history for is_done signal ---
    # The 'done' span may lag in Laminar but is always in history.
    history_says_done = _history_has_done(history)
    if history_says_done and steps and not any('"is_done": true' in s.raw_output for s in steps):
        # Add a synthetic done step so the success gate sees it
        steps.append(NormalizedStep(
            step_idx=len(steps),
            action_type="done",
            target="",
            value=None,
            url="",
            latency_ms=0,
            success=True,
            failure_reason=None,
            raw_input="{}",
            raw_output='{"is_done": true}',
        ))
        logger.info("Added synthetic done step from history (Laminar lag)")

    # --- fallback: extract from browser-use history ---
    if not steps:
        logger.info("No Laminar spans — falling back to history-based extraction")
        steps = _extract_from_history(history)
        trace_status = "ok"  # if we got here the run didn't crash

    # --- run-level success gate ---
    success, partial = determine_run_success(trace_status, steps)

    trace = NormalizedTrace(
        trace_id=trace_id or "unknown",
        task=task,
        domain=domain,
        success=success,
        partial=partial,
        steps=steps,
    )

    # --- handoff to Eric's store_trace ---
    store_trace(
        task=trace.task,
        domain=trace.domain,
        trace=[build_step_data(s) for s in trace.steps],
        success=trace.success,
    )

    # --- log to Convex for real-time analytics ---
    try:
        from dombot.convex_logger import log_run_to_convex

        log_run_to_convex(trace)
    except Exception:
        logger.debug("Convex log skipped", exc_info=True)

    status_label = "SUCCESS" if success else ("PARTIAL" if partial else "FAILED")
    logger.info(
        "Pipeline complete: %s | %d steps | trace_id=%s",
        status_label, len(steps), trace_id,
    )

    return trace


# ---------------------------------------------------------------------------
# Fallback: extract steps from browser-use AgentHistoryList
# ---------------------------------------------------------------------------


def _history_has_done(history) -> bool:
    """Check if browser-use history contains a successful 'done' action."""
    items = history.history if hasattr(history, "history") else (history or [])
    for item in items:
        if not (item.model_output and item.model_output.action):
            continue
        for action in item.model_output.action:
            data = action.model_dump(exclude_unset=True)
            if "done" in data:
                done_info = data["done"]
                if isinstance(done_info, dict) and done_info.get("success", done_info.get("text")):
                    return True
    return False


def _extract_from_history(history) -> list[NormalizedStep]:
    """Parse browser-use history into NormalizedSteps when Laminar is unavailable."""
    steps: list[NormalizedStep] = []
    items = history.history if hasattr(history, "history") else (history or [])

    idx = 0
    for item in items:
        if not (item.model_output and item.model_output.action):
            continue
        for action in item.model_output.action:
            action_data = action.model_dump(exclude_unset=True)
            action_name = next(iter(action_data.keys()), "unknown")
            params = action_data.get(action_name, {})

            raw_output = ""
            if hasattr(item, "result") and item.result:
                try:
                    raw_output = json.dumps(item.result.model_dump(exclude_unset=True))
                except Exception:
                    raw_output = str(item.result)

            steps.append(
                NormalizedStep(
                    step_idx=idx,
                    action_type=action_name,
                    target=params.get("selector", params.get("index", "unknown"))
                    if isinstance(params, dict)
                    else str(params),
                    value=params.get("value") or params.get("text")
                    if isinstance(params, dict)
                    else None,
                    url="",
                    latency_ms=0,
                    success=True,  # history doesn't expose per-step failure
                    failure_reason=None,
                    raw_input=json.dumps(action_data),
                    raw_output=raw_output,
                )
            )
            idx += 1

    return steps
