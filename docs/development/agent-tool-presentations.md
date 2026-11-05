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
- `status` is `running`, `done`, `failed` or `stopped`, see `STEP_STATUS` in
  `modules/core/chatRuns/constants.js`. A call is `running` from the moment the
  model makes it, so a change waiting behind another change in the same response
  is `running` too. `stopped` means the reply ended before the call's result: a
  change may already have completed, and the card says so.
- `input` is derived from the arguments before the call runs, such as a requested
  count. It never copies argument values.
- `facts` are confirmed after an authorized success, such as a count and a table
  name. A requested count doesn't prove how many items changed. A batch that
  partly fails is `done` with the count the tool reports.
- `error_code` is set on failed steps: `not_found`, `permission_denied`,
  `invalid_input` or `failed`. For an exception the tool raises, it comes from
  `classify_tool_error` in `baserow/core/tools/errors.py`, which also writes the
  message the model gets. Arguments that fail validation are `invalid_input`.
  `not_found` covers missing and inaccessible resources alike. Error messages
  never reach the step.

Calls to tools the reply doesn't offer get no step.

## Web search

The provider runs web search itself, so it has no `AgentToolType`. Its step uses
`web_search` as `tool`, starts when the provider reports the call and gets its
input once the call is complete. Unlike other tools, its `input` keeps the
queries (`queries`) and any page the provider opened (`url`), bounded in count and
length, because the step is the only record of what the Agent sent out. Code the
provider runs to filter results gets no step.

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
