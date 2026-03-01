#!/usr/bin/env python3
"""Seed MongoDB with sample task nodes from the POC data."""
from __future__ import annotations

import json
from pathlib import Path

from db.db import StepData, store_trace

SAMPLE_TRACES = Path(__file__).resolve().parent.parent / "poc" / "sample_traces.json"


def main() -> None:
    with SAMPLE_TRACES.open() as f:
        traces = json.load(f)

    for trace in traces:
        steps = [
            StepData(
                action=s["action"],
                target=s["target"],
                value=s.get("value"),
                success=True,
            )
            for s in trace["steps"]
        ]
        store_trace(
            task=trace["task"],
            domain=trace["domain"],
            trace=steps,
            success=trace["success"],
        )
        print(f"Stored trace {trace['trace_id']} (success={trace['success']})")

    print("Done seeding.")


if __name__ == "__main__":
    main()
