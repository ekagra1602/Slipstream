# Theorist: What is the optimal way to store graph-structured agent trace data in MongoDB Atlas for DomBot?

## Model Comparison

| Model | Core Mechanism | Predictions | Assumptions | Failure Conditions |
|-------|---------------|-------------|-------------|-------------------|
| **A: Pure Vector Search** | Embed full task descriptions with OpenAI embeddings; $vectorSearch retrieves top-k similar tasks; action sequences stored as arrays within retrieved documents | Retrieval <100ms for vector lookup alone; accuracy depends on embedding quality for task matching; no graph traversal capability | Task similarity is well-captured by embedding space; optimal action sequences are stable enough to store as flat arrays; v2 sub-task composition is not needed yet | Fails when semantically similar tasks require different action paths (e.g., "buy macbook on walmart" vs "buy macbook on amazon"); fails at sub-task composition; cannot represent branching or conditional paths |
| **B: $graphLookup Graph Traversal** | Store page states as documents (nodes) with `connectFromField`/`connectToField` references; actions are edges; $graphLookup traverses the graph to find optimal paths | Enables true path traversal; can find multi-hop paths; schema naturally represents the page-state-to-action-to-page-state structure | Graph fits in the 100MB aggregation pipeline memory limit; depth of traversal is bounded; indexes on connection fields are sufficient for performance | Fails when graph grows beyond memory limits (100MB pipeline limit); $graphLookup has no built-in cost/weight optimization (cannot natively find "best" path); cold-start latency increases with graph size; no native vector search integration within the traversal |
| **C: Graph RAG (LangChain/LlamaIndex on MongoDB)** | Use a graph RAG framework to extract knowledge graph triples from traces; combine knowledge graph traversal with vector retrieval; framework manages the graph-vector hybrid | Gets framework-level abstractions for graph+vector; can leverage community patterns; potentially handles sub-task composition via graph structure | Framework maturity on MongoDB is sufficient; latency overhead from framework abstraction layer is acceptable; the framework's graph extraction maps well to agent trace data (it was designed for document-to-knowledge-graph, not action-trace-to-execution-graph) | Fails due to impedance mismatch: Graph RAG frameworks extract entity-relationship triples from text, not action sequences from execution traces; adds 50-200ms framework overhead; dependency on framework release cycles; debugging is opaque |
| **D: Hybrid (Vector + Embedded Actions + $graphLookup for v2)** | Vector search for task matching (v1); action sequences embedded in task documents (v1); $graphLookup-ready schema with `parentTask`/`childTasks` fields for v2 sub-task composition | Meets <300ms target in v1 with single vector lookup + document read; schema supports v2 graph traversal without migration; write throughput is simple (one document per task completion) | The hybrid does not need to exercise both capabilities simultaneously in v1; the schema overhead of graph-ready fields does not degrade v1 performance; v2 requirements are predictable enough to design for now | Fails if v2 requirements diverge significantly from predicted sub-task structure; slight over-engineering risk for v1 if v2 never materializes; more complex schema than strictly needed for v1 |
| **E: Denormalized Document Model** | Single collection; each task document contains everything: embedding, action array, DOM snapshots, success metrics, failure history; no references between documents | Simplest possible reads (one document, one query); fastest writes (single insert); easiest to reason about; trivially meets <300ms | Task data is self-contained; cross-task relationships are not needed for v1; the document size stays under MongoDB's 16MB limit; no need for joins or lookups | Fails when documents grow too large (many action variants, full DOM snapshots); fails when sub-task composition is needed (no graph structure); fails when you need to query across task boundaries (e.g., "which page states appear in multiple tasks") |

## Mechanism-Level Reasoning

### Leading Model: D (Hybrid) with E (Denormalized) as the v1 implementation

The causal chain for the recommended approach:

1. **Agent completes a task run.** Laminar captures every step as a trace (page visited, action taken, DOM state, success/failure).

