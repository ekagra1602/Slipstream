# Research Master: What is the optimal way to store graph-structured agent trace data in MongoDB Atlas for DomBot?

## Agreement Matrix

| Claim | Empiricalist | Theorist | Contrarian | Falsifier | Verdict |
|-------|-------------|----------|------------|-----------|---------|
| V1 retrieval is single-hop vector search, not a graph problem | Agree (70%) | Strongly agree (92%) | Strongly agree (Thesis 2) | Agree (residual claim) | **CONSENSUS: True.** Highest-confidence claim across all agents. |
| Graph RAG frameworks are a poor fit for structured trace data | Agree (75%) | Strongly agree (88%) | Agree (Thesis 2) | Agree (no case studies) | **CONSENSUS: True.** Impedance mismatch -- traces are structured, not unstructured text. |
| $graphLookup is insufficient for weighted optimal path finding | Partially agree (50%) | Agree (70%) | Strongly agree (Thesis 1) | Strongly agree (FM1, FM7) | **CONSENSUS: True for v2.** Recursive BFS with no cost functions, no weighted shortest path. |
| Denormalized task doc with embedded action arrays is correct v1 schema | Agree (70%) | Strongly agree (92%) | Agree (Thesis 2) | Agree (residual) | **CONSENSUS: True.** Single-doc read + vector search = <60ms estimated. |
| MongoDB Atlas is "optimal" for this workload | Neutral (55%) | Leans yes (78%) | Disagrees (Theses 3,5) | Disagrees (45%) | **SPLIT.** See resolution below. |
| 300ms latency target is achievable for v1 | Agree (70%) | Agree (78%) | Neutral | Conditionally agree | **CONSENSUS: Likely true** for vector-only v1. |
| Adding graph-ready null fields is low-cost v2 insurance | Agree (65%) | Strongly agree | Partially disagree (schema lock-in risk) | Neutral | **LEAN: True.** Cost is near-zero; removal cost also near-zero. |
| 16MB doc limit is not a v1 constraint | Agree (90%) | Agree | Not addressed | Agree (FM3 medium) | **CONSENSUS: True** if DOM snapshots stored as references. |
| Traces may not compound due to DOM brittleness | Not addressed | Not addressed | Raises concern (Thesis 4) | Not addressed | **UNRESOLVED.** Only Contrarian raises it, but it threatens the entire value prop. |
| Vector search index sync lag is a concern | Raises concern | Not addressed | Not addressed | Agrees (FM4) | **PARTIALLY RESOLVED.** Seconds of lag at MVP scale; acceptable but monitor. |

### Resolution: "Is MongoDB Atlas optimal?"

This is the only true split across agents. Resolution: **MongoDB Atlas is pragmatically acceptable for MVP, not technically optimal.** The Theorist's 78% confidence is contingent on the MongoDB-only constraint stated in the question. The Contrarian correctly identifies that Redis VSS (<1ms vector search) and Pinecone (<50ms p99 at 1B+ scale) outperform Atlas on the core retrieval dimension. The Falsifier correctly notes that Atlas Vector Search runs on a separate mongot process, meaning "one database" is architecturally two processes. However, the operational simplicity argument holds for a 2-4 week MVP with a small team: one billing account, one connection string, one set of credentials. The decision to use MongoDB is treated as a constraint, not a conclusion -- if Atlas-specific limitations materialize, the revisit triggers below apply.

## Strongest Supporting Evidence

**1. V1 is vector-search-only, and HNSW handles this with large latency margin.**

All four agents converge. HNSW on <100K documents delivers sub-50ms p50 latency (ANN-benchmarks, not MongoDB-specific). Single-document read adds <5ms. Total MongoDB-side latency: ~60ms estimated, well within 300ms even with 3x pessimistic adjustment. Evidence quality is medium (algorithm-level, not Atlas-benchmarked), but the margin is large enough that the conclusion is robust.

**2. Graph RAG is architecturally mismatched for structured execution traces.**

The Theorist provides the clearest causal argument: Graph RAG frameworks (LangChain GraphTransformer, LlamaIndex KnowledgeGraphIndex) extract entity-relationship triples from unstructured text. DomBot's data is already structured (state -> action -> result with probability). Using Graph RAG would add an LLM round-trip to destructure and re-structure already-structured data. No agent contests this. No published case study uses Graph RAG for agent execution trace retrieval. This claim survived all four lenses at high confidence.

**3. $graphLookup is recursive BFS, not a graph query engine.**

The Contrarian and Falsifier provide definitive evidence: no `weightField`, no `costFunction`, no `shortestPath` option in $graphLookup. It discovers all reachable nodes, not the best path. For DomBot's v2 ("find action sequence with highest aggregate success rate"), you would need to pull the subgraph into application memory and run Dijkstra/A* in Python. Additionally, `restrictSearchWithMatch` cannot use compound indexes, so filtered traversals do collection scans at each hop (FM7). This is a structural limitation of MongoDB, not a tuning issue.

