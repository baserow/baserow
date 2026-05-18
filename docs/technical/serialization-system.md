# Serialization system

The serialization system is the mechanism Baserow uses to convert applications,
tables, views, fields, rows and a lot of other state into a portable
JSON-and-ZIP representation, and back again.

It is what powers, behind the scenes:

- **Templates** — the catalog of pre-built applications shipped with Baserow is
  just a set of serialized applications imported on first run.
- **Workspace export / import** — exporting a workspace to share or back up,
  and re-importing it elsewhere.
- **Snapshots** — taking a point-in-time copy of an application and restoring
  it later. Snapshots are stored as serialized data.
- **Duplication** — the "duplicate database" / "duplicate table" / "duplicate
  view" operations are implemented as in-memory `export_serialized` →
  `import_serialized` round trips.
Because so many features funnel through this system, it has strong implications
when you change a model or registry: if you don't update the
`export_serialized` / `import_serialized` paths, **template loading,
duplication and snapshots silently break**.

## The pattern

Every registry whose entries own user-visible state implements two methods on
its `Instance` base class:

- `export_serialized(instance, ...)` — return a JSON-serialisable dict
  describing the instance.
- `import_serialized(parent, serialized_values, id_mapping, ...)` — given the
  dict, recreate the instance under a new parent, populating an `id_mapping`
  dict from old ids → new ids so downstream cross-references can be rewritten.

Registries that participate include `application_type_registry`,
`field_type_registry`, `view_type_registry`, `view_filter_type_registry`,
`view_decoration_type_registry`, `formula_function_type_registry`,
`webhook_event_type_registry`, and several more in `core` and `contrib`.

The base classes live in `backend/src/baserow/core/registries.py`
(`ApplicationType`) and in each app's `registries.py` (e.g.
`FieldType.export_serialized`,
`ViewType.export_serialized`).

## Shape of the export

The application-level export, for a `database` application, looks roughly like:

```jsonc
{
  "id": 42,
  "name": "My database",
  "order": 1,
  "type": "database",
  "tables": [
    {
      "id": 100,
      "name": "Customers",
      "order": 1,
      "fields": [
        {"id": 1000, "type": "text", "name": "Name", "order": 1, ...},
        {"id": 1001, "type": "number", "name": "Revenue", "order": 2, ...}
      ],
      "views": [
        {
          "id": 2000,
          "type": "grid",
          "name": "All",
          "filters": [...],
          "sortings": [...],
          "decorations": [...]
        }
      ],
      "rows": [
        {"id": 1, "field_1000": "Acme", "field_1001": "1000.0", ...}
      ]
    }
  ]
}
```

Files (uploads, exports) referenced by serialized rows are written into a
companion `ExportZipFile` and referenced by relative path. The pair (JSON +
ZIP) is what gets stored / transmitted.

## `id_mapping`

The most important parameter in the import path. When importing a serialized
application into a workspace, every primary key gets remapped to a new one (so
that templates can be imported many times into the same workspace without
collision). `id_mapping` is the dictionary that records "old id 1000 became new
id 5042" so that when a row arrives whose `field_1000` value is set, the
importer can find the corresponding new field.

Conventionally, `id_mapping` has typed keys like
`"database_fields"`, `"database_views"`, `"database_view_filters"`,
`"database_rows"`, etc., each pointing at a `{old_id: new_id}` dict.

If you add a new type, give it its own key so other types' importers can rely
on it.

## `SerializationProcessorType`

A separate registry (`serialization_processor_registry`) lets you piggyback
extra data onto the serialized structure without modifying the core types.
This is how the search system, formulas, and other cross-cutting concerns
serialise their auxiliary state. Each processor implements
`export_serialized` and `import_serialized` that take a `serialized_structure`
dict and return / receive the same dict possibly with extra keys.

This is how core stays decoupled from concerns that span the system, e.g.
search indexes don't appear on field types' own export but get attached
through a processor.

## Round trips: duplicate, snapshot, restore

These three operations all use the same shape:

1. `application_type.export_serialized(application, config, files_zip)`
   produces the serialised dict (and an in-memory zip).
2. (Optional) persist to storage — snapshots store both; duplications keep
   the data in memory.
3. `application_type.import_serialized(workspace, serialized, config,
   id_mapping, files_zip)` produces a new application in the target workspace.

The `ImportExportConfig` (`baserow.core.registries`) controls
flags: whether to include row data, whether to remap permissions, whether the
files are external or internal, etc.

## Templates

Templates are JSON+ZIP files committed under
`backend/templates/`. On first run (or on `loaddata` calls), each template is
imported into a special templates workspace. When a user "installs a
template", that workspace's application is duplicated into theirs — again,
via the same `export_serialized` / `import_serialized` round trip.

## Adding a new type — serialisation checklist

When you add a new `FieldType`, `ViewType`, registered registry entry, or any
new model that participates in user-visible state, the serialisation work is
the easy thing to forget. Run this checklist:

1. Override `export_serialized()` to include every persisted attribute the type
   cares about (and recursively serialise sub-objects — e.g. a view's filters).
2. Override `import_serialized()` to:
   - Build the new instance under the supplied parent.
   - Use `id_mapping` to translate any cross-references in the serialised
     dict.
   - Add `{old_id: new_id}` to the right `id_mapping` bucket so other types
     can reference the new id.
3. Round-trip test: write a fixture, export it, import into a fresh workspace,
   compare. There's `baserow.test_utils` plumbing for this — search existing
   field type tests for `export_serialized` to find patterns.
4. If your type involves user-uploaded files, pass them through the
   `files_zip` parameter and reference them by archive path in the JSON.
5. If your data needs a side-channel that doesn't fit on the type itself,
   register a `SerializationProcessorType`.

## Gotchas

- **JSON-serialisable.** Values must round-trip through `json.dumps`. Date
  objects, decimals, sets — all must be converted to a JSON-safe form on
  export and restored on import.
- **`extract_allowed` and `CoreExportSerializedStructure`.** When the
  `ApplicationType` builds the core "shell" of the export, only a fixed list
  of fields (`["id", "name", "order", "type", "snapshot_from"]`) is
  guaranteed; everything else has to come from your subclass.
- **Order matters for fields and views.** Importers re-sort by `order` after
  insertion; don't rely on the source ordering being preserved if `order` is
  stale.
- **Row imports are by far the heaviest path.** For large applications the
  importer batches rows and uses `bulk_create` (see [queries](../patterns/queries.md))
  to keep performance acceptable.
- **Backwards-compatibility.** Old templates and snapshots must still import
  on a new Baserow version. If you change a field type's export shape, you
  need a migration path in `import_serialized` that handles both old and new
  formats.

## Related

- [Systems overview — Serialization system](systems-overview.md#serialization-system).
- [Snapshots — runbook stub](../runbooks/back-up-and-restore-baserow.md).
