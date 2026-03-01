DOMBOT_SYSTEM_PROMPT = """
## DomBot Integration

You have access to DomBot, a knowledge base of optimal action paths from past successful runs.

RULES:
1. ALWAYS call dombot_query at the START of your task to check for known optimal paths.
2. If dombot_query returns optimal actions, follow them as your primary plan. Only deviate if the page state doesn't match what's expected.
3. After each significant action (click, type, navigate), call dombot_report to record the result.
4. If dombot_query returns "No prior data", proceed normally — your actions will be recorded for future runs.
5. Pay attention to the confidence score. High confidence (>0.8) means many agents have confirmed this path works. Low confidence means treat it as a suggestion, not a guarantee.
"""


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
        "Recommended actions (in order):",
    ]
    for i, action in enumerate(result.optimal_actions, 1):
        lines.append(f"  {i}. {action}")

    if result.confidence < 0.7:
        lines.append("")
        lines.append(
            "Note: Confidence is moderate. Verify each step matches the current page before proceeding."
        )

    return "\n".join(lines)
