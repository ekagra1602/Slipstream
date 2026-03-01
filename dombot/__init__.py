"""Package exports with lazy imports.

Avoid importing heavy optional dependencies (e.g., browser_use) during package
initialization. This keeps server-only contexts (like Vercel API functions)
from crashing at import time.
"""

from __future__ import annotations

from typing import Any

__all__ = ["tools", "DOMBOT_SYSTEM_PROMPT", "initialize_laminar", "process_trace"]


def __getattr__(name: str) -> Any:
    if name == "tools":
        from dombot.tools import tools as _tools

        return _tools
    if name == "DOMBOT_SYSTEM_PROMPT":
        from dombot.prompts import DOMBOT_SYSTEM_PROMPT as _prompt

        return _prompt
    if name == "initialize_laminar":
        from dombot.trace_pipeline import initialize_laminar as _initialize_laminar

        return _initialize_laminar
    if name == "process_trace":
        from dombot.trace_pipeline import process_trace as _process_trace

        return _process_trace
    raise AttributeError(f"module 'dombot' has no attribute {name!r}")
