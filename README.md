# DomBot

**A shared learning layer for browser automation agents.**

DomBot makes browser-use agents faster and more reliable by learning optimal action paths from every run. The first user fumbles through 72 steps. The 1000th user gets a pre-loaded 12-step path straight to the goal.

**Analogy:** Waze for web agents — every run makes the map better for everyone.

---

## How It Works

DomBot registers as a tool inside browser-use. Before the LLM decides what to do, the agent calls DomBot to check if anyone has successfully completed a similar task before. If yes, the optimal path gets injected into the LLM's context. After each step, the agent reports what happened back to DomBot.

```
browser-use prepares DOM / screenshot / accessibility tree
    |
    v
Agent calls dombot_query("buy macbook on walmart", "walmart.com")
    |
    v
DomBot queries MongoDB (vector search on task embedding)
    |-- hit  --> returns optimal actions from past successful runs
    |-- miss --> returns nothing (agent proceeds normally)
    |
    v
LLM decides next action (now informed by past runs)
    |
    v
browser-use executes action
    |
    v
Agent calls dombot_report(action, target, success)
    |
    v
DomBot stores step data in MongoDB
    |
    v
Repeat --> traces compound --> paths converge
```

### Over Time

```
Run 1:     72 steps, 3 wrong turns, eventually buys Macbook
Run 100:   45 steps, different user, different mistakes
Run 500:   optimal path emerges -- 12 steps, straight there
Run 501:   new user gets the 12-step path pre-loaded. Done.
```

---

## Integration

DomBot uses browser-use's `@controller.action` API — no monkey-patching, no subclassing:

```python
from browser_use import Agent, Browser, Controller
from dombot import register_dombot_tools

controller = Controller()
register_dombot_tools(controller)

agent = Agent(
    task="buy a macbook on walmart",
    llm=llm,
    browser=Browser(use_cloud=True),
    controller=controller,
)

await agent.run()
```

---

## Architecture

```
browser-use agent
    |
    |-- dombot_query tool  --> DomBot API --> MongoDB Atlas ($vectorSearch)
    |-- dombot_report tool --> DomBot API --> MongoDB Atlas (store step)
    |
Laminar (trace capture)
    |
    v
Trace processing pipeline --> MongoDB Atlas (update task nodes)
```

### Stack

| Component | Role |
|-----------|------|
| **browser-use** | Agent execution (`use_cloud=True` for stealth + CAPTCHA) |
| **MongoDB Atlas** | Storage + vector search (`$vectorSearch` on task embeddings) |
| **Laminar** | Trace capture (native browser-use integration) |
| **OpenAI Embeddings** | Embed task descriptions for similarity matching |

### MongoDB Schema

One document per task type:

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

---

## Project Structure

```
dombot/
  __init__.py
  tools.py           # @controller.action tools (dombot_query, dombot_report)
  db.py              # MongoDB connection, query_context, store_step, store_trace
  embeddings.py      # Task embedding via OpenAI
  prompts.py         # System prompt additions, optimal path formatting
  trace_pipeline.py  # Laminar traces --> MongoDB task nodes
  config.py          # Environment config (API keys, MongoDB URI)
scripts/
  demo.py            # Demo script: run agent with DomBot
  seed_db.py         # Seed MongoDB with sample task nodes
tests/
```

---

## Team

| Person | Scope | Key Deliverables |
|--------|-------|------------------|
| **Person 1** | browser-use integration + prompt design | `tools.py`, `prompts.py` — register DomBot tools, design system prompt, format optimal path output so the LLM actually follows it |
| **Person 2** | MongoDB + data layer | `db.py`, `embeddings.py` — Atlas setup, vector search index, `query_context()`, `store_step()`, `store_trace()`, confidence scoring |
| **Person 3** | Laminar + trace pipeline + demo | `trace_pipeline.py`, `scripts/demo.py` — Laminar instrumentation, trace processing, convergence logic, demo script |

### Shared Interfaces

```python
# Person 2 implements, Person 1 calls via tools
def query_context(task: str, domain: str) -> OptimalPath | None
def store_step(task: str, domain: str, step: StepData) -> None
def store_trace(task: str, domain: str, trace: list[StepData], success: bool) -> None
```

---

## Setup

```bash
# Clone
git clone <repo-url>
cd dombot

# Install
pip install -r requirements.txt

# Environment
cp .env.example .env
# Fill in: MONGODB_URI, OPENAI_API_KEY, LAMINAR_API_KEY, BROWSERUSE_API_KEY

# Run demo
python scripts/demo.py
```

---

## The Big Picture

DomBot is two products built on one shared database:

- **Consumer (DomBot Agent)** — Python package. Works on any site, no site owner buy-in. Agents learn from each other.
- **Business (DomBot Site)** — Site owners opt in for verified maps, analytics on agent traffic, and an Agent Readiness Score.

The shared trace database is the moat. Every run makes it smarter. Once you have 1M traces across 10,000 sites, optimal paths are baked in. A competitor starting from zero is years behind.

**This is the Google crawl index moment for AI agents.**
