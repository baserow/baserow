# ADR 006: How the Button Field Shares Workflow Actions Across Modules

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Accepted                                       |
| Date         | 2026-07-22                                     |
| Issue        | https://github.com/baserow/baserow/issues/1722 |
| Author       | Al Amin (@alamin-br)                           |
| Contributors | Davide (@silvestrid), Jérémie (@jrmi)          |

## Summary

The button field is a database field whose cells render a button. A click runs an
ordered list of actions against the clicked row, each able to read the results of the
ones before it. The database module mirrors the builder's workflow action model on the
shared core base and runs every action as the user who clicks.

## Context

The core base (`baserow/core/workflow_actions`) is an abstract `WorkflowAction` with a
registry and a CRUD handler, and no execution logic. The builder subclasses it.
Automation does not: `AutomationNode` holds a `OneToOneField(Service)` and runs as a
graph, for no technical reason.

Local Baserow services run as the integration's `authorized_user`, which in a database
would attribute a click to whoever configured the field. Import order across
applications does not help a service that references tables of its own database.

## Decision

### 1. Model layer

The database module mirrors `contrib/builder/workflow_actions`:
`DatabaseWorkflowAction` (button field, `order`), an abstract
`DatabaseWorkflowServiceAction` holding `service`, a type registry, and a handler and
service layer that enforce permissions. Automation adopts the core base separately.
Keeping the three modules the same shape keeps a later merge cheap.

### 2. Action types

| Type                       | Runs           | Credential                   |
| -------------------------- | -------------- | ---------------------------- |
| Create, update, delete row | In the request | None; acts as the clicker    |
| Start workflow             | In the request | None; workflow id            |
| HTTP request               | Job            | None; own headers            |
| Send email                 | Job            | Instance mail server or SMTP |
| Slack message              | Job            | `slack_bot` integration      |
| Open URL                   | Browser        | None                         |

Service-backed types reuse the builder and automation service types. Types marked
`is_external` reach outside the installation; a click containing one runs as a
`ButtonFieldDispatchJob` and spends the button rate limit.

The dispatch endpoint runs the service-backed actions and returns frontend-only ones
under `client_actions` for the browser to run afterwards. A failure therefore stops a
navigation before it happens, and the data explorer offers an action only results that
already exist.

### 3. Execution

- Execution stops at the first failing action and shows an error toast. Nothing is
  rolled back. An HTTP error status counts as a failure.
- Further clicks on the same `(field_id, row_id)` get 409 while one runs.
- Row changes fire the usual webhooks, automation triggers and realtime updates.
- The row provider reads the row again before each action. Results of earlier actions
  live in a dict on the dispatch context and never outlive the click.

### 4. Who actions run as

Actions run as the clicker, set as `actor` on the dispatch context. Permission checks,
row history, created-by fields and the audit log all see that user, and a click fails
if they cannot write a target. A button only shortcuts what the clicker could already do.

- Each action type lists accepted integrations in `allowed_integration_types`.
  `local_baserow` is never accepted, since its user would replace the clicker.
- Attaching an integration requires `ReadIntegration`, and a duplicate drops
  integrations the requesting user cannot read.
- Integrations have no owner yet, so anyone who can build in the application can use
  them. Ownership is left to a joint design with the builder team.
- Start workflow is the exception: the workflow's nodes act as their integration's user.
  This is bounded by requiring the configuring user to read the workflow and the workflow
  to be in the field's workspace. The run records the clicker in `triggered_by`.

Configuring actions needs field update permission. Clicking needs the editor role and a
user session; API tokens and public views cannot click.

### 5. Import and common operations

- References to the database's own tables are deferred and resolved in one flat second
  pass after import. This holds while no button depends on another.
- Integrations import before tables. Exports strip credentials, so imported actions show
  as needing reconfiguration.
- A trashed target or missing required value sets `requires_reconfiguration` and
  disables the button until fixed.
- Clicks are never undoable. Configuration is, one action group per save.

## Options considered

| Option                                             | Why not                                                                       |
| -------------------------------------------------- | ----------------------------------------------------------------------------- |
| Node/service model like automation                 | Tied to graph traversal; rules out frontend-only actions.                     |
| Shared action-sequence abstraction in core first   | Large cross-team refactor that blocks the feature.                            |
| Run actions as the integration's `authorized_user` | Wrong name in row history; field editors reach the integration user's tables. |
| Browser runs frontend-only actions in list order   | Needs several dispatch calls, which the per-cell lock rejects.                |
| Start workflow runs its nodes as the clicker       | Workflows would behave differently for each person.                           |

## Consequences

- Row history and created-by fields are always the clicker's, except for what a started
  workflow does.
- Integrations are shared application-wide until ownership lands.
- Three similar thin layers exist until merging them is justified.

## Revisit triggers

- A fourth module needs action sequences, or buttons need branching.
- Buttons are wanted in public views.
- Integration ownership is scheduled.
- A second frontend-only action is prioritized.
