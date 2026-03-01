# Benchmark3 Diagnosis + Research-Agent Approval

## Context
This document explains why `benchmark3` confidence is not rising despite many judged-successful runs, and records a research-backed approve/defer matrix before implementation.

## What went wrong in benchmark3 (observed)
From the logs provided:
1. Many runs are marked:
- `Pipeline complete: SUCCESS (bloated — path not updated)`
- `Efficiency filter: <steps> > budget ... — path NOT updated`

2. Composite task structure has high branch factor:
- two item selections,
- per-item criteria checks,
- options vs direct add,
- modal handling,
- captcha/interstitial waits.

3. Outcome:
- run is often `judge=True`,
- but path update is blocked,
- therefore confidence/optimal path updates stagnate or decay.

This behavior is expected under current gating semantics.

---

## Root-cause summary
1. **Efficiency gate is too dominant for composite tasks**
- It blocks path reinforcement frequently, so learning signal is sparse.

2. **Task complexity exceeds single-flow assumptions**
- One prompt encodes multiple subtasks (mouse + keyboard + cart extract).
- Step count variability is structural, not just model quality.

3. **Noise inflation**
- Captcha/interstitial events add unavoidable extra steps.
- These are currently counted against compactness budgets.

4. **Soft guidance still allows drift**
- Retrieved path helps, but does not enforce stage-level execution bounds.

---

## Research-agent review (with online docs cross-check)

## Empiricalist — APPROVE
Approved changes:
1. Add strict contract metrics and gate learning on valid contract passes.
2. Keep efficiency filter but normalize for noise/composite tasks.
3. Add explicit metrics split: `agent_steps` vs `laminar_tool_steps`.
4. Add noise markers (captcha/interstitial) to benchmark outputs.

Evidence/doc support:
- Browser-Use runtime controls and limits can bound drift:  
  https://docs.browser-use.com/customize/agent/all-parameters
- Browser-Use hooks support step-level intervention:  
  https://docs.browser-use.com/customize/hooks
- Laminar online evaluators support automatic scoring attached to spans:  
  https://docs.lmnr.ai/evaluations/online-evaluators/introduction

## Theorist — APPROVE
Approved changes:
1. Milestone constraints for composite tasks.
2. Per-phase retry budgets via hooks.
3. Parameterized memory + task decomposition for multi-step prompts.

Evidence/doc support:
- AWM shows workflow memory improves success and reduces steps on web tasks:  
  https://arxiv.org/abs/2409.07429
- Browser-Use hooks are the right integration point for phase gating:  
  https://docs.browser-use.com/customize/hooks

## Contrarian — PARTIAL APPROVE
Approve with cautions:
1. Do not over-tighten global efficiency budgets.
2. Do not treat all long runs as low-quality; some are noise-induced.
3. Avoid adding many evaluators at once.

Caution support:
- Browser-Use environments are dynamic and failure handling is bounded by config/timeouts; over-constraining can hurt pass rate.  
  https://docs.browser-use.com/customize/agent/all-parameters

## Falsifier — APPROVE (with tests)
Required proving tests before claiming optimization:
1. Baseline vs milestone-gated A/B on same composite task (25/25).
2. Noise-stratified analysis (captcha-present vs clean).
3. Pass criterion:
- equal/higher pass rate,
- >=15% drop in p90 steps or p90 duration.

Doc support for evaluation instrumentation:
- Laminar online evaluators + metadata/tags for A/B slicing:  
  https://docs.lmnr.ai/evaluations/online-evaluators/scoring-with-hosted-evaluators  
  https://docs.lmnr.ai/tracing/structure/metadata  
  https://docs.lmnr.ai/tracing/structure/tags

---

## Approved implementation updates to add to main plan

## 1) Composite-aware efficiency policy (REQUIRED)
- Keep `success` and `path_update_allowed` separate.
- Count true successes for confidence volume.
- Only block path update if bloated **after** noise adjustment.

Noise adjustment fields:
- `captcha_events`
- `interstitial_events`
- `modal_recovery_count`

## 2) Composite task decomposition (REQUIRED)
Split monolithic tasks into phases/subtasks:
- Phase A: add cheapest qualifying mouse
- Phase B: add cheapest qualifying keyboard
- Phase C: cart extraction

Learn and score each phase independently + full run summary.

