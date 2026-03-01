# Nathan — Laminar + Trace Pipeline (Revised Plan)

## Scope
Nathan owns how raw agent runs become useful data in MongoDB:
- Laminar instrumentation setup
- Trace extraction + parsing
- Step-level and run-level success labeling
- Cross-run convergence signals
- Handoff to Eric's `store_trace()`

---

## Architecture

### 1. Instrumentation

Initialize Laminar once at process startup. Disable `BROWSER_USE_SESSION` — it is
unstable with `use_cloud=True` and low-level local spans may be missing.

```python
from lmnr import Laminar

Laminar.initialize(
    project_api_key=os.getenv("LMNR_PROJECT_API_KEY"),
    disabled_instruments={"BROWSER_USE_SESSION"},  # unstable with use_cloud=True
)
```

Wrap `agent.run()` with `@observe()` and capture `trace_id` via closure into
`register_done_callback` — the existing hook in `demo.py` that fires after every run:

```python
from lmnr import Laminar, observe

@observe()
async def run_agent(task: str, domain: str, tools, system_prompt: str):
    trace_id_holder: dict = {}

    async def on_done(history):
        # Still inside the @observe() span — get_trace_id() works here
        trace_id_holder["id"] = Laminar.get_trace_id()
        await process_trace(history, trace_id_holder["id"], task, domain)

    agent = Agent(
        task=task,
        browser=Browser(use_cloud=True),
        tools=tools,
        extend_system_message=system_prompt,
        register_done_callback=on_done,
    )
    return await agent.run()
```

**Trigger policy:** The pipeline is triggered exclusively via `register_done_callback`
— the browser-use hook that fires at the end of every `agent.run()`. There is no
separate scheduler, no polling, no post-hoc batch job. `demo.py` already wires this
hook; the pipeline replaces the placeholder `on_done` body there.

**`trace_id` capture guarantee:** `register_done_callback` fires synchronously before
`agent.run()` returns, meaning it executes while still inside the `@observe()` span.
`Laminar.get_trace_id()` reads the active OpenTelemetry context, which is still live
at that point. The closure pattern (`trace_id_holder`) passes it out to the caller if
needed for logging. Do not call `Laminar.get_trace_id()` after `agent.run()` returns
— the span context will have been exited and it will return `None`.

---

### 2. Canonical Models

```python
@dataclass
class NormalizedStep:
    step_idx: int
    action_type: str        # "click", "type", "navigate", etc.
    target: str             # selector or element description
    value: str | None       # typed value if applicable
    url: str
    latency_ms: int
    success: bool
    failure_reason: str | None   # "selector" | "navigation" | "auth" | "timeout" | "unknown"
    raw_input: str          # original JSON from Laminar span
    raw_output: str         # original JSON from Laminar span

@dataclass
class NormalizedTrace:
    trace_id: str
    task: str
    domain: str
    success: bool           # run-level gate (see section 3)
    partial: bool           # True if run ended mid-task without explicit completion
    steps: list[NormalizedStep]

@dataclass
class TaskAggregate:
    domain: str
    task: str
    run_count: int
    success_rate: float
    optimal_actions: list[str]
    confidence: float
```

---

### 3. Run-Level Success Gate

**Step-level success** (`span.status == "ok"`) is not sufficient alone.
A run is considered successful only when ALL of the following are true:

1. `traces.status == "ok"` (no unhandled exception in the run)
2. At least one `TOOL` span has `output` containing `"is_done": true` — meaning
   browser-use explicitly signaled task completion
3. Step count is above a minimum threshold (guards against trivially short runs)

If condition 2 or 3 fails but condition 1 passes → mark `partial=True`.
Partial runs are stored as raw traces but **not promoted** to `optimal_actions`.

```python
def determine_run_success(trace_row: dict, tool_spans: list[dict]) -> tuple[bool, bool]:
    """Returns (success, partial)."""
    if trace_row["status"] != "ok":
        return False, False
    completed = any(
        '"is_done": true' in s.get("output", "") for s in tool_spans
    )
    if not completed:
        return False, True   # ran without error but never finished — partial
    return True, False
```

---

### 4. Extraction with Retry + Idempotency

After `agent.run()` completes, flush and query with retry — spans may lag:

```python
import time
from lmnr import LaminarClient

client = LaminarClient(project_api_key=os.getenv("LMNR_PROJECT_API_KEY"))

def fetch_spans(trace_id: str, retries: int = 3, delay: float = 2.0) -> list[dict]:
    """Fetch TOOL spans for a trace. Retries if spans not yet available."""
    Laminar.flush()
    for attempt in range(retries):
        spans = client.sql.query(
            sql="""
            SELECT name, status, input, output, start_time, duration
            FROM spans
            WHERE trace_id = {trace_id:String}
              AND span_type = 'TOOL'
            ORDER BY start_time ASC
            """,
            parameters={"trace_id": trace_id},
        )
        if spans:
            return spans
        if attempt < retries - 1:
            time.sleep(delay)
    return []   # no spans found after retries — caller handles gracefully

def fetch_trace_row(trace_id: str) -> dict | None:
    rows = client.sql.query(
        sql="SELECT status FROM traces WHERE id = {trace_id:String}",
        parameters={"trace_id": trace_id},
    )
    return rows[0] if rows else None
```

**Idempotency guard:** before calling `store_trace()`, check if `trace_id` has
already been processed. Eric's `store_trace()` should be idempotent on `trace_id`,
but the pipeline also keeps a local set of processed IDs in the session to prevent
double-calls on retry.

---

### 5. Labeling — Failure Taxonomy

```python
def label_step(span: dict) -> NormalizedStep:
    success = span["status"] == "ok"
    failure_reason = None
    if not success:
        output = span.get("output", "")
        if "selector" in output or "element" in output:
            failure_reason = "selector"
        elif "navigation" in output or "timeout" in output:
            failure_reason = "navigation"
        elif "auth" in output or "login" in output:
            failure_reason = "auth"
        elif "timeout" in output:
            failure_reason = "timeout"
        else:
            failure_reason = "unknown"

    raw_input = span.get("input", "{}")
    parsed = json.loads(raw_input)
    action_type = span["name"]
    target = parsed.get("params", {}).get("selector", "unknown")
    value = parsed.get("params", {}).get("value")

    return NormalizedStep(
        step_idx=...,        # derived from order in sorted spans
        action_type=action_type,
        target=target,
        value=value,
        url=parsed.get("params", {}).get("url", ""),
        latency_ms=int(span["duration"] * 1000),
        success=success,
        failure_reason=failure_reason,
        raw_input=raw_input,
        raw_output=span.get("output", "{}"),
    )
```

---

### 6. Convergence Signals (Nathan computes, Eric persists)

Nathan computes and passes these to `store_trace()`. Eric owns final merge into MongoDB.

**Grouping:** Nathan groups traces by exact `(domain, task)` string — no fuzzy
matching, no intent normalization here. Grouping similar tasks across different phrasings
(e.g. "buy a macbook" vs "purchase macbook") is handled by Eric's vector embedding layer,
not by this pipeline.

```python
CONVERGENCE_MIN_RUNS = 5          # don't promote until at least 5 successful runs
CONVERGENCE_MIN_SUCCESS_RATE = 0.6
CONVERGENCE_PATH_CONSISTENCY = 0.5  # fraction of runs where a step appears at same position
```

The optimal action sequence = steps that appear at the same position in at least
`CONVERGENCE_PATH_CONSISTENCY` of successful runs.

---

### 7. Handoff to Eric

```python
def build_step_data(step: NormalizedStep) -> dict:
    return {
        "action": step.action_type,
        "target": step.target,
        "value": step.value,
        "success": step.success,
    }

# Called after each completed run:
store_trace(
    task=trace.task,
    domain=trace.domain,
    trace=[build_step_data(s) for s in trace.steps],
    success=trace.success,
)
```

Partial runs (`trace.partial == True`) are stored with `success=False` and are
used for failure analysis but not promoted to `optimal_actions`.

---

## Files to Build

| File | What it does |
|------|--------------|
| `dombot/trace_pipeline.py` | All of the above: init, extract, label, converge, handoff |
| `scripts/demo.py` | Already exists — update `on_done` to call pipeline + add `@observe()` wrapper |

---

## Real-Time vs Batch

| Path | When | Purpose |
|------|------|---------|
| `dombot_report` (@tools.action) | Per step, live | Immediate operational data |
| Laminar pipeline | After each `agent.run()` completes | Authoritative batch analysis for convergence |

---

## Build Order

1. Canonical models (`NormalizedStep`, `NormalizedTrace`)
2. Laminar init module with instrument toggles
3. `fetch_spans()` with retry + `fetch_trace_row()`
4. `label_step()` + failure taxonomy
5. Run-level success gate
6. `store_trace()` handoff + idempotency guard
7. Fixture-based tests for each stage
8. `scripts/demo.py` end-to-end wiring
