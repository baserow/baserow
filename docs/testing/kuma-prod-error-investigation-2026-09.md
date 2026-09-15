# Kuma production error investigation — 2026-09-11

Window: 2026-08-14 → 2026-09-11 (28d), PostHog project 7331 (Baserow Production).
Method: 5 parallel evidence sweeps (prod taxonomy, frontend audit, backend audit, deploy
gap, blast radius), each finding verified by 3 adversarial lenses (code / prod / fix).
35 findings survived, 5 were refuted.

## Headline

Prod is not degrading. The trace error rate is a **flat 7.6–13.3% band** with no trend
(last 7 days ≈ 11%). But the healthy baseline was **3.5–5.9%** (2026-06-13..06-16) and it
has never returned: a step change on 2026-06-17 put Kuma on a permanent floor ~3× the
original. Of 23,594 traces, 3,139 errored (13.31%); a further 315 delivered no answer
while recording `$ai_is_error=false`, so the true no-answer rate is **14.64%** and every
dashboard understates failures by ~10% relative.

**0 of 3,141 errored traces produced a partial answer.** Every failure is total.

## The reported incident, identified exactly

The screenshot is trace `9f0a7972-c595-489b-96d9-3c6734a7f81b`,
2026-09-10T20:11:20+02:00, span_name `33108: Create 3 number fiel`, latency 6.63s.
`output_state` verbatim:

```
Tool name conflicts with existing tool: 'create_rows_in_table_1189965'
```

Table `1189965` is the table in the screenshot's URL. The first attempt 91s earlier
(`7dd7e576`, 20:09:49) is *also* broken but differently: `output_state = null`,
`$ai_is_error=false`, latency 0.335s — a silent no-answer.

The console `SyntaxError` in the same screenshot is a **second, independent** bug that
was firing on a different event in the same response. It is not what produced the bubble.

## Ranked causes

| # | Cause | Prod volume (28d) | Fixed? |
|---|---|---|---|
| 1 | `ElementItem.order` AttributeError | 1,247 traces, **35% of all hard errors** | On the branch, unmerged |
| 2 | Off-thread DB connection never health-checked | 560 traces / 14d (34% of errors), one closed incident | No |
| 3 | `load_row_tools` tool-name conflict | 128 traces, 101 users, **rising 8→39/week** | On the branch, unmerged |
| 4 | Silent no-answer traces | 315 traces (1.34%), invisible to alerting | No |
| 5 | Frontend chunk-boundary event drop | 132 traces structurally at risk; 11 excess retries | No |

### 1. `ElementItem.order` — 35% of all errors, 78 days old

`enterprise/backend/.../assistant/tools/builder/types/element.py:1875` declares
`order: str` and `:1915` does `order=str(element.order)`. Migration `0071` (commit
`b70bc968d`, 2026-06-25, "#4706 graph system") renamed `Element.order` →
`compat_order`. There is no `Element.order` and no `__getattr__` fallback, so
`ElementItem.from_orm` raises on the **first element on the page**.

Reproduced empirically: a real `HeadingElement` through `ElementService().get_elements`
raises `'HeadingElement' object has no attribute 'order'` — byte-identical to prod.

Exclusive tool attribution (not inferential): the `list_elements` span appears in 379
errored traces vs 11 successful — 34:1. Shipped broken in **2.3.0**, so every
self-hosted user on a current release has broken builder tooling.

### 2. Off-request-thread DB connections

Kuma opens DB connections on threads Django's request signals never touch, and nothing
health-checks them. One dropped Postgres connection wedges **every subsequent request on
that worker until the process restarts** — which is why a transient blip became
2026-08-28: 437/910 (48%), 08-29: 268/494 (54%), 08-30: 166/688 (24%).

Zero occurrences since 2026-09-01, so **do not count this against the current 15%
figure** — it inflates the 14-day number. The wedging behaviour is still unfixed.

### 3. `load_row_tools` tool-name conflict — the reported failure

`tools/database/tools.py:1205` does `ctx.deps.dynamic_tools.extend(new_tools)` with no
de-duplication. The sequence:

1. `load_row_tools` bakes the *current* field schema into the generated tool signature.
2. `create_fields` adds fields. The registered `create_rows_in_table_<id>` is now stale
   and rejects the new field names.
