# Field system

The field system is the engine behind every column in every user table. If
you're working anywhere in the database module, you'll spend most of your
time here. This page is the architectural overview; [the
registries guide](registries.md) explains the registration pattern, and the
built-in field types in `baserow.contrib.database.fields.field_types` are the
best examples to copy.

For the broader request flow and the registry pattern itself, read
[Architectural patterns](architecture.md) and [Registries](registries.md)
first.

## Three things, three roles

| Component | Lives in | What it owns |
|---|---|---|
| **`FieldHandler`** | `baserow.contrib.database.fields.handler` | Orchestration. The create/update/convert/delete entry points. Triggers side effects. |
| **`FieldType` subclasses** | `baserow.contrib.database.fields.field_types` plus premium/enterprise modules | Per-type behaviour: storage shape, validation, search representation, dependency contract, conversion hooks. |
| **`Field` model + subclasses** | `baserow.contrib.database.fields.models` | The Django models. Polymorphic — every `FieldType` has its own model subclass (e.g. `TextField`, `LinkRowField`). |

Plus the registries:

- **`field_type_registry`** — string `type` → `FieldType` instance.
- **`field_converter_registry`** — supplies `FieldConverter`s for non-trivial
  type-to-type conversions.

The `FieldHandler` is the orchestrator; `FieldType` subclasses are the
customisation points; the registries are the extension surface used by core,
contrib, premium and enterprise code.

## The polymorphic `Field` model

Every `FieldType` has its own model subclass. There's a base `Field` table and
each subclass adds columns via Django's content-type framework. When you query
`Field.objects.filter(...)` you get base `Field` instances; calling `.specific`
on a base instance returns the concrete subclass instance.

This matters for queries — see [queries](queries.md) for the `specific()` /
`specific_iterator` patterns.

## Lifecycle — create

`FieldHandler.create_field(user, table, type_name, **kwargs)`:

1. Permission check via `CoreHandler`.
2. Validate (no duplicate primary, unique name within the table, etc.).
3. Resolve the `FieldType` from `field_type_registry`.
4. Extract allowed values from kwargs via the type's `allowed_fields`.
5. `field_type.prepare_values(field_values, user)` — normalise inputs.
6. `field_type.before_create(table, primary, field_values, last_order, user,
   kwargs)` — type-specific setup; returns a `before` token reused later.
7. Save the new `Field` row to the DB.
8. Create any `FieldConstraint`s.
9. Rebuild the field dependency graph via
   `FieldDependencyHandler.rebuild_or_raise_if_user_doesnt_have_permissions_after()`.
10. `schema_editor.add_field()` — alter the underlying user table to add the
    new column.
11. `field_type.after_create(...)` — post-save setup (e.g. building the M2M
    join table for link-row fields).
12. `field_type.init_field_data(...)` if `init_field_data=True` — populate
    initial values (e.g. autonumber sequence reset).
13. Update existing dependents via `_update_dependencies_of_field_created()`.
14. Schedule a search reindex for the new column:
    `SearchHandler.schedule_update_search_data(table, fields=[instance])`.
15. Emit `field_created` signal.

Steps 5-12 are the FieldType's hooks; steps 1-4 and 13-15 are the handler's
own work. Side effects fan out from there via signals (see
[architecture](architecture.md)).

## Lifecycle — update

`FieldHandler.update_field(user, field, new_type_name=None, **kwargs)`:

The interesting variable is whether the type changes.

**Same type:**

1. Resolve types (`from_field_type == to_field_type`).
2. `to_field_type.prepare_values(...)` and `to_field_type.before_update(...)`.
3. Handle constraints, save the `Field` row.
4. Decide if search needs reindex:
   `from_field_type.should_update_search_data(old_field, field_values)`.
5. `to_field_type.after_update(...)` — post-save fix-ups.
6. Update dependents via `_update_dependencies_of_field_updated()`.
7. Schedule search reindex if needed; emit `field_updated`.

**Type change:**

1. Resolve types (`from_field_type ≠ to_field_type`).
2. `ViewHandler().before_field_type_change(field)` — invalidate view filters
   and sortings that depended on the old type.
