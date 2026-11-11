# Role matrix after ADR 010

The [role matrix before ADR 010](010-role-matrix-before.md) with one more column: the
role that resolves on the child under the rules of
[ADR 010](010-admin-role-precedence.md). Both columns were produced by the role handler,
"Result before" by `develop` at c5c5650eda and "New result" by the branch implementing
the record. A new result that differs from the result before is marked "(new)" and shown
in bold; 70 of the 343 combinations of direct roles change, and 3 of the 18 rows with a
team.

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

| Workspace role | Application role | Child role | Result before | New result      |
| -------------- | ---------------- | ---------- | ------------- | --------------- |
| Admin          | –                | –          | Admin         | Admin           |
| Admin          | –                | Admin      | Admin         | Admin           |
| Admin          | –                | Builder    | Builder       | **Admin (new)** |
| Admin          | –                | Editor     | Editor        | **Admin (new)** |
| Admin          | –                | Commenter  | Commenter     | **Admin (new)** |
| Admin          | –                | Viewer     | Viewer        | **Admin (new)** |
| Admin          | –                | No access  | No access     | **Admin (new)** |
| Admin          | Admin            | –          | Admin         | Admin           |
| Admin          | Admin            | Admin      | Admin         | Admin           |
| Admin          | Admin            | Builder    | Builder       | **Admin (new)** |
| Admin          | Admin            | Editor     | Editor        | **Admin (new)** |
| Admin          | Admin            | Commenter  | Commenter     | **Admin (new)** |
| Admin          | Admin            | Viewer     | Viewer        | **Admin (new)** |
| Admin          | Admin            | No access  | No access     | **Admin (new)** |
| Admin          | Builder          | –          | Builder       | **Admin (new)** |
| Admin          | Builder          | Admin      | Admin         | Admin           |
| Admin          | Builder          | Builder    | Builder       | **Admin (new)** |
| Admin          | Builder          | Editor     | Editor        | **Admin (new)** |
| Admin          | Builder          | Commenter  | Commenter     | **Admin (new)** |
| Admin          | Builder          | Viewer     | Viewer        | **Admin (new)** |
| Admin          | Builder          | No access  | No access     | **Admin (new)** |
| Admin          | Editor           | –          | Editor        | **Admin (new)** |
| Admin          | Editor           | Admin      | Admin         | Admin           |
| Admin          | Editor           | Builder    | Builder       | **Admin (new)** |
| Admin          | Editor           | Editor     | Editor        | **Admin (new)** |
| Admin          | Editor           | Commenter  | Commenter     | **Admin (new)** |
| Admin          | Editor           | Viewer     | Viewer        | **Admin (new)** |
| Admin          | Editor           | No access  | No access     | **Admin (new)** |
| Admin          | Commenter        | –          | Commenter     | **Admin (new)** |
| Admin          | Commenter        | Admin      | Admin         | Admin           |
| Admin          | Commenter        | Builder    | Builder       | **Admin (new)** |
| Admin          | Commenter        | Editor     | Editor        | **Admin (new)** |
| Admin          | Commenter        | Commenter  | Commenter     | **Admin (new)** |
| Admin          | Commenter        | Viewer     | Viewer        | **Admin (new)** |
| Admin          | Commenter        | No access  | No access     | **Admin (new)** |
| Admin          | Viewer           | –          | Viewer        | **Admin (new)** |
| Admin          | Viewer           | Admin      | Admin         | Admin           |
| Admin          | Viewer           | Builder    | Builder       | **Admin (new)** |
| Admin          | Viewer           | Editor     | Editor        | **Admin (new)** |
| Admin          | Viewer           | Commenter  | Commenter     | **Admin (new)** |
| Admin          | Viewer           | Viewer     | Viewer        | **Admin (new)** |
| Admin          | Viewer           | No access  | No access     | **Admin (new)** |
| Admin          | No access        | –          | No access     | **Admin (new)** |
| Admin          | No access        | Admin      | Admin         | Admin           |
| Admin          | No access        | Builder    | Builder       | **Admin (new)** |
| Admin          | No access        | Editor     | Editor        | **Admin (new)** |
| Admin          | No access        | Commenter  | Commenter     | **Admin (new)** |
| Admin          | No access        | Viewer     | Viewer        | **Admin (new)** |
| Admin          | No access        | No access  | No access     | **Admin (new)** |
| Builder        | –                | –          | Builder       | Builder         |
| Builder        | –                | Admin      | Admin         | Admin           |
| Builder        | –                | Builder    | Builder       | Builder         |
| Builder        | –                | Editor     | Editor        | Editor          |
| Builder        | –                | Commenter  | Commenter     | Commenter       |
| Builder        | –                | Viewer     | Viewer        | Viewer          |
| Builder        | –                | No access  | No access     | No access       |
| Builder        | Admin            | –          | Admin         | Admin           |
| Builder        | Admin            | Admin      | Admin         | Admin           |
| Builder        | Admin            | Builder    | Builder       | **Admin (new)** |
| Builder        | Admin            | Editor     | Editor        | **Admin (new)** |
| Builder        | Admin            | Commenter  | Commenter     | **Admin (new)** |
| Builder        | Admin            | Viewer     | Viewer        | **Admin (new)** |
| Builder        | Admin            | No access  | No access     | **Admin (new)** |
| Builder        | Builder          | –          | Builder       | Builder         |
| Builder        | Builder          | Admin      | Admin         | Admin           |
| Builder        | Builder          | Builder    | Builder       | Builder         |
| Builder        | Builder          | Editor     | Editor        | Editor          |
| Builder        | Builder          | Commenter  | Commenter     | Commenter       |
| Builder        | Builder          | Viewer     | Viewer        | Viewer          |
| Builder        | Builder          | No access  | No access     | No access       |
| Builder        | Editor           | –          | Editor        | Editor          |
| Builder        | Editor           | Admin      | Admin         | Admin           |
| Builder        | Editor           | Builder    | Builder       | Builder         |
| Builder        | Editor           | Editor     | Editor        | Editor          |
| Builder        | Editor           | Commenter  | Commenter     | Commenter       |
| Builder        | Editor           | Viewer     | Viewer        | Viewer          |
| Builder        | Editor           | No access  | No access     | No access       |
| Builder        | Commenter        | –          | Commenter     | Commenter       |
| Builder        | Commenter        | Admin      | Admin         | Admin           |
| Builder        | Commenter        | Builder    | Builder       | Builder         |
| Builder        | Commenter        | Editor     | Editor        | Editor          |
| Builder        | Commenter        | Commenter  | Commenter     | Commenter       |
| Builder        | Commenter        | Viewer     | Viewer        | Viewer          |
| Builder        | Commenter        | No access  | No access     | No access       |
| Builder        | Viewer           | –          | Viewer        | Viewer          |
| Builder        | Viewer           | Admin      | Admin         | Admin           |
| Builder        | Viewer           | Builder    | Builder       | Builder         |
| Builder        | Viewer           | Editor     | Editor        | Editor          |
| Builder        | Viewer           | Commenter  | Commenter     | Commenter       |
| Builder        | Viewer           | Viewer     | Viewer        | Viewer          |
| Builder        | Viewer           | No access  | No access     | No access       |
| Builder        | No access        | –          | No access     | No access       |
| Builder        | No access        | Admin      | Admin         | Admin           |
| Builder        | No access        | Builder    | Builder       | Builder         |
| Builder        | No access        | Editor     | Editor        | Editor          |
| Builder        | No access        | Commenter  | Commenter     | Commenter       |
| Builder        | No access        | Viewer     | Viewer        | Viewer          |
| Builder        | No access        | No access  | No access     | No access       |
| Editor         | –                | –          | Editor        | Editor          |
| Editor         | –                | Admin      | Admin         | Admin           |
| Editor         | –                | Builder    | Builder       | Builder         |
| Editor         | –                | Editor     | Editor        | Editor          |
| Editor         | –                | Commenter  | Commenter     | Commenter       |
| Editor         | –                | Viewer     | Viewer        | Viewer          |
| Editor         | –                | No access  | No access     | No access       |
| Editor         | Admin            | –          | Admin         | Admin           |
| Editor         | Admin            | Admin      | Admin         | Admin           |
| Editor         | Admin            | Builder    | Builder       | **Admin (new)** |
| Editor         | Admin            | Editor     | Editor        | **Admin (new)** |
| Editor         | Admin            | Commenter  | Commenter     | **Admin (new)** |
| Editor         | Admin            | Viewer     | Viewer        | **Admin (new)** |
| Editor         | Admin            | No access  | No access     | **Admin (new)** |
| Editor         | Builder          | –          | Builder       | Builder         |
| Editor         | Builder          | Admin      | Admin         | Admin           |
| Editor         | Builder          | Builder    | Builder       | Builder         |
| Editor         | Builder          | Editor     | Editor        | Editor          |
| Editor         | Builder          | Commenter  | Commenter     | Commenter       |
| Editor         | Builder          | Viewer     | Viewer        | Viewer          |
| Editor         | Builder          | No access  | No access     | No access       |
| Editor         | Editor           | –          | Editor        | Editor          |
| Editor         | Editor           | Admin      | Admin         | Admin           |
| Editor         | Editor           | Builder    | Builder       | Builder         |
| Editor         | Editor           | Editor     | Editor        | Editor          |
| Editor         | Editor           | Commenter  | Commenter     | Commenter       |
| Editor         | Editor           | Viewer     | Viewer        | Viewer          |
| Editor         | Editor           | No access  | No access     | No access       |
| Editor         | Commenter        | –          | Commenter     | Commenter       |
| Editor         | Commenter        | Admin      | Admin         | Admin           |
| Editor         | Commenter        | Builder    | Builder       | Builder         |
| Editor         | Commenter        | Editor     | Editor        | Editor          |
| Editor         | Commenter        | Commenter  | Commenter     | Commenter       |
| Editor         | Commenter        | Viewer     | Viewer        | Viewer          |
| Editor         | Commenter        | No access  | No access     | No access       |
| Editor         | Viewer           | –          | Viewer        | Viewer          |
| Editor         | Viewer           | Admin      | Admin         | Admin           |
| Editor         | Viewer           | Builder    | Builder       | Builder         |
| Editor         | Viewer           | Editor     | Editor        | Editor          |
| Editor         | Viewer           | Commenter  | Commenter     | Commenter       |
| Editor         | Viewer           | Viewer     | Viewer        | Viewer          |
| Editor         | Viewer           | No access  | No access     | No access       |
| Editor         | No access        | –          | No access     | No access       |
| Editor         | No access        | Admin      | Admin         | Admin           |
| Editor         | No access        | Builder    | Builder       | Builder         |
| Editor         | No access        | Editor     | Editor        | Editor          |
| Editor         | No access        | Commenter  | Commenter     | Commenter       |
| Editor         | No access        | Viewer     | Viewer        | Viewer          |
| Editor         | No access        | No access  | No access     | No access       |
| Commenter      | –                | –          | Commenter     | Commenter       |
| Commenter      | –                | Admin      | Admin         | Admin           |
| Commenter      | –                | Builder    | Builder       | Builder         |
| Commenter      | –                | Editor     | Editor        | Editor          |
| Commenter      | –                | Commenter  | Commenter     | Commenter       |
| Commenter      | –                | Viewer     | Viewer        | Viewer          |
| Commenter      | –                | No access  | No access     | No access       |
| Commenter      | Admin            | –          | Admin         | Admin           |
| Commenter      | Admin            | Admin      | Admin         | Admin           |
| Commenter      | Admin            | Builder    | Builder       | **Admin (new)** |
| Commenter      | Admin            | Editor     | Editor        | **Admin (new)** |
| Commenter      | Admin            | Commenter  | Commenter     | **Admin (new)** |
| Commenter      | Admin            | Viewer     | Viewer        | **Admin (new)** |
| Commenter      | Admin            | No access  | No access     | **Admin (new)** |
| Commenter      | Builder          | –          | Builder       | Builder         |
| Commenter      | Builder          | Admin      | Admin         | Admin           |
| Commenter      | Builder          | Builder    | Builder       | Builder         |
| Commenter      | Builder          | Editor     | Editor        | Editor          |
| Commenter      | Builder          | Commenter  | Commenter     | Commenter       |
| Commenter      | Builder          | Viewer     | Viewer        | Viewer          |
| Commenter      | Builder          | No access  | No access     | No access       |
| Commenter      | Editor           | –          | Editor        | Editor          |
| Commenter      | Editor           | Admin      | Admin         | Admin           |
| Commenter      | Editor           | Builder    | Builder       | Builder         |
| Commenter      | Editor           | Editor     | Editor        | Editor          |
| Commenter      | Editor           | Commenter  | Commenter     | Commenter       |
| Commenter      | Editor           | Viewer     | Viewer        | Viewer          |
| Commenter      | Editor           | No access  | No access     | No access       |
| Commenter      | Commenter        | –          | Commenter     | Commenter       |
| Commenter      | Commenter        | Admin      | Admin         | Admin           |
| Commenter      | Commenter        | Builder    | Builder       | Builder         |
| Commenter      | Commenter        | Editor     | Editor        | Editor          |
| Commenter      | Commenter        | Commenter  | Commenter     | Commenter       |
| Commenter      | Commenter        | Viewer     | Viewer        | Viewer          |
| Commenter      | Commenter        | No access  | No access     | No access       |
| Commenter      | Viewer           | –          | Viewer        | Viewer          |
| Commenter      | Viewer           | Admin      | Admin         | Admin           |
| Commenter      | Viewer           | Builder    | Builder       | Builder         |
| Commenter      | Viewer           | Editor     | Editor        | Editor          |
| Commenter      | Viewer           | Commenter  | Commenter     | Commenter       |
| Commenter      | Viewer           | Viewer     | Viewer        | Viewer          |
| Commenter      | Viewer           | No access  | No access     | No access       |
| Commenter      | No access        | –          | No access     | No access       |
| Commenter      | No access        | Admin      | Admin         | Admin           |
| Commenter      | No access        | Builder    | Builder       | Builder         |
| Commenter      | No access        | Editor     | Editor        | Editor          |
| Commenter      | No access        | Commenter  | Commenter     | Commenter       |
| Commenter      | No access        | Viewer     | Viewer        | Viewer          |
| Commenter      | No access        | No access  | No access     | No access       |
| Viewer         | –                | –          | Viewer        | Viewer          |
| Viewer         | –                | Admin      | Admin         | Admin           |
| Viewer         | –                | Builder    | Builder       | Builder         |
| Viewer         | –                | Editor     | Editor        | Editor          |
| Viewer         | –                | Commenter  | Commenter     | Commenter       |
| Viewer         | –                | Viewer     | Viewer        | Viewer          |
| Viewer         | –                | No access  | No access     | No access       |
| Viewer         | Admin            | –          | Admin         | Admin           |
| Viewer         | Admin            | Admin      | Admin         | Admin           |
| Viewer         | Admin            | Builder    | Builder       | **Admin (new)** |
| Viewer         | Admin            | Editor     | Editor        | **Admin (new)** |
| Viewer         | Admin            | Commenter  | Commenter     | **Admin (new)** |
| Viewer         | Admin            | Viewer     | Viewer        | **Admin (new)** |
| Viewer         | Admin            | No access  | No access     | **Admin (new)** |
| Viewer         | Builder          | –          | Builder       | Builder         |
| Viewer         | Builder          | Admin      | Admin         | Admin           |
| Viewer         | Builder          | Builder    | Builder       | Builder         |
| Viewer         | Builder          | Editor     | Editor        | Editor          |
| Viewer         | Builder          | Commenter  | Commenter     | Commenter       |
| Viewer         | Builder          | Viewer     | Viewer        | Viewer          |
| Viewer         | Builder          | No access  | No access     | No access       |
| Viewer         | Editor           | –          | Editor        | Editor          |
| Viewer         | Editor           | Admin      | Admin         | Admin           |
| Viewer         | Editor           | Builder    | Builder       | Builder         |
| Viewer         | Editor           | Editor     | Editor        | Editor          |
| Viewer         | Editor           | Commenter  | Commenter     | Commenter       |
| Viewer         | Editor           | Viewer     | Viewer        | Viewer          |
| Viewer         | Editor           | No access  | No access     | No access       |
| Viewer         | Commenter        | –          | Commenter     | Commenter       |
| Viewer         | Commenter        | Admin      | Admin         | Admin           |
| Viewer         | Commenter        | Builder    | Builder       | Builder         |
| Viewer         | Commenter        | Editor     | Editor        | Editor          |
| Viewer         | Commenter        | Commenter  | Commenter     | Commenter       |
| Viewer         | Commenter        | Viewer     | Viewer        | Viewer          |
| Viewer         | Commenter        | No access  | No access     | No access       |
| Viewer         | Viewer           | –          | Viewer        | Viewer          |
| Viewer         | Viewer           | Admin      | Admin         | Admin           |
| Viewer         | Viewer           | Builder    | Builder       | Builder         |
| Viewer         | Viewer           | Editor     | Editor        | Editor          |
| Viewer         | Viewer           | Commenter  | Commenter     | Commenter       |
| Viewer         | Viewer           | Viewer     | Viewer        | Viewer          |
| Viewer         | Viewer           | No access  | No access     | No access       |
| Viewer         | No access        | –          | No access     | No access       |
| Viewer         | No access        | Admin      | Admin         | Admin           |
| Viewer         | No access        | Builder    | Builder       | Builder         |
| Viewer         | No access        | Editor     | Editor        | Editor          |
| Viewer         | No access        | Commenter  | Commenter     | Commenter       |
| Viewer         | No access        | Viewer     | Viewer        | Viewer          |
| Viewer         | No access        | No access  | No access     | No access       |
| No access      | –                | –          | No access     | No access       |
| No access      | –                | Admin      | Admin         | Admin           |
| No access      | –                | Builder    | Builder       | Builder         |
| No access      | –                | Editor     | Editor        | Editor          |
| No access      | –                | Commenter  | Commenter     | Commenter       |
| No access      | –                | Viewer     | Viewer        | Viewer          |
| No access      | –                | No access  | No access     | No access       |
| No access      | Admin            | –          | Admin         | Admin           |
| No access      | Admin            | Admin      | Admin         | Admin           |
| No access      | Admin            | Builder    | Builder       | **Admin (new)** |
| No access      | Admin            | Editor     | Editor        | **Admin (new)** |
| No access      | Admin            | Commenter  | Commenter     | **Admin (new)** |
| No access      | Admin            | Viewer     | Viewer        | **Admin (new)** |
| No access      | Admin            | No access  | No access     | **Admin (new)** |
| No access      | Builder          | –          | Builder       | Builder         |
| No access      | Builder          | Admin      | Admin         | Admin           |
| No access      | Builder          | Builder    | Builder       | Builder         |
| No access      | Builder          | Editor     | Editor        | Editor          |
| No access      | Builder          | Commenter  | Commenter     | Commenter       |
| No access      | Builder          | Viewer     | Viewer        | Viewer          |
| No access      | Builder          | No access  | No access     | No access       |
| No access      | Editor           | –          | Editor        | Editor          |
| No access      | Editor           | Admin      | Admin         | Admin           |
| No access      | Editor           | Builder    | Builder       | Builder         |
| No access      | Editor           | Editor     | Editor        | Editor          |
| No access      | Editor           | Commenter  | Commenter     | Commenter       |
| No access      | Editor           | Viewer     | Viewer        | Viewer          |
| No access      | Editor           | No access  | No access     | No access       |
| No access      | Commenter        | –          | Commenter     | Commenter       |
| No access      | Commenter        | Admin      | Admin         | Admin           |
| No access      | Commenter        | Builder    | Builder       | Builder         |
| No access      | Commenter        | Editor     | Editor        | Editor          |
| No access      | Commenter        | Commenter  | Commenter     | Commenter       |
| No access      | Commenter        | Viewer     | Viewer        | Viewer          |
| No access      | Commenter        | No access  | No access     | No access       |
| No access      | Viewer           | –          | Viewer        | Viewer          |
| No access      | Viewer           | Admin      | Admin         | Admin           |
| No access      | Viewer           | Builder    | Builder       | Builder         |
| No access      | Viewer           | Editor     | Editor        | Editor          |
| No access      | Viewer           | Commenter  | Commenter     | Commenter       |
| No access      | Viewer           | Viewer     | Viewer        | Viewer          |
| No access      | Viewer           | No access  | No access     | No access       |
| No access      | No access        | –          | No access     | No access       |
| No access      | No access        | Admin      | Admin         | Admin           |
| No access      | No access        | Builder    | Builder       | Builder         |
| No access      | No access        | Editor     | Editor        | Editor          |
| No access      | No access        | Commenter  | Commenter     | Commenter       |
| No access      | No access        | Viewer     | Viewer        | Viewer          |
| No access      | No access        | No access  | No access     | No access       |
| No role        | –                | –          | No access     | No access       |
| No role        | –                | Admin      | Admin         | Admin           |
| No role        | –                | Builder    | Builder       | Builder         |
| No role        | –                | Editor     | Editor        | Editor          |
| No role        | –                | Commenter  | Commenter     | Commenter       |
| No role        | –                | Viewer     | Viewer        | Viewer          |
| No role        | –                | No access  | No access     | No access       |
| No role        | Admin            | –          | Admin         | Admin           |
| No role        | Admin            | Admin      | Admin         | Admin           |
| No role        | Admin            | Builder    | Builder       | **Admin (new)** |
| No role        | Admin            | Editor     | Editor        | **Admin (new)** |
| No role        | Admin            | Commenter  | Commenter     | **Admin (new)** |
| No role        | Admin            | Viewer     | Viewer        | **Admin (new)** |
| No role        | Admin            | No access  | No access     | **Admin (new)** |
| No role        | Builder          | –          | Builder       | Builder         |
| No role        | Builder          | Admin      | Admin         | Admin           |
| No role        | Builder          | Builder    | Builder       | Builder         |
| No role        | Builder          | Editor     | Editor        | Editor          |
| No role        | Builder          | Commenter  | Commenter     | Commenter       |
| No role        | Builder          | Viewer     | Viewer        | Viewer          |
| No role        | Builder          | No access  | No access     | No access       |
| No role        | Editor           | –          | Editor        | Editor          |
| No role        | Editor           | Admin      | Admin         | Admin           |
| No role        | Editor           | Builder    | Builder       | Builder         |
| No role        | Editor           | Editor     | Editor        | Editor          |
| No role        | Editor           | Commenter  | Commenter     | Commenter       |
| No role        | Editor           | Viewer     | Viewer        | Viewer          |
| No role        | Editor           | No access  | No access     | No access       |
| No role        | Commenter        | –          | Commenter     | Commenter       |
| No role        | Commenter        | Admin      | Admin         | Admin           |
| No role        | Commenter        | Builder    | Builder       | Builder         |
| No role        | Commenter        | Editor     | Editor        | Editor          |
| No role        | Commenter        | Commenter  | Commenter     | Commenter       |
| No role        | Commenter        | Viewer     | Viewer        | Viewer          |
| No role        | Commenter        | No access  | No access     | No access       |
| No role        | Viewer           | –          | Viewer        | Viewer          |
| No role        | Viewer           | Admin      | Admin         | Admin           |
| No role        | Viewer           | Builder    | Builder       | Builder         |
| No role        | Viewer           | Editor     | Editor        | Editor          |
| No role        | Viewer           | Commenter  | Commenter     | Commenter       |
| No role        | Viewer           | Viewer     | Viewer        | Viewer          |
| No role        | Viewer           | No access  | No access     | No access       |
| No role        | No access        | –          | No access     | No access       |
| No role        | No access        | Admin      | Admin         | Admin           |
| No role        | No access        | Builder    | Builder       | Builder         |
| No role        | No access        | Editor     | Editor        | Editor          |
| No role        | No access        | Commenter  | Commenter     | Commenter       |
| No role        | No access        | Viewer     | Viewer        | Viewer          |
| No role        | No access        | No access  | No access     | No access       |

