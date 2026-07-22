# How the button field shares workflow actions, services, and integrations across modules

Issue: https://github.com/baserow/baserow/issues/1722

Status: draft, under review in the pull request that adds this document. It is updated
as the review discussion progresses and will state the final decision before it is
merged.

## Summary

The button field is a new database field type whose cells render a button. Clicking
it executes an ordered list of configured actions with the clicked row as context,
and each action's result available to the actions after it.

Baserow already has two modules that execute configured, service-backed actions: the
application builder and the automation module. The database module becomes the third
consumer. The first draft of this document framed that as a model-inheritance choice.
Review showed the model hierarchy is the cheap part; the expensive decisions are the
ones around it. This document therefore decides:

1. Which classes the database module shares or mirrors (the original question).
2. How action types are structured so that frontend-only actions remain possible.
3. How execution and failure behave.
4. How actions read the clicked row and each other's results.
5. How integrations become available to the database module.
6. Which user the actions run as, and how that changes with the upcoming Agent
   feature.
7. How import/export, duplication, snapshots, and templates keep working.
8. What kind of field a button actually is, and who may click it.
9. How the field behaves under common operations (trash, conversion, undo, user
   deletion).

## Context

### The three existing building blocks

**The core workflow action base** (`baserow/core/workflow_actions`) is deliberately
thin. `WorkflowAction` is an abstract model that combines generic mixins
(polymorphic content type, created/updated timestamps, hierarchy, registry access)
and defines no fields of its own. The module also provides `WorkflowActionType` (a
registry base with a `dispatch()` contract and import/export mixins) and
`WorkflowActionHandler` (generic polymorphic CRUD). It contains no execution logic.
Its value is not inherited behavior but a common shape: consumers that subclass it
get the same polymorphism, registry wiring, CRUD, and serialization patterns, which
keeps their implementations mergeable later.

**The builder implementation** (`contrib/builder/workflow_actions`) subclasses the
core base. `BuilderWorkflowAction` is the concrete model (page, element, event,
order). The `service` foreign key is not on that model; it sits on an abstract
subclass, `BuilderWorkflowServiceAction`. That split exists because the builder has
two kinds of action types:

- Service-backed types (create/update/delete rows, HTTP request, SMTP email, Slack
  message, AI agent, and so on). These are thin shells: their `dispatch()` forwards
  to `ServiceHandler().dispatch_service()`, and all real behavior lives in
  `core/services` and `contrib/integrations`.
- Frontend-only types (notification, open page, logout, refresh data source). These
  never reach the backend; the base type's `dispatch()` raises, and the client
  executes them.

Dispatching walks the ordered actions. After each dispatch, the handler gives every
registered data provider a `post_dispatch()` hook, which is how the
`previous_action` provider captures results for later actions in the same sequence.

**The automation implementation** (`contrib/automation/nodes`) did not reuse the
core base. `AutomationNode` holds a `OneToOneField(Service)` and models execution as
a graph (nodes, edges, previous-node outputs) rather than a flat ordered list.
Review of this document resolved a question the first draft left open: there was no
hard incompatibility behind that choice. The automation team was unsure the core
base would fit and never revisited the decision. Adopting the base in automation now
is mostly an inheritance change, and the automation team has offered to make it.

### Why this is more than a model-inheritance question

Three facts, all surfaced during review, shape most of this document:

- **Integrations are application-level objects.** Services need an integration, an
  integration belongs to an application, and the database application type does not
  support integrations today. Enabling the flag is one line; making import/export,
  duplication, snapshots, and templates behave correctly is the real work.
- **Actions run as the integration's user.** A `LocalBaserowIntegration` has an
  `authorized_user`, set by default to whoever created the integration, and every
  permission check and data access in its services runs as that user. Reused
  unchanged, a button click would be attributed to whoever configured the field,
  not whoever clicked it.
- **Import ordering assumes integrations live outside the database.** Builder and
  automation integrations can reference database tables because databases import
  first (`import_application_priority`). A database integration that references its
  own application's tables breaks that assumption: the integration would need
  objects that are created in the same import.

## Decision

### 1. Model layer: converge on the core base, mirror the builder

Two steps, agreed with the builder and automation maintainers during review:

1. A small preparatory change makes the automation module adopt the core
   `workflow_actions` base classes. This removes the one existing divergence, so
   the button field joins a pattern all modules share rather than picking a side.
   The automation team offered to open this PR.
