---
name: manage-backend-layers
description: Manage Baserow backend feature layers across Django models, handlers, services, undoable actions, serializers, API views, URLs, permissions, signals, migrations, and tests. Use when adding or changing backend CRUD/domain behavior that spans model, handler, service, action, and view layers; use the automation modules as the preferred modern pattern.
---

# Manage Baserow Backend Layers

Use this skill when a backend change spans several Baserow layers, especially:

- Django models and migrations
- `handler.py` domain/persistence methods
- `service.py` user-facing permission-aware orchestration
- `actions.py` undo/redo action types
- API serializers, errors, views, and URLs
- signals, permission operations, trash/search/import-export support
- focused backend tests

Prefer the newer automation modules as the first pattern source:

- Workflows: `backend/src/baserow/contrib/automation/workflows/`
- Nodes: `backend/src/baserow/contrib/automation/nodes/`
- API views: `backend/src/baserow/contrib/automation/api/workflows/views.py`
- API node views: `backend/src/baserow/contrib/automation/api/nodes/views.py`

## First Step

Identify the feature surface and inspect the nearest existing module before editing:

1. Is this a new model-backed concept, or a change to an existing model?
2. Is the behavior pure domain persistence, user-facing mutation, undoable, API-exposed, or all of those?
3. Does it need permissions, workspace scoping, signals, trash, import/export, ordering, or specific typed subclasses?
4. Is there a close automation workflow/node pattern, or a closer pattern in the target app?

Useful searches:

Use `rg -n "<pattern>" <paths>` as a faster equivalent when `rg` is available.

- `grep -RInE "class .*Handler|class .*Service|UndoableActionType|APIView" backend/src/baserow/contrib/automation`
- `grep -RInE "check_permissions|filter_queryset" backend/src/baserow/contrib/automation`
- `grep -RInE "@transaction.atomic|@map_exceptions|@validate_body|@require_request_data_type" backend/src/baserow`
- `grep -RInE "ActionTypeDescription|register_action|def undo|def redo" backend/src/baserow`
- `grep -RInE "objects_and_trash|TrashHandler|TrashableModelMixin|OrderableMixin" backend/src/baserow`

## Layer Responsibilities

Keep responsibilities separated. This is the core rule of the skill.

### Models

Models define persistence, relations, managers, ordering, mixins, and small model-local helpers.

Follow patterns from:

- `automation/workflows/models.py`
- `automation/nodes/models.py`
- Nearby target app models

Checklist:

1. Add fields, constraints, indexes, related names, and managers.
2. Use existing mixins when relevant: `CreatedAndUpdatedOnMixin`, `OrderableMixin`, `TrashableModelMixin`, `HierarchicalModelMixin`.
3. Add `objects_and_trash = models.Manager()` when trashed rows must be addressable.
4. Keep cross-object business workflows out of models unless nearby code already does it.
5. Add a migration for any schema change.

### Handlers

Handlers own domain logic and persistence without assuming an authenticated user permission context.

Follow patterns from:

- `automation/workflows/handler.py`
- `automation/nodes/handler.py`

Use handlers for:

- Fetching objects and raising domain exceptions like `DoesNotExist`
- Queryset construction, `select_related`, `prefetch_related`, and `specific_iterator`
- Create/update/delete persistence
- `extract_allowed`, allowed field lists, and m2m handling
- duplication, import/export, ordering, cache invalidation, trash mechanics
- returning typed result objects for original/new values when useful for undo

Avoid in handlers:

- `CoreHandler().check_permissions(...)`
- request objects, API serializers, or response shaping
- undo action registration
- broad side effects unless the existing module's handler clearly owns them

### Services

Services are the user-facing backend application layer. They usually accept `user`, check permissions, call handlers, emit signals, and coordinate related domain handlers.

Follow patterns from:

- `automation/workflows/service.py`
- `automation/nodes/service.py`

Use services for:

- `CoreHandler().check_permissions(...)`
- `CoreHandler().filter_queryset(...)`
- mapping API-facing IDs to model relations
- validating workspace membership or cross-object constraints
- calling the handler after permissions pass
- sending domain signals after successful mutations
- coordinating cache, graph, integration, notification, or related-object updates

Keep services callable from API views, action types, jobs, and tests. Do not return DRF responses from services.

