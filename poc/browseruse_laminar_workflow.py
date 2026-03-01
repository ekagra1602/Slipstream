#!/usr/bin/env python3
"""Run a Browser Use v3 multi-task session with Laminar enabled.

This workflow is designed for DomBot MVP validation:
1) Initialize Laminar tracing.
2) Start a Browser Use session (keepAlive=true).
3) Run multiple tasks in the same live session.
4) Poll session status until each task settles.
5) Persist local execution artifacts for downstream ingestion.
6) Stop task or session with explicit strategy.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from lmnr import Laminar

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for minimal environments
    load_dotenv = None

TERMINAL_SESSION_STATES = {"idle", "stopped", "timed_out", "error"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    browser_use_api_key: str
    lmnr_project_api_key: str
    base_url: str
    workspace_id: str | None
    proxy_country_code: str | None
    max_cost_usd: float | None
    output_schema: dict[str, Any] | None


class BrowserUseClient:
    def __init__(self, config: Config, timeout_s: int = 60) -> None:
        self.config = config
        self.http = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=timeout_s,
            headers={
                "Content-Type": "application/json",
                "X-Browser-Use-API-Key": config.browser_use_api_key,
            },
        )

    def _extract_session_id(self, payload: dict[str, Any]) -> str:
        for key in ("sessionId", "id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        raise RuntimeError(f"Could not extract session id from response: {payload}")

    def create_session(self, keep_alive: bool) -> dict[str, Any]:
        body: dict[str, Any] = {"keepAlive": keep_alive}
        if self.config.workspace_id:
            body["workspaceId"] = self.config.workspace_id
        if self.config.proxy_country_code:
            body["proxyCountryCode"] = self.config.proxy_country_code

        resp = self.http.post("/sessions", json=body)
        resp.raise_for_status()
        return resp.json()

    def run_task(self, session_id: str, task: str, keep_alive: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "sessionId": session_id,
            "task": task,
            "keepAlive": keep_alive,
        }
        if self.config.workspace_id:
            body["workspaceId"] = self.config.workspace_id
        if self.config.proxy_country_code:
            body["proxyCountryCode"] = self.config.proxy_country_code
        if self.config.max_cost_usd is not None:
            body["maxCostUsd"] = self.config.max_cost_usd
        if self.config.output_schema:
            body["outputSchema"] = self.config.output_schema

        resp = self.http.post("/sessions", json=body)
        resp.raise_for_status()
        return resp.json()

    def get_session(self, session_id: str) -> dict[str, Any]:
        resp = self.http.get(f"/sessions/{session_id}")
        resp.raise_for_status()
        return resp.json()

    def stop_session(self, session_id: str, strategy: str) -> dict[str, Any]:
        resp = self.http.post(f"/sessions/{session_id}/stop", json={"strategy": strategy})
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {"status": "ok", "strategy": strategy}

    def close(self) -> None:
        self.http.close()


def wait_for_settled_state(
    client: BrowserUseClient,
    session_id: str,
    poll_interval_s: float,
    timeout_s: int,
) -> tuple[str, dict[str, Any]]:
    start = time.time()
    last_payload: dict[str, Any] = {}

    while True:
        payload = client.get_session(session_id)
        last_payload = payload
        status = str(payload.get("status", "")).lower()

        if status in TERMINAL_SESSION_STATES:
            return status, payload

        if time.time() - start > timeout_s:
            raise TimeoutError(
                f"Timed out waiting for session={session_id} to settle. Last status={status}"
            )
        time.sleep(poll_interval_s)


def save_artifacts(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Browser Use v3 + Laminar workflow runner"
    )
    parser.add_argument(
        "--task",
        action="append",
        required=True,
        help="Task text. Pass multiple --task flags to chain tasks in one session.",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        default=True,
        help="Keep session alive between tasks (default true).",
    )
    parser.add_argument(
        "--stop-strategy",
        choices=("task", "session", "none"),
        default="session",
        help="Final stop behavior after all tasks.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds for session status.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Timeout in seconds per task settlement wait.",
    )
    parser.add_argument(
        "--output",
        default="poc/browseruse_workflow_run.json",
        help="Where to save run artifacts JSON.",
    )
    parser.add_argument(
        "--output-schema-json",
        default=os.getenv("BROWSER_USE_OUTPUT_SCHEMA_JSON"),
        help="Optional path to output schema JSON file.",
    )
    return parser.parse_args()


def load_config(output_schema_path: str | None) -> Config:
    if load_dotenv is not None:
        load_dotenv()
    browser_use_api_key = os.getenv("BROWSER_USE_API_KEY", "").strip()
    lmnr_project_api_key = os.getenv("LMNR_PROJECT_API_KEY", "").strip()
    if not browser_use_api_key:
        raise RuntimeError("Missing BROWSER_USE_API_KEY in environment/.env")
    if not lmnr_project_api_key:
        raise RuntimeError("Missing LMNR_PROJECT_API_KEY in environment/.env")

    return Config(
        browser_use_api_key=browser_use_api_key,
        lmnr_project_api_key=lmnr_project_api_key,
        base_url=os.getenv("BROWSER_USE_BASE_URL", "https://api.browser-use.com/api/v3"),
        workspace_id=os.getenv("BROWSER_USE_WORKSPACE_ID"),
        proxy_country_code=os.getenv("BROWSER_USE_PROXY_COUNTRY_CODE"),
        max_cost_usd=(
            float(os.getenv("BROWSER_USE_MAX_COST_USD"))
            if os.getenv("BROWSER_USE_MAX_COST_USD")
            else None
        ),
        output_schema=read_json(output_schema_path),
    )


def main() -> int:
    args = parse_args()
    config = load_config(args.output_schema_json)

    # Disable auto-instrumentations in this environment to avoid browser-use
    # import-time display probing crashes; tracing can be added manually later.
    Laminar.initialize(
        project_api_key=config.lmnr_project_api_key,
        instruments=[],
    )

    client = BrowserUseClient(config=config)
    artifact: dict[str, Any] = {
        "started_at": utc_now_iso(),
        "base_url": config.base_url,
        "workspace_id": config.workspace_id,
        "proxy_country_code": config.proxy_country_code,
        "max_cost_usd": config.max_cost_usd,
        "tasks": [],
    }

    try:
        created = client.create_session(keep_alive=args.keep_alive)
        session_id = client._extract_session_id(created)
        artifact["session_create_response"] = created
        artifact["session_id"] = session_id

        for task in args.task:
            launched = client.run_task(
                session_id=session_id,
                task=task,
                keep_alive=args.keep_alive,
            )
            settled_status, settled_payload = wait_for_settled_state(
                client=client,
                session_id=session_id,
                poll_interval_s=args.poll_interval,
                timeout_s=args.timeout,
            )
            artifact["tasks"].append(
                {
                    "task": task,
                    "launched_at": utc_now_iso(),
                    "launch_response": launched,
                    "settled_status": settled_status,
                    "settled_payload": settled_payload,
                }
            )

        if args.stop_strategy != "none":
            artifact["stop_response"] = client.stop_session(
                session_id=session_id,
                strategy=args.stop_strategy,
            )

        artifact["finished_at"] = utc_now_iso()
        save_artifacts(Path(args.output), artifact)
        print(f"Workflow completed. Artifacts saved to: {args.output}")
        print(f"Session ID: {artifact['session_id']}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
