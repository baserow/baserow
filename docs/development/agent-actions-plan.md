# Agent actions: email first

Implementation plan based on the product decisions agreed on 2026-11-11.
Implementation and validation notes are included below.

Branch: `6259-agent-send-email-action`, based on
`6259-agent-trigger-guard-rails` at `7ad1a72346`.

## First PR outcome

An agent has its own Actions section. Users can add several email actions, give
each a distinct tool name and usage description, and configure each through the
same SMTP form used by Automation. A new action starts enabled with Ask first
off. Only enabled, correctly configured actions are offered to the model.

The first PR delivers email end to end, including the shared foundations that
later actions need. Subsequent PRs add HTTP, Slack, configured Baserow actions,
then start workflow.

## Agreed product behavior

| Concern            | Behavior                                                                                                                                           |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Availability       | Separate enabled toggle, on when an action is added; incomplete configuration excludes it without changing the toggle.                             |
| Approval           | Separate Ask first setting, off by default.                                                                                                        |
| Workspace access   | Email works with No workspace access, using its SMTP connection.                                                                                   |
| SMTP options       | Same custom SMTP integration and permitted instance SMTP choices as Automation.                                                                    |
| Multiple actions   | Independent configuration, inputs, names, instructions and approval settings, including several email templates.                                   |
| Approval details   | Show the effective resolved operation, including fixed configuration, through the shared tool-details UI. This applies to future action types too. |
| Pending proposals  | Approve sends the call only while its action is unchanged. A template, input or name edit, disable or delete makes the approval deny the call.    |
| Disable/delete     | The action is no longer offered, and its pending calls are denied on approval.                                                                     |
| Replace a proposal | Reject it, change the configuration if needed, and ask the agent to try again.                                                                     |
| Future approvers   | Consider user/team routing as a later extension; implement neither selectors nor routing policy now.                                               |

The connection must remain usable and application authorization still applies.
Turning Ask first off does not approve an already pending request. “Always allow”
only affects the action whose call was approved while it is unchanged, never a
different action reusing its name.

Trigger runs offer actions like other tools: one that asks first holds its call,
and the shared conversation's editors decide it.

## Ownership and extension boundary

Use one `AgentAction` per configured action, owned by the agent and owning one
existing `Service`. Proposed fields: agent, service, name, description, inputs,
enabled and ask_first. The operation type comes from the service; it does not need
a duplicate type column or a polymorphic action model. Readiness is derived.

| Owner                      | Responsibility                                                                                                  |
| -------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Agent action               | Instance identity, name, instructions, declared inputs, enabled and Ask-first settings.                         |
| Shared service/integration | Operation configuration, formulas, service validation, credentials and actual execution.                        |
| Small action-type adapter  | Opt-in service support, starter defaults, static execution options and readable input projection.               |
| Shared Agent runtime       | Tool construction, validated arguments, approval keys, sequencing, cancellation and error handling.             |
| Agent editor host          | Action controls, input editor and context for the existing service form.                                        |

The email adapter supplies defaults, identifies the static sending options and
selects readable email fields. It does not send email or duplicate SMTP validation.
Use normal Baserow type registration for opt-in adapters; register only
`smtp_email` in the first PR. `DispatchTypes.ACTION` is not sufficient eligibility:
it also includes Automation flow-control services.

Use an `action_tools/` backend package for the new feature's handler/service/API
support; `contrib/agent/actions.py` already contains undoable configuration actions.
Follow the trigger feature's ownership, CRUD, permissions, undo/trash and realtime
patterns. New action types should not require their own model or CRUD endpoints.

## Starter email and editable templates

Create the action, backing service, input definitions and bindings atomically.
Seed defaults once. Subsequent edits and imports never regenerate removed inputs
or overwrite customized formulas.

| Service field                        | Starter                                                     |
| ------------------------------------ | ----------------------------------------------------------- |
| To                                   | Required Email input `to_email`: “Recipient email address.” |
| Subject                              | Required Text input `subject`: “Subject of the email.”      |
| Body                                 | Required Text input `body`: “Complete email message body.”  |
| Custom SMTP integration / From email | Editor-selected connection and configured sender.           |
| From name / CC / BCC                 | Empty.                                                      |
| Body format                          | Plain text, matching the shared service default.            |

Subject and body may be empty in the underlying SMTP service. Requiring them in
the starter tool schema expresses the sensible default without changing
Automation's rules. Users can replace them with fixed values or templates and
remove those model inputs.

