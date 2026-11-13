# Agent actions

An agent's **Actions** section holds tools its builder configures: a named tool,
the inputs the model fills in, and an existing integration service whose fields use
those inputs. Send email is the first action type. This page is the contract the
shared code keeps, and what the next action type has to add.

## What owns what

One `AgentAction` per configured action. It belongs to the agent and owns one
`Service`. The action's type is its service's type, so there is no polymorphic
action model, and readiness is derived, never stored.

| Owner                                | Responsibility                                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `AgentAction`                        | Name the model calls, instructions, declared inputs, enabled and Ask first.                     |
| Service and integration              | Configuration, formulas, validation, credentials and delivery.                                  |
| `AgentActionType` (`action_tools/`)  | Opts a service type in. Supplies the starter of a new action and the request people read.       |
| `BoundActionTool`                    | The tool of one reply: schema, argument validation, preview, approval and dispatch.             |
| Presenter (`toolPresentationTypes`)  | Labels and order of the service's fields, for the step card and the configuration errors.      |

Actions don't act as the agent's identity. They are offered with or without
workspace access and act through their own service.

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
3. The readable request, built from those values, is shown on the step.
4. With Ask first, the call is held. The resolved values are kept in the paused
   run (`ApprovalRequired(metadata=...)`) with the action's approval key.
5. `dispatch` sends the resolved values through `ServiceHandler.dispatch_service`.
   The dispatch context carries them (`DispatchContext.resolved_values`), so the
   service doesn't resolve its formulas again: what people read is what is sent,
   random values and dates included.

An approved call is denied instead of sent when:

- the action is no longer offered: deleted, renamed, disabled or broken;
- its approval key changed: the key digests the action's name, instructions and
  inputs, its exported service and its exported integration;
- it came back without its resolved values.

"Always allow" only stops asking first for the action whose call was approved,
while it is unchanged.

Not covered: the instance's own SMTP settings can change between hold and approval.

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
2. Make sure the service's resolved values survive JSON, as they wait in the paused
   run. Convert them in the type if they don't.
3. Register an `ActionToolPresentationType` under the same type name, with the
   label of each field in reading order, and the activity texts.
4. Reuse the service's form. Add a host capability to it only where the agent
   editor needs one.
5. Check that the exported service is stable: a list of child rows without an
   order changes the approval key between two reads.

The CRUD API, permissions, audit, realtime events, typed input editor, argument
validation, approvals and limits are shared and need nothing.

## Planned order

Send email, HTTP request, Slack message, configured Baserow create/update row,
start workflow. Before the Baserow row action, decide whose authority a configured
Local Baserow service acts with.
