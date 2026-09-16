# ADR 006: How the Button Field Shares Workflow Actions Across Modules

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Accepted                                       |
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
- Cross-application import order (databases first) cannot help services that live in the
  database application and reference that same database's tables.

## Decision

### 1. Model layer: converge on the core base, mirror the builder

1. A small PR, offered by the automation team, makes automation adopt the core
   `workflow_actions` base classes, removing the one existing divergence. It lands in
   parallel; nothing in the database work waits on it.
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
    WorkflowAction <|-- AutomationNode : automation PR, in parallel
    WorkflowAction <|-- DatabaseWorkflowAction : this feature
    DatabaseWorkflowAction <|-- DatabaseWorkflowServiceAction
```

The core base contains no behavior, so the database module adds its own thin glue layer;
the heavy machinery in `core/services` and `contrib/integrations` is used as is. Keeping
all three modules the same shape is what makes merging them into one shared
implementation cheap later. Generalizing the builder's dispatch process to serve both
modules is a promising follow-up with the builder team, not a prerequisite.

### 2. Action types: service-backed first, frontend actions kept possible

The first version registers service-backed types only: create, update, and delete
row(s), backed by the existing Local Baserow services. External types and code execution
follow later, with the same premium or enterprise licensing those services already have
elsewhere.

**Amendment (phases 4a to 4c, September 2026).** Three external types have since landed:
HTTP request (4a), SMTP email (4b) and Slack message (4c). Each reuses the service type
the builder and automation already have, so a button gets the same behaviour without a
second implementation. What makes them external rather than merely service-backed is
that they reach outside this installation, so only clicks containing one spend the rate
limit's budget, and the lock guarding the row is sized for how long they may take: each
service type says, and a click waits for the sum of its actions.

**Amendment (phase 4d, September 2026).** A fourth service-backed type landed alongside
them: start workflow, which queues an automation run and returns rather than reaching
outside this installation, so it is deliberately not one of the three external types
above. Section 5 records why, and what not being external changes for the rate limit and
the lock.

The Slack action posts to `chat.postMessage` through a bot token held by a
`slack_bot` integration on the field's own database. It answers with `ok`, `channel` and
`ts`, the message reference a later action can write into a row or thread against.
Because the response is what the service stores, its schema describes it under the same
`data` key the dispatch puts it in, rather than unwrapping it as the HTTP and email
services do: unwrapping would have meant migrating every sample already stored. The API
endpoint is configurable so the end-to-end tests can point it at a stub.

Frontend-only actions (success toast, navigate to a URL or table, apply a temporary
filter) will likely be wanted later. The `service` foreign key therefore goes on the
abstract `DatabaseWorkflowServiceAction`, exactly as in the builder, so frontend-only
types can be added later without a schema migration.

Phase 1's `url_formula` field attribute was scaffolding, not part of the end state. It
existed because the button shipped before the action layer. That layer has since arrived:
opening a URL is a frontend-only `open_url` action like any other, a data migration turns
every existing `url_formula` into one, and nothing reads the attribute any more. The
column was dropped in phase 3: the zero-downtime rule protects the previously released
version, and no released version carries a button field at all, so no older process is
left writing it during a rolling deploy. A button never carries both a `url_formula` and an action
list, and nothing is designed around them coexisting.

The builder's `open_page` is the working precedent, not just an analogy. Its `custom`
navigation branch already stores its target as a formula object, the same shape as
`url_formula`, so the action type had an implementation to mirror rather than invent.

The client does not, however, run a frontend-only action on its own. A click always calls
the dispatch endpoint; the endpoint dispatches the service-backed actions, skips the
frontend-only ones, and hands them back under a `client_actions` key for the browser to
execute once the response arrives. This is where the database diverges from the builder,
which does execute its notification and open-page actions without a round trip.
Implementation established why: running the two kinds in list order would need one
dispatch call per contiguous run of service-backed actions, and the click lock is keyed on
`(field_id, row_id)`, so every call after the first would be rejected with 409. Returning
the whole frontend tail in one response avoids that, and it buys a second property that
matters now that **same tab** is the default target: a failing action raises before the
response is built, so `client_actions` never reaches the browser and the navigation does
not happen, leaving the user on the error toast rather than carrying them away from it.
The cost is that a frontend-only action always runs after every service-backed one,
whatever its position in the list.

Phase 3 makes that cost safe rather than removing it. The data explorer offers an
action only what precedes it in the list, so a frontend-only action can only ever
name a service-backed one that has already run, and a service-backed action is never
offered a frontend-only one, which produces no result to read. The execution split
therefore stays as it is, and no ordering a user can configure resolves against an
action that has not run.

Public views are not part of that reasoning. An earlier draft of this section argued the
client-side path preserved the phase-1 behaviour of a URL button working in a publicly
shared view. That is no longer true and no longer wanted: phase 1 review concluded button
fields should not appear in public views at all, and `ButtonFieldType` now sets
`can_be_in_public_view = False`. There is no public-view button left to preserve, so
nothing in the action design should be shaped around one. Section 7's rule is the whole
story: buttons are unavailable to anonymous users, whether or not their actions reach the
server.

### 3. Execution flow and failure behavior

A dispatch endpoint receives the click, builds a `DatabaseDispatchContext`, and
dispatches the actions in order. The loading state belongs to the person who clicked:
their own cell shows it until the response arrives, and ignores further clicks meanwhile.

```mermaid
sequenceDiagram
    actor User as Clicking user
    participant Cell as The clicked cell
    participant API as Dispatch endpoint
    participant H as DatabaseWorkflowActionHandler
    participant SH as ServiceHandler

    User->>Cell: click
    Cell->>API: dispatch (button field id, row id)
    Note over Cell: loading until the response arrives
    loop actions in order
        API->>H: dispatch(action, DatabaseDispatchContext)
        H->>SH: dispatch_service(service, context)
        SH-->>H: result
        Note over H: post_dispatch stores the result<br/>for later actions (previous_action)
    end
    alt an action fails
        H-->>API: error for the failed action
        API-->>Cell: error toast naming the failed action
        Note over H: remaining actions are skipped,<br/>completed actions stay
    else the sequence succeeds
        API-->>Cell: results, plus the frontend-only actions to run
    end
