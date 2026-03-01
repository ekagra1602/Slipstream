# Falsifier: Optimal Storage for Graph-Structured Agent Trace Data in MongoDB Atlas

## Strongest Current Thesis

MongoDB Atlas is the optimal single database for DomBot's MVP because it handles vector search (task matching via embeddings), document storage (traces and DOM maps), and graph traversal ($graphLookup for path optimization) in one system, with <300ms retrieval latency. The "one database" approach reduces operational complexity and is sufficient for MVP scale.

## Falsification Criteria

This thesis is false if we observe any of the following:

1. **Latency breach**: MongoDB Atlas Vector Search + $graphLookup combined query exceeds 300ms at MVP-realistic scale (1,000 task nodes, 100,000 traces, 1536-dimension OpenAI embeddings).
2. **$graphLookup collapse**: $graphLookup hits the 100MB aggregation pipeline memory limit or degrades to >1s at graph depths of 10+ with thousands of connected nodes.
3. **Document size wall**: Realistic action sequences for complex browser tasks (50+ steps with DOM snapshots) exceed the 16MB BSON document limit, forcing a fundamental schema redesign.
4. **Vector search quality gap**: MongoDB Atlas Vector Search recall@10 falls below 90% compared to dedicated vector stores (Pinecone, Qdrant) on the same embedding corpus, making task matching unreliable.
5. **Concurrent write contention**: Multiple simultaneous agent runs writing traces to the same collection cause write lock contention that pushes read latency above 300ms.

## Kill-Shot Tests

| Test | Expected signal if thesis is TRUE | Expected signal if thesis is FALSE | Feasibility |
|------|----------------------------------|-----------------------------------|-------------|
| **KS1: Combined vector+graph query latency** -- Run `$vectorSearch` to find top-5 matching tasks, then `$graphLookup` to traverse their action paths (depth 10), on a collection with 10K task documents and 1536-dim vectors. Measure p50 and p99 latency. | p99 < 300ms | p99 > 500ms, especially if $graphLookup dominates at >200ms alone | High -- can run on Atlas free/shared tier in 1 hour |
| **KS2: $graphLookup memory ceiling** -- Create a collection with 50K nodes, each connected to 5-20 others (realistic task decomposition graph). Run $graphLookup with `maxDepth: 15`. Measure memory usage and whether it completes. | Completes in <500ms within 100MB memory | Fails with "exceeded memory limit" error, or requires `allowDiskUse` which pushes latency to multi-seconds | High -- synthetic data generation + single query |
| **KS3: Document size stress test** -- Serialize a realistic complex browser task trace: 80 steps, each with a DOM snapshot (~50KB compressed), action metadata, screenshots references, success/failure flags. Measure BSON size. | Total document < 5MB, well within 16MB limit | Total document > 16MB, or even > 10MB creating fragility for growth | High -- pure calculation, no infrastructure needed |
| **KS4: Vector search recall benchmark** -- Load 10K task descriptions with OpenAI embeddings into both MongoDB Atlas Vector Search (HNSW) and Qdrant. Run 100 query tasks and compare recall@10. | MongoDB recall@10 within 5% of Qdrant | MongoDB recall@10 more than 10% below Qdrant, indicating HNSW tuning limitations | Medium -- requires both systems running, ~2 hours setup |
| **KS5: Write contention under concurrent agents** -- Simulate 10 concurrent agent runs, each writing 50 trace steps/minute to the same collection. Measure read latency of vector search queries during writes. | Read latency stays < 300ms with concurrent writes | Read latency spikes to > 500ms during write bursts, or writes themselves slow below acceptable throughput | Medium -- requires Atlas cluster (not free tier) and load testing script |
| **KS6: $graphLookup vs. application-level BFS** -- Implement the same path traversal both as $graphLookup aggregation and as application-level BFS with individual `find()` calls (with connection pooling). Compare latency at depth 5 and depth 10. | $graphLookup is 2-5x faster than app-level BFS | App-level BFS is comparable or faster (meaning $graphLookup adds pipeline overhead without real benefit for shallow graphs) | High -- same dataset, two query implementations |

## Failure Mode Ranking

