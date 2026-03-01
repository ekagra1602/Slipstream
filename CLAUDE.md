# DomBot — Project Context

## What This Project Is

DomBot is a shared learning layer for browser-use agents. It registers custom tools via `@controller.action` that let the agent query a knowledge base of past successful runs before deciding what to do, and report results after each step. Every run compounds into better paths for future users.

**One-line pitch:** "Waze for web agents — every run makes the map better for everyone."

---

## How It Works

DomBot does NOT do its own DOM extraction or Playwright calls. It piggybacks on what browser-use already produces (DOM, screenshots, accessibility tree). DomBot's role is:

1. **Before the LLM decides:** Agent calls `dombot_query` tool → DomBot queries MongoDB for similar past successful runs → returns optimal actions as context
2. **After each step:** Agent calls `dombot_report` tool → DomBot stores what happened (action, target, success/failure)
3. **After a run completes:** Trace pipeline processes the full run → updates the task node in MongoDB → confidence and optimal path improve

```
browser-use extracts DOM / screenshot / accessibility tree (as normal)
    ↓
Agent calls dombot_query(task, domain) → MongoDB $vectorSearch
    ↓
LLM sees: normal browser-use context + DomBot's optimal path from past runs
    ↓
LLM decides action
    ↓
browser-use executes
    ↓
Agent calls dombot_report(step_data) → MongoDB stores step
    ↓
Repeat
```

---

## Integration Pattern

Uses browser-use's `@controller.action` decorator. No subclassing, no middleware, no monkey-patching.

```python
from browser_use import Controller

controller = Controller()

@controller.action("Query DomBot for optimal actions based on past successful runs")
def dombot_query(task: str, domain: str) -> str:
    return db.query_context(task, domain)

@controller.action("Report step result to DomBot")
def dombot_report(task: str, domain: str, action: str, target: str, success: bool) -> str:
    db.store_step(task, domain, {"action": action, "target": target, "success": success})
    return "stored"
```

---

## Tech Stack

| Component | Role |
|-----------|------|
| **browser-use** | Agent execution, `use_cloud=True` for stealth + CAPTCHA solving |
| **MongoDB Atlas** | Storage + `$vectorSearch` on task embeddings |
| **Laminar** | Trace capture, native browser-use integration |
| **OpenAI Embeddings** | Embed task descriptions for vector similarity |

---

## MongoDB Schema

### `task_nodes` collection (one doc per task type)

```json
{
  "task": "buy a macbook on walmart",
  "task_embedding": [0.23, 0.41, "..."],
  "domain": "walmart.com",
  "run_count": 500,
  "confidence": 0.94,
  "optimal_actions": [
    "search 'Macbook'",
    "click first Electronics result",
    "click Add to cart",
    "proceed to checkout"
  ],
  "step_traces": [
    {
      "step": 1,
      "action": "type",
      "target": "search_input",
      "value": "Macbook",
      "success_rate": 0.97,
      "attempt_count": 485
    }
  ]
}
```

Retrieval is a single `$vectorSearch` query. No Graph RAG, no `$graphLookup` (research agents unanimously rejected both for v1).

---

## Project Structure

```
dombot/
  __init__.py
  tools.py           # @controller.action tools (dombot_query, dombot_report)
  db.py              # MongoDB connection, query_context, store_step, store_trace
  embeddings.py      # Task embedding via OpenAI
  prompts.py         # System prompt additions, optimal path formatting for LLM
  trace_pipeline.py  # Laminar traces → MongoDB task nodes
  config.py          # Environment config
scripts/
  demo.py            # Demo: run agent with DomBot
  seed_db.py         # Seed MongoDB with sample data
tests/
```

---

## Team Split

| Person | Owns | Key Files |
|--------|------|-----------|
| **Person 1** | browser-use tools + prompt design | `tools.py`, `prompts.py` |
| **Person 2** | MongoDB + data layer | `db.py`, `embeddings.py`, `config.py` |
| **Person 3** | Laminar + trace pipeline + demo | `trace_pipeline.py`, `scripts/demo.py` |

### Shared Contract (Person 2 implements, Person 1 calls)

```python
def query_context(task: str, domain: str) -> OptimalPath | None
def store_step(task: str, domain: str, step: StepData) -> None
def store_trace(task: str, domain: str, trace: list[StepData], success: bool) -> None
```

---

## Key Design Decisions

1. **Tool-based integration, not middleware** — Uses `@controller.action`, not Agent subclassing. Cleaner, future-proof, works with cloud API.
2. **Node = task, not page** — Each MongoDB document represents a task (e.g., "buy macbook on walmart"), not a page state. Vector search finds the right task node.
3. **No Graph RAG for v1** — Research concluded that `$graphLookup` can't do weighted shortest path and Graph RAG is premature. Simple denormalized documents + vector search covers the MVP.
4. **Laminar for trace capture** — Native browser-use integration, SQL API for programmatic trace extraction. Runs on our infrastructure, invisible to consumers.
5. **`use_cloud=True`** — Gets browser-use cloud stealth (anti-detect, CAPTCHA, proxies) while keeping full SDK control.

---

## Two-Product Strategy (Future)

- **Consumer (DomBot Agent)** — Python package wrapping browser-use. Works on any site. Agents learn from each other's runs.
- **Business (DomBot Site)** — Site owners opt in for verified DOM maps at `/.well-known/dombot/map`, agent traffic analytics, Agent Readiness Score.

The consumer product is the wedge. The business product is the upsell.

---

## Notion Pages

Parent: https://www.notion.so/315fe709905c8066b044fb0377131bfc

| Page | ID | Summary |
|------|----|---------|
| BrowserUse (root) | `315fe709-905c-8066-b044-fb0377131bfc` | Parent page |
| First prototype | `315fe709-905c-80ac-b2c3-e90c1e439810` | Full spec, MVP scope |
| Dombot | `315fe709-905c-805d-bee3-ed3f2e71ef76` | Map generator, deploy flow |
| Consumer Product & Pre-Flight Crawl | `315fe709-905c-81ab-860d-c0304d9796c0` | Two-product strategy, caching |
| DomBot Integration | `315fe709-905c-81af-8273-e7e1147c52a4` | browser-use integration paths |
| MVP1 Architecture | `316fe709-905c-81c1-8451-c1288136d054` | Full MVP1 technical spec |
| Research: Web Agent Hackathon | `314fe709-905c-8122-9762-fc810cbe80fa` | Failure landscape, opportunities |
