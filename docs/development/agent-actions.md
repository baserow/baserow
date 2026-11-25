# Agent actions

An agent's **Actions** section holds tools its builder configures: a named tool,
the inputs the model fills in, and an existing service whose fields use those
inputs. The action types are the actions an automation offers: send email, HTTP
request, Slack message, AI prompt, start workflow, the Local Baserow row actions
(create, update and delete a row, get a row, list rows, aggregate rows) and, in the enterprise edition, semantic search. This page is the
contract the shared code keeps, and what the next action type has to add.

## What owns what

One `AgentAction` per configured action. It belongs to the agent and owns one
`Service`. The action's type is named after its service's type, unless types
share a service type: Create a row and Update a row both use the upsert service,
like the automation nodes of the same names, so `AgentAction.type` keeps the name.
There is no polymorphic action model, and readiness is derived, never stored.

| Owner                               | Responsibility                                                                                                          |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `AgentAction`                       | Name the model calls, instructions, declared inputs, enabled and Ask first.                                             |
| Service and integration             | Configuration, formulas, validation, credentials and delivery.                                                          |
| `AgentActionType` (`action_tools/`) | Opts a service type in. Supplies the starter of a new action and whether a call changes data. Changes the request people read and what the model reads back only where the defaults don't suit. |
| `BoundActionTool`                   | The tool of one reply: schema, argument validation, preview, approval and dispatch.                                     |
| Presenter (`toolPresentationTypes`) | Labels and order of the service's fields, for the step card and the configuration errors.                               |

## Whose permissions an action uses

**An action on Baserow data acts as the agent's Run as identity, never through
an integration.** This applies to every action whose service reads or changes
Baserow data, the ones built on a Local Baserow service: the row actions and
semantic search. Its editor offers no integration to pick, and the service
never keeps one. Permissions then live on one subject, the identity, instead of
being spread over integrations that different people authorized, and the agent's
workspace tools, triggers and actions all read and write as the same identity.

- Without an active identity the action isn't offered to the model, and its table
  field links to Workspace access.
- Its table must be one the identity can read in the agent's workspace. The table
  field only offers those.
- Everyone who chats with the agent reaches what the identity can read.

An action that calls another service keeps its integration, like Send email with
its SMTP integration, Slack message with its bot and AI prompt with its AI
integration: it needs that connection, not an identity, and works with or without
workspace access.

In code, the type of an action on Baserow data sets `acts_as_run_identity = True`.
The row actions extend `LocalBaserowAgentActionType`, which also checks the table
for all of an agent's actions in one permission check.
Create, update and import then drop any `integration_id`, the agent doesn't accept
an integration for it, and a call dispatches with the identity as its actor,
refreshed for each call. A call
held while the agent acted as one identity is denied once it acts as another.

## Defaults and locked types

A new action starts enabled. Ask first follows its type's `changes_data`: on for
a type that acts, outside Baserow, on values the model chose, like Send email;
off for a type that only reads, like semantic search. Tools that change data and
MCP tools start with Ask first on too. `changes_data` also decides, like for
built-in tools, whether a call waits behind an earlier held call.

Every registered type is offered, also when the workspace's license or the
instance can't run it. The model never gets such an action, and its builder may
only rename it, switch it or delete it, so it's ready again once the type can be
used. The editor shows the type's upgrade modal when a license would unlock it.

## Inputs and formulas

`AgentAction.inputs` is a JSON list of `{id, name, type, description, required}`.
Types are Text, Email, Number and Boolean.

- The model's schema uses input **names**. Formulas use input **IDs**, as literal
  `get('tool_input.<id>')` paths, so a rename keeps every binding and a deleted
  input is detected without resolving the formula.
- One Pydantic model generates the schema and validates the arguments: strict
  scalars, finite numbers, no unknown argument. A whole number stays an integer.
- Formulas may only read the action's own inputs. Every runtime function is
  allowed.
