# Database module review

Use this reference for changes under `backend/src/baserow/contrib/database` or
`web-frontend/modules/database`, their tests and docs, and premium or enterprise code
that implements or changes a Database extension point. Also use it when shared core
code changes a contract consumed by Database tables, fields, rows, views, formulas,
data syncs, imports, exports, or workflow actions.

This is a domain map, not a substitute for the topic references. Load backend or
frontend for the changed layer, state-compatibility for persisted behavior or
realtime, data-performance for query or fan-out changes, security for public access
or attacker-controlled data, and external-io for remote data sync/import/export,
webhooks, or worker-backed external effects.

## Preserve the module model

A Database change must keep four representations semantically aligned: metadata
objects, generated user-table schema/query expressions, serialized API/realtime
payloads, and frontend registries/stores.

A `Database` owns metadata `Table` objects. Each table corresponds to a physical
PostgreSQL `database_table_<id>` and `Table.get_model()` builds a dynamic Django model
over it. Most scalar and stored-derived fields use stable `field_<id>` columns, while
link and multi-valued fields can use relation tables. `View` objects are saved
projections over rows: their field options, filters, sorts, groups, decorations, and
sharing rules do not own the underlying row data.

Backend `FieldType`, `ViewType`, filter, aggregation, data-sync, export, and workflow
registries are the extension boundary. Their frontend counterparts normalize the
same capabilities for stores and components. When a base hook changes, search its
registrations, overrides, and consumers across core, premium, and enterprise.
Database must not import Builder, Automation, or Dashboard; those products consume
Database contracts or register extensions from their own layer.

For the changed concept, trace one coherent path:

```text
API / task / import / sync
  -> handler or user ActionType
  -> owning registry hooks
  -> metadata + generated model/query
  -> dependencies + history/search/webhooks/realtime
  -> frontend service -> database store -> field/view type -> surface
```

A bypass is safe only when it deliberately proves which validation, authorization,
derived effects, and broadcasts do not apply.

## Select the affected contract

| Change                                                        | Contract to trace                                                                                          | Usually load too                                                       |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Table metadata or generated schema                            | Metadata and physical schema remain compatible and recover together                                        | backend, state-compatibility, data-performance                         |
| Field or field type                                           | Storage, conversion, dependencies, query capabilities, serialization, and every supported UI surface agree | backend/frontend, state-compatibility; often data-performance          |
| Row create/update/delete/move                                 | Every entry point produces the same values and downstream effects                                          | backend, state-compatibility; security when authority changes          |
| View, filter, sort, group, search, decoration, or aggregation | Saved configuration, query semantics, visibility, and frontend state agree                                 | backend/frontend, data-performance; security when shared               |
| Formula, lookup, rollup, or dependency graph                  | References, generated SQL, stored results, and transitive updates agree                                    | state-compatibility, data-performance; security if user-controlled     |
| Import, export, template, snapshot, or data sync              | IDs, types, files, authority, retries, and partial failures round-trip                                     | state-compatibility; external-io/security at their boundaries          |
| Workflow or button action                                     | Navigation or dispatch semantics, authority, results, and failures agree                                   | backend/frontend; security and external-io for dispatched effects      |
| Grid, row modal, card, form, or realtime UI                   | Store transitions remain correct across all applicable view modes and field types                          | frontend, state-compatibility; data-performance for repeated cell work |

Use only the sections below that match the selected contract.

## Tables, fields, and generated schema

- Treat field metadata, its generated database column or relation, model shape, and
  cache version as one logical state transition. Creation, alteration, conversion,
  trash, restore, duplication, and failure must not leave a usable field pointing at
  the wrong physical shape. Include trashed fields whenever their physical shape is
  still required; trash keeps schema while permanent purge removes it.
- Generate a table model from the field snapshot required by the operation and reuse
  it. Repeated `table.get_model()` calls, `.specific` lookups, or cache invalidation
  inside row/field loops are scale smells; generated-model cache invalidation must be
  narrow and complete, including linked-table inputs. Do not globally clear it in an
  ordinary runtime path.
- Dynamic schema and identifiers use the schema editor and established identifier
  composition, never interpolated user names. Metadata migrations follow ordinary
  zero-downtime rules; columns or indexes on generated user tables use the lazy
  runtime path rather than iterating every table in a migration.
- A field type is a capability bundle, not only a model field and cell component.
  First decide whether it owns a column, relation, stored/query-time derived value,
  or configuration only. Then align the applicable hooks for input/database/API
  values, API docs and integration schemas, defaults, emptiness/equality, search,
  filter, sort, group, aggregation, index eligibility, formulas, dependencies,
  history, and copy/paste. Unsupported capabilities should be denied explicitly and
  consistently on both ends.