```

An earlier draft of this section broadcast that loading state to every open view over the
row realtime channel, the way the AI field does. That was descoped on 2026-07-28 and now
belongs to phase 4. Local dispatch is synchronous, so the clicking user has the outcome in
the response, and other viewers see the row changes arrive through the normal row-update
signals; between the two there is nothing for a concurrent viewer to watch. A broadcast
loading state is built when external actions make a dispatch slow enough for that gap to
be worth showing, which is also when the job/Celery pattern arrives.

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

Where those results live diverges, and deliberately. The builder keys them into the
cache under a client-supplied dispatch id, because its browser dispatches one action
at a time and a result would otherwise have to be trusted from the request body.
Automation reads them back from workflow history, because History is a product
feature there. A button runs its whole sequence inside one request (section 3), so
its results are a plain dict on the dispatch context: nothing outlives the request,
nothing is keyed by anything a caller supplies, and a fabricated result cannot be
fed to a later action. This is the concrete payoff of the per-click endpoint.

One consequence reaches the API. A dispatch result is serialized with
`user_field_names`, so it is keyed by field name, while a formula path holds
`field_<id>`. The server bridges the two itself when it resolves a path, but the
browser cannot: a frontend-only action may reference a row in a table it has no
fields for. Each result therefore carries the names of the fields it returned, built
only when the click has a frontend-only action to read them.

The raw row provider reads the row again as each action starts, so an action sees what
the actions before it did to it. Reading the row after an earlier action deleted it
fails that action and stops the sequence, rather than resolving to nothing and letting
the action write blanks. Like the builder's, both providers are implemented on backend
and frontend, so the action editor's data explorer and the dispatch path see the same
shapes.

This reverses an earlier decision to make the provider a click-time snapshot. That
version was never fully true: values held through a related manager, such as link row,
multiple select and multiple collaborators, were read when the formula ran rather than
when the click happened, so a sequence mixed snapshotted and live values with no way to
tell which was which. It also leaned on the previous-action provider as the way to read
fresher values, which reads a named earlier action's result rather than the row, in a
different shape from this provider. A click-time snapshot may return later as a provider
of its own, asked for by name.

### 5. Integrations and ownership

**Actions run as the user who clicks.** Permission checks, row history, created-by
fields, and the audit log all see the clicking user, and a click fails with the standard
error toast if that user lacks permission on a target table. The same rule holds per
field: an action that would write a field the clicker cannot write fails, rather than
silently skipping that field the way the builder's upsert does today. There is no way to
run an action on someone else's behalf: a button is a shortcut for things the clicker
could already do, not a way to do more. That holds for every action a button carries out
itself. Starting a workflow, added in phase 4d, is the one exception, and the amendment
below says how far it reaches and what bounds it.

This is a deliberate break from the builder and automation, where services run every
check as the integration's `authorized_user`. That model exists because builder end
users are usually not Baserow users at all. Database clickers are the opposite: always
logged-in collaborators with at least the editor role (section 7). Reusing the
on-behalf-of model here would put the wrong name in row history and created-by fields,
and would let anyone who can edit a field use the integration to reach every table its
user can reach. Neither is acceptable in a database. Attaching such an integration to an
action is what is refused; a button that starts a workflow reaches the same model one
step removed, which the amendment below states rather than hides.

Database buttons need no Local Baserow integration. That integration exists only to
carry a user for services that act inside Baserow, and for a button that user is the
clicker. The dispatch context carries the clicking user as the `actor`, and it flows
down to the services:

- No integration attached, which is every database button in v1: the service authorizes
  and executes as the actor, and fails if there is none.
- Integration present, which is the builder, automation, and any future opt-in:
  `authorized_user` authorizes, unchanged. Who started the run is recorded beside that,
  not instead of it: the run's history carries the person as `triggered_by`, and the
  dispatch context's `actor` stays empty, so a node that happens to have no integration
  does not start acting as whoever clicked.

Whether "no integration attached" is modeled as a nullable foreign key on the service or
as a small purpose-built object with the same interface is an implementation choice, not
made here. The architectural commitment is only that a database click never depends on
an integration's user.

This decision covers only Local Baserow services. External integrations (SMTP, Slack,
and the rest) carry real configuration rather than a stand-in user, so their services
keep requiring them. How those integrations are shared is deliberately not settled here.
The amendments below record what phases 4b and 4c settled instead. Review flagged that application-level sharing, the
current builder model, lets any builder attach someone else's credentials to their own
button and act as them, for example sending email from the creator's account.
Integrations today have no ownership at all, and review agreed on a sequence for fixing
that. When external integrations arrive, every integration states explicitly who can
reuse it, extending the warning the builder already shows at authorization time. A later
iteration adds real ownership: a `created_by` user and an `is_shared` flag, private by
default. Both steps are designed with the builder team, since they apply to its
integrations as much as to buttons.

**Amendment (phase 4b, September 2026).** The email action does not take an
`SMTPIntegrationType` integration after all. A database action carries no integration,
so a button sends only through this installation's own mail server, and the action type
pins `use_instance_smtp_settings` on every save rather than offering the choice. That
keeps a button's email out of the sharing question above entirely: there are no
credentials on the action to lend to anybody. It also makes
`BASEROW_INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS` a switch for the
feature: with it off, or with no mail server configured, the editor offers the action
disabled and says which of the two it is. An installation that wants per-action
credentials is the revisit trigger for attaching an integration here.

**Amendment (phase 4c, September 2026).** External integrations attach on the database
application itself, which the generic integration API already supports once the
application type declares `supports_integrations`. The Slack action is the first to use
this.

**Amendment (phase 4d, September 2026).** A fourth service-backed type, start workflow,
reuses the `CoreStartWorkflowServiceType` the builder and automation already have:
dispatch queues the automation's own Celery run and returns at once, so a click
experiences it like any other row action rather than like the external ones above. That
is also why `is_external` stays `False` here: the flag means "reaches outside this
installation," and it is what redacts a failure's message, sizes the dispatch lock's TTL,
and decides which clicks spend the button rate limit's budget. Queuing Celery work inside
Baserow does none of those things, so a button that starts workflows is not charged
against that budget at all — the automation module's own limits on how much it will run
are what bound it instead.

The shared service type takes only a workflow id, not the row, so the clicked row is
never handed to the workflow it starts. A workflow that needs the row waits for the
phase-6 trigger node, which is designed to carry it as payload.

The service type resolves that id through
`AutomationWorkflowService().get_workflow(user, workflow_id)`, which checks only that the
configuring user may read the workflow — and a user is commonly a member of more than one
workspace. Left alone, that would let an action name a workflow the button itself has no
business reaching. So the action type checks the workspace itself, the same defensive
shape section 6 already uses for an integration outside the field's own database:
`prepare_values` refuses a workflow that is not in the button field's own workspace on
save, and import blanks one that arrived pointing outside it rather than trust what the
file claims, leaving the action to report itself unconfigured like any other action
missing what it needs. A snapshot and its restore are the exception to that blanking, and
have to be: a snapshot's application is imported with no workspace on purpose, to hide it
from the system, so the workspace the copy belongs to is read from the import's own
`import_workspace_id` instead of from the field. Without that, taking a snapshot would
quietly unconfigure the button and the restore would hand back one that starts nothing,
which is the same reason section 6 gives for not dropping integrations on a restore.

**What a click reaches through a started workflow.** The invariant at the top of this
section does not survive this action, and it was never going to. An automation's Local
Baserow nodes act as their integration's `authorized_user`, not as whoever set the
workflow running, and dispatch checks only that the clicker may dispatch this field's
actions — nothing about the workflow. So an editor, who holds the dispatch operation but
not the builder role that reading or running a workflow needs, can click a button and
cause writes under another user's name in databases they cannot read, and cannot open the
workflow they ran or its history to see what happened.

That is what "a button starts a workflow" means. The alternative, running the workflow's
nodes as the clicker, is a different feature with a worse failure mode: workflows that
half-run, differently for each person who clicks. So the reach is accepted and bounded
instead, by two things and no more. The person configuring the action must be able to
read the workflow, which puts choosing one behind the same field-update permission as
every other action. And the workflow must be in the button field's own workspace, which
the guard above enforces on save and on import. Within a workspace, a button that starts
a workflow is a way for a builder to hand editors a lever on work the builder could
already do; across workspaces it is nothing at all. The invariant still holds unqualified
for every other action type: the row actions, the HTTP request, the email and the Slack
message all act as the clicker or as this installation, and none of them borrows another
user's reach.

The click itself is not anonymous, though. The run's history records the clicker as a
subject (`triggered_by_id`, `triggered_by_type` and `triggered_by_name`, so an agent can
start a run later and the name survives the user being deleted), and the click is
registered as a `dispatch_button_field` action, so the audit log holds who clicked which
button on which row. None of that changes who the nodes act as: the context's `actor` slot, which a Local
Baserow node without an integration would act as, stays empty for a run. A workflow that
another workflow starts records nobody, since the person is not a member of wherever
that second workflow lives. A test run or simulation started from the editor records
whoever pressed the button, including when it waits for its trigger's event: the
workflow keeps that subject beside its other temporary test state until the run starts
or is cancelled.

Not charging the button rate limit has one consequence worth stating plainly. When the
automation module's own limits are what refuse a run, the clicker is not told:
`async_start_workflow` catches the rate limit and the too-many-errors cases after dispatch
has already returned, records them in the workflow's history and returns nothing, so the
click shows the ordinary success toast and the reason is visible only to someone who can
open the workflow. Surfacing it at the button would mean waiting on the queue's decision,
which is the opposite of the fire-and-forget shape chosen above.

Each action type names the integration types it may carry in an
`allowed_integration_types` allow-list. It is empty unless the action needs a credential
of its own, which is why the row actions, the HTTP request, the email action and start
workflow all carry nothing: a row action acts as the clicker, an HTTP request carries its
own headers, email sends through the instance's own mail server, and start workflow
reaches automation by workflow id rather than by credential. No action type lists
`local_baserow`, because its `authorized_user` would replace the clicker as the acting
user, which is what this section forbids.

The database application derives what it will hold from those lists rather than keeping
a second one, so the two cannot drift apart. Every path reads the same rule: an
integration a button may carry is of a type the action accepts and belongs to the
field's own database. Saving, importing and dispatching all refuse anything else, and a
`local_baserow` integration is refused on a database outright, on create and on import,
so it cannot exist there to be attached.

Who may attach one is checked separately. Configuring an action through the endpoint
requires `ReadIntegration` on the integration named, on create and on update, and an
edit that resends neither the integration nor a new one keeps the one it already has
rather than becoming a way to drive a credential the editor may not read. Copying is
checked the same way wherever a person asks for it: duplicating a field, changing a
field type, duplicating a table and duplicating an application all carry the requesting
user, and a copy drops an integration that user cannot read. An import from a file and
a template install carry no such actor and keep what they came with. Snapshot create and
restore also carry none, deliberately: dropping a bot during a restore would quietly
unconfigure a restored application.

The ownership step above stays open. Until it lands, sharing is application-level as in
the builder, and the Slack integration type carries a warning saying so at the moment a
token is entered: anyone who can build in the application can send through the bot, and
can read its token, since the integrations endpoint serializes it in the clear as it
does for every other type. Masking it on read is worth doing and is not scoped here.
That warning comes out once ownership or private integrations land.

Clicks stay non-undoable (section 8), and that takes one deliberate step: dispatch
performs the row actions without registering them in the clicker's undo session, while
still firing the `action_done` signal that row history and the audit log listen to.
Without that step the clicker's session id, which arrives on every authenticated
request, would put every click in their undo stack.

```mermaid
flowchart LR
    subgraph app ["Database application"]
        BF["Button field"] -->|ordered 1..n| WA["Workflow actions"]
        WA -->|each backs onto| S["Service<br/>(integration: none in v1)"]
    end
    U["Clicking user"] -->|actor on the<br/>dispatch context| S
    S -->|permission checks, row history,<br/>created-by as the actor| T["Target tables and rows"]
