# Benchmark Optimization Meta-Analysis (All Benchmark Files)

## Scope
This report analyzes all benchmark outputs under `benchmarks/benchmark_v1`, `benchmark_v2`, and `benchmark_v3` (datasets only at time of analysis), then synthesizes recommendations using the research-agent workflow:
- empiricalist
- theorist
- contrarian
- falsifier

Also includes external research grounding from primary papers:
- WebArena (arXiv:2307.13854)
- Mind2Web (arXiv:2306.06070)
- Agent Workflow Memory (arXiv:2409.07429)
- SkillWeaver (arXiv:2504.07079)
- ReAct (arXiv:2210.03629)
- Reflexion (arXiv:2303.11366)

---

## Empiricalist Agent

### Observed facts from local benchmark files
Total run sets analyzed: 11 (`results.jsonl` files).

Key aggregates by run set:
- `v1 20260301T074821Z` (Walmart MacBook, 5 runs): strong stability (`steps` median 7, range 7-8).
- `v1 20260301T080105Z` (Walmart MacBook, 15 runs): stable-ish but mild variance (`steps` median 8, range 6-9).
- `v1 20260301T083056Z` (wireless mouse decision-heavy): high variance (`steps` median 13, range 6-16).
- `v1 20260301T085710Z` (wireless mouse + cart-only strict): very high variance (`steps` range 5-18), strong upward drift in time/steps.
- `v1 20260301T093632Z` (wireless mouse simplified 4 fields): much improved stability (`steps` median 7, range 6-8).
- `v1 20260301T095439Z` (hard composite qty=2): moderate variance (`steps` median 9, range 7-13).
- `v1 20260301T095516Z` (hard monitor flow): moderate variance (`steps` median 9, range 8-12).
- `v2` sets (Google first-result task): low pass rates (6/20, 6/20, 9/20) due ambiguous/visual-first vs organic-first mismatch and formatting/integrity issues.

### Evidence strength
- Strong: task structure strongly predicts variance.
  - Fixed-flow cart extraction tasks converge.
  - Decision-heavy cheapest+constraints tasks remain noisy.
- Strong: strict-output/format requirements can dominate failures even when navigation is successful.
- Moderate: confidence score is sensitive to judge gating and efficiency filtering; it does not monotonically track step reduction.

### Data gaps
- Current benchmark output mixes only one visible step metric (`steps` from agent history). Laminar/pipeline steps are in logs, not structured in CSV/JSONL.
- Token/cost telemetry currently zero in observed runs (`input_tokens/output_tokens/total_tokens = 0`), so cost optimization is not measurable yet.
- No explicit `schema_pass`/`format_pass` field despite many failures being formatting-related.

### Most reliable signals
- Judge pass + strict task design quality.
- Median/p90 duration over raw average.
- Step variance (CV and min/max spread) by task family.

### Empirical confidence
82%

---

## Theorist Agent

### Candidate models
1. **Path-memory-only model (current-ish)**
- Reuses step signatures and weighted counts.
- Works best when task is path-stable and low branching.

2. **Decision-augmented path model (recommended near-term)**
- Keep path memory, add decision priors (likely qualifying products/patterns).
- Better for cheapest+constraint tasks.

3. **Workflow/milestone memory model (AWM-like)**
- Store and retrieve reusable workflows with stage constraints.
- Highest expected reduction in variance for long/branchy tasks.

### Mechanism explanation for current non-convergence
- In decision-heavy tasks, branch factor dominates: product visibility, sponsorship, pagination, captcha/interstitials, and strict extraction requirements.
- Step hints alone cannot determine best candidate reliably in live DOM.
- Therefore, process drift remains even with better run weighting.

### Predictions
- Parameterized memory (`search(query)` not `search(macbook)`) will improve cross-item transfer and reduce wrong-value carryover.
- Adding decision priors (candidate title/price/rating bands) should reduce search detours.
- Milestone constraints should most strongly reduce step variance, especially p90 latency.

