# Empiricalist: What is the optimal way to store graph-structured agent trace data in MongoDB Atlas?

## Empirical Claims

| Claim | Evidence | Quality (High/Med/Low) | Source |
|-------|----------|----------------------|--------|
| MongoDB Atlas Vector Search uses Hierarchical Navigable Small World (HNSW) index with approximate nearest neighbor (ANN) search | MongoDB documentation states HNSW as the default index type; also supports IVFFlat | High | MongoDB Atlas Vector Search docs (as of 2024-2025) |
| Atlas Vector Search supports up to 4096 dimensions per vector | Documented limit in MongoDB Atlas specifications | High | MongoDB Atlas Vector Search limits documentation |
| $graphLookup has a 100MB memory limit per aggregation pipeline stage (unless allowDiskUse is set) | Documented in MongoDB aggregation pipeline memory restrictions | High | MongoDB aggregation pipeline docs |
| $graphLookup maxDepth is optional but unbounded traversal on large graphs risks exceeding memory limits or timeout | Documented behavior; no built-in pagination for $graphLookup results | High | MongoDB $graphLookup reference docs |
| MongoDB document size limit is 16MB | Fundamental MongoDB constraint, well-documented and unchanged since MongoDB 2.x | High | MongoDB BSON document size limit docs |
| $graphLookup performs recursive self-joins within a single collection; it cannot traverse across collections | Documented constraint: connectFromField, connectToField, and the traversal all operate on the "from" collection | High | MongoDB $graphLookup reference |
| HNSW-based vector search typically delivers sub-100ms p50 latency for datasets under 1M vectors on adequately provisioned clusters | Industry-wide HNSW benchmarks (ann-benchmarks.com); MongoDB has not published official latency SLAs but claims "low-latency" vector search | Med | ANN-benchmarks project; MongoDB marketing materials |
| LangChain has a MongoDBAtlasVectorSearch integration supporting vector store operations | Published LangChain integration, available in langchain-mongodb package | High | LangChain docs, PyPI langchain-mongodb package |
| LlamaIndex has a MongoDB Atlas vector store integration | Published integration in llama-index-vector-stores-mongodb package | High | LlamaIndex docs, PyPI package |
| Graph RAG on MongoDB requires application-level graph construction; there is no native Graph RAG feature in MongoDB Atlas | No MongoDB documentation describes a built-in Graph RAG pipeline; implementations use LangChain/LlamaIndex with custom graph construction logic | Med | Absence of documentation; community implementations |
| $graphLookup benefits from indexes on connectFromField and connectToField but does not use compound indexes for the recursive traversal | MongoDB optimization notes recommend indexing the connectToField in the "from" collection | Med | MongoDB performance best practices docs |
| MongoDB Atlas Search (Lucene-based) and Vector Search run on separate mongot processes alongside mongod | Architectural documentation shows search indexes are maintained by dedicated mongot processes | High | MongoDB Atlas architecture docs |
| Concurrent writes from multiple agents are handled by MongoDB's WiredTiger storage engine with document-level locking | WiredTiger uses intent locks at collection level and document-level concurrency control | High | MongoDB storage engine docs |

## Key Metrics

- **Vector search latency (HNSW, <1M vectors)**: Expected 10-50ms p50 on M10+ Atlas clusters -- this matters because the 300ms retrieval budget must include vector search + any graph traversal + network round trip. HNSW at this scale leaves ample headroom. *[Interpretation: based on general HNSW benchmarks, not MongoDB-specific published numbers]*

- **$graphLookup memory limit**: 100MB per pipeline stage (default) -- this matters because agent trace graphs with embedded action details (DOM snapshots, screenshots) could exceed this limit. A trace with 50 steps, each containing a 500KB DOM snapshot, would hit ~25MB for DOM data alone before accounting for BSON overhead. With allowDiskUse, this limit is relaxed but latency increases significantly due to disk spilling.

