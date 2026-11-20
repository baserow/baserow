# ADR 013: Identities use the User model

|              |                                                |
| ------------ | ---------------------------------------------- |
| Status       | Proposed                                       |
| Date         | 2026-11-02                                     |
| Issue        | https://github.com/baserow/baserow/issues/6259 |
| Author       | Davide Silvestri (@silvestrid)                 |
| Contributors |                                                |

## Summary

An identity is a User whose profile has `user_type="identity"`. It uses the same
workspace memberships and permission grants as a person, so one User record serves
permissions, Created by, Last modified by, collaborator assignments, mentions and
background jobs. Nothing converts between the identity that acts and the user stored
in a foreign key.

Identities replace the earlier Agent permission subject.

## Context

The existing Agent is a workspace-owned permission subject, but most attribution and
assignment fields reference User. Giving each Agent a second User record fixes those
foreign keys at the cost of synchronized names, two representations and conversions.
We keep one record instead: ordinary User queries stay people-only, and shared
permission and collaborator code opts in to identities.

## Terms

| Term              | Meaning                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------ |
| User              | A human user; its profile has `user_type="human"`.                                               |
| Django User       | The shared storage model for users and identities.                                               |
| Identity          | A nonhuman entity stored as a User with `user_type="identity"`, owned by one workspace.          |
| Actor             | The subject whose permissions authorize an operation; also includes tokens and anonymous actors. |
| Agent application | The configured AI application from ADR 011, distinct from its execution identity.                |
| Collaborator      | A user, or an identity where a field allows it, that can be assigned or mentioned.               |
| Subject           | A permission subject, including actors and teams.                                                |

## Decision

### Shared User storage and permissions

Keep Django's User model and add an immutable `human`/`identity` user type to
UserProfile. `AUTH_USER_MODEL` does not change and there is no Agent proxy.

An identity has a User, a UserProfile and one WorkspaceUser membership, which
supplies its workspace. Its workspace role is stored on WorkspaceUser, scoped roles
use RoleAssignment, and team and field grants use the existing User paths. Its stored
subject type is `auth.User`; there is no separate Agent subject.

UserProfile also stores the trash state and last activity of an identity.
`date_joined` is its creation time and `first_name` its only name, limited to 150
characters. Human profiles cannot be trashed, and the user type cannot be edited.

An identity keeps its single membership for life. The operations that add, remove or
change the membership of a person refuse an identity: only the identity handler
writes its role, and removal goes through identity deletion. Permission checks deny
an identity with more than one membership, counting trashed workspaces.
Cross-workspace service accounts and conversion between human and identity are
outside this decision.

### Explicit query boundaries

```python
User.objects.all()                          # Human users, including inactive users
User.objects_and_identities.all()           # Users and identities, including trashed identities
WorkspaceUser.objects.all()                 # Human memberships
WorkspaceUser.objects_and_identities.all()  # Memberships of users and identities
WorkspaceUser.objects_and_identities_and_trash.all()  # Also in trashed workspaces
```

`User.objects` and the default WorkspaceUser managers, and therefore
`workspace.workspaceuser_set`, return people only, so member administration,
invitations, seat counts and code outside this repository never see an identity by
accident; see Alternatives. The people filter positively matches `human`: a missing
or unknown profile is not a person. Django's base manager stays unfiltered so foreign
keys resolve identities, and a User and its profile are created atomically.

Permission checks and identity management opt in through the `objects_and_identities`
managers. On WorkspaceUser it leaves out trashed workspaces like `objects`, and
`objects_and_identities_and_trash` includes them like `objects_and_trash`. A forgotten
opt-in denies an identity instead of listing or billing it.

### Types and runtime classification

An identity is not a separate model, wrapper or type alias: a type checker cannot
tell the two kinds apart, so an annotation would promise what it cannot check.
`is_human(value)` and `is_identity(value)` read the profile's user type. A missing or
unknown type matches neither, and neither says that a user is active or authorized.
These checks at the human-only boundaries and the people-only default managers
enforce the distinction. RBAC `Actor` and `Subject` keep their meanings.

Subject code does not repeat the check. Both kinds are stored under the `auth.User`
subject type, which holds what they share and forwards what differs to a human or an
identity specific type. Resolving that specific type is the only place in subject
code that reads the user type; looking up the stored type never reads the profile.