### Model ranking
1. Workflow/milestone memory (best long-term)
2. Decision-augmented path memory (best near-term ROI)
3. Path-memory-only (insufficient alone)

### Theorist confidence
85%

---

## Contrarian Agent

### Primary thesis under challenge
"Non-linear confidence weighting alone will drive convergence."

### Counterarguments
- Weighting improves learning signal, but execution is still soft-guided and can drift each run.
- Judge pass can still approve runs that are operationally inefficient.
- Efficiency filtering can block bad updates but does not actively enforce better trajectories.

### Alternative explanations for variance
- CAPTCHA/interstitial randomness contributes significantly.
- Task constraints themselves may be conflicting (e.g., requiring fields unavailable on cart page).
- Output-format errors create apparent intelligence failures that are actually protocol failures.

### Failure modes
- Model retrieves stale/semantically adjacent but wrong guidance.
- Literal value leakage (non-parameterized memory) hurts transfer.
- Monolithic multi-intent task keys reduce reuse and increase noise.

### Revised confidence in main thesis
78% confidence that path weighting alone is not enough.

---

## Falsifier Agent

### Hypotheses to test
H1. Splitting complex tasks into subtask phases reduces variance.
H2. Parameterized memory improves cross-item transfer.
H3. Milestone constraints reduce p90 latency and step spread more than weighting-only.

### Disconfirming evidence criteria
- H1 false if split execution has similar or worse median steps and CV than monolithic prompt.
- H2 false if cross-item pass rate does not improve over baseline by >=10 percentage points.
- H3 false if p90 duration and step max do not decrease materially (>=15%) with equal/higher pass rate.

### Test designs
1. **Monolithic vs phased benchmark**
- Same objective, two implementations:
  - single prompt
  - decomposed phases (`search/select/add`, then `cart extract`)
- 25 runs each.

2. **Transfer test**
- Train memory with 25 runs on product A/B.
- Evaluate 25 runs on unseen product C.
- Compare with and without parameterized memory.

3. **Milestone A/B**
- Current soft guidance vs milestone-constrained guidance.
- Measure pass, median steps, p90 duration, fail taxonomy.

### Fastest decisive next test
Run monolithic vs phased A/B on one hard task (25 + 25), then compare:
- judge pass rate
- median steps
- p90 duration
- step CV

### Falsifier confidence
81%

---

## Synthesis (Master)

### Best current answer
Yes, there is optimization happening, but it is incomplete. Current system is good for stable workflows and weak for high-branch decision tasks. Splitting complex tasks into smaller phases is likely beneficial and should be tested immediately.

### What is high-confidence
- Stable tasks converge; decision-heavy tasks remain noisy.
- Output-schema/format constraints materially affect measured success.
- Weighted memory helps but does not enforce consistent trajectories.

### What is medium-confidence
- Parameterized memory + decision priors will reduce cross-item errors and detours.
- Milestones are highest-impact for variance but higher implementation effort.

### What is speculative
- Exact magnitude of improvements (e.g., 20-30% latency reduction) until A/B tests are run.

### Key disagreements resolved
No major contradiction across agents: all point to needing stronger execution structure, not just better scoring.

### Decision
Proceed with a phased optimization roadmap:
1. Add structured metrics (`agent_steps`, `laminar_steps`, `pipeline_steps`, `schema_pass`, `format_pass`).
2. Implement parameterized memory (slot-based step signatures).
3. Add decision priors for candidate selection in decision-heavy tasks.
4. If variance remains high, implement milestone constraints (v2).

### Confidence
84%

---

## Sources
- WebArena: https://arxiv.org/abs/2307.13854
- Mind2Web: https://arxiv.org/abs/2306.06070
- Agent Workflow Memory: https://arxiv.org/abs/2409.07429
- SkillWeaver: https://arxiv.org/abs/2504.07079
- ReAct: https://arxiv.org/abs/2210.03629
- Reflexion: https://arxiv.org/abs/2303.11366
