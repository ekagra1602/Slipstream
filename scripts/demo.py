"""
Demo: Run a browser-use agent with DomBot tools.

Visually confirms the agent calls dombot_query and dombot_report during a live run.

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

from dotenv import load_dotenv

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

# ── Imports ─────────────────────────────────────────────────────────────────

from browser_use import Agent, Browser

from dombot.db import get_step_log, get_trace_log, seed_task_node, store_trace
from dombot.prompts import DOMBOT_SYSTEM_PROMPT
from dombot.tools import tools

TASK = "Go to google.com and search for 'DomBot browser automation' and tell me the first result title"


async def on_step(browser_state, model_output, step_number):
    """Fires after every agent step — log it so we see the agent's decisions."""
    if model_output and model_output.action:
        actions = [a.__class__.__name__ for a in model_output.action]
        logger.info(f"Agent step #{step_number}: {actions}")


async def on_done(history):
    """Post-run callback: store the full trace.

    history is an AgentHistoryList — iterate history.history for AgentHistory items.
    """
    steps = []
    items = history.history if hasattr(history, "history") else history

    for item in items:
        if item.model_output and item.model_output.action:
            for action in item.model_output.action:
                action_data = action.model_dump(exclude_unset=True)
                action_name = next(iter(action_data.keys()), "unknown")
                steps.append(
                    {
                        "action": action_name,
                        "details": action_data.get(action_name, {}),
                    }
                )

    success = len(items) > 0 and items[-1].model_output is not None
    store_trace(task=TASK, domain="google.com", trace=steps, success=success)
    logger.info(f"Trace stored: {len(steps)} steps, success={success}")


async def main():
    # ── Pre-flight checks ───────────────────────────────────────────────────
    bu_key = os.getenv("BROWSER_USE_API_KEY")

    if not bu_key:
        print("ERROR: Set BROWSER_USE_API_KEY in .env (needed for cloud browser + LLM)")
        sys.exit(1)

    logger.info("BROWSER_USE_API_KEY loaded OK")

    # ── Optional: seed data so dombot_query returns something on first run ──
    # Comment this out to test the cold-start path instead.
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

    # ── Run the agent ───────────────────────────────────────────────────────
    # llm=None → browser-use uses its built-in ChatBrowserUse LLM (powered by BROWSERUSE_API_KEY)
    # No separate OpenAI key needed.
    browser = Browser(use_cloud=True)

    agent = Agent(
        task=TASK,
        browser=browser,
        tools=tools,
        extend_system_message=DOMBOT_SYSTEM_PROMPT,
        register_new_step_callback=on_step,
        register_done_callback=on_done,
    )

    print()
    print("=" * 60)
    print(f"Task: {TASK}")
    print(f"DomBot tools: dombot_query, dombot_report")
    print(f"Watch for '>>> dombot_query called' and '>>> dombot_report called' in the logs")
    print("=" * 60)
    print()

    result = await agent.run()

    # ── Post-run summary ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("RUN COMPLETE")
    print("=" * 60)
    print(f"Steps: {len(result.history)}")
    print()

    step_log = get_step_log()
    trace_log = get_trace_log()

    print(f"DomBot steps recorded: {len(step_log)}")
    for i, s in enumerate(step_log, 1):
        print(f"  {i}. [{s['action']}] {s['target']} — {'OK' if s['success'] else 'FAIL'}")

    print(f"\nDomBot traces stored: {len(trace_log)}")

    if result.final_result():
        print(f"\nAgent's answer: {result.final_result()}")

    await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
