# Sub-Agent Report

## Role

empiricalist

## Research Question

What are the best MongoDB Atlas data storage and search designs for DomBot MVP1 graph-RAG, and what should the agent do vs avoid doing given current context?

## Scope and Assumptions

- Assumption 1: MVP1 priorities are low-latency retrieval and reliable path reuse, not full graph-theory optimization.
- Assumption 2: Atlas-native capabilities should be preferred first to reduce operational overhead.

## Core Claims

1. Claim: Fastest practical retrieval for MVP is Atlas Vector Search with metadata pre-filtering, then optional rerank.
Evidence: MongoDB docs recommend `$vectorSearch` for ANN semantic retrieval, with filter support; hybrid examples combine vector + full text for better relevance.
Confidence (0-100): 90

2. Claim: A two-tier schema (`task_nodes` for optimized knowledge + `raw_traces` for provenance) is empirically best for speed and debuggability.
Evidence: DomBot MVP1 already separates optimized task representation from raw trace ingestion; this aligns with write-heavy trace capture and read-optimized task retrieval.
Confidence (0-100): 87

3. Claim: Use graph traversal (`$graphLookup`) selectively for offline/path recomputation, not hot-path inference.
Evidence: `$graphLookup` is powerful recursive traversal but generally heavier than direct vector + keyed retrieval for millisecond runtime decisions.
Confidence (0-100): 82

## Evidence Quality Assessment

- Source quality: High (MongoDB official docs + concrete DomBot architecture notes).
- Method quality: Strong for separating online serving vs offline optimization pipelines.
- Known biases/confounders: No benchmark in this workspace yet for your exact workload distribution.

## Strongest Counterpoint

- Counterpoint: A normalized graph schema from day one may simplify future v2 subtask composition.
- Why it matters: Avoids migration later, but likely increases MVP query complexity and latency.

## What Would Change My Mind

- New evidence required: Load test showing normalized graph queries match or beat denormalized task-node retrieval at p95 latency.
- Threshold for belief update: If normalized design keeps p95 retrieval <150ms with same relevance, move earlier to graph-first.

## Open Questions

1. Expected top-k retrieval latency target (p50/p95) for injected action guidance?
2. How often will tasks require cross-domain path composition vs single-domain route guidance?

## Agent Should / Shouldn't

- Should:
  - Retrieve by semantic task embedding + strict domain/context filters.
  - Prefer high-confidence, high-support paths only.
  - Fall back to baseline browser-use when confidence is low or stale.
- Shouldn't:
  - Execute low-support path suggestions blindly.
  - Depend on graph traversal in the per-step hot path.
  - Mix raw user-identifying trace data into shared inference context.