2. **Trace is processed into a task document.** The trace is distilled into a single document containing:
   - `task_description`: natural language ("buy a macbook on walmart")
   - `task_embedding`: OpenAI embedding vector (1536 dimensions)
   - `optimal_actions`: ordered array of action objects, each with `{step, action_type, selector, url, success_rate, dom_context}`
   - `failure_actions`: array of actions that failed, with failure reasons
   - `metadata`: `{domain, route_pattern, structural_hash, created_at, run_count, last_updated}`
   - `parent_task_id`: null for v1 (graph-ready field for v2)
   - `sub_task_ids`: [] for v1 (graph-ready field for v2)

3. **Document is upserted into MongoDB Atlas.** If a matching task exists (by structural hash + domain + route pattern), the existing document is updated with new success/failure data. Otherwise, a new document is inserted. This is a single write operation.

4. **Vector search index exists on `task_embedding`.** MongoDB Atlas maintains an ANN (Approximate Nearest Neighbor) index on the embedding field using HNSW (Hierarchical Navigable Small World) algorithm.

5. **Future agent requests optimal path.** Before the agent's first step:
   - Agent sends task description to DomBot
   - DomBot generates embedding via OpenAI API (~100-300ms, can be cached/precomputed)
   - DomBot runs `$vectorSearch` on the embedding field (~10-50ms on Atlas with warm index)
   - Top-k results are returned as full documents (action sequences included)
   - DomBot filters by domain/route if needed (using `filter` param in $vectorSearch, not post-filtering)
   - Optimal action sequence is injected into the agent's context

6. **Total retrieval latency:** ~100-350ms (dominated by embedding generation, not MongoDB query). The MongoDB portion alone is well under 100ms. [Inference, based on documented ANN search characteristics and typical Atlas cluster latency.]

7. **Graph structure for v2.** When sub-task composition is needed, the `parent_task_id` and `sub_task_ids` fields enable $graphLookup traversal without schema migration:
   ```javascript
   db.tasks.aggregate([
     { $match: { _id: parentTaskId } },
     { $graphLookup: {
         from: "tasks",
         startWith: "$sub_task_ids",
         connectFromField: "sub_task_ids",
         connectToField: "_id",
         as: "subtask_tree",
         maxDepth: 5
     }}
   ])
   ```

### Why E is the correct v1 and D is the correct v1+v2

For v1, Model E (denormalized single document) is functionally identical to Model D. The only difference is that D adds two empty/null fields (`parent_task_id`, `sub_task_ids`) that cost negligible storage and zero query overhead. D is therefore strictly dominant over E for the same v1 cost with v2 optionality.

### Why not B ($graphLookup first)?

Model B treats the problem as a graph problem from day one. This is premature because:

- **v1 does not need graph traversal.** A task maps to a single optimal action sequence. There is no multi-hop path to traverse.
- **$graphLookup has a 100MB memory limit** per aggregation pipeline stage (unless `allowDiskUse` is set, which adds latency). For a growing trace database, this becomes a constraint.
- **$graphLookup has no native cost optimization.** It returns all reachable nodes, not the "best" path. You would need application-level Dijkstra/A* on top of the returned subgraph. [Established fact from MongoDB documentation.]
- **$graphLookup does not integrate with $vectorSearch in the same pipeline stage.** You cannot do "find semantically similar tasks, then traverse their graph neighborhoods" in a single pipeline. You need two stages or two queries. [Established fact from MongoDB aggregation pipeline constraints.]

### Why not C (Graph RAG)?

Model C has a fundamental impedance mismatch:

- **Graph RAG frameworks (LangChain GraphTransformers, LlamaIndex KnowledgeGraphIndex) are designed to extract entity-relationship triples from unstructured text.** Example: "Apple is a company headquartered in Cupertino" becomes `(Apple, headquartered_in, Cupertino)`.
- **DomBot's data is structured execution traces.** The "graph" is not extracted from text -- it is directly observed: page state S1 + action A leads to page state S2 with probability P. This is a state machine, not a knowledge graph.
- **Using Graph RAG would mean:** (a) serializing structured trace data into text, (b) having an LLM extract triples from that text, (c) storing those triples, (d) querying them. This is a round trip through unstructured representation for data that was structured to begin with. [Inference, but strongly supported by the architecture of existing Graph RAG frameworks.]

