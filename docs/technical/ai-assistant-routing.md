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

Calling a deferred tool changes the mode and returns a retry instruction without
executing the requested operation. The model must call it again with the full
schema. Tool execution is sequential so later calls see earlier results and mode
changes. Dynamic row tools are available in database mode and are refreshed when
their table schema changes.

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

The prompt directs the agent to use reasonable defaults for a useful first
version. Missing user-owned data must be looked up before asking for clarification.
`ask_user` records a question for the final answer; it does not persist a separate
workflow or introduce a new frontend protocol. The next reply resumes through the
ordinary chat history.

## Verification

Run the assistant and prompt tests with:

```bash
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/ ../premium/backend/tests/baserow_premium_tests/prompts/test_prompt_assets.py -n=auto -q
```

The routing tests exercise discovery, switching without execution, one subsequent
execution, and unavailable groups. History and answer-validation tests cover
compaction, eviction, no-ops, failed mutations, and current-turn evidence. Domain
tool tests verify saved state and reconciliation. For live model runs, use the
[eval platform](../testing/ai-assistant-evals.md) with a disposable database and
record the source revision, model settings, case population, and failures.
Eval harness version 3 excludes required mode-switch redirects from the tool-error
budget. Genuine argument and output-validation failures still count. Older score
totals must be interpreted with their recorded harness version and configuration.
