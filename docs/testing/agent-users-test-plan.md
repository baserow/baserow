# Agent Users Test Plan

Agents are user accounts marked as agents (ADR 013). This plan lists the cases
that must hold for people and agents. Tests and code reference a case by its ID;
the plan never references them.

The plan follows the grid view test plan: topics are numbered buckets, every
operation belongs to a named operation set, and the same outcome always uses the
same sentence. When you add a case, reuse the terms and sentences below instead
of inventing new ones.

## Vocabulary

### Identities

| Term              | Meaning                                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------------- |
| Person            | A user account of a human.                                                                                        |
| Agent             | A user account marked as an agent, with exactly one workspace membership.                                         |
| Identity          | A person or an agent.                                                                                             |
| Home workspace    | The workspace of the agent's single membership.                                                                   |
| Other workspace   | Any workspace that is not the agent's home workspace.                                                             |
| Active agent      | An agent that is enabled, not trashed, not scheduled for deletion, and whose home workspace is not trashed.       |
| Disabled agent    | An agent whose account is disabled.                                                                               |
| Trashed agent     | An agent that was moved to the trash. Restoring it makes it active again.                                         |
| Deleted agent     | An agent that was permanently deleted.                                                                            |
| Unavailable agent | A disabled, trashed or deleting agent, an agent outside its home workspace, or an agent with a second membership. |

### Operation sets

Every case names one of these sets. Use the set name, not a synonym.

| Set             | Operations                                                                                                                               |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Lifecycle       | Create, rename, change role, trash, restore and permanently delete an agent; delete its home workspace.                                  |
| Execute         | An identity acts: any permission check, any filtered list, any integration action run as that identity.                                  |
| Sign in         | Every human credential: session token (fresh or cached), password, database token, MCP key, MCP OAuth token, realtime connection.        |
| List people     | Member list, invitations, seat count, last-human-admin rule, notification recipients.                                                    |
| List identities | Agent settings, subject options, run-as picker, team and field-permission pickers, audit log actor filter.                               |
| Assign          | Set a collaborator field value, default or filter, or import one.                                                                        |
| Mention         | Mention an identity in a rich text field or a row comment.                                                                               |
| Credit          | Store who acted: created by, last modified by, trashed by, uploaded by, row history, audit log, automation history, notification sender. |
| Defer           | Run stored work later as the stored identity: jobs, exports, snapshots, data syncs, AI field updates, realtime unsubscribes.             |
| Broadcast       | Send realtime events about an agent or its memberships.                                                                                  |
| Migrate         | Apply or roll back the agent identity migrations.                                                                                        |

### Standard outcomes

Write expectations with these exact sentences.

| Sentence                                    | Meaning                                                               |
| ------------------------------------------- | --------------------------------------------------------------------- |
| The agent is allowed.                       | The permission check passes or the list keeps the object.             |
| The agent is denied.                        | The permission check fails or the list drops the object.              |
| The agent is listed.                        | The identity appears in the list or picker.                           |
| The agent is hidden.                        | The identity does not appear in the list or picker.                   |
| The value is rejected.                      | Validation fails and nothing is stored.                               |
| No mention is stored for the agent.         | The mention is dropped without an error.                              |
| The sign-in is rejected.                    | Authentication fails.                                                 |
| No seat is used.                            | Seat counts and license users do not change.                          |
| No notification is created for the agent.   | The agent never becomes a notification recipient.                     |
| The credit keeps the agent's id and name.   | Stored credits still point at the agent and show its name.            |
| The credit keeps the agent's identity kind. | History still marks the actor as an agent after the agent is deleted. |
| Stored grants are unchanged.                | Roles, team memberships and field grants keep their records.          |
| Stored grants are hidden.                   | Records remain, but reads skip them while the agent is trashed.       |
| The queued work fails and changes nothing.  | The work ends as failed and writes no data.                           |
| Only users who can list agents receive it.  | The event reaches users allowed to list agents and nobody else.       |

## Numbering

Case IDs use `bucket.group.case`, with a letter suffix for variants of the same
case, for example `4.2.1b`.

| Bucket | Topic                              |
| ------ | ---------------------------------- |
| 1      | Identity model                     |
| 2      | Lifecycle                          |
| 3      | Workspace membership               |
| 4      | Authorization                      |
| 5      | Sign in                            |
| 6      | Seats, licenses and personal views |
| 7      | Credit and history                 |
| 8      | Assign                             |
| 9      | Mention                            |
| 10     | Defer                              |
| 11     | Broadcast                          |
| 12     | Integrations run as an agent       |
| 13     | Pickers and settings               |
| 14     | Migrate                            |

## Coverage matrix

Maps `identity state × operation set` to the expected outcome and its cases.
`—` means the combination does not exist.

