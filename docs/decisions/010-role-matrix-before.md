# Role matrix before ADR 010

Every combination of roles a member can hold on the workspace, on an application and on
a child of that application, and the role that resolves on the child in `develop` at
c5c5650eda, which is what production runs on 2026-10-14. Each row was resolved by the
role handler itself. [ADR 010](010-admin-role-precedence.md) changes some of these
results; the [role matrix after ADR 010](010-role-matrix-after.md) shows which.

## How to read it

- The child is a table of a database. A view below a table follows the same rules one
  level down. Automations, application builders and dashboards have no scopes below the
  application.
- A role is held by the member themselves unless it is marked "(team)": then a team the
  member belongs to holds it. "–" means no role assignment on that scope.
- The workspace role is the one stored on the membership. "No role" makes the member take
  the roles of their teams on the workspace instead.
- The result is the role that applies on the child, which is what decides what the
  member can do there.
- Builder, Editor, Commenter and Viewer resolve the same way; the rows differ only in
  which of them comes out.

## Every combination of direct roles

| Workspace role | Application role | Child role | Result    |
| -------------- | ---------------- | ---------- | --------- |
| Admin          | –                | –          | Admin     |
| Admin          | –                | Admin      | Admin     |
| Admin          | –                | Builder    | Builder   |
| Admin          | –                | Editor     | Editor    |
| Admin          | –                | Commenter  | Commenter |
| Admin          | –                | Viewer     | Viewer    |
| Admin          | –                | No access  | No access |
| Admin          | Admin            | –          | Admin     |
| Admin          | Admin            | Admin      | Admin     |
| Admin          | Admin            | Builder    | Builder   |
| Admin          | Admin            | Editor     | Editor    |
| Admin          | Admin            | Commenter  | Commenter |
| Admin          | Admin            | Viewer     | Viewer    |
| Admin          | Admin            | No access  | No access |
| Admin          | Builder          | –          | Builder   |
| Admin          | Builder          | Admin      | Admin     |
| Admin          | Builder          | Builder    | Builder   |
| Admin          | Builder          | Editor     | Editor    |
| Admin          | Builder          | Commenter  | Commenter |
| Admin          | Builder          | Viewer     | Viewer    |
| Admin          | Builder          | No access  | No access |
| Admin          | Editor           | –          | Editor    |
| Admin          | Editor           | Admin      | Admin     |
| Admin          | Editor           | Builder    | Builder   |
| Admin          | Editor           | Editor     | Editor    |
| Admin          | Editor           | Commenter  | Commenter |
| Admin          | Editor           | Viewer     | Viewer    |
| Admin          | Editor           | No access  | No access |
| Admin          | Commenter        | –          | Commenter |
| Admin          | Commenter        | Admin      | Admin     |
| Admin          | Commenter        | Builder    | Builder   |
| Admin          | Commenter        | Editor     | Editor    |
| Admin          | Commenter        | Commenter  | Commenter |
| Admin          | Commenter        | Viewer     | Viewer    |
| Admin          | Commenter        | No access  | No access |
| Admin          | Viewer           | –          | Viewer    |
| Admin          | Viewer           | Admin      | Admin     |
| Admin          | Viewer           | Builder    | Builder   |
| Admin          | Viewer           | Editor     | Editor    |
| Admin          | Viewer           | Commenter  | Commenter |
| Admin          | Viewer           | Viewer     | Viewer    |
| Admin          | Viewer           | No access  | No access |
| Admin          | No access        | –          | No access |
| Admin          | No access        | Admin      | Admin     |
| Admin          | No access        | Builder    | Builder   |
| Admin          | No access        | Editor     | Editor    |
| Admin          | No access        | Commenter  | Commenter |
| Admin          | No access        | Viewer     | Viewer    |
| Admin          | No access        | No access  | No access |
| Builder        | –                | –          | Builder   |
| Builder        | –                | Admin      | Admin     |
| Builder        | –                | Builder    | Builder   |
| Builder        | –                | Editor     | Editor    |
| Builder        | –                | Commenter  | Commenter |
| Builder        | –                | Viewer     | Viewer    |
| Builder        | –                | No access  | No access |
| Builder        | Admin            | –          | Admin     |
| Builder        | Admin            | Admin      | Admin     |
| Builder        | Admin            | Builder    | Builder   |
| Builder        | Admin            | Editor     | Editor    |
| Builder        | Admin            | Commenter  | Commenter |
| Builder        | Admin            | Viewer     | Viewer    |
| Builder        | Admin            | No access  | No access |
| Builder        | Builder          | –          | Builder   |
| Builder        | Builder          | Admin      | Admin     |
| Builder        | Builder          | Builder    | Builder   |
| Builder        | Builder          | Editor     | Editor    |
| Builder        | Builder          | Commenter  | Commenter |
| Builder        | Builder          | Viewer     | Viewer    |
| Builder        | Builder          | No access  | No access |
| Builder        | Editor           | –          | Editor    |
| Builder        | Editor           | Admin      | Admin     |
| Builder        | Editor           | Builder    | Builder   |
| Builder        | Editor           | Editor     | Editor    |
| Builder        | Editor           | Commenter  | Commenter |
| Builder        | Editor           | Viewer     | Viewer    |
| Builder        | Editor           | No access  | No access |
| Builder        | Commenter        | –          | Commenter |
| Builder        | Commenter        | Admin      | Admin     |
| Builder        | Commenter        | Builder    | Builder   |
| Builder        | Commenter        | Editor     | Editor    |
| Builder        | Commenter        | Commenter  | Commenter |
| Builder        | Commenter        | Viewer     | Viewer    |
| Builder        | Commenter        | No access  | No access |
| Builder        | Viewer           | –          | Viewer    |
| Builder        | Viewer           | Admin      | Admin     |
| Builder        | Viewer           | Builder    | Builder   |
| Builder        | Viewer           | Editor     | Editor    |
| Builder        | Viewer           | Commenter  | Commenter |
| Builder        | Viewer           | Viewer     | Viewer    |
| Builder        | Viewer           | No access  | No access |
| Builder        | No access        | –          | No access |
| Builder        | No access        | Admin      | Admin     |
| Builder        | No access        | Builder    | Builder   |
| Builder        | No access        | Editor     | Editor    |
| Builder        | No access        | Commenter  | Commenter |
| Builder        | No access        | Viewer     | Viewer    |
| Builder        | No access        | No access  | No access |
| Editor         | –                | –          | Editor    |
| Editor         | –                | Admin      | Admin     |
| Editor         | –                | Builder    | Builder   |
| Editor         | –                | Editor     | Editor    |
| Editor         | –                | Commenter  | Commenter |
| Editor         | –                | Viewer     | Viewer    |
| Editor         | –                | No access  | No access |
| Editor         | Admin            | –          | Admin     |
| Editor         | Admin            | Admin      | Admin     |
| Editor         | Admin            | Builder    | Builder   |
| Editor         | Admin            | Editor     | Editor    |
| Editor         | Admin            | Commenter  | Commenter |
| Editor         | Admin            | Viewer     | Viewer    |
| Editor         | Admin            | No access  | No access |
| Editor         | Builder          | –          | Builder   |
| Editor         | Builder          | Admin      | Admin     |
| Editor         | Builder          | Builder    | Builder   |
| Editor         | Builder          | Editor     | Editor    |
| Editor         | Builder          | Commenter  | Commenter |
| Editor         | Builder          | Viewer     | Viewer    |
| Editor         | Builder          | No access  | No access |
| Editor         | Editor           | –          | Editor    |
| Editor         | Editor           | Admin      | Admin     |
| Editor         | Editor           | Builder    | Builder   |
| Editor         | Editor           | Editor     | Editor    |
| Editor         | Editor           | Commenter  | Commenter |
| Editor         | Editor           | Viewer     | Viewer    |
| Editor         | Editor           | No access  | No access |
| Editor         | Commenter        | –          | Commenter |
| Editor         | Commenter        | Admin      | Admin     |
| Editor         | Commenter        | Builder    | Builder   |
| Editor         | Commenter        | Editor     | Editor    |
| Editor         | Commenter        | Commenter  | Commenter |
| Editor         | Commenter        | Viewer     | Viewer    |
| Editor         | Commenter        | No access  | No access |
| Editor         | Viewer           | –          | Viewer    |
| Editor         | Viewer           | Admin      | Admin     |
| Editor         | Viewer           | Builder    | Builder   |
| Editor         | Viewer           | Editor     | Editor    |
| Editor         | Viewer           | Commenter  | Commenter |
| Editor         | Viewer           | Viewer     | Viewer    |
| Editor         | Viewer           | No access  | No access |
| Editor         | No access        | –          | No access |
| Editor         | No access        | Admin      | Admin     |
| Editor         | No access        | Builder    | Builder   |
| Editor         | No access        | Editor     | Editor    |
| Editor         | No access        | Commenter  | Commenter |
| Editor         | No access        | Viewer     | Viewer    |
| Editor         | No access        | No access  | No access |
| Commenter      | –                | –          | Commenter |
| Commenter      | –                | Admin      | Admin     |
| Commenter      | –                | Builder    | Builder   |
| Commenter      | –                | Editor     | Editor    |
| Commenter      | –                | Commenter  | Commenter |
| Commenter      | –                | Viewer     | Viewer    |
| Commenter      | –                | No access  | No access |
| Commenter      | Admin            | –          | Admin     |
| Commenter      | Admin            | Admin      | Admin     |
| Commenter      | Admin            | Builder    | Builder   |
| Commenter      | Admin            | Editor     | Editor    |
| Commenter      | Admin            | Commenter  | Commenter |
| Commenter      | Admin            | Viewer     | Viewer    |
| Commenter      | Admin            | No access  | No access |
| Commenter      | Builder          | –          | Builder   |
| Commenter      | Builder          | Admin      | Admin     |
| Commenter      | Builder          | Builder    | Builder   |
| Commenter      | Builder          | Editor     | Editor    |
| Commenter      | Builder          | Commenter  | Commenter |
| Commenter      | Builder          | Viewer     | Viewer    |
| Commenter      | Builder          | No access  | No access |
| Commenter      | Editor           | –          | Editor    |
| Commenter      | Editor           | Admin      | Admin     |
| Commenter      | Editor           | Builder    | Builder   |
| Commenter      | Editor           | Editor     | Editor    |
| Commenter      | Editor           | Commenter  | Commenter |
| Commenter      | Editor           | Viewer     | Viewer    |
| Commenter      | Editor           | No access  | No access |
| Commenter      | Commenter        | –          | Commenter |
| Commenter      | Commenter        | Admin      | Admin     |
| Commenter      | Commenter        | Builder    | Builder   |
| Commenter      | Commenter        | Editor     | Editor    |
| Commenter      | Commenter        | Commenter  | Commenter |
| Commenter      | Commenter        | Viewer     | Viewer    |
| Commenter      | Commenter        | No access  | No access |
| Commenter      | Viewer           | –          | Viewer    |
| Commenter      | Viewer           | Admin      | Admin     |
| Commenter      | Viewer           | Builder    | Builder   |
| Commenter      | Viewer           | Editor     | Editor    |
| Commenter      | Viewer           | Commenter  | Commenter |
| Commenter      | Viewer           | Viewer     | Viewer    |
| Commenter      | Viewer           | No access  | No access |
| Commenter      | No access        | –          | No access |
| Commenter      | No access        | Admin      | Admin     |
| Commenter      | No access        | Builder    | Builder   |
| Commenter      | No access        | Editor     | Editor    |
| Commenter      | No access        | Commenter  | Commenter |
| Commenter      | No access        | Viewer     | Viewer    |
| Commenter      | No access        | No access  | No access |
| Viewer         | –                | –          | Viewer    |
| Viewer         | –                | Admin      | Admin     |
| Viewer         | –                | Builder    | Builder   |
| Viewer         | –                | Editor     | Editor    |
| Viewer         | –                | Commenter  | Commenter |
| Viewer         | –                | Viewer     | Viewer    |
| Viewer         | –                | No access  | No access |
| Viewer         | Admin            | –          | Admin     |
| Viewer         | Admin            | Admin      | Admin     |
| Viewer         | Admin            | Builder    | Builder   |
| Viewer         | Admin            | Editor     | Editor    |
| Viewer         | Admin            | Commenter  | Commenter |
| Viewer         | Admin            | Viewer     | Viewer    |
| Viewer         | Admin            | No access  | No access |
| Viewer         | Builder          | –          | Builder   |
| Viewer         | Builder          | Admin      | Admin     |
| Viewer         | Builder          | Builder    | Builder   |
| Viewer         | Builder          | Editor     | Editor    |
| Viewer         | Builder          | Commenter  | Commenter |
| Viewer         | Builder          | Viewer     | Viewer    |
| Viewer         | Builder          | No access  | No access |
| Viewer         | Editor           | –          | Editor    |
| Viewer         | Editor           | Admin      | Admin     |
| Viewer         | Editor           | Builder    | Builder   |
| Viewer         | Editor           | Editor     | Editor    |
| Viewer         | Editor           | Commenter  | Commenter |
| Viewer         | Editor           | Viewer     | Viewer    |
| Viewer         | Editor           | No access  | No access |
| Viewer         | Commenter        | –          | Commenter |
| Viewer         | Commenter        | Admin      | Admin     |
| Viewer         | Commenter        | Builder    | Builder   |
| Viewer         | Commenter        | Editor     | Editor    |
| Viewer         | Commenter        | Commenter  | Commenter |
| Viewer         | Commenter        | Viewer     | Viewer    |
| Viewer         | Commenter        | No access  | No access |
| Viewer         | Viewer           | –          | Viewer    |
| Viewer         | Viewer           | Admin      | Admin     |
| Viewer         | Viewer           | Builder    | Builder   |
| Viewer         | Viewer           | Editor     | Editor    |
| Viewer         | Viewer           | Commenter  | Commenter |
| Viewer         | Viewer           | Viewer     | Viewer    |
| Viewer         | Viewer           | No access  | No access |
| Viewer         | No access        | –          | No access |
| Viewer         | No access        | Admin      | Admin     |
| Viewer         | No access        | Builder    | Builder   |
| Viewer         | No access        | Editor     | Editor    |
| Viewer         | No access        | Commenter  | Commenter |
| Viewer         | No access        | Viewer     | Viewer    |
| Viewer         | No access        | No access  | No access |
| No access      | –                | –          | No access |
| No access      | –                | Admin      | Admin     |
| No access      | –                | Builder    | Builder   |
| No access      | –                | Editor     | Editor    |
| No access      | –                | Commenter  | Commenter |
| No access      | –                | Viewer     | Viewer    |
| No access      | –                | No access  | No access |
| No access      | Admin            | –          | Admin     |
| No access      | Admin            | Admin      | Admin     |
| No access      | Admin            | Builder    | Builder   |
| No access      | Admin            | Editor     | Editor    |
| No access      | Admin            | Commenter  | Commenter |
| No access      | Admin            | Viewer     | Viewer    |
| No access      | Admin            | No access  | No access |
| No access      | Builder          | –          | Builder   |
| No access      | Builder          | Admin      | Admin     |
| No access      | Builder          | Builder    | Builder   |
| No access      | Builder          | Editor     | Editor    |
| No access      | Builder          | Commenter  | Commenter |
| No access      | Builder          | Viewer     | Viewer    |
| No access      | Builder          | No access  | No access |
| No access      | Editor           | –          | Editor    |
| No access      | Editor           | Admin      | Admin     |
| No access      | Editor           | Builder    | Builder   |
| No access      | Editor           | Editor     | Editor    |
| No access      | Editor           | Commenter  | Commenter |
| No access      | Editor           | Viewer     | Viewer    |
| No access      | Editor           | No access  | No access |
| No access      | Commenter        | –          | Commenter |
| No access      | Commenter        | Admin      | Admin     |
| No access      | Commenter        | Builder    | Builder   |
| No access      | Commenter        | Editor     | Editor    |
| No access      | Commenter        | Commenter  | Commenter |
| No access      | Commenter        | Viewer     | Viewer    |
| No access      | Commenter        | No access  | No access |
| No access      | Viewer           | –          | Viewer    |
| No access      | Viewer           | Admin      | Admin     |
| No access      | Viewer           | Builder    | Builder   |
| No access      | Viewer           | Editor     | Editor    |
| No access      | Viewer           | Commenter  | Commenter |
| No access      | Viewer           | Viewer     | Viewer    |
| No access      | Viewer           | No access  | No access |
| No access      | No access        | –          | No access |
| No access      | No access        | Admin      | Admin     |
| No access      | No access        | Builder    | Builder   |
| No access      | No access        | Editor     | Editor    |
| No access      | No access        | Commenter  | Commenter |
| No access      | No access        | Viewer     | Viewer    |
| No access      | No access        | No access  | No access |
| No role        | –                | –          | No access |
| No role        | –                | Admin      | Admin     |
| No role        | –                | Builder    | Builder   |
| No role        | –                | Editor     | Editor    |
| No role        | –                | Commenter  | Commenter |
| No role        | –                | Viewer     | Viewer    |
| No role        | –                | No access  | No access |
| No role        | Admin            | –          | Admin     |
| No role        | Admin            | Admin      | Admin     |
| No role        | Admin            | Builder    | Builder   |
| No role        | Admin            | Editor     | Editor    |
| No role        | Admin            | Commenter  | Commenter |
| No role        | Admin            | Viewer     | Viewer    |
| No role        | Admin            | No access  | No access |
| No role        | Builder          | –          | Builder   |
| No role        | Builder          | Admin      | Admin     |
| No role        | Builder          | Builder    | Builder   |
| No role        | Builder          | Editor     | Editor    |
| No role        | Builder          | Commenter  | Commenter |
| No role        | Builder          | Viewer     | Viewer    |
| No role        | Builder          | No access  | No access |
| No role        | Editor           | –          | Editor    |
| No role        | Editor           | Admin      | Admin     |
| No role        | Editor           | Builder    | Builder   |
| No role        | Editor           | Editor     | Editor    |
| No role        | Editor           | Commenter  | Commenter |
| No role        | Editor           | Viewer     | Viewer    |
| No role        | Editor           | No access  | No access |
| No role        | Commenter        | –          | Commenter |
| No role        | Commenter        | Admin      | Admin     |
| No role        | Commenter        | Builder    | Builder   |
| No role        | Commenter        | Editor     | Editor    |
| No role        | Commenter        | Commenter  | Commenter |
| No role        | Commenter        | Viewer     | Viewer    |
| No role        | Commenter        | No access  | No access |
| No role        | Viewer           | –          | Viewer    |
| No role        | Viewer           | Admin      | Admin     |
| No role        | Viewer           | Builder    | Builder   |
| No role        | Viewer           | Editor     | Editor    |
| No role        | Viewer           | Commenter  | Commenter |
| No role        | Viewer           | Viewer     | Viewer    |
| No role        | Viewer           | No access  | No access |
| No role        | No access        | –          | No access |
| No role        | No access        | Admin      | Admin     |
| No role        | No access        | Builder    | Builder   |
| No role        | No access        | Editor     | Editor    |
| No role        | No access        | Commenter  | Commenter |
| No role        | No access        | Viewer     | Viewer    |
| No role        | No access        | No access  | No access |

