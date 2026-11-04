# Agent Users Test Plan

Agents use User identities and a single workspace membership. This plan assigns
each behavior to one primary test suite; API and frontend tests cover their own
boundaries instead of repeating the domain permission matrix.

## Shared setup

- Backend tests use `data_fixture.create_agent()` and the existing premium or
  enterprise fixture builders. The factory returns the agent User and accepts its
  workspace, role and trash state. Use a second workspace only for isolation tests.
- Reuse a local pytest fixture when several tests need the same workspace, human
  administrator and agent. Add tables, teams, licenses or credentials only in the
  suites that exercise them. Do not share mutable fixtures between tests.
- Frontend tests use the existing TestApp and mock-server fixtures. Seed one person
  and one agent with distinct User IDs. Component tests assert visible results;
  store tests own realtime state changes.
- IDs use `area.scenario`. Parameterize variations of the same rule, such as active,
  disabled and trashed identities. Each scenario below has one primary owner.

## Coverage matrix

| ID | Expected behavior | Primary coverage |
| --- | --- | --- |
| 1.1 | Creation yields one User, Profile and membership; names and roles update once. | Core agent handler tests |
| 1.2 | A second membership or standalone membership removal is rejected, including concurrent changes and trashed workspaces. | Membership tests |
| 1.3 | Trash preserves identity/grants; restore preserves ID and independent disabled state; hard deletion removes the agent User. | Agent lifecycle tests |
| 1.4 | People queries hide agents; explicit inclusive queries and stored foreign keys resolve them, including retained credits. | User manager tests |
| 1.5 | Empty upgrades remove core_agent; legacy data and unsafe rollback are rejected without changing it. | Core migration tests |
| 2.1 | Membership, enabled state and trash determine execution; individual and queryset checks agree. | Core permission tests |
| 2.2 | Early human grants and global queries do not grant agents account privileges. | Core permission tests |
| 2.3 | Scoped/team/field roles apply to agent Users; unavailable roles deny access without changing stored grants. | Enterprise permission tests |
| 2.4 | Agent admins never satisfy last-human-admin protection. | Workspace member tests |
| 3.1 | Human credentials cannot authenticate an agent, including cached JWTs, WebSockets, database tokens and MCP/OAuth. | Authentication boundary tests |
| 3.2 | Agent memberships and grants consume no human seats; direct license assignment is rejected. | License/seat tests |
| 3.3 | Agents remain valid notification senders but never become human recipients. | Notification handler tests |
| 4.1 | Agent CRUD and subject options expose canonical IDs and identity kind without exposing synthetic contact addresses. | Agent/subject API tests |
| 4.2 | Local Baserow run-as accepts the workspace's agent; rejects other humans/workspaces and unavailable identities without fallback. | Integration tests |
| 4.3 | Settings, run-as and permission selectors render the correct agent names/icons and submit auth.User IDs. | Frontend selector tests |
| 5.1 | Assignments, defaults, filters and import/export accept eligible workspace agents and reject outsiders. | Collaborator backend tests |
| 5.2 | Pickers, copy/paste and public cells render agents; realtime rename/trash/restore updates shared collaborator state. | Collaborator component/store tests |
| 6.1 | Rich-text and comment mentions preserve agent IDs; human mention notifications still work. | Mention backend tests |
| 6.2 | Mention suggestions and saved mentions show the agent name/icon. | Editor/comment frontend tests |
| 7.1 | Rows, views, trash, files and history credit the agent; deleted history retains its name and identity kind. | Attribution tests |
| 7.2 | Jobs, exports, snapshots, AI updates and syncs execute as the stored agent User and reject revoked access. | Deferred-work tests |

Scenario families identify coverage ownership, not a requirement to repeat every
combination through every layer. Reuse existing tests when a changed fixture or
assertion already proves the behavior. Future agent MCP credentials are outside
this change; scenario 3.1 covers today's human credential flows.

## Manual smoke check

Use a workspace with an administrator, a viewer, and an agent. Add collaborator,
Created by, Last modified by and rich-text fields to one table.

1. Create and rename the agent in settings. Select it as a Local Baserow run-as
   identity and perform an allowed row change. The row credits the agent.
2. Assign and mention the agent. Names and icons render in the grid, row details
   and shared view. A second browser updates after a rename.
3. Trash the agent. It disappears from current choices and cannot execute; existing
   credits retain its name. Restore it and verify the same assignments return.
4. Verify the people list and seat count did not increase. With an agent Admin
   present, the final human administrator still cannot leave the workspace.
5. Revoke the agent's role before queued work runs. The work is denied rather than
   running with the administrator's permissions.

Record automated commands and any unperformed browser checks in the PR validation
notes; this plan describes expected behavior rather than claiming a run passed.
