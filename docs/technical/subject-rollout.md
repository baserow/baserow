# Retained row identities

`core.Subject` represents attribution, never authentication or authorization.
Its `type` uses the existing actor registry names (`auth.User`, `core.Agent`).
UserProfile and Agent retain their separate concrete actor links. Agent API IDs
and typed permission references remain Agent IDs; row fields use Subject IDs.
UID is portable metadata, not a credential. Public field responses expose only
`id`, `name`, and `type`.

Subject has no independent sequence. Humans use their User ID; Agent and retained
import identities reserve IDs using `nextval(pg_get_serial_sequence(...))` on the
configured User table. Never reset that sequence to the maximum live User ID:
retained and non-human identities also occupy it.

Python lifecycle hooks synchronize names, UIDs, links and deletion states via
`SubjectType`. Core iterates registered types at startup and calls their
`register_lifecycle_signals()` hook; each type owns its signal senders and callbacks.
Account handlers, Django admin, Profile saves and Agent saves use
transactions so identity changes commit with the actor. The User model and its
columns are unchanged. Deleting the actor retains its last attribution. A Subject
with no live eligible actor cannot execute work.

`QuerySet.update`, `bulk_create`, raw SQL and older workers bypass these hooks.
Bulk account creation must explicitly synchronize Subjects and link Profiles in
its transaction, as the `fill_users` command does. Reconcile after older workers
drain and before switching consumers. Custom account writers must use an atomic
transaction around User saves and their synchronous signal handlers. If an older
worker renames and deletes an actor before reconciliation, its retained identity
keeps the last synchronized metadata; that intermediate rename cannot be recovered.

Collaborator assignment never grants access. Mentions continue to use User IDs.

## Subject types

The base type and registry live in `core/subject/registries.py`. UserSubjectType
lives in `core/user/subject_types.py`, and AnonymousUserSubjectType lives in
`core/subject/subject_types.py`. The original
`core.registries` and `core.subjects` imports remain compatibility re-exports;
callers can migrate and these aliases can be removed in a follow-up.

Persistent attribution is an explicit `SubjectType` capability:
`supports_persistent_subjects` defaults to false. Types own lifecycle synchronization, actor resolution,
workspace selection predicates, reference activation, reconciliation checks,
legacy portable-value recognition, manifest metadata export and human-readable
formatting. Selection
combines their predicates into one query; import caches activation checks.
Registering a permission actor alone never enables field attribution.
`SubjectHandler` coordinates selection, actor resolution and import/export through
these hooks, including packing and unpacking the identity manifest.

The frontend uses registered subject types for collaborator display names and
avatars, and `isUser()` for User-only mention eligibility. Historical migrations
remain self-contained and do not depend on the live registry.

## Deployment

1. Apply `core.0136_subject` for nullable links and the identity tables. Commit
   this DDL before doing data work. No generated user-table columns, collaborator
   through-table columns or indexes change.
2. Apply the non-atomic, retryable bounded Python backfill in
   `0137_backfill_subjects`, then deploy Python synchronization. Older consumers
   and workers can still use human IDs. Agent field references remain disabled.
3. Drain older workers/backends. Run `just b m reconcile_subjects`. This catches
   deployment-window writes and verifies each live User's profile, ID and cache.
4. Deploy Subject-aware consumers. Keep Agent references disabled until every
   User-based consumer has drained.
5. Run `just b m reconcile_subjects --enable-agent-references`. The persisted gate
   and existing `agents` feature flag must both be enabled for Agent attribution
   and collaborator selection.

Once activated, rollback must retain Subject-aware readers. Disabling the gate
prevents new Agent selections but does not erase existing Agent attribution.
Returning to User-based readers requires handling those references first.

## Formula name compatibility

New collaborator formula results contain `id`, `name` and `type`; they never
emit `first_name`. Stored legacy JSON remains readable through the formula
serializer and SQL compatibility readers used by search, filtering and text
conversion. When both keys exist, `name` takes precedence. Ordinary collaborator
serialization reads `name` directly. No stored-value rewrite is required.

Backends and workers that only read `first_name` must be drained before enabling
name-only formula writers. The Agent-reference gate does not gate this JSON format
change; a rolling deployment needs a prior release of compatible formula readers.

## Portable exports

Each exported table partitions the workspace's version 1 `identity_manifest`.
Author columns, collaborator values, filters and view defaults use manifest
references. Entries contain type, UID and cached name. Import hooks also accept
legacy human email values. Source numeric IDs are never assigned to destination
identities. Eligible live workspace identities are matched; unmatched portable
identities become retained, unselectable attribution. Import never creates an
executable Agent, credentials, roles or permissions. Snapshots and duplication
use the same mapping. Human-readable exports preserve human email formatting (author emails and
collaborator `Name <email>` values), and use `Name <UUID>` for Agents.
