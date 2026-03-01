#!/usr/bin/env python3
"""Minimal trace-first DomBot proof of concept.

This script demonstrates:
1) ingesting raw traces,
2) building task memory nodes from successful traces,
3) retrieving a suggested action plan for a new task.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Trace:
    trace_id: str
    task: str
    domain: str
    success: bool
    step_count: int
    latency_ms: int
    steps: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trace":
        return cls(
            trace_id=data["trace_id"],
            task=data["task"],
            domain=data["domain"],
            success=bool(data.get("success", False)),
            step_count=int(data.get("step_count", 0)),
            latency_ms=int(data.get("latency_ms", 0)),
            steps=list(data.get("steps", [])),
        )


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def normalize_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def token_vector(text: str) -> Counter[str]:
    return Counter(normalize_tokens(text))


def cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def action_signature(step: dict[str, Any]) -> str:
    action = step.get("action", "unknown")
    target = step.get("target", "unknown")
    value = step.get("value")
    if value:
        return f"{action}:{target}:{value}"
    return f"{action}:{target}"


def build_task_nodes(traces: list[Trace]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Trace]] = defaultdict(list)
    for t in traces:
        if t.success:
            key = (t.domain, t.task.lower().strip())
            grouped[key].append(t)

    nodes: list[dict[str, Any]] = []
    for (domain, task), bucket in grouped.items():
        run_count = len(bucket)
        avg_steps = sum(t.step_count for t in bucket) / run_count
        avg_latency = sum(t.latency_ms for t in bucket) / run_count

        # Majority action sequence by position.
        pos_votes: dict[int, Counter[str]] = defaultdict(Counter)
        for t in bucket:
            for idx, step in enumerate(t.steps):
                pos_votes[idx][action_signature(step)] += 1

        optimal_actions: list[str] = []
        min_consensus = 0.5
        for idx in sorted(pos_votes):
            sig, votes = pos_votes[idx].most_common(1)[0]
            if votes / run_count < min_consensus:
                continue
            optimal_actions.append(sig)

        confidence = min(0.99, 0.6 + (0.08 * run_count))
        node_id = f"node_{domain.replace('.', '_')}_{abs(hash(task)) % 1_000_000}"
        nodes.append(
            {
                "_id": node_id,
                "domain": domain,
                "task": task,
                "task_vector": dict(token_vector(task)),
                "run_count": run_count,
                "avg_step_count": round(avg_steps, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "confidence": round(confidence, 2),
                "optimal_actions": optimal_actions,
            }
        )
    return nodes


def suggest_task_node(
    nodes: list[dict[str, Any]], query_task: str, domain: str | None
) -> tuple[dict[str, Any] | None, float]:
    qv = token_vector(query_task)
    best: dict[str, Any] | None = None
    best_score = -1.0
    for node in nodes:
        if domain and node["domain"] != domain:
            continue
        nv = Counter(node.get("task_vector", {}))
        score = cosine_similarity(qv, nv)
        if score > best_score:
            best = node
            best_score = score
    return best, best_score


def cmd_build(args: argparse.Namespace) -> int:
    traces_data = read_json(Path(args.traces))
    traces = [Trace.from_dict(t) for t in traces_data]
    nodes = build_task_nodes(traces)
    write_json(Path(args.out), nodes)
    print(f"Built {len(nodes)} task node(s) -> {args.out}")
    return 0


def cmd_suggest(args: argparse.Namespace) -> int:
    nodes = read_json(Path(args.nodes))
    node, score = suggest_task_node(nodes, args.task, args.domain)
    if not node:
        print("No matching task node found.")
        return 1

    print("Suggested plan")
    print(f"- domain: {node['domain']}")
    print(f"- matched_task: {node['task']}")
    print(f"- similarity: {score:.3f}")
    print(f"- run_count: {node['run_count']}")
    print(f"- confidence: {node['confidence']}")
    print("- optimal_actions:")
    for i, action in enumerate(node["optimal_actions"], start=1):
        print(f"  {i}. {action}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Trace-first DomBot POC")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="Build task memory nodes from raw traces")
    pb.add_argument("--traces", required=True, help="Path to raw traces JSON file")
    pb.add_argument("--out", required=True, help="Output path for task nodes JSON")
    pb.set_defaults(func=cmd_build)

    ps = sub.add_parser("suggest", help="Suggest best prior action path for a task")
    ps.add_argument("--nodes", required=True, help="Path to task nodes JSON")
    ps.add_argument("--task", required=True, help="Incoming user task")
    ps.add_argument("--domain", help="Optional domain filter")
    ps.set_defaults(func=cmd_suggest)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
