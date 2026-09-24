# AI assistant routing and action memory

Kuma uses one agent with database, application, automation, and explanation modes.
The implementation lives in `baserow_enterprise.assistant`. Modes control tool
discovery and schema size; the domain services still enforce the acting user's
permissions and workspace boundaries.

## Tool discovery

`AssistantToolRegistry` first filters tool groups through `can_use`. The permitted
tools share one catalog and a routing map in `tools/routing.py`. Tools active in
the current mode expose their full schemas. Other permitted tools are deferred
and discoverable through the model's tool search support.

Calling a deferred tool changes the mode. If its arguments already match the
full JSON schema, it follows the normal validated execution path immediately.
Incomplete calls return `changed: false` with instructions to reissue the call
using the full schema, without consuming the tool-error retry budget. Those
pending calls remain visible until reissued, and routing-only results are
excluded from verified action memory. Tool execution is sequential so later calls
see earlier results and mode changes. Dynamic row tools are available in database
mode and are refreshed when their table schema changes.

When adding a tool, register it in its domain's tool functions and ensure the
routing map assigns it an owner. A mode switch never grants permissions or makes
an unavailable tool group discoverable.

## Action memory and completion evidence

Chat history is compacted to user prompts and final answers, retaining at most
20 messages. `action_memory.py` also stores recent mutation outcomes in versioned
message metadata. This ledger retains at most 12 outcomes and 4,000 serialized
characters. Large values are truncated, while request fingerprints use the full
arguments to distinguish similar requests.

The ledger provides prior resource IDs and partial or failed outcomes to the
model. It is bounded context, not an audit log or an idempotency guarantee. Old
chats without this metadata remain readable. Tools must still inspect current
resource state and enforce permissions before acting.

Completion validation uses only live tool results after the latest user prompt.
A prior success, a reused resource, or an explicit no-op cannot by itself justify
claiming a new change. A partial result can support an answer that acknowledges
unfinished work. Output-validation retries stay within the same user turn.

The answer checks are English text heuristics. They catch common unsupported
success claims, printed tool calls, false mode limitations, and unnecessary
handoffs. They do not verify every named resource, interpret all languages, or
prove that every part of a request succeeded. Persisted-state checks and trace
review remain necessary when evaluating task completion.

## Reuse and clarification

Creation tools reconcile exact-name matches within the authorized parent scope.
They return existing resource IDs and report conflicting definitions or requested
settings that remain unapplied. Reuse does not silently overwrite an existing
resource. It also does not prevent duplicates across concurrent agent runs.

Product questions use documentation without requiring example tables or fields to
exist. Inspection requests use read tools. For changes, missing user-owned data
must be looked up before asking for clarification; displaying existing data does
not authorize creating replacement tables or sample records. New build requests
with enough context use reasonable defaults for a useful first version.
Compact table schemas identify omitted fields and direct the agent to request the
full schema before treating a field as missing. Page discovery distinguishes
application IDs from page IDs; `setup_page` populates a page created separately by
`create_pages`.
`ask_user` records a question for the final answer; it does not persist a separate
workflow or introduce a new frontend protocol. The next reply resumes through the
ordinary chat history.

## Builder formulas and documentation retrieval

Implicit formulas inside a collection use its current record. Explicit formulas
can still intentionally access an absolute row or another data source. Builder
updates reject unsupported properties before applying changes, retain existing
formula values when generation fails, and report any separately committed updates
as partial. Buttons navigate through click actions; links store their destination
directly and can use button styling.

Knowledge-base synchronization indexes overlapping passages, including document
titles, instead of embedding whole pages that exceed the embedding model's input
limit. Passage metadata triggers reindexing of legacy or incomplete indexes.
Retrieval combines semantic and lexical matches and limits passages per document.
Answers must cite retrieved sources and distinguish supported information from
documentation gaps; missing evidence does not establish feature availability.
If synthesis returns no valid citation, it reconsiders the same passages once for
supported partial information. This fallback keeps the citation checks and can
still return no evidence.

## Verification

Run the assistant and prompt tests with:

```bash
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/ ../premium/backend/tests/baserow_premium_tests/prompts/test_prompt_assets.py -n=auto -q
```

The routing tests exercise discovery, immediate execution of complete calls,
deferred execution of incomplete calls, and unavailable groups. History and
answer-validation tests cover compaction, eviction, no-ops, failed mutations,
and current-turn evidence. Domain
tool tests verify saved state and reconciliation. For live model runs, use the
[eval platform](../testing/ai-assistant-evals.md) with a disposable database and
record the source revision, model settings, case population, and failures.
Generated eval user identities use UUIDs because the database persists across
scenarios and Faker's per-instance uniqueness cache does not.
Eval harness version 5 preserves version 3's exclusion of required mode-switch
redirects from the tool-error budget. Genuine argument and output-validation
failures still count. It also matches production's sequential tool execution,
records request-limit, model/tool retry exhaustion, and other case errors as
failures without retrying or aborting the suite, and checks
saved Builder navigation and card values across multiple records. Metadata records
the evaluator source hash. Older score totals must be interpreted with their
recorded checks, harness version, and configuration.