3. The model correctly diagnoses this and re-calls `load_row_tools`.
4. `extend()` appends a duplicate name; pydantic-ai raises. It is not a `ModelRetry`, so
   it escapes the run and kills the turn — after the 3 fields are already committed.

The model's own reasoning from the reported trace: *"It doesn't accept the new number
fields because they are not recognized?"*

The tool docstring (`tools.py:1250`) actively tells the model **not** to reload — exactly
the wrong advice after a schema change. Order-dependent, hence flaky: `create_fields`
before `load_row_tools` succeeds.

### 4. Silent no-answer traces

315 traces closed with no `answer` and no `$ai_is_error` (229 `output_state=null`, 86
`{"tool_calls":[...]}` with no answer key). p90 latency 44–52s with executed tool calls —
genuine turns that mutated state and returned nothing. Excluded from every error
dashboard by construction.

### 5. Frontend chunk-boundary event drop

`enterprise/web-frontend/.../services/assistant.js:38-51`:

```js
const chunk = xhr.responseText.substring(buffer.length)
buffer = xhr.responseText                    // advances past the partial tail
chunk.split('\n\n').forEach((line) => { JSON.parse(line) /* throws; event lost */ })
```

`buffer` is a high-water mark, not a buffer. The incomplete trailing fragment is parsed,
throws, and is never reunited with its continuation. Written in `b776ef397`
(2025-09-11, "Introduce AI Assistant 1/3") and **never modified in one year**.

`json.dumps` escapes newlines, so a raw `\n\n` never appears inside a payload — the
delimiter is unambiguous and the fix is purely tail retention.

**Blast radius is smaller than payload size suggests.** The answer is emitted twice —
`AiMessageChunk` (`assistant.py:445`) and the persisted `AiMessage` (`:762`), which
inherits `type: "ai/message"`. Both carry the complete answer, so one boundary destroys
one copy and the survivor still renders. Losing *both* needs payload > bytes-per-tick.

- Sizes (20,077 successful traces): p50 910 B, p90 3,215, p99 11,796, max 53,030.
- 37.9% exceed one 1,400 B TCP segment; **0.657% (132) exceed 16,384 B**, the TLS-record
  / HTTP/2 DATA-frame ceiling above which one event *cannot* arrive in one transport unit.
- Retry rate on *successful* traces by answer size is U-shaped and spikes **12.50% above
  16 KB vs a 3.82% floor** (3.3×, ≈5σ, 9 distinct users, 8 days). One user resent an
  identical prompt 5 times at 126/76/28/37/23s gaps after five backend-successful traces.

Honest counter-evidence: the *aggregate* retry signal (1,358 traces) is NOT this bug —
retried traces are smaller than non-retried (p50 535 vs 913 B).

Per-type loss: `ai/started` inert; `thinking`/`reasoning` self-superseding; `navigation`
breaks routing and fails onboarding; `chat/title` permanent; `ai/cancelled` wedges Stop;
second `ai/message` silently kills feedback (message keeps its temp uuid,
`can_submit_feedback` stays false).

**Amplifier:** the backend re-sends the entire accumulated reasoning text on every token
delta (`assistant.py:588-600`) — quadratic bytes. ~430 KB streamed at the median trace
for an 877 B answer; multi-MB at p90. This multiplies the boundary count.

## Observability: why none of this was in Sentry

`views.py:282-291` collapses every backend failure into one untyped bubble, logged only
to loguru. The loguru sinks are stderr + OTel (`telemetry.py:79-87`); `sentry_sdk.init`
registers only Django + Celery integrations (`base.py:1657-1672`). **There is no
loguru→Sentry bridge, so 837 user-visible failures per 11 days can produce zero Sentry
issues by construction.** The log line carries no chat/user/workspace/model/tool context.

`AiErrorMessage.code` is never set — which is why `$ai_error_normalized` is 100%
`"Unknown error"`. `RECURSION_LIMIT_EXCEEDED` and `TIMEOUT` are dead enum members.

Failures at `assistant.py:725/733/762/764/774` are *outside* the trace context manager
(opened at `:475`), so they produce no `$ai_trace` error at all. The measured rates are
lower bounds.

