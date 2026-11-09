# Agent tool presentations

Agent replies show each tool call as a card above the reply, live and after reload.
Core's `toolPresentation` registry and its `ChatStepGroup` card render them. The
Agent module registers its database presenters in `modules/agent/plugin.js`.

See [Background chat runs](./background-chat-runs.md) for the streaming lifecycle.

## The step contract

The backend emits `step` events and saves the same steps on the assistant message:

```json
{
    "id": "unique-call-id",
    "tool": "create_rows",
    "status": "done",
    "changes_data": true,
    "input": { "requested_count": 2 },
    "facts": { "count": 2, "table": "Tasks" }
}
```

- `tool` is the tool's name. Frontend presenters are registered under it. They
  only describe calls and never select what runs or what is allowed.
- `status` is `running`, `done`, `failed`, `stopped` or `skipped`, see
  `STEP_STATUS` in `modules/core/chatRuns/constants.js`. A call is `running` from
  the moment the model makes it, so a change waiting behind another change in the
  same response is `running` too. `stopped` means the reply ended before the
  call's result: a change may already have completed, and the card says so.
  `skipped` means the call changed nothing and failed nothing; it has no card.
- `input` is derived from the arguments before the call runs, such as a requested
  count. It never copies argument values.
- `facts` are confirmed after an authorized success, such as a count and a table
  name. A requested count doesn't prove how many items changed. A batch that
  partly fails is `done` with the count the tool reports.
- `error_code` is set on failed steps: `not_found`, `permission_denied`,
  `invalid_input`, `invalid_formula`, `conflict` or `failed`. For an exception
  the tool raises, it comes from `classify_tool_error` in
  `baserow/core/tools/errors.py`. Arguments that fail validation are
  `invalid_input`. `not_found` covers missing and inaccessible resources alike.
- `error_message` is the tool error's message, written for people and at most
  1,000 characters. The card shows it instead of the code's generic label.
- `item_errors` lists up to 20 failed items, each with `item`, `code` and
  `message`. On a `done` step they make the call partial: some items changed,
  these didn't. An error's `hint` is advice for the model and is never stored.

When a call fails and the model calls the same tool again, the retry continues
the failed card instead of adding one. A retry that is `skipped` keeps the
failure. A call the run denied is not continued, as other arguments can't fix it.

Calls to tools the reply doesn't offer get no step.

### Input previews

Write tools can add `input.values`, a copy of the arguments they select in
`DatabaseAgentToolType.step_input_arguments`. Core's `tool_input_preview` shortens
strings to 1,000 characters and sets `input.truncated` when it does. It leaves the
preview out when the stored JSON would exceed 16 KiB, because a partial copy could
misstate the request. The card shows it as escaped JSON, collapsed by default. It
describes the request, not what changed, and is stored with the step.

Row tools don't select their rows: values can include passwords, which the row
itself only stores hashed.

## Web search

The provider runs web search itself, so it has no `AgentToolType`. Its step uses
`web_search` as `tool`, starts when the provider reports the call and gets its
input once the call is complete. Unlike other tools, its `input` keeps the
queries (`queries`) and any page the provider opened (`url`), bounded in count and
length, because the step is the only record of what the Agent sent out. A reply that
was meant to search but couldn't, because the provider refused the tool, gets one
failed step whose `input` is `{"unavailable": true}`.

## Adding a tool

**Backend.** An `AgentToolType` describes its calls with
`get_step_input(arguments)` and `get_step_facts(ctx, arguments, result)`. Both
default to `{}`. A failure in either is logged without values and doesn't change
the tool's result.

**Frontend.** Extend `ToolPresentationType` from
`modules/core/toolPresentationTypes.js` and implement `getLabel(t)`,
`getDescription(t)` and `getActivity(step, t)`. Register it in the
`toolPresentation` namespace from the owning module's plugin. Return
`WORKSPACE_TOOL_GROUP` from `group` only for workspace reads: consecutive reads
share one card, and each change gets its own. Unknown tools, missing translations
and presenter errors fall back to generic labels that keep the step's status.

**Translations.** Put labels in the owning module's English locale file. Use plural
forms such as `"Creating {count} row | Creating {count} rows"`, called with
`t(key, { count }, count)`.

**Coverage.** Add each tool to `tests/cases/agent_tools.json` with valid
arguments, the expected `input` and representative `facts`. Backend tests check
the examples against the tool registry and argument schemas. Frontend tests check
that every tool has a registered presenter with translated titles for each status.
The fixture's `step_error_codes` keeps the backend and frontend codes in sync.
