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
import re
import time
import uuid
from dataclasses import dataclass, field

from lmnr import Laminar, LaminarClient

from dombot.config import LAMINAR_API_KEY
from dombot.domain_utils import canonicalize_domain

logger = logging.getLogger("dombot.trace_pipeline")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_STEP_COUNT = 2  # runs shorter than this are marked partial

CONVERGENCE_MIN_RUNS = 5
CONVERGENCE_MIN_SUCCESS_RATE = 0.6
CONVERGENCE_PATH_CONSISTENCY = 0.5

# If true, a negative browser-use judge verdict forces run success=False.
REQUIRE_JUDGE_PASS = os.getenv("DOMBOT_REQUIRE_JUDGE_PASS", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}

# Efficiency filter: runs longer than (optimal_path_length + EFFICIENCY_SLACK) steps
# do not update the optimal path or boost success-rate confidence.
# They still increment run_count so volume grows honestly.
EFFICIENCY_SLACK: int = int(os.getenv("DOMBOT_EFFICIENCY_SLACK", "3"))
EFFICIENCY_FILTER_ENABLED: bool = os.getenv(
    "DOMBOT_EFFICIENCY_FILTER", "1"
).strip().lower() not in {"0", "false", "no"}
EFFICIENCY_BASE_SLACK: int = int(os.getenv("DOMBOT_EFFICIENCY_BASE_SLACK", str(EFFICIENCY_SLACK)))
EFFICIENCY_PHASE_SLACK: int = int(os.getenv("DOMBOT_EFFICIENCY_PHASE_SLACK", "2"))
EFFICIENCY_NOISE_SLACK: int = int(os.getenv("DOMBOT_EFFICIENCY_NOISE_SLACK", "1"))

# Actions that are meta/tool-level and should never be stored as learned path steps.
# dombot_query/dombot_report are DomBot tool calls, not browser actions.
# done marks task completion — storing it pollutes optimal_actions with result text.
_SKIP_ACTIONS = frozenset({"dombot_query", "dombot_report", "done"})

_CAPTCHA_KEYWORDS = frozenset({
    "captcha", "recaptcha", "challenge", "verify you are human", "i am not a robot",
})

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
    path_update_allowed: bool = True
    efficiency_reason: str = ""
    contract_pass: bool = True
    schema_pass: bool = True
    format_pass: bool = True
    scope_pass: bool = True
    contract_failure_reason: str = ""
    agent_steps: int = 0
    laminar_tool_steps: int = 0
    pipeline_steps_total: int = 0
    captcha_events: int = 0
    interstitial_events: int = 0
    modal_recovery_count: int = 0


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


def apply_quality_gate_from_judge(
    history,
    success: bool,
    partial: bool,
) -> tuple[bool, bool]:
    """Optionally gate run success based on browser-use judge verdict.

    If judge verdict is explicitly False and gating is enabled, override
    success/partial so the run does not reinforce confidence.
    """
    if not REQUIRE_JUDGE_PASS:
        return success, partial

    try:
        is_validated = history.is_validated() if hasattr(history, "is_validated") else None
        judgement = history.judgement() if hasattr(history, "judgement") else None
    except Exception:
        return success, partial

    if is_validated is False:
        reason = ""
        if isinstance(judgement, dict) and judgement.get("failure_reason"):
            reason = f" reason={judgement.get('failure_reason')!r}"
        logger.info("Quality gate: judge verdict FAIL -> forcing run failure.%s", reason)
        return False, False

    return success, partial


# ---------------------------------------------------------------------------
# Efficiency filter
# ---------------------------------------------------------------------------


def _count_effective_steps(steps: list[NormalizedStep]) -> int:
    """Steps that reflect planner decisions, excluding synthetic done markers."""
    return sum(1 for s in steps if s.action_type != "done")


def _noise_counts(steps: list[NormalizedStep]) -> tuple[int, int, int]:
    """Return (captcha_events, interstitial_events, modal_recovery_count)."""
    captcha = 0
    interstitial = 0
    modal_recovery = 0
    for s in steps:
        combined = " ".join([s.action_type, s.target, s.value or "", s.raw_output]).lower()
        if any(kw in combined for kw in _CAPTCHA_KEYWORDS):
            captcha += 1
        if any(kw in combined for kw in ("interstitial", "protection plan", "upsell", "confirm you're human")):
            interstitial += 1
        if s.action_type == "click" and any(kw in combined for kw in ("no thanks", "close dialog", "close")):
            modal_recovery += 1
    return captcha, interstitial, modal_recovery


