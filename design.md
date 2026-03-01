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

  Status: Done — tools.py, prompts.py, and integration tests (tests/test_dombot.py) all implemented.

  ---
Eric — MongoDB + Data Layer

  Owns: Everything that goes in and out of the database.

  - MongoDB Atlas setup, collections, vector search index
  - Embedding pipeline (OpenAI text-embedding-3-small, 1536 dimensions)
  - query_context(task, domain) → $vectorSearch → return optimal actions
  - store_step() / store_trace() → ingest + update task nodes
  - Confidence scoring — how do you merge multiple traces into one optimal path? When 3 runs disagree, which actions win?
  - Schema design and data modeling

  Status: Core implementation done. Waiting on MongoDB Atlas cluster provisioning.

  ### What's implemented (db/)

  **db/config.py** — env-based config (MONGODB_URI, OPENAI_API_KEY, model/dimension constants).

  **db/embeddings.py** — embed_task() wraps OpenAI embeddings API.

  **db/db.py** — full shared contract:
  - query_context(task, domain) → OptimalPath | None
  - store_step(task, domain, step) → None
  - store_trace(task, domain, trace, success) → None

  Key internals:
  - _action_signature(step) — creates "action:target" or "action:target:value" keys
  - _recompute_optimal_path() — called after store_trace, rebuilds optimal_actions and confidence
  - _validate_inputs() / _validate_step() — raises ValueError on empty/whitespace inputs

  ### Confidence scoring

  confidence = min(0.99, success_rate * 0.7 + volume_factor * 0.3)

  - success_rate = _success_count / run_count
  - volume_factor = min(1.0, run_count / 10) — ramps up over first 10 runs
  - Capped at 0.99

  ### Optimal action selection

  A step makes it into optimal_actions when:
  - Frequency ≥ 50% of successful runs (attempt_count / success_count ≥ 0.5)
  - Success rate ≥ 70%
  - Sorted by success rate desc, then attempt count desc

  ### Vector search pipeline

  Uses $vectorSearch with an inline domain filter (NOT a separate $match stage):

  ```
  $vectorSearch { index, path, queryVector, numCandidates: 50, limit: 5, filter: {domain} }
  → $limit 1
  → $project { task, domain, confidence, run_count, optimal_actions, step_traces, score }
  ```

  The domain filter is inside $vectorSearch so Atlas pre-filters before ranking.
  Previous approach (separate $match after $vectorSearch) could miss valid matches
  if all top-5 vector results were wrong-domain.

  **Atlas index requirement:** task_vector_index must include the domain filter field:
  ```json
  {
    "fields": [
      {"type": "vector", "path": "task_embedding", "numDimensions": 1536, "similarity": "cosine"},
      {"type": "filter", "path": "domain"}
    ]
  }
  ```

  ### Input validation

  All public functions validate inputs at entry:
  - Empty/whitespace task or domain → ValueError
  - Empty action or target on StepData → ValueError
  - Empty trace list → ValueError

  ### Unit tests (tests/test_db.py)

  26 tests, no live MongoDB needed. Uses mock_collection + mock_embed fixtures
  (set up in tests/conftest.py, which also handles dummy env vars before import).

  | Test class | Coverage |
  |---|---|
  | TestActionSignature | with/without value, empty string, None |
  | TestRecomputeOptimalPath | confidence formula, 0.99 cap, threshold filtering, sorting, zero runs, empty steps |
  | TestStoreStep | upsert structure, $inc paths, success vs failure counters, embed called |
  | TestStoreTrace | successful/failed trace, run_count increments, embed called once, recompute called |
  | TestQueryContext | pipeline structure (domain in $vectorSearch, no $match), result unpacking, missing field defaults |
  | TestInputValidation | empty/whitespace task, domain, step fields, empty trace |

  Run: `python -m pytest tests/test_db.py -v`

  ---
Nathan — Laminar + Trace Processing Pipeline

  Owns: How raw agent runs become useful data in MongoDB.

  - Laminar instrumentation — Laminar.initialize(), custom span attributes
  - Pipeline: Laminar traces → parse steps → determine success/failure per step → call Person 2's store_trace()
  - Trace comparison logic — across N runs, which steps are common to successful runs vs failed runs?
  - Convergence logic — when has a task node "converged" enough to be confident? (run_count threshold, success rate)
  - Analytics / observability — cache hit rate, step reduction metrics, confidence over time