## Roles held through a team

A team can hold a role on the workspace too. On one scope the member's own role wins over
the roles of their teams, whatever the roles are, and the workspace role stored on the
membership wins over a team's role on the workspace unless it is "No role".

| Workspace role         | Application role        | Child role           | Result    |
| ---------------------- | ----------------------- | -------------------- | --------- |
| No role, Admin (team)  | –                       | –                    | Admin     |
| No role, Admin (team)  | –                       | No access            | No access |
| No role, Editor (team) | –                       | –                    | Editor    |
| No role, Editor (team) | –                       | Viewer               | Viewer    |
| Editor, Admin (team)   | –                       | –                    | Editor    |
| Editor, Admin (team)   | –                       | No access            | No access |
| Admin                  | –                       | No access (team)     | No access |
| Admin                  | No access (team)        | –                    | No access |
| Editor                 | Admin (team)            | –                    | Admin     |
| Editor                 | Admin (team)            | Viewer               | Viewer    |
| Editor                 | Admin (team)            | No access (team)     | No access |
| Editor                 | Viewer, Admin (team)    | –                    | Viewer    |
| Editor                 | Admin, No access (team) | –                    | Admin     |
| Editor                 | Admin                   | No access (team)     | No access |
| Viewer                 | –                       | Viewer, Admin (team) | Viewer    |
| Viewer                 | –                       | Admin, Viewer (team) | Admin     |
| No access              | Editor (team)           | –                    | Editor    |
| No access              | –                       | Editor (team)        | Editor    |