```

Configuration keeps the existing field boundary: creating a button field and editing its
actions follow field update permissions, so the builder role and above. The action
editor offers the tables the configuring user can reach, and the same check happens
again at click time as the clicker, so a configuration made by someone with broader
access cannot give anyone extra access.

### 6. Import, export, duplication, and sharing

Table and field ids inside service configurations and previous-action references remap
through the standard `id_mapping` on import, as builder services already do. The hard
case is ordering: a service inside a database can point at tables of that same database,
which do not exist yet mid-import. The builder has the same problem with formulas and
solves it with a second pass; that machinery is builder-internal, so the database
follows the same pattern inside its own deferred import machinery: import all objects
first, defer every service and formula reference without checking whether it could
already resolve (some references live inside formulas, so checking up front is
unreliable anyway), then resolve them all once the import completes.

The second pass is flat and needs no dependency ordering. Everything a button's actions
reference is a table, field, or view, and all of those exist after the first pass. No
button needs anything produced by another button: buttons store no cell value, actions
cannot write to them, and previous-action references stay inside one field's own ordered
list. An action type that breaks this rule must change this document first.

```mermaid
flowchart TD
    A["Import all application objects"] --> B["Defer every service and<br/>formula reference"]
    B --> C["Import completes"]
    C --> D["Second pass resolves all<br/>deferred references"]
    D --> E["after_import hooks run;<br/>unconfigured external integrations<br/>surface as reconfigure states"]
