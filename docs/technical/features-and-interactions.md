# Features and interactions

A catalogue of the major user-facing features of the database plugin, plus a
map of which features interact in non-trivial ways. The interaction map is
the more valuable half — it's where most bugs and design questions live.

For the *implementation* of each feature, follow the links to the relevant
technical or plugin guide.

## Feature catalogue

### Tables and rows

- **Tables** — the spreadsheet-like unit of structured data. Backed by a
  dynamically generated Django model. See
  [dynamic models](dynamic-models.md).
- **Rows** — the records inside a table. Soft-deletion via the
  [trash system](trash-system.md); history via the
  [row history pattern](../patterns/row_history_from_action.md).

### Fields

Built-in field types and what's notable about them:

| Type | Notes |
|---|---|
| `text`, `long_text`, `email`, `phone_number`, `url` | Basic scalar text. |
| `number` | Decimal places + prefix/suffix formatting. |
| `boolean` | True / false. |
| `date`, `last_modified`, `created_on`, `last_modified_by`, `created_by` | Time + metadata fields. |
| `single_select`, `multiple_select` | User-defined option sets. |
| `link_row` | M2M between tables; powers lookups, rollups and counts. |
| `formula` | Polymorphic: result type derived from the formula expression. See [formula](formula-technical-guide.md). |
| `lookup` | Pulls a value from a linked row. Implemented as a constrained formula. |
| `rollup` | Aggregates linked rows (sum, count, max, …). |
| `count` | Counts linked rows. |
| `multiple_collaborator` | Multiple users from the workspace. |
| `file`, `password`, `rating`, `duration`, `autonumber`, `uuid`, `ai`, `rich_text` | Special-purpose. |

See [field system](../patterns/field-system.md) and
[plugin: field-type](../plugins/field-type.md).

### Views

Built-in view types:

| Type | Notable |
|---|---|
| `grid` | Spreadsheet-style. Supports filtering, sorting, grouping, search, decorations. |
| `gallery` | Card layout. |
| `kanban` | Board grouped by a single-select field. |
| `calendar` | Time-based layout on a date field. |
| `form` | Public input form generating rows. |
| `timeline` | Date-range layout. |

View modifiers, applied to most view types:

- **Filtering** — boolean conditions over fields, combined as a tree.
- **Sorting** — ordered list of field-direction pairs.
- **Grouping** — applies on grid view today; group-by hooks exist for others.
- **Search** — full-text TSV search across the table.
- **Decorations** — visual annotations conditional on row state.

### Cross-cutting features

- **Comments / row activity** — per-row commentary and history.
- **Webhooks** — fire HTTP requests on row events.
- **Data sync** — periodic pull from Airtable / ICS / JSON / etc.
- **Imports / exports** — CSV / JSON / XML / Excel.
- **Snapshots** — point-in-time application copies. Serialization-backed.
- **Templates** — pre-built applications. Serialization-backed.
- **API tokens** — long-lived credentials with per-resource scopes.
- **Realtime updates** — every state change pushed to subscribed clients.
- **Undo / redo** — through the action system.
- **Notifications** — events users opted into seeing.
- **Search** — workspace-scoped full-text search.
- **Trash** — soft-delete + retention for almost everything.
- **Permissions** — RBAC (enterprise), public sharing, personal views
  (premium).

## Interaction map

The interesting question for a new developer isn't "what features exist" —
it's "which features lie about being independent." This table marks the
pairs that *don't* compose cleanly and where you need to think carefully.

Legend: ✔ = simple, ⚠ = non-trivial, watch out, 🛑 = known landmine.

| → \ ↓ | Field type | View modifier | Realtime | Trash | Undo | Snapshot/export | Search | Notifications | Webhooks |
|---|---|---|---|---|---|---|---|---|---|
| **Field type** | — | ⚠ | ✔ | ⚠ | ⚠ | ⚠ | ⚠ | ✔ | ⚠ |
| **View modifier** | ⚠ | — | ✔ | ⚠ | ⚠ | ⚠ | ⚠ | ✔ | ✔ |
| **Realtime** | ✔ | ✔ | — | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **Trash** | ⚠ | ⚠ | ✔ | — | ⚠ | ⚠ | ⚠ | ✔ | ✔ |
| **Undo/redo** | ⚠ | ⚠ | ✔ | ⚠ | — | ✔ | ✔ | ✔ | ✔ |
| **Snapshot/export** | ⚠ | ⚠ | ✔ | ⚠ | ✔ | — | ⚠ | ✔ | ✔ |
| **Search** | ⚠ | ⚠ | ✔ | ⚠ | ✔ | ⚠ | — | ✔ | ✔ |
| **Formula** | 🛑 | ⚠ | ✔ | ⚠ | ⚠ | ⚠ | ⚠ | ✔ | ⚠ |
| **Link rows** | 🛑 | 🛑 | ⚠ | 🛑 | ⚠ | 🛑 | ⚠ | ✔ | ⚠ |
| **Permissions** | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ | ⚠ |