2. The database module adds a layer mirroring `contrib/builder/workflow_actions`
   with database concepts substituted: a concrete `DatabaseWorkflowAction`
   subclassing the core `WorkflowAction`, with a foreign key to the button field
   and an `order` field; an abstract `DatabaseWorkflowServiceAction` subclass
   holding the `service` foreign key; a `database_workflow_action_type_registry`;
   and a handler plus permissioned service layer shaped like the builder's.

To be explicit about what is and is not reused: the core base grants no execution
behavior, so step 2 is a disciplined re-implementation of a thin layer, not code
reuse. The heavy machinery (request handling, dispatch, the service and integration
types themselves) lives in `core/services` and `contrib/integrations` and is
consumed unchanged. Keeping the three module layers the same shape is what makes a
later extraction of a shared execution abstraction cheap, if a fourth consumer or a
need for branching ever justifies it.

The builder team also raised that the most valuable thing to share may be the
builder's action dispatch process itself, generalized to serve both modules,
especially if both end up mixing frontend and backend actions. We treat that as a
promising follow-up to explore together; it is not a prerequisite for the button
field and does not change the model decision above.

### 2. Action types: service-backed first, frontend actions kept possible

The first version registers service-backed types only: create row(s), update
row(s), and delete row(s), all backed by the existing Local Baserow services.
External types (HTTP request, SMTP email, Slack message) and code execution follow
in later releases behind the license tiers where those services already sit.

The first draft said "service-backed types only" as a design principle. Review
pushed back with concrete frontend-only actions that make sense for a button: show
a success toast using a previous action's result, navigate to a URL or table, apply
a temporary filter, sort, or search. We accept that direction. The concession in
the data model is exactly the builder's: the `service` foreign key goes on the
abstract `DatabaseWorkflowServiceAction`, not on the base model, so frontend-only
types can be added later without a schema migration. Which frontend actions to
build, and when, stays a product decision outside this document.

### 3. Execution flow and failure behavior

Dispatch mirrors the builder: an endpoint receives the click, loads the action
sequence, builds a `DatabaseDispatchContext`, and dispatches each service-backed
action in order through the registry. Progress is broadcast the way the AI field
does it: state changes ride the existing row realtime channel, so every open view
sees the button enter and leave its loading state. No bespoke websocket layer.

On failure, behavior matches the builder exactly, confirmed with the builder team
as the intended common behavior: execution stops at the first failing action, the
remaining actions do not run, and the clicking user sees an error toast naming the
failed action. Nothing already executed is rolled back, because a sequence may
contain effects that cannot be reversed (an email cannot be unsent). Retries,
alternate on-error action stacks, and a per-click run history are explicitly out of
scope here; they are candidates for later releases and, ideally, for a solution
shared with the builder.

Local row actions dispatch synchronously within the request, like builder actions
today. When slow or external actions arrive (HTTP, email), execution should move
behind the existing job/Celery pattern with realtime completion updates, as the AI
field already does. The API contract for the dispatch endpoint must therefore not
promise synchronous completion; clients treat "dispatched" and "completed" as
separate states from the start.

### 4. Row context and result chaining

The database module registers its own data provider registry for button dispatch,
with two providers:

