from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pymongo import MongoClient

from db.config import (
    COLLECTION_TASK_NODES,
    DB_NAME,
    MONGODB_URI,
    VECTOR_INDEX_NAME,
)
from db.embeddings import embed_task

_client: MongoClient | None = None


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
                "run_count": 1,
                "optimal_actions": 1,
                "step_traces": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    results = list(collection.aggregate(pipeline))
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
    )


def store_step(task: str, domain: str, step: StepData) -> None:
    """Append a single step observation to the task node's step_traces."""
    _validate_inputs(task, domain)
    _validate_step(step)
    collection = _get_collection()
    sig = _action_signature(step)

    # Upsert the task node, increment attempt_count for this step signature.
    collection.update_one(
        {"task": task, "domain": domain},
        {
            "$setOnInsert": {
                "task": task,
                "domain": domain,
                "task_embedding": embed_task(task),
                "run_count": 0,
                "confidence": 0.0,
                "optimal_actions": [],
            },
            "$inc": {
                f"_step_counts.{sig}.attempts": 1,
                f"_step_counts.{sig}.successes": 1 if step.success else 0,
            },
        },
        upsert=True,
    )


def store_trace(task: str, domain: str, trace: list[StepData], success: bool) -> None:
    """Process a completed run trace and update the task node."""
    _validate_inputs(task, domain)
    if not trace:
        raise ValueError("trace must be a non-empty list")
    collection = _get_collection()
    embedding = embed_task(task)

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
                "optimal_actions": [],
                "_step_counts": {},
                "_success_count": 0,
            },
        },
        upsert=True,
    )

    # Increment run counters.
    inc_ops: dict[str, int] = {"run_count": 1}
    if success:
        inc_ops["_success_count"] = 1
        for step in trace:
            sig = _action_signature(step)
            inc_ops[f"_step_counts.{sig}.attempts"] = 1
            inc_ops[f"_step_counts.{sig}.successes"] = 1 if step.success else 0

    collection.update_one(
        {"task": task, "domain": domain},
        {"$inc": inc_ops},
    )

    # Recompute optimal path and confidence from accumulated counts.
    _recompute_optimal_path(collection, task, domain)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _action_signature(step: StepData) -> str:
    if step.value:
        return f"{step.action}:{step.target}:{step.value}"
    return f"{step.action}:{step.target}"


def _recompute_optimal_path(collection, task: str, domain: str) -> None:
    """Rebuild optimal_actions, step_traces, and confidence from _step_counts."""
    doc = collection.find_one({"task": task, "domain": domain})
    if not doc:
        return

    run_count = doc.get("run_count", 0)
    success_count = doc.get("_success_count", 0)
    step_counts: dict[str, dict] = doc.get("_step_counts", {})

    if run_count == 0:
        return

    # Build step_traces sorted by success rate descending.
    step_traces = []
    for sig, counts in step_counts.items():
        attempts = counts.get("attempts", 0)
        successes = counts.get("successes", 0)
        rate = successes / attempts if attempts > 0 else 0.0
        step_traces.append({
            "action_signature": sig,
            "attempt_count": attempts,
            "success_rate": round(rate, 3),
        })

    step_traces.sort(key=lambda s: (-s["success_rate"], -s["attempt_count"]))

    # Optimal actions: steps that appear in >50% of successful runs with >70% success rate.
    min_frequency = 0.5
    min_success_rate = 0.7
    optimal_actions = [
        s["action_signature"]
        for s in step_traces
        if s["attempt_count"] / max(success_count, 1) >= min_frequency
        and s["success_rate"] >= min_success_rate
    ]

    # Confidence: blend of success rate and run volume, capped at 0.99.
    success_rate = success_count / run_count
    volume_factor = min(1.0, run_count / 10)  # ramps up over first 10 runs
    confidence = round(min(0.99, success_rate * 0.7 + volume_factor * 0.3), 3)

    collection.update_one(
        {"task": task, "domain": domain},
        {
            "$set": {
                "confidence": confidence,
                "optimal_actions": optimal_actions,
                "step_traces": step_traces,
            }
        },
    )
