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
ones before it. The database module reuses the workflow action model the builder already
has, and runs every action as the user who clicks.

## Context

The application builder and automation already run configured, service-backed actions.
The builder builds on a shared core base for workflow actions; automation does not, for
no technical reason. In both, actions run as the user who set up the integration, which
in a database would attribute a click to whoever configured the field. A database
service can also reference tables of its own database, which ordinary import ordering
does not handle.

## Decision

### 1. Model layer

The database module mirrors the builder's workflow actions on the shared core base, and
automation moves onto the same base separately. Keeping the three modules the same shape
keeps a later merge cheap.

### 2. Action types

A button can create, update or delete rows, start an automation workflow, send an HTTP
request, an email or a Slack message, and open a URL. Service-backed actions reuse the
services the builder and automation already have. Actions that reach outside the
installation run in the background and are rate limited. Browser-only actions, such as
opening a URL, run after the server-side actions finish, so a failure stops them.

### 3. Execution

Actions run in order and stop at the first failure, which the clicker sees. Completed
actions are not rolled back, since some cannot be undone. A button cannot run twice at
once for the same row. Each action sees the row as the actions before it left it, and
row changes trigger the same side effects as a manual edit.

### 4. Who actions run as

Actions run as the clicker, so permissions, row history and the audit log all show the
person who clicked. A button only shortcuts what the clicker could already do, so a click
fails rather than skipping a field the clicker cannot write. External actions may use an
integration for their credentials, but never one that would change who the action runs
as.

Starting a workflow is the exception: the workflow runs as its own integrations' users.
This is bounded by requiring whoever configures the button to have access to the
workflow, and the workflow to be in the same workspace.

Configuring a button follows field update permissions. Clicking needs the editor role
and a logged-in user; API tokens and public views cannot click.

### 5. Import and common operations

References to the database's own tables are resolved after the whole import. Credentials
are stripped on export, so imported actions ask to be reconfigured. A button whose
target is trashed or incomplete is disabled until fixed. Clicks are not undoable;
configuration changes are.

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
- Integrations are shared across an application until they get owners.
- Three similar layers exist until merging them is justified.

## Revisit triggers

- A fourth module needs action sequences, or buttons need branching.
- Buttons are wanted in public views.
- Integration ownership is scheduled.
