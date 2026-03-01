# DomBot Skill Transfer — Master Research Synthesis

**Date**: 2026-03-01
**Status**: Final
**Author**: Master Research Agent (synthesized from Empiricalist, Theorist, Contrarian, Falsifier)

---

## 1. Question

Can DomBot achieve true cross-item transfer on Walmart by moving from nearest-neighbor task-text/path similarity retrieval to reusable abstract skill primitives (`wm_search_product`, `wm_select_product`, `wm_add_to_cart`, `wm_open_cart`, `wm_extract_cart_fields`)?

---

## 2. Best Current Answer

The current system structurally cannot achieve cross-item transfer: `_action_signature()` in `/Users/nathaniellee/claude/browseruse/Dombot/db/db.py` embeds product-specific values into step keys (e.g., `type:search_input:macbook` vs. `type:search_input:airpods`), making separate task nodes for each product-task string inevitable under the existing `(task, domain)` grouping key. A skill layer — specifically a grouping key change from `(domain, task)` to `(domain, intent_class)` — would make cross-item transfer structurally possible. However, before investing in the skill layer, one decisive test must be run first: whether current DomBot path hints beat no-DomBot baseline on novel products at all. If they do not, the skill layer is solving a secondary problem while the primary mechanism (retrieval → hint → LLM compliance) remains unvalidated.

---

## 3. What We Know (High Confidence)

These facts are directly verifiable in the codebase or from the 10-run Walmart benchmark data.

**[Empiricalist] KNOWN — structural cross-item transfer blockage is confirmed in code.**
In `/Users/nathaniellee/claude/browseruse/Dombot/db/db.py`, `_action_signature()` at line 252–255:
```python
def _action_signature(step: StepData) -> str:
    if step.value:
        return f"{step.action}:{step.target}:{step.value}"
    return f"{step.action}:{step.target}"
```
And `store_trace()` at line 162 uses `{"task": task, "domain": domain}` as the MongoDB upsert key. The combination means every distinct task string produces a separate node, and step signatures inside a node embed product-specific values. `type:search_input:macbook` and `type:search_input:airpods` are permanently distinct keys. This is not a retrieval problem — it is a storage-schema problem.

**[Empiricalist] KNOWN — 3 of 5 proposed Walmart skill primitives are already product-invariant in current traces.**
In `poc/sample_traces.json`, steps `click:add_to_cart`, `click:view_cart`, and `click:checkout_cta` carry no product-specific `value` field and would be identical across any product. Only `type:search_input:<product>` and `click:first_electronics_result` are product-specific.

**[Empiricalist] KNOWN — 10-run Walmart benchmark shows 10/10 judged_pass, steps 6–16 (high variance), duration 80–178s.**
From the benchmark summary data cited by all four agents. Step variance of 10 steps across 10 successful runs is large relative to the 6-step floor visible in `poc/sample_traces.json`. The -1.2 step reduction (9.7%) across 10 runs is within noise.

**[Empiricalist] KNOWN — confidence formula in `db/db.py` is NOT the simple saturating formula described in the research brief.**
The actual production formula in `_recompute_optimal_path()` (lines 276–344) is:
```python
success_rate = success_count / run_count
volume_factor = min(1.0, run_count / 20)  # ramps up over first 20 runs
base_confidence = success_rate * (0.5 + 0.5 * volume_factor)
confidence = round(min(0.99, base_confidence * (0.85 + 0.15 * quality_factor)), 3)
```
This saturates at 20 runs (not 10 as cited). At 10 runs with 100% success, confidence ≈ 0.75, not 0.94. The Falsifier's H4 kill condition is based on the wrong formula — the actual formula is more conservative and includes a quality factor from step traces.

**[Theorist] KNOWN — the grouping key change is a minimal schema intervention, not a full rewrite.**
`build_task_nodes()` in `poc/trace_poc.py` at line 92 uses:
```python
key = (t.domain, t.task.lower().strip())
```
Changing this to `(t.domain, intent_class)` would reuse the entire position-voting algorithm unchanged. The skill layer is latent in the algorithm — only the grouping key and an intent classifier are new additions.

**[Falsifier] KNOWN — no cross-item or no-DomBot-baseline benchmark data exists.**
No condition A (no-DomBot), no condition B vs. condition C (path vs. skill), no cross-product held-out set has been run. All 10 Walmart runs used the same task string and all succeeded, producing no failure taxonomy data.

---

## 4. What We Infer (Medium Confidence)

These are reasonable inferences from the evidence, but require testing to confirm.