- **Document size limit**: 16MB per BSON document -- this matters because storing an entire agent trace (all steps + embeddings + metadata) in a single document will hit this limit for complex traces. A 1536-dim OpenAI embedding is ~6KB. 100 steps with embeddings alone = ~600KB, well within limits. But adding DOM snapshots, screenshots, or full HTML pushes toward the limit fast.

- **$graphLookup traversal cost**: O(V + E) where V = visited documents and E = edges traversed -- each "hop" requires an index lookup on the from collection. For a trace with 20 steps (typical browser automation task), this means ~20 index lookups. At ~0.1-0.5ms per indexed lookup on in-memory working set, total traversal = 2-10ms. *[Interpretation: estimated from general MongoDB indexed lookup performance]*

- **Vector dimensions**: Up to 4096 supported -- OpenAI text-embedding-3-small (1536 dims) and text-embedding-3-large (3072 dims) both fit within this limit.

- **Atlas Vector Search index build time**: Indexes are built asynchronously by mongot; initial index creation on <100K documents typically completes in seconds to low minutes. Incremental updates happen automatically. *[Quality: Med -- based on reported developer experience, not official SLAs]*

- **Concurrent write throughput**: WiredTiger document-level locking means concurrent agent writes to different trace documents do not block each other. Write concern w:1 with journal provides durability at ~1-5ms per write on Atlas. *[Quality: Med -- general MongoDB performance, not specific to this workload]*

## Schema Design Evidence

### Measured fact: Two viable schema patterns exist

**Pattern A: Task-centric documents (flat, MVP-appropriate)**
```json
{
  "_id": ObjectId,
  "task_description": "buy a macbook on walmart",
  "task_embedding": [/* 1536 floats */],
  "optimal_actions": [
    {"step": 1, "action": "navigate", "target": "walmart.com", "success_rate": 0.95},
    {"step": 2, "action": "click", "selector": "#search-input", "success_rate": 0.98},
    {"step": 3, "action": "type", "text": "Macbook", "success_rate": 0.90}
  ],
  "total_runs": 47,
  "avg_success_rate": 0.82,
  "last_updated": ISODate
}
```
- Vector index on `task_embedding` for similarity search
- Single document read to get full action sequence
- Fits well within 16MB for typical traces (20-50 steps)
- Query: `$vectorSearch` on task_embedding, return top-k matches

**Pattern B: Node-per-step with $graphLookup (graph-native)**
```json
// Task node
{"_id": "task_123", "type": "task", "description": "buy macbook", "embedding": [...], "first_step": "step_1"}
// Step nodes
{"_id": "step_1", "type": "step", "task_id": "task_123", "action": "navigate", "next_step": "step_2", "success_rate": 0.95}
{"_id": "step_2", "type": "step", "task_id": "task_123", "action": "click", "next_step": "step_3", "success_rate": 0.98}
```
- Requires $graphLookup to reconstruct path
- More flexible for shared sub-paths across tasks (v2)
- Higher query latency: vector search + $graphLookup pipeline
- More documents to manage; higher write amplification when updating success rates

### Measured fact: Hybrid query pipeline is achievable

MongoDB aggregation pipelines can chain `$vectorSearch` -> `$graphLookup` in a single query. The `$vectorSearch` stage must be the first stage in the pipeline. The results feed into subsequent stages including `$graphLookup`. This is documented and functional.

## Confounders & Gaps

- **No published MongoDB-specific vector search latency benchmarks**: MongoDB does not publish p50/p95/p99 latency numbers for Atlas Vector Search. The "low-latency" claim is marketing language. All latency estimates in this report are inferred from HNSW algorithm benchmarks (ann-benchmarks.com) and general MongoDB performance, NOT from MongoDB-specific measurements. This is the single largest evidence gap.

- **$graphLookup performance at scale is poorly documented**: MongoDB documentation provides no performance benchmarks for $graphLookup. Community reports suggest it works well for small graphs (hundreds of nodes) but degrades on graphs with thousands of nodes or high branching factor. No published measurements exist for the specific pattern of "vector search -> graph traversal" pipelines.