- A Local Baserow service resolves its filter values and its search query only
  while a call is sent. A call is sent with its arguments, so these can read the
  inputs too. They aren't part of the resolved values, so the request people read
  lists the call's inputs instead (`LocalBaserowAgentActionType.get_preview`). A
  type says so with `filters_read_inputs`, and the editor then offers the inputs
  in filter values. Semantic search doesn't: it only accepts fixed filter values.

## Names

The name is what the model calls, so it must be unique among the agent's actions,
can't be a built-in tool's name, and can't start with `mcp<number>_`, which is
where the tools of connected apps live. A built-in tool added later must not take
a name actions may already have: rename it, or migrate the actions.

## Readiness

Only enabled actions without configuration errors are offered.
`AgentActionType.get_configuration_errors` combines the service's static checks,
the integration's ownership, type and liveness, or the run identity for an action
on Baserow data, and the input references of the formulas. It never resolves a
formula, contacts the integration or sends anything. A broken action is left out;
it never fails the reply. An agent's actions are checked together, with the
identity resolved once (`get_configuration_errors_by_action`).

## One call

1. The arguments are validated. Invalid ones go back to the model and never wait
   for approval.
2. `prepare` resolves the service's formulas **once**. The result is the call's
   resolved values.
3. The readable request, built from those values, is shown on the step. Each
   action type decides how to limit what a call may send and what its preview
   shows. Send email limits neither yet; HTTP request limits the request (below).
4. With Ask first, the call is held. The resolved values the type keeps
   (`get_held_values`, all of them by default) are kept in the paused run
   (`ApprovalRequired(metadata=...)`) with the action's approval key. An approved
   call rebuilds what it sends from them (`complete_held_values`).
5. `dispatch` sends the resolved values through `ServiceHandler.dispatch_service`,
   as the run identity for an action on Baserow data. The dispatch context carries
   them (`DispatchContext.resolved_values`), so the
   service doesn't resolve its formulas again: what people read is what is sent,
   random values and dates included.
6. The model reads the service's result, cut to `ACTION_MAX_RESULT_CHARACTERS`
   (`fit_result`): the first items of a list whole, the others left out.

An approved call is denied instead of sent when:

- the action is no longer offered: deleted, renamed, disabled or broken;
- its approval key changed: the key digests the action's name, instructions and
  inputs, its exported service and its exported integration, without the
  integration's name and place in the list;
- it came back without its resolved values.

"Always allow" only stops asking first for the action whose call was approved,
while it is unchanged.

Not covered: the instance's own SMTP settings can change between hold and approval.

## HTTP request

- A new action is a POST with a JSON body bound to one `body` input. Its URL is
  empty, which is a configuration error, so it isn't offered until it has one.
  Only what the body type sends is resolved and checked, for builder and
  automation requests too.
- `prepare` refuses, as an input error the model can fix: a URL that isn't a full
  `http(s)` address or is over 8 KB, a request over 64 KB in all, keys included,
  a header with a line break or a character outside Latin-1, and a JSON body that
  isn't valid JSON (`NaN` and numbers too large for a float included). Nothing
  waits for approval or goes out.
- The approver reads a value only when its formula is exactly one input, as the
  model chose it. A value the builder fixed, or one that mixes fixed text with an
  input, is where a key sits: it shows as `••••••••`. The URL always shows where
  it goes, with its user, password, path and query values hidden unless the model
  chose the whole URL. The inputs no shown value is exactly are listed apart
  (`get_preview` adds them), so the approver reads every choice of the model.
- Hidden values aren't kept with a held call (`get_held_values`). An approved
  call resolves them again from its arguments and sends the shown values as kept
  (`complete_held_values`). Values are keyed by row position, as saving rows
  recreates them with new IDs.
- A request carrying a hidden value only goes to the host the builder set: the
  URL is resolved with every input empty and must have the same scheme, host and
  port. Otherwise the model could send a key elsewhere. When the URL has no
  fixed host at all, the action has a `fixed_host` configuration error instead.
