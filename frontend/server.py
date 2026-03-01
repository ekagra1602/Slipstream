#!/usr/bin/env python3
"""FastAPI backend: REST endpoints, WebSocket, and static file serving."""
from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import logging
import os
import random
import re
import sys
import urllib.error
import urllib.request
import uuid
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

# Allow imports from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.db import _get_collection, register_callback  # noqa: E402
from dombot.convex_http import convex_query, is_convex_configured  # noqa: E402
from dombot.domain_utils import canonicalize_domain  # noqa: E402
from dombot.trace_ingest import ingest_trace  # noqa: E402
from frontend.demo_seed import DEFAULT_DOMAINS, generate_demo_docs  # noqa: E402

app = FastAPI(title="Slipstream Knowledge Graph")
logger = logging.getLogger("frontend.server")

STATIC_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, data: dict):
        for ws in list(self.connections):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()

# Bridge sync db callbacks to async WebSocket broadcasts.
_loop: asyncio.AbstractEventLoop | None = None
_pending_events: list[dict] = []


# Convex signal poller state.
_CONVEX_POLL_INTERVAL_SEC = 0.4
_CONVEX_RECENT_LIMIT = 50
_CONVEX_SEEN_MAX = 5000

_convex_signal_task: asyncio.Task | None = None
_convex_last_watermark: tuple[int, str] | None = None
_convex_seen_ids: set[str] = set()
_convex_seen_order: deque[str] = deque()


def _on_db_event(event: dict):
    """Called synchronously from db.py — schedule async broadcast."""
    if _loop and _loop.is_running():
        _loop.call_soon_threadsafe(asyncio.ensure_future, manager.broadcast(event))
    else:
        _pending_events.append(event)


register_callback(_on_db_event)


def _convex_run_key(run: dict) -> tuple[int, str]:
    timestamp_ms = int(run.get("timestampMs") or 0)
    trace_id = str(run.get("traceId") or "")
    return (timestamp_ms, trace_id)


def _remember_convex_trace_id(trace_id: str) -> None:
    if not trace_id or trace_id in _convex_seen_ids:
        return

    _convex_seen_ids.add(trace_id)
    _convex_seen_order.append(trace_id)

    while len(_convex_seen_order) > _CONVEX_SEEN_MAX:
        old_id = _convex_seen_order.popleft()
        _convex_seen_ids.discard(old_id)


def _convex_run_to_event(run: dict) -> dict:
    return {
        "type": "trace_arrived",
        "trace_id": str(run.get("traceId") or ""),
        "task": str(run.get("task") or ""),
        "domain": str(run.get("domain") or ""),
        "success": bool(run.get("success", False)),
        "partial": bool(run.get("partial", False)),
        "step_count": int(run.get("stepCount") or 0),
        "timestamp_ms": int(run.get("timestampMs") or 0),
        "signal_source": "convex",
    }


async def _poll_convex_runs_loop() -> None:
    """Poll Convex for newly inserted runs and fan-out lightweight events."""
    global _convex_last_watermark

    while True:
        try:
            runs = convex_query("runs:listRecentRuns", {"limit": _CONVEX_RECENT_LIMIT})
            if not isinstance(runs, list):
                runs = []

            normalized_runs = [run for run in runs if isinstance(run, dict)]
            normalized_runs.sort(key=_convex_run_key)

            # Bootstrap watermark to "now" set; don't replay historical runs.
            if _convex_last_watermark is None:
                if normalized_runs:
                    _convex_last_watermark = _convex_run_key(normalized_runs[-1])
            else:
                for run in normalized_runs:
                    key = _convex_run_key(run)
                    trace_id = str(run.get("traceId") or "")

                    if trace_id and trace_id in _convex_seen_ids:
                        continue
                    if key <= _convex_last_watermark:
                        continue

                    await manager.broadcast(_convex_run_to_event(run))
                    _remember_convex_trace_id(trace_id)

                if normalized_runs:
                    latest = _convex_run_key(normalized_runs[-1])
                    if latest > _convex_last_watermark:
                        _convex_last_watermark = latest

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Convex signal poll failed", exc_info=True)

        await asyncio.sleep(_CONVEX_POLL_INTERVAL_SEC)


