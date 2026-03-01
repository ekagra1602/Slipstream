# DomBot

DomBot turns browser automation from fragile index-based clicks into a stable, semantic interface for AI agents.

At a high level, DomBot builds a structured **interaction map** of web pages (nodes, roles, names, selectors, fallbacks) and uses it to make agent actions faster, cheaper, and more resilient across runs.

## Why DomBot

Most browser agents rely on screenshots plus accessibility trees and then choose elements by transient indices (for example, "click element 47"). This breaks easily as UIs evolve.

DomBot introduces a stable layer:

- Named semantic nodes (for example, `checkout_primary_cta`)
- Ranked selector fallbacks
- Route-aware and structure-aware caching
- Graceful degradation to baseline agent behavior

Result: agents reason over meaning, not brittle element positions.

## Core Concept

DomBot is designed as **middleware, not a tool command the agent must remember to call**.

It sits between "observe page state" and "send context to LLM":

1. Observe page
2. Build or fetch NodeMap
3. Enrich LLM context with semantic nodes
4. Agent plans action
5. Executor uses preferred selector, then fallbacks if needed

## What a Node Map Contains (MVP)

Each interaction node includes:

- Stable `node_id` (semantic intent key)
- Role/tag (`button`, `input`, `link`, etc.)
- Accessible name/text
- Preferred selector (`data-testid`, id, role-based)
- Ranked fallback selectors
- Context hints (container, nearby text)
- Allowed actions (`click`, `type`, `select`, ...)

## Browser Agent Integration (browser-use style)

Current loop:

1. Screenshot + accessibility tree
2. LLM picks element
3. Executor performs action

With DomBot:

1. Screenshot + accessibility tree
2. DomBot extracts or fetches NodeMap
3. LLM receives page context + NodeMap and picks semantic node IDs
4. Executor resolves selectors (preferred first, fallback next)
5. Repeat

Example integration shape:

```python
from browser_use import Agent
from dombot import DomBot

dombot = DomBot(cache="local")  # or "shared"

agent = Agent(
    task="complete checkout",
    llm=llm,
    browser=browser,
    observation_middleware=[dombot.enrich],
)
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

## Trace-First POC

This repo includes a minimal proof-of-concept for the trace memory loop in `poc/`.

Build task memory nodes from sample traces:

```bash
python3 poc/trace_poc.py build \
  --traces poc/sample_traces.json \
  --out poc/task_nodes.json
```

Query a suggested plan for a new task:

```bash
python3 poc/trace_poc.py suggest \
  --nodes poc/task_nodes.json \
  --domain walmart.com \
  --task "purchase a mac laptop from walmart"
```

The output shows the best-matching prior task and its learned `optimal_actions`.
