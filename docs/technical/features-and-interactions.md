# Features and interactions

A map of which database-plugin features interact in non-trivial ways — where
most bugs and design questions live. For the *catalogue* of features and
field/view types, see [database plugin](database-plugin.md). This page is
purely about the interactions.

## Interaction map

The useful question for a new developer isn't only "what features exist" —
it's "which features are coupled?" This table marks the pairs that need extra
care.

Legend: ✔ = simple, ⚠ = non-trivial, watch out, 🛑 = high risk, ask before changing.

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
  values current as either side changes. See
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
  linked items is fragile because one row can belong to many groups. Check
  existing grouping tests before changing this path.
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
- [Plugin and extension system](systems-overview.md#plugin-and-extension-system).
