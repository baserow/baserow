# ADR 006: How the Button Field Shares Workflow Actions Across Modules

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-07-22                                     |
| Issue        | https://github.com/baserow/baserow/issues/1722 |
| Author       | Al Amin (@alamin-br)                           |
| Contributors | Davide (@silvestrid), Jérémie (@jrmi)          |

## Summary

The button field is a new database field type whose cells render a button. Clicking it
runs an ordered list of configured actions with the clicked row as context, and each
action's result available to the actions after it.

The application builder and the automation module already execute configured,
service-backed actions; the database module becomes the third consumer. This document
decides how that consumer is built: which classes are shared, how integrations reach the
database module, which user the actions run as, how import/export keeps working, and how
execution, failures, and permissions behave.

## Context

**The core base** (`baserow/core/workflow_actions`) is an abstract `WorkflowAction` with
generic mixins and no fields of its own, plus a registry base and a generic CRUD
handler. It contains no execution logic; its job is to keep the module implementations
consistent so they can be merged later.

**The builder** (`contrib/builder/workflow_actions`) subclasses it.
`BuilderWorkflowAction` holds page, element, event, and order; the `service` foreign key
sits on the abstract `BuilderWorkflowServiceAction`, because action types come in two
kinds: service-backed ones (thin shells forwarding to
`ServiceHandler().dispatch_service()`) and frontend-only ones (notification, open page,
logout, refresh data source) that never reach the backend. After each dispatch, data
providers get a `post_dispatch()` hook, which is how `previous_action` results reach
later actions.

**Automation** (`contrib/automation/nodes`) did not reuse the core base:
`AutomationNode` holds a `OneToOneField(Service)` and executes as a graph. Review
established there was no technical blocker behind that: the team was unsure the base
would fit and never came back to it. Adopting it now is mostly an inheritance change.

Three constraints shape everything below:

- Integrations are application-level objects, and the database application type does not
  support them today. Enabling the flag is one line; import/export, duplication, and
  templates are the real work.
- Local Baserow services run every permission check as the integration's
  `authorized_user`, by default its creator. Reused unchanged, a click would be
  attributed to whoever configured the field, not whoever clicked.
- Cross-application import order (databases first) cannot help an integration that lives
  in the database application and references its own tables.

## Decision

### 1. Model layer: converge on the core base, mirror the builder

1. A small preparatory PR, offered by the automation team, makes automation adopt the
   core `workflow_actions` base classes, removing the one existing divergence.
2. The database module mirrors `contrib/builder/workflow_actions` with database concepts
   substituted: `DatabaseWorkflowAction` (foreign key to the button field, `order`),
   abstract `DatabaseWorkflowServiceAction` holding the `service` foreign key, a type
   registry, and a handler and service layer that enforce permissions.

```mermaid
classDiagram
    class WorkflowAction {
        <<abstract, baserow.core>>
    }
    class BuilderWorkflowAction {
        page
        element
        event
        order
    }
    class BuilderWorkflowServiceAction {
        <<abstract>>
        service : FK Service
    }
    class AutomationNode {
        workflow
        service : OneToOne Service
        graph edges
    }
    class DatabaseWorkflowAction {
        field : FK button field
        order
    }
    class DatabaseWorkflowServiceAction {
        <<abstract>>
        service : FK Service
    }

    WorkflowAction <|-- BuilderWorkflowAction : exists today
    BuilderWorkflowAction <|-- BuilderWorkflowServiceAction
    WorkflowAction <|-- AutomationNode : step 1, preparatory PR
    WorkflowAction <|-- DatabaseWorkflowAction : step 2, this feature
    DatabaseWorkflowAction <|-- DatabaseWorkflowServiceAction
```

The core base contains no behavior, so step 2 re-implements a thin layer rather than
reusing code; the heavy machinery in `core/services` and `contrib/integrations` is used
as is. Keeping all three modules the same shape is what makes merging them into one
shared implementation cheap later. Generalizing the builder's dispatch process to serve
both modules is a promising follow-up with the builder team, not a prerequisite.

### 2. Action types: service-backed first, frontend actions kept possible

The first version registers service-backed types only: create, update, and delete
row(s), backed by the existing Local Baserow services. External types (HTTP request,
SMTP email, Slack) and code execution follow later, with the same premium or enterprise
licensing those services already have elsewhere.

Frontend-only actions (success toast, navigate to a URL or table, apply a temporary
filter) will likely be wanted later. The `service` foreign key therefore goes on the
abstract `DatabaseWorkflowServiceAction`, exactly as in the builder, so frontend-only
types can be added later without a schema migration.

### 3. Execution flow and failure behavior

A dispatch endpoint receives the click, builds a `DatabaseDispatchContext`, and
dispatches the actions in order. State changes are broadcast over the existing row
realtime channel, as the AI field already does, so every open view sees the loading
state.

