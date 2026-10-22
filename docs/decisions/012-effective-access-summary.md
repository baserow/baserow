# ADR 012: The share dialog counts effective access, resolved by the backend

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-22                                     |
| Issue        | https://github.com/baserow/baserow/issues/6012 |
| Author       | Peter Evans (@picklepete)                      |
| Contributors |                                                |

## Summary

The "Also has access (inherited)" section of the share dialog of a database, table or
view counted every member by their stored workspace role. It counted people twice and
counted people who can't open the object at all. From now on the backend resolves the
role every member and agent effectively holds on the object, with the code the
permission checks use, and the dialog counts each of them once, under the level their
role comes from.

## Context

The share dialog of an object lists the members, teams and agents with a role on the
object itself ("direct access"), followed by a summary of who else reaches it through a
level above. The summary was computed in the browser from the workspace members in the
store, which overstated access:

- A member with a direct role on the object was listed as direct access and counted
  again under their workspace role.
- A member blocked on a level above, for example given "No access" on the database
  above a table, can't open the table but was counted under their workspace role.
- "No role" members who take their role from a team, and agents, weren't counted at all.

Getting this right in the browser means repeating the resolution rules there: the most
specific scope wins, a member's own role wins over their teams' roles on the same scope,
roles of several teams add up, "No role" defers to the teams, and the admin precedence of
[ADR 010](010-admin-role-precedence.md). Two copies of those rules would drift.

| Term              | Meaning                                                                                                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------- |
| Effective role    | The role a member or agent holds on an object once every rule above is applied.                               |
| Source level      | The scope the effective role comes from: the object itself, or the workspace, database or table above it.     |
| Navigation access | The read only access to a database or table that a role on something inside it gives, to be able to reach it. |

## Decision

### 1. One endpoint resolves effective access with the permission code

`GET /api/role/<workspace_id>/effective-access/?scope_type&scope_id` returns, for every
user and agent with access to the scope, their effective role, the source level, and
whether they hold it themselves or through teams. It is built on
`get_roles_per_scope_for_actors`, the function the permission checks use, so the
summary and the permissions can't disagree. It needs the same permission as listing the
scope's role assignments and costs a constant number of queries, whatever the size of
the workspace. The workspace is a valid scope, so the members page can show effective
workspace roles from the same endpoint (#6374).

### 2. Each member or agent is counted once, under their source level

The dialog shows one row per level above the object that someone reaches it through:
the workspace, the database for a table or view, and the table for a view. A member or
agent is counted under their source level only. Whoever has their source level on the
object itself is direct access, either listed themselves or reached through a team
listed there, and anyone listed as direct access isn't counted, even when their own row
has no effect because they are an admin above. Whoever resolves to "No access",
including being blocked on a level above, isn't counted anywhere.

### 3. Navigation access doesn't count as access

A member whose only role is on a table or view inside a database can see the database in
the sidebar but none of its content. They aren't counted in the database's dialog, and
likewise for a table they only reach a view of. Their access is shown in the dialog of
the object they hold the role on.

### 4. People are counted, teams are named

The rows count members and agents per role, with agents counted apart ("1 Editor
agent"): an agent acts with its access, but isn't a person or a billed seat. Teams aren't
counted: a team's members are already counted, a team's role doesn't always apply to all
of its members, and an empty team grants nothing. A team appears as a row only where it
holds a role on the object itself, as direct access.

### 5. Who may manage an object's roles sees who reaches it, and from which level

Anyone allowed to read the roles of an object gets the effective access of everyone on
it, including the level it comes from, even when they can't read the roles of that level.
An admin of a table who isn't an admin of its database therefore learns that a member
reaches the table through a role on the database, and can infer that a member missing
from the response, despite a workspace role, is blocked on the database. Any accurate
answer to "who can reach this object" reveals such a block, and the admin needs to know
where access comes from to change it, for instance to override the block with a role on
the table.

The teams a role comes through are named only when the requesting user may list the
members of that team. Otherwise the response still tells that the role comes through
teams. An admin of one database who isn't an editor of the workspace sees the counts
and who has access, but not which teams people belong to.

### 6. The dialog shows counts, per-person details are a follow-up

The response is per person, but the dialog only shows the counts per role, as in the
design. A list of the people in a row, with the team their role comes through, can be
added on top of the same response later.

## Options considered

| Option                                                   | Why not                                                                                                                    |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Fix the counts in the browser                            | Repeats the resolution rules client side, needs every role assignment of every level and team membership, and would drift. |
| Grouped count queries per level on the backend           | Same problem on the backend: a second implementation of the resolution rules next to the one the permission checks use.    |
| Count navigation access in the inherited rows            | Overstates access: the database's content isn't reachable, and the access doesn't come from above.                         |
| Show navigation access in a separate "inside" section    | Honest, but not in the design and needs a scan of every scope below the object. Can be added if asked for.                 |
| Count teams next to people                               | Counts the same people twice and counts empty teams, while a team's role may not apply to its members.                     |
| Fold agents into the role counts                         | Hides that an automated actor has access, and blurs the counts with billed seats.                                          |
| Say "a level above" to who can't read that level's roles | Loses the breakdown per level the admin needs, adds a second response shape, and still reveals blocks above by omission.   |
| Return only counts to who can't read the parent's roles  | Two response shapes for one endpoint, and the counts still reveal blocks above when they don't add up.                     |

## Consequences

- The counts are exact: summed with the direct access list, everyone with access to the
  object appears once.
- Opening the dialog makes one more request, which resolves every member and agent of
  the workspace. It is a constant number of queries, and the response grows with the
  number of members with access, about 150 bytes each.
- A row of a level above links to that level's share dialog, opened on top, when its
  roles may be read; the summary refreshes when it closes.
- "No access" now asks for confirmation, in the picker and on a row.
- Follow-up work: a per-person list in the rows, #6374 on the same endpoint, and #6014,
  which lists each subject's role assignments on the members, teams and agents pages.

## Revisit triggers

- Workspaces large enough for the per-person response to slow the dialog down.
- A request to see who can reach an object only to navigate to something inside it.
