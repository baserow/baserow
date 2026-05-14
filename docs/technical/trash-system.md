# Trash system

Baserow soft-deletes almost everything user-visible. Deleting a row, a view, a
field, a table, an application or even a workspace doesn't immediately destroy
it — it goes into the trash. A user with access can restore it, or empty the
trash to delete it for good. After a configurable retention window a periodic
Celery task permanently deletes everything older than the limit.

This page describes the moving parts. Entry point:
`baserow.core.trash.handler.TrashHandler`.

## The two data structures

- **`TrashEntry`** (`baserow.core.models.TrashEntry`) — one row per trashed item.
  Records the type, item id, parent ids (if relevant), the user who trashed it,
  the workspace/application, when it was trashed, and a marker for items already
  permanently deleted. Trash entries can also link to parent entries via a
  cascading foreign key so that permanent deletion of a parent (e.g. an
  application) propagates to its descendants (tables, fields, rows).

- **The trashable model itself.** Trashable models inherit from
  `TrashableModelMixin`, which adds a `trashed: bool` column and a custom
  `trash` manager that returns trashed instances (the default manager filters
  them out). Restoring a row is just setting `trashed = False`.

## `TrashableItemType` — the registry

For each trashable Django model there's a `TrashableItemType` subclass registered
in `trash_item_type_registry`. The registry is the extension point: to make a new
model trashable, register a `TrashableItemType` for it.

The base class (see `baserow/core/trash/registries.py`) requires implementations
to provide:

- `model_class` — the Django model.
- `permanently_delete_item(trashed_item, lookup_cache)` — actually delete the row
  (and any related state — files, search index entries, etc.) when the retention
  window expires.
- `restore(trashed_item, trash_entry)` — flip `trashed = False`, save, and emit
  any realtime signals so other clients see the restore.
- `get_parent(trashed_item)` — return the parent item if one exists (used to
  link trash entries hierarchically so parent deletion cascades).
- `get_name(trashed_item)` / `get_names(trashed_item)` — the human-readable
  label shown in the trash modal.
- `requires_parent_id: bool` — `True` if a parent id is required to look up this
  type (e.g. a row needs its table id).

Built-in registrations (non-exhaustive, see each app's `apps.py`):

| Type | Where registered |
|---|---|
| `WorkspaceTrashableItemType`, `ApplicationTrashableItemType` | `baserow.core.apps` |
| `TableTrashableItemType`, `FieldTrashableItemType`, `RowTrashableItemType`, `RowsTrashableItemType` (bulk), `ViewTrashableItemType` | `baserow.contrib.database.apps` |
| `WidgetTrashableItemType` | `baserow.contrib.dashboard.apps` |
| `AutomationTrashableItemType`, `AutomationWorkflowTrashableItemType`, `AutomationNodeTrashableItemType` | `baserow.contrib.automation.apps` |
| `DomainTrashableItemType` | `baserow.contrib.builder.apps` |

## Trashing flow

`TrashHandler.trash(requesting_user, workspace, application, trash_item, ...)`:

1. Look up whether the parent already has a trash entry. If yes, link the new
   entry to it via a cascading FK so they share fate at permanent-deletion time.
2. Set `trash_item.trashed = True` and save.
3. Create the `TrashEntry`.
4. Emit signals so the ws layer can broadcast the deletion to other clients.

There is also `permanently_delete(...)` for items that bypass the retention
window (rare; mostly used for cleanup of unrecoverable state).

## Restore flow

`TrashHandler.restore(requesting_user, trash_entry_id)`:

1. Refuse to restore a child whose parent is still trashed (raises
   `CannotRestoreChildBeforeParent`). The user has to restore the parent first.
2. Call the type's `restore()` which flips `trashed = False` and saves.
3. Delete the `TrashEntry` (the item is alive again).
4. Emit signals.

## Permanent deletion

A periodic Celery task in `baserow.core.trash.tasks` walks `TrashEntry` rows
older than the retention window, looks up each type, and calls
`permanently_delete_item()`. This is where files get removed, search index
entries are cleaned up, and the actual SQL `DELETE` runs.

Two relevant signals fire around this:

- `before_permanently_deleted` — last chance to capture state.
- `permanently_deleted` — fired after the row is gone.

### Retention window

Default **72 hours** (`HOURS_UNTIL_TRASH_PERMANENTLY_DELETED`, set in
`baserow.config.settings.base`, derived from env var of the same name, default
`24 * 3`). Set to a different number of hours to lengthen or shorten.

## Trash listings

The trash modal in the UI is backed by API endpoints that list `TrashEntry` rows
in scope, grouped by parent. Type-specific operations
(`ReadWorkspaceTrashOperationType`, `EmptyWorkspaceTrashOperationType`, etc.) are
registered in `trash_operation_type_registry` and gate who can see/empty what.

## Gotchas

- **Cascading via the FK, not via business logic.** If you trash a table, you
  *don't* iterate its rows and trash each one — you just create one trash entry
  for the table and the row data sits there until the parent's entry hits the
  retention window. Restoring the table makes all the rows visible again.
- **Search indexes.** Most trashable types' `permanently_delete_item()` is
  responsible for tearing down the search index entries for the deleted item.
  When adding a new trashable type, double-check this is wired up.
- **Trashed fields stay in the generated table model.** A trashed `Field` is
  filtered out of `_field_objects` on the dynamic model, but the column itself
  still exists in the user table so that NOT NULL constraints don't break on
  restore. See [dynamic models](dynamic-models.md).
- **Parent inference.** `get_parent()` must return the parent item, not just its
  id, because the trash handler needs the type lookup to find the parent's
  trash entry.

## Related

- [Systems overview — Trash system](systems-overview.md#trash-system).
- [Architectural patterns](../patterns/architecture.md) — where trashing sits in
  the request flow.