```mermaid
sequenceDiagram
    actor User as Clicking user
    participant API as Dispatch endpoint
    participant H as DatabaseWorkflowActionHandler
    participant SH as ServiceHandler
    participant WS as Realtime channel

    User->>API: click (button field id, row id)
    API->>WS: button enters loading state (all open views)
    loop actions in order
        API->>H: dispatch(action, DatabaseDispatchContext)
        H->>SH: dispatch_service(service, context)
        SH-->>H: result
        Note over H: post_dispatch stores the result<br/>for later actions (previous_action)
    end
    alt an action fails
        H-->>User: error toast naming the failed action
        Note over H: remaining actions are skipped,<br/>completed actions stay
    end
    API->>WS: button back to idle, row updates broadcast
```

Failure behavior matches the builder: execution stops at the first failing action, the
rest are skipped, and the user sees an error toast. Nothing is rolled back, since
sequences can contain irreversible effects (an email cannot be unsent). Retries,
on-error action stacks, and per-click run history are out of scope, and so is rate
limiting until external action types arrive.

Dispatch is serialized per button cell: while a click is running, the endpoint rejects
further clicks for the same field and row, so a double click cannot run a sequence
twice. Row changes made by actions fire the normal side effects (webhooks, automation
triggers, realtime updates), the same as a manual edit; buttons add no loop guard of
their own beyond what automation already applies to its triggers.

Local row actions dispatch synchronously in the request. Slow external actions later
move behind the existing job/Celery pattern with realtime completion, so the API treats
"dispatched" and "completed" as separate states from the start.

### 4. Row context and result chaining

The database module registers two data providers for button dispatch:

- **A raw row provider** exposing the clicked row's values with their real types. The AI
  field's `HumanReadableFieldsDataProviderType` is not reused for this: it stringifies
  every value, which is right for prompt text and wrong for writing numbers, dates, or
  links into rows.
- **A previous-action provider** modeled on the builder's `PreviousActionProviderType`
  and automation's `PreviousNodeProviderType`, with identifier remapping on import, so
  all three modules keep the same design.

The raw row provider is a snapshot taken at dispatch time: every action sees the row as
it was when the user clicked, even after an earlier action changed or deleted it;
fresher values come from the previous-action provider.

### 5. Integrations and ownership

**Actions run as the user who clicks.** Permission checks, row history, created-by
fields, and the audit log all see the clicking user, and a click fails with the standard
error toast if that user lacks permission on a target table. There is no way to run an
action on someone else's behalf: a button is a shortcut for things the clicker could
already do, not a way to do more.

This is a deliberate break from the builder and automation, where services run every
check as the integration's `authorized_user`. That model exists because builder end
users are usually not Baserow users at all. Database clickers are the opposite: always
logged-in collaborators with at least the editor role (section 7). Reusing the
on-behalf-of model here would put the wrong name in row history and created-by fields,
and would let anyone who can edit a field use the integration to reach every table its
user can reach. Neither is acceptable in a database.

The mechanism is small and shared. The dispatch context carries the clicking user as the
`actor`; it flows down to the services, and the Local Baserow services use the actor
instead of `authorized_user` for permission checks and execution. Clicks stay
non-undoable (section 8), so click-triggered actions register outside any undo scope
even though they run as the clicking user.

The database application type still enables `supports_integrations`, but in the first
version the integration is an implementation detail, not something users manage. One
internal Local Baserow integration is created automatically per database the first time
a button field needs it, the same way dashboard integrations are handled; it is never
shown to users and is not bound to any person. Because of this, v1 needs no integrations
settings UI: the builder-style settings modal arrives together with external integration
types, whose credentials users do have to manage.

```mermaid
flowchart LR
    subgraph app ["Database application"]
        BF["Button field"] -->|ordered 1..n| WA["Workflow actions"]
        WA -->|each backs onto| S["Service"]
        I["Internal Local Baserow integration<br/>(auto-created, hidden)"]
    end
    S -->|configured via| I
    U["Clicking user"] -->|actor: permission checks,<br/>row history, created-by| T["Target tables and rows"]
```

Configuration keeps the existing field boundary: creating a button field and editing its
actions follow field update permissions, so the builder role and above. The action
editor offers the tables the configuring user can reach, and the same check happens
again at click time as the clicker, so a configuration made by someone with broader
access cannot give anyone extra access.

### 6. Import, export, duplication, and sharing

Table and field ids inside service configurations and previous-action references remap
through the standard `id_mapping` on import, as builder services already do. The hard
case is ordering: an integration inside a database can point at tables of that same
database, which do not exist yet mid-import. The builder has the same problem with
formulas and solves it in two passes: import everything, register the references that
cannot be resolved yet, and resolve them once the import completes. We reuse that
mechanism.

