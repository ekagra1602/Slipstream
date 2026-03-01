# Browser Use v3 Session API Notes (Pocket Copy)

Saved: 2026-03-01
Source context: user-provided OpenAPI JSON for `https://api.browser-use.com/api/v3/openapi.json`

## Base URL

`https://api.browser-use.com/api/v3`

## Auth

Header: `X-Browser-Use-API-Key: <key>`

## Key Endpoints

### Sessions
- `POST /sessions` - create session and/or dispatch task
- `GET /sessions` - list sessions
- `GET /sessions/{session_id}` - get session details/status/output
- `DELETE /sessions/{session_id}` - soft delete session
- `POST /sessions/{session_id}/stop` - stop with strategy

### Session Files
- `GET /sessions/{session_id}/files` - list session workspace files
- `POST /sessions/{session_id}/files/upload` - get presigned upload URLs

### Workspaces (persistent shared file storage)
- `GET /workspaces`
- `POST /workspaces`
- `GET /workspaces/{workspace_id}`
- `PATCH /workspaces/{workspace_id}`
- `DELETE /workspaces/{workspace_id}`
- `GET /workspaces/{workspace_id}/files`
- `DELETE /workspaces/{workspace_id}/files?path=...`
- `GET /workspaces/{workspace_id}/size`
- `POST /workspaces/{workspace_id}/files/upload`

## Session Persistence Behavior

`POST /sessions` request supports:
- `task` (optional)
- `sessionId` (optional)
- `keepAlive` (default false)
- `workspaceId` (optional)

Behavior:
- no `sessionId`, no `task` => create idle session
- no `sessionId`, with `task` => create + run task
- with `sessionId`, with `task` => run task on existing idle session
- with `sessionId`, no `task` => validation error

`keepAlive=false` => auto-stop after task
`keepAlive=true` => session remains `idle` for follow-up tasks

Stop strategies:
- `session` (default): destroy sandbox/session
- `task`: stop current task but keep session alive

## Why This Matters for DomBot

- Use `sessionId` as runtime continuity key (same browser state across follow-up tasks).
- Keep your own permanent IDs in Mongo (`trace_id`, `task_node_id`); do not rely on session ID as long-term memory key.
- Use `workspaceId` for reusable artifacts/files across sessions.
- Better trace quality: multi-stage workflows can be logged under one runtime thread.

## Note

This was described as "hidden" in conversation, but appears to be a publicly documented v3/experimental session API snapshot.