## Strongest Unresolved Objections

**1. Do browser automation traces actually compound, or do they decay too fast?**

Only the Contrarian raises this (Thesis 4), but it is the most structurally threatening objection because it questions the entire DomBot value proposition, not just the storage pattern. Industry standard: 10-30% flake rate in automated test suites due to UI changes. E-commerce sites deploy multiple times per day. Anti-bot systems randomize page structures. If traces decay in weeks, the compounding cache becomes a maintenance burden.

- **Impact if true:** The entire shared-cache architecture is solving a problem that does not exist. Storage optimization becomes irrelevant.
- **Mitigation:** DomBot may operate at a semantic level ("find search bar") rather than DOM-selector level ("click #search-input-v2"), extending trace half-life. The trace decay experiment (Near-Term Test 4) directly validates this.
- **Why unresolved:** No empirical data exists. This is a product-level question that storage design cannot answer.

**2. What does v2's graph structure actually look like?**

The Theorist assumes parent-child task trees. The Contrarian and Falsifier suggest it could be a weighted page-state DAG or an action graph with success-rate edges. These require fundamentally different schemas. If v2 is a weighted DAG, $graphLookup is structurally inadequate and a dedicated graph database would be needed.

- **Impact if true:** The graph-ready null fields in v1 are useless. V2 may require Neo4j or application-level graph algorithms regardless.
- **Mitigation:** Keep v1 schema simple. Defer v2 schema decisions until v2 requirements are concrete. The null fields cost nothing to add or remove.
- **Why unresolved:** V2 requirements are not yet defined. This is structural uncertainty, not data-limited.

**3. MongoDB Atlas vector search latency is unverified on the actual target configuration.**

All latency estimates are based on HNSW algorithm benchmarks (ann-benchmarks.com), not MongoDB Atlas-specific measurements. MongoDB does not publish p50/p95/p99 latency SLAs. The Empiricalist flags this as "the single largest evidence gap."

- **Impact if true (latency is worse than estimated):** If p99 exceeds 200ms at 10K documents, the 300ms budget is at risk after adding embedding generation and network overhead.
- **Mitigation:** Near-Term Test 1 resolves this within 2 hours.
- **Why unresolved:** Nobody has run the benchmark yet. This is data-limited uncertainty, fully solvable.

## Final Thesis

For DomBot's MVP1, the optimal storage pattern is a **denormalized task-centric document model with Atlas Vector Search** -- not Graph RAG, not $graphLookup, not a multi-database architecture. Each task is a single MongoDB document containing the task description, its OpenAI embedding vector, an ordered array of optimal actions with success rates, failure history, and metadata. Retrieval is a single `$vectorSearch` query returning the most similar task document(s) with full action sequences in one round trip. This pattern meets the <300ms latency target with significant margin (~60ms estimated for the MongoDB portion), handles concurrent writes via WiredTiger document-level locking, stays well within the 16MB document limit for typical traces, and requires no graph traversal for the v1 use case. Graph-ready fields (`parent_task_id`, `sub_task_ids`) should be added as null/empty placeholders at negligible cost. Graph RAG should be explicitly rejected due to architectural mismatch. $graphLookup should be understood as a recursive BFS join useful for shallow tree traversals, not a graph query engine -- if v2 requires weighted path optimization, evaluate Neo4j or application-level graph computation at that time. MongoDB Atlas is pragmatically acceptable for MVP (not theoretically optimal) because operational simplicity outweighs the capability gap versus specialized tools at this scale and timeline.

## Confidence

**72%** -- Breakdown:

| Component | Confidence | Uncertainty Type |
|-----------|-----------|-----------------|
| V1 storage pattern (denormalized + vector search) | 90% | Data-limited (solvable with benchmarks) |
| MongoDB Atlas as v1 platform | 65% | Pragmatic (works, but not best-in-class at any single capability) |
| V2 graph readiness of schema | 45% | Structural (unsolvable until v2 is designed) |
| Trace compounding assumption | 50% | Empirical (solvable with product experimentation) |

The overall 72% reflects high confidence in the v1 storage pattern dragged down by moderate confidence in the platform choice and low confidence in v2 preparedness. The v1 pattern uncertainty is fully resolvable with 2-3 hours of benchmarking. The v2 and trace-compounding uncertainties are structural and will persist until product decisions are made.

## Near-Term Tests