Start with a unique name such as `send_email`, then `send_email_2`. Suggested
description: “Send an email to the specified recipient. Use this to contact
someone or deliver information by email.” Both name and description are editable.

Figma's introduction template is a supported example: inputs `name` and
`email`, a fixed subject and CC, and a body combining fixed text with the name.
A completely fixed action may have no model inputs.

## Input definitions and formulas

Use an action-owned JSON list with immutable input ID, editable name, type,
description and required flag. No input table is needed.

- Initial types: Text, Email, Number and Boolean. An Email input represents one
  address; the To field can still accept several through Text or existing formulas.
- The model schema uses input names. Formula paths use action-local IDs, such as
  `get('tool_input.<id>')`; schema titles display readable names in formula pills.
- Rename preserves bindings. Deleting an input in the editor removes its formula
  references in the same save, preserving surrounding template text and other
  expressions. An emptied required service field still needs configuration.
  External or stale references remain invalid; recreating the same name does not
  redirect old bindings.
- Required means the agent must supply a value, independently of whether a formula
  references the input. Optional inputs support optional recipients and fallbacks.
  The editor exposes a compact Required/Optional dropdown in each input header,
  defaulting new inputs to Required.
  Configurable default values are deferred to a separate change.
- Existing action/trigger cards and input-variable editors start collapsed; newly
  added items open for configuration. Lists support expand/collapse all. Collapsing
  preserves draft values and keeps enable switches accessible.
- Copying an action with its service preserves its local input IDs and formulas.
- Formulas use declared action inputs and ordinary formula functions. Direct
  trigger-payload access is outside this PR.

One dynamic Pydantic model should generate the tool schema and validate supplied
arguments. `Tool.from_schema()` alone does not validate them; use its supported
`args_validator` hook. Follow the existing Core MCP dynamic-model pattern, use
strict scalars/finite numbers, reject unknown arguments and reuse Django's email
validator. Optional omission stays absent/None, rather than becoming a fabricated
empty string, zero or false. Nested schemas and custom constraints can wait for
an action that needs them.

## Tool identity, discovery and readiness

Keep three concepts separate: immutable action identity, editable callable name,
and stable presentation type. Persist unique provider-compatible names; reject
collisions with other actions and reserved workspace-tool names at save time.
Do not recompute names/suffixes across the catalog on each run.

Compose the runtime catalog from existing workspace tools and bound action tools.
Replace name-only registry lookups at that boundary with a per-generation tool
map. Preserve workspace-tool identity checks. Email uses its configured SMTP
authority; clearing workspace access must not clear actions or their settings.
Application permissions and integration ownership/usability checks still apply;
SMTP does not borrow an editor's workspace identity. Reuse Automation's SMTP
configuration and deployment rules without a separate Agent SMTP policy. This
does not decide the authority of future configured Local Baserow actions.

Derive action readiness before advertising it. Reuse existing formula parsing and
integration ownership/type/liveness checks, with a small shared service
configuration hook for SMTP. The Agent layer checks names, input definitions and
input references; the service checks sending-mode availability, integration host
and required From/To configuration. Expose configuration errors to the editor.

Readiness is local configuration validity, not a successful connection test.
Discovery must not send email, log into SMTP, resolve DNS, dispatch a service or
evaluate formulas with invented arguments. Missing SMTP username/password is valid
for unauthenticated relays. Invalid supplied addresses and delivery failures are
handled at invocation. A broken action does not make the entire agent unusable.

## Preview, approve and execute

Every configured action uses the same sequence:

1. Validate model arguments and resolve the action's formulas without effects.
2. Derive a readable view from the resolved values and emit it to the step.
3. If required, hold the call with the action's approval key and wait.
4. On approval, dispatch the current action through the shared service lifecycle.

Actions without Ask first use the same preview for their activity cards. A preview
failure becomes a normal tool error before waiting or performing an external
effect.

### Approval key

A held call saves its tool's approval key in `AgentToolApproval.tool_key`, the
mechanism MCP tools already use. An action's key is a digest of its ID, name,
instructions, inputs and exported service configuration, integration reference
included. On approval the reply denies the call when the action is no longer
offered, or when its key changed: the approver never sends something other than
what they saw, without storing a private copy of the operation. Rejecting a
request is how to cancel it. Formulas only read the call's own inputs, so
resolving them again on approval gives the previewed values. Instance SMTP
settings aren't part of the key.

### Shared display

