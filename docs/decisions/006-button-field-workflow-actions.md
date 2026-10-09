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
ones before it. The database module follows the builder's workflow action design,
and runs every action as the user who clicks.

## Context

The application builder and automation already run configured, service-backed actions.
The builder builds on a shared core base for workflow actions; automation does not,
though nothing prevents it. In both, actions run as the user who set up the integration,
which in a database would attribute a click to whoever configured the field. A database
service can also reference tables of its own database, which ordinary import ordering
does not handle.

| Term                | Meaning                                                              |
| ------------------- | -------------------------------------------------------------------- |
| Clicker             | The logged-in user who clicks the button.                            |
| Server-side action  | An action backed by a service the builder or automation already has. |
| External action     | A server-side action that reaches outside this Baserow installation. |
| Browser-only action | An action the browser runs, such as opening a URL.                   |
| Integration         | Stored credentials an action can use, such as a Slack bot token.     |

Out of scope: retries, on-error actions, a per-click run history, per-field click
permissions and integration ownership.

## Decision

### 1. Model layer

The database module mirrors the builder's workflow actions on the shared core base, and
automation moves onto the same base separately. Only server-side actions carry a
service, so browser-only actions can be added without a schema change. Keeping the
three modules the same shape keeps a later merge cheap.

### 2. Action types

An action changes rows, starts an automation workflow, calls something outside Baserow
(such as an HTTP request, an email or a Slack message), or runs in the browser (such as
opening a URL). Server-side actions reuse the services the builder and automation
already have. A click with an external action runs as a background job the browser
waits on, so a slow call never holds a web request, and these clicks are rate limited.
Browser-only actions run after the server-side ones finish, so a failure stops them.

### 3. Execution

The server runs a click's whole sequence in one go, unlike the builder, where the
browser drives each step. Results of earlier actions come only from the server and
last only for that click.

Actions run in order and stop at the first failure, which the clicker sees. An external
call that answers with an error counts as a failure, unlike in the builder. Completed
actions are not rolled back, since some cannot be undone. A button cannot run twice at
once for the same row. Each action sees the row as the actions before it left it, and
row changes trigger the same side effects as a manual edit.

### 4. Who actions run as

Actions run as the clicker, so permissions, row history and the audit log all show the
person who clicked. A button only shortcuts what the clicker could already do, so a click
fails rather than skipping a field the clicker cannot write. External actions may use an
integration for their credentials, but never one that would change who the action runs
as. Integrations a button uses are stored on its own database and travel with it when
it is copied or exported.

Starting a workflow is the exception: the workflow runs as its own integrations' users.
This is bounded by requiring whoever configures the button to have access to the
workflow, and the workflow to be in the same workspace. Starting a workflow only
queues it: the click succeeds even if the run later fails or is refused, and an editor
may not be able to open the workflow to see what it did. The run records who clicked.

Configuring a button follows field update permissions. Clicking needs the editor role
and a logged-in user; API tokens and public views cannot click.

### 5. Import and common operations

Actions are copied, trashed and restored with their field. References to the
database's own tables are resolved after the whole import. Credentials are stripped on
export, so imported actions ask to be reconfigured. A button whose target is trashed or
incomplete is disabled until fixed. Clicks are not undoable, since a partly undoable
click is more confusing than none; configuration changes are. Secrets never reach the
undo or audit log, so undo does not restore them.

## Options considered

| Option                                     | Why not                                                          |
| ------------------------------------------ | ---------------------------------------------------------------- |
| Model actions as automation nodes          | Built for graphs, not ordered lists; no browser-only actions.    |
| Build a shared action-sequence model first | Large cross-team refactor that blocks the feature.               |
| Run actions as the integration's user      | Wrong person in row history; widens what a field editor reaches. |
| Run browser-only actions in list order     | Would need several server calls per click.                       |
| Run a started workflow as the clicker      | Workflows would behave differently for each person.              |

## Consequences

- Row history always shows the clicker, except for what a started workflow does.
- Anyone who can configure buttons in a database can use every integration stored on
  it, until integrations get owners.
- Three similar layers exist until merging them is justified.

## Revisit triggers

- A fourth module needs action sequences, or buttons need branching.
- Buttons are wanted in public views.
- Integration ownership is scheduled.