### Actions

Use `UndoableActionType` for user-facing mutations that should participate in undo/redo or action history.

Follow patterns from:

- `automation/workflows/actions.py`
- `automation/nodes/actions.py`

Checklist:

1. Give each action a stable `type`.
2. Define an `ActionTypeDescription` and a dataclass `Params`.
3. `do(...)` should call the service, then `register_action(...)`.
4. Store enough IDs and original/new values in params for undo and redo.
5. Scope the action using the nearest existing scope type, often application or workspace scope.
6. `undo(...)` and `redo(...)` should call services or trash restore helpers, not duplicate persistence logic.

Use a plain service call instead of an action only when the operation is internal, read-only, non-user-facing, or nearby code does not make similar mutations undoable.

### API Serializers, Errors, Views, URLs

Views should be thin and explicit. They validate input, map exceptions, invoke actions or services, serialize output, and return responses.

Follow patterns from:

- `automation/api/workflows/serializers.py`
- `automation/api/workflows/errors.py`
- `automation/api/workflows/views.py`
- `automation/api/nodes/serializers.py`
- `automation/api/nodes/views.py`
- `automation/api/*/urls.py`

Checklist:

1. Add request and response serializers near the API module.
2. Add API error constants for domain exceptions.
3. Use `@extend_schema` with operation IDs, tags, parameters, request, and response schemas.
4. Use `@transaction.atomic` around mutations.
5. Use `@map_exceptions` to map domain exceptions to API error constants.
6. Use `@validate_body(...)` for simple serializers.
7. Use registry discriminator helpers when the model is typed or polymorphic.
8. Call action `do(...)` for undoable mutations; call services for reads and non-undoable operations.
9. Register URLs in the local API `urls.py` and any parent API URL file if needed.

## Implementation Order

For model-backed CRUD/domain features, work in this order:

1. Model and domain exceptions
2. Handler methods with allowed fields and typed return values if needed
3. Operation types and permission behavior
4. Service methods with permission checks and signals
5. Undoable action types for user-facing mutations
6. API serializers, errors, views, and URLs
7. Registrations in `apps.py`, registries, trash/search/object scope modules, or signal receivers
8. Migrations
9. Tests

For a change to an existing feature, first trace the existing call chain from URL to view to action/service to handler to model, then patch the narrowest layer that owns the behavior.

## Permission And Signal Pattern

For permission-aware mutations, the common shape is:

1. Service fetches the parent or target object through a handler.
2. Service calls `CoreHandler().check_permissions(...)` with the specific operation type, workspace, and context.
3. Service validates cross-object constraints.
4. Service calls the handler mutation.
5. Service sends a domain signal after success.
6. Action wraps the service call and registers undo metadata.
7. View calls the action inside `transaction.atomic`.

Do not skip operation types when introducing a new user-visible capability. If permissions are part of the task, also use the `Manage Baserow Permissions` skill.

## Tests

Use the `Write Baserow Backend Tests` skill for detailed test conventions. At minimum, add or update focused tests for:

- handler create/update/delete or ordering behavior
- service permission checks and signal side effects
- action undo/redo behavior when actions are involved
- API status codes, validation, exception mapping, and response shape
- migrations or data backfills when behavior depends on existing rows

Good automation test locations to inspect:

- `backend/tests/baserow/contrib/automation/workflows/`
- `backend/tests/baserow/contrib/automation/nodes/`
- `backend/tests/baserow/contrib/automation/api/`

Run the narrowest relevant backend test first:

- `just b test tests/baserow/contrib/automation/workflows/`
- `just b test tests/baserow/contrib/automation/nodes/`
- `just b test tests/path/to/test_file.py`

## Guardrails

- Do not put permission checks in handlers unless the target module already has that older pattern and changing it would be out of scope.
- Do not duplicate mutation logic in views, actions, services, and handlers. Each layer should delegate down.
- Do not register an undoable action without enough params to undo and redo deterministically.
- Do not expose a model mutation through an API view without mapping its domain exceptions.
- Do not add model fields without a migration. Check with `just b manage makemigrations --check`.
- Do not forget queryset scoping and `workspace` context in permission checks.
- Do not rename persisted action types, operation types, or API routes casually.
- Prefer the closest existing module pattern over a new abstraction.