Frontend: **zero `$exception` events exist in this project across 180 days.** The
streaming parser's only handler is `console.trace(e)`.

## Deploy picture

- Prod runs a **develop-based build, not 2.3.3**. Proof: pydantic-ai's retry-exhaustion
  wording flips in prod `output_state` on exactly 2026-08-24 (2.28.0 was pinned to
  develop on 08-20). develop→prod lag ≈ 4 days.
- **None of the 4 `kuma-assistant-reliability` commits are in prod.** Verified
  empirically, not just from git: `e66572a38` replaces the system-prompt header
  `Other modes (switch_mode to access)` with `Tools that exist but are not callable in
  this mode`; across 158k prod generations the old header appears every day (24 on
  09-10) and the new one **zero times**.
- **No release since 2.3.3 (2026-07-21, 52 days).** 93 unreleased changelog entries.

## Other confirmed findings

- **Cancellation is entirely inert.** `activeRequests` is created inside the service
  factory (`services/assistant.js:13`) and the store re-invokes `assistant($client)` per
  action (`:293`, `:352`), so `cancelMessage` looks up a *different Map*, always misses,
  and never calls `xhr.abort()`. `_userCancelled` is written once and read nowhere;
  `xhr.onabort` and the store's `if (error.cancelled) return` are dead code. Nothing
  aborts on panel unmount or workspace switch.
- **Errored first messages vanish from the sidebar.** A failed first message leaves
  `chat.title` empty and `list_chats` (`handler.py:104-112`) filters untitled chats out.
  The user's question and any tables the run created become unreachable.
- **No transactional boundary spans a run.** 11 tool sites each commit their own
  `transaction.atomic()`. A mid-run failure leaves half-applied schema changes. On client
  disconnect the current tool still commits, and nothing is logged (`GeneratorExit` is a
  `BaseException`, so both catch layers miss it).
- **A 401 on the streaming endpoint crashes the auth-refresh interceptor.** The custom
  adapter rejects with an error carrying no `config`, so `clientAuthRefresh.js:41-48`
  throws `TypeError: Cannot read properties of undefined (reading 'skipAuthRefresh')`,
  and that TypeError is rendered as the assistant's reply.
- **Latent trapdoor:** `_stream_assistant_message` (`views.py:301-304`) has no `else`, so
  an unmapped type returns `None`, which Django's `make_bytes` encodes as the literal
  `b'None'` with no delimiter — corrupting two events. `TOOL_CALL` and `TOOL` are
  unmapped in `TYPE_SERIALIZER_MAP`. Not reachable today; breaks the next type added.

## Refuted — do not re-derive

- **`onload` has no recovery path** — true that nothing re-parses `responseText`, but
  axios' default `transformResponse` and the absence of any consumer of the resolved
  value make this a non-issue, not a critical finding.
- **`forEach(async ...)` reorders events** — refuted 3/3. `handleStreamingResponse` is
  fully synchronous (Vuex invokes it synchronously and its body is only `commit()` calls),
  so ordering is safe *today*. It is a latent fragility: any `await` added to that handler
  silently reorders full-replace commits.
- **`ClearDBStateMiddleware` drops the primary-DB pin mid-stream** — premise confirmed,
  consequence refuted.
- **A 16 KB deterministic-loss cliff** — the U-shaped retry spike is real, but "deterministic
  loss above 16,384 B" overstates it; loss needs a split *inside* one copy of two.
- **389 traces measured as "backend fine, user saw nothing"** — the count conflates
  several shapes; the defensible figure is the 315 silent no-answer traces.

## Verification plan

No fix should land without these:

- `list_elements` against a page holding **one element of each registered element type**.
  The bug survived 78 days because no test called `from_orm` against a real ORM element.
- Register the same table's row tools **twice in one run**; assert no raise.
- `create_fields` after `load_row_tools`, then `create_rows` — assert the new fields are
  accepted without a reload.
- Frontend: feed the adapter a body split at every byte offset; assert every event is
  delivered exactly once for all splits. This is the test that makes the class of bug
  impossible, not just this instance.
- Instrumentation: assert a run that ends with no `ai/message` sets `$ai_is_error`.
