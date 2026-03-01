#!/usr/bin/env python3
"""Benchmark runner for DomBot learning over repeated tasks.

Usage examples:
  source .venv/bin/activate
  export DOMBOT_DB_BACKEND=mongo
  python scripts/benchmark1.py --runs 10 --mode same
  python scripts/benchmark1.py --runs 15 --mode paraphrase
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from browser_use import Agent, Browser
from dombot.db import get_backend_name
from dombot.prompts import DOMBOT_SYSTEM_PROMPT
from dombot.tools import tools
from dombot.trace_pipeline import initialize_laminar, process_trace


DEFAULT_TASK = "Go to google.com and search for 'DomBot browser automation' and tell me the first result title"
DEFAULT_DOMAIN = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated DomBot benchmark tasks and log results.")
    parser.add_argument("--runs", type=int, default=10, help="Number of benchmark runs")
    parser.add_argument(
        "--mode",
        choices=["same", "paraphrase"],
        default="same",
        help="Use identical task text each run or rotate paraphrases",
    )
    parser.add_argument("--task", default=DEFAULT_TASK, help="Base task description")
    parser.add_argument(
        "--domain",
        default=DEFAULT_DOMAIN,
        help="Optional domain override for DomBot query/store (auto-inferred from task when omitted)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="CSV output path (default: benchmarks/benchmark1_<timestamp>.csv)",
    )
    return parser.parse_args()


def paraphrase_tasks(base_task: str) -> list[str]:
    return [
        base_task,
        "Search Google for 'DomBot browser automation' and return the first result title.",
        "Find the top result title on google.com for DomBot browser automation.",
        "On Google, query DomBot browser automation and tell me the first result title.",
        "Go to google.com, run DomBot browser automation search, then report the first title.",
    ]


def build_run_tasks(base_task: str, runs: int, mode: str) -> list[str]:
    if mode == "same":
        return [base_task for _ in range(runs)]

    templates = paraphrase_tasks(base_task)
    out: list[str] = []
    for i in range(runs):
        out.append(templates[i % len(templates)])
    return out


def infer_domain_from_task(task: str, fallback: str = "") -> str:
    """Infer domain from task text (URL or bare domain)."""
    # URL form: https://walmart.com/...
    url_match = re.search(r"https?://[^\s)]+", task, flags=re.IGNORECASE)
    if url_match:
        host = urlparse(url_match.group(0)).hostname
        if host:
            return host.lower()

    # Bare domain form: walmart.com
    domain_match = re.search(r"\b([a-z0-9-]+\.)+[a-z]{2,}\b", task, flags=re.IGNORECASE)
    if domain_match:
        return domain_match.group(0).lower()

    return fallback.lower() if fallback else "unknown.local"


def default_output_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path("benchmarks") / "benchmark_v1" / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "results.csv"


def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    xs = sorted(values)
    idx = (len(xs) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(xs) - 1)
    frac = idx - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


def _safe_model_dump(obj) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            return {}
    return {}


def _sum_token_keys(node, acc: dict[str, int]) -> None:
    if node is None:
        return
    if isinstance(node, dict):
        # Common token key aliases across providers/libs.
        key_map = {
            "input_tokens": "input_tokens",
            "prompt_tokens": "input_tokens",
            "output_tokens": "output_tokens",
            "completion_tokens": "output_tokens",
            "total_tokens": "total_tokens",
        }
        for k, v in node.items():
            if k in key_map and isinstance(v, (int, float)):
                acc[key_map[k]] += int(v)
            else:
                _sum_token_keys(v, acc)
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _sum_token_keys(item, acc)
        return


def _extract_token_usage(result, history) -> tuple[int, int, int]:
    acc = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    # Try usage() helpers first if present.
    for obj in (history, result):
        if hasattr(obj, "usage"):
            try:
                usage_obj = obj.usage()
                _sum_token_keys(_safe_model_dump(usage_obj), acc)
            except Exception:
                pass

    # Fall back to dumping history/result recursively.
    _sum_token_keys(_safe_model_dump(history), acc)
    _sum_token_keys(_safe_model_dump(result), acc)

    # Normalize total if missing.
    if acc["total_tokens"] == 0 and (acc["input_tokens"] or acc["output_tokens"]):
        acc["total_tokens"] = acc["input_tokens"] + acc["output_tokens"]

    return acc["input_tokens"], acc["output_tokens"], acc["total_tokens"]


def _estimate_usd_cost(input_tokens: int, output_tokens: int) -> float:
    # Optional model pricing knobs for your environment.
    # Defaults are 0.0 so this remains safe if unknown.
    in_per_1k = _to_float(os.getenv("DOMBOT_INPUT_USD_PER_1K", "0.0"))
    out_per_1k = _to_float(os.getenv("DOMBOT_OUTPUT_USD_PER_1K", "0.0"))
    return round((input_tokens / 1000.0) * in_per_1k + (output_tokens / 1000.0) * out_per_1k, 6)


def load_mongo_collection():
    try:
        from pymongo import MongoClient
        from db.config import COLLECTION_TASK_NODES, DB_NAME, MONGODB_URI
    except Exception:
        return None

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
    return client[DB_NAME][COLLECTION_TASK_NODES]


def fetch_task_node_metrics(collection, task: str, domain: str) -> tuple[int | None, float | None, int | None]:
    if collection is None:
        return None, None, None
    doc = collection.find_one({"task": task, "domain": domain}, sort=[("_id", -1)])
    if not doc:
        return None, None, None
    return (
        doc.get("run_count"),
        doc.get("confidence"),
        len(doc.get("optimal_actions", [])),
    )


async def run_once(run_idx: int, task: str, domain: str) -> dict:
    from lmnr import Laminar as _Lmnr, observe

    row: dict = {
        "run_idx": run_idx,
        "task": task,
        "domain": domain,
        "status": "unknown",
        "steps": 0,
        "duration_s": 0.0,
        "trace_id": "",
        "agent_success": "",
        "judge_validated": "",
        "judge_failure_reason": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_usd_cost": 0.0,
        "final_result": "",
        "error": "",
    }

    t0 = time.time()

    @observe()
    async def _wrapped() -> dict:
        trace_id_holder: dict = {}
        history_holder: dict = {}

        async def on_done(history):
            trace_id_holder["id"] = str(_Lmnr.get_trace_id() or "")
            history_holder["history"] = history
            await process_trace(history, trace_id_holder["id"] or None, task, domain)

        browser = Browser(use_cloud=True)
        agent = Agent(
            task=task,
            model="bu-max",
            browser=browser,
            tools=tools,
            extend_system_message=DOMBOT_SYSTEM_PROMPT,
            register_done_callback=on_done,
        )

        try:
            result = await agent.run()
            history = history_holder.get("history", result.history)
            row["status"] = "ok"
            row["steps"] = len(result.history)
            row["final_result"] = (result.final_result() or "")[:400]
            row["trace_id"] = trace_id_holder.get("id", "")
            row["agent_success"] = history.is_successful() if hasattr(history, "is_successful") else ""
            row["judge_validated"] = history.is_validated() if hasattr(history, "is_validated") else ""
            if hasattr(history, "judgement"):
                j = history.judgement() or {}
                row["judge_failure_reason"] = (j.get("failure_reason") or "")[:300]
            input_tokens, output_tokens, total_tokens = _extract_token_usage(result, history)
            row["input_tokens"] = input_tokens
            row["output_tokens"] = output_tokens
            row["total_tokens"] = total_tokens
            row["estimated_usd_cost"] = _estimate_usd_cost(input_tokens, output_tokens)
            return row
        finally:
            await browser.stop()

    try:
        await _wrapped()
    except Exception as exc:
        row["status"] = "error"
        row["error"] = str(exc)[:400]

    row["duration_s"] = round(time.time() - t0, 3)
    return row


async def main_async(args: argparse.Namespace) -> int:
    load_dotenv(override=True)

    if not os.getenv("BROWSER_USE_API_KEY"):
        print("ERROR: BROWSER_USE_API_KEY is required")
        return 1

    backend = get_backend_name()
    print(f"DomBot backend: {backend}")
    if backend != "mongo":
        print("WARNING: backend is not 'mongo'. Set DOMBOT_DB_BACKEND=mongo for real learning benchmarks.")

    initialize_laminar()
    collection = load_mongo_collection()

    out_path = Path(args.output) if args.output else default_output_path()
    out_dir = out_path.parent
    run_tasks = build_run_tasks(args.task, args.runs, args.mode)

    rows: list[dict] = []
    for i, task in enumerate(run_tasks, 1):
        domain = infer_domain_from_task(task, args.domain)
        print(f"\n--- Run {i}/{args.runs} ---")
        print(f"task: {task}")
        print(f"domain: {domain}")
        row = await run_once(i, task, domain)
        run_count, confidence, optimal_actions_len = fetch_task_node_metrics(collection, task, domain)
        row["mongo_run_count"] = run_count if run_count is not None else ""
        row["mongo_confidence"] = confidence if confidence is not None else ""
        row["mongo_optimal_actions"] = optimal_actions_len if optimal_actions_len is not None else ""
        rows.append(row)
        print(
            f"status={row['status']} steps={row['steps']} agent_success={row['agent_success']} "
            f"judge={row['judge_validated']} conf={row['mongo_confidence']}"
        )

    fieldnames = [
        "run_idx",
        "task",
        "domain",
        "status",
        "steps",
        "duration_s",
        "trace_id",
        "agent_success",
        "judge_validated",
        "judge_failure_reason",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_usd_cost",
        "mongo_run_count",
        "mongo_confidence",
        "mongo_optimal_actions",
        "final_result",
        "error",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    jsonl_path = out_dir / "results.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    total = len(rows)
    ok = sum(1 for r in rows if r["status"] == "ok")
    judged_pass = sum(1 for r in rows if r["judge_validated"] is True)
    durations = [_to_float(r.get("duration_s")) for r in rows]
    steps = [_to_int(r.get("steps")) for r in rows]
    total_tokens_series = [_to_int(r.get("total_tokens")) for r in rows]
    usd_cost_series = [_to_float(r.get("estimated_usd_cost")) for r in rows]
    confidences = [_to_float(r.get("mongo_confidence"), default=-1.0) for r in rows]
    confidences = [c for c in confidences if c >= 0.0]

    avg_steps = round(sum(steps) / max(total, 1), 2)
    avg_duration = round(sum(durations) / max(total, 1), 2)
    median_steps = round(statistics.median(steps), 2) if steps else 0.0
    median_duration = round(statistics.median(durations), 2) if durations else 0.0
    p90_duration = round(_percentile(durations, 0.9), 2) if durations else 0.0
    min_duration = round(min(durations), 2) if durations else 0.0
    max_duration = round(max(durations), 2) if durations else 0.0
    min_steps = min(steps) if steps else 0
    max_steps = max(steps) if steps else 0
    pass_rate = round((judged_pass / max(total, 1)) * 100.0, 2)
    avg_total_tokens = round(sum(total_tokens_series) / max(total, 1), 2)
    avg_usd_cost = round(sum(usd_cost_series) / max(total, 1), 6)
    total_usd_cost = round(sum(usd_cost_series), 6)
    unique_domains = sorted({str(r.get("domain") or "").strip() for r in rows if str(r.get("domain") or "").strip()})
    domain_display = ", ".join(unique_domains) if unique_domains else (args.domain or "(none)")

    # Compare early vs late performance to show trend.
    k = max(1, min(5, total // 2))
    first_d = durations[:k]
    last_d = durations[-k:]
    first_s = steps[:k]
    last_s = steps[-k:]
    first_d_avg = round(sum(first_d) / max(len(first_d), 1), 2)
    last_d_avg = round(sum(last_d) / max(len(last_d), 1), 2)
    first_s_avg = round(sum(first_s) / max(len(first_s), 1), 2)
    last_s_avg = round(sum(last_s) / max(len(last_s), 1), 2)
    duration_delta = round(last_d_avg - first_d_avg, 2)
    steps_delta = round(last_s_avg - first_s_avg, 2)

    conf_start = round(confidences[0], 3) if confidences else 0.0
    conf_end = round(confidences[-1], 3) if confidences else 0.0
    conf_peak = round(max(confidences), 3) if confidences else 0.0
    conf_delta = round(conf_end - conf_start, 3) if confidences else 0.0

    judge_fail_reasons = [str(r.get("judge_failure_reason") or "").strip() for r in rows if r.get("judge_validated") is False]

    summary_path = out_dir / "summary.md"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("# Benchmark v1 Summary\n\n")
        f.write(f"- runs: {total}\n")
        f.write(f"- ok: {ok}\n")
        f.write(f"- judged_pass: {judged_pass}\n")
        f.write(f"- judged_pass_rate_pct: {pass_rate}\n")
        f.write(f"- judged_fail: {total - judged_pass}\n")
        f.write(f"- avg_total_tokens: {avg_total_tokens}\n")
        f.write(f"- avg_estimated_usd_cost: {avg_usd_cost}\n")
        f.write(f"- total_estimated_usd_cost: {total_usd_cost}\n")
        f.write(f"- avg_steps: {avg_steps}\n")
        f.write(f"- median_steps: {median_steps}\n")
        f.write(f"- min_steps: {min_steps}\n")
        f.write(f"- max_steps: {max_steps}\n")
        f.write(f"- avg_duration_s: {avg_duration}\n")
        f.write(f"- median_duration_s: {median_duration}\n")
        f.write(f"- p90_duration_s: {p90_duration}\n")
        f.write(f"- min_duration_s: {min_duration}\n")
        f.write(f"- max_duration_s: {max_duration}\n")
        f.write(f"- first_{k}_avg_duration_s: {first_d_avg}\n")
        f.write(f"- last_{k}_avg_duration_s: {last_d_avg}\n")
        f.write(f"- duration_delta_last_minus_first_s: {duration_delta}\n")
        f.write(f"- first_{k}_avg_steps: {first_s_avg}\n")
        f.write(f"- last_{k}_avg_steps: {last_s_avg}\n")
        f.write(f"- steps_delta_last_minus_first: {steps_delta}\n")
        f.write(f"- confidence_start: {conf_start}\n")
        f.write(f"- confidence_end: {conf_end}\n")
        f.write(f"- confidence_peak: {conf_peak}\n")
        f.write(f"- confidence_delta: {conf_delta}\n")
        f.write(f"- mode: {args.mode}\n")
        f.write(f"- domains: {domain_display}\n")
        f.write(f"- backend: {backend}\n")
        if judge_fail_reasons:
            f.write("\n## Judge Fail Reasons\n")
            for i, reason in enumerate(judge_fail_reasons, 1):
                f.write(f"{i}. {reason}\n")
        f.write("\n## Files\n")
        f.write(f"- CSV: `{out_path}`\n")
        f.write(f"- JSONL: `{jsonl_path}`\n")

    print("\n=== Benchmark Complete ===")
    print(f"runs: {total}, ok: {ok}, judged_pass: {judged_pass}")
    print(f"csv: {out_path}")
    print(f"jsonl: {jsonl_path}")
    print(f"summary: {summary_path}")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
