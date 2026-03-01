"""Mock DB layer — in-memory placeholder until Person 2 (Eric) implements the real MongoDB backend.

Shared contract:
    query_context(task, domain) -> OptimalPath | None
    store_step(task, domain, step)  -> None
    store_trace(task, domain, trace, success) -> None

The in-memory store allows full round-trip testing (seed → query → report → verify)
without MongoDB. Person 2 replaces the implementations, keeps the same signatures.
"""

from dataclasses import dataclass, field


@dataclass
class OptimalPath:
    task: str
    domain: str
    confidence: float
    run_count: int
    optimal_actions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# In-memory store (replaced by MongoDB in production)
# ---------------------------------------------------------------------------

# task_nodes: keyed by (task, domain) → OptimalPath
_task_nodes: dict[tuple[str, str], OptimalPath] = {}

# step_log: list of all reported steps (append-only)
_step_log: list[dict] = []

# trace_log: list of all completed traces
_trace_log: list[dict] = []


def seed_task_node(
    task: str,
    domain: str,
    confidence: float,
    run_count: int,
    optimal_actions: list[str],
) -> OptimalPath:
    """Seed the in-memory store with a task node. For testing / demo use."""
    node = OptimalPath(
        task=task,
        domain=domain,
        confidence=confidence,
        run_count=run_count,
        optimal_actions=optimal_actions,
    )
    _task_nodes[(task, domain)] = node
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
    """Return optimal path for a similar task, or None if no prior data.

    TODO (Person 2): Replace with MongoDB $vectorSearch on task embeddings.
    The real implementation will find the closest task by vector similarity
    rather than exact (task, domain) match.
    """
    # Exact match first
    if (task, domain) in _task_nodes:
        return _task_nodes[(task, domain)]

    # Simple substring fallback to simulate vector similarity
    for (stored_task, stored_domain), node in _task_nodes.items():
        if stored_domain == domain and (
            stored_task.lower() in task.lower() or task.lower() in stored_task.lower()
        ):
            return node

    return None


def store_step(task: str, domain: str, step: dict) -> None:
    """Store a single step result.

    TODO (Person 2): Replace with MongoDB insert into step_traces array.
    """
    entry = {"task": task, "domain": domain, **step}
    _step_log.append(entry)


def store_trace(task: str, domain: str, trace: list[dict], success: bool) -> None:
    """Store the full trace after a run completes.

    TODO (Person 2): Replace with MongoDB upsert — update confidence,
    run_count, and merge optimal_actions on the task node.
    """
    entry = {"task": task, "domain": domain, "steps": trace, "success": success}
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