- **A raw row provider.** Action parameter formulas resolve the clicked row's
  values with their real types. We deliberately do not reuse the AI field's
  `HumanReadableFieldsDataProviderType` for this: it stringifies every value, which
  is correct inside a text prompt and wrong when writing a number, date, or link
  into another row. The human-readable provider remains the right tool where prose
  is wanted (and stays available to an AI-agent action's prompt, for example).
- **A previous-action provider**, modeled on the builder's
  `PreviousActionProviderType` and automation's `PreviousNodeProviderType`, exposing
  each action's dispatch result to the actions after it, with identifier remapping
  on import so references survive export/import. A third sibling of an existing
  pair, not a new shape, so the three can be merged if execution is ever
  consolidated.

### 5. Integrations become available to the database module

The database application type enables `supports_integrations`. Integrations stay
application-level objects, managed in an application-level settings modal patterned
on the builder's, and they behave like builder integrations when the application is
duplicated, exported, imported, or snapshotted.

We considered attaching integration configuration to the button field itself
instead. Rejected: integrations are deliberately reusable, permission-checked,
application-scoped objects. Embedding them per field would fragment credential
management, multiply copies of the same SMTP or Slack configuration across fields,
and diverge from every other module for no capability gain. A field-level shortcut
in the UI ("create an integration from here") can still open the same
application-level objects.

Setting the flag is the trivial 5% of this decision; the consequences for
import/export are the other 95% and are covered in section 7.

### 6. Which user the actions run as

Today, every Local Baserow service call runs as the integration's
`authorized_user`, by default the user who created the integration. Export strips
this field (it is sensitive) and import rebinds it to the importing user.

**For the first version we change nothing.** Button actions run as the
integration's `authorized_user`, and row changes are attributed to that user in row
history and the audit log. This is a documented, temporary limitation, and it is
the same limitation the builder and automation live with today.

The proper fix is already planned by the builder team for the near term: the
**Agent** feature introduces workspace-scoped virtual users that replace real users
in integrations. When it lands, button integrations bind to agents, and audit
entries gain initiator metadata with the goal of recording three things: the acting
agent, the real initiator, and the origin, as in "row created by agent Y, initiated
by user X clicking button field Z". For a publicly shared view the initiator is
recorded as anonymous. The button field adopts this as soon as it exists rather
than building its own attribution mechanism now and migrating off it later.

Two deliberate consequences of this model, settled during review:

- A click may perform actions the clicking user could not perform directly. That is
  a feature, not a leak: a button is a predefined, admin-configured operation, and
  its power comes from the integration (later the agent), guarded by who is allowed
  to configure the field. The action editor therefore offers the tables the
  integration's user (later the agent) can reach, not the editing user's tables.
- If that user or agent loses permission on a target table, clicks fail loudly at
  dispatch time with the standard error toast. No silent skipping, no fallback.

### 7. Import, export, duplication, and sharing

**Ordering.** Cross-application ordering is solved today by importing databases
before builder and automation applications. That cannot help an integration that
lives in the database application and references its own tables. We adopt the
mechanism the builder already uses for the equivalent problem (formulas referencing
objects that do not exist yet): deferred, post-import resolution. The import
creates all objects first, including button fields and their actions; references
that cannot be resolved yet are registered instead of resolved inline; after the
import completes, a second pass resolves them. This is confirmed with the builder
team as the intended pattern rather than inventing new ordering rules between
applications.

**Credentials.** Exports and templates strip sensitive integration fields, as they
do today. For the Local Baserow integration, the existing `after_import` hook
rebinds `authorized_user` to the importing user, so a re-imported database with
row-action buttons works immediately. External integrations (SMTP, Slack, HTTP
credentials) cannot self-heal: after import the service exists with its
configuration but without credentials. This "reconfigure your integrations" state
is new for database users, so it must be explicit: a button whose integration is
unconfigured renders disabled with an error indicator, and the field editor points
at the integration to fix. Once Agents land, the automatic rebinding for Local
Baserow disappears too, and this reconfiguration surface becomes the shared,
normal path; the builder team plans the same UX and we intend to share it.

**Duplication and snapshots** follow from the above: duplicating a field duplicates
its actions and their services; duplicating or snapshotting the application also
copies its integrations; identifier remapping covers table, field, and view
references inside action configurations, and previous-action references remap
through the standard id-mapping tables.

### 8. What kind of field is a button, and who may click it

A button is not a read-only field in the sense the database module uses the term
today. Existing read-only fields are table columns whose values the server
computes; users cannot write them but also cannot interact with them. A button
stores no cell value at all, is interactive, and different users may eventually
have different rights to use it.

Practically, the field type behaves as follows:

- No stored cell value, and no participation in filtering, sorting, or grouping.
- Row write endpoints reject values for it, the same enforcement path read-only
  fields use. It shares that mechanic without inheriting the category's meaning;
  API documentation should describe it as an action field, not a computed one.
- Clicking is a distinct operation on a dedicated dispatch endpoint, which is where
  permissions attach. In the first version: executing buttons require at least the
  editor role, and they are disabled in publicly shared views and for viewers and
  commenters, enforced at the endpoint, not merely hidden in the UI.
- A future per-field "who can click" permission (an RBAC operation on the dispatch
  endpoint) fits this model without rework. It is out of scope for the first
  version.

### 9. Behavior under common operations

| Operation | Behavior |
| --- | --- |
| Field duplication | Actions and their services are duplicated; both fields point at the same application-level integrations. |
| Application duplication, snapshot, export/import | Integrations are copied with the application; deferred post-import resolution reconnects self-references; sensitive credentials strip and must be reconfigured (Local Baserow self-heals until Agents land). |
| Trash and restore | Actions and services follow the field through trash and restore, as builder actions follow their element. |
| Field type conversion | Converting a button to another type deletes its actions and services. Converting another type into a button starts with an empty action list. Both are destructive one-way conversions, like other configuration-carrying fields. |
| Undo/redo | Configuration changes (field settings, action list edits) are undoable like other field updates. Clicks are not undoable, even when every action in the sequence touches only rows, because sequences may include irreversible effects and a partially undoable button is more confusing than a consistently non-undoable one. |
| Deleting the integration's user | Deleting the `authorized_user` cascades away the Local Baserow integration; the services survive with a null integration and the affected buttons enter the same disabled, "reconfigure integration" error state as after a credential-stripped import. The Agent feature removes this failure mode, since agents are not deletable user accounts. |
| Failure mid-sequence | Execution stops, later actions do not run, completed actions stay, the user sees an error toast (section 3). |

## Options considered for the model layer

### Option 1: database-scoped `DatabaseWorkflowAction`, mirroring the builder (chosen, with a preparatory step)

Add `contrib/database` workflow actions subclassing the core abstract
`WorkflowAction`, with a registry, handler, and service layer mirroring
`contrib/builder/workflow_actions`, preceded by the small change that brings
automation onto the same base.

Pros:

- Proven shape; the builder demonstrates it for element-triggered, ordered,
  service-backed actions, which is exactly the button's shape.
- Fastest path that still converges: after the preparatory step, all three modules
  share one ancestry, and the expensive machinery (services, integrations) is
  consumed unchanged.
- Module isolation: database depends on core only, not on builder or automation
  internals.

Cons:

- The thin module layer (model, registry, execution loop, previous-result
  provider) is re-implemented a third time. Reviewers sized this honestly: the
  existing builder action types are mostly empty shells around shared services, so
  the duplication is small, but it is not zero.
- Consolidation of execution itself is deferred, not solved.

### Option 2: node/service model, following the automation pattern

Give the button field an ordered list of records each holding a
`OneToOneField(Service)`, like `AutomationNode`, skipping the `WorkflowAction` base.

Pros:

- Matches automation's "every node is a service" invariant.
- Could later inherit automation features such as routers and run history.

Cons:

- `AutomationNode` is coupled to workflows and graph traversal (edges,
  previous-node outputs); reusing it means first extracting those parts, a refactor
  of a shipped module.
- A flat ordered list needs none of the graph machinery.
- It would also foreclose frontend-only action types, which review concluded we
  want to keep possible (section 2).
- It diverges from the core abstraction at the exact moment review established
  that converging automation onto it is nearly free.

### Option 3: extract a shared executable action-sequence abstraction into core first

Refactor so core owns "ordered, service-backed action sequence with context
chaining" (models, execution loop, previous-result provider), port builder and
automation onto it, then build the button field on top.

Pros:

- One implementation of execution and chaining instead of three.
- Future consumers become cheap.

Cons:

- A large cross-team refactor of two shipped modules, with migration risk, blocking
  a large feature on work with no user-facing value of its own.
- The right shared abstraction is not yet known; the button field is the third data
  point that would inform it. Extracting after three real consumers exist is
  cheaper than guessing now and migrating later.

The chosen path takes Option 1 and borrows the cheap part of Option 3: unify the
base classes now (nearly free), defer unifying execution until the need is proven.

## Consequences

- The button field ships without waiting on any cross-team refactor; the only
  upstream dependency is a small, offered, inheritance-only automation change.
- The database module gains integrations, which is the largest single work item in
  this document (settings UI, import/export handling, reconfiguration states) and
  the main schedule risk.
- Attribution is knowingly imperfect in the first version and fixed by adopting
  Agents, not by building throwaway mechanics.
- Three parallel thin execution layers exist until a real consolidation trigger
  appears. The mitigations are structural: shared base classes, same layer shape,
  sibling data providers.

## Revisit triggers

- A fourth consumer of ordered service-backed actions appears, or the button field
  needs branching or routers: extract the shared execution abstraction (Option 3)
  instead of copying a fourth time.
- The Agent feature lands: bind button integrations to agents and add initiator
  metadata to audit entries.
- Frontend-only button actions get prioritized: pick up the shared, generalized
  dispatch-process discussion with the builder team before implementing them
  independently.
