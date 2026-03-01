# Nathan Plan: Laminar Integration + Trace Processing

## Scope (from `design.md`)
Nathan owns the Laminar and trace-processing lane:
- Laminar instrumentation setup
- Trace extraction/parsing
- Step-level success/failure labeling
- Cross-run comparison and convergence logic
- Analytics outputs for learning quality

This work turns raw agent telemetry into structured learning signals that feed the Mongo memory layer.

## Objective
Build a reliable pipeline:
1. Capture browser-agent traces
2. Normalize trace data into a stable schema
3. Label outcomes (step + task)
4. Aggregate across runs to detect winning paths
5. Emit clean payloads for storage/update by the data layer

## Architecture
### 1) Instrumentation
- Initialize Laminar once at process startup.
- DomBot itself does not call Playwright directly; Playwright instrumentation is only for observing browser-use internals.
- Use explicit instrument control to avoid unstable runtime paths:
  - Enable: `BROWSER_USE`, `PLAYWRIGHT`
  - Disable (currently unstable in this environment): `BROWSER_USE_SESSION`
- Keep environment toggles so we can switch between safe and full modes without code rewrites.

### 2) Normalized Trace Contract
Define internal canonical models so downstream logic is deterministic:
- `NormalizedStep`
  - `session_id`, `task_id`, `step_idx`, `timestamp`
  - `action_type`, `target`, `url`, `latency_ms`
  - `success`, `failure_reason`, `raw_attributes`
- `NormalizedTrace`
  - run/task metadata + ordered `NormalizedStep[]`
- `TaskAggregate`
  - grouped statistics and selected optimal action sequence

### 3) Extraction Pipeline
- Pull trace/spans from Laminar query layer (or local payload fixtures initially).
- Order events deterministically (by run and step index/timestamp).
- Transform provider-specific span fields into the canonical contract.
- Preserve raw evidence fields for debugging.

### 4) Labeling Pipeline
- Compute step-level and task-level outcomes.
- Failure taxonomy:
  - `selector`
  - `navigation`
  - `auth`
  - `timeout`
  - `unknown`
- Keep labels explicit and testable; avoid hidden heuristics.

### 5) Aggregation + Convergence
- Group traces by `(domain, normalized_task_intent)`.
- Compute:
  - `run_count`
  - `success_rate`
  - common successful step sequence
  - confidence score
- Convergence thresholds:
  - minimum successful run count
  - minimum success rate
  - path consistency threshold

### 6) Handoff to Data Layer (Eric)
Emit storage-ready payloads through the shared contract in `CLAUDE.md`:
- `store_trace(task, domain, trace, success)`
- `store_step(task, domain, step)` (optional real-time path)

Nathan's normalized records are internal. The adapter layer maps them into `StepData` list payloads for shared interfaces.

Convergence ownership split:
- Nathan computes convergence metrics/signals from trace analysis.
- Eric owns final confidence merge logic and persisted task-node scoring behavior.

## Execution Plan
1. Implement in `dombot/trace_pipeline.py` first (per current project contract), with clear internal sections for:
   - Laminar init
   - normalization models
   - extraction
   - labeling
   - aggregation
2. Implement Laminar bootstrap with instrument toggles.
3. Implement normalization models and validation.
4. Implement extractor + deterministic ordering.
5. Implement labeling and failure taxonomy.
6. Implement aggregation/convergence scoring.
7. Add fixture-based tests for each stage.
8. Add CLI runner for local replay (`extract -> label -> aggregate`).
9. Integrate outputs with shared storage hooks.

## Real-Time vs Batch Writes
- `dombot_report` path is real-time, per-step operational reporting.
- Laminar path is authoritative batch/offline analysis for convergence and quality metrics.
- Both are intentional: one supports immediate behavior updates, the other supports robust cross-run learning.

## Success Criteria
- Reproducible parsing of raw traces into canonical records
- Correct outcome labels on fixture test cases
- Stable aggregate/confidence outputs across repeated runs
- Clear, versioned contract for storage integration
- Observable metrics for improvement over time

## Immediate Next Steps
1. Create canonical models + schema tests.
2. Implement Laminar init module with safe/default instrument config.
3. Build first extractor from fixture payloads to `NormalizedTrace`.
4. Add initial convergence scoring function and unit tests.