def _has_captcha_noise(steps: list[NormalizedStep]) -> bool:
    """Return True if any step shows CAPTCHA handling.

    CAPTCHA steps are environment noise, not planner waste — the filter should
    not penalise runs for them.
    """
    for s in steps:
        combined = " ".join([
            s.action_type, s.target, s.value or "", s.raw_output,
        ]).lower()
        if any(kw in combined for kw in _CAPTCHA_KEYWORDS):
            return True
    return False


def _estimate_phase_count(task: str) -> int:
    """Estimate number of task phases from prompt structure."""
    text = task.lower()
    count = 1
    if "first," in text and "then" in text:
        count += 1
    count += len(re.findall(r"\bthen\b", text))
    count += len(re.findall(r"\bafter that\b", text))
    if any(kw in text for kw in ("add", "cart", "search for")) and text.count(" and ") >= 2:
        count += 1
    return max(1, min(count, 6))


def _check_efficiency(
    steps: list[NormalizedStep],
    task: str,
    domain: str,
) -> tuple[bool, str]:
    """Check whether this run is within the efficiency budget.

    Budget = len(prior.optimal_actions) + EFFICIENCY_SLACK.

    Returns (ok, reason) where reason is a log-friendly string.

    Rules:
    - Filter disabled via env var → always ok.
    - No prior optimal path (cold start) → always ok.
    - effective_steps <= budget → ok.
    - effective_steps > budget → not ok; run counted but path NOT updated.
    """
    if not EFFICIENCY_FILTER_ENABLED:
        return True, "filter disabled"

    from dombot.db import query_context
    prior = query_context(task, domain)
    if prior is None or not prior.optimal_actions:
        return True, "no prior path — cold start accepted"

    optimal_len = len(prior.optimal_actions)
    effective = _count_effective_steps(steps)
    captcha_events, interstitial_events, modal_recovery_count = _noise_counts(steps)
    phase_count = _estimate_phase_count(task)
    phase_penalty = max(0, phase_count - 1) * EFFICIENCY_PHASE_SLACK
    noise_penalty = (captcha_events + interstitial_events + modal_recovery_count) * EFFICIENCY_NOISE_SLACK
    budget = optimal_len + EFFICIENCY_BASE_SLACK + phase_penalty + noise_penalty

    if effective <= budget:
        return True, (
            f"{effective} steps ≤ budget {budget} "
            f"(optimal={optimal_len} + base_slack={EFFICIENCY_BASE_SLACK} "
            f"+ phase_penalty={phase_penalty} + noise_penalty={noise_penalty})"
        )

    return False, (
        f"{effective} steps > budget {budget} "
        f"(optimal={optimal_len} + base_slack={EFFICIENCY_BASE_SLACK} "
        f"+ phase_penalty={phase_penalty} + noise_penalty={noise_penalty}) — path NOT updated"
    )


