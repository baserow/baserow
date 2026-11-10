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
    "input": {
        "requested_count": 2,
        "values": {
            "table": "Tasks",
            "rows": [{ "Name": "Acme" }, { "Name": "Beta" }]
        }
    },
    "facts": { "count": 2 }
}
```

- `tool` is the tool's name. Frontend presenters are registered under it. They
  only describe calls and never select what runs or what is allowed.
- `status` is `running`, `waiting`, `done`, `failed`, `rejected`, `stopped` or
  `skipped`, see `STEP_STATUS` in `modules/core/chatRuns/constants.js`. Calls
  held for approval are `waiting` from their call event, including changes that
  follow a held call in the same response. Other valid calls are `running`
  until their result arrives. `rejected` means the owner denied the call, so it
  did not run. A held call the reply ends without resuming is `rejected` if the
  owner rejected it, `stopped` if they approved it, since the resume may have run
  it, and `failed` if undecided. Copies end held calls the same way, as approvals
  aren't copied; a copy of a reply that still waited marks approved calls `failed`
  too. `stopped` means the reply ended before the call's result: a change may
  already have completed, and the card says so. `skipped` means the call changed nothing and failed nothing; it has
  no card. A held call is never `skipped`, as the owner already saw it. A held
  call gets its readable request when it is held, so the owner decides on
  names, not IDs.
- `input` is what the call asked for. `requested_count` is known when the call
  starts. `values`, the request with names instead of IDs, follows while it
  runs, before the tool changes anything; see
  [Readable requests](#readable-requests).
- `facts` are confirmed after an authorized success: a count, and the names of
  created or read tables. A requested count doesn't prove how many items
  changed. A batch that partly fails is `done` with the count the tool reports.
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

Every call has its own step, so a retry after a failure is a new step.

Calls to tools the reply doesn't offer get no step.

### Readable requests

`AgentToolType.get_step_preview(ctx, arguments)` names a database tool's request
as the Agent identity, before the tool runs. The tool sends it to its running
step as a `ToolCallInputEvent`, so `input.values` stays on running, stopped and
failed steps too.

- What the identity can't name keeps its ID, such as `{"field_id": 4}` or
  `{"row_id": 12}`. The tool, not the preview, decides whether the call
  succeeds; a preview that can't be built is left out.
- Only values of known, readable fields are shown; everything else, such as a
  password or a misspelled field, is masked as `"••••"`.
- Every list keeps 10 items and every object 10 keys, at any depth;
  `requested_count` keeps the requested number.
- Strings keep 1,000 characters.
- Over 16 KiB of JSON, trailing items are left out until it fits; when none
  fits, the list is left out, never shown empty.
- `input.truncated` marks any of these cuts; the card says the preview is
  shortened.
- Each ID is resolved on its own: two fields named "Name" stay two entries.
- Rows are named by their primary field value, or `unnamed row <id>`, when the
  identity may list them.
- Field IDs in views and filters become names when the identity may list the
  table's fields; others stay as written.
- An integer `linked_table` in `create_fields` the identity can't see stays as
  written.
- Reads of one table name only the table, for the title; clients never show a
  read's input.

The card shows `values` as indented JSON, collapsed by default.

## Web search

The provider runs web search itself, so it has no `AgentToolType`. Its step uses
`web_search` as `tool`, starts when the provider reports the call and gets its
input once the call is complete. Unlike other tools, its `input` keeps the
queries (`queries`) and any page the provider opened (`url`), bounded in count and
length, because the step is the only record of what the Agent sent out. A reply that
was meant to search but couldn't, because the provider refused the tool, gets one
failed step whose `input` is `{"unavailable": true}`. A search is never held for
approval, even next to a held call. A resumed reply offers search only if its
paused run did, so a provider that refused it isn't asked again.

## Adding a tool

**Backend.** An `AgentToolType` describes its calls with
`get_step_input(arguments)`, `get_step_preview(ctx, arguments)` and
`get_step_facts(ctx, arguments, result)`. `get_step_input` and `get_step_facts`
default to `{}`; a failure in either is logged without values and doesn't change
the tool's result. `get_step_preview` defaults to `None`; build it with the helpers
in `contrib/agent/previews.py`. When it raises, the step has no `values` and the call still runs.

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
arguments, the expected `input`, the `preview` a call on the test table produces,
and representative `facts`. Backend tests check
the examples against the tool registry and argument schemas. Frontend tests check
that every tool has a registered presenter with translated titles for each status.
The fixture's `step_error_codes` keeps the backend and frontend codes in sync.
