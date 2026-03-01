# Research Question

## Core Question

What is the optimal way to store graph-structured agent trace data in MongoDB Atlas for DomBot, considering Graph RAG, vector search, and fast retrieval of optimal action paths for browser automation agents?

## Why This Matters

DomBot captures browser-use agent traces (every step: page visited, action taken, success/failure) and needs to store them so that future agent runs can retrieve the optimal path for similar tasks. The data is naturally graph-shaped (page states as nodes, actions as edges with success rates). We need the fastest possible retrieval to inject optimal paths before the agent's first step. The choice of storage pattern determines whether the system works at <300ms or is too slow to be useful.

## Scope

- In scope: MongoDB Atlas capabilities (vector search, $graphLookup, document design, indexing strategies), Graph RAG patterns on MongoDB, alternative graph-on-document approaches, performance characteristics, schema design for task nodes with embeddings
- Out of scope: Non-MongoDB solutions (Neo4j, Pinecone standalone), the Laminar trace capture pipeline (already decided), browser-use integration details (already decided)

## Constraints

- Time budget: MVP in 2-4 weeks
- Risk tolerance: Moderate — prefer proven patterns over cutting-edge
- Resources: MongoDB Atlas (cloud), Python backend, OpenAI embeddings
- Must support vector similarity search on task descriptions
- Must support graph-like traversal of action paths
- Must handle concurrent writes from multiple consumer agent runs
- Target: <300ms retrieval for optimal path lookup

## Decision Context

- Decision deadline: Now — this is the next build step
- What decision this research should inform: The MongoDB schema design, indexing strategy, and query patterns for DomBot's shared trace database. Specifically: should we use $graphLookup for path traversal, pure vector search with embedded action sequences, Graph RAG with LangChain/LlamaIndex on MongoDB, or a hybrid approach? What does the document schema look like? What indexes do we need?

## Working Prompt

What is the optimal way to store graph-structured agent trace data in MongoDB Atlas for DomBot, considering Graph RAG, vector search, and fast retrieval of optimal action paths for browser automation agents

## Context from conversation

- DomBot wraps browser-use agents via `use_cloud=True` to get cloud infrastructure while keeping SDK control
- Laminar auto-captures every agent step as traces
- For MVP1, a node = a task (e.g., "buy a macbook on walmart") with stored optimal actions
- Vector search matches task intent ("buy macbook" ≈ "purchase mac laptop")
- Graph traversal is v2 (composing sub-tasks), but schema should not preclude it
- The shared cache compounds across all users — every run makes it better
- MongoDB Atlas chosen because it handles vector search + document storage + $graphLookup in one DB
- Supermemory considered but doesn't do true graph traversal
- The system learns which steps fail and routes around them (e.g., "search Mac → mac and cheese" gets deprioritized, "search Macbook → electronics" gets promoted)