### Why not A (Pure Vector Search)?

Model A works for v1 but has no path to v2. It is Model E minus the graph-ready fields. Since adding those fields costs nothing, A is strictly dominated by D.

## Testable Predictions

1. **Vector search retrieval latency <50ms on Atlas M10+ cluster with <100k documents** -- test by benchmarking `$vectorSearch` with OpenAI 1536-dim embeddings on a seeded collection of 1k, 10k, 100k task documents.

2. **End-to-end retrieval (embedding generation + vector search + document return) <350ms** -- test by measuring full round trip from task description string to returned action sequence, including OpenAI API call for embedding.

3. **Task matching accuracy >85% for semantically equivalent tasks** -- test by creating a test set of task description pairs that should match (e.g., "buy a macbook on walmart" and "purchase a mac laptop from walmart.com") and measuring recall@5.

4. **Single document model stays under 16MB for tasks with <500 action steps** -- test by computing worst-case document size: 500 actions * ~2KB per action (selector + DOM context) = ~1MB, well under 16MB. DOM snapshots are the risk factor.

5. **$graphLookup on `parent_task_id`/`sub_task_ids` returns sub-task tree in <100ms for trees of depth 5 and branching factor 3** -- test by seeding a hierarchical task collection and benchmarking the aggregation.

6. **Write throughput supports 100 concurrent agent completions/second with single-document upserts** -- test by load testing with concurrent upsert operations on an Atlas M10 cluster.

7. **Models A, D, and E make identical predictions for v1 performance** -- this is by design. They only diverge at v2, when sub-task composition is introduced. Any benchmark that shows a difference between A/D/E in v1 would indicate implementation error, not model difference.

## Internal Consistency Check

- **Contradiction: "schema should not preclude graph traversal" vs. "no graph needed for v1."** These are not actually contradictory -- adding null/empty graph fields to a denormalized document has zero cost. But there is a subtle risk: if the v2 graph structure ends up being fundamentally different from parent-child task composition (e.g., if it needs to be a DAG of page states, not a tree of tasks), then the pre-planned fields are useless. Mitigation: the fields are cheap to add and cheap to ignore.

- **Boundary condition: document size.** If DomBot stores full DOM snapshots in each task document, documents can exceed 16MB. The model assumes DOM snapshots are stored as compact structural hashes or references, not full HTML. If full DOM storage is required, a separate collection for DOM snapshots (referenced by ID) would be needed, partially breaking the denormalized model.

- **Boundary condition: embedding staleness.** If OpenAI changes its embedding model, all stored embeddings become incompatible with new query embeddings. The model assumes embedding model stability or a re-embedding migration strategy.

- **Boundary condition: action sequence divergence.** If the same task has multiple valid action sequences (e.g., different paths to checkout), the single-document model must handle this. The model assumes a single `optimal_actions` array, but reality may require multiple ranked sequences. This is solvable within the document model (array of arrays) but increases document size.

- **Boundary condition: concurrent writes to the same task document.** If two agents complete the same task simultaneously and both try to update success rates, one write may be lost. Mitigation: use `$inc` and `$push` atomic operators rather than full document replacement.

## Confidence

**78%** -- Model D (Hybrid with denormalized v1) is the clear winner for the stated requirements, but uncertainty comes from three sources: (1) the v2 graph structure is speculative and may not match the parent-child model assumed here, (2) there is limited published benchmarking of $vectorSearch + $graphLookup in the same application on Atlas, and (3) the document size boundary depends on decisions about DOM snapshot granularity that have not been finalized.

---

## Scope and Assumptions

- Assumption 1: MongoDB Atlas M10 or higher cluster is available, which supports Atlas Vector Search indexes.
- Assumption 2: OpenAI `text-embedding-3-small` or `text-embedding-3-large` is used, producing 1536-dim or 3072-dim vectors.
- Assumption 3: Task volume is <100k unique tasks in the first year (MVP scale), growing to ~1M in year 2.
- Assumption 4: The primary query pattern is "given a task description, return the best known action sequence" -- not "given a page state, return all tasks that visit this page."
- Assumption 5: DOM snapshots are stored as structural hashes or compact representations, not full HTML trees.

