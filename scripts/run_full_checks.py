#!/usr/bin/env python3
"""Run end-to-end DomBot DB checks in one command.

Checks:
1) Environment variables present
2) MongoDB ping + write/read smoke test
3) Vector index presence/type/status
4) db/db.py integration path (store_trace/store_step/query_context)
5) Optional unit tests: tests/test_db.py
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import shutil

from dotenv import load_dotenv
from pymongo import MongoClient

# Ensure local packages are importable regardless of caller cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def section(name: str) -> None:
    print(f"\n=== {name} ===")


def ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def list_search_indexes(db) -> list[dict]:
    # Works across pymongo versions by using command response directly.
    resp = db.command({"listSearchIndexes": "task_nodes"})
    cursor = resp.get("cursor", {})
    return cursor.get("firstBatch", [])


def run() -> int:
    load_dotenv(override=True)

    failures = 0

    section("Environment")
    uri = os.getenv("MONGODB_URI")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not uri:
        fail("MONGODB_URI is missing")
        failures += 1
    else:
        ok("MONGODB_URI present")

    if not openai_key:
        fail("OPENAI_API_KEY is missing")
        failures += 1
    else:
        ok("OPENAI_API_KEY present")

    if failures:
        return 1

    section("Mongo Smoke")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    ping = client.admin.command("ping")
    if ping.get("ok") == 1:
        ok("ping ok")
    else:
        fail(f"unexpected ping response: {ping}")
        failures += 1

    db = client["dombot"]
    col = db["write_test"]
    doc = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "run_full_checks",
    }
    res = col.insert_one(doc)
    found = col.find_one({"_id": res.inserted_id})
    if found:
        ok(f"write/read ok inserted_id={res.inserted_id}")
    else:
        fail("write/read failed")
        failures += 1

    section("Vector Index")
    try:
        indexes = list_search_indexes(db)
    except Exception as exc:
        fail(f"unable to list search indexes: {exc}")
        return 1

    idx = next((i for i in indexes if i.get("name") == "task_vector_index"), None)
    if idx is None:
        fail("task_vector_index not found on dombot.task_nodes")
        failures += 1
    else:
        idx_type = idx.get("type")
        idx_status = idx.get("status")
        print(f"index type={idx_type} status={idx_status}")
        if idx_type != "vectorSearch":
            fail("task_vector_index is not type=vectorSearch")
            failures += 1
        elif idx_status != "READY":
            fail("task_vector_index is not READY")
            failures += 1
        else:
            ok("task_vector_index is vectorSearch + READY")

    section("db/db.py Integration")
    try:
        from db import db as live_db

        task = f"integration-openai-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        domain = "integration.test.local"

        trace = [
            live_db.StepData(action="navigate", target="home", success=True),
            live_db.StepData(action="click", target="cta", success=True),
        ]

        live_db.store_trace(task, domain, trace, success=True)
        live_db.store_step(
            task,
            domain,
            live_db.StepData(action="click", target="cta", success=True),
        )
        result = live_db.query_context(task, domain)

        if result is None:
            fail("query_context returned None after writes")
            failures += 1
        else:
            ok("query_context returned a result")
            print(f"task={result.task}")
            print(f"domain={result.domain}")
            print(f"run_count={result.run_count}")
            print(f"confidence={result.confidence}")
            print(f"optimal_actions_len={len(result.optimal_actions)}")
            print(f"step_traces_len={len(result.step_traces)}")
    except Exception as exc:
        fail(f"integration path failed: {exc}")
        failures += 1

    section("Unit Tests (optional)")
    if importlib.util.find_spec("pytest") is not None:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_db.py", "-q"],
            check=False,
            cwd=str(REPO_ROOT),
        )
        if proc.returncode == 0:
            ok("tests/test_db.py passed")
        else:
            fail("tests/test_db.py failed")
            failures += 1
    else:
        pytest_bin = shutil.which("pytest")
        if pytest_bin:
            proc = subprocess.run(
                [pytest_bin, "tests/test_db.py", "-q"],
                check=False,
                cwd=str(REPO_ROOT),
            )
            if proc.returncode == 0:
                ok("tests/test_db.py passed (system pytest)")
            else:
                fail("tests/test_db.py failed (system pytest)")
                failures += 1
        else:
            warn("pytest not installed in interpreter or PATH; skipping tests/test_db.py")

    section("Summary")
    if failures:
        fail(f"{failures} check(s) failed")
        return 1
    ok("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