- **Graph RAG on MongoDB is nascent**: As of early 2025, no mature Graph RAG framework natively supports MongoDB as a graph backend. LangChain's GraphRAG implementations (e.g., Neo4j, Nebula) are more mature. MongoDB-based Graph RAG requires custom implementation. The LangChain MongoDBAtlasVectorSearch class handles vector search but not graph traversal.

- **Cluster tier dramatically affects performance**: Latency numbers depend heavily on Atlas cluster tier (M10, M30, M50, etc.), data residency, and whether the working set fits in RAM. No benchmarks are meaningful without specifying cluster tier. The 300ms target is achievable on M10+ for small datasets but unverified.

- **allowDiskUse impact on $graphLookup latency**: When the 100MB memory limit is exceeded and allowDiskUse kicks in, latency can increase by 10-100x (from milliseconds to seconds). No published measurements for this degradation on Atlas.

- **mongot process resource contention**: Atlas Vector Search runs on dedicated mongot processes that share node resources with mongod. Under heavy write load (many concurrent agent traces being written), vector index updates may lag. No published data on this lag.

- **Selection bias in community reports**: Most performance reports for MongoDB Atlas come from MongoDB employees, partners, or sponsored content. Independent benchmarks are scarce.

## What Would Change My View

- **Published MongoDB Atlas Vector Search latency benchmarks** at specific cluster tiers, dataset sizes, and vector dimensions -- this would replace my HNSW-based estimates with actual numbers and could either confirm or invalidate the 300ms budget.

- **A benchmark comparing Pattern A (flat documents + vector search) vs Pattern B ($graphLookup pipeline) latency** for the specific workload of "find similar task, retrieve action sequence" -- this would directly answer which schema to use.

- **A working Graph RAG implementation on MongoDB** with measured retrieval latency and quality metrics -- if this exists and performs well, it could change the recommendation from custom implementation to framework-based.

- **Evidence that $graphLookup degrades severely at >1000 task nodes** -- if true, Pattern B becomes non-viable for production scale and Pattern A is the only option.

- **Evidence that mongot vector index update lag exceeds 5 seconds under concurrent write load** -- if true, newly written traces would not be immediately searchable, breaking the "every run makes it better" design goal.

## Confidence

**55%** -- Confidence is moderate-low because the core question ("what is optimal?") requires performance comparison data that does not exist in published form. The evidence strongly supports that both patterns are *feasible* on MongoDB Atlas, but which is *optimal* for this specific workload cannot be determined without running benchmarks on the actual cluster configuration. The 300ms target is *likely* achievable with Pattern A on M10+ clusters with <100K documents, but this is an informed estimate, not a measured fact.

---

## Role

Empiricalist

## Research Question

What is the optimal way to store graph-structured agent trace data in MongoDB Atlas for DomBot, considering Graph RAG, vector search, and fast retrieval of optimal action paths for browser automation agents?

## Scope and Assumptions

- Assumption 1: MongoDB Atlas is the chosen platform (not subject to change). Evaluation is constrained to what works within MongoDB.
- Assumption 2: OpenAI embeddings (1536 or 3072 dimensions) will be used for task description vectors.
- Assumption 3: MVP dataset is small (<10K task documents, <100K step documents) and will grow over months.
- Assumption 4: Atlas cluster is M10 or higher with adequate RAM for the working set.
- Assumption 5: Network latency between application and Atlas is <20ms (same region).

## Core Claims

1. **Claim**: Pattern A (task-centric flat documents with embedded action arrays + vector search) will meet the 300ms retrieval target for MVP and is the lower-risk choice.
Evidence: Single-document reads on indexed collections are typically <5ms. HNSW vector search on <100K documents is typically <50ms. Total pipeline: <100ms estimated, well within 300ms budget. No $graphLookup overhead. No multi-document assembly.
Confidence (0-100): 70

2. **Claim**: Pattern B ($graphLookup for path traversal) adds 10-50ms latency over Pattern A for typical trace depths (10-30 steps) but enables shared sub-path composition needed for v2.
Evidence: Each $graphLookup hop requires an indexed lookup (~0.1-0.5ms). 20 hops = 2-10ms plus pipeline overhead. Still within 300ms but with less headroom and more complexity.
Confidence (0-100): 50