- Follow field behavior through grid cells, row edit, cards, form views, public
  views, docs examples, import/export, and premium wrappers such as AI fields only
  when that field claims support for those surfaces. A wrapper or derived field
  delegates value semantics to its underlying type rather than reimplementing a
  drifting subset.
- For a gated field or view type, distinguish registry availability and use of
  existing objects from direct create, conversion, direct duplicate, table/database
  duplicate, import, template, and snapshot paths. State explicitly which operations
  remain valid after the flag is disabled.
- Field conversion is bidirectional behavior over existing rows, not just a schema
  alteration. Check old and new values, null/empty/error cases, dependants, view
  configuration, indexes, stable field identity, and undo/recovery for both
  conversion directions.
- Formula, lookup, and rollup fields have persisted dependency metadata even when
  their values are generated at query time. Create, update, delete, restore, rename,
  conversion, and link changes preserve dependency order, cross-table paths,
  broken-reference healing, deleted relations, cycle/depth bounds, and formula mode.
  Inspect generated SQL and bound the rows affected by a dependency cascade.
- Duplication, export/import, templates, and snapshots are staged graph rebuilds:
  create metadata and schema before rows, resolve deferred relations and M2M data,
  then run type-owned post-import hooks in dependency order. Remap every field,
  table, option, and formula reference through registry/AST hooks rather than text
  replacement.

## Row mutations and derived effects

- Ordinary API writes, batch endpoints, imports, form submissions, data syncs,
  automations, undo/redo, and internal callers should converge on one bulk-capable
  row mutation contract. Compare their validation and side-effect ledger when a path
  intentionally bypasses user actions or signals.
- Parse each submitted value with its `FieldType`, against one field/model snapshot.
  Read-only, write-only, derived, data-sync-owned, and omitted fields retain distinct
  meanings. Partial updates must not erase values that were not supplied.
- After a mutation, account for every affected row and transitive dependant: formula
  and lookup values, row order, search data, history, webhooks, automation triggers,
  notifications, view aggregations, and realtime recipients. Define whether each
  consumer follows submitted fields or materially changed fields instead of passing
  through a raw request payload accidentally.
- Treat `updated_field_ids` and equivalent change sets as domain data. They include
  explicit edits, always-updated/rule fields, and recomputed dependants so every
  downstream consumer sees the intended mutation. When the set broadens, trace every
  serializer, webhook, automation, notification, and row-checker consumer and assert
  required keys and values, not only that emitted keys form a subset.
- Correlate prepared, filtered, created, and returned rows by stable row identity,
  never list position. Preserve deterministic order where clients, undo, or
  grouped/buffered views rely on it.
- Keep the durable mutation and required dependency updates atomic. External calls
  and broadcasts happen only from a state other transactions may safely observe;
  retries and two-way sync conflict handling must not duplicate an effect or overwrite
  a newer local value.
- For data-sync changes, preserve the source's stable row identity, synced-field
  ownership, schema-drift and unmatched-row policy, failure atomicity, one-active-job
  rule, consolidated signals, and two-way loop prevention. Test source-scale batches,
  not only a few rows.
- Action parameters are persisted compatibility contracts used by undo/redo and
  history after deployment. Verify do/undo/redo with old serialized shapes and note
  that row history is produced through action completion/providers, not merely row
  signals.

## Views and one effective transformation contract

- Treat filtering, sorting, grouping, searching, field visibility, decorations, and
  aggregations as independent transformations with an explicit order. Grouping and
  sorting are distinct typed streams even when they reference the same field: use
  their respective capability hooks and annotation aliases. For saved and ad-hoc
  parameters, preserve missing/inherit, empty/clear, and supplied/replace through
  rows, metadata, group data, public endpoints, refreshes, and exports.
- A field/view capability must agree across backend registries, frontend registries,
  API validation, generated queryset, and client-side row matching/ordering. On
  field deletion, type change, or move, clean or migrate every saved field reference
  instead of leaving a view that fails only when reopened.
- Rows, group metadata, footer aggregations, exports, refresh snapshots, public
  endpoints, and frontend comparisons use equivalent effective semantics. Metadata
  must describe ad-hoc overrides rather than silently reporting only the saved view.
- Public and restricted views apply the same row and field visibility to list and
  single-row reads, search, link-row choices, aggregations, exports, realtime, and
  error behavior. A serializer fix is incomplete if the queryset, metadata, event,
  or footer still discloses a hidden value or formula dependency.
- Inspect generated SQL when combining links, formulas, filters, groups, and
  aggregations. Independent many-to-many joins can multiply rows; test unequal
  relation cardinalities and assert exact row order, group keys/counts, and absence
  of duplicates rather than only adjacency.
