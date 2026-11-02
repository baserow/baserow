# ADR 013: Agents use User identities

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-11-02                                     |
| Issue        | https://github.com/baserow/baserow/issues/6259   |
| Author       | Davide Silvestri (@silvestrid)                   |
| Contributors |                                                |

## Summary

An agent identity is a User whose profile has `identity_type="agent"`. It uses
the same workspace memberships and permission grants as a person. We remove the
`Agent` model and `core_agent` table.

This gives an agent one identity for permissions, Created by, Last modified by,
collaborator assignments, mentions and background jobs. There is no conversion
between the identity that acts and the user recorded in a foreign key.

## Context

The existing Agent is a workspace-owned permission subject. It can act through
Local Baserow integrations, but most attribution and assignment fields reference
User. Giving each Agent a second User identity solves those foreign keys while
adding synchronized names, two representations and conversions for background work.

We instead make the distinction between a person and an agent explicit. Ordinary
User queries remain people-only. Shared permission and collaborator code opts in
to agents.

## Terms

| Term | Meaning |
| --- | --- |
| Person | A User with profile identity type `human`. |
| Agent identity | A User with profile identity type `agent`, owned by one workspace. |
| Actor | The subject whose permissions authorize an operation; also includes tokens and anonymous actors. |
| Agent application | The configured AI application from ADR 011, distinct from its execution identity. |
| Collaborator | A person or agent identity that can be assigned or mentioned in a workspace. |

## Decision

### One identity and shared permissions

Keep Django's existing User model. Add an immutable `human`/`agent` discriminator
to UserProfile; do not change `AUTH_USER_MODEL` or introduce an Agent proxy.

An agent has a User, a UserProfile and a WorkspaceUser membership. Its workspace
role is stored on WorkspaceUser, scoped roles use RoleAssignment, and team and
field grants use the existing User paths. Its persisted subject type is
`auth.User`. The `core.Agent` subject registration disappears.

UserProfile also stores trash state (agents can be trashed and restored) and last
activity. User's `date_joined` supplies creation time and
`first_name` is the single name. Agent names therefore use the User limit of 150 characters. Human profiles cannot be trashed.

The agent's single WorkspaceUser membership supplies its workspace. Membership
writes lock the User row and check all memberships, including those in trashed
workspaces, to prevent a second membership. Standalone removal or reassignment
is forbidden; removal goes through agent deletion. Identity type cannot be changed
through profile editing. Cross-workspace service accounts and human/agent conversion
are outside this decision.

### Explicit query boundaries

```python
User.objects.all()               # People, including inactive people
User.identities.all()            # People and agents, without trashed agents
User.identities.agents()         # Agents, without trashed agents
User.identities_and_trash.all()  # All identities, including retained agent credits
```

`User.objects` stays people-only even though every identity is a User; see
Alternatives.

Django's base manager stays unfiltered so foreign keys resolve every identity.
The people predicate positively matches `human`; a missing or unknown profile
does not become a person. User and profile creation is atomic.

WorkspaceUser queries do not inherit User manager filters. Shared membership
query helpers distinguish people from agents. Member administration, invitations,
seat counts and last-human-admin checks select people; permission checks select
both kinds. Agent management remains in the existing agent settings/API.

### Agent execution and human sign-in are separate

`is_active` means enabled for both identity kinds. Human sign-in and existing
human credential flows require identity type `human`, including cached JWT,
WebSocket, SSO, database token and current MCP/OAuth credentials. Agents have
unusable passwords, synthetic unique addresses under `agents.invalid`, and neither
staff nor superuser status.

Future MCP access can authenticate as an agent using an explicitly issued agent
token or another revocable machine credential. Calls are attributed to the agent
User and use its current workspace permissions, further limited by credential
scope. The issuer's permissions authorize issuance, not subsequent calls.
Disabled or trashed agents cannot execute even with a valid credential. This
change keeps human credential flows separate; the agent credential mechanism
will be implemented later.

