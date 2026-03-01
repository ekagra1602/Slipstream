# DomBot Optimization Plan (Pre-Change)

## Purpose
This document is the pre-implementation blueprint for fixing DomBot's convergence issues and improving workflow optimization reliability on live web tasks.

It captures:
- what we are changing,
- why each change is necessary,
- implementation order,
- validation criteria,
- risks and mitigations.

## Agent-AI Optimizer Review Status
Reviewed using the `agent-ai-optimizer` framework against:
- `BENCHMARK3_DIAGNOSIS_AND_APPROVAL.md` (benchmark3 diagnosis),
- this implementation plan.

Decision: **APPROVED WITH ADDITIONS**.

Approval rationale:
1. Core bottlenecks are correctly identified (composite-task variance, strict update gating, drift/noise contamination).
2. The phased implementation order is sound for causality and attribution.
3. Existing plan needs additional safeguards for production rollout, cost control, and regression detection.

---

## Problem Statement
Current behavior shows partial optimization but inconsistent convergence on harder tasks.

Observed issues:
1. **Soft guidance drift**
- Retrieved `optimal_actions` influence behavior, but the agent still replans freely each run.
- Result: high run-to-run variance in steps and latency on decision-heavy tasks.

2. **Literal memory contamination**
- Step memory can retain literal values (for example, product-specific search terms), reducing transfer quality.

3. **False-positive learning risk**
- Some runs are operationally poor (bloated, formatting-invalid, wrong extraction scope) yet can appear superficially successful.

4. **Task contract ambiguity**
- Failures often come from formatting/scope constraints, not navigation.
- Without strict contract validation, memory can optimize the wrong objective.

5. **Metric confusion**
- Multiple step counters exist (agent steps vs Laminar tool steps) but are not always surfaced together in benchmark outputs.

---

## Optimization Objective
Converge toward:
1. Higher contract-valid pass rate.
2. Lower median and p90 **agent steps**.
3. Lower median and p90 duration.
4. Lower variance (step and time spread) across repeated runs.
5. Better transfer to similar new tasks without brittle replay.

---

## Core Design Principles
1. **Correctness first**
- No run should reinforce memory unless it is both judge-valid and contract-valid.

2. **Generalize structure, not literals**
- Learn reusable workflow patterns and parameterized actions.

3. **Constrain execution just enough**
- Use milestone constraints and retry budgets to reduce drift, without strict replay brittleness.

4. **Separate diagnostics from KPIs**
- Agent-level outcomes are primary KPI; Laminar/tool metrics are diagnostic.

5. **Iterative rollout with A/B checks**
- One major feature class at a time, measure impact, then proceed.

---

## Full Feature Plan (What + Why)

## 1) Task Contracts + Strict Schema Validator
### What
- Add task contract parsing and validation layer:
  - required output format,
  - required fields,
  - page scope constraints,
  - failure policy.

### Why
- Prevents false-positive learning from runs that violate user contract.
- Fixes major source of judge disagreement (format and scope failures).

### Expected impact
- Immediate increase in reliability of learned traces.
- Cleaner benchmark signal.

---

## 2) Parameterized Memory
### What
- Replace literal step signatures with slot-based signatures.
- Example: `search:{query}` instead of `search:macbook`.
- Store slot values separately as context.

### Why
- Prevents wrong literal carryover.
- Improves cross-item transfer quality.

### Expected impact
- Better reuse on similar tasks with different entities.

---

## 3) Canonical Task Normalization
### What
- Normalize equivalent task phrasings into stable canonical keys.

### Why
- Prevents memory fragmentation across minor wording differences.

### Expected impact
- Faster confidence stabilization on repeated intent.

---

## 4) Milestone-Constrained Execution
### What
- Define stage order for task families.
- Enforce stage completion criteria.
- Limit allowed action types per stage.
- Add bounded retries and checkpoint recovery.

### Why
- Strongest lever to reduce variance and loop drift without strict replay.

### Expected impact
- Lower p90 steps/time; tighter run consistency.

---

## 5) Decision-Level Priors
### What
- Store successful candidate priors (title/price/rating patterns, sponsor avoidance).
- Use them at selection stage as ranked hints.

### Why
- Decision-heavy tasks cannot be optimized by path hints alone.

### Expected impact
- Fewer exploratory detours on product-selection tasks.

---

## 6) Learning Policy Refinement
### What
- Keep hard gate: learn only on judge+contract pass.
- Keep efficiency filter to block bloated path updates.
- Keep non-linear weighting:
  - steps primary,
  - time secondary,
  - add stability and recency decay.

### Why
- Prioritizes robust, efficient trajectories.

### Expected impact
- More meaningful confidence and optimal action updates.

---