## 3) Milestone guardrails via Browser-Use hooks (REQUIRED)
Use `on_step_start/on_step_end` to enforce:
- phase order,
- retry budgets,
- bounded recovery.

## 4) Contract scorer in Laminar (REQUIRED)
Add one online evaluator for:
- schema/format/scope pass score,
- attached per trace for dashboard and regression.

## 5) Benchmark output expansion (REQUIRED)
Add columns:
- `agent_steps`
- `laminar_tool_steps`
- `pipeline_steps_total`
- `path_update_allowed`
- `captcha_events`
- `schema_pass`, `format_pass`, `scope_pass`

## 6) Retrieval improvements (DEFER PARTIAL)
Use Supermemory-like ideas incrementally:
- metadata/container-style filtering first,
- reranking optional,
- query rewriting only if recall remains poor.

References:
- https://supermemory.ai/docs/concepts/filtering
- https://supermemory.ai/docs/memory-api/features/reranking
- https://docs.supermemory.ai/memory-api/features/query-rewriting

---

## Explicit defer list
1. Full strict replay.
2. Full HUD migration for runtime loop.
3. Multi-evaluator suite before single contract evaluator is stable.

HUD references reviewed (not first-priority for current bottleneck):
- https://docs.hud.ai/
- https://docs.hud.ai/platform/mcp

---

## Final verdict
Yes, the benchmark3 confidence issue is explainable and fixable.
The high-confidence path is:
1. composite-aware gating,
2. phase decomposition,
3. milestone hook control,
4. contract evaluator instrumentation,
5. expanded benchmark metrics.

This should materially improve convergence signal quality before the next benchmark cycle.

---

## Latest run evidence (Run 21-24 excerpt)
Observed in your latest logs:
1. Repeated pattern:
- `Efficiency filter: 23 steps > budget 13 ... path NOT updated`
- `Pipeline complete: SUCCESS (bloated — path not updated)`

2. Benchmark summary line still reports lower `steps` (for agent loop KPI), while trace pipeline logs larger Laminar extraction counts.
- This is expected: they are different counters.

3. Confidence remains low/flat (`~0.13-0.15`) despite many `judge=True` outcomes.
- Root cause: reinforcement is frequently blocked on composite runs due to strict efficiency budget.

4. Composite task branch variability remains high:
- alternative product picks (`onn 5-button` vs `onn travel`),
- extra modal/captcha/no-thanks handling,
- list vs PDP path choice.

Conclusion:
- Current policy is too strict for this benchmark family; it suppresses learning on otherwise valid runs.

---

## B4 implementation order (locked)
1. **Decouple success from update gating**
- Keep `run_success = judge_pass && contract_pass`.
- Compute `path_update_allowed` separately.
- Confidence volume must use `run_success`, not `path_update_allowed`.

2. **Composite-aware efficiency budget**
- Replace fixed `optimal + slack` with:
- `budget = optimal + base_slack + phase_penalty + noise_penalty`.
- Phase penalty from declared stage count; noise penalty from captcha/interstitial/modal events.

3. **Phase decomposition for benchmark3-style tasks**
- Persist and score per-phase traces (`mouse`, `keyboard`, `cart_extract`) and aggregate run trace.
- Path update can be allowed per phase even when full-run budget is exceeded.

4. **Milestone hook guardrails**
- Enforce phase order and max retries per phase via Browser-Use hooks.
- Prevent broad detours once a phase objective is met.

5. **Single Laminar contract evaluator**
- Add one online evaluator (schema/format/scope).
- Use result as hard gate for `run_success`.

6. **Metrics expansion in CSV/JSONL**
- Add: `path_update_allowed`, `agent_steps`, `laminar_tool_steps`, `pipeline_steps_total`,
  `captcha_events`, `interstitial_events`, `modal_recovery_count`,
  `schema_pass`, `format_pass`, `scope_pass`.

---

## Approval status after docs re-check
Approved now:
1. Browser-Use hooks for milestone control.
2. Browser-Use runtime parameter profile for stability.
3. Laminar online evaluator + tags/metadata for A/B slices.
4. Supermemory-style filtering/reranking as secondary retrieval improvement.

Deferred:
1. Full strict replay.
2. Full HUD migration.
3. Multi-evaluator stack before single-evaluator baseline proves value.