| Failure Mode | Plausibility (H/M/L) | Impact if Realized |
|-------------|----------------------|-------------------|
| **FM1: $graphLookup hits 100MB memory limit on realistic graphs** -- MongoDB's aggregation pipeline has a 100MB memory limit per stage. $graphLookup materializes all traversed documents in memory. With thousands of nodes at depth 10+, each node carrying embeddings (1536 floats = ~6KB) plus action metadata, this ceiling is reachable. `allowDiskUse: true` bypasses it but adds disk I/O latency. | **HIGH** | **Critical** -- The entire "graph traversal in MongoDB" claim collapses. Would need to either strip embeddings from graph nodes (losing the combined query advantage) or move graph traversal to application layer (losing the "one query" benefit). |
| **FM2: Vector search and $graphLookup cannot compose in a single aggregation pipeline efficiently** -- Atlas Vector Search runs on a separate `mongot` process, not the core `mongod`. The `$vectorSearch` stage must be the first stage in the pipeline. Combining it with `$graphLookup` requires either two separate queries or pipeline gymnastics that negate the single-system advantage. | **HIGH** | **Severe** -- If you cannot do vector search then graph traversal in one round trip, you are making two queries anyway (vector search to find matching tasks, then graph lookup to traverse paths). The latency budget is now split between two queries plus network overhead, making <300ms much harder. |
| **FM3: 16MB document limit forces schema fragmentation for large traces** -- A single browser automation trace with 80+ steps including DOM state, screenshots, and metadata could approach or exceed 16MB. Even if it doesn't exceed the limit, large documents hurt read performance (full document must be fetched even for partial reads unless using projection). | **MEDIUM** | **Moderate** -- Solvable by storing steps as separate documents with a trace_id reference. But this means the "document model is natural for traces" claim weakens, and you are essentially doing relational joins via $lookup, losing the document model advantage. |
| **FM4: Atlas Vector Search index lag on writes** -- Atlas Vector Search indexes are eventually consistent. When an agent writes a new trace, it may not be immediately searchable by subsequent agents. The sync delay is documented to be potentially seconds to minutes depending on cluster load. | **MEDIUM** | **Moderate** -- For a "shared cache that compounds across users," stale reads mean one agent's discovery does not help the next agent for some lag window. Not fatal for MVP but undermines the real-time learning claim. |
| **FM5: HNSW recall degradation at small corpus sizes** -- HNSW (the algorithm behind Atlas Vector Search) is optimized for large corpora. At MVP scale (1K-10K task nodes), the index may not have enough data for HNSW to outperform brute-force exact search, and the recall at default settings may be poor for nuanced task matching ("buy macbook" vs "buy mac laptop" vs "buy mac and cheese"). | **LOW-MEDIUM** | **Moderate** -- Could cause false matches early on. Tunable via `numCandidates` parameter (oversample and rerank), but this adds latency. If you are using exact search anyway at MVP scale, the vector search index adds overhead for no benefit. |
| **FM6: Concurrent write contention on WiredTiger** -- MongoDB uses document-level locking in WiredTiger. Multiple agents writing to the same collection should not lock each other. But if write volume is high enough to cause cache pressure or checkpoint stalls, read latency can spike. | **LOW** | **Low for MVP** -- 10 concurrent agents is manageable. This becomes a problem at 100+ concurrent agents, which is post-MVP. |
| **FM7: $graphLookup cannot use indexes effectively for filtered traversals** -- $graphLookup supports a `restrictSearchWithMatch` filter, but it cannot use compound indexes that include the `connectFromField`/`connectToField` along with the filter. This means filtered graph traversals (e.g., "only traverse edges with success_rate > 0.7") do collection scans at each hop. | **MEDIUM** | **Severe** -- The core use case is "find the optimal path," which requires filtering by success rate. If every hop does a collection scan, latency scales linearly with collection size. At 100K trace documents, each hop could take 50-100ms, making a depth-5 traversal 250-500ms before any vector search. |

## Detailed Analysis of Top Failure Modes

### 1. The $graphLookup Memory Problem (FM1)

MongoDB's aggregation pipeline imposes a 100MB memory limit per stage by default. `$graphLookup` materializes all visited documents during traversal. Consider DomBot's scenario:

- 10K task nodes, each ~10KB (embeddings + metadata) = 100MB total collection size
- A graph traversal at depth 10 touching even 500 nodes = 5MB in memory
- This is within limits for moderate graphs

