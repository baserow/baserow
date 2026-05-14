# Creating a feature

The practical how-to. When you sit down to add a new endpoint, action,
handler, or model in Baserow, this is the order to do things in and the
files you'll touch.

Read [Architectural patterns](architecture.md), [Registries](registries.md)
and [Queries](queries.md) first if you haven't.

## The shape of a typical feature

Most user-visible features in Baserow split into these layers, in this order:

1. **Model** — the persisted state.
2. **Migration** — getting that state into the database safely.
3. **Handler** — the business logic.
4. **Action** — if it's a state change worth recording / undoing.
5. **Service** — permissions, fetch optimisation, composition.
6. **View** — DRF view, URL, serializer, error mapping.
7. **Tests** — unit + API + occasionally e2e.
8. **Changelog entry.**

If your feature is read-only there is no action; if it's trivial there may be
no service. Everything else is almost always present.

## Adding a model

Where it goes:

- **Core concept** (workspace, user, application, notification): under
  `backend/src/baserow/core/<area>/models.py`.
- **Database application concept** (table, field, view, row metadata,
  webhook): `backend/src/baserow/contrib/database/<area>/models.py`.
- **Premium / enterprise** feature: under the matching plugin directory.

Conventions:

- Inherit from `CreatedAndUpdatedOnMixin` if you want `created_on` /
  `updated_on` columns (most models do).
- Inherit from `HierarchicalModelMixin` and implement `get_parent()` if your
  model fits into the hierarchy (almost everything does — workspace →
  application → table → field/view/row, etc.). This is what lets generic
  permission checks walk the tree.
- Add `Meta.ordering` if the natural sort isn't insertion order.
- Add indexes for any query path that filters by columns other than primary
  key in production traffic.

If the model is **trashable**, inherit from `TrashableModelMixin` and register
a `TrashableItemType` for it (see [trash system](../technical/trash-system.md)).

## Writing a migration (zero-downtime)

Baserow is deployed without downtime, so migrations need to coexist with old
code reading and writing the same tables. Follow these patterns.

### Nullable-then-backfill-then-NOT-NULL

For a new non-nullable column on a non-trivial table, split into three
migrations (or three operations in one migration):

1. `AddField(name="x", null=True, default=None)`.
2. `RunPython(populate_x, reverse_populate_x)` to backfill.
3. `AlterField(name="x", null=False)`.

Worked example: `baserow/contrib/database/migrations/0053_add_and_move_public_flags.py`
uses temp fields (`public_temp`, `slug_temp`), backfills with
`bulk_update(batch_size=...)`, then renames back.

### Backfill in batches

`RunPython` migrations must batch and commit periodically on large tables.
Don't load millions of rows into memory.

```python
def populate_x(apps, schema_editor):
    Model = apps.get_model("app", "Model")
    for chunk in chunked_iterator(Model.objects.all(), chunk_size=1000):
        Model.objects.bulk_update(
            [update_one(obj) for obj in chunk], ["x"], batch_size=100
        )
```

A real example with explicit batching and atomic-per-chunk semantics:
`baserow/core/migrations/0081_usersource_uid.py` (single-pass, but the
pattern is the same) and
`baserow/contrib/database/migrations/0081_batch_webhooks.py` (multi-chunk).

### `atomic = False` for index operations

PostgreSQL's `CREATE INDEX CONCURRENTLY` doesn't run in a transaction. To use
it, set `atomic = False` on the migration class and use `RunSQL` with
`CREATE INDEX CONCURRENTLY IF NOT EXISTS ...`.

Worked example: `baserow/core/migrations/0113_alter_notification_options_and_more.py`.

### Use `apps.get_model()` in `RunPython`

Never `from app.models import Model` inside a migration function — at the
point your migration runs, the schema may not match the current model code.
Use `apps.get_model("app", "Model")`.

### Reversibility

Every `RunPython` and `RunSQL` should pass a `reverse_code` / `reverse_sql`,
even if it's a no-op. Without one, the migration cannot be rolled back, which
makes incident response much harder.

### Check before commit

- Did you add a NOT NULL with no default on a large table? (Wrong.)
- Did you create an index without `CONCURRENTLY` on a large table? (Wrong.)
- Did you put a `RunPython` that scans millions of rows in a single
  transaction? (Wrong.)
- Did you import models directly? (Wrong.)

The full migration checklist is in
[Migration conventions in the queries doc](queries.md). When in doubt, ask
in review.

## Writing a handler

Where it goes:

- Core handler: `baserow/core/handler.py` or domain-specific
  `baserow/core/<area>/handler.py`.
- Database handler: `baserow/contrib/database/<area>/handler.py`.

A handler is a class with classmethods (or a singleton with instance methods —
both styles exist). The single most important property: a handler method must
be callable **without HTTP context**. From a shell, a management command, a
Celery task, a test. If you find yourself reaching for request/response data
inside a handler, you want a service.

What a handler typically does:

1. Validates inputs that can't be checked at the API layer (cross-model
   invariants, business rules).
