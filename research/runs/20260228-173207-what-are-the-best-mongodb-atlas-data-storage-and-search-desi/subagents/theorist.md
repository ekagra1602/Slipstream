# Sub-Agent Report

## Role

theorist

## Research Question

What are the best MongoDB Atlas data storage and search designs for DomBot MVP1 graph-RAG, and what should the agent do vs avoid doing given current context?

## Scope and Assumptions

- Assumption 1: Graph-RAG here means retrieval over task/action knowledge with optional relationship traversal.
- Assumption 2: System should optimize for control-loop correctness, not only retrieval novelty.

## Core Claims

1. Claim: Best architecture is a layered memory model, not a single "graph DB" abstraction.
Evidence: Atlas supports document model + vector search + text search + aggregation traversal; combining these gives composability and simpler operations than introducing a separate graph engine in MVP.
Confidence (0-100): 88

2. Claim: The right conceptual split is:
- Episodic memory (`raw_traces`)
- Semantic task memory (`task_nodes` with embeddings)
- Relational memory (`task_edges` for optional traversal)
Evidence: This preserves provenance, enables ANN retrieval, and allows gradual graph enrichment.
Confidence (0-100): 86

3. Claim: Hybrid retrieval (vector + lexical/metadata fusion) should dominate pure vector for actionable agent instructions.
Evidence: MongoDB hybrid search guidance indicates better relevance from combining full-text and vector signals.
Confidence (0-100): 84

## Evidence Quality Assessment

- Source quality: High for capability docs, medium for expected relevance uplift without local evals.
- Method quality: Strong abstraction alignment with MVP1 and v2 path expansion.
- Known biases/confounders: Task intent embeddings may drift; lexical constraints still critical.

## Strongest Counterpoint

- Counterpoint: A single denormalized `task_nodes` collection may be enough for long enough, making edges unnecessary now.
- Why it matters: Could reduce complexity and speed implementation.

## What Would Change My Mind

- New evidence required: Error analysis showing significant failures due to missing explicit relationships.
- Threshold for belief update: If >20% of wrong suggestions stem from missing relationship modeling, add edges immediately.

## Open Questions

1. Do you need deterministic replay guarantees or only probabilistic guidance?
2. Should confidence be global per task or contextual per route/state signature?

## Agent Should / Shouldn't

- Should:
  - Treat retrieved paths as priors; validate against live page state before acting.
  - Use confidence + context match gates (domain, route class, state hash).
  - Log outcomes for continual memory updates.
- Shouldn't:
  - Treat memory as ground truth when DOM/state diverges.
  - Over-index on embedding similarity without rule constraints.
  - Collapse all contexts into one global best path.