Reuse the existing membership and role permission managers. User membership
checks already enforce workspace membership, active status and pending deletion;
extend them to check agent trash state and the single-workspace rule. Managers
that currently grant access only to human Users must explicitly retain that
restriction when agents become Users. Extend the existing member manager to deny
agent checks and queries without a workspace. Missing or unknown identity metadata denies
access, and the same membership rules apply to checks and queryset filtering.

A trashed agent, or one in a trashed workspace, cannot execute even with
`include_trash=True`. This deliberately tightens current behavior, which lets
trash-inclusive checks count trashed Agents and workspaces.
Humans can still inspect and restore trashed agents through the existing trash flow.

Within that boundary, agents use ordinary workspace, scoped, team and field
permissions. New agents default to NO_ACCESS with RBAC and MEMBER otherwise.
Preserve existing team fallback semantics. An
unavailable stored agent role denies access after an edition/license change;
it is never silently replaced by a more permissive role.

Interactive behavior uses a shared human predicate instead of `isinstance(User)`.
Agents produce audit events, but no interactive undo history or human analytics.
They cannot own personal views, receive human notifications, consume human seats
or satisfy the requirement for a remaining human administrator. Feature access
uses the existing workspace/instance entitlement rules; agents are not assigned
human LicenseUser seats.

### Lifecycle and configuration

Agent creation atomically creates the User, Profile and membership. Trashing keeps
the identity, membership, grants and historical credits while blocking execution
and hiding the identity from current collaborator choices. Restore keeps the same User ID
and does not reactivate an independently disabled identity.

Profile stores agent trash state and participates in the existing `agent` trash
type. Its internal trash item ID can be the Profile ID; public identity IDs are
always User IDs. Permanent agent/workspace deletion must explicitly remove the
owned User, including when deletion happens through ORM cascades.

An AgentApplication retains its own configuration and lifecycle. Duplicating,
restoring or deleting an application must not implicitly copy or remove execution
authority. Existing run-as bindings resolve User identities. New application
execution features are outside this change.

### Attribution, assignments and deferred work

User foreign keys store the acting User directly. Jobs and scheduled work execute
as their stored User and recheck current permissions. Generic actor histories
remain because tokens and anonymous actors still exist. Row history, automation
history and audit records snapshot identity kind as well as name, so the distinction
survives deletion. New User actors record `human` or `agent`; old records and other
actor kinds can leave the snapshot null. User subject metadata also includes kind.

Collaborator and mention queries include eligible workspace agents explicitly.
Agent names and icons update through existing realtime events. Public collaborator
cell values keep their existing shape. Notification recipients remain humans.

### Removal and migration

Preserve historical migration `0121_agent.py`. Add one new core migration that
adds Profile fields with database defaults/nullability and removes Agent. Remove
all runtime model imports, `core.Agent` registrations, queries and client branches.

This design does not carry a general legacy Agent conversion system. Before any
schema changes, the migration checks for old Agent rows and persisted references
that would become invalid. If found, it stops with an actionable error and leaves
the data intact. Nonproduction cleanup or conversion requires a separate explicit
decision; the migration must never reinterpret an Agent ID as an existing User ID.
Old imports with `core.Agent` authorization are rejected clearly, without falling
back to the importing person's authority. Reverse migration refuses to remove the
Profile discriminator while agent identities exist; otherwise an enabled agent
could become a human account to older code. History snapshot fields have small
companion migrations in their owning apps.

## Alternatives

- **Keep Agent plus User:** preserves class-based separation, but requires two
  representations, synchronized names and conversions throughout deferred work.
- **Move Agent fields to Profile but keep separate permissions:** removes a table
  while retaining parallel membership and role handling.
- **Make `User.objects` return every identity:** matches the User definition,
  but it is Django's default manager. Existing call sites, seat counts, login,
  password reset and code outside this repository would silently include agents;
  a forgotten opt-in should hide an agent, not bill, email or authenticate it.
- **Replace Django's User model:** would support fields directly on User, but adds
  a much larger migration across the existing foreign-key graph.

## Consequences

Shared identity removes synchronization and makes existing User foreign keys work
for agents. Shared memberships reuse roles, teams and field grants.

The cost is making human-only behavior explicit. The people manager is a query
default, not an authentication or permission boundary. New code must distinguish
human account behavior from operations available to both identity kinds.
