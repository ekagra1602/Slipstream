# Cross-Item Transfer for DomBot (Research Brief)

## Question
Can DomBot learn reusable Walmart shopping behavior from prior tasks (e.g., MacBook, iPhone) so a new product task (e.g., AirPods) starts with high performance?

## Short Answer
Yes, partially with current trace learning; strongly yes if DomBot shifts from whole-task path memory to reusable skill-level transfer.

## What the Literature Says

1. Real web tasks are hard and brittle without structured evaluation.
- WebArena reports low autonomous baseline success on realistic multi-step tasks (best GPT-4 agent in paper: 14.41% vs 78.24% human).
- Implication for DomBot: raw prompting + trajectory memory is not enough; robust task-specific validators and state checks are required.
- Source: https://arxiv.org/abs/2307.13854

2. Cross-site/domain generalization is possible but depends on state filtering and grounding.
- Mind2Web shows better generalization when large raw HTML is filtered before decision-making.
- Implication for DomBot: retrieval and selector grounding should emphasize compact, relevant state abstractions.
- Source: https://arxiv.org/abs/2306.06070

3. Skill libraries produce measurable transfer gains.
- SkillWeaver reports relative success improvements via discovered reusable APIs, including transfer from strong agents to weaker ones.
- Implication for DomBot: create reusable action APIs (search, open result, add to cart, open cart, extract fields), not just step-frequency voting.
- Source: https://arxiv.org/abs/2504.07079

4. Lifelong skill accumulation improves novel task performance.
- Voyager (different domain, same agent-learning principle) shows persistent skill libraries help solve unseen tasks in new worlds.
- Implication for DomBot: maintain a growing, composable skill inventory with retrieval by intent + context.
- Source: https://arxiv.org/abs/2305.16291

## Applied Takeaways for DomBot

### Current System (what it does well)
- Learns from repeated successful traces.
- Uses judge-gated outcomes and confidence for path reuse.
- Now supports quality-weighted path optimization (correct + faster + fewer steps).

### Current Limitation
- Learning is still mostly task-cluster/path-based.
- Transfer from `buy MacBook` to `buy AirPods` is limited if task strings/paths diverge.

### Needed Upgrade: Skill-Centric Transfer
Add a reusable skill layer on top of path memory.

Proposed Walmart skill primitives:
- `wm_open_home`
- `wm_search_product(query)`
- `wm_select_product(policy)` (first non-sponsored / cheapest in-stock / min rating)
- `wm_add_to_cart(quantity)`
- `wm_open_cart`
- `wm_extract_cart_fields()`

Each skill should track:
- success rate
- median latency
- median steps
- failure taxonomy (selector/timeout/captcha/interstitial)
- context constraints (desktop/mobile, signed-in/out, captcha present)

## Proposed Retrieval Policy
At runtime:
1. Infer task intent slots (site, product_query, selection_policy, output_schema).
2. Retrieve top matching skills by `(site, intent, context)`.
3. Compose a short plan from skills.
4. Execute with strict postconditions.
5. Log outcomes back to both skill-level and trace-level stores.

## Evaluation Protocol (DomBot-Specific)

### Dataset Split (Walmart)
- Train products: `macbook air`, `iphone 15`, `wireless mouse`, `gaming keyboard`.
- Test products (unseen): `airpods`, `usb-c hub`, `monitor arm`.

### A/B Conditions
- A: baseline browser-use (no DomBot retrieval)
- B: current DomBot path retrieval
- C: DomBot + skill-layer retrieval (target design)

### Metrics
Primary:
- judged pass rate
- strict schema pass rate (all required fields extracted from cart page)

Secondary:
- median duration
- median steps
- avg token usage
- estimated USD cost
- recovery count (retries/backtracks)

Transfer metric:
- zero-shot test success on unseen products after training products only

### Significance
- Use at least 20 runs/condition for noisy commerce flows.
- Report median deltas + bootstrap CI.
- Claim improvement only if CI excludes 0 for main metrics.

## Recommended Implementation Order
1. Canonical task schema + slot extraction (product + policy + output contract).
2. Skill storage schema in Mongo (`skills` collection).
3. Skill retrieval + composition in `dombot_query` response.
4. Strict validators for commerce outputs (cart page source required).
5. A/B benchmark harness for baseline/path/skill conditions.

## Risk Notes
- CAPTCHA/interstitials can dominate latency; separate these from planner quality.
- Product availability/pricing drift introduces non-stationarity.
- Ambiguous instructions ("first result") must be policy-locked per benchmark.

## Decision
Cross-item transfer is achievable and worth building. The highest ROI is adding a skill layer and transfer benchmark protocol, not more raw repetitions of item-specific tasks.

## Confidence
84%
- High confidence in direction (supported by WebArena/Mind2Web/SkillWeaver/Voyager patterns).
- Medium confidence in exact performance gains until DomBot skill layer is implemented and benchmarked.