3. `from_field_type.get_dependants_which_will_break_when_field_type_changes(...)`
   — identify dependents that need fixing up after.
4. `field.change_polymorphic_type_to(new_model_class)` — swap the subclass row.
5. **Conversion** — see next section.
6. `to_field_type.after_update(...)`.
7. Cascade updates to broken dependents via
   `dependant_field_type.field_dependency_updated(...)`.
8. Apply collected updates via the `update_collector`.
9. Schedule search reindex; emit `field_updated` with `field_type_changed=True`.

The order matters: dependent recomputation happens **before** the search
reindex is scheduled, so the index is rebuilt against the post-recompute
values rather than the stale ones.

## Lifecycle — convert (the interesting one)

When a field's type changes, the existing column data must convert from one
representation to another. Baserow has two paths:

### Custom converter (preserves data)

`field_converter_registry.find_applicable_converter(from_model, old_field,
field)` returns the first registered `FieldConverter` whose `is_applicable()`
returns `True`. If found, its `alter_field()` owns the schema change and the
data migration.

Real examples:

- **`TextFieldToMultipleSelectFieldConverter`** — splits the comma-separated
  text values into individual select options, creating the options as needed.
- **`MultipleSelectFieldToSingleSelectFieldConverter`** — picks the first
  option per row, sets the rest to NULL.
- **`LinkRowFieldConverter`** — drops and recreates the M2M table.
- **`RecreateFieldConverter`** — generic fallback. Drops the old column and
  creates the new one. **Data is lost.**

### Lenient schema editor (data loss possible)

If no converter applies, `lenient_schema_editor()` does the conversion:

1. `from_field_type.get_alter_column_prepare_old_value()` — pre-process old
   data (e.g. trim whitespace before parsing).
2. PostgreSQL `ALTER COLUMN` with `USING` clause that attempts to cast.
3. `to_field_type.get_alter_column_prepare_new_value()` — post-process the
   converted value.
4. **Any value that fails to cast is silently set to NULL.** There is no
   per-value error report. The subsequent search reindex will pick up the
   nulled values — old text won't keep matching after the conversion runs.

**Rule of thumb:** if a conversion needs to preserve data and would otherwise
fail or null out, register a `FieldConverter`. Don't hope the lenient path
handles it gracefully.

## Lifecycle — delete

`FieldHandler.delete_field(user, field, delete_strategy=DeleteFieldStrategyEnum.TRASH)`:

1. Permission check; refuse to delete primary fields unless overridden.
2. Identify dependents via `FieldDependencyHandler`.
3. `FieldDependencyHandler.break_dependencies_delete_dependants(field)` —
   delete edges; formulas/lookups that referenced this field error out.
4. Emit `before_field_deleted`.
5. Apply the delete strategy:
   - **`TRASH`** (default) — `TrashHandler.trash(...)`. Cascade-trash related
     fields via `field_type.get_other_fields_to_trash_restore_always_together(field)`.
   - **`DELETE_OBJECT`** — immediate hard delete; no recovery.
   - **`PERMANENTLY_DELETE`** — through the trash system but bypassing the
     retention window.
6. Cascade updates to dependents via `field_dependency_deleted()`.
7. Emit `field_deleted` with the list of fields that were updated as a result.

See [trash system](../technical/trash-system.md) for the broader trash flow.

## Search reindex contract

Field types control how their data ends up in search. Two methods on
`FieldType`:

- **`get_search_expression(field, queryset) -> Expression`** — returns a
  Django ORM expression that casts the field's value to `CharField` for
  inclusion in the table's TSV column. Default: `Cast(field.db_column,
  output_field=CharField())`. Override for non-trivial types (e.g.
  `LinkRowFieldType` joins to the related row's primary value).
- **`is_searchable(field) -> bool`** — whether to include this field in search
  at all. Defaults to `True`; computed/read-only fields may return `False`.

Critical to understand: the search index for row data lives in a
per-workspace search table (not per-field TSV columns on the user table —
that's a legacy V1 layout still present on some deployments). Reindex is
asynchronous and **debounced** (`SearchHandler.schedule_update_search_data`
inserts pending-update rows and schedules a Celery task), so search data can
lag behind writes briefly. New fields are **not** indexed at creation — the
first read of a view bootstraps indexing for any field whose
`search_data_initialized_at` is still NULL.

See [table rows full-text search](../technical/table-rows-search.md) for the
full indexing pipeline and the legacy V1 caveat, and
[workspace search guide](../technical/workspace-search.md) for how those
results are aggregated across types.

## Dependency contract

Formulas, lookups and rollups depend on other fields' values. When the source
changes, the dependent must recompute. `FieldDependencyHandler` tracks the
graph.

Field types participate via:

- **`get_field_dependencies(field, field_cache) -> FieldDependencies`** —
  declares the fields this type depends on. Computed dynamically from the
  field's definition (formula expression, lookup target, rollup target).
- **`field_dependency_created(field, created_field, update_collector, ...)`**
  — called when a new field is added that this field now depends on.
- **`field_dependency_updated(field, updated_field, old_field,
  update_collector, ...)`** — called when a dependency changes.
- **`field_dependency_deleted(field, deleted_field, update_collector, ...)`**
  — called when a dependency goes away.

The `update_collector` is a queue. Hooks add updates to it; after all hooks
have fired, the handler applies the queued updates in dependency order. This
prevents circular update storms.

## Representative field types

| Type | File | Why it's interesting to study |
|---|---|---|
| `TextFieldType` | `field_types.py` | Baseline; minimal hooks. |
| `NumberFieldType` | `field_types.py` | Demonstrates `allowed_fields` extending the base model. |
| `LinkRowFieldType` | `field_types.py` | Manages M2M tables; uses `before_create`/`after_create`/`before_schema_change`; cascade-deletes via `get_other_fields_to_trash_restore_always_together`. |
| `FormulaFieldType` | `field_types.py` | Polymorphic — wraps a dynamic type based on formula result. Implements `field_dependency_updated` for recompute. Search expression delegates to the resolved type. |

Read these in roughly that order to build a model of how complexity scales.

## Surprises for new developers

1. **The `Field` model is polymorphic.** Every type has its own subclass. To
   access type-specific columns from a base `Field`, you need `.specific`.
   When iterating many fields, use `specific_iterator()` to avoid N+1.
2. **FieldType hooks aren't just for validation.** `after_create()` creates
   M2M tables. `before_field_type_change()` cleans up view filter state. Not
   implementing a hook silently skips required behaviour.
3. **Dependencies are recomputed, not stored as schema.** Editing a formula
   string rediscovers its dependencies on save. Bugs in
   `get_field_dependencies` cause hard-to-diagnose stale data.
4. **The lenient schema editor silently NULLs unconvertible values.** If you
   add a new type pair conversion and don't write a `FieldConverter`, data
   loss is the default behaviour. There is no error.
5. **Search reindex is async on commit.** Search may lag a moment behind
   recent writes. Code that needs synchronous search after a write should
   flush explicitly.
6. **Deleting a field can cascade silently.** `LinkRowFieldType`'s
   `get_other_fields_to_trash_restore_always_together` trashes the
   backreference field on the other side. Don't be surprised when "deleting
   one field" trashes two trash entries.

## Related

- [Registries](registries.md) — registration mechanics for new types.
- [Database plugin](../technical/database-plugin.md) — where field types sit
  in the wider database application.
- [Dynamic models](../technical/dynamic-models.md) — how field changes
  invalidate the generated model cache.
- [Table rows full-text search](../technical/table-rows-search.md) — how
  `get_search_expression` ends up in the index.
- [Workspace search](../technical/workspace-search.md) — cross-type
  aggregation on top of the per-table index.
- [AI field architecture](../development/ai-field-architecture.md) and
  [Embeddings server](../development/embeddings-server.md) — the `ai` field
  type's compute path.
- [Undo/redo guide](../technical/undo-redo-guide.md) — actions wrap most
  field-handler operations.
