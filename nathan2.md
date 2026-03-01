# Nathan — Laminar + Trace Pipeline

## How Laminar works with browser-use

### Setup — one call before the agent runs
```python
from lmnr import Laminar, LaminarClient

Laminar.initialize(project_api_key=os.getenv("LMNR_PROJECT_API_KEY"))
```
That's it. Laminar auto-instruments browser-use — every agent step, LLM call, and browser action becomes a span automatically. No extra config.

---

## What Laminar captures per run

Two key tables:

| Table | What it is |
|---|---|
| `traces` | One row per agent run — has `status` (`ok`/`error`), cost, duration, `trace_id` |
| `spans` | One row per step/action — has `name`, `span_type`, `status`, `input`, `output` |

Span types that matter:
- **`TOOL`** spans = browser-use actions (`click`, `type`, `navigate`, etc.)
- **`DEFAULT`** spans = `agent.step.1`, `agent.step.2`, etc. (each reasoning loop)
- **`LLM`** spans = individual LLM calls

**Success/failure per step** = `span.status == "ok"` vs `"error"`. That's the signal.

---

## How to capture trace_id and query it after a run

```python
from lmnr import Laminar, LaminarClient, observe

@observe()
async def run_agent(task, domain):
    agent = Agent(task=task, llm=llm)
    history = await agent.run()
    trace_id = Laminar.get_trace_id()   # capture while still in span
    return history, trace_id

history, trace_id = await run_agent(task, domain)
Laminar.flush()  # ensure spans are sent before querying

client = LaminarClient(project_api_key=os.getenv("LMNR_PROJECT_API_KEY"))
steps = client.sql.query(
    sql="""
    SELECT name, status, input, output, duration
    FROM spans
    WHERE trace_id = {trace_id:String}
      AND span_type = 'TOOL'
    ORDER BY start_time ASC
    """,
    parameters={"trace_id": str(trace_id)}
)
```

---

## What each step row looks like

```python
{
  "name": "click",             # the action
  "status": "ok",              # "ok" or "error" → success/failure
  "input": '{"action": "click", "params": {"selector": "..."}}',
  "output": '{"is_done": false, "extracted_content": null, "error": null}',
  "duration": 0.43             # seconds
}
```

---

## The full pipeline

```
1. @observe() wrapper → captures trace_id after agent.run()
2. Laminar.flush()   → ensure all spans sent before querying
3. client.sql.query() → pull TOOL spans ordered by start_time
4. Parse each span: name, status→success, input→action+target+value
5. Determine overall success (traces.status == "ok")
6. Call Eric's store_trace(task, domain, parsed_steps, success)
```

---

## What you call (Eric's contract)

```python
store_trace(task: str, domain: str, trace: list[StepData], success: bool) -> None
```

Where `StepData` is:
```python
{
  "action": "click",
  "target": "search_input",
  "value": "Macbook",       # optional
  "success": True
}
```

---

## Files to build

| File | What it does |
|------|--------------|
| `dombot/trace_pipeline.py` | Main pipeline: @observe wrapper, flush, SQL query, parse, call store_trace |
| `scripts/demo.py` | Wires everything together end to end |