## 7) Benchmarking and Evaluation Upgrade
### What
- Surface all relevant metrics in benchmark outputs:
  - `agent_steps`,
  - `laminar_tool_steps`,
  - `pipeline_steps_total`,
  - `schema_pass`, `format_pass`, `scope_pass`,
  - failure taxonomy.
- Add monolithic vs phased benchmark modes.
- Add significance checks (median delta + bootstrap CI).

### Why
- Needed to prove true convergence and avoid misleading averages.

### Expected impact
- Clear, defensible performance claims.

---

## 8) Runtime Controls and Model Strategy
### What
- Tune runtime caps (max steps/failures/timeouts).
- Maintain one stable tuning model; periodically A/B with stronger model.

### Why
- Reduces confounds while still identifying reasoning bottlenecks.

### Expected impact
- More stable optimization loop and better diagnostics.

---

## 9) Prompt/Policy Versioning + Lineage (ADD NOW)
### What
- Version all major agent prompts/policies (`planner`, `selector`, `validator`, `memory retrieval prompt`).
- Stamp each run with version IDs in trace metadata.
- Require benchmark outputs to include version lineage.

### Why
- Prevents mixed-policy confounds when comparing variants.
- Makes regressions attributable to exact behavior changes.

### Expected impact
- Faster root-cause analysis and cleaner A/B interpretation.

---

## 10) Cost and Token Budget Guardrails (ADD NOW)
### What
- Add hard and soft per-run budgets:
  - `prompt_tokens`,
  - `completion_tokens`,
  - estimated cost per run.
- Add early-stop policy when contract feasibility is low and budget is near cap.

### Why
- Optimization must improve quality/latency without hidden cost explosion.
- Prevents expensive non-convergent trajectories from dominating learning cycles.

### Expected impact
- Better quality-per-dollar and safer benchmark scaling.

---

## 11) Canary + Auto-Rollback Strategy (ADD NOW)
### What
- Roll out optimization features in canary mode:
  - `baseline` (control),
  - `candidate` (new logic),
  - fixed traffic split.
- Define automatic rollback triggers:
  - pass-rate regression threshold,
  - p90 latency regression threshold,
  - schema/scope failure spike.

### Why
- Prevents broad regressions when enabling milestone constraints or new gating logic.
- Gives operational safety while iterating quickly.

### Expected impact
- Higher reliability during live evolution of agent policies.

---

## 12) Failure Replay Pack + Triage Queue (ADD NOW)
### What
- Auto-capture a compact replay pack for failed/near-failed runs:
  - task input,
  - model/runtime params,
  - phase transitions,
  - failure taxonomy,
  - key screenshots/events.
- Route packs to a ranked triage queue by frequency x impact.

### Why
- Converts noisy failures into actionable optimization backlog.
- Speeds iteration on recurring failure classes.

### Expected impact
- Shorter fix cycles and more targeted optimization work.

---

## Research-Backed Additions (After External Docs Cross-Check)
These items were added after explicitly reviewing Browser-Use, Laminar, and Supermemory docs plus AWM literature.

### A) Browser-Use hook-level control (add now)
#### What
- Implement `on_step_start` / `on_step_end` milestone enforcement and loop budgets.
- Use per-step guardrails without full strict replay.

#### Why
- Directly reduces drift and retry loops while preserving flexibility.

#### Source
- Browser-Use lifecycle hooks:  
  https://docs.browser-use.com/customize/hooks

### B) Browser-Use runtime caps profile (add now)
#### What
- Define benchmark profile defaults for:
  - `max_actions_per_step`
  - `max_failures`
  - `max_steps`
  - `step_timeout`
  - `max_validations`
  - optional `fallback_llm`

#### Why
- Constrains runaway trajectories and improves consistency under noise.

#### Source
- Browser-Use all parameters:  
  https://docs.browser-use.com/customize/agent/all-parameters

### C) Captcha/noise reduction controls (add now)
#### What
- Standardize cloud session settings for benchmarks:
  - `cloud_profile_id`
  - `cloud_proxy_country_code`
  - `cloud_timeout`
- Track captcha/interstitial presence in benchmark metadata.

#### Why
- Captcha variance currently masks optimization gains.

#### Sources
- Browser-Use remote browser/cloud parameters:  
  https://docs.browser-use.com/customize/browser/remote  
- Browser-Use cloud stealth/proxies:  
  https://docs.cloud.browser-use.com/usage/stealth

### D) Laminar online contract evaluator (add now)
#### What
- Register one online evaluator for strict contract scoring:
  - schema/format/scope score
  - attach numeric score to spans/traces
- Use score for dashboarding and regression trending.

#### Why
- Gives objective, automated quality signal tied to actual traces.

#### Sources
- Laminar online evaluators intro:  
  https://docs.lmnr.ai/evaluations/online-evaluators/introduction  
