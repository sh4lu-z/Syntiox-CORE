# WebSocket Event Protocol (v2)

Every event sent over `/ws` passes through `backend/event_bus.py` in strict FIFO order.

`GET /ping` returns `{"status": "SYNTIOX_CORE_HERE", "protocol": 2}` for client feature detection.

## Envelope

All outbound JSON messages share these envelope fields:

```json
{
  "event": "token",
  "agent_id": "main",
  "seq": 1842,
  "ts": 1763093745.512,
  "run_id": "a1b2c3d4e5f6",
  "step": 3,
  "data": "..."
}
```

- `seq`: monotonically increasing integer across the backend process; clients can sort by `seq` and detect dropped frames.
- `ts`: Unix epoch timestamp in seconds (millisecond precision).
- `run_id`: 12-char hex ID assigned per user request that enters the agent loop (`null` outside runs, including slash commands `/history`, `/load`, `/new`).
- `step`: current main-loop step number (or `null` outside a step); for `subagent` / `browser_subagent`, `step_start` and `step_end` carry the sub-agent's own step index while nested events keep the enclosing main-loop step.
- `agent_id`: `"main"`, `"subagent"`, or `"browser_subagent"`.

## Payload Caps and Slow Clients

- Large string fields are capped at `WS_MAX_FIELD_CHARS` (default `200000`, set `0` to disable). When capped, the payload gets `"truncated": true`.
- Each client send has a 5-second timeout in the dispatcher; timed-out or closed sockets are dropped without stalling other clients.
- `final` is routed through the same queue as run events (targeted to the requesting socket) so it cannot arrive before trailing tokens or `run_end`.

## Server-to-Client Events

### Run & Session Lifecycle

- `run_start`: `command` (str), `session_id` (int | null)
- `session`: `session_id` (int | null), `title` (str) — emitted when a new session is created or after `/load` or `/new`
- `step_start`: `step` (int), `max_steps` (int)
- `step_end`: `step` (int), `model` (str | null), `usage` (`{"input_tokens", "output_tokens", "thinking_tokens"}` | null), `finish_reason` (str | null), `duration_ms` (int)
- `run_end`: `outcome` (`"complete"` | `"error"` | `"stopped"` | `"step_limit"`), `content` (str), `duration_ms` (int)
- `final`: `content` (str), `run_id` (str | null) — sent to the requesting socket only

### Streaming Model Output

- `state`: `status` (str) — e.g. `"Thinking"`, `"Planning"`, `"Code Generating"`, `"Responding"`, `"Compacting"`, `"Running <tool>"`, retry states
- `thinking`: `data` (str) — reasoning chunks (Gemini thinking parts + Groq `delta.reasoning`)
- `token`: `data` (str) — assistant text chunks (`main`, `subagent`, `browser_subagent`)
- `tool_call_delta`: `index` (int), `call_id` (str), `name` (str), `args_delta` (str) — live argument fragments on Groq streams (also switches state to `"Code Generating"` for file-writing tools)
- `tool_call_detected`: `index` (int), `call_id` (str), `name` (str), `args` (dict) — emitted on Gemini as soon as a function-call part arrives in the stream (also switching state to `"Code Generating"` for file-writing tools), and on Groq after fragments assemble

### Tool & Terminal Execution

- `tool_call`: `tool` (str), `args` (dict), `call_id` (str) — emitted right before execution
- `tool_output`: `stream` (`"stdout"` | `"stderr"`), `data` (str), `call_id` (str, optional) — live output from `run_terminal_command`, batched at <= 4 KB / 100 ms
- `tool_result`: `tool` (str), `output` (str), `call_id` (str), `ok` (bool), `duration_ms` (int), `truncated` (bool)

### Retries, Compaction & Interactions

- `retry`: `provider` (`"google"` | `"groq"`), `reason` (`"busy"` | `"rate_limit"` | `"failover"`), `attempt` (int), `max` (int), `wait_s` (number)
- `compaction`: `scope` (`"conversation"` | `"loop"`), `evicted` (int), `before_chars` (int), `after_chars` (int), `method` (`"llm"` | `"fallback"`)
- `interaction_required`: `interaction_id` (str), `interaction_type` (`"approval"` | `"question"` | `"mcp_permission"`), `payload` (dict)
- `interaction_resolved`: `interaction_id` (str), `outcome` (`"resolved"` | `"cancelled"` | `"timeout"`)

### Browser, Background Tasks, Timers & Workspace

- `browser_page`: `url` (str), `title` (str), `action` (str)
- `browser_handoff`: `phase` (`"started"` | `"done"` | `"timeout"`), `reason` (str)
- `task_output`: `task_id` (str), `stream` (`"stdout"` | `"stderr"`), `data` (str) — incremental bytes flushed every 2 s and on exit
- `task_end`: `task_id` (str), `code` (int)
- `timer`: `prompt` (str) — emitted when `schedule()` fires
- `workspace_changed`: `workspace` (str | null), `effective_dir` (str), `scratch_dir` (str), `is_scratch` (bool)
- `system`: `message` (str)

## Client-to-Server Messages

- Run command: `{"command": "..."}` (optional `"workspace": "C:\\path"` or `null` applies before running)
- Stop current run: `{"action": "stop"}`
- Respond to interaction:
  - Approval: `{"action": "interaction_response", "interaction_id": "...", "approved": true}`
  - Question: `{"action": "interaction_response", "interaction_id": "...", "response": "...", "selected": [...], "custom_text": "..."}`
  - MCP permission: `{"action": "interaction_response", "interaction_id": "...", "decision": "run" | "allow_always" | "skip"}`
- Query / change workspace: `{"action": "get_workspace"}` or `{"action": "set_workspace", "path": "..."}`
