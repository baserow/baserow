# Database plugin

The database plugin is the Baserow application type that gives users tables,
fields, views, formulas, search, and everything spreadsheet-like. It is one of
several application types in Baserow (`builder`, `automation`, `dashboard`,
`integrations` are the others) and lives in
`backend/src/baserow/contrib/database/`.

This page is the entry into the database-specific architecture. If you're new
to the codebase, start with the [systems overview](systems-overview.md), then
[architectural patterns](../patterns/architecture.md), then
[registries](../patterns/registries.md), and only then this page.

## What it contains

A database application owns:

- **Tables** — each user table is backed by its own PostgreSQL table and a
  Django model generated at runtime. See
  [dynamic models](dynamic-models.md).
- **Fields** — the columns of a table. Each field type
  (`text`, `number`, `link_row`, `formula`, …) is a registered `FieldType`.
  See [field system](../patterns/field-system.md) and
  [Create field type](../plugins/field-type.md).
- **Views** — alternative presentations of the same data (grid, gallery,
  kanban, calendar, …). Each view type is a registered `ViewType`. See
  [Create view type](../plugins/view-type.md).
- **Rows** — the actual data, accessed through the dynamically generated model
  of each table.
- **Webhooks** — outbound HTTP callbacks fired when table state changes.
- **Data sync** — periodic sync from external sources (Airtable, ICS, JSON,
  …) into a table.
- **Imports / exports** — bulk row import from CSV/JSON/XML/Excel; exports to
  the same formats. See
  [systems overview — table/view import/export](systems-overview.md#table--view-import--export-system).
- **Search** — TSV-backed full-text search per table. See
  [workspace search](workspace-search.md).
- **Formulas** — a typed formula language with cross-field dependency
  tracking. See [formula technical guide](formula-technical-guide.md).

## Working with tables programmatically

Every operation has a handler entry point. Examples:

```python
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler

# Create a table
table = TableHandler().create_table(user, database, name="Customers")

# Add fields
name_field = FieldHandler().create_field(
    user, table, "text", name="Name", primary=True,
)
revenue_field = FieldHandler().create_field(
    user, table, "number", name="Revenue",
)

# Insert a row using the dynamically generated model
model = table.get_model()
row = RowHandler().create_row(
    user, table,
    {f"field_{name_field.id}": "Acme", f"field_{revenue_field.id}": 100000},
)

# Query the rows
for row in model.objects.all():
    print(row.id, getattr(row, f"field_{name_field.id}"))
```

The same operations can run through the REST API. Handlers are the canonical
business logic; the API is a serialisation layer over them. See
[architectural patterns](../patterns/architecture.md).

## Module layout

`backend/src/baserow/contrib/database/`:

| Subfolder | What's there |
|---|---|
| `api/` | DRF views, serializers, URLs, exception mappings. |
| `table/` | `TableHandler`, `Table` model, dynamic model generation, table cache. |
| `fields/` | `FieldHandler`, every built-in `FieldType`, field converters, dependency tracking. |
| `views/` | `ViewHandler`, every built-in `ViewType` (grid, gallery, kanban, calendar, form), view filters, sortings, decorations, group bys. |
| `rows/` | `RowHandler`, row signals, row history. |
| `webhooks/` | Outbound webhook delivery. |
| `data_sync/` | Periodic sync from external data sources. |
| `file_import/` | CSV / JSON / XML / Excel importers. |
| `export/` | Row data exporters. |
| `formula/` | Formula parser, type system, function registry, AST. |
| `search/` | TSV-based search indexing. |
| `airtable/` | Airtable importer. |
| `data_providers/` | Pluggable data-provider hooks used by formulas. |
| `field_rules/` | Computed field-rule infrastructure. |
| `migrations/` | Django migrations for the contrib.database app. |
| `apps.py` | Application registration — every type, handler, signal connects here. |

Mirror layout in `web-frontend/modules/database/` for the frontend
counterpart: components, services, stores, realtime handlers, and the Nuxt
modules that wire them up.

## Cross-cutting concerns

Many subsystems hook into database operations through signals (see
[architectural patterns](../patterns/architecture.md)):

- The search system reindexes affected rows on writes.
- The websocket layer broadcasts changes to subscribed clients.
- The formula / field-dependency system recomputes derived values.
- The notification system emits user mentions and collaborator events.
- The trash system intercepts deletions for soft-delete + retention.

If you change how a handler writes data, audit the receivers in `baserow.ws.*`,
`baserow.contrib.database.search`, the dependency code in
`baserow.contrib.database.fields.dependencies`, and the notification handlers.

## See also

- [Systems overview](systems-overview.md) — the map of subsystems.
- [Architectural patterns](../patterns/architecture.md) — request flow shape.
- [Registries](../patterns/registries.md) — the extension pattern.
- [Field system](../patterns/field-system.md) — the central architectural
  concept of the database plugin.
- [Dynamic models](dynamic-models.md) — how `Table.get_model()` works.
- [Formula technical guide](formula-technical-guide.md).
- [Workspace search guide](workspace-search.md).
- [Undo/redo guide](undo-redo-guide.md).
- [Permissions guide](permissions-guide.md).
- [Action system](action-system.md).
- [Trash system](trash-system.md).
- [Notification system](notification-system.md).
- [Serialization system](serialization-system.md).
- [Plugin guides for the database](../plugins/introduction.md).