- A call only follows a redirect on the same host and port, and never from https
  to http. Moving from http to https on the default ports is followed. Its headers and body would otherwise go where the approver never saw.
  Builder and automation requests follow every redirect, as before
  (`DispatchContext.redirects_stay_on_host`).
- The model reads the status, the content type and the body back. A body longer
  than `ACTION_MAX_RESULT_CHARACTERS` (20,000) comes back as the start of its text
  with `body_truncated`. A refused address or a malformed request is an input error;
  an unreachable API, a timeout and a too large answer are failures
  (`ToolFailedError`) that say what happened.
- Headers, query parameters and form data rows are ordered by ID, so the
  exported service, and the approval key, read the same each time.

## Limits

`BASEROW_AGENT_MAX_ACTIONS_PER_AGENT` caps the actions one agent can have. It is
unset by default. It blocks adding and restoring an action; an imported or
duplicated agent keeps the actions it had.

## Copies and trash

- A duplicate copies the actions, with their integrations if they have one, and
  keeps them enabled.
  An import or a template keeps the configuration but starts every action disabled.
- Input IDs are local to the action, so formulas survive a copy unchanged.
- Trashing an action trashes its service. Restoring it keeps its ID and gives it
  the next free name if another action took its name meanwhile.

## Adding the next action type

1. Subclass `AgentActionType` with the service type's name as `type`, in the
   agent module (`contrib/agent/action_tools/action_types.py`), and register it in
   `agent_action_type_registry`. Set `service_type_name` when the type shares its
   service type with another one. Set `changes_data = False` when a call only
   reads. Extend `LocalBaserowAgentActionType` when the service reads or changes
   Baserow data (see [Whose permissions an action uses](#whose-permissions-an-action-uses)).
   Implement `get_defaults()`: the starter name, instructions, inputs and service
   values. `bound_input` gives an input and the formula that reads it.

    Everything else has a default. Override it only where it doesn't suit:
    - `get_preview_values(service, resolved_values)` shows every resolved value.
      Select the values when a formula can hold a credential, like HTTP request
      does, or to add a fixed setting people should read.
    - `get_configuration_errors` for what the shared checks miss and only an
      agent requires. A setting every host needs, like the channel of a Slack
      message, is checked by the service type's own `get_configuration_errors`.
    - `get_formulas` when the service type queries its formulas for each service,
      which checking all of an agent's actions would repeat.
    - `get_tool_result` when cutting the result to `ACTION_MAX_RESULT_CHARACTERS`
      from the end loses what matters most.

2. Make sure the service's resolved values survive JSON, as they wait in the paused
   run, and that their keys are the same after a save: the upsert service names a
   mapped value after its field, not after the mapping's id.
3. Reuse the service's form as it is. An action on Baserow data gets the tables
   its identity can read from `GET /api/agent/{id}/action-types/`, which the
   service type lists with `get_form_choices`
   (`LocalBaserowSubjectReadableTablesMixin`), like a trigger. Add a host
   capability to the form only where the agent editor needs one.
4. Check that the exported service is stable: a list of child rows without an
   order changes the approval key between two reads.
5. Optionally register an `ActionToolPresentationType` under the same type name,
   with the label of each field in reading order, and the activity texts. Without
   one the step is titled with the service type's name, and a field
   `GenericActionToolPresentationType` has no label for shows as the service names
   it.

The CRUD API, permissions, audit, realtime events, typed input editor, argument
validation, approvals and the cap on an agent's actions are shared and need nothing.

## Not hosted

`test_every_automation_node_type_is_hosted_or_left_out_on_purpose` fails when an
automation node type is neither an action or trigger type of agents nor listed
there as left out. Router, goto, iterator, wait, response and the manual trigger
only mean something inside a workflow. Create rows and update rows, the CSV and
XLS readers, run code and the fields updated trigger aren't hosted yet.