| State                       | Execute       | Sign in        | List people    | List identities | Assign            | Mention                       | Defer                      | Seat             |
| --------------------------- | ------------- | -------------- | -------------- | --------------- | ----------------- | ----------------------------- | -------------------------- | ---------------- |
| Person                      | Allowed       | Allowed        | Listed (3.2.1) | Listed (13.1.1) | Allowed           | Allowed, notified (9.1.2)     | Runs                       | Used             |
| Active agent                | By role (4.1) | Rejected (5.1) | Hidden (3.2.1) | Listed (13.1.1) | Allowed (8.1.1)   | Allowed, not notified (9.1.2) | Runs as the agent (10.1.1) | Not used (6.1.1) |
| Agent in an other workspace | Denied (4.2)  | Rejected (5.1) | Hidden (3.2.1) | Hidden (13.1.2) | Rejected (8.1.2d) | Dropped (9.1.4)               | Denied (10.2.1c)           | Not used (6.1.1) |
| Disabled agent              | Denied (4.2)  | Rejected (5.1) | Hidden (3.2.1) | Hidden (13.1.2) | Rejected (8.1.2a) | Dropped (9.1.4)               | Denied (10.2.1b)           | Not used (6.1.1) |
| Trashed agent               | Denied (4.2)  | Rejected (5.1) | Hidden (3.2.1) | Hidden (13.1.2) | Rejected (8.1.2b) | Dropped (9.1.4)               | Denied (10.2.1a)           | Not used (6.1.1) |
| Deleted agent               | —             | —              | —              | —               | Cleared (8.2.2)   | —                             | —                          | —                |

## 1. Identity model

### 1.1.1 An agent is one account with one membership

- The agent can't use a password, has a synthetic email and has no staff rights.
- The agent's home workspace comes from its membership.
- Membership lists split people from agents.

### 1.1.2 The default list of users contains people only

- The agent is hidden.
- An account without a profile is hidden.
- Stored references to the agent still resolve.

### 1.1.3 The inclusive list of identities hides trashed agents

- People and active agents are listed.
- The trashed agent is hidden, unless the list explicitly includes the trash.
- The list can be narrowed to agents.

### 1.1.4 Standard account creation creates a person

- Creating a user or a superuser creates a person.

## 2. Lifecycle

### 2.1.1 Manage agents through the API

- An admin can create, rename, change the role of, trash and restore an agent.
- A member can list agents; any change is denied.
- A non-member gets the standard workspace-membership error.

### 2.2.1 Role changes

- Stored grants are unchanged by a rename, also after a license change.
- A role change can't be undone through the undo history.
- A role must exist and be visible in the agent's home workspace.

### 2.3.1 Trash and restore

- The trashed agent is hidden from agent settings.
- Stored grants are hidden.
- Restoring returns the same id, role and team memberships.
- A disabled agent stays disabled after restore.

### 2.4.1 Permanent deletion

Variants: `a` deleting from the trash, `b` deleting the home workspace, `c` deleting the home workspace in bulk.

- The account, profile and membership are removed.
- Role assignments and team memberships are removed.

## 3. Workspace membership

### 3.1.1 One membership per agent

- An agent with a second membership is an unavailable agent.

### 3.2.1 People lists hide agents

- The agent is hidden from the member list.
- An agent admin never counts as the last human admin.
- The workspace list counts agents separately from members.

## 4. Authorization

### 4.1.1 Roles, teams and field grants apply to agents

- The agent is allowed when its direct, team or field grant allows it.
- A direct workspace role overrides a team role.
- The agent is denied without any grant.

### 4.1.2 Unavailable roles deny

- The agent is denied.
- Stored grants are unchanged.

### 4.2.1 Unavailable agents can't execute

Variants: `a` disabled, `b` trashed, `c` deleting, `d` home workspace trashed, `e` second membership. Each variant runs with and without trash-inclusive checks.

- The agent is denied.

### 4.3.1 No global or template rights

- The agent is denied for instance-wide operations and public templates.

### 4.4.1 Permission checks for people stay as cheap as before

- A permission check for a person does no extra work for agents.

### 4.5.1 Trashed subjects are hidden from grants

- Stored grants are hidden while the agent is trashed.
- Stored grants are unchanged after restore.

## 5. Sign in

### 5.1.1 Human credentials never authenticate an agent

Variants: `a` session token, `b` cached session token, `c` password, `d` database token, `e` MCP key, `f` MCP OAuth token, `g` realtime connection.

- The sign-in is rejected.

### 5.2.1 Human account flows skip agents

- Signing up with an agent's email is rejected.
- Password reset, email verification, password change and email change do nothing for the agent.

## 6. Seats, licenses and personal views

### 6.1.1 Agents use no seats

- No seat is used.
- Assigning a seat to the agent is rejected.

### 6.2.1 Personal views stay human-only

- The agent is denied access to a person's personal view.
- The agent is denied creating, adopting or importing a personal view, also when every user has Premium.

### 6.3.1 Agents get Premium from workspace or instance entitlements

- The agent is allowed when the workspace or the instance has the feature.
- No seat is used.

## 7. Credit and history

### 7.1.1 Stored credits point at the agent

- Created by, last modified by, trashed by and uploaded by store the agent.
- The credit keeps the agent's id and name, also for a trashed agent.

### 7.2.1 Row, automation and audit history

- The credit keeps the agent's id and name.
- The credit keeps the agent's identity kind.

