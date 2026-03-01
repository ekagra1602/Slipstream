"""
Demo: Run a browser-use agent with DomBot tools + Laminar trace pipeline.

Visually confirms the agent calls dombot_query and dombot_report during a live run,
then processes the trace through the Laminar pipeline.

Usage:
    # 1. Copy .env.example to .env and fill in your keys
    # 2. Run:
    python scripts/demo.py
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser_use import Agent, Browser
from dotenv import load_dotenv

from dombot.db import get_backend_name, get_step_log, get_trace_log, seed_task_node
from dombot.prompts import DOMBOT_SYSTEM_PROMPT
from dombot.tools import tools
from dombot.trace_pipeline import initialize_laminar, process_trace

load_dotenv()

# ── Logging — so you can see DomBot tool calls in real time ─────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet down noisy libs, keep dombot loud
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger("demo")

TASK = "Go to google.com and search for 'DomBot browser automation' and tell me the first result title"
DOMAIN = "google.com"


async def on_step(browser_state, model_output, step_number):
    """Fires after every agent step — log it so we see the agent's decisions."""
    if model_output and model_output.action:
        actions = [a.__class__.__name__ for a in model_output.action]
        logger.info(f"Agent step #{step_number}: {actions}")


async def main():
    # ── Pre-flight checks ───────────────────────────────────────────────────
    bu_key = os.getenv("BROWSER_USE_API_KEY")

    if not bu_key:
        print("ERROR: Set BROWSER_USE_API_KEY in .env (needed for cloud browser + LLM)")
        sys.exit(1)

    logger.info("BROWSER_USE_API_KEY loaded OK")

    # ── Initialize Laminar (safe — no-ops if key is missing) ────────────────
    initialize_laminar()

    backend = get_backend_name()
    logger.info("DomBot DB backend: %s", backend)

    # ── Optional: seed data so dombot_query returns something on first run ──
    # Only seed in mock mode. Mongo mode uses real DB state.
    if backend == "mock":
        seed_task_node(
            task="search for 'DomBot browser automation' on google",
            domain="google.com",
            confidence=0.75,
            run_count=8,
            optimal_actions=[
                "Navigate to google.com",
                "Type 'DomBot browser automation' into search input",
                "Press Enter or click Google Search",
                "Read the first result title",
            ],
        )
        logger.info("Seeded demo data into mock DB")

    # ── Build the agent with Laminar-wired on_done callback ─────────────────
    # trace_id capture: on_done fires inside run_agent's @observe() span,
    # so Laminar.get_trace_id() returns the active trace ID reliably.

    try:
        from lmnr import observe

        @observe()
        async def run_agent():
            trace_id_holder: dict = {}

            async def on_done(history):
                from lmnr import Laminar as _LmnrInner
                trace_id_holder["id"] = _LmnrInner.get_trace_id()
                tid = str(trace_id_holder["id"]) if trace_id_holder.get("id") else None
                await process_trace(history, tid, TASK, DOMAIN)

            browser = Browser(use_cloud=True)
            agent = Agent(
                task=TASK,
                model="bu-max",
                browser=browser,
                tools=tools,
                extend_system_message=DOMBOT_SYSTEM_PROMPT,
                register_new_step_callback=on_step,
                register_done_callback=on_done,
            )

            print()
            print("=" * 60)
            print(f"Task: {TASK}")
            print("DomBot tools: dombot_query, dombot_report")
            print(f"Laminar tracing: {'ENABLED' if trace_id_holder is not None else 'DISABLED'}")
            print("=" * 60)
            print()

            result = await agent.run()
            await browser.stop()
            return result

        result = await run_agent()

    except ImportError:
        # Laminar not installed — run without @observe wrapper
        logger.warning("lmnr package not installed — running without Laminar tracing")

        async def on_done_fallback(history):
            await process_trace(history, None, TASK, DOMAIN)

        browser = Browser(use_cloud=True)
        agent = Agent(
            task=TASK,
            model="bu-max",
            browser=browser,
            tools=tools,
            extend_system_message=DOMBOT_SYSTEM_PROMPT,
            register_new_step_callback=on_step,
            register_done_callback=on_done_fallback,
        )

        print()
        print("=" * 60)
        print(f"Task: {TASK}")
        print("DomBot tools: dombot_query, dombot_report")
        print("Laminar tracing: DISABLED (lmnr not installed)")
        print("=" * 60)
        print()

        result = await agent.run()
        await browser.stop()

    # ── Post-run summary ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("RUN COMPLETE")
    print("=" * 60)
    print(f"Steps: {len(result.history)}")
    print()

    if backend == "mongo":
        try:
            from pymongo import MongoClient
            from db.config import COLLECTION_TASK_NODES, DB_NAME, MONGODB_URI

            col = MongoClient(MONGODB_URI)[DB_NAME][COLLECTION_TASK_NODES]
            doc = col.find_one({"task": TASK, "domain": DOMAIN}, sort=[("_id", -1)])
            if doc:
                step_counts = doc.get("_step_counts", {})
                print(f"DomBot steps tracked (Mongo signatures): {len(step_counts)}")
                print("DomBot traces stored (Mongo run_count):", doc.get("run_count", 0))
                print("DomBot confidence:", doc.get("confidence", 0.0))
                print("DomBot optimal actions:", len(doc.get("optimal_actions", [])))
            else:
                print("DomBot Mongo summary: no matching task node found")
        except Exception as exc:
            print(f"DomBot Mongo summary unavailable: {exc}")
    else:
        step_log = get_step_log()
        trace_log = get_trace_log()

        print(f"DomBot steps recorded (via dombot_report): {len(step_log)}")
        for i, s in enumerate(step_log, 1):
            print(f"  {i}. [{s['action']}] {s['target']} — {'OK' if s['success'] else 'FAIL'}")

        print(f"\nDomBot traces stored (via pipeline): {len(trace_log)}")
        for t in trace_log:
            label = "SUCCESS" if t["success"] else "FAILED"
            print(f"  - {label} | {len(t['steps'])} steps")

    if result.final_result():
        print(f"\nAgent's answer: {result.final_result()}")


if __name__ == "__main__":
    asyncio.run(main())
