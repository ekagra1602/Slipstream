# Sub-Agent Report

## Role

falsifier

## Research Question

How should DomBot integrate with BrowserUse, and what are the strongest benefits, risks, and near-term execution plan?

## Scope and Assumptions

- Assumption 1: The strongest claim to test is: "DomBot materially improves BrowserUse reliability and cost on realistic workflows."
- Assumption 2: Success must be shown beyond one polished demo path.

## Core Claims

1. Claim: The main thesis fails if gains do not persist under dynamic-state stress.
Evidence: Docs acknowledge breakpoints (dynamic forms, SPAs, canvas, iframes, auth gating).
Confidence (0-100): 90

2. Claim: Selector fallback success is insufficient if state-transition verification is absent.
Evidence: Failure-landscape identifies silent event-sequence failures; a recovered selector can still produce no valid outcome.
Confidence (0-100): 88

3. Claim: Shared cache value fails if cache-hit rates are low in realistic, personalized sessions.
Evidence: Structural-hash exact match protects correctness but may reduce reuse if pages diverge often.
Confidence (0-100): 84

## Evidence Quality Assessment

- Source quality: Strong for threat surface from internal docs.
- Method quality: Good for defining falsification criteria; limited by lack of measured experiment outputs.
- Known biases/confounders: Proposed mitigations may be optimistic without load/variant testing.

## Strongest Counterpoint

- Counterpoint: The system is designed to degrade gracefully to baseline BrowserUse, so downside is additive complexity rather than catastrophic breakage.
- Why it matters: This lowers integration risk and supports incremental rollout.

## What Would Change My Mind

- New evidence required: A falsification test suite where DomBot still wins under the hardest regimes.
- Threshold for belief update:
  - Dynamic mutation test: <=5% regression vs baseline.
  - Selector break test: >=80% recovery without extra LLM call.
  - End-to-end suite: >=20% absolute completion gain in multi-step tasks.

## Open Questions

1. What is the abort condition when map confidence is low but fallback keeps “succeeding” semantically incorrectly?
2. How should rollback + verification be coupled with map selection for one coherent control loop?