```mermaid
flowchart TD
    A["Import all application objects"] --> B{"Reference already<br/>resolvable via id_mapping?"}
    B -->|yes| C["Link immediately"]
    B -->|no| D["Register as deferred reference"]
    C --> E["Import completes"]
    D --> E
    E --> F["Second pass resolves deferred references"]
    F --> G["after_import hooks run;<br/>unconfigured integrations surface<br/>as reconfigure states on buttons"]
```

Exports and templates strip sensitive integration fields, as today. This does not affect
the internal Local Baserow integration, which carries no credentials and is simply
recreated on import. External integrations cannot recover on their own; their buttons
render disabled with an error indicator pointing at the integration to reconfigure. The
builder needs the same reconfigure experience; both modules should share one solution.

### 7. What kind of field is a button, and who may click it

A button is not a read-only field in the current sense (a server-computed column). It
stores no cell value, is interactive, and users may eventually have different rights to
it. Concretely:

- No stored value; no filtering, sorting, or grouping.
- Row write endpoints reject it through the same path as read-only fields, but the API
  documentation describes it as an action field, not a computed one.
- Clicking is a distinct operation on the dispatch endpoint, where permissions attach:
  editor role minimum, disabled in public views and for viewers and commenters, enforced
  backend-side.
- The dispatch endpoint accepts user sessions only; database API tokens cannot click in
  the first version, since a token has no role or identity to record.
- A future per-field "who can click" permission (a role-based permission on that
  endpoint) fits without rework; it is out of scope for the first version.

### 8. Behavior under common operations

- **Field duplication.** Actions and services are duplicated; both fields point at the
  same internal integration.
- **Application duplication, snapshot, export/import.** Integrations are copied with the
  application; deferred resolution reconnects self-references; stripped credentials only
  affect external integrations, which must be reconfigured.
- **Trash and restore.** Actions and services follow the field, as builder actions
  follow their element.
- **Deleting or trashing a target table or field.** Services keep the dangling reference
  and the button enters the reconfigure state rather than failing only at click time;
  restoring from trash heals it without reconfiguration.
- **Field type conversion.** Converting away deletes actions and services; converting
  into a button starts empty. Both directions are destructive, like other fields that
  carry configuration.
- **Undo/redo.** Configuration changes are undoable like other field updates. Clicks are
  never undoable, even when a sequence only touches rows: a partially undoable button is
  more confusing than none.
- **Deleting a user.** Nothing breaks: actions run as whoever clicks, and the internal
  integration is not bound to a person, so no button depends on any particular account.
- **Failure mid-sequence.** Execution stops, later actions are skipped, completed
  actions stay, and the user sees an error toast (section 3).

## Options considered for the model layer

### Option 1: `DatabaseWorkflowAction` mirroring the builder (chosen)

Database-scoped subclass of the core base, mirroring `contrib/builder/workflow_actions`,
preceded by the automation convergence PR.

- Pro: a proven pattern that fits the button exactly; no cross-team refactor; database
  depends only on core.
- Con: the thin module layer is re-implemented a third time (small: builder action types
  are mostly empty shells around shared services); execution consolidation is deferred,
  not solved.

### Option 2: node/service model, following the automation pattern

An ordered list of records each holding a `OneToOneField(Service)`, like
`AutomationNode`, skipping the `WorkflowAction` base.

- Pro: matches automation's "every node is a service" invariant.
- Con: `AutomationNode` is coupled to workflows and graph traversal a flat list does not
  need; it rules out frontend-only action types; and it diverges from the core base just
  as bringing automation onto it becomes nearly free.

### Option 3: extract a shared action-sequence abstraction into core first

Refactor core to own ordered service-backed execution with context chaining, port
builder and automation, then build the button field on top.

- Pro: one implementation instead of three; future consumers become cheap.
- Con: a large cross-team refactor with migration risk, blocking the feature on work
  with no user-facing value, before the third real consumer exists to show what the
  right abstraction is.

The chosen path is Option 1 plus the cheap part of Option 3: unify the base classes now,
defer unifying execution until a real need appears.

## Consequences

- The button field ships without waiting on a cross-team refactor; the upstream
  dependencies are the small automation inheritance change and the `actor` property on
  the dispatch context (section 5).
- The database module gains integrations, but v1 keeps them internal: import/export
  handling remains the main schedule risk, while the settings UI and reconfigure states
  move to the version that adds external integrations.
- Actions are authorized and attributed as the clicking user, so permissions, row
  history, and created-by fields are always right, with no on-behalf-of machinery.
- Until a merge is justified, three similar thin layers exist side by side; the shared
  base classes keep them cheap to unify.

## Revisit triggers

- A fourth consumer appears, or buttons need branching/routers: extract the shared
  execution abstraction (Option 3) instead of copying a fourth time.
- Buttons reach public views: anonymous clicks would need an explicit field-level "run
  as the field owner" option, reopening the on-behalf-of execution rejected here.
- Frontend-only button actions are prioritized: design the shared dispatch mechanism
  with the builder team before building one alone.