### 7.3.1 Notifications

- The agent can be a notification sender.
- No notification is created for the agent.

## 8. Assign

### 8.1.1 Active agents of the home workspace are collaborators

- The agent is listed.
- Assigning the agent stores it.

### 8.1.2 Unavailable agents are not collaborators

Variants: `a` disabled, `b` trashed, `c` deleting, `d` other workspace, `e` second membership.

- The agent is hidden.
- The value is rejected.

### 8.2.1 Bulk assignment, trash and restore

- Bulk assignment stores the agent.
- No notification is created for the agent.
- The agent's assignments are hidden while it is trashed and return after restore.

### 8.2.2 Import, export and duplicate

- Values, defaults and filters keep the agent inside its home workspace.
- Importing into an other workspace drops the agent.
- A filter on an unavailable agent keeps its value after duplicate and import.
- Permanently deleting the agent clears its assignments.

### 8.3.1 Collaborator metadata

- Every list of available collaborators includes the agent with its identity kind.
- Cell values don't change shape.
- Viewers see minimal agent metadata.
- Loading collaborators takes the same number of queries for any number of members.

## 9. Mention

### 9.1.1 Rich text mentions

- The agent is listed in mention suggestions with the agent icon.
- The saved mention shows the agent's name.

### 9.1.2 Comment mentions notify people only

- The mention keeps the agent's id.
- No notification is created for the agent.

### 9.1.3 An agent authors a comment

- The comment belongs to the agent.
- Mentioned people are notified.
- The agent is not subscribed to the row's comments.

### 9.1.4 Unavailable agents in mentions

Variants: `a` disabled, `b` trashed, `c` other workspace.

- The agent is hidden from mention suggestions.
- No mention is stored for the agent.
- No notification is created for the agent.

## 10. Defer

### 10.1.1 Stored work runs as the agent

- Jobs, exports, snapshots, data syncs and AI field updates run as the agent.
- The job belongs to the agent; another agent can't read it.
- The credit keeps the agent's id and name.

### 10.2.1 Revoked authority stops queued work

Variants: `a` trashed, `b` disabled, `c` membership removed, `d` role removed.

- The queued work fails and changes nothing.

### 10.3.1 Realtime unsubscribes find agents

Variants: `a` active agent, `b` trashed agent.

- Unsubscribing an agent from tables completes without errors.

## 11. Broadcast

### 11.1.1 Agent events

Variants: `a` create, `b` update, `c` delete, `d` restore.

- Only users who can list agents receive it.

### 11.1.2 Team events

- A team change broadcasts the agent's current teams.
- A team change for people broadcasts no agent event.

## 12. Integrations run as an agent

### 12.1.1 Run as the home workspace's agent

- The agent is allowed as the run-as identity of its home workspace.
- The integration lists the databases of the agent's home workspace.

### 12.1.2 Unavailable agents can't be the run-as identity

Variants: `a` disabled, `b` trashed, `c` agent of an other workspace.

- The agent is denied, and the action doesn't fall back to another identity.
- Updating the integration doesn't authorize the agent again.

### 12.1.3 Legacy agent references in imports

- The value is rejected.

## 13. Pickers and settings

### 13.1.1 Subject options

- The default subject options list people.
- Options for agents list active agents.
- The agent is listed with the agent avatar and badge.
- Options never show an agent's synthetic email.

### 13.1.2 Unavailable identities in pickers

- A disabled person is hidden.
- The agent is hidden when it is disabled or trashed.

### 13.2.1 Agent settings

- Settings create, rename, change the role of and trash agents.
- Agent names accept up to 150 characters.

### 13.3.1 Collaborator pickers and cells

- The agent is listed with the agent icon.
- Renames, trash and restore update the shared collaborator state.

### 13.4.1 Agents shown as agents

- Audit log filters, access summaries, team samples and team and field-permission pickers list agents separately from people, with the agent icon.
- History entries show the agent icon after the agent is deleted.

## 14. Migrate

### 14.1.1 Upgrade and guarded rollback

- Existing profiles become people.
- The old agent table is removed.
- Rollback is refused while agents exist and succeeds once they are gone.

### 14.1.2 Legacy data is refused

- The upgrade refuses legacy agent records and references before changing the schema.

### 14.2.1 History snapshot columns

- Upgrading adds the identity kind to row, automation and audit history without changing existing entries.

## Manual checks

Use a workspace with an admin, a viewer and a table with collaborator, created
by, last modified by and rich text fields. Enable agents.

1. Lifecycle: create and rename an agent. The agent is listed in agent settings. The agent is hidden from the member list. No seat is used.
2. Execute: run an integration action as the agent. The credit keeps the agent's id and name.
3. Assign and Mention: the agent is listed with the agent icon. A second browser updates after a rename.
4. Lifecycle: trash the agent. The agent is hidden from current choices. Stored grants are hidden. Restore it: stored grants are unchanged.
5. List people: with an agent admin present, the last human admin still can't leave.
6. Defer: revoke the agent's role before queued work runs. The queued work fails and changes nothing.