**[Contrarian] INFERRED (55%) — the primary bottleneck is selector grounding, not action sequencing.**
The 6–16 step variance in the 10-run Walmart benchmark is consistent with a grounding variance signature: the LLM knows to "click add to cart" but struggles to identify the correct DOM element across Walmart's A/B layout tests and sponsored block placements. DomBot's `optimal_actions` hints address sequencing ("click:add_to_cart"), not selector grounding (which CSS selector or element index corresponds to add_to_cart in the current DOM state). If this inference is correct, both path-retrieval and skill-layer hints are solving the wrong problem.

Conflict marker: The Theorist disagrees, arguing that even sequence-level hints reduce exploration steps and that grounding is improved by element-description hints that DomBot provides. This conflict is unresolved and testable by examining Laminar traces for whether the agent calls `dombot_query` and then still takes extra steps to locate the element.

**[Empiricalist / Theorist] INFERRED (62%) — embedding similarity between cross-item task strings is high enough for vectorSearch to return a useful near-match.**
"buy macbook on walmart" and "buy airpods on walmart" share high cosine similarity on `text-embedding-3-small` (both are short purchase-intent sentences on the same domain with shared structural tokens: buy, on, walmart). The `$vectorSearch` retrieval step would likely return the macbook node for an airpods query. However, the returned `optimal_actions` would include `type:search_input:macbook`, which is actively wrong for the airpods task. Retrieval works; returned content is incorrect for cross-item use.

**[Theorist] INFERRED (68%) — the correct skill boundary is the phase transition, not the 5-primitive decomposition.**
The Theorist's grounding in the Options Framework (Sutton 1999) is the strongest theoretical justification in the set. Skills should be defined by stable initiation/termination conditions observable in DOM state, not by human-intuited step groupings. `wm_add_to_cart` is likely correctly atomic because its termination condition (cart count increments) is a single, observable DOM change. `wm_select_product` may be poorly defined if Walmart's product listing DOM is unstable (sponsored blocks, lazy loading). This inference can only be confirmed by running traces and examining where multi-step variance clusters.

**[Contrarian] INFERRED (60%) — SkillWeaver/Voyager analogies are partially applicable, with a critical disanalogy.**
SkillWeaver and Voyager use code-as-skill (deterministic, executable against stable APIs or sandboxed environments). DomBot uses hint-as-skill (natural language retrieved to guide an LLM acting on live, non-deterministic DOM). The gain mechanism is different: SkillWeaver gains by bypassing repeated LLM planning; DomBot can only reduce LLM exploration steps, not eliminate LLM decision-making. The transfer magnitude for DomBot is likely smaller than literature suggests. However, the directional claim (structured retrieval beats unstructured retrieval) remains sound.

---

## 5. What Is Speculative (Low Confidence)

**[Theorist, 22%] SPECULATIVE — embedding reformulation alone (task frame normalization) achieves cross-item transfer without schema changes.**
The proposal to embed slot-normalized frames (`site=walmart, intent=purchase, category=electronics`) so "buy MacBook" and "buy AirPods" collapse to the same node is theoretically elegant but carries negative transfer risk: collapsing all purchase tasks to one node prevents learning product-class-specific behaviors (e.g., electronics vs. apparel have different Walmart page layouts). There is no evidence this works, and the risk of corrupting the knowledge base with averaged-out paths is real. Rated speculative.

**[Theorist/Empiricalist, 35%] SPECULATIVE — skill layer produces measurable step reduction on the specific Walmart task within hackathon scope.**
Even if the skill layer is architecturally correct, whether it produces a detectable step reduction in 20–30 runs depends on: (a) Walmart DOM stability, (b) LLM compliance with hint instructions at high confidence, (c) whether step variance is driven by planner confusion or grounding failures. Without H3 baseline data, the gain magnitude is purely speculative.

**[Contrarian, speculative] SPECULATIVE — LLM already knows the skill sequence and DomBot adds near-zero marginal value.**
The Contrarian's strongest objection — that GPT-4-class models have absorbed "search → select → add to cart" from training — is directionally plausible but cannot be true at the selector level. The LLM does not know Walmart's current DOM structure, element indices, or which result to prefer. Where DomBot may genuinely add value is in providing selector-level ground truth from past successful runs. This is speculative until H3 is run.

---

## 6. Key Disagreements Across Agents

### Conflict 1: Theorist (72%) vs. Contrarian (28%) on skill-layer confidence

**The conflict.** Theorist rates skill-layer achievability at 72% based on algorithmic analysis (grouping key change is minimal, Options Framework grounding, SkillWeaver analogy). Contrarian rates it at 28% based on three objections: LLM prior, Walmart DOM instability, and hackathon timeline.

