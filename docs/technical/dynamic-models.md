# Dynamic table models

User tables in Baserow are real PostgreSQL tables with real Django models — but
the Django model classes are **generated at runtime** from the table's field
definitions. There is no `class Customers(models.Model)` in the codebase for a
user's "Customers" table. Instead, `Table.get_model()` builds a fresh model
class on demand, and that class is what every query against user data goes
through.

This page explains how that works, where the caches are, what invalidates them,
and the surprises new developers regularly run into.

Read [Systems overview](systems-overview.md) and
[Architectural patterns](../patterns/architecture.md) first.

## Entry point

```python
from baserow.contrib.database.table.models import Table

table = Table.objects.get(pk=table_id)
model = table.get_model()  # → a subclass of GeneratedTableModel

# Now use it like any Django model
for row in model.objects.all():
    print(row.id, row.field_1234)

# Or with human-readable attribute names
model_with_names = table.get_model(attribute_names=True)
for row in model_with_names.objects.all():
    print(row.name, row.revenue)
```

`Table.get_model()` lives in
`baserow.contrib.database.table.models` and wraps the real generation function
`Table._get_model()`. Its useful kwargs:

| kwarg | What it does |
|---|---|
| `attribute_names=True` | Use the field's user-given name (`name`, `revenue`) for model attributes instead of `field_1234`. Disables the Redis cache. |
| `field_ids=[...]` | Restrict the generated model to only these fields. Performance shortcut. |
| `field_names=[...]` | Same but by name. |
| `add_dependencies=True` (default) | When restricting fields, automatically include fields the requested ones depend on (e.g. formula sources). |
| `use_cache=True` (default) | Use the cached `field_attrs` if present. |
| `manytomany_models={}` | Internal — shared dict for resolving link-row M2Ms across nested calls. |
| `app_label=...` | Internal — override the model's app label, used to make circular link-rows safe. |

## How a model is built

`_get_model()` does roughly the following:

1. Fetch all `Field` rows for the table — including **trashed fields** so the
   generated model still knows about the columns that exist in the database
   (NOT NULL constraints would break on restore otherwise). Trashed fields are
   filtered out of `_field_objects` and stored in `_trashed_field_objects`.
2. For each field, call `field_type.get_model_field(field, **kwargs)` to get
   the appropriate Django model field (e.g. `models.CharField`,
   `models.DecimalField`).
3. Assemble an `attrs` dict — Django field attributes, plus `_field_objects`,
   plus `Meta` with `db_table = "database_table_{table_id}"` and
   `app_label`/`managed` settings.
4. Build the class with `type(name, bases, attrs)`, where `bases` is
   `(GeneratedTableModel, TrashableModelMixin, CreatedAndUpdatedOnMixin,
   models.Model)`.
5. Call `_after_model_generation()` so field types can do post-class
   setup — most notably `LinkRowFieldType.after_model_generation` adds the
   ManyToMany field via `contribute_to_class` (see "Gotchas" below).

The result is a Django model class indistinguishable from a hand-written one
for ORM purposes.

## `GeneratedTableModel` — the base class

Every generated model inherits from `GeneratedTableModel`
(`baserow.contrib.database.table.models`). It is the safe `isinstance` check
for "is this a user-table model" and provides shortcuts useful when you have
the model class but not the fields:

- `get_field_objects()` — list of `_field_objects` entries.
- `get_field_object_by_id(field_id)`.
- `get_fields()`, `get_primary_field()`, `get_searchable_fields()`.
- `get_primary_field_value()` — for rendering a row's display label.
- `info()` — rich-formatted debug table of fields (dev-only).

It also mixes in `HierarchicalModelMixin` which provides `get_parent()` (the
`Table`) and `get_root()` (the workspace).

## Caching

There are **two layers**, both of which `get_model()` consults.

### Layer 1 — per-request local cache

`baserow.core.cache.local_cache` (built on `asgiref.local.Local`, so it's safe
across both threads and async tasks). Keyed by
`database_table_model_{table_id}`. Scope: the duration of a single HTTP request
or background task.

Hit only when the kwargs are at their defaults (i.e. no `field_ids`,
`field_names`, `attribute_names`, etc.). The check is
`are_kwargs_default(...)`.

