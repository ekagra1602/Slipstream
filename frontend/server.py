#!/usr/bin/env python3
"""FastAPI backend: REST endpoints, WebSocket, and static file serving."""
from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Allow imports from project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.db import (  # noqa: E402
    StepData,
    _get_collection,
    register_callback,
    store_trace,
)

app = FastAPI(title="DomBot Knowledge Graph")

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
        self.connections.remove(ws)

    async def broadcast(self, data: dict):
        for ws in list(self.connections):
            try:
                await ws.send_json(data)
            except Exception:
                self.connections.remove(ws)

manager = ConnectionManager()

# Bridge sync db callbacks to async WebSocket broadcasts.
_loop: asyncio.AbstractEventLoop | None = None
_pending_events: list[dict] = []


def _on_db_event(event: dict):
    """Called synchronously from db.py — schedule async broadcast."""
    if _loop and _loop.is_running():
        _loop.call_soon_threadsafe(asyncio.ensure_future, manager.broadcast(event))
    else:
        _pending_events.append(event)


register_callback(_on_db_event)


@app.on_event("startup")
async def _capture_loop():
    global _loop
    _loop = asyncio.get_running_loop()


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/graph")
def get_graph():
    """Return full graph data for initial load."""
    collection = _get_collection()
    docs = list(collection.find(
        {},
        {
            "task_embedding": 0,
            "_step_counts": 0,
            "_success_count": 0,
            "_history": 0,
        },
    ))

    nodes = []
    links = []
    domain_set: dict[str, dict] = {}

    # Build task nodes and collect domains.
    for doc in docs:
        task_id = str(doc["_id"])
        domain = doc["domain"]
        confidence = doc.get("confidence", 0.0)
        run_count = doc.get("run_count", 0)

        nodes.append({
            "id": task_id,
            "type": "task",
            "task": doc["task"],
            "domain": domain,
            "confidence": confidence,
            "run_count": run_count,
            "optimal_actions": doc.get("optimal_actions", []),
            "step_traces": doc.get("step_traces", []),
        })

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

    # Build domain nodes and domain→task links.
    for domain, stats in domain_set.items():
        domain_id = f"domain:{domain}"
        avg_conf = stats["total_confidence"] / stats["count"] if stats["count"] else 0
        nodes.append({
            "id": domain_id,
            "type": "domain",
            "domain": domain,
            "task_count": stats["count"],
            "total_runs": stats["total_runs"],
            "avg_confidence": round(avg_conf, 3),
        })
        for tid in stats["task_ids"]:
            links.append({"source": domain_id, "target": tid, "type": "hub"})

    # Cross-task links: tasks sharing 2+ action signatures (within AND across domains).
    all_task_actions = {}
    for node in nodes:
        if node.get("type") != "task":
            continue
        sigs = set()
        for a in node.get("optimal_actions", []):
            parts = a.split(":")
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
                links.append({
                    "source": tid_list[i],
                    "target": tid_list[j],
                    "type": "cross",
                    "strength": len(shared),
                })

    # Cross-domain links: connect domain nodes that share tasks with similar action patterns.
    for i, (d1, s1) in enumerate(domain_set.items()):
        for d2, s2 in list(domain_set.items())[i + 1:]:
            # Check if any tasks between these domains are linked.
            d1_tids = set(s1["task_ids"])
            d2_tids = set(s2["task_ids"])
            has_cross_link = any(
                link_item for link_item in links
                if link_item.get("type") == "cross"
                and (
                    (link_item["source"] in d1_tids and link_item["target"] in d2_tids)
                    or (link_item["source"] in d2_tids and link_item["target"] in d1_tids)
                )
            )
            if has_cross_link:
                links.append({
                    "source": f"domain:{d1}",
                    "target": f"domain:{d2}",
                    "type": "cross",
                })

    return {"nodes": nodes, "links": links}


@app.get("/api/graph/history")
def get_graph_history():
    """Return timestamped events for time-slider."""
    collection = _get_collection()
    docs = list(collection.find(
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
    ))

    events = []
    for doc in docs:
        node_id = str(doc["_id"])
        created = doc.get("created_at")
        if created:
            events.append({
                "timestamp": created.isoformat(),
                "type": "created",
                "node_id": node_id,
                "task": doc["task"],
                "domain": doc["domain"],
                "confidence": doc.get("confidence", 0),
                "run_count": doc.get("run_count", 0),
            })
        # Include history snapshots.
        for h in doc.get("_history", []):
            events.append({
                "timestamp": h["timestamp"].isoformat(),
                "type": "updated",
                "node_id": node_id,
                "task": doc["task"],
                "domain": doc["domain"],
                "confidence": h.get("confidence", 0),
                "run_count": h.get("run_count", 0),
            })

    events.sort(key=lambda e: e["timestamp"])
    return {"events": events}


# ---------------------------------------------------------------------------
# Simulate endpoint
# ---------------------------------------------------------------------------

SIMULATE_TASKS = [
    ("buy running shoes on walmart", "walmart.com", [
        ("type", "search_input", "running shoes"),
        ("click", "first_result", None),
        ("click", "add_to_cart", None),
    ]),
    ("buy a monitor on amazon", "amazon.com", [
        ("type", "search_box", "4k monitor"),
        ("click", "first_result", None),
        ("click", "add_to_cart", None),
    ]),
    ("search for restaurants on google", "google.com", [
        ("type", "search_input", "restaurants near me"),
        ("click", "search_button", None),
        ("click", "maps_result", None),
    ]),
    ("fork a repository on github", "github.com", [
        ("type", "search_input", "react"),
        ("click", "first_repo", None),
        ("click", "fork_button", None),
    ]),
    ("upload a video on youtube", "youtube.com", [
        ("click", "create_button", None),
        ("click", "upload_video", None),
        ("click", "select_file", None),
    ]),
    ("bookmark a tweet on x", "x.com", [
        ("click", "explore_tab", None),
        ("click", "first_tweet", None),
        ("click", "bookmark_button", None),
    ]),
    ("endorse a skill on linkedin", "linkedin.com", [
        ("type", "search_input", "Jane Doe"),
        ("click", "first_person_result", None),
        ("click", "endorse_skill_button", None),
    ]),
    ("buy a tv on bestbuy", "bestbuy.com", [
        ("type", "search_input", "OLED TV"),
        ("click", "first_result", None),
        ("click", "add_to_cart", None),
    ]),
    ("buy a gift card on target", "target.com", [
        ("type", "search_input", "gift card"),
        ("click", "first_result", None),
        ("click", "add_to_cart", None),
    ]),
    ("buy a camera on ebay", "ebay.com", [
        ("type", "search_input", "mirrorless camera"),
        ("click", "first_result", None),
        ("click", "buy_now_button", None),
    ]),
]

_auto_simulate_task: asyncio.Task | None = None


@app.post("/api/simulate")
async def simulate():
    """Trigger a fake agent run."""
    task_name, domain, raw_steps = random.choice(SIMULATE_TASKS)
    steps = [StepData(action=a, target=t, value=v, success=True) for a, t, v in raw_steps]

    # Run in thread to avoid blocking (db calls are sync).
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, store_trace, task_name, domain, steps, True)

    return {"status": "ok", "task": task_name, "domain": domain}


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
    elif action == "stop":
        if _auto_simulate_task and not _auto_simulate_task.done():
            _auto_simulate_task.cancel()
        _auto_simulate_task = None
        return {"status": "stopped"}
    return {"status": "unknown_action"}


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
