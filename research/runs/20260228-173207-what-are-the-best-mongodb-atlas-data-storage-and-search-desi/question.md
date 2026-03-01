# Research Question

## Core Question

What are the best MongoDB Atlas data storage and search designs for DomBot MVP1 graph-RAG, and what should the agent do vs avoid doing given current context?

## Why This Matters

DomBot MVP1 proposes shared learning from browser-use traces and fast retrieval of optimal actions. Storage/search design determines latency, correctness, privacy, and scaling.

## Scope

- In scope: Atlas-native schema options, vector + lexical/hybrid retrieval, graph traversal options, indexing, latency/perf considerations, operational tradeoffs.
- Out of scope: full multi-cloud comparison, non-Atlas managed graph databases unless required as contrast.

## Constraints

- Time budget: MVP-first, production-ready enough for early users.
- Risk tolerance: moderate; reliability and privacy must not regress baseline browser-use.
- Stack context: browser-use + Laminar traces + MongoDB Atlas + DomBot middleware.

## Decision Context

- Decision deadline: immediate MVP1 architecture implementation.
- Decision informed: whether to use Atlas as the primary store for task nodes + traces + vector retrieval and how to structure graph-RAG behavior safely.

## DomBot Context Sources (Notion)

- https://www.notion.so/316fe709905c81c18451c1288136d054 (DomBot — MVP1 Architecture)
- https://www.notion.so/315fe709905c81af8273e7e1147c52a4 (DomBot — Integration)
- https://www.notion.so/315fe709905c811ca60ce9a2c705ad59 (How the DomBot Demo Works with browser-use)

## Atlas / MongoDB Primary Sources

- https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/
- https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-stage/
- https://www.mongodb.com/docs/atlas/atlas-search/hybrid-search/vector-search-with-full-text-search/
- https://www.mongodb.com/docs/manual/reference/operator/aggregation/graphLookup/
- https://www.mongodb.com/docs/atlas/atlas-search/about/deployment-options/
- https://www.mongodb.com/docs/atlas/architecture/current/scalability/
- https://www.mongodb.com/docs/manual/core/timeseries/timeseries-best-practices/
- https://www.mongodb.com/developer/products/mongodb/retail-reference-architecture-part-2-building-knowledge-graph-rag/