**Resolution.** Neither estimate is well-grounded because neither has run H3 (baseline comparison). The Theorist's 72% assumes the retrieval-to-hint mechanism works on novel products; this is unverified. The Contrarian's 28% assumes the LLM prior dominates; this is also unverified. Correct weight: 45% on skill layer being worth implementing at hackathon scope, conditional on H3 showing current DomBot beats baseline.

The Contrarian's timeline objection is the strongest and most testable: a manually-authored skill library in MongoDB (5 hand-crafted skill documents) is implementable in ~4 hours and would test the retrieval + composition mechanism without requiring automated skill discovery. If manual skills work, the architecture is validated; automated extraction is a v2 problem.

### Conflict 2: Theorist says algorithm implicitly extracts skills vs. Contrarian says 26-hour scope is the real constraint

**Resolution.** Both are correct at different levels. The Theorist is correct that changing the grouping key from `(domain, task)` to `(domain, intent_class)` would make skill extraction latent in the existing position-voting algorithm. The Contrarian is correct that this requires an intent classifier, new schema, new retrieval pipeline, and composition strategy — none of which is trivially hackable in 26 hours. The resolution: seed 5 hand-written skill nodes into a new `skills` collection, add a `dombot_skill_query` tool that retrieves by `(site, intent_class)`, and test whether manual skills transfer. This proves the mechanism without automated skill extraction.

### Conflict 3: Empiricalist (58%) vs. Contrarian (28%) on achievability

**Resolution.** The gap is explained by the Empiricalist including the structural fix feasibility in the 58% estimate, while the Contrarian is estimating whether a working implementation will show measurable gains within the hackathon. These are different questions. Structural achievability is ~75% (the code change is clear). Empirical measurability within 26 hours is ~35%. Combined estimate for "skill layer works and we can prove it at the hackathon": 40%.

### Conflict 4: Contrarian's "LLM already knows the sequence" objection vs. Theorist's transfer function

**Resolution.** The Contrarian is partially right at the sequence level (action ordering) and wrong at the selector level (which DOM element). DomBot's value proposition should be reframed: not "tell the LLM to search then click then add to cart" (LLM knows this) but "tell the LLM exactly which element succeeded in past runs, and which interstitial handling steps are required." This is a hint content problem, not a hint existence problem. The `optimal_actions` format in `prompts.py` currently encodes `click:first_electronics_result` — an abstract description, not a selector. If skills encoded last-known successful selectors (e.g., `[data-automation-id="add-to-cart-btn"]`), the marginal value over LLM prior would be concrete and non-trivial.

### Conflict 5: Falsifier (run H3 first) vs. Theorist/Empiricalist (implement skill layer)

**Resolution.** The Falsifier is correct on sequencing. H3 (30-run alternating no-DomBot/DomBot on AirPods) is the fastest, cheapest way to validate whether the underlying retrieval → hint → LLM mechanism works at all on novel products. Cost: ~$4.50, time: ~2–3 hours. If H3 fails (no significant difference, or DomBot arm has higher variance), the skill layer thesis is irrelevant — the team would be building a more sophisticated version of a mechanism that doesn't work. H3 must run before skill layer implementation.

---

## 7. Most Critical Falsification Test

**Run H3 immediately.**

**Experimental design.**
- 30 runs, alternating arm assignment (run 1: no-DomBot, run 2: DomBot, ...) on Walmart.
- Task: "Buy AirPods on walmart.com and add to cart" (product NOT in current MongoDB task_nodes).
- Seed MongoDB with 10 MacBook task node runs ONLY before starting H3 — no AirPods prior data.
- Arm A (no-DomBot): `Agent` without `tools=tools` and without `extend_system_message=DOMBOT_SYSTEM_PROMPT`.
- Arm B (current DomBot): standard `Agent` with `tools=tools` and `DOMBOT_SYSTEM_PROMPT`.
- Primary metric: median steps (Wilcoxon rank-sum, p < 0.05).
- Secondary metric: median duration and step variance ratio (Arm B variance / Arm A variance).

**Kill condition.**
If Arm B median steps >= Arm A, OR if Arm B step variance > Arm A step variance (hint injection confusing agent): current retrieval mechanism does not transfer to novel products. Stop skill layer work. Pivot to Contrarian's Intervention A (selector caching) or Intervention B (task frame embedding reformulation).

