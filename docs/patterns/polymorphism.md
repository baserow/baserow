# Polymorphism and `.specific`

`Application`, `Field`, `View`, `Job`, and a handful of other Baserow
models are **polymorphic** — a single base model has many subclass
models, each with its own columns, all sharing a parent table for
querying. When you query the base model you get base instances; the
`.specific` attribute promotes one to its actual subclass.

This pattern shows up everywhere in the code. Getting it wrong is a
common source of N+1 queries and "why does my new column not work?"
bugs.

For the broader Django/Baserow vocabulary mismatch see
[Baserow vs Django](baserow-vs-django.md). For the ORM-query side of
the story see [Queries](queries.md#specific-and-specific_iterator-polymorphic-models).

## The mechanism

`backend/src/baserow/core/mixins.py` —
`PolymorphicContentTypeMixin`:

```python
class PolymorphicContentTypeMixin:
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        ...
    )

    @property
    def specific(self):
        """Returns this instance in its most specific subclassed form."""
        return self.get_specific()
```

Every polymorphic base model mixes this in. The `content_type` column
holds a Django `ContentType` FK — the entry identifying which concrete
subclass this row is. `Application.content_type` might point to
`Database`, `Builder`, `Automation`; `Field.content_type` to
`TextField`, `LinkRowField`, `FormulaField`; etc.

## How a polymorphic query works

```python
# Returns base instances of Field. Subclass columns are NOT loaded.
fields = Field.objects.filter(table=table)
for field in fields:
    print(field.name)           # ✓ works (base column)
    print(field.number_decimal_places)  # ✗ AttributeError on most Fields
```

To get subclass columns:

```python
field = field.specific          # one query per call
print(field.number_decimal_places)
```

`.specific` looks at `field.content_type` (already loaded if you
`select_related("content_type")`-ed), finds the subclass model class
through Django's content-type registry, and **re-fetches the row** as
an instance of that subclass.

Without `select_related("content_type")`, that's two queries per
instance. With it, one. With `specific_iterator(...)`, batched. See
[Queries](queries.md#specific-and-specific_iterator-polymorphic-models) for the
canonical recipe.

## `specific_iterator` — the N+1 fix

`backend/src/baserow/core/db.py`:

```python
from baserow.core.db import specific_iterator

for field in specific_iterator(Field.objects.filter(table=table)):
    print(type(field), field.name)
    # ↑ field is the subclass instance: TextField, NumberField, …
```

`specific_iterator`:

1. Walks the input queryset (or pre-loaded list) once.
2. Groups instances by `content_type`.
3. Issues one query per content type to fetch all subclass rows of
   that type.
4. Returns the results in the original input order.

For a table with 30 fields across 8 types, that's **8 queries
instead of 30**.

Variants worth knowing (from the function signature):

- **`per_content_type_queryset_hook`** — runs once per subclass
  queryset before execution. Use to add `select_related` /
  `prefetch_related` that only make sense for some subclasses
  (e.g. `LinkRowField.link_row_table`).
- **`base_model`** — pass the model when the input is a pre-loaded
  list, not a queryset.
- **`select_related`** — apply to every subclass queryset.
- **`skip_missing_specific_objects=True`** — tolerate orphaned base
  rows (rare in production; useful in test fixtures during
  migrations).

## When to use `.specific` vs base

- **Need subclass columns or subclass behaviour?** Use `.specific`.
  No exceptions; you can't reach subclass state otherwise.
- **Need only base columns and the type identity?** Use the base
  instance. `field.content_type` already tells you the subclass;
  `field.name`, `field.table_id`, etc. are on the base.
- **Iterating multiple instances?** Use `specific_iterator`. Never
  `.specific` in a loop.

The common mistake is calling `.specific` inside a `for` loop —
each call triggers a query, and the loop quietly N+1s. The fix is
always `specific_iterator`.

## Where this is used

| Base | Subclasses |
|---|---|
| `Application` | `Database`, `Builder`, `Automation`, `Dashboard`, …. Application types live in `application_type_registry`. |
| `Field` | `TextField`, `LongTextField`, `LinkRowField`, `FormulaField`, `LookupField`, `SingleSelectField`, … one subclass per `FieldType`. |
| `View` | `GridView`, `GalleryView`, `FormView`, `KanbanView`, … one per `ViewType`. |
| `Job` | One subclass per `JobType` (per-job columns: `original_table`, `imported_count`, `url`, …). |
| `Integration` / `Service` | Builder/automation integration polymorphism (`LocalBaserowIntegration`, `LocalBaserowGetRow`, …; types live in `integration_type_registry` and `service_type_registry`). |
| `DataSync` source | One subclass per `DataSyncType`. |
| Premium / enterprise extensions | Premium `AIField`, enterprise role types, etc. |

`TrashEntry` is not in this list deliberately: although `TrashableItemType`
follows the same registry-of-types pattern, the storage model itself is not
polymorphic — `TrashEntry` uses a `trash_item_type` text discriminator plus
generic-FK-like columns rather than `PolymorphicContentTypeMixin`.

The pattern is so widespread that "this thing has a `*Type` in
`<thing>_type_registry`" is a strong signal the underlying model is
polymorphic. See [Registries](registries.md).

## Working with `.specific` in handlers

The handler convention: load with `select_related("content_type")`,
promote to `.specific` once at the top, work with the specific
instance from there on.

```python
class FieldHandler:
    def get_field(self, field_id):
        return Field.objects.select_related("content_type").get(id=field_id)

    def update_field(self, user, field, **kwargs):
        field = field.specific            # promote once
        field_type = field_type_registry.get_by_model(field)
        # … use field_type and field …
```

Most handler methods that touch polymorphic models start with this
shape. New handler methods should follow it.

## `get_by_model(...)` vs `get(...)` on a registry

`field_type_registry.get(type_string)` returns the `FieldType`
instance by string ("text", "number", …).

`field_type_registry.get_by_model(model_instance_or_class)` returns
the `FieldType` instance from a Django model instance or class —
useful when you have a `field.specific` but don't want to read its
`type` string just to look up the registry entry.

Both are common; the choice depends on whether the caller has a
type string or a model instance.

## Type conversion — `change_polymorphic_type_to`

When a user changes a field's type ("convert text to number"),
`FieldHandler` calls `change_polymorphic_type_to(new_subclass)` on
the base row:

1. The base row keeps its primary key — the polymorphic identity is
   preserved.
2. The `content_type` column is updated to the new subclass.
3. The old subclass row is deleted; a new subclass row with the same
   PK is created.

This is **why** polymorphic columns can change at all — without the
content-type indirection, conversion would require deleting and
re-creating the row, breaking every FK and reference. The fixed PK
lets dependents (views, filters, formulas) keep their links.

The data migration (cell values from the old type to the new type)
is a separate concern — see
[Field system — convert](field-system.md#lifecycle-convert-the-interesting-one).

## Adding a new polymorphic subclass

For the common cases — adding a new field type, view type, or application
type — follow the relevant registry pattern. The
[`*_type_registry` registration](registries.md) handles the polymorphic
plumbing; you don't usually hand-write it.

The shape if you ever need to add a new polymorphic *parent*:

1. Mix `PolymorphicContentTypeMixin` into the base model.
2. Add the `content_type` ForeignKey (the mixin auto-checks it's
   present).
3. Build a `*Type` base class extending `Instance` (see
   [Registries](registries.md)).
4. Create a `*TypeRegistry` extending `Registry`.
5. Subclasses are concrete Django models inheriting from the base.
   Their per-instance columns go on the subclass model.
6. Register subclasses from `apps.py` `ready()`.

For most contributors this is once-in-a-career territory. Far more
common: adding a new subclass to an existing parent.

## Gotchas

- **`isinstance(field, TextField)` is fine.** The subclass instance is
  a real Python instance of its class once you've promoted.
- **`isinstance(field, TextField)` on a *base* instance is False.**
  `Field.objects.get(...)` returns a `Field`, not a `TextField`. Use
  `.specific` first.
- **Pickling specific instances** is fine; they're regular models.
- **Bulk-creating subclass rows** through the base manager won't
  trigger the content-type assignment. Either create through the
  subclass model directly, or use the handler that knows how to
  set `content_type`.
- **`field.content_type_id` is `int`**; `field.content_type` is the
  resolved `ContentType` row (triggers a query if not
  `select_related`-ed).
- **Polymorphism is not free.** Each specific subclass is its own
  database table joined on PK. Queries against many subclasses are
  query-heavy unless you use `specific_iterator`.

## Anti-patterns

- **`.specific` inside a loop.** N+1 — use `specific_iterator`.
- **`if field.content_type.model == 'textfield': …`** Branching on
  the type string at the call site. The `FieldType` subclass exists
  to absorb that branching — push the per-type behaviour into a
  method on the type class.
- **Storing subclass columns on the base.** If a column only makes
  sense for one subclass, it goes on that subclass model. The base
  stays generic.
- **Mutating a base instance and `.save()`-ing.** Saves only the base
  columns. Subclass column changes are silently lost. Always work
  with `.specific` if you're mutating.
- **Forgetting to `select_related("content_type")`.** Every `.specific`
  access becomes two queries instead of one. Small loops feel fine
  in dev; production traffic exposes it immediately.

## Related

- [Baserow vs Django](baserow-vs-django.md) — the polymorphism is
  one of the "things a Django developer doesn't expect but finds."
- [Queries](queries.md#specific-and-specific_iterator-polymorphic-models) — the canonical
  query recipe.
- [Registries (backend)](registries.md) — `*_type_registry`
  alongside polymorphic models.
- [Field system](field-system.md) — `FieldType` subclasses + the
  polymorphic `Field` model.
- [Dynamic models](../technical/dynamic-models.md) — different
  mechanism (user-table model generation), not the same as the
  Django ContentType polymorphism described here.