1. **Benchmark $vectorSearch on Atlas M10 at 1K/10K/50K documents with 1536-dim embeddings.**
   - Expected signal if thesis holds: p99 < 100ms at 10K documents.
   - Expected signal if thesis fails: p99 > 200ms at 10K documents.
   - Decision impact: If p99 > 150ms, evaluate Redis VSS or Pinecone as vector layer.
   - Time: 2 hours.

2. **Measure end-to-end retrieval latency (task description string -> returned action sequence)** including OpenAI embedding API call, Atlas query, and deserialization.
   - Expected signal: Total < 350ms, with embedding generation dominating.
   - Decision impact: If embedding generation > 250ms, implement embedding caching/precomputation.
   - Time: 1 hour (after test 1).

3. **Compute worst-case document size for realistic 50-step traces** with action metadata, compact DOM context (structural hashes), and success metrics.
   - Expected signal: < 2MB per document.
   - Decision impact: If > 5MB, design separate DOM storage collection immediately.
   - Time: 30 minutes, no infrastructure.

4. **Trace decay experiment: Execute the same task 10 times over 2 weeks.** Measure how many stored action steps remain valid after 1, 3, 7, 14 days.
   - Expected signal if compounding works: > 70% of steps valid at 7 days.
   - Expected signal if compounding fails: < 50% of steps valid at 7 days.
   - Decision impact: If decay is rapid, add TTL/decay mechanisms and consider semantic-level actions.
   - Time: 2 weeks (background).

5. **Prototype two-query pattern (vector search + separate path lookup)** and measure combined latency as v2 baseline.
   - Expected signal: Combined < 200ms.
   - Decision impact: If > 200ms, v2 may need a different architecture than MongoDB-only.
   - Time: 1 hour (after test 1).

## Recommended Decision

**Now:** Build v1 with the denormalized task-centric document model on MongoDB Atlas.

**Schema:**
```javascript
// Collection: tasks
{
  _id: ObjectId,
  task_description: "buy a macbook on walmart",
  task_embedding: [/* 1536 floats */],
  optimal_actions: [
    { step: 1, action_type: "navigate", target: "walmart.com", selector: null, text: null, success_rate: 0.95, run_count: 47 },
    { step: 2, action_type: "click", target: null, selector: "#search-input", text: null, success_rate: 0.98, run_count: 47 },
    { step: 3, action_type: "type", target: null, selector: "#search-input", text: "Macbook", success_rate: 0.90, run_count: 47 }
  ],
  failure_actions: [
    { step: 3, action_type: "type", text: "Mac", failure_reason: "returned mac and cheese results", failure_count: 12 }
  ],
  metadata: {
    domain: "walmart.com",
    route_pattern: "/search/*",
    structural_hash: "abc123",
    run_count: 47,
    avg_success_rate: 0.82,
    created_at: ISODate,
    last_updated: ISODate
  },
  parent_task_id: null,    // v2 graph-ready
  sub_task_ids: []          // v2 graph-ready
}
```

**Indexes:**
- Atlas Vector Search index (HNSW) on `task_embedding` with filter on `metadata.domain`
- Standard index on `metadata.domain` + `metadata.structural_hash` (for upsert matching)
- Standard index on `metadata.last_updated` (for decay/TTL queries)

**Query pattern:**
```javascript
db.tasks.aggregate([
  { $vectorSearch: {
      index: "task_embedding_index",
      path: "task_embedding",
      queryVector: queryEmbedding,
      numCandidates: 100,
      limit: 5,
      filter: { "metadata.domain": "walmart.com" }
  }},
  { $project: {
      task_description: 1,
      optimal_actions: 1,
      metadata: 1,
      score: { $meta: "vectorSearchScore" }
  }}
])
```

**Do NOT build:** $graphLookup queries, Graph RAG pipelines, multi-collection step-level schemas, or LangChain/LlamaIndex graph integrations.

**Reversible next steps (weeks 1-2):**
- Run Near-Term Tests 1-3 in week 1 before production data ingestion.
- Start trace decay experiment (Test 4) in parallel.
- Implement atomic updates (`$inc` for run_count, `$set` for success rates) to handle concurrent writes to the same task document.
- Set `numCandidates` to 100+ on vector search to compensate for possible HNSW recall issues at small corpus sizes.

**Trigger to revisit:**
- `$vectorSearch` p99 > 150ms at 10K documents on M10 --> evaluate Redis VSS or Pinecone as vector layer.
- Trace decay > 50% step breakage within 7 days --> redesign around semantic actions, add TTL eviction.
- V2 requirements demand weighted shortest-path across shared page states --> evaluate Neo4j as dedicated graph layer.
- Document sizes routinely > 5MB --> split into two-collection model (task summaries + step details).
- Concurrent agent count > 50 with measurable read latency degradation --> evaluate cluster tier upgrade or read replicas.