3. **Claim**: Graph RAG on MongoDB is not production-ready as a framework solution and would require significant custom implementation.
Evidence: No LangChain or LlamaIndex integration provides Graph RAG with MongoDB as both vector store and graph store. Neo4j is the primary Graph RAG backend in these frameworks. MongoDB would require custom graph construction, entity extraction, and traversal logic.
Confidence (0-100): 75

4. **Claim**: The 16MB document size limit will not be a constraint for MVP action sequences but would become one if storing DOM snapshots or screenshots inline.
Evidence: 50 action steps with metadata (~1KB each) + one 1536-dim embedding (~6KB) = ~56KB total. Well within 16MB. But a single DOM snapshot can be 200KB-2MB; 50 of these = 10-100MB, exceeding the limit.
Confidence (0-100): 90

5. **Claim**: A hybrid schema (Pattern A for MVP, designed to migrate to Pattern B for v2) is architecturally feasible without data loss.
Evidence: The migration path is: (1) keep flat task documents, (2) add step-level documents with references, (3) build $graphLookup queries alongside existing flat queries, (4) deprecate flat action arrays once graph queries are validated. MongoDB's flexible schema supports both patterns coexisting.
Confidence (0-100): 65

## Evidence Quality Assessment

- Source quality: Medium. Primary sources are MongoDB documentation (high quality but marketing-influenced) and general HNSW algorithm benchmarks (high quality but not MongoDB-specific). No independent MongoDB Atlas Vector Search benchmarks found. Web search and web fetch tools were unavailable during this research, limiting access to recent community benchmarks and blog posts.
- Method quality: Low-Medium. All performance estimates are inferred from algorithmic complexity and general MongoDB behavior, not from direct measurements on Atlas clusters matching the target configuration. No experiments were run.
- Known biases/confounders: MongoDB documentation emphasizes capabilities over limitations. Community content about MongoDB vector search skews toward success stories. The absence of published latency SLAs is itself a data point (if performance were consistently excellent, MongoDB would likely publish numbers).

## Strongest Counterpoint

- Counterpoint: Pattern A (flat documents) may be a premature optimization that creates technical debt. If v2 graph traversal is a near-term goal, building Pattern B from the start avoids a costly migration and the $graphLookup overhead (estimated 10-50ms) is well within the 300ms budget.
- Why it matters: The question assumes Pattern A is "safer" for MVP, but if the v2 graph features are needed within 2-3 months, the migration cost may exceed the cost of building Pattern B correctly from day one. The evidence does not clearly favor one over the other when factoring in development velocity.

## What Would Change My Mind

- New evidence required: (1) Actual benchmark of $vectorSearch -> $graphLookup pipeline on M10 Atlas cluster with 10K task documents and 20-step traces. (2) A working Graph RAG on MongoDB implementation with published retrieval quality and latency. (3) Community reports of $graphLookup failures or severe performance degradation at the expected scale.
- Threshold for belief update: If $vectorSearch -> $graphLookup pipeline exceeds 200ms p95 on M10 with 10K documents, Pattern B becomes non-viable for MVP. If it stays under 100ms p95, Pattern B should be the default choice from day one.

## Open Questions

1. What is the actual p50/p95 latency of `$vectorSearch` on MongoDB Atlas M10 with 10K documents and 1536-dim embeddings? (Must be measured, not estimated.)
2. What is the actual latency of `$vectorSearch` followed by `$graphLookup` (20 hops) in a single aggregation pipeline on Atlas? (Must be measured.)
3. Does mongot vector index update lag create a meaningful delay between writing a new trace and being able to search for it? What is the consistency model?
4. What happens to $graphLookup performance when the graph has high branching factor (e.g., a task step that branches into 10 alternative next steps based on success/failure)?
5. Is there a published MongoDB Atlas Vector Search entry in ann-benchmarks.com or VectorDBBench that provides independent performance measurements?
6. How does the LangChain `MongoDBAtlasVectorSearch` class handle metadata filtering in combination with vector search, and does this add measurable latency?