### Identity execution and user sign-in are separate

`is_active` means enabled for both kinds. Sign-in and every existing human credential
(cached JWT, WebSocket, SSO, database token, MCP and OAuth) require the `human` type.
Identities have unusable passwords, synthetic unique addresses under
`identities.invalid`, and neither staff nor superuser status.

A later credential, such as an identity token, can let MCP authenticate as an
identity. Calls then use the identity's current permissions, limited by the
credential's scope, and a disabled or trashed identity cannot act. This is future
work.

Permissions reuse the existing membership and role managers:

- Membership checks already require an active member that is not pending deletion.
  For an identity they also require that it is not trashed and has a single
  membership.
- Managers that grant access outside workspace membership stay people-only, and the
  member manager denies an identity every check or query without a workspace.
- A missing or unknown user type is denied. Checks and queryset filtering follow the
  same rules.
- A trashed identity, or one in a trashed workspace, cannot act even with
  `include_trash=True`. This tightens the earlier behavior, which counted trashed
  Agents and workspaces. People can still inspect and restore trashed identities.
- Inside its workspace an identity uses ordinary workspace, scoped, team and field
  permissions. New identities get NO_ACCESS with RBAC and MEMBER otherwise, and team
  fallback is unchanged.
- An identity whose stored role is unavailable after an edition or license change is
  denied, never given a more permissive role.

Identities produce audit events but no undo history or human analytics; the
specific subject type says which. They cannot own
personal views, receive notifications, occupy a license seat or count as the
remaining human administrator. Feature access follows the existing workspace and
instance entitlements.

### Lifecycle and configuration

Creating an identity creates its User, profile and membership atomically. Trashing
keeps the identity, membership, grants and historical credits, blocks execution and
hides it from collaborator choices. Restoring keeps the same User ID and does not
re-enable an identity that was disabled separately.

The profile takes part in the existing `identity` trash type. Its trash item can use
the profile ID; public identity IDs are always User IDs. Permanently deleting an
identity or its workspace must remove the User, including through ORM cascades.

An Agent application keeps its own configuration and lifecycle: deleting it never
removes the identity. It acts in the workspace as the identity it runs as, stored as
`auth.User` and the identity's User ID. It never runs as a person: a binding resolves
only to an active identity of the application's workspace. A trashed identity reports the binding as trashed, so it can
be restored; a disabled, deleted or foreign one reports it as missing. Either way the
application has no workspace access until someone picks an active identity.

Binding an Agent application or a Local Baserow integration to an existing identity
takes the permission to bind identities, held by workspace builders and admins, and
by every member without role-based access. Everyone who can edit the bound
application then acts with the identity's access, which can exceed their own; this is
accepted so builders can use the identities admins create. Creating, editing and
deleting identities stays with admins. Keeping or clearing a binding needs no extra
permission, and run-as choices list no identities for someone who cannot bind them. A duplicate or a restored snapshot is a new binding, also when the original
lost its own since, so it keeps the identity only when the person who makes it may
bind identities. Otherwise an Agent application loses its run-as and a Local Baserow
integration is authorized as that person, as an import from another workspace is.

Every shared tool entry point starts a new permission lifetime per call, so a revoked
or trashed identity stops acting on the next call even when the caller reuses its
tool context. MCP refuses to register a tool function that skips this boundary.

### Attribution, assignments and deferred work

User foreign keys store the acting User. Jobs and scheduled work run as their stored
User and recheck its current permissions. Generic actor histories remain because
tokens and anonymous actors still exist. Row history, automation history and audit
records snapshot the user type next to the name, so the kind survives deletion; old
records and other actor kinds leave it null. User subject metadata includes the kind.

Collaborator fields can opt in to identity assignments.

- A collaborator field with `include_identities` accepts the active identities of its
  workspace. Without it, pickers, paste, validation and cell values are human-only.
- Turning that option off deletes the identity assignments, because hidden values
  would still count in filters, formulas and aggregations and would reappear if the
  option came back. The field update backs up the column first, so it can be undone.
- Rich text fields suggest people for mentions. Existing identity mentions keep
  their display names.
