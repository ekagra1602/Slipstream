import os

_MILESTONE_ENABLED = os.getenv("DOMBOT_MILESTONE_PROMPTS", "1") != "0"

DOMBOT_SYSTEM_PROMPT = """
## DomBot Integration

You have access to DomBot, a knowledge base of optimal action paths from past successful runs.

RULES:
1. ALWAYS call dombot_query at the START of your task to check for known optimal paths.
2. If dombot_query returns optimal actions, follow them as your primary plan. Only deviate if the page state doesn't match what's expected.
3. After each significant action (click, type, navigate), call dombot_report to record the result.
4. If dombot_query returns "No prior data", proceed normally — your actions will be recorded for future runs.
5. Pay attention to the confidence score. High confidence (>0.8) means many agents have confirmed this path works. Low confidence means treat it as a suggestion, not a guarantee.
6. When actions are grouped into phases, complete each phase before moving to the next. Do not revisit completed phases.
7. Respect the retry budget for each phase. If you exceed the max attempts for a phase, move on to the next phase.
"""


# Phase definitions for milestone grouping.
# Each phase has action prefixes and target keywords used to classify actions.
MILESTONE_PHASES = [
    {
        "name": "SEARCH",
        "description": "Find the target item using search",
        "action_prefixes": ["type", "go_to_url", "search"],
        "target_keywords": ["search", "query", "input", "url"],
        "retry_budget": 3,
    },
    {
        "name": "SELECT",
        "description": "Choose the correct product from results",
        "action_prefixes": ["click"],
        "target_keywords": ["product", "result", "item", "link"],
        "retry_budget": 3,
    },
    {
        "name": "CART",
        "description": "Add to cart and verify",
        "action_prefixes": ["click"],
        "target_keywords": ["cart", "add", "bag", "basket"],
        "retry_budget": 2,
    },
    {
        "name": "EXTRACT",
        "description": "Extract final result or complete the task",
        "action_prefixes": ["extract", "click", "done"],
        "target_keywords": ["extract", "result", "price", "checkout", "complete", "finish"],
        "retry_budget": 2,
    },
]


def _classify_action(action: str, phase: dict) -> bool:
    """Check if an action string matches a milestone phase."""
    action_lower = action.lower()
    # Check action prefix match (e.g., "type:search_input" starts with "type")
    prefix_match = any(action_lower.startswith(p) for p in phase["action_prefixes"])
    if not prefix_match:
        return False
    # If phase has target keywords, require at least one keyword match
    if phase["target_keywords"]:
        return any(kw in action_lower for kw in phase["target_keywords"])
    return True


def _group_into_milestones(optimal_actions: list[str]) -> list[dict]:
    """Walk actions in order, assign each to the current or next phase.

    Phases advance forward-only (no going back). If an action doesn't match
    the current phase, try advancing to the next matching phase. Actions that
    don't match any remaining phase stay in the current phase.

    Returns list of {phase, actions} groups (only non-empty groups).
    """
    if not optimal_actions:
        return []

    phases = MILESTONE_PHASES
    groups = [{"phase": p, "actions": []} for p in phases]
    current_phase_idx = 0

    for action in optimal_actions:
        placed = False
        # Try current phase first
        if current_phase_idx < len(phases) and _classify_action(
            action, phases[current_phase_idx]
        ):
            groups[current_phase_idx]["actions"].append(action)
            placed = True
        else:
            # Try advancing to a later phase (forward-only)
            for i in range(current_phase_idx + 1, len(phases)):
                if _classify_action(action, phases[i]):
                    current_phase_idx = i
                    groups[i]["actions"].append(action)
                    placed = True
                    break
        # If no phase matched, keep it in the current phase
        if not placed and current_phase_idx < len(phases):
            groups[current_phase_idx]["actions"].append(action)

    # Return only non-empty groups
    return [g for g in groups if g["actions"]]


def format_optimal_path(result) -> str:
    """Format an OptimalPath result for LLM consumption.

    Args:
        result: An OptimalPath object from db.query_context() with fields:
            - domain (str)
            - confidence (float)
            - run_count (int)
            - task (str)
            - optimal_actions (list[str])
    """
    lines = [
        f"[DomBot] Found optimal path for similar task on {result.domain}",
        f"Confidence: {result.confidence:.0%} ({result.run_count} successful runs)",
        f'Similar task: "{result.task}"',
        "",
    ]
    exec_conf = getattr(result, "execution_confidence", None)
    contract_conf = getattr(result, "contract_confidence", None)
    if exec_conf is not None and contract_conf is not None:
        lines.insert(2, f"Execution/Contract confidence: {exec_conf:.0%} / {contract_conf:.0%}")

    milestones = _group_into_milestones(result.optimal_actions)

    if _MILESTONE_ENABLED and len(milestones) >= 2:
        # Milestone format with phase headers and retry budgets
        lines.append("Recommended workflow:")
        lines.append("")
        for i, group in enumerate(milestones, 1):
            phase = group["phase"]
            lines.append(
                f"Phase {i} — {phase['name']} (max {phase['retry_budget']} attempts):"
            )
            lines.append(f"  {phase['description']}")
            for action in group["actions"]:
                lines.append(f"  → {action}")
            lines.append("")
        lines.append(
            "RULES: Complete each phase before moving to the next. "
            "Do not revisit completed phases."
        )
    else:
        # Flat list fallback for single-group or unclassifiable paths
        lines.append("Recommended actions (in order):")
        for i, action in enumerate(result.optimal_actions, 1):
            lines.append(f"  {i}. {action}")

    # Cold-start guard: avoid emitting unstable path hints too early.
    # Before enough successful runs, guidance should be treated as weak context.
    if result.run_count < 3:
        lines.append("")
        lines.append(
            "Note: Learning is still warming up (<3 successful runs). "
            "Do not assume any cached answer is correct; verify live page state."
        )
        return "\n".join(lines)

    if result.confidence < 0.7:
        lines.append("")
        lines.append(
            "Note: Confidence is moderate. Verify each step matches the current page before proceeding."
        )

    return "\n".join(lines)
