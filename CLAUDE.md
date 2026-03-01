# BrowserUse / DomBot — Project Context

## What This Project Is

**DomBot** — a deploy-time DOM metadata layer that makes browser agents (browser-use, Skyvern, etc.) faster and more reliable. Two complementary products:

1. **DomBot Agent** (Consumer) — a package installed on the agent side. Runs semantic extraction on every page visit, builds/caches DOM maps locally, optionally contributes to a shared community cache.
2. **DomBot Site** (Business) — a developer build step. Exports a versioned DOM map at `/.well-known/dombot/map`. Emits an Agent Readiness Score on every deploy. CI integration.

**One-line pitch:** "DomBot turns every deploy into a versioned agent interface + a regression test for agent reliability."

**Analogy:** DomBot is to AI agents what `sitemap.xml` + Schema.org is to search engines.

---

## Notion Pages (BrowserUse workspace)

Parent page: https://www.notion.so/315fe709905c8066b044fb0377131bfc

| Page | URL | Summary |
|------|-----|---------|
| BrowserUse (root) | `315fe709-905c-8066-b044-fb0377131bfc` | Parent page, links all sub-pages |
| First prototype | `315fe709-905c-80ac-b2c3-e90c1e439810` | Full DomBot spec: problem, solution, MVP scope, demo plan |
| Dombot | `315fe709-905c-805d-bee3-ed3f2e71ef76` | Summary: map generator vs. harness, deploy flow, node map schema, Agent Readiness Score |
| DomBot — Consumer Product & Pre-Flight Crawl Architecture | `315fe709-905c-81ab-860d-c0304d9796c0` | Two-product strategy, pre-flight crawl loop, caching/invalidation, shared DOM cache |
| DomBot — Integration | `315fe709-905c-81af-8273-e7e1147c52a4` | How DomBot hooks into browser-use as observation middleware |
| Research: Web Agent Hackathon | `314fe709-905c-8122-9762-fc810cbe80fa` | Failure landscape, opportunity map, mechanism sketches (rollback + memory loop) |
| Pivot 4: Agent Observability | `315fe709-905c-81d3-879e-e83d6587dc81` | Agent drift, continuous-task observability, ASI metric, deep competitive scan |

---

## Core Architecture

### DOM Node Map schema (per node)
```json
{
  "node_id": "checkout_primary_cta",
  "role": "button",
  "name": "Checkout",
  "selectors": {
    "preferred": "[data-testid='checkout']",
    "fallbacks": ["button:has-text('Checkout')", "[aria-label*='Checkout']"]
  },
  "context": { "container": "cart_summary", "nearby_text": ["Total", "Shipping"] },
  "actions": ["click"]
}
```

### Cache key strategy
```javascript
hash(interactive_elements) = hash of:
  - role/type/label/name values of interactive nodes
  - relative positions in the tree
  - NOT content (prices, names) — structure only
```
Cache lookup: `cache[domain][route_pattern][structural_hash]`
Route normalization: `/product/1234` → `/product/:id`

### Integration with browser-use
DomBot sits between **observe** and **send to LLM** as automatic middleware:
```python
agent = Agent(
    task="complete checkout",
    llm=llm,
    browser=browser,
    observation_middleware=[dombot.enrich]  # fires on every page, before LLM
)
```

### Deploy pipeline
```
Build/Deploy → DomBot scan → Extract nodes → Emit dombot_map.json
                                                   ↓
                                         Harness: Agent Readiness Score
                                         Diff vs. previous map
                                         Optionally fail CI
```

---

## Key Failure Modes (from Research page)

1. **Compound Reliability Decay** — 89% per-step → ~31% end-to-end on 10-step tasks
2. **DOM Drift** — SPAs, shadow DOMs, A/B tests, canvas elements
3. **Event Sequencing** — `element.click()` silently fails; need full hover→mousedown→mouseup→click chain
4. **Timing/State Sync** — 500ms–2s model latency, agent acts on stale DOM
5. **Vision Precision** — 24px calendar cells, dense grids

---

## Opportunities / What's Being Built

| ID | Name | Core idea |
|----|------|-----------|
| 1 | DOM-Diff Rollback Engine | Signal-based (not LLM) rollback on state regression |
| 2 | Action Fingerprinting + Self-Healing Selectors | Live versioned map of action→DOM-state pairs |
| 3 | Trace→Memory→Behavior Loop ("Agent Déjà Vu") | Structured failure traces fed back as pre-execution context |
| 4 | DOM Event Verification | Before/after diff to confirm click actually registered |
| 5 | Execution Budget Controller | Kill/reroute tasks that are stalling |

---

## Research Workspace

Located at `research/`. Five-agent workflow: empiricalist → theorist → contrarian → falsifier → research-master.

```bash
cd research && ./setup_run.sh "Your research question"
```

---

## Working with Notion

Use the `notion` subagent (`.claude/agents/notion.md`) to:
- Fetch latest context from any page above
- Add findings/decisions to Notion pages
- Search for related content

To invoke: use the Agent tool with `subagent_type: "notion"` — or run `/notion` if configured as a command.
