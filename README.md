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
```

## Mongo Write Smoke Test

Quick write/read check without `pymongo` (uses `mongosh` + `.env`):

```bash
source .venv/bin/activate
python scripts/check_mongo_write.py
```

If you want the direct `pymongo` check, make sure these imports are present:

```python
import os
from pymongo import MongoClient
```

## Launch Quality Gate

Run the blocking launch checks (syntax, lint, formatting, and core tests):

```bash
python scripts/quality_gate.py
```

Install local hook enforcement (runs the same gate on commit):

```bash
pip install -r requirements-dev.txt
npm install
pre-commit install
```

Default blocking pytest scope excludes opt-in suites:
- `tests/test_db_live.py` (`live_db` marker)
- `tests/test_dombot.py` (`ui_dependent` marker)

Run optional suites explicitly:

```bash
DOMBOT_RUN_LIVE_DB_TESTS=1 python -m pytest tests/test_db_live.py -q -m live_db
DOMBOT_RUN_UI_TESTS=1 python -m pytest tests/test_dombot.py -q -m ui_dependent
```

## Caching and Invalidation Strategy

DomBot uses a structural cache key:

`(domain, route_pattern, structural_hash(page))`

Where `structural_hash` is derived from interactive structure (roles, labels, relative positions), not volatile content like prices.

- Hash match -> cache hit -> reuse NodeMap
- Hash miss -> extract fresh map -> cache new entry

Important property: old entries are not force-invalidated; they naturally expire by TTL while exact-match lookups prevent stale map reuse.

## Route Pattern Normalization

Equivalent route structures are grouped:

- `/product/1234` -> `/product/:id`
- `/user/nathaniel/settings` -> `/user/:username/settings`
- `/search?q=shoes` -> `/search`

This improves cache reuse while structural hash still separates genuinely different DOM variants.

## Agent Readiness Scoring (Harness Concept)

DomBot separates two concerns:

- **Map Generator (DomBot):** produces interaction artifacts
- **Harness (Evaluator):** scores readiness and reports regressions across deploys

MVP readiness dimensions:

- Stable locator coverage
- Accessibility role/name quality
- Structural drift vs previous deploy
- Risk flags (modals, missing labels, hidden/disabled controls, iframe/canvas-heavy surfaces)

## Product Strategy

DomBot can evolve as two complementary products:

1. **Consumer product ("DomBot Agent")**
   - Installed in agent stacks
   - Local cache by default, optional shared cache
   - Makes existing agents faster and more reliable

2. **Business product ("DomBot Site")**
   - Deploy-time map publication (`/.well-known/dombot/map`)
   - Agent-traffic analytics and quality tooling
   - Helps sites become "agent-ready"

## Shared Cache Flywheel

Longer term, a shared cache unlocks network effects:

1. One user maps a common workflow
2. Other users get instant warm-start maps
3. Confidence improves from repeated successful executions
4. Fallback quality improves from real failure telemetry

## Status

This repository currently captures the DomBot concept and architecture direction.

Near-term MVP target:

- Local page-level extraction middleware
- Structural hash cache
- Selector fallback execution
- Demo showing run-1 learning and run-2 speedup

## One-Line Pitch

DomBot turns every deploy into a versioned agent interface and a regression signal for agent reliability.
