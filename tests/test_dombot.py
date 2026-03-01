"""
End-to-end tests for DomBot tools, prompts, and mock DB.

Simulates the full lifecycle:
  1. Cold start — no data, agent explores
  2. Seed data — optimal path returned and formatted
  3. Report steps — stored in DB
  4. Store trace — full run recorded
  5. Edge cases — low confidence, domain mismatch, etc.

Run (opt-in UI/runtime path):
  DOMBOT_RUN_UI_TESTS=1 python -m pytest tests/test_dombot.py -q
  DOMBOT_RUN_UI_TESTS=1 python tests/test_dombot.py
"""

import asyncio
import os
import sys

if "pytest" in sys.modules:
    import pytest

    pytestmark = pytest.mark.ui_dependent
    if os.getenv("DOMBOT_RUN_UI_TESTS") != "1":
        pytest.skip(
            "Set DOMBOT_RUN_UI_TESTS=1 to run tests/test_dombot.py",
            allow_module_level=True,
        )

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dombot.db import (
    OptimalPath,
    clear_store,
    get_step_log,
    get_trace_log,
    seed_task_node,
    store_trace,
)
from dombot.prompts import DOMBOT_SYSTEM_PROMPT, format_optimal_path
from dombot.tools import (
    DomBotQueryParams,
    DomBotReportParams,
    dombot_query,
    dombot_report,
    tools,
)

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}{f' — {detail}' if detail else ''}")


# ── Test 1: Tools register with browser-use ────────────────────────────────

def test_tools_registered():
    print("\n[Test 1] Tools register with browser-use")
    actions = list(tools.registry.registry.actions.keys())
    check("dombot_query registered", "dombot_query" in actions)
    check("dombot_report registered", "dombot_report" in actions)
    check(
        "built-in actions still present",
        "click" in actions and "input" in actions and "navigate" in actions,
    )
    check(
        "tools are additive (not replacing built-ins)",
        len(actions) > 20,
        f"got {len(actions)} actions",
    )


# ── Test 2: Cold start — no prior data ─────────────────────────────────────

async def test_cold_start():
    print("\n[Test 2] Cold start — dombot_query with no prior data")
    clear_store()

    result = await dombot_query(
        params=DomBotQueryParams(
            task_description="buy a TV on bestbuy.com",
            domain="bestbuy.com",
        )
    )

    check("returns ActionResult", result is not None)
    check(
        "says no prior data",
        "No prior data" in result.extracted_content,
        result.extracted_content,
    )
    check(
        "says proceed normally",
        "Proceed normally" in result.extracted_content,
    )


# ── Test 3: Seeded data — optimal path returned ────────────────────────────

async def test_seeded_query():
    print("\n[Test 3] Seeded data — dombot_query returns optimal path")
    clear_store()

    seed_task_node(
        task="buy a macbook on walmart",
        domain="walmart.com",
        confidence=0.94,
        run_count=500,
        optimal_actions=[
            "Type 'Macbook' into search input",
            "Click first result in Electronics category",
            "Click 'Add to Cart' button",
            "Click 'Proceed to checkout'",
        ],
    )

    result = await dombot_query(
        params=DomBotQueryParams(
            task_description="buy a macbook on walmart",
            domain="walmart.com",
        )
    )

    content = result.extracted_content
    check("contains [DomBot] header", "[DomBot] Found optimal path" in content)
    check("contains confidence", "94%" in content)
    check("contains run count", "500 successful runs" in content)
    check("contains task description", "buy a macbook on walmart" in content)
    check("contains first action", "Macbook" in content and "search input" in content)
    check("contains all 4 actions", content.count("→") >= 4, f"found {content.count('→')} action arrows")
    check(
        "no low-confidence warning (94% > 70%)",
        "Confidence is moderate" not in content,
    )


# ── Test 4: Low confidence warning ─────────────────────────────────────────

async def test_low_confidence():
    print("\n[Test 4] Low confidence path includes warning")
    clear_store()

    seed_task_node(
        task="book a flight on delta",
        domain="delta.com",
        confidence=0.55,
        run_count=12,
        optimal_actions=["Search for flights", "Select departure"],
    )

    result = await dombot_query(
        params=DomBotQueryParams(
            task_description="book a flight on delta",
            domain="delta.com",
        )
    )

    content = result.extracted_content
    check("contains confidence 55%", "55%" in content)
    check(
        "contains moderate confidence warning",
        "Confidence is moderate" in content,
    )
    check(
        "tells agent to verify steps",
        "Verify each step" in content,
    )


# ── Test 5: dombot_report stores steps ─────────────────────────────────────

