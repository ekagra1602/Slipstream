"""Live integration tests for db/db.py against real MongoDB Atlas.

Opt-in only:
    DOMBOT_RUN_LIVE_DB_TESTS=1 python -m pytest tests/test_db_live.py -v
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

# Must override defaults from tests/conftest.py (which sets localhost for unit tests).
load_dotenv(override=True)


def _require_live_mode() -> None:
    if os.getenv("DOMBOT_RUN_LIVE_DB_TESTS") != "1":
        pytest.skip("Set DOMBOT_RUN_LIVE_DB_TESTS=1 to run live DB tests")


def _require_env() -> tuple[str, str]:
    uri = os.getenv("MONGODB_URI")
    openai_key = os.getenv("OPENAI_API_KEY")
    if not uri:
        pytest.skip("MONGODB_URI is not set")
    if not openai_key:
        pytest.skip("OPENAI_API_KEY is not set")
    if "localhost:27017" in uri or uri.startswith("mongodb://localhost"):
        pytest.skip("MONGODB_URI points to localhost; expected Atlas URI for live test")
    return uri, openai_key


def _wait_for_vector_index_ready(client: MongoClient, timeout_s: int = 90) -> None:
    db = client["dombot"]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = db.command({"listSearchIndexes": "task_nodes"})
        batch = resp.get("cursor", {}).get("firstBatch", [])
        idx = next((i for i in batch if i.get("name") == "task_vector_index"), None)
        if idx and idx.get("type") == "vectorSearch" and idx.get("status") == "READY":
            return
        time.sleep(3)

    pytest.skip("task_vector_index is not READY as vectorSearch on dombot.task_nodes")


@pytest.mark.live_db
def test_live_store_and_query_context_roundtrip():
    _require_live_mode()
    uri, _ = _require_env()

    from db import db as live_db
    from db.config import COLLECTION_TASK_NODES, DB_NAME

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    _wait_for_vector_index_ready(client)

    task = f"live-db-integration-{uuid.uuid4().hex}"
    domain = "integration.test.local"

    trace = [
        live_db.StepData(action="navigate", target="home", success=True),
        live_db.StepData(action="click", target="cta", success=True),
    ]

    try:
        # Exercise full write path.
        live_db.store_trace(task, domain, trace, success=True)
        live_db.store_step(
            task,
            domain,
            live_db.StepData(action="click", target="cta", success=True),
        )

        # Confirm direct write landed for this exact task/domain.
        written = client[DB_NAME][COLLECTION_TASK_NODES].find_one(
            {"task": task, "domain": domain}
        )
        assert written is not None

        # Exercise vector query path.
        # Atlas vector indexes can be briefly eventually consistent for newest docs,
        # so poll for a short window for the exact task to appear in results.
        deadline = time.time() + 30
        result = None
        while time.time() < deadline:
            result = live_db.query_context(task, domain)
            if result is not None and result.task == task:
                break
            time.sleep(1)

        assert result is not None
        assert result.domain == domain
        assert result.run_count >= 1
        assert 0.0 <= result.confidence <= 0.99
        assert result.task == task, "vector query did not return newly written task within 30s"
    finally:
        # Keep test idempotent and avoid polluting production data.
        client[DB_NAME][COLLECTION_TASK_NODES].delete_many(
            {"task": task, "domain": domain}
        )