def _evaluate_contract(task: str, final_result: str | None) -> tuple[bool, bool, bool, bool, str]:
    """Return (contract_pass, schema_pass, format_pass, scope_pass, reason)."""
    if not final_result:
        return False, False, False, False, "missing final_result"

    text = final_result.strip()
    # Normalize escaped newlines from model output ("\\n") into real lines before
    # enforcing "exactly N lines" contracts.
    if "\\n" in text:
        text = text.replace("\\n", "\n")
    lower_task = task.lower()

    schema_pass = True
    format_pass = True
    scope_pass = True
    reasons: list[str] = []

    m = re.search(r"exactly\s+(\d+)\s+lines?", lower_task)
    if m:
        expected = int(m.group(1))
        got = len([ln for ln in text.splitlines() if ln.strip()])
        if got != expected:
            schema_pass = False
            format_pass = False
            reasons.append(f"expected {expected} lines, got {got}")

    if "cart page only" in lower_task:
        banned = (
            "not displayed on cart page",
            "from product page",
            "from search results",
            "not visible on this cart page",
        )
        if any(tok in text.lower() for tok in banned):
            scope_pass = False
            reasons.append("scope violation: non-cart source referenced")

    if "if any field is missing, fail" in lower_task:
        missing_tokens = ("missing", "information unavailable", "unavailable", "n/a")
        if any(tok in text.lower() for tok in missing_tokens):
            if "fail" not in text.lower() and "failed" not in text.lower():
                schema_pass = False
                reasons.append("missing field without explicit failure")

    contract_pass = schema_pass and format_pass and scope_pass
    return contract_pass, schema_pass, format_pass, scope_pass, "; ".join(reasons)


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
    external_metrics: dict | None = None,
) -> NormalizedTrace | None:
    """Full pipeline: fetch Laminar spans → label → determine success → store.

    Called from register_done_callback while inside the @observe() span.
    Falls back to history-based extraction if Laminar spans aren't available.
    """
    from dombot.trace_ingest import ingest_trace

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
    canonical_domain = canonicalize_domain(domain) or domain
    resolved_trace_id = trace_id or f"trace-{uuid.uuid4().hex}"
    success, partial = apply_quality_gate_from_judge(history, success, partial)
    execution_success = bool(success)
    final_result = _extract_final_result(history)
    contract_pass, schema_pass, format_pass, scope_pass, contract_reason = _evaluate_contract(task, final_result)
    if success and not contract_pass:
        success = False
        partial = False
        logger.info("Quality gate: contract validation FAIL -> forcing run failure. reason=%r", contract_reason)

    trace = NormalizedTrace(
        trace_id=resolved_trace_id,
        task=task,
        domain=canonical_domain,
        success=success,
        partial=partial,
        steps=steps,
        contract_pass=contract_pass,
        schema_pass=schema_pass,
        format_pass=format_pass,
        scope_pass=scope_pass,
        contract_failure_reason=contract_reason,
    )

    run_duration_s = 0.0
    if trace.steps:
        run_duration_s = round(
            sum(max(0, int(s.latency_ms or 0)) for s in trace.steps) / 1000.0,
            3,
        )

    # --- efficiency filter: only reinforce path on compact successful runs ---
    # Bloated runs (judge passed but too many steps) still count toward run_count
    # so volume grows honestly, but they don't update optimal_actions or boost
    # success-rate confidence.
    efficiency_ok = True
    efficiency_reason = "not evaluated"
    if success:
        efficiency_ok, efficiency_reason = _check_efficiency(steps, task, domain)
        if not efficiency_ok:
            logger.info("Efficiency filter: %s", efficiency_reason)
        else:
            logger.debug("Efficiency filter: %s", efficiency_reason)
    agent_steps = len(history.history) if hasattr(history, "history") else len(steps)
    laminar_tool_steps = _count_effective_steps(steps)
    pipeline_steps_total = len(steps)
    captcha_events, interstitial_events, modal_recovery_count = _noise_counts(steps)
    trace.path_update_allowed = bool(success and efficiency_ok)
    trace.efficiency_reason = efficiency_reason
    trace.agent_steps = int(agent_steps)
    trace.laminar_tool_steps = int(laminar_tool_steps)
    trace.pipeline_steps_total = int(pipeline_steps_total)
    trace.captcha_events = int(captcha_events)
    trace.interstitial_events = int(interstitial_events)
    trace.modal_recovery_count = int(modal_recovery_count)

    # --- handoff to Eric's store_trace ---
    store_trace(
        task=trace.task,
        domain=trace.domain,
        trace=[build_step_data(s) for s in trace.steps
               if s.action_type not in _SKIP_ACTIONS],
        success=trace.success,
        path_update_allowed=trace.path_update_allowed,
        run_metrics={
            "steps": len(trace.steps),
            "duration_s": run_duration_s,
            "final_result": final_result,
            "path_update_allowed": trace.path_update_allowed,
            "efficiency_reason": trace.efficiency_reason,
            "contract_pass": trace.contract_pass,
            "schema_pass": trace.schema_pass,
            "format_pass": trace.format_pass,
            "scope_pass": trace.scope_pass,
            "contract_failure_reason": trace.contract_failure_reason,
            "execution_success": execution_success,
            "agent_steps": trace.agent_steps,
            "laminar_tool_steps": trace.laminar_tool_steps,
            "pipeline_steps_total": trace.pipeline_steps_total,
            "captcha_events": trace.captcha_events,
            "interstitial_events": trace.interstitial_events,
            "modal_recovery_count": trace.modal_recovery_count,
            **(external_metrics or {}),
        },
    )

    if success and not efficiency_ok:
        status_label = "SUCCESS (bloated — path not updated)"
    elif success:
        status_label = "SUCCESS"
    elif partial:
        status_label = "PARTIAL"
    else:
        status_label = "FAILED"

    logger.info(
        "Pipeline complete: %s | %d steps | trace_id=%s",
        status_label, len(steps), trace.trace_id,
    )

    return trace


# ---------------------------------------------------------------------------
# Fallback: extract steps from browser-use AgentHistoryList
# ---------------------------------------------------------------------------


def _extract_final_result(history) -> str | None:
    """Extract the agent's final answer from the last 'done' action in history."""
    items = history.history if hasattr(history, "history") else (history or [])
    for item in reversed(items):
        if not (item.model_output and item.model_output.action):
            continue
        for action in item.model_output.action:
            data = action.model_dump(exclude_unset=True)
            if "done" in data:
                done_info = data["done"]
                if isinstance(done_info, dict):
                    return done_info.get("text") or done_info.get("extracted_content")
                if isinstance(done_info, str):
                    return done_info
    return None


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