## Roles held through a team

A team can hold a role on the workspace too, which applies to the members whose stored
role is "No role". A team's Admin is not held directly, so it gets no precedence: a role
on a scope inside still wins, on the workspace as on an application.

| Workspace role         | Application role        | Child role           | Result before | New result      |
| ---------------------- | ----------------------- | -------------------- | ------------- | --------------- |
| No role, Admin (team)  | –                       | –                    | Admin         | Admin           |
| No role, Admin (team)  | –                       | No access            | No access     | No access       |
| No role, Editor (team) | –                       | –                    | Editor        | Editor          |
| No role, Editor (team) | –                       | Viewer               | Viewer        | Viewer          |
| Editor, Admin (team)   | –                       | –                    | Editor        | Editor          |
| Editor, Admin (team)   | –                       | No access            | No access     | No access       |
| Admin                  | –                       | No access (team)     | No access     | **Admin (new)** |
| Admin                  | No access (team)        | –                    | No access     | **Admin (new)** |
| Editor                 | Admin (team)            | –                    | Admin         | Admin           |
| Editor                 | Admin (team)            | Viewer               | Viewer        | Viewer          |
| Editor                 | Admin (team)            | No access (team)     | No access     | No access       |
| Editor                 | Viewer, Admin (team)    | –                    | Viewer        | Viewer          |
| Editor                 | Admin, No access (team) | –                    | Admin         | Admin           |
| Editor                 | Admin                   | No access (team)     | No access     | **Admin (new)** |
| Viewer                 | –                       | Viewer, Admin (team) | Viewer        | Viewer          |
| Viewer                 | –                       | Admin, Viewer (team) | Admin         | Admin           |
| No access              | Editor (team)           | –                    | Editor        | Editor          |
| No access              | –                       | Editor (team)        | Editor        | Editor          |
