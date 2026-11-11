# ADR 010: Admin roles can't be lowered within their scope

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-13                                     |
| Issue        | https://github.com/baserow/baserow/issues/1532 |
| Author       | Peter Evans (@picklepete)                      |
| Contributors | Davide Silvestri (@silvestrid)                 |

## Summary

A role given to an admin on a database, table or view lowers their access on it, down to
"No access", and admins have locked themselves and each other out by accident. From now
on the Admin role a member holds themselves can't be lowered at the level they hold it
or anywhere below it: a workspace Admin keeps full access to the whole workspace, and an
Admin of a database to everything in it. A role held through a team never gives that,
and nobody can change their own role through the API.

## Context

Enterprise RBAC resolves a member's role per scope: the workspace, an application, a
table or a view. A member's workspace role is stored on their membership and an agent's
on the agent; every other role is a role assignment of a user, an agent or a team on one
scope. On one scope the member's own role wins over the roles of their teams, and the
stored workspace role wins over a team's role on the workspace unless it is "No role".
Across scopes the most specific one wins, and the Admin role gets no special treatment:
"No access" on a table replaces Admin on its database, for a workspace admin as for
anyone else.

That symmetry was a deliberate choice when RBAC shipped in 2022
([#1474](https://github.com/baserow/baserow/issues/1474)). In practice it hurts. The
role picker preselects "No access", so adding a colleague or a team to a table without
touching the dropdown locks them out, admins included
([#4345](https://github.com/baserow/baserow/issues/4345), folded into
[#6012](https://github.com/baserow/baserow/issues/6012)). An admin locked out of a
database can't see it, can't open its share dialog and can't undo the assignment.

In scope: how roles resolve for admins, what the share dialog shows for them, and who can
change whose role. Out of scope: the picker's default role and the confirmation before
"No access" (#6012), the access summary of a scope (#6012), which roles a team may hold,
and privacy inside a table, which field permissions and personal views keep providing.

| Term             | Meaning                                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| Scope            | The workspace, an application, a table or a view; a role is held on exactly one of them.                          |
| Level            | The position of a scope in the hierarchy: workspace, then application, then table, then view.                     |
| Direct role      | A role the member holds themselves: their stored workspace role, or a role assignment with the member as subject. |
| Team role        | A role assignment with a team as subject. It reaches the member through their membership of the team.             |
| Admin precedence | The rule that a direct Admin role can't be lowered at the level it is held or inside it.                          |
| Inert assignment | A stored role assignment the precedence rule ignores. It stays in the database and has no effect.                 |
| Self assignment  | A request in which the user changing a role is also the subject of that role.                                     |

### Behaviour today and after this record

Two companion files list every combination of roles on the workspace, an application and
a child of it, resolved by the role handler itself: the
[role matrix before ADR 010](010-role-matrix-before.md) shows the result in production
today, and the [role matrix after ADR 010](010-role-matrix-after.md) adds the result
under this record. In short:

- Today the most specific role wins everywhere. A lower role on a database replaces a
  workspace Admin's role there, and "No access" on a table replaces Admin on its
  database.
- After this record a direct Admin role holds at its level and below. A workspace Admin
  resolves to Admin on every scope of the workspace, and an Admin of an application on
  every scope inside it. 70 of the 343 combinations of direct roles change, all of them
  to Admin.
- Roles held through a team resolve as they do today, with one exception: a team's lower
  role on a scope no longer applies under the member's own Admin role above it.
- Every other combination, Builder down to "No access", resolves exactly as today.

## Decision

### 1. A direct Admin role holds at its level and everywhere below it

An admin of the workspace, by the role stored on their membership or on the agent, is an
admin on everything in the workspace. An admin of an application, a table or a view, by
a role assignment of their own, is an admin on that scope and on everything inside it.
Any role on a descendant scope, directly assigned or through a team, is ignored for
them. To restrict such an admin, lower the Admin role that makes them one.

### 2. Roles held through a team don't make admins

A team's Admin role on an application or a table applies on that scope like any other
team role, and a role on a scope inside still wins there. On one scope the member's own
role keeps winning over the roles of their teams, whatever they are, so a direct Viewer
next to a team's Admin stays a Viewer.

A team's Admin role on the workspace keeps doing what it does today: a member or an
agent whose stored role is "No role" takes it and resolves to Admin on the workspace,
but without the precedence, so a role on a scope inside still wins for them. Whether a
team should be able to hold Admin on the workspace at all is left for a later decision.

### 3. The rules live in role resolution, once

`RoleAssignmentHandler.apply_admin_precedence` rewrites the ordered per scope role list
when it is built, given the scopes on which the actor holds Admin directly, so permission
checks, the permissions object sent to the frontend, queryset filtering and the field
permissions manager all see the same result. The role permission manager additionally
builds the permissions object and the queryset filters of a workspace admin from the
Admin role's own operation set, so an operation the role doesn't hold, for instance one
not yet synced into a long lived instance, stays denied. Permission checks keep walking
the scope list: that walk is what denies a context from another workspace, so no admin
shortcut may skip it.

### 4. Existing assignments are kept and become inert

No data migration. An assignment the rules ignore stays stored, so demoting the admin
later makes it effective again, and nothing has to tell an accidental assignment from a
deliberate one. The share dialog of an object shows such users and agents with a locked
Admin role and an explanation naming the level that makes them an admin, offers removal
only, and lists them in its picker with that reason instead of offering them.

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

| Option                                                   | Why not                                                                                                                                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Keep the most specific role and send admins placeholders | Admins stay locked out of their own objects; placeholders only solve the ordering endpoints, which was the original scope of #1532.                                      |
| Prevent it in the UI only                                | Teams, other admins and the API still lock admins out, and the existing assignments stay effective.                                                                      |
| Delete the stale assignments in a migration              | Loses the intent behind them, can't tell accidental from deliberate, and demotion wouldn't restore them.                                                                 |
| Reject direct lower roles on admins at the API           | Can't apply to teams, so the same rule would behave two ways. The unused `ERROR_CANT_ASSIGN_ROLE_EXCEPTION_TO_ADMIN` dates from this idea.                               |
| Let a team's Admin role make admins too                  | Team membership isn't known where roles are set, so such admins could neither be shown nor locked there, and a member's effective role would differ from the stored one. |
| Make instance staff a workspace bypass                   | A different concern. `is_staff` only unlocks instance settings and must keep doing only that.                                                                            |

## Consequences

- Nothing in a workspace can be hidden from its admins, and nothing inside an object from
  that object's direct admin. Privacy inside a table stays with field permissions and
  personal views. To restrict an admin, lower their role at the level that makes them an
  admin.
- The last admin can't step down. A second admin has to be promoted first.
- The share dialog locks exactly the users and agents the backend protects: the stored
  workspace roles are known client side, and the dialog fetches the role assignments of
  the parent database and table. A parent whose roles the user may not read is skipped,
  so its admins aren't marked there.
- A team's Admin on a database shows as Admin in the database's share dialog, but its
  members can still be given a lower role on a table inside. The explanation of full
  access is only shown for users and agents.
- A "No role" member whose team holds Admin on the workspace is an admin of the
  workspace without the new protection: a lower role on a database or table inside still
  locks them out, and the members page lists them as Admin under "Highest role" all the
  same. Restricting Admin for teams on the workspace is a separate decision.
- The ordering endpoints work for admins without placeholders.
- Follow-up work: #6012 (picker defaults to Viewer, confirmation before "No access",
  access summary of a scope) and #6374, which shows the effective workspace role of "No
  role" members on the members page.

## Revisit triggers

- A real need for an application, table or view that its admins can't see.
- Team membership becoming available client side, which would allow a team's Admin role
  to make admins too.