### Specifics worth knowing

- **Field type × view modifier** — Filters and sorts depend on the field
  type's capabilities. Changing a field's type calls
  `ViewHandler.before_field_type_change(field)` to invalidate filters/sorts
  that referenced behaviour the new type doesn't support.
- **Field type × search** — Every searchable field type provides a
  `get_search_expression`. Changing a field's type, or changing values,
  schedules a TSV reindex.
- **Field type × dynamic model** — Every field change (create / update /
  delete / type conversion) bumps `Table.version` and invalidates the
  generated model cache. See [dynamic models](dynamic-models.md).
- **Formula × link row** — The most complex interaction in Baserow. Lookups
  and rollups are formulas over a link-row field; the dependency graph keeps
  values current as either side changes. Bugs in this corner are common
  enough that #5184 (link-row group-by crash) is on the bug queue. See
  [formula technical guide](formula-technical-guide.md) and
  [field system: dependency contract](../patterns/field-system.md#dependency-contract).
- **Formula × field deletion** — Deleting a field that a formula depends on
  breaks the formula. The dependency system reports the break to the
  affected dependents via `field_dependency_deleted`.
- **Link row × trash** — Deleting a linked row removes M2M rows, but the
  link-row field's backref is cascade-trashed via
  `get_other_fields_to_trash_restore_always_together`. Restoring the field
  restores both ends.
- **Link row × group-by** — Grouping by a link-row field when rows have many
  linked items has surfaced as a crash (#5184). The combination is fragile.
- **Trash × cascading** — Trashing a parent doesn't iterate children; the
  `TrashEntry` is linked via cascading FK so permanent deletion of a parent
  takes its children with it. Restoring a child whose parent is still trashed
  raises `CannotRestoreChildBeforeParent`. See
  [trash system](trash-system.md).
- **Trash × search** — Each `TrashableItemType`'s `permanently_delete_item()`
  is responsible for tearing down the search index entries. New trashable
  types must wire this up.
- **Undo/redo × every action** — Most state changes flow through an
  `ActionType`. Undoable types implement `undo()` / `redo()`. Anything that
  bypasses the action system won't appear in the undo stack — common source
  of "but I did Ctrl+Z" support tickets.
- **Snapshot/export × everything** — Snapshots and templates are
  serialise-and-deserialise of the entire application. Any feature whose
  state isn't covered by `export_serialized` / `import_serialized` is lost
  in snapshots. See [serialization system](serialization-system.md).
- **Realtime × every state change** — Handlers emit signals; receivers
  translate to ws messages. A new feature whose handler doesn't emit signals
  appears to work but doesn't update other clients in real time. Check
  `baserow.ws.*` receivers for what's covered.
- **Permissions × everything** — Permission checks live in services (or
  actions when there's no service). Adding a new endpoint without a
  permission check is the most common security regression. RBAC in
  enterprise extends but doesn't replace the base permission model.

## Reading order for a new developer

The most efficient sequence to internalise this map:

1. Read this page top-to-bottom to know what exists.
2. [Dynamic models](dynamic-models.md) — the universal substrate.
3. [Field system](../patterns/field-system.md) — the central interaction
   hub.
4. [Action system](action-system.md) — the auditing/undo backbone.
5. [Architectural patterns](../patterns/architecture.md) — how the layers
   compose.
6. [Workspace search](workspace-search.md), [trash](trash-system.md),
   [serialization](serialization-system.md) — supporting systems.
7. [Formula](formula-technical-guide.md) — left for last because it pulls
   in everything else.

## Related

- [Systems overview](systems-overview.md).
- [Database plugin](database-plugin.md).
- The plugin guides under [`docs/plugins/`](../plugins/introduction.md).
