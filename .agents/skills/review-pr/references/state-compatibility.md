# State, lifecycle, and compatibility review

Use this reference for models or stored values, migrations, feature flags,
import/export, duplication, trash/restore, undo/redo, caches, realtime, Celery, saved
expressions or result shapes, and any change whose behavior differs over time.

## Model the state over time

For each persisted or derived value, identify its authoritative producer, complete
source inputs, invalidators, consumers, and recovery path. Exercise the applicable
timeline: absent, created, edited, saved, reopened, executed, failed, retried,
concurrently changed, restarted, disabled, restored, and removed.

- Missing, null, empty, false, zero, inherit, clear, not-loaded, invalid, skipped,
  partial, and failed remain distinct wherever behavior or recovery differs.
- Resolve mutable configuration once for a logical operation, or lock/version it.
  Preflight, authorization, quota, execution, stored result, and UI metadata cannot
  describe different snapshots.
- Async completion carries resource identity and generation. It cannot overwrite a
  replacement or newer edit; cleanup removes only state created by that invocation.
- Any ordering used for execution, permissions, or output is total and deterministic
  with an explicit tie-breaker. Correlate filtered/reordered collections by stable id,
  not position.

## Apply the lifecycle matrix selectively

For a new or changed persisted concept, check every path that can carry it:

- create/update, bulk variants, direct API and internal calls;
- duplicate at field/table/application/workspace level;
- export/import, templates, snapshots, and id/path remapping;
- trash, restore, permanent delete, user deletion, and workspace deletion;
- undo/redo, retries, partial failure, and action grouping;
- type conversion, dependencies, history, webhooks, automations, notifications, and
  search/indexing;
- public/restricted endpoints, every applicable view/surface, and realtime payloads;
- feature flag on/off and existing objects created while the flag was enabled.

Alternate entry points must preserve the same validation, permissions, audit,
signals, cache/index invalidation, broadcasts, and derived-state updates as the
ordinary path. Do not mechanically apply irrelevant lifecycle cases; explain which
ones carry the changed contract.

## Persisted and derived compatibility

- Once users can save, reference, export, or cache a shape, treat it as a public
  contract even when its class is internal. Account for old JSON, samples, formulas,
  schema paths, cached metadata, and stale browser state.
- A semantic change to materialized values needs scoped recalculation/backfill or an
  explicit operator/user recovery plan. Old untouched rows and newly recomputed rows
  cannot silently retain different semantics.
- For database formula-function semantics, inspect the formula version/migration
  registry explicitly. Recalculate only affected formulas and their transitive
  dependants, and test from a pre-change stored cell rather than a fresh formula.
- Structured formulas and paths are migrated through their parser/AST and id-remap
  hooks, not regex replacement. Test realistic legacy variants and dependants.
- Prefer dual-read/alias/migration before removing or renaming API URLs, payload keys,
  websocket events, cache keys, task names/signatures, or import formats.
- New frontend works with the previous backend and new backend with the previous
  frontend during rolling deploys. Old workers may reject new Celery tasks; stale tabs
  must receive a compatible response or explicit refresh path.

## Django zero-downtime migrations

- The previous application version continues to read and write against the new
  schema. Per [repository policy](../../../../AGENTS.md#good-practices), fields added
  to an existing model must define
  `db_default` or accept `null`; a Python `default` alone does not protect old writers.
  Check that the chosen default/null meaning works for old and new code. Do not
  rename or drop a live column in the same release. Keep fields still used by the
  previous version and mark later removal with
  `# TODO ZDM: remove this field in the next version`.
- Data migrations use historical models from `apps.get_model()` and the migration
  connection (`schema_editor.connection.alias` for ORM `.using(...)`), rather than
  importing live models or assuming the default database. Check dependencies and
  any imported helpers remain valid when replaying the migration in a later release.
  See [core 0120](../../../../backend/src/baserow/core/migrations/0120_add_ai_agent_provider_model_feature.py)
  for historical-model and database-alias handling.
- Justify backfills with an existing-data scenario. Prefer set-based operations or
  bounded batches, preserve concurrent writes, and use database functions when
  defaults must be evaluated per row. Inspect fresh installs and upgrades from
  representative historical data; the
  [core migration tests](../../../../backend/tests/baserow/core/migrations/test_core_migrations.py)
  demonstrate forward/reverse checks against historical state.
- Inspect emitted DDL for locks, table rewrites, scans, and transaction duration on
  populated tables. State-only changes and new empty tables need different evidence
  from changes to busy existing tables. Concurrent index operations must run outside
  an atomic transaction, with Django's model state matching the physical index; see
  [database 0215](../../../../backend/src/baserow/contrib/database/migrations/0215_view_public_id_index.py)
  for `atomic = False` and `SeparateDatabaseAndState`.
- For non-atomic or long-running work, consider interruption after partial progress
  and verify retry behavior. `CREATE INDEX CONCURRENTLY IF NOT EXISTS` alone can skip
  an invalid index left by a failed build; database 0215 detects and removes that
  state before retrying. Backfills must avoid duplicating or overwriting completed
  work on resume. Check the supported rollback path: safe reverse operations when
  schema rollback is intended, or an explicit recovery/forward-fix plan when it is
  irreversible. Do not equate application rollback with reversing every migration.
- Never iterate generated user tables in a migration. Create their columns/indexes
  through the established lazy runtime path. For indexes on busy existing metadata
  tables, use the concurrent pattern above to avoid blocking normal writes.
- Merge migration work created on the same branch rather than adding a second file.
  Do not rewrite migrations inherited from the base. Verify migration drift with
  the repository check.

## Commit and rollback effects

- Trace each mutation through its signals and receivers to the actual task enqueue,
  broadcast, email, webhook, or external cache write. Effects that depend on durable
  rows must wait for commit through `transaction.on_commit` or the established
  equivalent. A domain signal may run inside the transaction when its receiver
  defers the external effect, as in the
  [Automation websocket receivers](../../../../backend/src/baserow/contrib/automation/workflows/ws/signals.py).
- Verify a successful commit produces the intended effect and that rollback after
  the mutation produces none. Include an inner savepoint or outer transaction when
  the changed path uses one. Observe the enqueue/broadcast boundary; merely asserting
  a signal fired or a callback was registered does not prove commit timing or
  rollback behavior. Use the correct database connection for the callback.
- Check callback inputs still describe the intended resource and state when invoked,
  including callbacks created in loops. Where delivery is required, assess failure
  after commit and the existing retry/recovery path; `on_commit` does not make a
  database write and broker delivery atomic.

## Realtime, retries, and caches

- Partial events contain enough identity and state to reconstruct safely, including
  unbuffered clients. Recipient permission filtering applies to normal, clear, and
  null payloads.
- High-frequency broadcasts are gated/throttled and go through the regular store
  update path. Reconnect and stale-client behavior are explicit.
- Ephemeral state has a TTL refreshed by every write path. Locks and singleton leases
  cover or refresh throughout the work; retry paths are finite, idempotent, and join
  the original action where appropriate.
- Cache keys include tenant/permission scope and every semantic input. Every mutation
  path invalidates or versions the value; process restart and a cold cache preserve
  correctness.

Regression tests start from pre-change persisted state where compatibility is the
claim and exercise more than the first successful invocation.