- Row comments can mention identities, and identities can author comments through
  the tools of an Agent application.

Identity names and icons update through realtime events. Public collaborator cell
values keep their shape. Exports write an identity as `Name <identity>`, since its
synthetic address is not an email. Identities never receive email or in-app
notifications and are never subscribed to row comment notifications; a later trigger
or setting can let one react.

## Alternatives

- **Keep Agent plus User:** preserves class-based separation, but requires two
  representations, synchronized names and conversions throughout deferred work.
- **Move Agent fields to Profile but keep separate permissions:** removes a table
  while retaining parallel membership and role handling.
- **Make `User.objects` return users and identities:** matches the storage model,
  but it is Django's default manager. Existing call sites, seat counts, login,
  password reset and code outside this repository would silently include identities;
  a forgotten opt-in should hide an identity, not bill, email or authenticate it.
- **Replace Django's User model:** would support fields directly on User, but is a
  much larger change across the existing foreign-key graph.
- **Register identities under their own subject type name:** shows the kind in
  every stored reference, but one row could then be stored under two type names
  and nothing in the database rejects the wrong one. The identity subject type
  therefore keeps the `auth.User` name.

### A Subject table that users and identities both point to

The alternative studied in most depth keeps identities out of the User table. A new
Subject table holds one row per user and per identity, and whatever records who did
or owns something points at a Subject instead of a User.

| | Subject table | Shared User storage (this decision) |
|---|---|---|
| References to move | 52 columns in 9 apps with foreign keys, plus the author and collaborator columns of every user table | None |
| Table inheritance | Not possible: the User table belongs to Django and cannot become a child of Subject. The link goes through the profile and is kept by code, not by the schema | No link to keep |
| Reaching the actor behind a reference | The Subject's type says which table to read, so loading the actors behind a list takes one query per subject type, like a generic foreign key | A foreign key to User |
| Kinds of reference | Three: User foreign keys, Subject foreign keys, and the type and id pairs of roles and integrations, with a different id for the same non-human | Two as today, with one id |
| Work per subject type | A feature only gets what a Subject exposes: name, key and state. Synchronizing, resolving, selecting, importing and exporting need hooks that every subject type implements and every feature tests per type | The same User fields and code for both kinds |
| Code reading the references | Receives a Subject and converts it back to a user or identity | Unchanged, an identity is a User |
| Jobs started by an identity | The required user of all 21 job types becomes a Subject while queued and running jobs still hold user ids, and about 40 places that read it convert it back | The job stores the identity as its user and runs as it |
| Comments and mentions | The author and the mentioned users of comments and rich text become Subjects, each in its own table | An identity authors and is mentioned as a User |
| Notifications | A Subject as sender next to recipients that stay Users | The identity is the sender, recipients stay people |
| Trash, files, views and snapshots | Who trashed, uploaded, owns or created something each needs its own column to move | The existing columns hold the identity |
| Data sync and AI fields | The user they run as becomes a Subject, resolved before each run | They run as the stored identity |
| Copies of a name and email | Two, synchronized by code that bulk updates, raw SQL and older workers bypass | One |
| Deleted accounts | Leave a Subject that keeps the name and email, so erasing personal data needs its own step | Unchanged |
| Ids | Subjects reuse user ids and identities draw from the user sequence, so resetting it collides | One row per id |
| Schema change | New tables, every user copied into them, and both kept in sync until the switch | Three new profile fields |
| Stored formats | Collaborator values in formula cells and the import and export format change | Unchanged |
| What stays on User | Sign-in, sessions, two-factor authentication, OAuth grants, tokens, invitations and license seats; 8 of the 52 columns belong to Django and the OAuth library | Nothing moves |
| Human-only rules | Still needed: an identity cannot sign in, take a seat or own a personal view | Needed, stated by the default managers and the subject types |

The Subject table never becomes the only way to say who: every feature keeps
choosing between a Subject and a User, and each one is converted separately.

## Consequences

Shared User storage removes synchronization and makes every existing User foreign key
work for identities. Shared memberships reuse roles, teams and field grants.

The cost is that human-only behavior must be explicit. The people managers are a
query default, not an authentication or permission boundary, so new code must tell
account behavior for people apart from operations open to both.
