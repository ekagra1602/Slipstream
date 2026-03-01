# Sub-Agent Report

## Role

contrarian

## Research Question

What are the best MongoDB Atlas data storage and search designs for DomBot MVP1 graph-RAG, and what should the agent do vs avoid doing given current context?

## Scope and Assumptions

- Assumption 1: "Graph-RAG" can be overused as branding where simpler retrieval works better.
- Assumption 2: Early performance bottlenecks may be model latency and browser-state uncertainty, not database search.

## Core Claims

1. Claim: Do not force graph traversal into MVP runtime path unless you can prove it beats direct retrieval.
Evidence: DomBot goal is rapid guidance injection; `$graphLookup` recursion adds complexity and can hurt p95 under load.
Confidence (0-100): 85

2. Claim: Atlas Vector Search alone can produce semantically plausible but operationally unsafe actions without strict filters.
Evidence: Similar tasks can differ critically by auth state, route variant, locale, or UI experiment branch.
Confidence (0-100): 87

3. Claim: Shared memory creates contamination risk (bad traces, adversarial or low-quality behavior) unless governance is explicit.
Evidence: MVP1 envisions cross-user shared map; without trust scoring, nearest-neighbor retrieval can amplify bad patterns.
Confidence (0-100): 89

## Evidence Quality Assessment

- Source quality: Good for platform capability; weaker for trust/governance specifics because this is design-time projection.
- Method quality: Strong risk framing around failure externalities.
- Known biases/confounders: Conservative stance may delay useful compounding effects.

## Strongest Counterpoint

- Counterpoint: Early network effects are core to DomBot moat; delaying shared memory could delay differentiation.
- Why it matters: Speed to learning loop may matter more than perfect governance in early phase.

## What Would Change My Mind

- New evidence required: Robust trust-weighting and rollback outcomes showing low harm from shared-memory errors.
- Threshold for belief update: If harmful suggestion rate <1% with automatic rollback protections, expand shared memory faster.

## Open Questions

1. Who can write into shared memory and how is quality scored/revoked?
2. How are private session artifacts stripped before indexing?

## Agent Should / Shouldn't

- Should:
  - Gate shared suggestions by trust score + recency + context fit.
  - Keep local/session memory as higher-priority than global when conflict exists.
  - Require live validation checks before committing irreversible actions.
- Shouldn't:
  - Execute checkout/payment/account-changing actions solely from retrieved memory.
  - Store raw PII-bearing traces in reusable public memory.
  - Assume "similar task string" equals "same operational context".
