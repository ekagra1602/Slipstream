# Master Synthesis

## Final Thesis

For DomBot MVP1, use MongoDB Atlas as the primary store with a hybrid memory architecture: `raw_traces` for ingestion/provenance, `task_nodes` as the read-optimized retrieval layer, optional `task_edges` for offline graph enrichment, Atlas Vector Search for fast semantic candidate retrieval, and hybrid reranking (vector + full-text + metadata filters) for action reliability. Keep graph traversal (`$graphLookup`) out of per-step hot path. The agent should treat retrieved memory as a prior, never as unquestioned truth.

## Confidence

- Overall confidence (0-100): 86
- Why this confidence level: Strong alignment between DomBot MVP1 goals and Atlas-native capabilities; remaining uncertainty is workload-specific performance and trust/governance behavior under shared memory.

## Agreement Matrix

- Where all agents agree:
  - Atlas Vector Search is central to MVP retrieval.
  - Runtime should be retrieval-first and low-latency; heavy graph ops should be offline.
  - Guardrails are mandatory: confidence gates, context matching, and fallback behavior.
- Where 2+ agents disagree:
  - How early to add explicit graph edges/traversal.
  - How aggressively to enable shared/global memory writes.

## Atlas Storage/Search Options (Researched)

1. Option A: Task-centric denormalized store (fastest MVP)
- Collections: `raw_traces`, `task_nodes`
- Retrieval: `$vectorSearch` on `task_nodes.task_embedding` + filter by `domain`, `route_class`, `state_signature`
- Strength: lowest latency and implementation complexity
- Weakness: limited relational expressiveness

2. Option B: Normalized graph-ready store
- Collections: `tasks`, `subtasks`, `task_edges`, `raw_traces`
- Retrieval: vector candidate -> edge traversal (`$graphLookup`) for composed plans
- Strength: better for v2 compositional path planning
- Weakness: more joins/traversal cost and ops complexity in MVP

3. Option C: Hybrid recommended path (best fit)
- Online serving: Option A (`task_nodes`) for inference-time speed
- Offline optimization: build/update `task_edges` and confidence weights from traces
- Retrieval: vector + hybrid lexical rerank + trust/recency/context gates
- Strength: balances speed now with graph evolution later
- Weakness: requires disciplined pipeline separation

4. Option D: Multi-tier memory controls (safety-oriented extension)
- `local_memory` (session/user scoped), `shared_memory` (global), `rejected_patterns`
- Trust scoring + write governance + rollback signals
- Strength: mitigates contamination and privacy risk
- Weakness: adds policy complexity

## Fastest Search Path (Recommended)

1. Embed task intent.
2. `$vectorSearch` in `task_nodes` with strict metadata filters (`domain`, auth state class, route pattern, freshness window).
3. Optional hybrid rerank using Atlas Search full-text signals for explicit intent terms.
4. Return top-k actions only if confidence + support + context match thresholds pass.
5. Cache retrieval result per run-step context.

Expected design goal: keep retrieval path simple enough to hit low-latency step budgets; move expensive graph recomputation to background jobs.

## Best Evidence

1. Evidence: Atlas provides ANN vector search and hybrid (vector + full-text) guidance patterns.
Why decisive: Directly matches DomBot need for semantic retrieval with precision constraints.

2. Evidence: `$graphLookup` exists for recursive traversal, but is better suited for selective use rather than every-step inference.
Why decisive: Preserves step-loop responsiveness.

3. Evidence: DomBot MVP1 already defines a two-layer memory (`raw_traces` + optimized task memory) and middleware injection model.
Why decisive: Existing architecture aligns with recommended option C without large redesign.

## Strongest Objections / Failure Modes

1. Objection: Similar-vector results can still be operationally wrong.
Impact if true: Agent executes harmful/irrelevant actions despite "high relevance" retrieval.
Mitigation or test: Enforce hard context gates and post-action verification before continuing.

2. Objection: Shared memory can be polluted by poor traces.
Impact if true: Error patterns propagate across users.
Mitigation or test: Trust-weighted writes, minimum support counts, and downranking on failed outcomes.

## Decision and Actions

- Recommended decision now: Implement Option C (hybrid online/offline architecture) on Atlas.
- Reversible next steps (1-2 weeks):
  1. Create `raw_traces` and `task_nodes` schemas, plus vector index on `task_embedding`.
  2. Add metadata filters and confidence gating in retrieval API.
  3. Add outcome-feedback loop to update confidence and mark stale/bad paths.
  4. Add optional `task_edges` table but keep traversal off hot path.

- Trigger points for reassessment:
  - If p95 retrieval >150ms, simplify pipeline and reduce online stages.
  - If wrong-suggestion execution >2%, tighten no-execute thresholds and trust gating.
  - If v2 composition demand rises (>20% tasks requiring subtask composition), promote graph traversal layer.

## Test Plan

1. Test: Retrieval latency + relevance benchmark
Expected signal: Top-k quality improves with hybrid rerank while keeping p95 under budget.
Decision impact: Confirms serving-path viability.

2. Test: Safety gate eval on dynamic/auth-varied workflows
Expected signal: Lower wrong-action rate vs ungated retrieval.
Decision impact: Validates do/don't execution policy.

## Agent Outcome Policy (What It Should / Shouldn't Do)

- Should:
  - Use retrieved paths as priors, then verify against live DOM/state.
  - Enforce no-execute gates on low confidence, stale signature, or trust mismatch.
  - Fall back to baseline browser-use behavior when retrieval confidence is insufficient.
  - Log outcomes and feed failures back to memory downranking.

- Shouldn't:
  - Blindly execute irreversible actions (checkout, payment, account changes) from memory alone.
  - Run recursive graph traversal in every interaction step.
  - Reuse guidance across major structural-hash/state changes.
  - Share raw trace artifacts containing sensitive identifiers.

## Source Links

- DomBot MVP1 Architecture: https://www.notion.so/316fe709905c81c18451c1288136d054
- DomBot Integration: https://www.notion.so/315fe709905c81af8273e7e1147c52a4
- Demo Integration Notes: https://www.notion.so/315fe709905c811ca60ce9a2c705ad59
- Atlas Vector Search Overview: https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/
- `$vectorSearch` stage: https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/
- Hybrid search (vector + full-text): https://www.mongodb.com/docs/atlas/atlas-search/hybrid-search/vector-search-with-full-text-search/
- `$graphLookup`: https://www.mongodb.com/docs/manual/reference/operator/aggregation/graphLookup/
- Atlas Search deployment options: https://www.mongodb.com/docs/atlas/atlas-search/about/deployment-options/
- Atlas scalability architecture: https://www.mongodb.com/docs/atlas/architecture/current/scalability/
- Time series best practices: https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/
- MongoDB GraphRAG reference article: https://www.mongodb.com/developer/products/mongodb/retail-reference-architecture-part-2-building-knowledge-graph-rag/
