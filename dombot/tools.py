import logging

from browser_use import ActionResult, Tools
from pydantic import BaseModel, Field

from dombot.prompts import format_optimal_path

logger = logging.getLogger("dombot")

tools = Tools()


class DomBotQueryParams(BaseModel):
    task_description: str = Field(
        description="The current task the agent is trying to accomplish"
    )
    domain: str = Field(
        description="The domain of the current website (e.g. walmart.com)"
    )


class DomBotReportParams(BaseModel):
    task_description: str = Field(
        description="The current task the agent is trying to accomplish"
    )
    action_taken: str = Field(
        description="What action was performed (e.g. 'click', 'type', 'scroll')"
    )
    target_element: str = Field(
        description="Description of the element acted on (e.g. 'search input', 'Add to Cart button')"
    )
    success: bool = Field(description="Whether the action succeeded")
    current_url: str = Field(
        description="The current page URL after the action"
    )
    notes: str = Field(
        default="", description="Any relevant observations about the result"
    )


@tools.action(
    description="Query DomBot knowledge base for optimal actions from past successful runs. Call this FIRST before starting any task.",
    param_model=DomBotQueryParams,
)
async def dombot_query(params: DomBotQueryParams) -> ActionResult:
    """Query past successful runs for an optimal action path."""
    from dombot.db import query_context

    logger.info(f">>> dombot_query called | task={params.task_description!r} domain={params.domain!r}")

    result = query_context(params.task_description, params.domain)

    if result is None:
        logger.info(">>> dombot_query result: NO DATA (cold start)")
        return ActionResult(
            extracted_content=(
                "[DomBot] No prior data for this task. "
                "Proceed normally — your actions will be recorded for future runs."
            )
        )

    formatted = format_optimal_path(result)
    logger.info(f">>> dombot_query result: found path (confidence={result.confidence:.0%}, {len(result.optimal_actions)} actions)")
    return ActionResult(extracted_content=formatted)


@tools.action(
    description="Report step result to DomBot after each significant action. This helps DomBot learn optimal paths for future runs.",
    param_model=DomBotReportParams,
)
async def dombot_report(params: DomBotReportParams) -> ActionResult:
    """Report a completed step so DomBot can learn from it."""
    from dombot.db import store_step

    domain = params.current_url.split("/")[2] if "/" in params.current_url else params.current_url

    logger.info(
        f">>> dombot_report called | action={params.action_taken!r} "
        f"target={params.target_element!r} success={params.success} url={params.current_url}"
    )

    store_step(
        task=params.task_description,
        domain=domain,
        step={
            "action": params.action_taken,
            "target": params.target_element,
            "success": params.success,
            "url": params.current_url,
            "notes": params.notes,
        },
    )
    return ActionResult(extracted_content="[DomBot] Step recorded.")