2. Loads required state, often inside `transaction.atomic()`.
3. Mutates state.
4. Emits signals.

What a handler should *not* do:

- HTTP serialisation. That's the view.
- Permission checks. That belongs in the service (or the action's `do()` if
  there's no service yet).
- Build error responses. Raise domain exceptions; let the view map them.

See [queries](queries.md) for ORM patterns inside a handler.

## Writing an action

If your operation should be in the audit log or undoable, wrap it in an
`ActionType`. The full how-to is in
[action-system](../technical/action-system.md); the short version:

1. Subclass `ActionType` (non-undoable) or `UndoableActionType`.
2. Define a `type: str` and a `Params` dataclass capturing everything you
   need to undo.
3. Implement `do()` to call your handler and `register_action(...)`.
4. For undoable: implement `undo()` and `redo()`.
5. Implement `scope()` to return the right `ActionScopeStr` for undo scoping.
6. Register in `apps.py`.

Service-or-view code then calls `MyActionType.do(user, ...)` instead of the
handler directly.

## Writing a service

Where it goes: next to the handler. Either `service.py` / `services.py`
(single class) or a `services/` package (multiple). Both patterns exist.

The decision rule: create a service for new code unless the endpoint is a
trivial read with no permission nuance. Direct view-to-handler is acceptable
for simple GETs and considered legacy for everything else.

A typical service method does:

1. `CoreHandler().check_permissions(user, operation, workspace=...,
   context=...)`.
2. Loads only what's needed for this operation, with the right
   `select_related` / `prefetch_related`.
3. Delegates to an action (state change) or handler (read).
4. Returns plain data the view can serialise.

The view becomes a one-liner: deserialise input, call the service, serialise
output.

## Writing a view

Where it goes:

- `backend/src/baserow/<area>/api/<resource>/views.py` (DRF view).
- `backend/src/baserow/<area>/api/<resource>/serializers.py`.
- `backend/src/baserow/<area>/api/<resource>/urls.py`.
- `backend/src/baserow/<area>/api/<resource>/errors.py` for the exception
  mapping.

Conventions:

- Use DRF `APIView` or `GenericAPIView` subclasses.
- Use `map_exceptions` to translate domain exceptions to HTTP responses.
- Document with `extend_schema` decorators so the OpenAPI / redoc page picks
  up the endpoint.
- Validate the request body via a serializer — never reach into
  `request.data` directly.
- Do not call handlers directly if a service exists.

The custom token API for database tokens has a separate documentation page in
`web-frontend/modules/database/pages/APIDocsDatabase.vue` — if your endpoint
is accessible by API token, update that too.

## Writing tests

Conventions in this codebase:

- **Unit tests** for handlers and services live in
  `backend/tests/baserow/.../test_<module>.py`, mirroring the source layout.
- **API tests** for views live alongside the unit tests with `test_<area>_views.py`
  filenames; they use `APIClient`.
- **`data_fixture`** is the test fixture that creates DB objects efficiently.
  Use `data_fixture.create_text_field(...)`, `data_fixture.create_row_for_many_to_many_field(...)`,
  etc. Search existing tests for examples.
- **Query-count tests** for hot paths. See [queries](queries.md).
- **Snapshot / serialisation round-trip tests** for any new field type or
  view type. See [serialization](../technical/serialization-system.md).

## Wiring it up

Once your model, handler, action, service and view exist, the loose ends:

- **Register everything in `apps.py`** — actions, field types, view types,
  trash item types, notification types, scopes — they all register in
  `ready()`. Forgetting this is the #1 way new features don't work in
  production but pass tests.
- **Add a changelog entry** in `changelog/entries/unreleased/` using
  `changelog/src/changelog.py`. The PR template will remind you.
- **Update docs** if your feature has a user-facing surface.
- **Premium/enterprise**: code lives under `premium/` or `enterprise/`. Core
  code must not import from these directories.
- **Realtime updates** — if the change should propagate to other clients,
  make sure your handler emits a signal and there's a receiver in `ws/` that
  translates it. The action system handles this for actions automatically via
  `action_done`.

## Checklist before opening the PR

- [ ] Handler is callable without HTTP context.
- [ ] View has no business logic.
- [ ] Permission check happens (in service or action).
- [ ] State change is an action if it should be auditable or undoable.
- [ ] Signal emitted for any change other clients should see.
- [ ] N+1 audited; query-count test added for hot paths.
- [ ] Migration follows zero-downtime conventions; reversible.
- [ ] All new types registered in `apps.py`.
- [ ] Serialisation `export_serialized` / `import_serialized` implemented for
      any new persisted concept.
- [ ] Changelog entry added.
- [ ] Tests cover the happy path + 1-2 edge cases.
- [ ] Docs updated if user-facing.

## Related

- [Architectural patterns](architecture.md).
- [Registries](registries.md).
- [Queries](queries.md).
- [Action system](../technical/action-system.md).
- [Engineering workflow](../development/engineering-workflow.md).
