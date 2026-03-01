from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Callable

from pymongo import MongoClient

from db.config import (
    COLLECTION_TASK_NODES,
    DB_NAME,
    MONGODB_URI,
    VECTOR_INDEX_NAME,
)
from db.embeddings import embed_task

_client: MongoClient | None = None

# ---------------------------------------------------------------------------
# Event callback system
# ---------------------------------------------------------------------------

_event_callbacks: list[Callable] = []


def register_callback(fn: Callable) -> None:
    """Register a callback to be notified of data changes."""
    _event_callbacks.append(fn)


def _fire_event(event: dict) -> None:
    for fn in _event_callbacks:
        try:
            fn(event)
        except Exception:
            pass


def _get_collection():
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
    return _client[DB_NAME][COLLECTION_TASK_NODES]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def _validate_inputs(task: str, domain: str) -> None:
    if not task or not task.strip():
        raise ValueError("task must be a non-empty string")
    if not domain or not domain.strip():
        raise ValueError("domain must be a non-empty string")


def _validate_step(step: StepData) -> None:
    if not step.action or not step.action.strip():
        raise ValueError("action must be a non-empty string")
    if not step.target or not step.target.strip():
        raise ValueError("target must be a non-empty string")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class StepData:
    action: str
    target: str
    value: str | None = None
    success: bool = True


@dataclass
class OptimalPath:
    task: str
    domain: str
    confidence: float
    run_count: int
    optimal_actions: list[str]
    step_traces: list[dict[str, Any]] = field(default_factory=list)
    successful_results: list[str] = field(default_factory=list)
    last_run: dict[str, Any] = field(default_factory=dict)
    execution_confidence: float = 0.0
    contract_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Public API — the shared contract
# ---------------------------------------------------------------------------

