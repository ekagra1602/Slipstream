# Sub-Agent Report

## Role

empiricalist

## Research Question

How should DomBot integrate with BrowserUse, and what are the strongest benefits, risks, and near-term execution plan?

## Scope and Assumptions

- Assumption 1: The Notion data reflects current design intent as of February 28, 2026.
- Assumption 2: Claimed benchmarks (e.g., per-step reliability and rollback gains) are directional unless independently reproduced.

## Core Claims

1. Claim: Middleware integration at the observation stage is the lowest-friction path.
Evidence: Integration doc specifies one inserted step (`extract_or_fetch_map(page)`) and a clean hook (`observation_middleware=[dombot.enrich]`) with fallback to existing BrowserUse loop.
Confidence (0-100): 88

2. Claim: Local page-level semantic map caching is likely to improve speed and reduce repeated LLM dependence on revisited routes.
Evidence: Architecture doc describes cache hit path and structural-hash keying, including route normalization (`/product/:id`) and no-stale guarantee by exact hash match.
Confidence (0-100): 80

3. Claim: Most practical reliability gains will come from fallback selectors + state verification, not map generation alone.
Evidence: Failure-landscape doc emphasizes event-sequencing and silent action failure; integration docs emphasize selector fallback but do not yet define verification as a hard requirement.
Confidence (0-100): 84

## Evidence Quality Assessment

- Source quality: Medium-high for internal architecture detail; medium for external quantitative claims because not reproduced in this workspace.
- Method quality: Strong system decomposition (generator vs harness, middleware placement, cache invalidation logic).
- Known biases/confounders: Hackathon-oriented framing may overstate novelty/speedup and understate operational burden.

## Strongest Counterpoint

- Counterpoint: Runtime page dynamics (modals, mutation-heavy SPAs, canvas/iframes) can nullify cached-map gains and force fallback to baseline behavior frequently.
- Why it matters: If fallback frequency is high, complexity increases without consistent ROI.

## What Would Change My Mind

- New evidence required: Controlled A/B on representative workflows comparing baseline BrowserUse vs DomBot-enabled flow.
- Threshold for belief update: At least 20-30% improvement in end-to-end completion rate OR 30%+ drop in retries/LLM calls across >=3 site types.

## Open Questions

1. What exact observation payload size increase does NodeMap injection create, and does it raise token costs on first-run pages?
2. What percentage of real workflows can be covered by stable semantic IDs without manual curation?