async def test_report_stores_steps():
    print("\n[Test 5] dombot_report stores steps correctly")
    clear_store()

    r1 = await dombot_report(
        params=DomBotReportParams(
            task_description="buy a macbook on walmart",
            action_taken="type",
            target_element="search input",
            success=True,
            current_url="https://www.walmart.com/",
            notes="Typed search query",
        )
    )

    check("returns step recorded", "[DomBot] Step recorded" in r1.extracted_content)

    await dombot_report(
        params=DomBotReportParams(
            task_description="buy a macbook on walmart",
            action_taken="click",
            target_element="Add to Cart button",
            success=True,
            current_url="https://www.walmart.com/product/12345",
        )
    )

    await dombot_report(
        params=DomBotReportParams(
            task_description="buy a macbook on walmart",
            action_taken="click",
            target_element="checkout link",
            success=False,
            current_url="https://www.walmart.com/cart",
            notes="Element not found — page layout changed",
        )
    )

    log = get_step_log()
    check("3 steps stored", len(log) == 3, f"got {len(log)}")

    step1 = log[0]
    check("step 1 action is 'type'", step1["action"] == "type")
    check("step 1 target is 'search input'", step1["target"] == "search input")
    check("step 1 success is True", step1["success"] is True)
    check("step 1 domain extracted from URL", step1["domain"] == "walmart.com")
    check("step 1 notes preserved", step1["notes"] == "Typed search query")

    step3 = log[2]
    check("step 3 success is False", step3["success"] is False)
    check("step 3 failure note preserved", "page layout changed" in step3["notes"])


# ── Test 6: store_trace records full run ────────────────────────────────────

def test_store_trace():
    print("\n[Test 6] store_trace records full run")
    clear_store()

    trace = [
        {"action": "type", "target": "search input", "success": True},
        {"action": "click", "target": "first result", "success": True},
        {"action": "click", "target": "Add to Cart", "success": True},
    ]
    store_trace(
        task="buy a macbook on walmart",
        domain="walmart.com",
        trace=trace,
        success=True,
    )

    log = get_trace_log()
    check("1 trace stored", len(log) == 1, f"got {len(log)}")
    check("trace has 3 steps", len(log[0]["steps"]) == 3)
    check("trace marked as success", log[0]["success"] is True)
    check("trace has correct task", log[0]["task"] == "buy a macbook on walmart")

    # Store a failed trace
    store_trace(
        task="buy a macbook on walmart",
        domain="walmart.com",
        trace=[{"action": "click", "target": "broken link", "success": False}],
        success=False,
    )
    log = get_trace_log()
    check("2 traces stored total", len(log) == 2)
    check("second trace marked as failure", log[1]["success"] is False)


# ── Test 7: Fuzzy matching (simulated vector search) ───────────────────────

async def test_fuzzy_matching():
    print("\n[Test 7] Fuzzy task matching (simulates vector search)")
    clear_store()

    seed_task_node(
        task="buy a macbook on walmart",
        domain="walmart.com",
        confidence=0.9,
        run_count=100,
        optimal_actions=["Search", "Click", "Add to cart"],
    )

    # Query with slightly different phrasing — substring match should work
    result = await dombot_query(
        params=DomBotQueryParams(
            task_description="buy a macbook on walmart and check out",
            domain="walmart.com",
        )
    )
    check(
        "substring match finds similar task",
        "Found optimal path" in result.extracted_content,
    )

    # Query with completely different task on same domain
    result2 = await dombot_query(
        params=DomBotQueryParams(
            task_description="buy headphones on walmart",
            domain="walmart.com",
        )
    )
    check(
        "different task returns no data",
        "No prior data" in result2.extracted_content,
    )

    # Query with matching task on wrong domain
    result3 = await dombot_query(
        params=DomBotQueryParams(
            task_description="buy a macbook on walmart",
            domain="amazon.com",
        )
    )
    check(
        "wrong domain returns no data",
        "No prior data" in result3.extracted_content,
    )


# ── Test 8: format_optimal_path edge cases ─────────────────────────────────

def test_format_edge_cases():
    print("\n[Test 8] format_optimal_path edge cases")

    # Single action
    single = OptimalPath(
        task="simple task",
        domain="example.com",
        confidence=0.99,
        run_count=1000,
        optimal_actions=["Do the thing"],
    )
    out = format_optimal_path(single)
    check("single action formatted", "1. Do the thing" in out)
    check("no action #2", "2." not in out)

    # Exactly 70% confidence — should NOT trigger warning (< 0.7 triggers it)
    boundary = OptimalPath(
        task="boundary test",
        domain="example.com",
        confidence=0.7,
        run_count=50,
        optimal_actions=["Step 1"],
    )
    out = format_optimal_path(boundary)
    check(
        "70% confidence has no warning (threshold is < 0.7)",
        "Confidence is moderate" not in out,
    )

    # 69% — should trigger
    low = OptimalPath(
        task="low test",
        domain="example.com",
        confidence=0.69,
        run_count=10,
        optimal_actions=["Step 1"],
    )
    out = format_optimal_path(low)
    check("69% triggers warning", "Confidence is moderate" in out)

    # Empty actions list
    empty = OptimalPath(
        task="empty task",
        domain="example.com",
        confidence=0.8,
        run_count=5,
        optimal_actions=[],
    )
    out = format_optimal_path(empty)
    check("empty actions still formats", "Recommended actions" in out)
    check("no numbered items", "1." not in out)


