# ADR 013: Agents are stored in user foreign keys through an agent user

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-10-29                                     |
| Issue        | https://github.com/baserow/baserow/issues/6259 |
| Author       | Davide Silvestri (@silvestrid)                 |
| Contributors |                                                |

## Summary

Agents now change data: they create, update and delete rows, tables, fields and views.
Every place that records who did something, and every place a person can be picked, is
a foreign key to `auth.User`, so today an Agent's work is recorded as nobody and an
Agent can't be assigned a row. Each `Agent` subject gets an agent user: an `auth.User`
row that can't sign in and belongs to no workspace, written into user foreign keys in
the Agent's place. Permission checks keep running as the `Agent` subject.

## Terms

| Term            | Meaning                                                                                                                     |
| --------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `Agent` subject | The core permission subject with a workspace role, see [ADR 011](011-agent-applications.md). An Agent acts as one.          |
| Actor           | Whoever performs an operation and is permission checked: a user or an `Agent` subject.                                      |
| Agent user      | The `auth.User` row of one `Agent` subject, with the same id. It is stored in user foreign keys in the Agent's place and is never an actor.   |
| Collaborator    | Someone a row can be assigned to or mention: a member of the workspace, or the agent user of one of its non-trashed Agents. |

## Context

Agents act on their own. Local Baserow integrations run as an `Agent` subject (#6064),
and Agent Builder tools create, update and delete rows, tables, fields and views as the
`Agent` subject their Agent runs as (#6540, #6543). The permission side handles this
well: the workspace permission managers accept both actor types, and an `Agent` subject
can't sign in, receive email, take a seat or appear among members.

Recording who did something is where it falls short. About 75 model fields reference
`auth.User`, and they fall in four groups:

| Group                  | Fields                                                                                                                                                              | Today, when an Agent acts                                                                                                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Who did it             | Row `created_by` and `last_modified_by`, `TrashEntry.user_who_trashed`, `View.owned_by`, `Notification.sender`, `UserFile.uploaded_by`                              | Null for rows, row trash, row notifications and files, and an edit erases the previous editor. Trashing anything else, creating a view or sending any other notification raises an error. |
| Stored now, acts later | `Job.user` (about 20 job types), `AIField.ai_auto_update_user`, data sync `authorized_user`                                                                         | Jobs refuse non-user actors. AI auto-update and data sync store the Agent's id as a user id: an unrelated user.                                                                           |
| Picked as a target     | Collaborator field values, rich text mentions, row comment mentions                                                                                                 | Only workspace members are accepted                                                                                                                                                       |
| People only            | Sign-in providers, 2FA, `WorkspaceUser`, invitations, tokens, MCP endpoints, OAuth, `LicenseUser`, notification recipients, `Action.user`, templates, conversations | Never an Agent                                                                                                                                                                            |

`RowComment.user`, `Snapshot.created_by` and `ImportExportResource.created_by` record who
did something too, but no Agent can comment, snapshot or import yet.

Non-user actors were handled one place at a time. `user_for_row_audit_columns` stores
null for rows, row trash and row notifications; jobs refuse them; `is_interactive_user`
drops the uploader of a file. A few tables gained a generic actor (subject type and id):
row history, the audit log, automation history and the authorized subject of Local
Baserow integrations. A generic actor can't reach the rest. `created_by`,
`last_modified_by` and collaborator values are a column or a through table inside every
user table, so storing an `Agent` there would mean a schema change in every table of
every database.

Agents are still behind the `agents` feature flag, so production holds no Agent data
that a migration would have to carry.

Scope: the first three groups. Agent Builder applications are out of scope: they act as
the `Agent` subject they run as, so that subject is what gets credited and assigned.

## Decision

### 1. Every `Agent` subject has an agent user

`Agent.user` is a nullable one-to-one link to `auth.User` (`on_delete=PROTECT`, related
name `agent`). On creation, `Agent.save()` creates the agent user and takes its id. A
CHECK constraint enforces `Agent.id == Agent.user_id` whenever the user exists. Agents
must not be created with an explicit id or user, or with `bulk_create`, which skips
`save()`. The agent user is built so it can never be a person:

- `email` and `username` are `agent-<uuid>@agents.invalid`. The `.invalid` top-level
  domain is reserved (RFC 2606), so no email is delivered and no SSO identity matches.
- `is_active=False` and an unusable password, so no sign-in or token is accepted.
- No `WorkspaceUser` row, so it is in no member list and holds no role.
- `first_name` is the Agent's name, kept in sync on rename.
- A `UserProfile` with the default language and UTC. Collaborator queries join the
  profile, and it is where an Agent's language (table and field names it creates) and
  timezone are read from.

Agents created before this change are legacy Agents. They keep a null `user` and
their existing ids, roles and integrations. They receive no credits and cannot be
assigned or mentioned until deleted and recreated. Conversions always follow the
`user` relation: a legacy Agent can have the same id as an unrelated person.

The agent user lives as long as the Agent. Trashing an Agent keeps its agent user, so credits keep
showing its name. Deleting an Agent permanently, alone or with its workspace, deletes its
agent user right after, which then reads as a deleted person does.

### 2. Two conversions, never an agent user as actor

| Function            | Meaning                         | User     | `Agent` subject                  | Other actors (anonymous, token) |
| ------------------- | ------------------------------- | -------- | -------------------------------- | ------------------------------- |
| `user_for_actor(a)` | The user stored for an actor    | The user | Its agent user                   | None                            |
| `actor_for_user(u)` | The actor a stored user acts as | The user | (given its agent user) The Agent | n/a                             |

Both are `SubjectType` hooks behind two `subject_type_registry` methods, so generic code
never checks for Agents. Code that stores an actor in a user foreign key calls
`user_for_actor`. Code that acts for a stored user calls `actor_for_user`. A trashed
Agent is returned as is: it isn't in its workspace, so permission checks deny it.

If the rule is broken, the agent user is an inactive user with no workspace, so every
permission check denies it: the failure is closed, never a wrong grant.

`user_for_actor` replaces `user_for_row_audit_columns`, and an actor's language and
timezone are read from `user_for_actor(actor).profile`.

### 3. Who did it

Every "who did it" field stores `user_for_actor(actor)`. The conversion sits where the
field is written: `TrashHandler.trash` (all trash callers),
`NotificationHandler.construct_notification` (all notification types), row creation and
update, view creation and file uploads from Local Baserow. An Agent's edit now sets Last
modified by to the Agent instead of erasing it. Row comments, snapshots and import
resources follow the same rule once an Agent can reach them.

Duplicating a table or application, restoring a snapshot and importing map these users by
email through the workspace's collaborators (section 5), so an Agent's credits survive
inside its workspace.

### 4. Stored now, acts later

- **Jobs.** `Job.user` stores `user_for_actor(actor)`. Job types act as `job.actor`, which
  is `actor_for_user(job.user)`, and job lookups and listings filter on
  `user_for_actor(actor)`. Agents can then duplicate, import and export like people.
  Snapshot jobs, which reuse `Snapshot.created_by` as the actor, do the same.
- **AI field auto-update and data sync.** `ai_auto_update_user`, data sync
  `authorized_user` and periodic sync `authorized_user` store `user_for_actor(actor)`, and
  later runs act as `actor_for_user(...)`. Today these store `user.id`, which for an
  Agent is its own id read as a user id: an unrelated user, whom later runs would act as.
  No Agent tool creates AI fields or data syncs yet, so this hasn't been reachable.

### 5. Agents are collaborators

A workspace's collaborators are its members (users with a `WorkspaceUser` row) plus the
agent users of its non-trashed Agents, defined by one query in `CoreHandler`. Every place
that checks membership for a collaborator or a mention uses it instead of `WorkspaceUser`:

- collaborator values: validation, bulk validation, the related-manager filter on the
  generated through table, random values, and import and export by email;
- `available_collaborators`, which feeds the collaborator, Created by and Last modified
  by pickers and filters;
- collaborator and Created by / Last modified by view filters, and formula export;
- the email mapping used when duplicating, restoring and importing (section 3);
- rich text mentions and row comment mentions.

While an Agent is trashed, its assignments are hidden the way a removed member's are, and
they return on restore.

In the frontend, each workspace carries its Agents as `{id, user_id, name}` next to
`users`, sent to every member and kept current by the Agent realtime events. Collaborator
lookups (names, sorting, copy and paste, mentions) go through one store getter that
includes them. Collaborator pickers list Agents in their own group, and chips, Created by
and Last modified by show an Agent icon for those user ids.

### 6. People-only places leave agent users out

Most already do, because an agent user is inactive, has an unusable password and has no
`WorkspaceUser` row: password and SSO sign-in, password reset, JWTs and WebSockets, API
and MCP tokens, impersonation, member lists, invitations and seat counting.

`User.objects` and Django's default user manager return people only, including
inactive people. Agent users are hidden automatically, even when their Agent is
trashed. Admin pages, user counts, seat assignment and user actor options therefore
need no per-query exclusion helper.

Code that intentionally reads both people and agent users uses
`User.objects_and_agents`. This includes collaborator queries, Agent-user cleanup,
and username/email uniqueness checks. Django's base manager stays unfiltered so
stored user foreign keys, including credits and job owners, still resolve Agent
users. The generated-table foreign-key reader follows the same rule.

The managers are installed on the concrete user model during application startup.
Django's historical auth models and migration state keep their original manager;
no auth schema or data migration is needed.

Notification recipients skip inactive users. Agent users are inactive, and deactivated
people can't sign in to read a notification anyway. This covers collaborator
assignments, mentions, comment subscriptions and data sync deactivation.

### 7. What stays as is

Row history, the audit log, automation history and Local Baserow integrations keep
storing the `Agent` subject itself as a generic actor: they record the actor, and they
also record actors that have no user (anonymous, tokens). New "who did it" fields use a
user foreign key filled by `user_for_actor`. Agents still create no undo actions.

## Options considered

### 1. Keep a separate actor and handle each user foreign key on its own

Each new place an Agent reaches gets an `isinstance` branch or a generic actor column.

- Pro: no new rows; everything that doesn't know about Agents fails closed.
- Con: the cost grows with every feature an Agent can use, and the per-table columns and
  collaborator through tables can't take a generic actor, so Agents are never shown in
  Created by or Last modified by and can never be assigned a row.

### 2. Agents are users

The `Agent` subject is replaced by a `User` with a flag, holding a `WorkspaceUser` row.

- Pro: every foreign key, permission check and picker works unchanged.
- Con: it fails open. Every place that lists, counts, emails or signs in people would need
  to leave Agents out: about 117 `User.objects` and 58 `WorkspaceUser.objects` uses, seat
  counting, the admin users page, invitations, password reset and SSO. Forgetting one
  bills an Agent as a seat, emails it, lists it as a member or lets someone sign in as it.
  `auth.User` isn't a custom model, so there is no single flag to filter on either. The
  `Agent` subject's roles, teams and field permissions from #5851 would need migrating.

### 3. An agent user next to the `Agent` subject (chosen)

The `Agent` subject stays the actor; its agent user only fills user foreign keys.

- Pro: every user foreign key works, including per-table columns and collaborator values.
  Permissions keep failing closed: the agent user has no `WorkspaceUser` row, so code that
  wrongly uses it as an actor is denied. The work from #5851 and #6064 stays.
- Con: two rows per Agent, kept in sync. The default user manager must hide agent
  users, and code that needs them must use `objects_and_agents`. Code that reads a
  stored user and acts on it must map it back to the `Agent` subject.

## Consequences

Easier:

- An Agent is credited wherever a person is: Created by, Last modified by, trash,
  uploaded files, notifications it sends, views and jobs it creates.
- Agents can trash tables, fields, views and anything else. Today that raises an error.
- Rows can be assigned to Agents and Agents can be mentioned, which later lets an
  assignment start an Agent.
- Agents can run jobs, AI field auto-update and data syncs.
- The per-place branches for non-user actors go, and new features reach Agents without
  new branches.

Harder, and the costs we accept:

- Two rows per Agent. `AgentHandler` keeps the agent user's name in step, and a delete
  receiver removes it with the Agent.
- Deactivated people stop receiving notifications and notification emails.
- Everyone writing code that stores or loads an actor must use the two conversions.
  Getting it wrong fails closed, so it shows up as a denied action in tests, not as a
  leak.
- Agent names and agent user ids become visible to every member of the workspace, as
  member names are. Under role-based access, Viewers, Commenters and Editors see them
  even though they can't list Agents. Roles and settings stay behind the Agents
  permission.
- License checks made per user see the agent user, which holds no seat. Features
  licensed per seat aren't available to Agents unless the workspace or instance has the
  license.
- Collaborator values are exported by email. An Agent assigned in an exported table is
  dropped when imported into another workspace, like a person who isn't a member there.
- Rows Agents changed before this decision keep a null Created by or Last modified by:
  the actor wasn't recorded, so it can't be backfilled.

Migration and rollout:

- `Agent.user` is added as a nullable column with the same-id CHECK constraint.
  Existing Agents, including trashed ones, remain unchanged. The migration advances
  the user sequence above all existing Agent ids, preventing collisions when new
  Agents take their users' ids. No existing actor references are rewritten.
- The column stays nullable for zero-downtime deploys and legacy Agents. Agents are
  behind the `agents` feature flag. Re-keying legacy Agents, if ever needed, belongs
  in an opt-in management command because it must update every typed actor store.
- An Agent created by the previous backend during the rollout overlap has no agent user
  and keeps today's behavior: null credits, not assignable. This is accepted as the
  feature is flagged.

Follow-up work:

- The Agent Builder stack (#6543) replaces its own `isinstance` branches for table
  language and view `owned_by` with `user_for_actor`.
- Personal views stay unavailable to Agents: the premium permission manager denies them
  to non-user actors.
- Starting an Agent when a row is assigned to it, or when it is mentioned, is a separate
  decision.

## Revisit triggers

- Agents need to sign in or hold their own API tokens.
- Baserow moves to a custom user model, where a user kind could replace the separate
  `Agent` row.