This cache is cleared by the `LocalCacheMiddleware` at the boundary of every
request.

### Layer 2 — distributed Redis cache (versioned)

The dedicated `generated_models` cache backend (Redis in production).
Key: `full_table_model_{table_id}_{BASEROW_VERSION}`.

This cache **does not store the model class itself** — dynamically generated
Python classes can't be safely round-tripped through a cache. It stores the
precomputed `field_attrs` dict that the generator uses to assemble the model.
The model class is rebuilt from those attrs on a cache hit, which is much
faster than re-querying all the fields and calling each
`field_type.get_model_field()`.

Stored shape: `{"field_attrs": {...}, "version": table.version}`.

The cache is invalidated by **version mismatch**: every `Table` row has a
`version: str` UUID column; when something changes that affects the model,
`invalidate_table_in_model_cache(table_id)` rolls the UUID, so the cache lookup
finds a stale `version` and discards the entry.

Invalidation happens in:

- `Field` model save / delete (via the `invalidate_table_model_cache` method on
  the FieldHandler).
- `FieldHandler.update_field()`.
- `FieldHandler.move_field_between_tables()` — invalidates both tables.
- Table post-delete signal.
- Search index initialise/update.

Also, the cache key includes `BASEROW_VERSION` — so every Baserow upgrade is a
full cache flush for free.

## What forces a fresh model build

In day-to-day code, anything that mutates a table's schema:

- A field added, updated (including type conversion), deleted, restored.
- A field moved between tables.
- The table itself being deleted (cache invalidated then dropped).

Restores and undo/redo go through the same mutation paths, so they invalidate
correctly.

If you're writing code that *directly* manipulates `Field` rows outside the
`FieldHandler` (rare — usually a migration or a data-fix script), call
`invalidate_table_in_model_cache(table_id)` yourself.

## Gotchas

### 1. The class object is not stable across calls

```python
m1 = table.get_model()
m2 = table.get_model()
assert m1 is m2  # ❌ NOT guaranteed
```

Every call returns a *fresh* Python class object, even on a cache hit (the
class is rebuilt from cached `field_attrs`). The class **name** is stable
(`Table42Model`) but identity is not. Use `isinstance(row, GeneratedTableModel)`,
or compare by `table_id`, not by class identity.

### 2. `LinkRowFieldType.get_model_field()` returns `None`

This is intentional. The M2M field for a link row can't be added during the
initial `type(...)` call because it might reference the same model
(self-link) or a not-yet-built model. The field type's
`after_model_generation()` hook attaches it via `contribute_to_class()` after
the class exists. If you debug into model generation and see a "missing"
link-row attribute, that's why.

### 3. Trashed fields are columns, not attributes

The PostgreSQL column for a trashed field is still there (to support restore).
The generated model knows about it via `_trashed_field_objects` but doesn't
expose it as an attribute. If you query the underlying table directly with
raw SQL, you'll see columns the ORM model doesn't mention.

### 4. `attribute_names=True` disables the Redis cache

Because the attribute names are derived from current field names (which can
change), the cached attrs would go stale. Use `attribute_names=True` only for
human-readable code paths (exports, formula rendering, snapshots), not for
hot-path queries.

### 5. `add_dependencies=True` may include more fields than you asked for

If you call `table.get_model(field_ids=[10])` and field 10 is a formula that
references field 7, the generated model will include both fields 10 and 7. To
disable this transitively-include behaviour, pass `add_dependencies=False`.

### 6. Circular link rows need consistent `app_label`

If you generate two mutually-linked models in the same call chain, both must
share the same `app_label` so Django's pending-operations resolver pairs them
up. The generator manages this for you via the shared `manytomany_models`
dict; if you ever bypass that path, you'll see "pending operations" exceptions.

## Where to read next

- [Field system](../patterns/field-system.md) — the FieldType ↔ FieldHandler
  contract that drives model generation.
- [Caching](caching.md) — the broader cache architecture this slot fits into.
- `baserow.contrib.database.table.models` — the source.
- `baserow.contrib.database.table.cache` — the Redis cache helpers.
- `baserow.core.cache` — `local_cache` and the cache primitives.