```

An export strips an integration's credentials, so an imported Slack bot arrives named
and unusable, its token an empty string. The action reports that the way it reports any
other missing piece, so the editor says so before the click rather than after an
outbound request that was never going to work, and the bot can be repaired in place:
the integration dropdown opens the same modal in edit mode for the one selected. This
reuses the error state the builder already shows for misconfigured actions rather than
inventing a database-specific one.

**Constraint discovered in implementation, since resolved.** Actions are serialized from
`FieldType.export_serialized`, which at first received only the field: no `files_zip`, no
`storage`, and no `import_export_config`, so the action export path could not apply
`exclude_sensitive_data`. Phase 4a widened it to the same arguments the builder's export
path receives. Phase 4c added the database's integrations to the application export,
imported before its tables so an action's `integration_id` remaps through `id_mapping`;
an integration outside the field's own database, or of a type the action does not allow,
is dropped on import and the action shows as unconfigured.

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

The editor role is the click permission for every action, and for the row actions, the
HTTP request, the email and the Slack message that is the whole story: a click does what
that editor could have done by hand. The start workflow action of phase 4d is the one
place where it buys more. Running or even reading an automation workflow needs the builder
role, so an editor who clicks a button that starts one causes work they have no permission
to start themselves, performed as the workflow's own integration users, in databases they
may not be able to open — and with no way to see the workflow or its history afterwards.
The bound is on who may configure the action, not on who may click it: choosing the
workflow needs the field-update permission, so the builder role, and the workflow must
belong to the button field's own workspace (section 5). A per-field click permission is
the natural place to narrow this further when it is wanted.

### 8. Behavior under common operations

- **Field duplication.** Actions and services are duplicated with the field.
- **Application duplication, snapshot, export/import.** Deferred resolution reconnects
  self-references. A database's integrations travel with it, imported before its tables
  so an action's `integration_id` remaps. An export strips their credentials, and the
  action reports the missing one (section 6). A copy a person asked for drops an
  integration that person cannot read (section 5).
- **Trash and restore.** Actions and services follow the field, as builder actions
  follow their element. Deleting a single action trashes it with its service, so it
  can be restored; the service is deleted when the trash is emptied. A field changing
  away from a button takes its trashed actions' trash entries with it.
- **Deleting or trashing a target table or field.** Services keep the dangling reference
  and the button enters the reconfigure state rather than failing only at click time;
  restoring from trash heals it without reconfiguration.
- **Field type conversion.** Converting away deletes actions and services, and undoing
  the conversion recreates them from the copy the field update logged (see Undo/redo);
  converting into a button starts empty.
- **Undo/redo.** Clicks are never undoable, even when a sequence only touches rows: a
  partially undoable button is more confusing than none. Configuring the actions is:
  creating, updating, reordering and deleting each register an undoable action in the
  table scope, and the editor sends a save's field update and action calls under one
  action group, so one undo takes back the whole save. An undo takes back at most
  `MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP` (20) steps of a group, newest first, so a save
  that would register more is sent without a group and each step undoes on its own.
  An update logs the action's values without the fields its service type declares in
  `sensitive_fields`, since the log is copied into the audit log. That is decided per
  service type: HTTP leaves out headers, query parameters, form data and body; email
  leaves out sender, recipients, subject and body; Slack declares none, so its channel
  and text are logged as they are, while its token stays on the integration. Undo
  leaves the left-out fields as they are, so a save that changes both kinds is only
  partly reverted: changing an HTTP action's URL and its headers, then undoing, puts
  the old URL back with the new headers. An edit to only left-out fields adds no undo
  step. A type change keeps the service it replaces instead of deleting it, so undo
  and redo attach the service each side had, sensitive fields included, after checking
  the user may still use its integration or workflow; the kept service is deleted when
  the undo step is cleaned up. Undoing a delete restores the action and the order the
  field had before it. A field changing away from a button logs its actions without
  sensitive values, so undoing that brings them back with those fields blank: an email
  action comes back with no sender, recipients, subject or body.
- **Audit log.** A click registers one `dispatch_button_field` action after every
  permission check has passed and before the first action runs, inside the lock when
  there is one, so a click refused for permission or as already running leaves no entry
  and a click that fails half way still does. A button with no actions returns before
  registering anything, so its clicks leave no entry. A button with only client actions
  takes no lock, so a double click on it is two entries. Clicks stay out of the undo
  stack.
- **Deleting a user.** Nothing breaks: actions run as whoever clicks, and v1 services
  have no integration, so no button depends on any particular account.
- **Failure mid-sequence.** Execution stops, later actions are skipped, completed
  actions stay, and the user sees an error toast (section 3).

## Options considered for the model layer

### Option 1: `DatabaseWorkflowAction` mirroring the builder (chosen)

Database-scoped subclass of the core base, mirroring `contrib/builder/workflow_actions`,
preceded by the automation convergence PR.

- Pro: a proven pattern that fits the button exactly; no cross-team refactor; database
  depends only on core.
- Con: a third thin glue layer to maintain (registrations and empty shells around shared
  services, no real logic duplicated); execution consolidation is deferred, not solved.

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

- The button field ships without waiting on a cross-team refactor; the only upstream
  dependencies are the `actor` property on the dispatch context and making the
  integration unnecessary for database services (section 5). The core side is mostly in
  place already (the service's integration foreign key is nullable and a
  `requires_integration` hook exists); the real work is the actor fallback in the Local
  Baserow service types, a handful of dispatch paths shared with the builder and
  automation and reviewed with those teams. The automation inheritance change lands in
  parallel and blocks nothing.
- v1 needs no integrations at all, since local row actions run as the actor; external
  action types bring their own integrations later. Import/export of self-referencing
  services remains the main schedule risk; the settings UI, credential handling, and
  reconfigure states move entirely to the version that adds external action types.
- Actions are authorized and attributed as the clicking user, so permissions, row
  history, and created-by fields are always right, with no on-behalf-of machinery.
- Until a merge is justified, three similar thin layers exist side by side; the shared
  base classes keep them cheap to unify.

## Revisit triggers

- A fourth consumer appears, or buttons need branching/routers: extract the shared
  execution abstraction (Option 3) instead of copying a fourth time.
- Buttons reach public views: anonymous clicks would need an explicit opt-in that
  attaches a Local Baserow integration to the action, reopening on-behalf-of execution
  with the integration's user.
- External integration types are scheduled: ship them with explicit sharing warnings on
  every integration, and plan the ownership iteration (`created_by` plus `is_shared`,
  private by default) with the builder team (section 5).
- A second frontend-only button action is prioritized: `open_url` shipped with a
  client-side dispatch mechanism of its own (section 2), so the next one is the moment to
  design a shared one with the builder team rather than copy it a third time.