# ── Test 9: System prompt content ───────────────────────────────────────────

def test_system_prompt():
    print("\n[Test 9] System prompt content")
    check("mentions dombot_query", "dombot_query" in DOMBOT_SYSTEM_PROMPT)
    check("mentions dombot_report", "dombot_report" in DOMBOT_SYSTEM_PROMPT)
    check("says call at START", "START" in DOMBOT_SYSTEM_PROMPT)
    check("mentions confidence", "confidence" in DOMBOT_SYSTEM_PROMPT.lower())
    check(
        "says to follow optimal path",
        "follow them" in DOMBOT_SYSTEM_PROMPT,
    )
    check("has 7 rules", DOMBOT_SYSTEM_PROMPT.count("\n1.") == 1 and "7." in DOMBOT_SYSTEM_PROMPT)


# ── Test 10: Full lifecycle simulation ──────────────────────────────────────

async def test_full_lifecycle():
    print("\n[Test 10] Full lifecycle — cold start → explore → seed → follow path")
    clear_store()

    # --- Run 1: Cold start, no data ---
    print("  --- Simulating Run 1 (cold start) ---")
    q1 = await dombot_query(
        params=DomBotQueryParams(
            task_description="search for MacBook Pro on amazon.com",
            domain="amazon.com",
        )
    )
    check("run 1: no prior data", "No prior data" in q1.extracted_content)

    # Agent explores, reports steps
    steps_run1 = [
        ("type", "search bar", True, "https://www.amazon.com/", "Searched for MacBook Pro"),
        ("click", "first search result", True, "https://www.amazon.com/dp/B0SOMETHING", ""),
        ("extract", "price element", True, "https://www.amazon.com/dp/B0SOMETHING", "Price: $1,999"),
    ]
    for action, target, success, url, notes in steps_run1:
        await dombot_report(
            params=DomBotReportParams(
                task_description="search for MacBook Pro on amazon.com",
                action_taken=action,
                target_element=target,
                success=success,
                current_url=url,
                notes=notes,
            )
        )

    log = get_step_log()
    check("run 1: 3 steps recorded", len(log) == 3, f"got {len(log)}")

    # Post-run: store trace
    store_trace(
        task="search for MacBook Pro on amazon.com",
        domain="amazon.com",
        trace=[{"action": a, "target": t, "success": s} for a, t, s, _, _ in steps_run1],
        success=True,
    )
    check("run 1: trace stored", len(get_trace_log()) == 1)

    # --- Between runs: seed the DB with what we learned ---
    # (In production, Person 2's trace_pipeline would do this automatically)
    seed_task_node(
        task="search for MacBook Pro on amazon.com",
        domain="amazon.com",
        confidence=0.85,
        run_count=1,
        optimal_actions=[
            "Type 'MacBook Pro' into search bar",
            "Click first search result",
            "Extract price from product page",
        ],
    )

    # --- Run 2: Data exists, agent should follow path ---
    print("  --- Simulating Run 2 (with data) ---")
    clear_store()  # clear step log but re-seed
    seed_task_node(
        task="search for MacBook Pro on amazon.com",
        domain="amazon.com",
        confidence=0.85,
        run_count=1,
        optimal_actions=[
            "Type 'MacBook Pro' into search bar",
            "Click first search result",
            "Extract price from product page",
        ],
    )

    q2 = await dombot_query(
        params=DomBotQueryParams(
            task_description="search for MacBook Pro on amazon.com",
            domain="amazon.com",
        )
    )
    check("run 2: optimal path returned", "Found optimal path" in q2.extracted_content)
    check("run 2: shows 3 recommended actions", q2.extracted_content.count("→") >= 3)
    check("run 2: confidence shown", "85%" in q2.extracted_content)

    # Agent follows the path, reports steps
    for action, target, success, url, notes in steps_run1:
        await dombot_report(
            params=DomBotReportParams(
                task_description="search for MacBook Pro on amazon.com",
                action_taken=action,
                target_element=target,
                success=success,
                current_url=url,
                notes=notes,
            )
        )

    check("run 2: steps recorded", len(get_step_log()) == 3)

    # What the LLM would actually see:
    print("\n  --- What the LLM sees from dombot_query ---")
    print(q2.extracted_content)


# ── Run all tests ───────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("DomBot Integration Tests")
    print("=" * 60)

    test_tools_registered()
    await test_cold_start()
    await test_seeded_query()
    await test_low_confidence()
    await test_report_stores_steps()
    test_store_trace()
    await test_fuzzy_matching()
    test_format_edge_cases()
    test_system_prompt()
    await test_full_lifecycle()

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