Reuse `StepPreview`, `ToolCallInputEvent`, `input.values`/`input.truncated`,
Core's `toolPresentation` registry and `ChatToolInput`, already shared by approval
and activity cards. Use the stable presentation type independently of the custom
callable name. Existing workspace tools retain their current preview path.

A small per-service projection selects/names the effective inputs. Email shows
From, To/CC/BCC, subject, body and body format. Future actions include static
destinations such as Slack channel or Baserow table alongside resolved values.
Raw formula dictionaries are insufficient: HTTP uses generated header keys and
row services use field-mapping IDs.

Mask/exclude credentials explicitly. Export `sensitive_fields` is a different
policy: email content is sensitive for export but must be visible to its approver.
The readable view may be shortened with the existing visible truncation indicator;
execution always sends the full payload.

### Dispatch

Dispatch through `ServiceHandler.dispatch_service` and normal
`ServiceType.dispatch`, preserving integration checks, hooks, transaction behavior
and result transformation. Do not bypass that lifecycle with a direct SMTP sender
or a direct `dispatch_data` call.

Reuse existing sequential side-effect execution and shielded cancellation.
SMTP offers no exactly-once guarantee; do not automatically retry an ambiguous
send or claim cancellation reverses delivery.

## Editor and lifecycle

Register an Actions configuration section. Use Core's `GroupedMenu`, as Agent
triggers already do, with shared service labels/icons/groups and the supported
action types. Automation's node-menu wrapper includes graph/recipe behavior the
Agent does not need.

Host `serviceType.formComponent` with the Agent application, workspace, formula
component and action-input provider. Add one focused input editor using Core
controls. Give the shared SMTP form a small host capability for inline integration
creation/editing. Load Agent-owned integrations into the existing store.

Use existing integration checks on save and
`ServiceHandler.dispatch_service(..., application_id=agent.id)` at execution.

Implementation defaults following repository lifecycle conventions:

- Internal application copies preserve configuration, inputs/bindings, enabled
  and Ask-first settings. Copy integrations first and remap service references.
- External imports/templates preserve configuration and Ask first but start
  actions disabled, following Agent web search's external-copy convention.
- Apply existing secret/content redaction. Imported SMTP configuration may be
  incomplete; show that and do not silently reseed defaults.
- Never retain an unmapped integration ID from another application.
- Keep existing trigger-copy behavior and do not copy pending approvals.

This work supports existing application operations; it does not add an individual
action duplication feature or a new action-template system.

## First PR work areas and validation

| Work area             | Main locations                                                                 | Acceptance evidence                                                                                   |
| --------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Action lifecycle      | Agent models, `action_tools/`, API, permissions, audit/trash, websocket events | Multiple independent actions; defaults; edits; permissions; missing configuration.                    |
| Service support       | Shared services/integrations and the SMTP type                                 | Both SMTP modes, read-only readiness, integration ownership.                                          |
| Runtime               | Agent request/responder, approval resume and input provider                    | Strict input validation; approvals denied after edits/rename/disable/delete; no secret exposure.      |
| Presentation/editor   | Agent configuration, shared tool presentation, SMTP form                       | Dedicated section, shared picker/form, typed inputs, previews in activity and approval cards.         |
| Application lifecycle | Agent application type plus shared integration/service import/export           | Copy/remap/redaction/undo/snapshot behavior; pending approvals remain only in the original.           |

Add one migration for the new action model. Approvals reuse `tool_key`, so they
need no new tables.

Targeted regressions must cover:

- New actions enabled with Ask first off; invalid actions excluded and recover
  after configuration fixes; disabled ones stay disabled.
- Three email templates with distinct names and inputs; renaming/deleting one
  never changes another's name or permissions.
- Input rename/delete, fixed templates, omitted/invalid arguments and formula
  references; strict Email/Number/Boolean behavior.
- Approved calls are denied once their action is renamed, edited, disabled or
  deleted, and sent unchanged otherwise.
- Old-name reuse; “Always allow” only targets the unchanged approved action;
  concurrent decisions do not schedule duplicate execution.
- Unavailable/foreign integrations and application access changes; SMTP with no
  workspace identity; changing workspace access leaves action settings intact.
- Both manual and trigger runs; current workspace-tool approval behavior.
- Generic resolved-input presentation with a lightweight test-only second shape,
  redaction/truncation, and an unchanged full execution payload.
- Export/import/duplicate/snapshot/undo/realtime behavior.

