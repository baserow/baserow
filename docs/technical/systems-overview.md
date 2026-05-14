# Systems overview

This is the high-level map of the major subsystems that make up Baserow. It is the
recommended starting point before diving into any individual technical guide.

Each system below has a one-paragraph description and, where one exists, a pointer to
the deeper guide. Some systems are well documented; others currently live only in the
code. Open follow-ups to fill the gaps are tracked separately.

For the architectural pattern that ties these systems together (view → service →
action → handler → ORM, plus signals and realtime), see
[Architectural patterns](../patterns/architecture.md). For the registry pattern that
nearly every system uses to make itself extensible, see
[Registries](../patterns/registries.md).

## Generated model / user table system

Each user-created table is backed by its own PostgreSQL table and a dynamically
generated Django model. `Table.get_model()` builds the model class on demand from the
table's field definitions, which lets us reuse Django ORM and migrations to manage
user data. Field serialisations are cached through the Django cache backend (Redis in
production, in-memory in tests) to avoid regenerating them on every request. The
relevant entry points are `baserow.contrib.database.table.handler.TableHandler` and
`Table.get_model()`.

## Field system

Fields are the column definitions of user tables. Each field type (`text`, `number`,
`link_row`, `formula`, …) is a subclass of `FieldType` registered in
`field_type_registry`, and it owns the rules for storage, validation, search
representation, formula compatibility, import/export, and converters when a field
changes type. `FieldHandler` is the orchestration layer that creates, updates, deletes
and converts fields, coordinating side effects across dependent systems (dynamic model
regeneration, search reindex, formula recomputation, dependency graph updates).

See also: [Create database table field](../plugins/field-type.md),
[Field converters](../plugins/field-converter.md).

## Serialization system

Allows exporting Baserow applications to and from JSON / ZIP. It powers templates,
workspace export/import, snapshots, and the in-memory "duplicate" flow (every
duplication is just a serialize-then-deserialize round trip). Each registry that owns
user-visible types implements `export_serialized` / `import_serialized` on its
instances. See `baserow.core.export_serialized` and the per-app
`export_serialized.py` modules.

## Action system

The event-based backbone of user-driven changes. Every state-changing user operation
goes through an `ActionType` so it can be audited and, where applicable, undone or
redone. `ActionHandler.do()` runs the action and writes an `Action` model row to the
audit log. Actions live in `actions.py` modules per domain
(e.g. `baserow/contrib/database/rows/actions.py`). The registry and base classes are
in `baserow.core.action.registries`.

See also: [Undo/redo guide](undo-redo-guide.md).

## Permissions system

A flexible system used for RBAC, personal/restricted views, and staff/admin-only
features. `CoreHandler.check_permissions()` is the single entry point; the actual
check is delegated to the registered `PermissionManagerType` chain
(`permission_manager_type_registry`). Some managers live in core; RBAC and several
others live in `enterprise/`.

See also: [Permissions guide](permissions-guide.md).

## Realtime system

Sends realtime updates to clients over Django Channels websockets when state changes.
Backend handlers emit Django signals; receivers in `baserow.ws.*` translate those
signals into messages addressed to relevant page/table subscribers. The frontend has
matching realtime handlers that update the Vuex store, which causes components to
re-render without a page refresh.

See also: [WebSockets guide](websockets.md),
[WebSocket API](../apis/web-socket-api.md).

## Trash system

Provides soft-deletion and restore for almost every user-visible entity (workspace,
application, table, field, row, view). Deletions move objects to the trash; after the
retention window (`HOURS_UNTIL_TRASH_PERMANENTLY_DELETED`, default 72) a periodic
Celery task permanently removes them. Each trashable type registers a
`TrashableItemType` in `trash_item_type_registry` describing how to trash, restore and
permanently delete its instances. Entry point: `baserow.core.trash.handler.TrashHandler`.

## Search system

Maintains per-column TSV (PostgreSQL full-text search) representations so that
searching across user tables is fast even on large datasets. Field types decide how
their values get serialized into the TSV column; field updates, row writes and field
type conversions all trigger reindex paths. See
`baserow.contrib.database.search` and `baserow.core.search.registries`.

See also: [Workspace search guide](workspace-search.md).

## Notification system

Sends in-product notifications (and, where configured, emails) to users when
something happens that they care about: a row mention, a collaborator assignment,
a job completion, etc. Each notification kind is a `NotificationType` registered in
`notification_type_registry`, which owns the formatting, recipient resolution, and
delivery channels. Entry point:
`baserow.core.notifications.handler.NotificationHandler`.

## Table / view import / export system

Allows bulk-importing data into tables from CSV/JSON/XML/Excel and exporting tables or
views to a file. Importers and exporters are types registered in their respective
registries; long imports are executed as jobs (see [Job system](#job-system)) with
progress reporting and cancellation. See `baserow.contrib.database.file_import` and
`baserow.contrib.database.export`.

## Formula system

Lets users define formulas that compute cell values from other fields, and recompute
those values when their dependencies change. The formula language has its own parser,
type system, function registry, and an execution path that compiles formulas down to
Django expressions for evaluation at the database level. This is the most complex
system in the codebase; defer the deep dive until the rest of the map is in place.

See also: [Formula technical guide](formula-technical-guide.md),
[Understanding Baserow formulas](../tutorials/understanding-baserow-formulas.md).

## Field dependency system

Tracks which fields depend on which other fields (primarily because of formulas, link
rows, lookups and rollups). When a field value or field definition changes, the
dependency graph is used to decide what else has to be recomputed or reindexed. See
`baserow.contrib.database.fields.dependencies` and
`FieldDependencyHandler`.

## License / feature / pricing system

Gates premium and enterprise features behind license checks. Code that runs only
under a license lives under `premium/` or `enterprise/`; the core has no direct
knowledge of either. Feature checks go through `LicenseHandler` and the feature
registry. Avoid coupling core or contrib code to license state — use the registered
hooks instead.

## Telemetry / logs / metrics

Sends traces, logs and metrics via OpenTelemetry. Tracing is wired through
`baserow.core.telemetry` and applied broadly via the `baserow_trace_methods`
decorator on handlers and action types. Production traces are shipped to Honeycomb.

See also: [Metrics and logs](../development/metrics-and-logs.md),
[Monitoring Baserow](../installation/monitoring.md).

## Plugin system

External code can extend Baserow by registering new application types, field types,
view types, filters, formula functions, etc. into the same registries the built-in
code uses. The premium and enterprise editions are themselves plugins, which is the
mechanism that keeps the licensing boundary clean.

See also: [Plugin basics](../plugins/introduction.md).

## Job system

Moves costly user-triggered operations (duplications, exports, large imports,
snapshots) to a Celery worker so the request thread stays responsive. Each job kind
is a `JobType` in `job_type_registry`; jobs report progress, can be cancelled, and
can broadcast realtime updates as they advance.

See also: [Jobs pattern](../patterns/jobs.md).

## Where this fits

If you are new to Baserow, read this page first, then
[Architectural patterns](../patterns/architecture.md) and
[Registries](../patterns/registries.md). After that, the deeper per-system guides
(undo/redo, permissions, websockets, workspace search, jobs) can be read in any
order driven by whatever you happen to be working on.
