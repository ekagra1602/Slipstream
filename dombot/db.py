"""DomBot data facade.

Exposes a stable contract for tool/pipeline code:
    query_context(task, domain) -> OptimalPath | None
    store_step(task, domain, step)  -> None
    store_trace(task, domain, trace, success) -> None

Backends:
  - MongoDB (db/db.py) when available
  - In-memory mock fallback for demos/tests

Set DOMBOT_DB_BACKEND to force behavior:
  - "mongo": require Mongo backend
  - "mock": always use in-memory backend
  - "auto" (default): use Mongo when import/env is ready, otherwise fallback to mock
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from dombot.domain_utils import canonicalize_domain


@dataclass
class OptimalPath:
    task: str
    domain: str
    confidence: float
    run_count: int
    optimal_actions: list[str] = field(default_factory=list)
    successful_results: list[str] = field(default_factory=list)
    last_run: dict[str, Any] = field(default_factory=dict)
    execution_confidence: float = 0.0
    contract_confidence: float = 0.0


# ---------------------------------------------------------------------------
# In-memory store (replaced by MongoDB in production)
# ---------------------------------------------------------------------------

# task_nodes: keyed by (task, domain) → OptimalPath
_task_nodes: dict[tuple[str, str], OptimalPath] = {}

# step_log: list of all reported steps (append-only)
_step_log: list[dict] = []

# trace_log: list of all completed traces
_trace_log: list[dict] = []

_backend_name: str | None = None
_real_db_module: Any | None = None


def _canon_domain(domain: str) -> str:
    normalized = canonicalize_domain(domain)
    if normalized:
        return normalized
    return (domain or "").strip().lower()


def _normalize_task_text(task: str) -> str:
    text = " ".join((task or "").strip().lower().split())
    return text


def _resolve_backend() -> tuple[str, Any | None]:
    global _backend_name, _real_db_module
    if _backend_name is not None:
        return _backend_name, _real_db_module

    mode = os.getenv("DOMBOT_DB_BACKEND", "auto").strip().lower()
    if mode not in {"auto", "mongo", "mock"}:
        mode = "auto"

    if mode == "mock":
        _backend_name = "mock"
        _real_db_module = None
        return _backend_name, _real_db_module

    try:
        from db import db as real_db

        _backend_name = "mongo"
        _real_db_module = real_db
        return _backend_name, _real_db_module
    except Exception as exc:
        if mode == "mongo":
            raise RuntimeError(
                "DOMBOT_DB_BACKEND='mongo' but Mongo backend could not be loaded"
            ) from exc
        _backend_name = "mock"
        _real_db_module = None
        return _backend_name, _real_db_module


def get_backend_name() -> str:
    """Return the active backend name: 'mongo' or 'mock'."""
    backend, _ = _resolve_backend()
    return backend


def seed_task_node(
    task: str,
    domain: str,
    confidence: float,
    run_count: int,
    optimal_actions: list[str],
) -> OptimalPath:
    """Seed the in-memory store with a task node. For testing / demo use."""
    canonical_domain = _canon_domain(domain)
    node = OptimalPath(
        task=task,
        domain=canonical_domain,
        confidence=confidence,
        run_count=run_count,
        optimal_actions=optimal_actions,
    )
    _task_nodes[(task, canonical_domain)] = node
    return node


def clear_store() -> None:
    """Reset all in-memory data."""
    _task_nodes.clear()
    _step_log.clear()
    _trace_log.clear()


# ---------------------------------------------------------------------------
# Shared contract functions
# ---------------------------------------------------------------------------

def query_context(task: str, domain: str) -> OptimalPath | None:
    """Return optimal path for a similar task, or None if no prior data."""
    task = _normalize_task_text(task)
    canonical_domain = _canon_domain(domain)
    backend, real_db = _resolve_backend()
    if backend == "mongo":
        result = real_db.query_context(task, canonical_domain)
        if result is None:
            return None
        return OptimalPath(
            task=result.task,
            domain=_canon_domain(result.domain),
            confidence=result.confidence,
            run_count=result.run_count,
            optimal_actions=list(result.optimal_actions),
            successful_results=list(getattr(result, "successful_results", []) or []),
            last_run=dict(getattr(result, "last_run", {}) or {}),
            execution_confidence=float(getattr(result, "execution_confidence", 0.0) or 0.0),
            contract_confidence=float(getattr(result, "contract_confidence", 0.0) or 0.0),
        )

    # Mock backend behavior below.
    # Exact match first
    if (task, canonical_domain) in _task_nodes:
        return _task_nodes[(task, canonical_domain)]

    # Simple substring fallback to simulate vector similarity
    for (stored_task, stored_domain), node in _task_nodes.items():
        if stored_domain == canonical_domain and (
            stored_task.lower() in task.lower() or task.lower() in stored_task.lower()
        ):
            return node

    return None


def store_step(task: str, domain: str, step: dict) -> None:
    """Store a single step result."""
    task = _normalize_task_text(task)
    canonical_domain = _canon_domain(domain)
    backend, real_db = _resolve_backend()
    if backend == "mongo":
        real_db.store_step(
            task=task,
            domain=canonical_domain,
            step=real_db.StepData(
                action=step.get("action", ""),
                target=step.get("target", ""),
                value=step.get("value"),
                success=bool(step.get("success", True)),
            ),
        )
        return

    # Mock backend behavior below.
    entry = {"task": task, "domain": canonical_domain, **step}
    _step_log.append(entry)


def store_trace(
    task: str,
    domain: str,
    trace: list[dict],
    success: bool,
    path_update_allowed: bool = True,
    run_metrics: dict | None = None,
) -> None:
    """Store the full trace after a run completes."""
    task = _normalize_task_text(task)
    canonical_domain = _canon_domain(domain)
    backend, real_db = _resolve_backend()
    if backend == "mongo":
        real_db.store_trace(
            task=task,
            domain=canonical_domain,
            trace=[
                real_db.StepData(
                    action=s.get("action", ""),
                    target=s.get("target", ""),
                    value=s.get("value"),
                    success=bool(s.get("success", True)),
                )
                for s in trace
            ],
            success=success,
            path_update_allowed=path_update_allowed,
            run_metrics=run_metrics,
        )
        return

    # Mock backend behavior below.
    entry = {
        "task": task,
        "domain": canonical_domain,
        "steps": trace,
        "success": success,
        "path_update_allowed": bool(path_update_allowed),
        "run_metrics": run_metrics or {},
    }
    _trace_log.append(entry)


# ---------------------------------------------------------------------------
# Accessors for test verification
# ---------------------------------------------------------------------------

def get_step_log() -> list[dict]:
    return list(_step_log)


def get_trace_log() -> list[dict]:
    return list(_trace_log)


def get_task_nodes() -> dict[tuple[str, str], OptimalPath]:
    return dict(_task_nodes)