- Hosted/SDK scoring:  
  https://docs.lmnr.ai/evaluations/online-evaluators/scoring-with-hosted-evaluators

### E) Laminar experiment metadata/tags (add now)
#### What
- Tag all runs by experiment variant (`baseline`, `param_mem`, `milestone_on`, etc.).
- Add metadata fields for noise markers and benchmark family.

#### Why
- Enables clean A/B slicing and avoids ambiguous conclusions.

#### Sources
- Laminar metadata:  
  https://docs.lmnr.ai/tracing/structure/metadata  
- Laminar tags:  
  https://docs.lmnr.ai/tracing/structure/tags

### F) Supermemory-style retrieval controls (defer partial)
#### What
- Keep current storage, but incorporate ideas:
  - metadata/container-style filtering for retrieval scope
  - optional reranking on ambiguous queries
  - optional query rewriting only where recall is poor

#### Why
- Improves retrieval quality, but increases complexity/latency if adopted too early.

#### Sources
- Supermemory filtering concepts/API:  
  https://supermemory.ai/docs/concepts/filtering  
  https://supermemory.ai/docs/memory-api/features/filtering  
- Reranking:  
  https://supermemory.ai/docs/memory-api/features/reranking  
- Query rewriting:  
  https://docs.supermemory.ai/memory-api/features/query-rewriting

### G) Workflow-memory evidence (supports milestones)
#### What
- Keep milestones as high-effort/high-payoff feature.

#### Why
- External evidence shows workflow memory reduces steps and improves success under distribution shift.

#### Source
- Agent Workflow Memory (AWM):  
  https://arxiv.org/abs/2409.07429

---

## Defer / Exclude for Now
1. Full HUD platform integration for core runtime optimization.
2. Multi-evaluator expansion before contract evaluator is stable.
3. Full strict replay policy.
4. Full Supermemory migration before in-agent controls are stabilized.

Reason: these increase scope and confounds before core convergence controls are validated.

---

## Implementation Order (Phased)

## Phase A (Foundation)
1. Task contracts + strict validator.
2. Validator-gated learning.
3. Benchmark metric expansion.

**Gate to proceed:**
- contract-valid pass rate is measurable,
- false-positive learning is blocked.

## Phase B (Transfer)
1. Parameterized memory.
2. Canonical task normalization.

**Gate to proceed:**
- improved pass and/or reduced drift on similar-but-not-identical tasks.

## Phase C (Variance reduction)
1. Milestone constraints.
2. Retry budgets + checkpoint recovery.

**Gate to proceed:**
- p90 step/time reduction with pass rate preserved or improved.

## Phase D (Decision-heavy optimization)
1. Decision priors.
2. Stability and recency weighting refinements.

**Gate to proceed:**
- reduced detours on criteria-based selection tasks.

## Phase E (Hardening)
1. Full A/B benchmark matrix.
2. Significance reporting and regression guardrails.
3. Noise-stratified reporting (captcha/interstitial vs clean runs).
4. Laminar-tagged variant comparison dashboards.

## Phase F (Operationalization)
1. Prompt/policy version lineage in all runs.
2. Cost/token budget guardrails.
3. Canary deployment with auto-rollback thresholds.
4. Failure replay pack + triage queue.

---

## Acceptance Criteria (Convergence)
For a target task family, over rolling window:
1. `contract_pass_rate >= 95%`.
2. `judge_pass_rate` non-decreasing.
3. median `agent_steps` decreases or stabilizes at low plateau.
4. p90 duration decreases.
5. step/time variance decreases.
6. confidence does not increase on contract-invalid runs.
7. median cost per successful run is non-increasing after Phase F.
8. rollback triggers do not fire for two consecutive benchmark cycles.

---

## Risks and Mitigations
1. **Over-constraining execution**
- Risk: pass rate drop.
- Mitigation: staged rollout and bounded A/B tests.

2. **Parser brittleness for contracts**
- Risk: false validator failures.
- Mitigation: fallback contract and explicit parser tests.

3. **Noisy web environment (captcha/interstitials)**
- Risk: masked improvements.
- Mitigation: track noise-specific failure taxonomy and p90 metrics.

4. **Metric overfitting**
- Risk: optimize to one metric while harming others.
- Mitigation: multi-metric gates (pass + median + p90 + variance).

---

## Why This Plan Should Work
This plan closes the main failure loop:
- It ensures memory only learns from truly valid outcomes,
- removes literal contamination,
- reduces run drift with structure,
- and upgrades evaluation so convergence can be proven, not assumed.
- It adds operational safety (canary + rollback), cost control, and policy lineage needed for durable agent-ai optimization.

In short: optimize the right objective first, then optimize speed/steps within that objective.
