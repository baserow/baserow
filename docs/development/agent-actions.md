# Agent actions

An agent's **Actions** section holds tools its builder configures: a named tool,
the inputs the model fills in, and an existing integration service whose fields use
those inputs. Send email and HTTP request are the action types so far. This page
is the contract the shared code keeps, and what the next action type has to add.

## What owns what

One `AgentAction` per configured action. It belongs to the agent and owns one
`Service`. The action's type is its service's type, so there is no polymorphic
action model, and readiness is derived, never stored.

| Owner                               | Responsibility                                                                            |
| ----------------------------------- | ----------------------------------------------------------------------------------------- |
| `AgentAction`                       | Name the model calls, instructions, declared inputs, enabled and Ask first.               |
| Service and integration             | Configuration, formulas, validation, credentials and delivery.                            |
| `AgentActionType` (`action_tools/`) | Opts a service type in. Supplies the starter of a new action and the request people read. |
| `BoundActionTool`                   | The tool of one reply: schema, argument validation, preview, approval and dispatch.       |
| Presenter (`toolPresentationTypes`) | Labels and order of the service's fields, for the step card and the configuration errors. |

Actions don't act as the agent's identity. They are offered with or without
workspace access and act through their own service.

A new action starts enabled, with Ask first on: it acts outside Baserow, on
values the model chose. Tools that change data and MCP tools start the same way.

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

## Names

The name is what the model calls, so it must be unique among the agent's actions,
can't be a built-in tool's name, and can't start with `mcp<number>_`, which is
where the tools of connected apps live. A built-in tool added later must not take
a name actions may already have: rename it, or migrate the actions.

## Readiness

Only enabled actions without configuration errors are offered.
`AgentActionType.get_configuration_errors` combines the service's static checks,
the integration's ownership, type and liveness, and the input references of the
formulas. It never resolves a formula, contacts the integration or sends anything.
A broken action is left out; it never fails the reply.

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
5. `dispatch` sends the resolved values through `ServiceHandler.dispatch_service`.
   The dispatch context carries them (`DispatchContext.resolved_values`), so the
   service doesn't resolve its formulas again: what people read is what is sent,
   random values and dates included.

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
  than 20,000 characters comes back as the start of its text with
  `body_truncated`. A refused address or a malformed request is an input error;
  an unreachable API, a timeout and a too large answer are failures
  (`ToolFailedError`) that say what happened.
- Headers, query parameters and form data rows are ordered by ID, so the
  exported service, and the approval key, read the same each time.

## Limits

`BASEROW_AGENT_MAX_ACTIONS_PER_AGENT` caps the actions one agent can have. It is
unset by default. It blocks adding and restoring an action; an imported or
duplicated agent keeps the actions it had.

## Copies and trash

- A duplicate copies the actions with their integrations and keeps them enabled.
  An import or a template keeps the configuration but starts every action disabled.
- Input IDs are local to the action, so formulas survive a copy unchanged.
- Trashing an action trashes its service. Restoring it keeps its ID and gives it
  the next free name if another action took its name meanwhile.

## Adding the next action type

1. Subclass `AgentActionType` in `contrib/agent/action_tools/action_types.py`
   with the service type's name as `type`, and register it in `apps.py`. Implement:
    - `get_defaults()`: the starter name, instructions, inputs and service values.
    - `get_preview_values(service, resolved_values)`: an explicit allowlist of what
      people read, fixed settings included. Never credentials.

    Decide there how to limit what a call may send and what its preview shows:
    nothing shared limits either.

2. Make sure the service's resolved values survive JSON, as they wait in the paused
   run. Convert them in the type if they don't.
3. Register an `ActionToolPresentationType` under the same type name, with the
   label of each field in reading order, and the activity texts.
4. Reuse the service's form. Add a host capability to it only where the agent
   editor needs one.
5. Check that the exported service is stable: a list of child rows without an
   order changes the approval key between two reads.

The CRUD API, permissions, audit, realtime events, typed input editor, argument
validation, approvals and the cap on an agent's actions are shared and need nothing.

## Planned order

Send email, HTTP request, Slack message, configured Baserow create/update row,
start workflow. Before the Baserow row action, decide whose authority a configured
Local Baserow service acts with.
