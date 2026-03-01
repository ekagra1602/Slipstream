# Mongo Integration Handoff

## Scope
This file summarizes the work completed to get DomBot's MongoDB + vector search integration running end-to-end, including fixes applied, validation steps, and current status.

## What Was Implemented

### 1. One-command verification script
- Added: `scripts/run_full_checks.py`
- Purpose: run a full health check in one command:
  - env vars present (`MONGODB_URI`, `OPENAI_API_KEY`)
  - Mongo ping + write/read smoke
  - vector index existence/type/status (`task_vector_index`, `vectorSearch`, `READY`)
  - real `db/db.py` integration (`store_trace`, `store_step`, `query_context`)
  - unit tests (`tests/test_db.py`) with pytest fallback

### 2. Live integration pytest
- Added: `tests/test_db_live.py`
- Added: `pytest.ini` marker `live_db`
- Purpose: opt-in live test against Atlas:
  - checks index readiness
  - writes via real DB layer
  - queries via `$vectorSearch`
  - cleans up inserted test docs

### 3. DB facade alignment
- Updated: `dombot/db.py`
- Before: tools/pipeline used only in-memory mock.
- After: backend facade with auto routing:
  - `DOMBOT_DB_BACKEND=auto|mongo|mock`
  - converts dict step payloads to real `StepData` for Mongo backend
  - preserves mock behavior for local/demo tests
- Added helper: `get_backend_name()`

### 4. Demo summary fixed for Mongo mode
- Updated: `scripts/demo.py`
- Before: summary always read mock in-memory counters (showed `0` in Mongo mode).
- After:
  - detects active backend
  - seeds mock data only in mock mode
  - in Mongo mode, prints summary from `dombot.task_nodes` (run_count/confidence/optimal action count)

### 5. Mongo-safe `_step_counts` keys
- Updated: `db/db.py`
- Bug fixed: `WriteError` on update path when action signature contained `.`/`$` (e.g., done text).
- Fix:
  - store `_step_counts` under Mongo-safe keys
  - save original signature in `signature` field
  - reconstruct readable signature for `step_traces`/`optimal_actions`

### 6. Mongo smoke utility
- Added: `scripts/check_mongo_write.py`
- Purpose: verify write/read path quickly via `mongosh` + `.env` loading.

## Atlas / Index Setup Completed
- Confirmed database: `dombot`
- Confirmed collection: `task_nodes`
- Vector index created as:
  - name: `task_vector_index`
  - type: `vectorSearch`
  - definition:
    - vector field `task_embedding` (`1536`, `cosine`)
    - filter field `domain`
- Confirmed status: `READY`

## Key Issues Encountered and Resolved

1. URI formatting / shell interpolation issues
- Incorrect URI slashes and special-char password (`$`) handling.
- Resolved with correct URI format and URL encoding (`%24`) + proper quoting.

2. Wrong DB selected (`dombot’` with curly quote)
- Caused confusion and empty index results.
- Resolved by switching to exact `dombot`.

3. Wrong index type initially (`search` + `knnVector`)
- Not aligned with `$vectorSearch` path used in code.
- Resolved by recreating as `type: "vectorSearch"`.

4. Live pytest using localhost URI
- `tests/conftest.py` defaulted mock URI to localhost.
- Resolved in `tests/test_db_live.py` with `.env` override and localhost guard.

5. Demo crash due Mongo update path (`..attempts`)
- Resolved with Mongo-safe key encoding in `db/db.py`.

6. Demo summary showing zero counts in Mongo mode
- Resolved by reading real Mongo summary in `scripts/demo.py`.

## Current Status
- `scripts/run_full_checks.py`: PASS
- `tests/test_db.py` (26 mocked unit tests): PASS
- `scripts/demo.py`: runs with Mongo backend and persists trace updates
- Verified Mongo task node updates:
  - `run_count` incrementing
  - `confidence` updating
  - `optimal_actions` populated

## Important Notes
- `tests/test_db.py` are mocked unit tests (not live DB).
- `tests/test_db_live.py` is the live integration test.
- Browser judge output may fail for answer quality while DB ingestion still succeeds.

## Commands You Can Reuse

### Full checks
```bash
python scripts/run_full_checks.py
```

### Live pytest only
```bash
DOMBOT_RUN_LIVE_DB_TESTS=1 python -m pytest tests/test_db_live.py -v
```

### Unit tests only
```bash
python -m pytest tests/test_db.py -v
```

### Demo with real Mongo backend
```bash
export DOMBOT_DB_BACKEND=mongo
python scripts/demo.py
```

### Quick Mongo inspect
```javascript
use dombot
db.task_nodes.find({}, {task:1, domain:1, run_count:1, confidence:1, optimal_actions:1}).sort({_id:-1}).limit(5)
```

## Files Added/Updated
- Added: `scripts/run_full_checks.py`
- Added: `tests/test_db_live.py`
- Added: `pytest.ini`
- Added: `scripts/check_mongo_write.py`
- Updated: `dombot/db.py`
- Updated: `db/db.py`
- Updated: `scripts/demo.py`
- Updated: `README.md`

