# Background chat runs

The shared backend engine is `baserow.core.chat_runs`; the frontend follower is
in the core module under `chatRuns`. Both work without enterprise installed.
Kuma supplies an adapter. See [ADR 010](../decisions/010-background-ai-chat-runs.md)
for the architecture and durability trade-offs.

## Backend adapters

Register a `ChatRunType` in `chat_run_type_registry` during app startup. It owns:

- `can_read`, `can_cancel` and `can_follow_chat`: independent access checks for
  output, Stop and conversation discovery.
- `execute(run, journal)`: execute once, emitting cumulative text with
  `journal.emit_text(text)` and other JSON events with `journal.emit(kind, data)`.
  Observe `journal.stop_requested` and drain active tools before returning a
  `ChatRunOutcome`. Core provides `ToolExecutor` and `ShieldedToolset` for
  pydantic-ai tools that must drain before Stop completes.
- `persist_outcome`: save the answer and conversation history. It runs in the
  transaction that ends the locked run. Return the serialized saved message;
  core saves that payload as the durable run outcome.
- `serialize_outcome`: return the saved result for recovery. The default uses
  that durable payload. An adapter with mutable message metadata can resolve its
  saved message by the stored ID, so feedback and titles stay current.
- `on_run_lost(run, events)`: save an interrupted turn. `events` is a complete,
  retained Redis prefix or `None`, obtained before the finalization transaction.
  Missing output cannot establish that no tools changed anything.
- `on_run_not_started`: save the outcome of work which provably never started.
- `ensure_interruption_warning`: preserve a missing-result warning in durable
  conversation state before pruning run metadata. Return `False` to retain the
  run when that cannot be done safely. Reconstruct any missing prior-turn
  warnings before the next model call.

Create the human message and call `ChatRunHandler.start_run` in one transaction.
Celery enqueue runs after commit. Only a successful conditional claim executes
the model. The run engine does not restart execution after a broker failure,
refresh, worker loss or incomplete replay. Product-level provider-request and
validation retries within a live run are separate from run recovery.

Use `ChatRunService` for permission-aware reads and cancellation. The core API
provides `GET /api/chat-runs/<id>/` for durable status/outcome and
`POST /api/chat-runs/<id>/cancel/` for Stop. Read and cancel checks are separate.
Read status from the primary; Redis completion alone is not authoritative.

## HTTP adapters

`follow_run` replays and waits with `XREAD BLOCK`, then periodically rechecks
permissions and durable status. It yields ordered events with generation-bearing
cursors and a `replayed` flag. Suppress navigation and other live-only effects
for replay, reconnect catch-up and reset baselines. A terminal database outcome
replaces temporary output even when Redis completion is missing.

Register a streaming path with `register_stream_path` and return an async
`StreamingHttpResponse` from the existing authenticated Django view. The ASGI
router applies Django middleware during preparation, closes its database
connections, and follows asynchronously outside the ordinary HTTP limiter. Long
responses have a separate admission limit and Redis read pool. Always validate
authentication, permissions and resume parameters before returning HTTP 200.
Initial request bodies are limited to 2 MiB and 15 seconds, independently of the
stream lifetime, so incomplete anonymous requests cannot reserve slots indefinitely.
Disconnect closes only the follower.

Kuma preserves `POST /assistant/chat/<uuid>/messages/`, HTTP 200 and raw cumulative
JSON records separated by `\n\n`. It adds `_run` metadata to records and exposes
`X-Chat-Run-ID` through CORS. A resume-only POST carries `run_id`, optional
`cursor` and `tab_id`; it cannot contain a prompt or UI context. GET remains JSON
history with additive active/latest run metadata. Heartbeats are blank record
separators, not SSE comments.

## Output bounds and recovery

Redis keys use the stable `baserow:chat-runs:v1` namespace, independent of the
Django cache version. Streams use Redis 6.2-compatible commands without consumer
groups. Each follower receives every event.

Buffers retain their whole prefix and are bounded to 8 MiB or 10,000 events.
The journal coalesces output every 250 ms and bounds pending events to 1 MiB or
1,024 events, including callbacks from tool threads. Active buffers expire after
one hour, longer than the 900-second run deadline and 1,020-second task limit;
available finished replay expires after 24 hours. Hitting a bound disables replay instead
of silently trimming a needed prefix. Generation changes, missing prefixes and
invalid cursors are explicit recovery conditions.

Output failure never cancels a healthy claimed worker. The adapter retains its
computed answer in memory and saves it only at termination. Lease renewal and
Stop do not wait for Redis publication. PostgreSQL holds no token-event table or
periodic output snapshots. A combined worker and replay loss can lose all partial
text; committed tool changes remain.

The default per-process limits are 100 HTTP followers, 128 Redis read connections
and a separate 16-connection writer pool. The core frontend makes at most three
automatic stream attachment attempts and checks durable status every five
seconds. Focus/reopen can trigger another bounded attachment attempt. Lifecycle
websocket messages carry identity/status only and are never an output transport.

The browser retains up to 20 finished followers in addition to active runs.
An adapter's `shouldRetainFollower` hook can retain a pending product handoff,
such as Kuma onboarding, until the product consumes it. Logout closes followers
and prevents their late responses from applying product effects.

## Verification

Shared engine tests live in `backend/tests/baserow/core/chat_runs`, and shared
frontend tests in `web-frontend/test/unit/core/chatRuns`. Kuma has separate
adapter and browser tests. For the opt-in Redis integration tests, point
`BASEROW_TEST_CHAT_RUN_REDIS_URL` at an isolated supported Redis server. They use
unique keys and remove them individually, including a 100-follower capacity and
disconnect check. Never point fault-injection tests at a shared deployment.