def query_context(task: str, domain: str) -> OptimalPath | None:
    """Vector-search for the most relevant task node and return its optimal path."""
    _validate_inputs(task, domain)
    collection = _get_collection()
    query_embedding = embed_task(task)

    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "task_embedding",
                "queryVector": query_embedding,
                "numCandidates": 50,
                "limit": 5,
                "filter": {"domain": domain},
            }
        },
        {
            "$limit": 1
        },
        {
            "$project": {
                "task": 1,
                "domain": 1,
                "confidence": 1,
                "execution_confidence": 1,
                "contract_confidence": 1,
                "run_count": 1,
                "optimal_actions": 1,
                "step_traces": 1,
                "successful_results": 1,
                "_last_run": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    try:
        results = list(collection.aggregate(pipeline))
    except Exception:
        # Vector index unavailable (e.g. index was dropped, mongot sidecar down).
        # Return None so callers degrade gracefully instead of crashing.
        return None
    if not results:
        return None

    doc = results[0]
    return OptimalPath(
        task=doc["task"],
        domain=doc["domain"],
        confidence=doc.get("confidence", 0.0),
        run_count=doc.get("run_count", 0),
        optimal_actions=doc.get("optimal_actions", []),
        step_traces=doc.get("step_traces", []),
        successful_results=doc.get("successful_results", []),
        last_run=doc.get("_last_run", {}) or {},
        execution_confidence=doc.get("execution_confidence", 0.0),
        contract_confidence=doc.get("contract_confidence", 0.0),
    )


def store_step(task: str, domain: str, step: StepData) -> None:
    """Append a single step observation to the task node's step_traces."""
    _validate_inputs(task, domain)
    _validate_step(step)
    collection = _get_collection()
    sig = _action_signature(step)
    key = _mongo_safe_key(sig)

    # Only update existing task nodes — never create new ones from agent step reports.
    # Ghost nodes were caused by upsert=True here; store_trace owns node creation.
    collection.update_one(
        {"task": task, "domain": domain},
        {
            "$inc": {
                f"_step_counts.{key}.attempts": 1,
                f"_step_counts.{key}.successes": 1 if step.success else 0,
            },
            "$set": {f"_step_counts.{key}.signature": sig},
        },
        upsert=False,
    )

    _fire_event({
        "type": "step_recorded",
        "task": task,
        "domain": domain,
        "action": step.action,
        "target": step.target,
        "success": step.success,
    })


def store_trace(
    task: str,
    domain: str,
    trace: list[StepData],
    success: bool,
    path_update_allowed: bool = True,
    run_metrics: dict[str, Any] | None = None,
) -> None:
    """Process a completed run trace and update the task node."""
    _validate_inputs(task, domain)
    if not trace:
        raise ValueError("trace must be a non-empty list")
    collection = _get_collection()
    embedding = embed_task(task)
    now = datetime.now(timezone.utc)

    # Ensure the document exists.
    collection.update_one(
        {"task": task, "domain": domain},
        {
            "$setOnInsert": {
                "task": task,
                "domain": domain,
                "task_embedding": embedding,
                "run_count": 0,
                "confidence": 0.0,
                "execution_confidence": 0.0,
                "contract_confidence": 0.0,
                "optimal_actions": [],
                "_step_counts": {},
                "_success_count": 0,
                "created_at": now,
                "_execution_success_count": 0,
                "_contract_success_count": 0,
                "_metrics": {
                    "success_runs": 0,
                    "success_steps_sum": 0,
                    "success_duration_sum": 0.0,
                    "weight_sum": 0.0,
                },
            },
            "$set": {"updated_at": now},
        },
        upsert=True,
    )

    existing_doc = collection.find_one({"task": task, "domain": domain}) or {}
    existing_metrics = existing_doc.get("_metrics", {})
    prev_success_runs = int(existing_metrics.get("success_runs", 0) or 0)
    prev_steps_sum = float(existing_metrics.get("success_steps_sum", 0.0) or 0.0)
    prev_duration_sum = float(existing_metrics.get("success_duration_sum", 0.0) or 0.0)

    run_steps = int((run_metrics or {}).get("steps", len(trace)) or len(trace))
    run_duration_s = float((run_metrics or {}).get("duration_s", 0.0) or 0.0)

    if prev_success_runs > 0:
        avg_steps = prev_steps_sum / prev_success_runs
        avg_duration = prev_duration_sum / prev_success_runs if prev_duration_sum > 0 else 0.0
    else:
        avg_steps = float(run_steps)
        avg_duration = run_duration_s

    # Reward successful runs that complete with fewer steps and lower latency.
    # Use non-linear step weighting so low-step runs move confidence/path quality
    # more than marginal speed-only improvements.
    step_ratio = avg_steps / max(run_steps, 1) if run_steps > 0 else 1.0
    step_ratio = _clamp(step_ratio, 0.6, 1.8)
    step_score = step_ratio ** 1.8  # non-linear emphasis on lower-step runs

    speed_ratio = 1.0
    if run_duration_s > 0.0 and avg_duration > 0.0:
        speed_ratio = avg_duration / run_duration_s
    speed_ratio = _clamp(speed_ratio, 0.75, 1.35)
    speed_score = speed_ratio ** 1.2

    # Dominant signal is steps, secondary is speed.
    run_weight = round(_clamp(0.2 + 0.6 * step_score + 0.2 * speed_score, 0.3, 1.9), 3)

    # Increment run counters.
    inc_ops: dict[str, Any] = {"run_count": 1}
    set_ops: dict[str, str] = {}
    execution_success = bool((run_metrics or {}).get("execution_success", success))
    contract_pass = bool((run_metrics or {}).get("contract_pass", success))

    if execution_success:
        inc_ops["_execution_success_count"] = 1
    if contract_pass:
        inc_ops["_contract_success_count"] = 1

    if success:
        inc_ops["_success_count"] = 1
        inc_ops["_metrics.success_runs"] = 1
        inc_ops["_metrics.success_steps_sum"] = run_steps
        inc_ops["_metrics.weight_sum"] = run_weight
        if run_duration_s > 0.0:
            inc_ops["_metrics.success_duration_sum"] = run_duration_s
        for step in trace:
            sig = _action_signature(step)
            key = _mongo_safe_key(sig)
            inc_ops[f"_step_counts.{key}.attempts"] = 1
            inc_ops[f"_step_counts.{key}.successes"] = 1 if step.success else 0
            if path_update_allowed:
                inc_ops[f"_step_counts.{key}.weighted_success"] = run_weight if step.success else 0.0
            set_ops[f"_step_counts.{key}.signature"] = sig

    update_doc: dict[str, Any] = {"$inc": inc_ops}
    if set_ops:
        update_doc["$set"] = set_ops
    collection.update_one({"task": task, "domain": domain}, update_doc)

    # Persist latest run-level diagnostics for observability and benchmark joins.
    metrics_update = {
        "_last_run.path_update_allowed": bool(path_update_allowed),
        "_last_run.contract_pass": bool((run_metrics or {}).get("contract_pass", True)),
        "_last_run.schema_pass": bool((run_metrics or {}).get("schema_pass", True)),
        "_last_run.format_pass": bool((run_metrics or {}).get("format_pass", True)),
        "_last_run.scope_pass": bool((run_metrics or {}).get("scope_pass", True)),
        "_last_run.contract_failure_reason": str((run_metrics or {}).get("contract_failure_reason", "") or ""),
        "_last_run.agent_steps": int((run_metrics or {}).get("agent_steps", 0) or 0),
        "_last_run.laminar_tool_steps": int((run_metrics or {}).get("laminar_tool_steps", 0) or 0),
        "_last_run.pipeline_steps_total": int((run_metrics or {}).get("pipeline_steps_total", 0) or 0),
        "_last_run.captcha_events": int((run_metrics or {}).get("captcha_events", 0) or 0),
        "_last_run.interstitial_events": int((run_metrics or {}).get("interstitial_events", 0) or 0),
        "_last_run.modal_recovery_count": int((run_metrics or {}).get("modal_recovery_count", 0) or 0),
        "_last_run.efficiency_reason": str((run_metrics or {}).get("efficiency_reason", "") or ""),
        "_last_run.milestone_violations": int((run_metrics or {}).get("milestone_violations", 0) or 0),
        "_last_run.phase_revisits": int((run_metrics or {}).get("phase_revisits", 0) or 0),
        "_last_run.milestone_steps_observed": int((run_metrics or {}).get("milestone_steps_observed", 0) or 0),
    }
    collection.update_one({"task": task, "domain": domain}, {"$set": metrics_update})

    # Recompute optimal path and confidence from accumulated counts.
    _recompute_optimal_path(collection, task, domain)

    # Fetch updated doc for event data.
    updated = collection.find_one(
        {"task": task, "domain": domain},
        {"confidence": 1, "run_count": 1, "_id": 0},
    )

    # Append history snapshot.
    collection.update_one(
        {"task": task, "domain": domain},
        {
            "$push": {
                "_history": {
                    "timestamp": now,
                    "confidence": updated["confidence"] if updated else 0.0,
                    "run_count": updated["run_count"] if updated else 0,
                }
            }
        },
    )

    _fire_event({
        "type": "node_updated" if updated and updated.get("run_count", 0) > 1 else "node_added",
        "task": task,
        "domain": domain,
        "confidence": updated["confidence"] if updated else 0.0,
        "run_count": updated["run_count"] if updated else 0,
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _action_signature(step: StepData, include_value: bool = False) -> str:
    """Build a step signature string.

    include_value=False (default)  → generic key for _step_counts and optimal_actions.
                                     e.g. "type:search_input"
                                     Enables cross-item transfer without hardcoding item names.
    include_value=True             → optional granular key for diagnostics.
                                     e.g. "type:search_input:macbook"
    """
    base = f"{step.action}:{step.target}"
    if include_value and step.value:
        return f"{base}:{step.value}"
    return base


def _strip_signature_value(signature: str) -> str:
    """Strip the value portion from a stored signature for generic hints.

    "type:search_input:macbook" → "type:search_input"
    "click:add_to_cart"         → "click:add_to_cart" (no change)
    """
    parts = signature.split(":")
    if len(parts) > 2:
        return ":".join(parts[:2])
    return signature


def _mongo_safe_key(signature: str) -> str:
    """Convert a signature into a Mongo-safe field key for dotted update paths."""
    # Dots and leading-dollar segments are invalid in path keys.
    safe = signature.replace(".", "\uFF0E").replace("$", "\uFF04")
    # Collapse accidental empty segments if input has repeated separators.
    safe = re.sub(r"\uFF0E{2,}", "\uFF0E", safe)
    return safe


def _mongo_unsafe_key(key: str) -> str:
    """Best-effort reverse transform for legacy docs without stored signature."""
    return key.replace("\uFF0E", ".").replace("\uFF04", "$")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _recompute_optimal_path(collection, task: str, domain: str) -> None:
    """Rebuild optimal_actions, step_traces, and confidence from _step_counts."""
    doc = collection.find_one({"task": task, "domain": domain})
    if not doc:
        return

    run_count = doc.get("run_count", 0)
    success_count = doc.get("_success_count", 0)
    execution_success_count = doc.get("_execution_success_count", success_count)
    contract_success_count = doc.get("_contract_success_count", success_count)
    step_counts: dict[str, dict] = doc.get("_step_counts", {})

    if run_count == 0:
        return

    # Build step_traces sorted by quality score descending.
    step_traces = []
    for sig, counts in step_counts.items():
        action_sig = counts.get("signature") or _mongo_unsafe_key(sig)
        attempts = counts.get("attempts", 0)
        successes = counts.get("successes", 0)
        weighted_success = counts.get("weighted_success", successes)
        rate = successes / attempts if attempts > 0 else 0.0
        weighted_rate = weighted_success / max(success_count, 1)
        quality_score = 0.7 * rate + 0.3 * min(1.0, weighted_rate)
        step_traces.append({
            "action_signature": action_sig,
            "attempt_count": attempts,
            "success_rate": round(rate, 3),
            "weighted_success": round(weighted_success, 3),
            "weighted_rate": round(weighted_rate, 3),
            "quality_score": round(quality_score, 3),
        })

    step_traces.sort(key=lambda s: (-s["quality_score"], -s["success_rate"], -s["attempt_count"]))

    # Optimal actions: frequent and high-quality among successful runs.
    # Signatures are stored with values (e.g. "type:search_input:macbook")
    # but optimal_actions strips the value so hints are generic across items.
    # This enables cross-item transfer: "type:search_input" tells the agent
    # to use the search box without hardcoding which product.
    min_frequency = 0.5
    min_success_rate = 0.65
    min_quality_score = 0.72
    optimal_actions_raw = [
        s["action_signature"]
        for s in step_traces
        if s["attempt_count"] / max(success_count, 1) >= min_frequency
        and s["success_rate"] >= min_success_rate
        and s["quality_score"] >= min_quality_score
    ]
    # Strip product-specific values → "type:search_input:macbook" → "type:search_input"
    optimal_actions = list(dict.fromkeys(
        _strip_signature_value(sig) for sig in optimal_actions_raw
    ))

    # Confidence: conservative, multiplicative scaling by volume.
    # This avoids an additive "free floor" at low success rates and keeps
    # confidence <= success_rate while sample size is still small.
    success_rate = success_count / run_count
    volume_factor = min(1.0, run_count / 20)  # ramps up over first 20 runs
    base_confidence = success_rate * (0.5 + 0.5 * volume_factor)
    if step_traces:
        top_n = step_traces[: min(5, len(step_traces))]
        quality_factor = sum(s["quality_score"] for s in top_n) / len(top_n)
    else:
        quality_factor = 1.0
    confidence = round(min(0.99, base_confidence * (0.85 + 0.15 * quality_factor)), 3)
    execution_success_rate = execution_success_count / run_count if run_count else 0.0
    contract_success_rate = contract_success_count / run_count if run_count else 0.0
    execution_confidence = round(min(0.99, execution_success_rate * (0.5 + 0.5 * volume_factor)), 3)
    contract_confidence = round(min(0.99, contract_success_rate * (0.5 + 0.5 * volume_factor)), 3)

    collection.update_one(
        {"task": task, "domain": domain},
        {
            "$set": {
                "confidence": confidence,
                "execution_confidence": execution_confidence,
                "contract_confidence": contract_confidence,
                "optimal_actions": optimal_actions,
                "step_traces": step_traces,
            }
        },
    )