@app.on_event("startup")
async def _startup_tasks():
    global _loop, _convex_signal_task
    _loop = asyncio.get_running_loop()

    if _pending_events:
        for event in list(_pending_events):
            await manager.broadcast(event)
        _pending_events.clear()

    if is_convex_configured():
        _convex_signal_task = asyncio.create_task(_poll_convex_runs_loop())
        logger.info("Convex signal poller enabled")
    else:
        logger.info("Convex signal poller disabled (CONVEX_URL missing)")


@app.on_event("shutdown")
async def _shutdown_tasks():
    global _auto_simulate_task, _convex_signal_task

    if _auto_simulate_task and not _auto_simulate_task.done():
        _auto_simulate_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _auto_simulate_task
    _auto_simulate_task = None

    if _convex_signal_task and not _convex_signal_task.done():
        _convex_signal_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _convex_signal_task
    _convex_signal_task = None


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------


def _normalize_domain(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    return canonicalize_domain(value) or value


def _build_graph_from_docs(docs: list[dict], include_cold_tasks: bool) -> dict:
    nodes = []
    links = []
    domain_set: dict[str, dict] = {}

    for doc in docs:
        task_id = str(doc["_id"])
        task = str(doc.get("task") or "").strip()
        domain = _normalize_domain(doc.get("domain"))
        confidence = float(doc.get("confidence", 0.0) or 0.0)
        run_count = int(doc.get("run_count", 0) or 0)

        if not task or not domain:
            continue
        if not include_cold_tasks and run_count <= 0:
            continue

        nodes.append(
            {
                "id": task_id,
                "type": "task",
                "task": task,
                "domain": domain,
                "confidence": confidence,
                "run_count": run_count,
                "optimal_actions": doc.get("optimal_actions", []),
                "step_traces": doc.get("step_traces", []),
            }
        )

        if domain not in domain_set:
            domain_set[domain] = {
                "total_confidence": 0.0,
                "total_runs": 0,
                "count": 0,
                "task_ids": [],
            }
        domain_set[domain]["total_confidence"] += confidence
        domain_set[domain]["total_runs"] += run_count
        domain_set[domain]["count"] += 1
        domain_set[domain]["task_ids"].append(task_id)

    for domain, stats in domain_set.items():
        domain_id = f"domain:{domain}"
        avg_conf = (
            stats["total_confidence"] / stats["count"] if stats["count"] else 0
        )
        nodes.append(
            {
                "id": domain_id,
                "type": "domain",
                "domain": domain,
                "task_count": stats["count"],
                "total_runs": stats["total_runs"],
                "avg_confidence": round(avg_conf, 3),
            }
        )
        for tid in stats["task_ids"]:
            links.append({"source": domain_id, "target": tid, "type": "hub"})

    all_task_actions = {}
    for node in nodes:
        if node.get("type") != "task":
            continue
        sigs = set()
        for action in node.get("optimal_actions", []):
            parts = action.split(":")
            if parts:
                sigs.add(parts[0] + ":" + parts[1] if len(parts) > 1 else parts[0])
        all_task_actions[node["id"]] = {"sigs": sigs, "domain": node["domain"]}

    tid_list = list(all_task_actions.keys())
    for i in range(len(tid_list)):
        for j in range(i + 1, len(tid_list)):
            a = all_task_actions[tid_list[i]]
            b = all_task_actions[tid_list[j]]
            shared = a["sigs"] & b["sigs"]
            if len(shared) >= 2:
                links.append(
                    {
                        "source": tid_list[i],
                        "target": tid_list[j],
                        "type": "cross",
                        "strength": len(shared),
                    }
                )

    for i, (d1, s1) in enumerate(domain_set.items()):
        for d2, s2 in list(domain_set.items())[i + 1 :]:
            d1_tids = set(s1["task_ids"])
            d2_tids = set(s2["task_ids"])
            has_cross_link = any(
                link_item
                for link_item in links
                if link_item.get("type") == "cross"
                and (
                    (link_item["source"] in d1_tids and link_item["target"] in d2_tids)
                    or (
                        link_item["source"] in d2_tids and link_item["target"] in d1_tids
                    )
                )
            )
            if has_cross_link:
                links.append(
                    {
                        "source": f"domain:{d1}",
                        "target": f"domain:{d2}",
                        "type": "cross",
                    }
                )

    return {"nodes": nodes, "links": links}


def _compute_graph_stats() -> dict:
    collection = _get_collection()
    docs = list(collection.find({}, {"domain": 1, "run_count": 1}))

    domain_values: list[str] = []
    non_canonical = set()
    task_nodes = 0
    total_runs = 0
    zero_run_tasks = 0

    for doc in docs:
        task_nodes += 1
        raw_domain = str(doc.get("domain") or "").strip().lower()
        canonical = _normalize_domain(raw_domain)
        if canonical:
            domain_values.append(canonical)

        if raw_domain and canonical and raw_domain != canonical:
            non_canonical.add(raw_domain)
        if raw_domain.startswith("www."):
            non_canonical.add(raw_domain)

        run_count = int(doc.get("run_count", 0) or 0)
        total_runs += max(0, run_count)
        if run_count <= 0:
            zero_run_tasks += 1

    return {
        "taskNodes": task_nodes,
        "domainNodes": len(set(domain_values)),
        "totalRuns": total_runs,
        "zeroRunTasks": zero_run_tasks,
        "nonCanonicalDomains": sorted(non_canonical),
    }


def _reseed_demo_graph(
    *,
    domain_count: int,
    tasks_per_domain: int,
    include_history: bool,
) -> dict:
    collection = _get_collection()
    docs, summary = generate_demo_docs(
        domain_count=domain_count,
        tasks_per_domain=tasks_per_domain,
        include_history=include_history,
    )

    collection.delete_many({})
    if docs:
        collection.insert_many(docs)

    return {
        "status": "ok",
        "insertedNodes": summary.inserted_nodes,
        "insertedDomains": summary.inserted_domains,
        "totalRuns": summary.total_runs,
        "warnings": summary.warnings,
    }


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/api/graph")
def get_graph(
    include_cold_tasks: bool = Query(
        default=False,
        description="Include tasks with run_count <= 0 in graph payload.",
    )
):
    """Return full graph data for initial load."""
    collection = _get_collection()
    docs = list(
        collection.find(
            {},
            {
                "task_embedding": 0,
                "_step_counts": 0,
                "_success_count": 0,
                "_history": 0,
            },
        )
    )
    return _build_graph_from_docs(docs, include_cold_tasks=include_cold_tasks)


@app.get("/api/graph/history")
def get_graph_history():
    """Return timestamped events for time-slider."""
    collection = _get_collection()
    docs = list(
        collection.find(
            {},
            {
                "task": 1,
                "domain": 1,
                "confidence": 1,
                "run_count": 1,
                "created_at": 1,
                "updated_at": 1,
                "_history": 1,
            },
        )
    )

    events = []
    for doc in docs:
        node_id = str(doc["_id"])
        created = doc.get("created_at")
        if created:
            events.append(
                {
                    "timestamp": created.isoformat(),
                    "type": "created",
                    "node_id": node_id,
                    "task": doc["task"],
                    "domain": _normalize_domain(doc.get("domain")),
                    "confidence": doc.get("confidence", 0),
                    "run_count": doc.get("run_count", 0),
                }
            )
        # Include history snapshots.
        for history in doc.get("_history", []):
            events.append(
                {
                    "timestamp": history["timestamp"].isoformat(),
                    "type": "updated",
                    "node_id": node_id,
                    "task": doc["task"],
                    "domain": _normalize_domain(doc.get("domain")),
                    "confidence": history.get("confidence", 0),
                    "run_count": history.get("run_count", 0),
                }
            )

    events.sort(key=lambda event: event["timestamp"])
    return {"events": events}


@app.get("/api/admin/graph/stats")
def get_graph_stats():
    """Return lightweight graph health stats for operator checks."""
    return _compute_graph_stats()


class DemoReseedPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: str = "full"
    domains: int = Field(default=10, ge=1, le=len(DEFAULT_DOMAINS))
    tasks_per_domain: int = Field(default=100, alias="tasksPerDomain", ge=1, le=200)
    include_history: bool = Field(default=True, alias="includeHistory")


@app.post("/api/admin/demo/reseed")
async def reseed_demo(payload: DemoReseedPayload):
    """Destructively reset task_nodes and seed deterministic demo topology."""
    if payload.mode != "full":
        raise HTTPException(status_code=400, detail="Only mode='full' is supported.")

    loop = asyncio.get_running_loop()
    reseed_fn = functools.partial(
        _reseed_demo_graph,
        domain_count=payload.domains,
        tasks_per_domain=payload.tasks_per_domain,
        include_history=payload.include_history,
    )
    result = await loop.run_in_executor(None, reseed_fn)
    return result


class TraceStepPayload(BaseModel):
    action: str = Field(min_length=1)
    target: str = Field(min_length=1)
    value: str | None = None
    success: bool = True


class TraceIngestPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    success: bool = True
    partial: bool = False
    steps: list[TraceStepPayload] = Field(min_length=1)
    trace_id: str | None = Field(default=None, alias="traceId")
    timestamp_ms: int | None = Field(default=None, alias="timestampMs")


# ---------------------------------------------------------------------------
# Simulate endpoint
# ---------------------------------------------------------------------------

SIMULATE_TASKS = [
    (
        "buy running shoes on walmart",
        "walmart.com",
        [
            ("type", "search_input", "running shoes"),
            ("click", "first_result", None),
            ("click", "add_to_cart", None),
        ],
    ),
    (
        "buy a monitor on amazon",
        "amazon.com",
        [
            ("type", "search_box", "4k monitor"),
            ("click", "first_result", None),
            ("click", "add_to_cart", None),
        ],
    ),
    (
        "search for restaurants on google",
        "google.com",
        [
            ("type", "search_input", "restaurants near me"),
            ("click", "search_button", None),
            ("click", "maps_result", None),
        ],
    ),
    (
        "fork a repository on github",
        "github.com",
        [
            ("type", "search_input", "react"),
            ("click", "first_repo", None),
            ("click", "fork_button", None),
        ],
    ),
    (
        "upload a video on youtube",
        "youtube.com",
        [
            ("click", "create_button", None),
            ("click", "upload_video", None),
            ("click", "select_file", None),
        ],
    ),
    (
        "bookmark a tweet on x",
        "x.com",
        [
            ("click", "explore_tab", None),
            ("click", "first_tweet", None),
            ("click", "bookmark_button", None),
        ],
    ),
    (
        "endorse a skill on linkedin",
        "linkedin.com",
        [
            ("type", "search_input", "Jane Doe"),
            ("click", "first_person_result", None),
            ("click", "endorse_skill_button", None),
        ],
    ),
    (
        "buy a tv on bestbuy",
        "bestbuy.com",
        [
            ("type", "search_input", "OLED TV"),
            ("click", "first_result", None),
            ("click", "add_to_cart", None),
        ],
    ),
    (
        "buy a gift card on target",
        "target.com",
        [
            ("type", "search_input", "gift card"),
            ("click", "first_result", None),
            ("click", "add_to_cart", None),
        ],
    ),
    (
        "buy a camera on ebay",
        "ebay.com",
        [
            ("type", "search_input", "mirrorless camera"),
            ("click", "first_result", None),
            ("click", "buy_now_button", None),
        ],
    ),
]

_auto_simulate_task: asyncio.Task | None = None


@app.post("/api/traces")
async def create_trace(payload: TraceIngestPayload):
    """Ingest a completed trace into Mongo + Convex side-channel."""
    loop = asyncio.get_running_loop()
    ingest_fn = functools.partial(
        ingest_trace,
        task=payload.task,
        domain=payload.domain,
        steps=[step.model_dump() for step in payload.steps],
        success=payload.success,
        partial=payload.partial,
        trace_id=payload.trace_id,
        timestamp_ms=payload.timestamp_ms,
    )
    result = await loop.run_in_executor(None, ingest_fn)

    return {
        "status": "ok",
        "trace_id": result["trace_id"],
        "task": result["task"],
        "domain": result["domain"],
    }


@app.post("/api/simulate")
async def simulate():
    """Trigger a fake agent run."""
    task_name, domain, raw_steps = random.choice(SIMULATE_TASKS)
    steps = [
        {"action": action, "target": target, "value": value, "success": True}
        for action, target, value in raw_steps
    ]

    # Run in thread to avoid blocking (db and Convex calls are sync).
    loop = asyncio.get_running_loop()
    ingest_fn = functools.partial(
        ingest_trace,
        task=task_name,
        domain=domain,
        steps=steps,
        success=True,
        partial=False,
    )
    result = await loop.run_in_executor(None, ingest_fn)

    return {
        "status": "ok",
        "task": task_name,
        "domain": domain,
        "trace_id": result["trace_id"],
    }


@app.post("/api/auto-simulate/{action}")
async def auto_simulate(action: str):
    """Start or stop auto-simulation."""
    global _auto_simulate_task

    if action == "start":
        if _auto_simulate_task and not _auto_simulate_task.done():
            return {"status": "already_running"}

        async def _run():
            while True:
                await asyncio.sleep(random.uniform(3, 5))
                await simulate()

        _auto_simulate_task = asyncio.create_task(_run())
        return {"status": "started"}

    if action == "stop":
        if _auto_simulate_task and not _auto_simulate_task.done():
            _auto_simulate_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _auto_simulate_task
        _auto_simulate_task = None
        return {"status": "stopped"}

    return {"status": "unknown_action"}


# ---------------------------------------------------------------------------
# Chat endpoint — An integration + local fallback
# ---------------------------------------------------------------------------

AN_API_KEY = os.getenv("AN_API_KEY", "").strip()
AN_AGENT_SLUG = (os.getenv("AN_AGENT_SLUG", "agent") or "agent").strip()
AN_CHAT_URL = f"https://relay.an.dev/v1/chat/{AN_AGENT_SLUG}"

_an_sandbox_id: str | None = None
_an_thread_id: str | None = None

_CHAT_SOURCE_VALUES = {"auto", "live", "demoMock"}
_QUERY_STOPWORDS = {
    "the",
    "a",
    "an",
    "for",
    "on",
    "in",
    "of",
    "to",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "what",
    "which",
    "how",
    "many",
    "much",
    "with",
    "about",
    "have",
    "has",
    "been",
    "agent",
    "agents",
    "task",
    "tasks",
    "run",
    "runs",
    "level",
    "confidence",
}


class ChatPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(min_length=1)
    source: str | None = "auto"
    demo_snapshot: dict | None = Field(default=None, alias="demoSnapshot")


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_chat_source(source: str | None) -> str:
    value = (source or "auto").strip()
    return value if value in _CHAT_SOURCE_VALUES else "auto"


def _task_rows_from_live_db() -> list[dict]:
    collection = _get_collection()
    docs = list(
        collection.find(
            {},
            {
                "task": 1,
                "domain": 1,
                "confidence": 1,
                "run_count": 1,
                "optimal_actions": 1,
            },
        )
    )

    rows: list[dict] = []
    for doc in docs:
        task = str(doc.get("task") or "").strip()
        domain = _normalize_domain(doc.get("domain"))
        if not task or not domain:
            continue

        rows.append(
            {
                "task": task,
                "domain": domain,
                "confidence": max(0.0, min(1.0, _coerce_float(doc.get("confidence")))),
                "run_count": max(0, _coerce_int(doc.get("run_count"))),
                "optimal_actions": list(doc.get("optimal_actions") or []),
            }
        )

    return rows


def _task_rows_from_demo_snapshot(snapshot: dict | None) -> list[dict]:
    if not isinstance(snapshot, dict):
        return []

    tasks = snapshot.get("tasks")
    if not isinstance(tasks, list):
        return []

    rows: list[dict] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        task = str(item.get("task") or "").strip()
        domain = _normalize_domain(item.get("domain"))
        if not task or not domain:
            continue

        rows.append(
            {
                "task": task,
                "domain": domain,
                "confidence": max(0.0, min(1.0, _coerce_float(item.get("confidence")))),
                "run_count": max(0, _coerce_int(item.get("run_count"))),
                "optimal_actions": list(item.get("optimal_actions") or []),
            }
        )

    return rows


def _build_metrics(task_rows: list[dict]) -> dict:
    total_runs = sum(max(0, _coerce_int(task.get("run_count"))) for task in task_rows)
    domain_rollups: dict[str, dict] = {}

    for task in task_rows:
        domain = str(task.get("domain") or "").strip().lower()
        if not domain:
            continue
        if domain not in domain_rollups:
            domain_rollups[domain] = {
                "domain": domain,
                "task_count": 0,
                "total_runs": 0,
                "confidence_sum": 0.0,
            }
        domain_rollups[domain]["task_count"] += 1
        domain_rollups[domain]["total_runs"] += max(
            0,
            _coerce_int(task.get("run_count")),
        )
        domain_rollups[domain]["confidence_sum"] += max(
            0.0,
            min(1.0, _coerce_float(task.get("confidence"))),
        )

    domains = []
    for rollup in domain_rollups.values():
        task_count = rollup["task_count"]
        avg_confidence = (
            (rollup["confidence_sum"] / task_count) if task_count > 0 else 0.0
        )
        domains.append(
            {
                "domain": rollup["domain"],
                "task_count": task_count,
                "total_runs": rollup["total_runs"],
                "avg_confidence": avg_confidence,
            }
        )

    domains.sort(key=lambda item: item["total_runs"], reverse=True)
    tasks_sorted = sorted(
        task_rows,
        key=lambda item: (
            _coerce_int(item.get("run_count")),
            _coerce_float(item.get("confidence")),
            str(item.get("task") or ""),
        ),
        reverse=True,
    )

    return {
        "total_tasks": len(task_rows),
        "total_domains": len(domains),
        "total_runs": total_runs,
        "domains": domains,
        "tasks": tasks_sorted,
    }


def _build_context_lines(metrics: dict, source_used: str) -> list[str]:
    lines = [
        "=== DATA CONTEXT ===",
        f"Source: {source_used}",
        f"Total tasks: {metrics['total_tasks']}",
        f"Total domains: {metrics['total_domains']}",
        f"Total runs: {metrics['total_runs']}",
        "",
        "--- Per-domain summary ---",
    ]

    for domain_item in metrics["domains"]:
        avg_pct = round(domain_item["avg_confidence"] * 100)
        lines.append(
            f"{domain_item['domain']}: {domain_item['task_count']} tasks, "
            f"{domain_item['total_runs']} runs, {avg_pct}% avg confidence"
        )

    lines.append("")
    lines.append("--- Tasks ---")
    for task in metrics["tasks"][:300]:
        conf_pct = round(_coerce_float(task.get("confidence")) * 100)
        action_list = list(task.get("optimal_actions") or [])
        action_preview = "; ".join(action_list[:5]) if action_list else "none"
        lines.append(
            f"- {task['task']} ({task['domain']}): {conf_pct}% confidence, "
            f"{task['run_count']} runs, optimal=[{action_preview}]"
        )

    return lines


def _append_convex_recent_runs(lines: list[str]) -> None:
    if not is_convex_configured():
        return

    try:
        runs = convex_query("runs:listRecentRuns", {"limit": 20})
    except Exception:
        logger.debug("Unable to query recent Convex runs for chat context", exc_info=True)
        return

    if not isinstance(runs, list) or not runs:
        return

    lines.append("")
    lines.append("--- Recent runs (Convex) ---")
    for run in runs[:15]:
        if not isinstance(run, dict):
            continue
        status = (
            "OK"
            if bool(run.get("success"))
            else "PARTIAL"
            if bool(run.get("partial"))
            else "FAIL"
        )
        lines.append(
            f"[{status}] {run.get('task', '?')} ({run.get('domain', '?')}) "
            f"— {_coerce_int(run.get('stepCount'))} steps"
        )


def _build_data_context(
    requested_source: str | None,
    demo_snapshot: dict | None,
) -> tuple[str, dict, str]:
    normalized_source = _normalize_chat_source(requested_source)
    demo_rows = _task_rows_from_demo_snapshot(demo_snapshot)

    if normalized_source == "demoMock":
        source_used = "demoMock"
        task_rows = demo_rows
    elif normalized_source == "live":
        source_used = "live"
        task_rows = _task_rows_from_live_db()
    else:
        if demo_rows:
            source_used = "demoMock"
            task_rows = demo_rows
        else:
            source_used = "live"
            task_rows = _task_rows_from_live_db()

    metrics = _build_metrics(task_rows)
    lines = _build_context_lines(metrics, source_used)

    if source_used == "live":
        _append_convex_recent_runs(lines)

    lines.append("=== END DATA CONTEXT ===")
    return source_used, metrics, "\n".join(lines)


def _message_tokens(message: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", message.lower())
    seen = set()
    filtered = []
    for token in tokens:
        if token in _QUERY_STOPWORDS:
            continue
        if len(token) < 3:
            continue
        if token in seen:
            continue
        seen.add(token)
        filtered.append(token)
    return filtered


def _detect_domain_hint(message: str, metrics: dict) -> str | None:
    lower = message.lower()
    domains = [str(item.get("domain") or "") for item in metrics.get("domains", [])]

    for domain in sorted(domains, key=len, reverse=True):
        if domain and domain in lower:
            return domain

    for domain in sorted(domains, key=len, reverse=True):
        root = domain.split(".")[0]
        if len(root) < 3:
            continue
        if re.search(rf"\b{re.escape(root)}\b", lower):
            return domain

    return None


def _match_tasks(message: str, metrics: dict) -> list[dict]:
    tasks = list(metrics.get("tasks") or [])
    if not tasks:
        return []

    domain_hint = _detect_domain_hint(message, metrics)
    if domain_hint:
        tasks = [task for task in tasks if task.get("domain") == domain_hint]

    query_tokens = _message_tokens(message)
    if not query_tokens:
        return tasks[:20]

    scored: list[tuple[int, dict]] = []
    for task in tasks:
        haystack = f"{task.get('task', '')} {task.get('domain', '')}".lower()
        score = sum(1 for token in query_tokens if token in haystack)
        if score > 0:
            scored.append((score, task))

    if not scored:
        return tasks[:20]

    scored.sort(
        key=lambda item: (
            item[0],
            _coerce_int(item[1].get("run_count")),
            _coerce_float(item[1].get("confidence")),
        ),
        reverse=True,
    )

    top_score = scored[0][0]
    if top_score >= 2:
        strong_matches = [task for score, task in scored if score == top_score]
        return strong_matches[:20]
    return [task for _, task in scored[:20]]


def _build_local_insight_reply(message: str, metrics: dict, source_used: str) -> str:
    total_tasks = _coerce_int(metrics.get("total_tasks"))
    if total_tasks <= 0:
        return (
            f"No task data available in `{source_used}` source yet. "
            "Run a few simulations first, then ask again."
        )

    matched = _match_tasks(message, metrics)
    if not matched:
        return (
            f"I could not find a direct task match. "
            f"Current dataset has {metrics['total_tasks']} tasks across "
            f"{metrics['total_domains']} domains and {metrics['total_runs']} total runs."
        )

    run_sum = sum(_coerce_int(task.get("run_count")) for task in matched)
    confidence_mean = (
        sum(_coerce_float(task.get("confidence")) for task in matched) / len(matched)
    )
    confidence_pct = round(confidence_mean * 100, 1)

    lower_message = message.lower()
    wants_confidence = "confidence" in lower_message
    wants_count = any(
        phrase in lower_message
        for phrase in ("how many", "count", "run", "runs", "tasks", "task")
    )

    top_matches = matched[:3]
    match_lines = [
        f"- {task['task']} ({task['domain']}): "
        f"{round(_coerce_float(task.get('confidence')) * 100)}% confidence, "
        f"{_coerce_int(task.get('run_count'))} runs"
        for task in top_matches
    ]

    if wants_confidence and wants_count:
        return (
            f"Across {len(matched)} matching tasks, average confidence is "
            f"{confidence_pct}% with {run_sum} total runs.\n"
            + "\n".join(match_lines)
        )
    if wants_confidence:
        return (
            f"Average confidence for {len(matched)} matching tasks is "
            f"{confidence_pct}%.\n"
            + "\n".join(match_lines)
        )
    if wants_count:
        return (
            f"I found {len(matched)} matching tasks with {run_sum} total runs.\n"
            + "\n".join(match_lines)
        )

    return (
        f"Matched {len(matched)} tasks (source: {source_used}). "
        f"Average confidence: {confidence_pct}%. Total runs: {run_sum}.\n"
        + "\n".join(match_lines)
    )


def _call_an_chat_api(full_message: str) -> str:
    global _an_sandbox_id, _an_thread_id

    body: dict = {
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"type": "text", "text": full_message}],
            }
        ]
    }
    if _an_sandbox_id:
        body["sandboxId"] = _an_sandbox_id
    if _an_thread_id:
        body["threadId"] = _an_thread_id

    request = urllib.request.Request(
        AN_CHAT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {AN_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    full_text: list[str] = []
    with urllib.request.urlopen(request, timeout=35) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:].strip()
            if payload == "[DONE]":
                break

            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue

            event_type = str(event.get("type") or "")
            if event_type == "text-delta":
                full_text.append(str(event.get("delta") or ""))
                continue

            if event_type == "start":
                sandbox_id = event.get("sandboxId")
                thread_id = event.get("threadId")
                if sandbox_id:
                    _an_sandbox_id = str(sandbox_id)
                if thread_id:
                    _an_thread_id = str(thread_id)
                continue

            delta = event.get("delta")
            if isinstance(delta, dict):
                text_delta = delta.get("text")
                if text_delta:
                    full_text.append(str(text_delta))

    return "".join(full_text).strip()


@app.post("/api/chat")
async def chat(payload: ChatPayload):
    message = payload.message.strip()
    if not message:
        return {"reply": "Please ask a question.", "sourceUsed": "none", "relayUsed": False}

    loop = asyncio.get_running_loop()
    build_fn = functools.partial(
        _build_data_context,
        payload.source,
        payload.demo_snapshot,
    )
    source_used, metrics, context = await loop.run_in_executor(None, build_fn)
    full_message = f"{context}\n\nUser question: {message}"

    relay_used = False
    reply = ""

    if AN_API_KEY:
        try:
            reply = await loop.run_in_executor(None, _call_an_chat_api, full_message)
            relay_used = bool(reply)
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning("An relay request failed: %s", exc)
        except Exception:
            logger.exception("Unexpected An relay failure")

    if not reply:
        reply = _build_local_insight_reply(message, metrics, source_used)

    return {"reply": reply, "sourceUsed": source_used, "relayUsed": relay_used}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive; client doesn't send data.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ---------------------------------------------------------------------------
# Static files — serve index.html at root, other files from frontend dir
# ---------------------------------------------------------------------------


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


# Mount static files last so API routes take precedence.
app.mount("/", StaticFiles(directory=str(STATIC_DIR)), name="static")
