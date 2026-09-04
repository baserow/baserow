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

- The previous application version continues to run against the new schema. New
  fields define `db_default`; do not rename or drop a live column in the same release.
  Remove model state first and leave a `# TODO ZDM` for the later physical drop.
- Use database functions for per-row defaults. Data migrations are set-based,
  idempotent, safe with concurrent writes, justified by an existing-data scenario,
  and covered by a historical migration test.
- Never iterate generated user tables in a migration. Create their columns/indexes
  through the established lazy runtime path; create metadata-table indexes
  concurrently with separate database/state operations.
- Merge migration work created on the same branch rather than adding a second file.
  Verify migration drift with the repository check.

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