## Core Claims

1. **Claim:** For v1 (single-task retrieval), a denormalized document model with vector search is optimal and any graph structure is unnecessary overhead.
   Evidence: The v1 query pattern is a single vector similarity lookup followed by reading one document. No joins, no traversals, no multi-hop queries. Adding graph structure to v1 queries adds latency without adding capability.
   Confidence: 92

2. **Claim:** $graphLookup is the correct mechanism for v2 sub-task composition, but only if the graph is a shallow tree (depth <10, branching factor <10).
   Evidence: $graphLookup operates within the 100MB aggregation memory limit. A tree of depth 5 with branching factor 3 produces ~364 nodes, each ~10KB = ~3.6MB, well within limits. But a broad graph (depth 10, branching 10) produces 10 billion nodes, which is infeasible.
   Confidence: 70

3. **Claim:** Graph RAG frameworks (LangChain, LlamaIndex) are a poor fit for this problem because agent execution traces are structured data, not unstructured text requiring knowledge extraction.
   Evidence: Graph RAG frameworks use LLM-based entity extraction to build knowledge graphs from documents. DomBot's trace data is already structured (page state, action, result). Using Graph RAG would add an unnecessary LLM round-trip to re-structure already-structured data.
   Confidence: 88

## Evidence Quality Assessment

- Source quality: Mixed. MongoDB documentation is authoritative for feature capabilities and limits. Performance claims are based on general ANN search characteristics and MongoDB architecture, not DomBot-specific benchmarks. Graph RAG framework analysis is based on direct inspection of framework architectures (LangChain GraphTransformer, LlamaIndex KnowledgeGraphIndex).
- Method quality: Theoretical analysis and architectural reasoning. No empirical benchmarks specific to this use case exist yet. The testable predictions section is designed to close this gap.
- Known biases/confounders: There is a bias toward simplicity in the analysis (preferring the denormalized model). This is mitigated by the explicit rule not to treat parsimony as evidence. The denormalized model is preferred because it makes identical predictions to more complex models for v1, not because it is simpler.

## Strongest Counterpoint

- Counterpoint: The denormalized document model may create a "schema debt" trap where v2's actual graph requirements are fundamentally incompatible with the v1 document structure, requiring a painful migration.
- Why it matters: If v2 needs a true page-state graph (where the same page state appears as a node in thousands of task paths), the denormalized model duplicates that state across thousands of documents. A normalized graph model (Model B) would share the node. The migration from denormalized to normalized would require reshaping every document.

## What Would Change My Mind

- New evidence required: (1) A benchmark showing $graphLookup + $vectorSearch in the same pipeline achieving <300ms on a realistic dataset. This would make Model B more viable for v1. (2) A Graph RAG framework that natively handles structured execution traces (not text documents). This would make Model C viable. (3) Evidence that v2 sub-task composition requires a page-state-level graph (not a task-level tree). This would undermine Model D's graph-ready schema.
- Threshold for belief update: If any benchmark shows the denormalized model exceeding 300ms for the primary query pattern at <100k documents, or if $graphLookup + $vectorSearch achieves <100ms combined, the ranking changes.

## Open Questions

1. What is the actual latency of `$vectorSearch` on Atlas M10 with 1536-dim vectors at 10k, 50k, 100k document scale? No published DomBot-specific benchmarks exist.
2. Can `$vectorSearch` and `$graphLookup` be combined in a single aggregation pipeline, or do they require separate queries? MongoDB documentation is ambiguous on this for Atlas Vector Search specifically.
3. What is the right granularity for DOM state storage -- full snapshots, structural hashes, or element-level references? This determines whether the 16MB document limit is a real constraint.
4. Should action sequences be stored as ordered arrays (current assumption) or as a decision tree structure (action A at state S1 leads to S2 with probability P1 or S3 with probability P2)?
5. How should embedding model versioning be handled -- store the model version with each embedding, or re-embed on model change?
