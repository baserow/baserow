# Database plugin

The database plugin is the Baserow application type that gives users tables,
fields, views, formulas, search, and everything spreadsheet-like. It is one of
several application types Baserow ships under `backend/src/baserow/contrib/`;
this page is the deep dive for the database type, which lives in
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
  See [field system](../patterns/field-system.md).
- **Views** — alternative presentations of the same data (grid, gallery,
  kanban, calendar, …). Each view type is a registered `ViewType`. See
  [view filters](../patterns/view-filters.md) for one common extension point.
- **Rows** — the actual data, accessed through the dynamically generated model
  of each table.
- **Webhooks** — outbound HTTP callbacks fired when table state changes.
- **Data sync** — periodic sync from external sources (Airtable, ICS, JSON,
  …) into a table.
- **Imports / exports** — bulk row import from CSV/JSON/XML/Excel; exports to
  the same formats. See
  [systems overview — table/view import/export](systems-overview.md#table-view-import-export-system).
- **Search** — Postgres full-text search backed by an async-indexed
  per-workspace search table. See
  [table rows full-text search](table-rows-search.md) for the indexing
  pipeline and query path, and [workspace search](workspace-search.md) for
  the cross-type aggregation on top.
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

## Fields

Every column on a user table is a `Field` row, polymorphic on its `FieldType`.
The type owns the behaviour: storage, validation, search representation,
import/export, conversion when the column type changes, and formula
compatibility. See [field system](../patterns/field-system.md) for the
handler architecture and the field-dependency graph, and
[Frontend registries](../patterns/frontend-registries.md) for the matching
frontend type registrations.

| Group | Types | Notes |
|---|---|---|
| Text-like | `text`, `long_text`, `url`, `email`, `phone_number`, `password` | Stored verbatim; `password` is write-only. |
| Numeric & boolean | `number`, `boolean`, `rating`, `autonumber` | `autonumber` is server-assigned per row. |
| Date & time | `date`, `duration`, `created_on`, `last_modified` | `created_on` / `last_modified` are read-only metadata. |
| Choice | `single_select`, `multiple_select` | Backed by `SelectOption`. |
| Files & people | `file`, `multiple_collaborators`, `created_by`, `last_modified_by` | The `*_by` variants are read-only metadata. |
| Relational | `link_row`, `lookup`, `count` | Cross-table; participate in the field-dependency graph. |
| Computed | `formula`, `rollup`, `ai` | Derived values, recomputed via the dependency graph. `ai` is premium. |
| Identity | `uuid` | Auto-generated per row. |

Source of truth: every registered core `FieldType` lives in
`backend/src/baserow/contrib/database/fields/field_types.py`. Premium and
enterprise editions register additional types under
`premium/backend/src/baserow_premium/fields/` and
`enterprise/backend/src/baserow_enterprise/`. The string in the `type` column
above is the wire-level identifier used by the REST API.

## Views

A view is a registered `ViewType` — an alternative presentation of the same
table. Per-view filters, sortings, group-bys, and decorations attach to the
view; the view layer reads rows through the table's dynamic model.

| View type | Edition | What it is |
|---|---|---|
| `grid` | core | Spreadsheet view; the default. |
| `gallery` | core | Card grid driven by a cover field. |
| `form` | core | Public or private form that writes new rows. |
| `kanban` | premium | Columns grouped by a single-select field. |
| `calendar` | premium | Events placed by a date field. |
| `timeline` | premium | Gantt-style range view. |

Source of truth:
`backend/src/baserow/contrib/database/views/view_types.py` for core,
`premium/backend/src/baserow_premium/views/view_types.py` for premium.

## Webhooks

Row, field, and view writes can fire outbound HTTP callbacks. Each event kind
is a `WebhookEventType` registered in `webhook_event_type_registry`; delivery
is asynchronous through Celery with retries and a per-table rate limit, and
the call history is visible to the user. The frontend registers matching
event types so the configuration UI can describe what each event carries.

Source of truth:
`backend/src/baserow/contrib/database/webhooks/` (handler, registries, models,
tasks) and `web-frontend/modules/database/webhookEventTypes.js`.

## Data sync

A data-synced table periodically pulls rows from an external source. Each
source is a `DataSyncType` registered in `data_sync_type_registry`; the type
declares the field schema, fetches rows, and provides a unique key so the
sync upserts instead of duplicating.

| Sync type | Edition | Source |
|---|---|---|
| `ical_calendar` | core | iCalendar URL. |
| `postgresql` | core | A PostgreSQL table. |
| Local Baserow, Jira issues, GitHub issues, GitLab issues, Hubspot contacts | enterprise | Two-way and one-way syncs against SaaS APIs. |

For a one-off bulk import of an entire Airtable base, see the Airtable
importer under `backend/src/baserow/contrib/database/airtable/` — that's a
job, not a recurring sync.

Source of truth:
`backend/src/baserow/contrib/database/data_sync/` for core,
`enterprise/backend/src/baserow_enterprise/data_sync/` for enterprise.

## Formulas

A typed expression language with cross-field dependency tracking, compiled
down to Django ORM expressions and evaluated at the database. The dependency
graph decides what gets recomputed when an upstream value or definition
changes. See [Formula technical guide](formula-technical-guide.md) for the
type system, AST, function registry, and dependency mechanics, and
[Understanding Baserow formulas](../tutorials/understanding-baserow-formulas.md)
for the user-facing tutorial.

## Search and import/export

Full-text search is implemented through a per-workspace `tsvector` search
table populated asynchronously; field types decide how their values are
expressed via `get_search_expression`. See
[Table rows full-text search](table-rows-search.md) for the indexing
pipeline and query path, and [Workspace search](workspace-search.md) for the
cross-type aggregation layer.

Bulk row import (CSV/JSON/XML/Excel) and table/view export use registered
importer and exporter types; long imports run as jobs. See
[Serialization system](serialization-system.md) and
[Systems overview — table/view import/export](systems-overview.md#table-view-import-export-system).

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
- [Table rows full-text search](table-rows-search.md) and
  [workspace search guide](workspace-search.md).
- [AI field architecture](../development/ai-field-architecture.md) and
  [embeddings server](../development/embeddings-server.md) — the premium
  `ai` field type.
- [Undo/redo guide](undo-redo-guide.md).
- [Permissions guide](permissions-guide.md).
- [Action system](action-system.md).
- [Trash system](trash-system.md).
- [Notification system](notification-system.md).
- [Serialization system](serialization-system.md).
- [Legacy plugin guides](../plugins/introduction.md) — historical reference only.
