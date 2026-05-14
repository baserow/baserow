# Baserow vs Django — same words, different meanings

A senior Django developer can read most of the Baserow codebase fluently from
day one. The trap is the words we share. Baserow overloads several Django
terms — **field**, **table**, **model**, **application**, **migration** — to
mean Baserow-specific things that are *related to* but *not the same as*
their Django counterparts.

This page resolves the ambiguity. If you only read one pattern doc before
diving in, read this one.

## The big four overloads

| Word | Django meaning | Baserow meaning |
|---|---|---|
| **Field** | A column on a Django model (`models.CharField`, etc.). | A user-defined column on a user-defined table. Backed by a row in the `Field` table (or one of its polymorphic subclasses like `TextField`, `LinkRowField`). Mapped to a Django field through `FieldType.get_model_field()` at model generation time. |
| **Table** | A SQL table that corresponds to a Django model. | A user-defined logical table (`Table` row), backed by a real SQL table (`database_table_{id}`) and a dynamically generated Django model. |
| **Model** | A Python class subclassing `django.db.models.Model`. | Same — but **the Django model for a user table doesn't exist in the source code**. It's generated at runtime by `Table.get_model()`. |
| **Application** | A Django app (directory with `apps.py`, `models.py`, etc.). | A Baserow application *type* (e.g. a database, a builder app, an automation, a dashboard). A Baserow application is a row in `Application` (polymorphic), not a Django app. Baserow application types are not Django apps. |

Once you have those mappings, most things make sense.

## The full glossary

**Django field** = Python descriptor on a Django model. Lives in code.

**Baserow field** = column on a user table. Lives as data in the `Field`
table (or a polymorphic subclass). Has a corresponding `FieldType`
implementation that knows how to translate it into a Django field at model
generation time. See [field system](field-system.md).

**Django model** = Python class. Hand-written.

**Baserow model** = generated Python class for a user table. Built at
runtime from `Field` rows. See [dynamic models](../technical/dynamic-models.md).

**Django table** = SQL table backing a Django model. Comes from a migration.

**Baserow table** = (a) the `Table` row representing a user's logical table,
*and* (b) the real PostgreSQL table named `database_table_{id}` that holds
the user's row data. These are two different things; both are referred to
as "the table" in conversation. Context disambiguates — when in doubt, ask.

**Django migration** = a file that alters the schema declaratively. Tracked
in `django_migrations`.

**Baserow migration** = same, but you have an additional category: user-table
schema changes happen at runtime via the schema editor when a user adds /
removes / converts a field. They are *not* Django migrations and *not* tracked
in `django_migrations`. They alter the `database_table_{id}` tables directly.

**Django app** = a Python package with `apps.py` declaring a Django
`AppConfig`. Has its own `models.py`, `migrations/`, etc.

**Baserow application** = a row in the `Application` table representing a
user-facing app (database, builder, automation, dashboard, integrations).
*Each Baserow application is an instance of an application type, registered
in `application_type_registry`.* Baserow application types are not Django
apps. A single Django app (`baserow.contrib.database`) implements one
Baserow application type (`database`). But the mapping isn't necessarily 1:1.

**Django signal** = `django.dispatch.Signal`. Standard Django.

**Baserow signal** = same — but the codebase is structured around emitting
them from handlers and dispatching to receivers in `baserow.ws.*`, search,
notifications, etc. See [architectural patterns](architecture.md).

**Django registry** = the global `apps` registry, plus `ContentType`.

**Baserow registry** = an extension-point pattern used pervasively. A
collection of polymorphic implementations keyed by a string `type`. See
[registries](registries.md).

**View** in Django = a request handler. In Baserow = (a) a user-defined
presentation of a table (grid view, kanban view) *and* (b) a DRF view
class. Context disambiguates; the user-facing "view" is what people usually
mean.

**Permission** in Django = an entry in `auth_permission`. In Baserow =
something granted via the permission system (`PermissionManagerType` in
`permission_manager_type_registry`, RBAC in enterprise). Baserow's
permission model is its own thing; `django.contrib.auth.Permission` is
barely used.

## Three things a Django developer expects but doesn't find

1. **`class Customers(models.Model)` for a user table.** Doesn't exist.
   `Table.get_model()` generates the class at runtime from the `Field` rows.
   See [dynamic models](../technical/dynamic-models.md).

2. **Migrations for user tables.** They live outside Django's migration
   system. When a user adds a field, `FieldHandler.create_field()` calls
   `schema_editor.add_field()` to alter the `database_table_{id}` table
   directly. There's no migration file.

3. **`ContentType` for user tables.** A user-table model doesn't have a
   `ContentType` entry. The Baserow `Field` model and `Application` model
   *do* use Django's `ContentType` framework for their own polymorphism, but
   user tables don't. The polymorphism is implemented separately via
   `GeneratedTableModel`.

## Three things a Django developer doesn't expect but finds

1. **Polymorphic models with `.specific`.** `Application`, `Field`, `View`,
   and a few others use Django's content-type framework to store multiple
   subclasses behind one parent table. `app.specific` returns the concrete
   subclass instance. See [queries](queries.md) for the `specific_iterator`
   pattern.

2. **A "handler" layer between view and ORM.** Django convention puts
   business logic on managers or model methods. Baserow puts it in
   handlers (`TableHandler`, `FieldHandler`, `RowHandler`, `CoreHandler`,
   …). The view delegates to a service or directly to the handler. See
   [architectural patterns](architecture.md).

3. **An action layer between service and handler.** State changes that
   should be auditable or undoable run through an `ActionType` instead of
   straight to a handler. See [action system](../technical/action-system.md).

## The mental model in one sentence

> A user table in Baserow is data that *describes* a Django model — at
> request time, that data is turned into a real Django model via
> `Table.get_model()`, and from there it behaves like any other ORM model
> for the duration of the request.

Hold that, and the rest of the architecture stops feeling weird.

## Related

- [Systems overview](../technical/systems-overview.md).
- [Architectural patterns](architecture.md).
- [Registries](registries.md).
- [Field system](field-system.md).
- [Dynamic models](../technical/dynamic-models.md).