- View sort/group indexes are derived state owned by `ViewIndexingHandler`. Every
  path that changes an effective indexed expression must schedule the appropriate
  rebuild/drop, including copy/import and field conversion/deletion. Legacy
  generated-table columns and indexes use the lazy view-loaded task/signal path, not
  a migration over all user tables.
- Queued exports preserve omission as well as values in their serialized job
  parameters. A new optional default must not make old workers receive a key or
  contract they cannot deserialize during a rolling deployment.
- Verify the applicable view types and access modes, not only Grid: Gallery, Kanban,
  Calendar, Timeline, Form, row modal, collaborative/personal/restricted ownership,
  public sharing, templates, and read-only/two-way data sync consume overlapping but
  different capabilities.

## Frontend stores, cells, and realtime

- Database stores and `FieldType`/`ViewType` own row and view semantics. Components
  render and wire interactions; they should not grow a parallel rule for filtering,
  value conversion, permissions, or realtime reconciliation.
- Route local and realtime row changes through the regular `ViewType.rowUpdated`
  family and store mutations. Mark whether each before/after value is a complete
  snapshot or patch; missing and explicit null are not interchangeable. Include
  identity, order, explicit edits, always-updated fields, and recomputed dependants.
  If a buffered or unbuffered client lacks enough state to decide a
  filter/sort/group/search transition, preserve a placeholder and refresh instead of
  guessing.
- Preserve the two update timelines: directly editable values can be optimistic,
  while server-derived formula/lookup values remain pending until authoritative data
  arrives. Failure rolls back or refreshes all affected cells, order, groups, and
  aggregations without erasing a newer edit.
- Sparse buffers keep loaded rows, absolute positions/counts, group paths, selection,
  row-modal ownership, request generation, and eviction coherent without
  materializing all rows. Correlate temporary and server row IDs everywhere; after
  each await, stale work must not mutate or clear loading for a newer request.
- Exercise cell editing together with selection, multi-select, copy/paste, keyboard
  navigation, row creation/deletion, and the row modal. Map source to writable
  destination fields without shifting columns, and keep create-plus-paste in its
  intended undo group. In Grid, select relevant grouped/ungrouped,
  buffered/unbuffered, public/read-only, row-coloring, variable-height, and long/wide
  modes from `docs/testing/grid-view-test-plan.md`.
- For Form changes, parse query-prefill values through the field type, derive
  conditional visibility only from eligible earlier fields, reset newly hidden
  values to type defaults, and validate/submit only visible prepared values. Preserve
  public authentication and edit-token behavior.
- Per-cell render, computed, watcher, and registry work multiplies by visible rows ×
  fields and can repeat during scrolling or realtime. Memoize by every semantic input
  and test invalidation; do not trade correct reused cells for a fast warm render.

## Database-specific security and scale screen

- Model scale using the multiplying dimensions that changed: tables per database,
  fields per table, rows per table, links per cell, dependency depth/fan-out, views
  and groups, concurrent editors, public viewers, webhooks, and sync records. Use a
  wide generated table and realistic row/link cardinality for query counts, plans,
  payloads, and UI work.
- Verify indexes against the generated-table query actually used for filtering,
  ordering, linking, or search. The `field_<id>` shape, casts, formula expressions,
  joins, and selectivity decide whether PostgreSQL can use an index; merely exposing
  the `db_index` option is not evidence.
- Database values and configuration are attacker-controlled input. Load the security
  reference for dynamic SQL or formulas, persisted rich content, files, URLs, public
  views, or any capability that can execute or fan out.
- A public token, view share, API token, table role, or field permission grants only
  its declared rows, fields, and operations. Test a valid object from another
  workspace, hidden fields and formula references, restricted rows, bulk endpoints,
  exports, websocket events, and logs/errors for data or schema disclosure.
- Workflow/button fields, webhooks, imports, and two-way sync can turn row access into
  execution, network, or mass-mutation authority. Authorize the acting user and
  target at dispatch time, bound fan-out and recursion, and ensure a user cannot make
  Baserow execute with the creator's or worker's broader authority. Distinguish a
  passive client-side navigation button from server-dispatched actions; for the
  latter, preserve field-scoped order, result mapping, stop-on-failure behavior, and
  the documented treatment of earlier successful side effects.

## Evidence that fits the change

Prefer one end-to-end regression around the changed contract plus focused unit tests
at registry boundaries. Use pre-change persisted data for compatibility, a second
client for realtime, public/restricted callers for visibility, linked and derived
fields for query correctness, and small-versus-representative data for scale.

When the change affects Grid interactions, use the relevant slice of
`docs/testing/grid-view-test-plan.md`; do not mechanically run its entire matrix.
Record which field types, view/access modes, mutation entry points, and cardinalities
were selected and why. A test that constructs an impossible row or calls a registry
hook directly cannot establish that the production path is wired correctly.
