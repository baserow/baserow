# ADR 010: Admin roles can't be lowered within their scope

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-13                                     |
| Issue        | https://github.com/baserow/baserow/issues/1532 |
| Author       | Peter Evans (@picklepete)                      |
| Contributors | Davide Silvestri (@silvestrid)                 |

## Summary

A role given to an admin on a database, table or view could lower their access on it,
down to "No access", and admins locked themselves and each other out by accident. From
now on an admin of the workspace keeps the admin role on everything in it, an admin of an
object keeps it on everything inside that object, and nobody can change their own role
through the API. An Admin from a team counts like a direct one at every level, the
workspace included. This reverses the decision recorded in
[#1474](https://github.com/baserow/baserow/issues/1474) in December 2022. The record
documents how roles resolve in production today and the hierarchy we are moving to.

## Context

RBAC shipped in October 2022 with roles held per scope: the workspace, an application, a
table or a view. The rules as they run in production are written out in the next
subsection.

In November 2022, [#1474](https://github.com/baserow/baserow/issues/1474) proposed that
database and table admins should be admins of everything beneath them, as workspace
admins were at the time. After discussion the team dropped the concept entirely, workspace
admins included: teams made it hard to explain, it complicated the resolution code, it
avoided UX work in the role modals, and it allowed tables that are private from admins.
The ordering endpoints, which need the full list of ids, were to be served by sending
admins placeholders for the tables they couldn't see. That placeholder idea was the
original [#1532](https://github.com/baserow/baserow/issues/1532).

In practice the symmetry hurt. The role picker preselects the last role in its list,
which is "No access", so adding a team or a colleague without touching the dropdown locks
them out. [#4345](https://github.com/baserow/baserow/issues/4345) recorded in November
2025 that users and staff had locked themselves out this way; it was later folded into
[#6012](https://github.com/baserow/baserow/issues/6012). An admin locked out of a
database can't see it, can't open its role modal and can't undo the assignment. In 2026
#1532 was rewritten to the rules in the Decision, and a maintainer comment extended them
to admins at every level.

In scope: how roles resolve for admins, what the role modals show for them, and who can
change whose role. Out of scope: the picker's default role and the confirmation before
"No access" (#6012), the access summary of a scope (#6012), and privacy inside a table,
which field permissions and personal views keep providing.

| Term             | Meaning                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| Scope            | The workspace, an application, a table or a view; a role is held on exactly one of them.          |
| Level            | The position of a scope in the hierarchy: workspace, then application, then table, then view.     |
| Admin precedence | The rule that an admin role at a scope can't be lowered at that scope or inside it.               |
| Inert assignment | A stored role assignment the precedence rule ignores. It stays in the database and has no effect. |
| Self assignment  | A request in which the user changing a role is also the subject of that role.                     |

### How roles resolve in production today

This describes `develop` at c5c5650eda, before this change, which is what production
runs.

**Where a role is held.** A member's workspace role is a field on their membership
record and an agent's is a field on the agent. Every other role is a role assignment row:
one subject, one scope, one role. The subject is a user, an agent or a team. Users and
agents hold assignments on applications, tables and views; teams also hold them on the
workspace itself. The UI offers Admin and Builder on the workspace, applications and
tables, Editor, Commenter, Viewer and No access on those and on views, and "No role" on
the workspace only, to users only. Below an application only a database has scopes of
its own, its tables and views; automations, application builders and dashboards have
none.

**At the workspace.** A member's own workspace role is canonical. A team's role on the
workspace is ignored for a member whose own role is anything but "No role", so an Editor
whose team is Admin of the workspace is an Editor. A "No role" member takes the roles of
their teams on the workspace, merged, and is No access without one. Someone who isn't a
member resolves to No access everywhere in the workspace.

**On one scope below the workspace.** Subject types have a priority: user first, then
agent, then team. On a scope, the rows of the highest priority subject type present
define the role and rows of the other subject types are ignored, whatever role they
carry. A direct Viewer on a table beats a team Admin on it, and a direct Admin beats a
team Viewer. Rows of equal priority, a member of two teams that both hold a role on the
scope, are merged: every operation held by either role is allowed.

**Across scopes.** The resolved roles are ordered from the workspace down to the most
specific scope. For a given object, every scope that contains it replaces the roles found
so far, so the most specific scope wins outright: No access on a table replaces Admin on
its database, and Admin on a table replaces No access on its database. When the object
itself contains a scope with a role other than No access, a hidden read-only role is
added so the member can open the object and reach what is inside: an Editor on one table
of a database they have No access to can open that database and sees that table only.

**Admins are not special.** A row placed by a team or by another admin applies to an
admin exactly as it applies to anyone else, at every level. The role modal renders the
member's own row read-only and leaves them out of its picker, so a member can't lower
their own role on a scope through the UI, but a team they belong to, another admin or a
direct API call can. The workspace user endpoint accepts a member lowering their own
workspace role as long as another admin remains.

Every case in the table below is reachable in production. A direct row on an admin is
placed by another admin from the role modal, whose picker offers every other member, or
through the role assignment endpoints, which have no guard. A team row is placed by
adding a team the admin belongs to. The result is the same for a direct row and a team
row unless the table says otherwise.

| Workspace role      | Application role | Table role                    | Resolved on the table | Why                                                               |
| ------------------- | ---------------- | ----------------------------- | --------------------- | ----------------------------------------------------------------- |
| Admin               | No access        |                               | No access             | The most specific scope wins; the admin can't open the database.  |
| Admin               |                  | Viewer, via a team            | Viewer                | The team's row on the table replaces the workspace role.          |
| Editor              | Admin            | No access                     | No access             | The most specific scope wins.                                     |
| Editor              | Viewer           | Commenter                     | Commenter             | The most specific scope wins.                                     |
| No role, team Admin |                  |                               | Admin                 | A "No role" member takes their teams' workspace roles.            |
| Editor, team Admin  |                  |                               | Editor                | The member's own workspace role beats their team's Admin on it.   |
| Viewer              |                  | Admin direct, Viewer via team | Admin                 | On one scope the user's row beats the team's.                     |
| Viewer              |                  | Viewer direct, Admin via team | Viewer                | On one scope the user's row beats the team's.                     |
| No access           |                  | Editor                        | Editor                | The database becomes read-only so the member can reach the table. |

## Decision

### The target hierarchy

Agreed on 2026-10-14. Three rules, applied from the top down:

1. **A workspace Admin sees and does everything in the workspace.** This is a subset of
   the admins: only those whose workspace role is Admin, stored on their membership or
   given by a team. An Admin on an application or a table isn't a workspace admin.
2. **An Admin on an application sees and does everything on it and inside it.** An
   application is a database, an automation, an application builder or a dashboard. An
   Admin on a database is an Admin on every table and view in it, whatever rows exist
   on them: the parent rule means the children are ignored. The same holds one level
   down, for an Admin on a table and its views.
3. **Without an Admin above, the most specific role assignment decides.** Whether
   permission X is granted on table Y is answered by the role held on table Y, as today.

| Workspace role | Application role | Table role | Result    | Why                                       |
| -------------- | ---------------- | ---------- | --------- | ----------------------------------------- |
| Admin          | No access        |            | Admin     | They can see it anyway.                   |
| Editor         | Admin            | No access  | Admin     | They are an Admin on the parent.          |
| Editor         | Viewer           | Commenter  | Commenter | They can comment; the most precise scope. |

The nine cases of the production table, resolved under these rules. Five change, the
other four resolve as they do today:

| Workspace role      | Application role | Table role                    | Resolved on the table | Why    | Previously |
| ------------------- | ---------------- | ----------------------------- | --------------------- | ------ | ---------- |
| Admin               | No access        |                               | Admin                 | Rule 1 | No access  |
| Admin               |                  | Viewer, via a team            | Admin                 | Rule 1 | Viewer     |
| Editor              | Admin            | No access                     | Admin                 | Rule 2 | No access  |
| Editor              | Viewer           | Commenter                     | Commenter             | Rule 3 | Commenter  |
| No role, team Admin |                  |                               | Admin                 | Rule 1 | Admin      |
| Editor, team Admin  |                  |                               | Admin                 | Rule 1 | Editor     |
| Viewer              |                  | Admin direct, Viewer via team | Admin                 | Rule 2 | Admin      |
| Viewer              |                  | Viewer direct, Admin via team | Admin                 | Rule 2 | Viewer     |
| No access           |                  | Editor                        | Editor                | Rule 3 | Editor     |

Two points the rules leave open, and how this record settles them:

- **An Admin through a team and a lesser direct role at the same level.** The Admin
  wins, at every level, the workspace included. A member whose stored workspace role is
  Editor and whose team is Admin of the workspace is a workspace Admin; a member with a
  direct Viewer on a table whose team is Admin of that table is an Admin of it.
  Production resolves both to the lesser role, because the stored workspace role and the
  user's row win. This record resolves both to Admin, so that nobody can lower an Admin
  at the level they are an Admin of, which is what the maintainer comment on #1532 asks
  for. Between non-admin roles the subject priority keeps deciding: a stored Viewer whose
  team is Editor at the workspace stays a Viewer, and "No role" members keep taking their
  teams' roles.
- **Views.** The UI doesn't offer Admin on a view. The backend applies rule 2 to every
  scope regardless, so a view Admin assigned through the API behaves the same way.

Rule 3 is production behaviour and doesn't change: the subject priority and the hidden
read-only role on ancestors keep applying wherever no Admin is held above.

### 1. An admin of the workspace is an admin everywhere in it

Whether the role is stored on the membership record or on the agent, or comes from any
team that holds Admin on the workspace, every role on a lower scope is ignored for that
actor, directly assigned or through a team. To restrict a workspace admin, their stored
role has to be lowered and every team Admin they hold on the workspace removed. This is
rule 1.

### 2. An admin of an object keeps it on the object and everything inside it

An admin of an application, table or view keeps the admin role on that scope and on all
its descendants. Lower roles on the same scope from any subject type, and any role on a
descendant scope, are ignored. This is rule 2. The same-scope part holds at the
workspace too: an Admin from a team is never lowered by a stored or direct role at any
level. A team's non-admin role on the workspace still applies only to "No role" members.

### 3. The rules live in role resolution, once

`RoleAssignmentHandler.apply_admin_precedence` rewrites the ordered per scope role list
when it is built, so permission checks, the permissions object sent to the frontend,
queryset filtering and the field permissions manager all see the same result. The role
permission manager additionally builds the permissions object and the queryset filters
of workspace admins from the Admin role's own operation set, so an operation the role
doesn't hold, for instance one not yet synced into a long lived instance, stays denied.
Permission checks keep walking the scope list: that walk is what denies a context from
another workspace, so no admin shortcut may skip it.

### 4. Existing assignments are kept and become inert

No data migration. An assignment the rules ignore stays stored, so demoting the admin
later makes it effective again, and nothing has to tell an accidental assignment from a
deliberate one. The role modals show such subjects with a locked Admin role and an
explanation naming the level that makes them an admin, offer removal only, and don't
offer them in the picker.

### 5. Nobody can change their own role through the API

Both the workspace user endpoint and the role assignment endpoints reject a self
assignment at every scope, workspace included. The UI already rendered the user's own row
read-only; the API now matches it. Another admin has to change an admin's role, and the
last admin check still applies to leaving a workspace.

### 6. Lower roles on admins are accepted and ignored, not rejected

A direct "No access" on a workspace admin is stored like any other assignment and has no
effect. Rejecting it would give one rule two behaviours, since a team assignment can't be
rejected for the admins it happens to contain, and the UI never sends it.

## Options considered

| Option                                                       | Why not                                                                                                                                    |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Keep the 2022 rule and send admins placeholders              | Admins stay locked out of their own objects; placeholders only solve ordering.                                                             |
| Prevent it in the UI only                                    | Teams, other admins and the API still lock admins out, and the existing assignments stay effective.                                        |
| Delete the stale assignments in a migration                  | Loses the intent behind them, can't tell accidental from deliberate, and demotion wouldn't restore them.                                   |
| Reject direct lower roles on admins at the API               | Can't apply to teams, so the same rule would behave two ways. The unused `ERROR_CANT_ASSIGN_ROLE_EXCEPTION_TO_ADMIN` dates from this idea. |
| Keep subject priority on the same scope below the workspace  | A direct Editor would beat a team Admin on a table, contradicting "cannot be given a lower role on that same object".                      |
| Keep the stored workspace role canonical over a team's Admin | The only level at which an Admin could still be lowered. One rule at every level is easier to explain and matches the rule below it.       |
| Make instance staff a workspace bypass                       | A different concern. `is_staff` only unlocks instance settings and must keep doing only that.                                              |

## Consequences

- Nothing in a workspace can be hidden from its admins, and nothing inside an object from
  that object's admin. Privacy inside a table stays with field permissions and personal
  views. To restrict an admin, lower their role at the level that makes them an admin.
- The last admin can't step down. A second admin has to be promoted first.
- A member who is admin of the workspace or of an object only through a team isn't
  locked in the role modal, because team membership isn't known client side. The backend
  ignores their lower roles regardless.
- The members page shows the stored workspace role, so lowering it has no visible effect
  while a team the member belongs to holds Admin on the workspace. The last admin check
  counts stored Admins only. Both need to learn about team derived workspace admins.
- The ordering endpoints work for admins without placeholders, which was #1474's first
  motivation.
- Follow-up work: #6012 (picker defaults to Viewer, confirmation before "No access",
  access summary of a scope) and the share dialog of #6013, which replaces the role modal
  and has to apply the same locks.

## Revisit triggers

- A real need for an application, table or view that its admins can't see.
- Team membership becoming available client side, so team derived admins can be locked
  in the UI too.