Run targeted backend/frontend suites and changed-file lint, then manually verify
the Figma flow and actual delivery against the local test SMTP backend. Dependency
probes performed during planning are not application tests.

## Agreed follow-up PR order

| PR  | Action                               | Incremental value                                                                                                          |
| --- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| 1   | Send email                           | Outreach, replies, digests and reusable templates; establishes the shared foundation.                                      |
| 2   | HTTP request                         | External CRM/ticket APIs, custom webhooks and the broadest integration reach.                                              |
| 3   | Slack message                        | Team notifications, escalation and handoff using an existing service.                                                      |
| 4   | Configured Baserow create/update row | Named, constrained operations with fixed tables/field mappings; basic row CRUD already exists through workspace tools.     |
| 5   | Start workflow                       | Let the model select deterministic multi-step procedures; the current service does not accept arbitrary runtime arguments. |

Before PR 4, resolve configured Local Baserow authority and how its tools differ
from workspace tools. Parameterized workflow invocation is separate from merely
exposing the current start-workflow service. Provider-specific email/calendar/
ticket actions can follow as their integrations land.

Defer approver routing, direct trigger-data formulas, nested input-schema editing,
Automation flow-control nodes, agent orchestration, generic versioning and
prototype-only integrations. Each future action must satisfy the approval-key
and readable-input contract before being offered.

## Design and implementation evidence

Inspected Figma desktop frames
[38 · Action picker](https://www.figma.com/design/Rs3tQxWIAAI8mYZO2Rmre7/AI-agent-builder?node-id=426-135844&m=dev)
and
[39 · Send an email](https://www.figma.com/design/Rs3tQxWIAAI8mYZO2Rmre7/AI-agent-builder?node-id=426-136356&m=dev).
The desktop document reported unsynchronized changes; these are the locally
visible designs, not a claim of a freshly synchronized remote file.

Relevant code: `contrib/agent/triggers/`, `contrib/agent/replies.py`,
`contrib/agent/registries.py`, `core/services/{handler,registries}.py`,
`contrib/integrations/core/service_types.py`, `AgentTriggerPicker.vue`,
`CoreSMTPEmailServiceForm.vue`, and
[Agent tool presentations](./agent-tool-presentations.md).
The `agent-builder` branch supplied ideas for explicit inputs and a service host;
its broader model, dynamic name collisions and unvalidated `Tool.from_schema`
arguments are not copied.

The email implementation is on `6259-agent-send-email-action`, based on
`6259-agent-trigger-guard-rails`. No later action types are enabled by this change.

## Adding the next action

Register one `AgentActionType` in `contrib/agent/action_tools/` for an existing
service type. Its four responsibilities are:

1. `get_defaults()` seeds the callable name, usage instructions, typed inputs and
   service bindings once. Formula paths use input IDs; initial bindings use simple
   mode so the editor shows readable chips. References use literal
   `get('tool_input.<id>')` paths so deleted inputs can be detected without
   evaluating the formula.
2. `get_configuration_errors(action)` combines static service/integration checks
   with input-reference validation. It must not execute formulas or contact the
   integration.
3. `get_preview(action, arguments)` resolves the formulas with the validated
   arguments and returns a safe, bounded `StepPreview` input. Never include
   credentials.
4. `dispatch(action, arguments)` uses normal service dispatch with the
   application ownership checks.

The existing lifecycle API, typed-input editor, per-action toggles, strict model
argument validation, approval keys and approval cards are shared. Add a
presenter keyed by the stable service type and expose that type through the
action registry. Reuse its existing service form; add host capabilities only
where required. The approval key covers the exported service, so services with
child settings (for example HTTP headers) need nothing extra.

Creation/update/deletion follow the trigger convention: audit changed fields
without copying message content into action history. Trash restoration preserves
the action ID and allocates another callable name if its old name was reused.

## Implementation validation

Targeted suites cover action CRUD, permissions, import/export, trash, realtime,
typed inputs, previews, SMTP dispatch, approval keys, shared chat runs, and the
editor. A test-only second adapter verifies that the runtime handles an arbitrary
preview and dispatch without SMTP-specific fields.

The new migration was applied to an isolated PostgreSQL database, followed by a
clean migration-drift check. A real localhost SMTP exchange verified the
HTML email, all To/CC/BCC recipients, and omission of BCC from message headers.
Editor component DOM with production styles was inspected at desktop and 390px
widths; behavior is covered by the mounted-component suites. A full live-provider
browser session was not part of this validation.
