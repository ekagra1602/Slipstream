Gray — browser-use Integration + Prompt Design

  Owns: The tools AND how the LLM actually uses the context.

  - @controller.action tools (dombot_query, dombot_report)
  - System prompt engineering — this is the hard part. How do you instruct the agent to always call DomBot first? How do you phrase the
  returned optimal path so the LLM actually follows it instead of doing its own thing? What happens when the optimal path is wrong for this
  specific run?
  - Format the output of dombot_query — the shape of what the LLM sees
  - Handle edge cases: what if there's no data yet (cold start)? What if the returned path is stale?
  - Testing against different task types — does the prompt work for "buy a macbook" AND "book a flight" AND "fill out a form"?
  - use_cloud=True setup + demo script

  ---
Eric — MongoDB + Data Layer

  Owns: Everything that goes in and out of the database.

  - MongoDB Atlas setup, collections, vector search index
  - Embedding pipeline (OpenAI)
  - query_context(task, domain) → $vectorSearch → return optimal actions
  - store_step() / store_trace() → ingest + update task nodes
  - Confidence scoring — how do you merge multiple traces into one optimal path? When 3 runs disagree, which actions win?
  - Schema design and data modeling

  ---
Nathan — Laminar + Trace Processing Pipeline

  Owns: How raw agent runs become useful data in MongoDB.

  - Laminar instrumentation — Laminar.initialize(), custom span attributes
  - Pipeline: Laminar traces → parse steps → determine success/failure per step → call Person 2's store_trace()
  - Trace comparison logic — across N runs, which steps are common to successful runs vs failed runs?
  - Convergence logic — when has a task node "converged" enough to be confident? (run_count threshold, success rate)
  - Analytics / observability — cache hit rate, step reduction metrics, confidence over time