**Pass condition.**
If Arm B median steps < Arm A by >=1.5 steps, p < 0.05: baseline retrieval mechanism works on novel products. Proceed to implement manual skill layer. If Arm B is better but p > 0.05 or delta < 1.5 steps: mechanism is weak, skill layer remains speculative.

**Cost and time.** ~$4.50 total, ~2–3 hours of wall-clock time at ~5 min/run. This is the single experiment that resolves whether the entire skill layer investment is justified.

**Implementation note.** Use the existing `benchmark1.py` in `/Users/nathaniellee/claude/browseruse/Dombot/scripts/benchmark1.py`. Add an `--arm` flag for no-DomBot condition, or run two separate invocations with and without DomBot tools. The benchmark harness already collects all required metrics.

---

## 8. Decision + Confidence

**Decision.**

Do NOT implement the skill layer before running H3. After H3:

- **If H3 passes**: Implement manual skill layer. Hand-write 5 Walmart skill documents into a new `skills` MongoDB collection. Add `dombot_skill_query` tool that retrieves by `(site=walmart.com, intent_class=<buy|search|add_to_cart|...>)`. Change `optimal_actions` format to include element-type hints, not just abstract action names. Run cross-item validation (10 AirPods runs with skill hints, compare to H3 Arm B). This is achievable within a 26-hour hackathon if H3 is run first and returns a clear pass.

- **If H3 fails (no DomBot lift on novel products)**: Pivot to Intervention B: change the embedding key from raw task string to a slot-normalized frame (`site + intent + product_category`). This is a 2-hour code change in `db/db.py` (`embed_task()` call and the upsert key). Re-run H3. If this also fails, the DomBot mechanism needs a different hypothesis.

**What to build regardless of H3 outcome:**
The `_action_signature()` function should be refactored to strip product-specific values before computing step signatures for the purpose of `optimal_actions` path construction. The product value (e.g., `macbook`) should be stored separately as a slot parameter, not fused into the action key. This is a low-risk, 1-hour change that improves cross-item retrieval quality regardless of whether the skill layer is added.

```python
# Current (blocks transfer):
def _action_signature(step: StepData) -> str:
    if step.value:
        return f"{step.action}:{step.target}:{step.value}"
    return f"{step.action}:{step.target}"

# Proposed (separates structure from content):
def _action_signature(step: StepData, include_value: bool = False) -> str:
    base = f"{step.action}:{step.target}"
    if include_value and step.value:
        return f"{base}:{step.value}"
    return base
# Use include_value=True for step_counts keying (preserves current behavior)
# Use include_value=False for optimal_actions path construction (enables transfer)
```

**Confidence in this decision: 72%.**

The 28% uncertainty is entirely due to H3 not being run yet. If H3 confirms a measurable DomBot lift on novel products, confidence in the overall skill layer direction rises to ~80%. If H3 returns null results, the research question is answered negatively and the team avoids building a non-working system.

---

## Supporting Code References

All file paths below are absolute.

| Claim | File | Lines |
|-------|------|-------|
| `_action_signature()` embeds product values | `/Users/nathaniellee/claude/browseruse/Dombot/db/db.py` | 252–255 |
| Upsert key is `(task, domain)` — blocks skill grouping | `/Users/nathaniellee/claude/browseruse/Dombot/db/db.py` | 162 |
| Confidence formula (actual production version) | `/Users/nathaniellee/claude/browseruse/Dombot/db/db.py` | 325–333 |
| `build_task_nodes` grouping key — latent skill algorithm | `/Users/nathaniellee/claude/browseruse/Dombot/poc/trace_poc.py` | 89–92 |
| `optimal_actions` format sent to LLM | `/Users/nathaniellee/claude/browseruse/Dombot/dombot/prompts.py` | 26–36 |
| Benchmark harness for H3 | `/Users/nathaniellee/claude/browseruse/Dombot/scripts/benchmark1.py` | 228–298 |
| Sample action signatures (product-specific confirmed) | `/Users/nathaniellee/claude/browseruse/Dombot/poc/task_nodes.json` | 18–24 |

---

## Appendix: Agent Confidence Summary

| Agent | Confidence in Skill Layer | Key Driver |
|-------|--------------------------|------------|
| Empiricalist | 58% | Structural fix is clear; no cross-item data exists |
| Theorist | 72% | Grouping key change is minimal; Options Framework grounds it |
| Contrarian | 28% | LLM prior + Walmart DOM instability + hackathon scope |
| Falsifier | Deferred | H3 must run first; all skill-layer confidence is premature |
| **Master Synthesis** | **40% (pre-H3) / 72% (post-H3 pass)** | H3 is the key gate |