However, if nodes grow (DOM snapshots, action sequences) or the graph is dense, the 100MB ceiling becomes real. The `allowDiskUse: true` flag bypasses this but introduces disk I/O that can add 100-500ms of latency, potentially blowing the 300ms budget.

**Verdict**: Not an immediate killer at MVP scale, but a ticking time bomb as data grows.

### 2. The Two-Process Architecture Problem (FM2)

This is the most architecturally damning finding. MongoDB Atlas Vector Search runs on a separate `mongot` process that syncs from the primary `mongod`. This has two implications:

- `$vectorSearch` must be the **first stage** in any aggregation pipeline. You cannot do `$graphLookup` first and then vector search within it.
- The typical pattern becomes: (1) `$vectorSearch` to find matching tasks, (2) pipe those IDs into `$graphLookup` to traverse paths. But `$graphLookup` on the output of `$vectorSearch` requires the traversal collection to be specified upfront and the connection fields to work on the vector search results.

In practice, this likely means two separate queries or an awkward pipeline where `$graphLookup` follows `$vectorSearch` but operates on a different collection via `$lookup`-like semantics. The "single unified query" narrative fractures.

### 3. The Schema Tension (FM3)

The document model creates a genuine tension:

- **Option A**: Store entire traces as single documents (natural, but risks 16MB limit for complex tasks)
- **Option B**: Store steps as separate documents with references (scales better, but now you are doing joins)
- **Option C**: Store denormalized summaries in task nodes with references to full traces (hybrid, but duplicates data)

None of these are clean. Option C is most practical but means the "document model naturally fits" claim is overstated -- you are engineering around limitations, same as you would with any database.

### 4. Vector Search Index Sync Lag (FM4)

Atlas Vector Search indexes sync from `mongod` to `mongot` asynchronously. MongoDB documentation acknowledges that new or updated documents may not appear in vector search results immediately. For DomBot's use case where "every run makes the cache better," there is a window where Agent B cannot benefit from Agent A's just-completed trace. The lag is typically seconds but can be longer under load.

### 5. The "Jack of All Trades" Tax

MongoDB Atlas does vector search, document storage, and graph traversal. But:
- Its vector search (HNSW) has fewer tuning knobs than Pinecone or Qdrant (no product quantization, limited distance metrics in earlier versions)
- Its graph traversal ($graphLookup) is a single aggregation stage, not a full graph query language (no shortest path, no weighted traversal, no Dijkstra)
- Its document storage is excellent, but that is table stakes

The risk is not that any single capability fails catastrophically, but that each is 70-80% as good as the specialized alternative, and the combined mediocrity adds up.

## Residual Claim

After attempted falsification, the following survives:

**MongoDB Atlas is a pragmatically acceptable (not optimal) single database for DomBot's MVP, provided the team:**

1. Accepts two-query patterns (vector search, then separate graph/path lookup) rather than assuming a single unified pipeline
2. Stores action steps as separate documents with trace references (not monolithic trace documents)
3. Sets `numCandidates` high enough on vector search to compensate for HNSW recall at small corpus sizes
4. Plans to revisit the architecture when hitting ~50K task nodes or when needing true graph algorithms (shortest weighted path)
5. Accepts eventual consistency on vector search index updates (seconds of lag)

The thesis as stated -- that MongoDB is "optimal" and handles all three concerns "in one system" with a single <300ms query -- is likely false in the strict sense. But the weaker claim -- that MongoDB is good enough for MVP and avoids the operational cost of running three systems -- is defensible.

The real decision is not "is MongoDB optimal?" but "is the 20-30% capability gap worth the operational cost of running MongoDB + Neo4j + Pinecone?" For a 2-4 week MVP with moderate risk tolerance, the answer is probably no -- stick with MongoDB, but do so with eyes open about its limitations rather than under the illusion that it is optimal.

## Confidence in Residual

**45%** -- The strict thesis ("optimal," "one system," "<300ms combined") is likely false due to the two-process architecture forcing multi-query patterns and $graphLookup limitations on filtered traversals. The weaker "good enough for MVP" claim survives but depends on scale assumptions that need empirical validation via Kill-Shot Tests KS1 and KS2 before committing.
