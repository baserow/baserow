---
name: Manage Baserow Permissions
description: Create, edit, or debug Baserow permission operations and permission managers across backend and frontend, including OperationType, PermissionManagerType, PERMISSION_MANAGERS ordering, frontend permission managers, and permission tests.
---

# Manage Baserow Permissions

Use this skill when a task involves Baserow permissions: adding or editing an
operation, changing backend permission decisions, adding a permission manager,
updating frontend `$hasPermission` behavior, or debugging permission failures.

Start with `docs/technical/permissions-guide.md` when the task needs conceptual
detail. This skill is the implementation checklist; the guide is the source for
the full model and terminology.

## First Step

Before editing, identify which layer is changing:

1. A new or changed `OperationType`
2. A backend `PermissionManagerType`
3. `PERMISSION_MANAGERS` order or enablement
4. A frontend permission manager or `$hasPermission` call
5. Tests for backend, frontend, or both

Then inspect the nearest existing implementation in the same product area:

- Core backend managers: `backend/src/baserow/core/permission_manager.py`
- Core operation registration: `backend/src/baserow/core/apps.py`
- Default manager order: `backend/src/baserow/config/settings/base.py`
- Core frontend managers: `web-frontend/modules/core/permissionManagerTypes.js`
- Core frontend registration: `web-frontend/modules/core/plugin.js`
- Premium examples: `premium/backend/src/baserow_premium/permission_manager.py`,
  `premium/web-frontend/modules/baserow_premium/permissionManagerTypes.js`,
  `premium/web-frontend/modules/baserow_premium/plugin.js`
- Enterprise examples: `enterprise/backend/src/baserow_enterprise/role/permission_manager.py`,
  `enterprise/backend/src/baserow_enterprise/apps.py`,
  `enterprise/web-frontend/modules/baserow_enterprise/permissionManagerTypes.js`,
  `enterprise/web-frontend/modules/baserow_enterprise/plugin.js`

Useful searches:

Use `rg -n "<pattern>" <paths>` as a faster equivalent when `rg` is available.

- `grep -RInE "class .*OperationType" backend/src premium/backend enterprise/backend`
- `grep -RInE "operation_type_registry.register" backend/src premium/backend enterprise/backend`
- `grep -RInE "class .*PermissionManagerType" backend/src premium/backend enterprise/backend`
- `grep -RInE "permission_manager_type_registry.register|PERMISSION_MANAGERS" backend/src premium/backend enterprise/backend`
- `grep -RInE "PermissionManagerType|permissionManager|\\$hasPermission|hasPermission\\(" web-frontend premium/web-frontend enterprise/web-frontend`

## Permission Model

Permission checks are an ordered chain. Each backend permission manager can:

- return `True` to allow
- return a `PermissionException` to deny
- omit the check result to pass through to the next manager

If every manager passes through, the permission is denied by default.

The order in `PERMISSION_MANAGERS` is part of the behavior. Place narrower or
more specific managers before broad fallback managers such as `basic` when they
must be able to allow or deny first.

## Backend Workflow

### Adding or updating an operation

1. Find the closest operation class for the same object family.
2. Define an `OperationType` subclass with a stable `type` string.
3. Set `context_scope_name` to the scope of the object passed as `context`.
4. Set `object_scope_name` when the operation targets different objects than the
   context, especially list operations.
5. Register it in the relevant app config with `operation_type_registry.register(...)`.
6. Update tests or fixtures that enumerate all operations if needed.

Common operation base classes already encode scope choices. Prefer extending the
nearest existing base class instead of filling in scope names manually.

### Adding or updating a backend permission manager

1. Create or update a `PermissionManagerType` subclass near the feature owner.
2. Keep the `type` string stable once persisted or exposed to the frontend.
3. Implement `check_multiple_permissions(self, check, workspace=None, include_trash=False)`.
4. Implement `get_permissions_object(self, actor, workspace=None)` if the frontend
   must make matching permission decisions without another backend request.
5. Implement `filter_queryset(self, actor, operation_name, queryset, workspace=None)`
   when list endpoints or selectors need permission-aware querysets.
6. Register the manager with `permission_manager_type_registry.register(...)`.
7. Add the manager to `PERMISSION_MANAGERS` if it should run in normal settings.

`check_multiple_permissions` must be batch-friendly. Do not perform one query per
check when a set-based lookup can answer the whole batch.

`filter_queryset` must exclude the same objects that individual permission checks
would deny. Keep the operation name, context scope, and returned queryset model
aligned.

### Checking permissions in backend code

Use `CoreHandler().check_permission(actor, operation_name, context=..., workspace=...)`.
It returns `True` or raises `PermissionException`.

Use `CoreHandler().filter_queryset(actor, operation_name, queryset, workspace=...)`
when returning a list of objects whose visibility depends on permissions.

Pass `workspace` explicitly for workspace-scoped operations. Only omit it for
core operations that genuinely do not belong to a workspace.

## Frontend Workflow

Frontend permission decisions are based on permission objects returned by backend
permission managers at login or workspace load time. Add a frontend permission
manager when UI code needs to evaluate the same rule locally.

1. Add or update a class extending `PermissionManagerType`.
2. Make `static getType()` return the same string as the backend manager `type`.
3. Implement `hasPermission(permissions, operation, context, workspaceId)`.
4. Return `true` to allow, `false` to deny, and `null`/`undefined` to pass through,
   matching the existing frontend convention in nearby managers.
5. Register it in the module `plugin.js` with
   `app.$registry.register('permissionManager', new MyPermissionManagerType(context))`.
6. Update `$hasPermission(operation, context, workspaceId)` call sites only when
   the UI actually needs to hide, disable, or branch on the new behavior.

Keep the backend `get_permissions_object` data sufficient for the frontend
decision. Do not make the frontend manager fetch extra permission data.

## Testing

For backend changes, prefer focused pytest tests near the manager or feature:

- Core manager behavior: `backend/tests/baserow/core/**`
- Premium manager behavior: `premium/backend/tests/baserow_premium_tests/**`
- Enterprise manager behavior: `enterprise/backend/tests/baserow_enterprise_tests/**`

Use `@override_settings(PERMISSION_MANAGERS=[...])` when the tested decision
depends on manager order or enablement. Use the registry fixtures from
`backend/src/baserow/test_utils/pytest_conftest.py` when tests need temporary
operation or permission manager registrations.

For frontend changes, use the frontend unit test skill and inspect existing tests
around registry setup, permission manager classes, or UI components calling
`$hasPermission`.

Validation commands:

- Backend: `just b test path/to/test_file.py`
- Frontend core: `just f yarn test:core path/to/test_file`
- Frontend enterprise: `just f yarn test:enterprise path/to/test_file`

## Guardrails

- Do not rely only on frontend permission checks for enforcement; backend checks
  are authoritative.
- Do not add a frontend permission manager with a different type string from its
  backend manager.
- Do not place a specific manager after `basic` if it needs to override the broad
  basic decision.
- Do not omit `filter_queryset` when list visibility differs by object.
- Do not add per-object database queries inside `check_multiple_permissions`.
- Do not rename operation or manager type strings casually; other code and saved
  data may depend on them.
- Do not duplicate the full permission guide here; read
  `docs/technical/permissions-guide.md` for deeper conceptual background.
