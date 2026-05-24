---
name: create-update-service
description: Create or update Baserow integration and service types, including services exposed as Application Builder data sources, Builder workflow actions, Automation node actions, Automation node triggers, or dashboard data sources. Use when adding a ServiceType/IntegrationType subclass, registering backend/frontend types, or wiring service wrappers in builder or automation.
---

# Create Or Update Baserow Services And Integrations

Use this skill when a task involves creating or updating a Baserow integration type or service type in the `contrib/integrations` stack, especially when that service must be usable as one or more of:

- Application Builder data source
- Application Builder workflow action
- Automation node action
- Automation node trigger
- Dashboard data source
- Plain integration-backed service

This repo already has the core patterns. Prefer copying an existing implementation close to the target behavior instead of inventing a new structure.

Integrations and services are shared by the Application Builder, Dashboard, and Automation tools. The reusable service lives in `contrib/integrations`; product-specific objects usually wrap that service.

## Service Usage Map

Decide the intended product surface before editing:

| Surface | Backend wrapper | Frontend wrapper | Required dispatch type |
|---|---|---|---|
| Builder data source | `DataSource.service` in `backend/src/baserow/contrib/builder/data_sources/**` | Service type registered in `web-frontend/modules/integrations/plugin.js` and used by builder data source UI | `DispatchTypes.DATA` |
| Dashboard data source | `DashboardDataSource.service` in `backend/src/baserow/contrib/dashboard/**` | Service type registered in integrations plugin and dashboard form/UI | `DispatchTypes.DATA` |
| Builder workflow action | `BuilderWorkflowServiceActionType` subclass in `backend/src/baserow/contrib/builder/workflow_actions/workflow_action_types.py` plus a workflow action model | `WorkflowActionType` subclass in `web-frontend/modules/builder/workflowActionTypes.js` | `DispatchTypes.ACTION` |
| Automation action node | `AutomationNodeActionNodeType` subclass in `backend/src/baserow/contrib/automation/nodes/node_types.py` plus an automation node model | `ActionNodeTypeMixin` node type in `web-frontend/modules/automation/nodeTypes.js` | `DispatchTypes.ACTION` |
| Automation trigger node | trigger node type in `backend/src/baserow/contrib/automation/nodes/node_types.py`, often using `TriggerServiceTypeMixin` | `TriggerNodeTypeMixin` node type in `web-frontend/modules/automation/nodeTypes.js` | trigger-capable service type |

For data sources, a service with `DispatchTypes.DATA` is normally enough because the product object points directly at the service. For workflow actions and automation nodes, also add wrapper types/models so the service appears in the action/node registries.

## First Step

Before editing, identify which of these applies:

1. New integration type only
2. New service type attached to an existing integration
3. Existing service exposed on a new surface, such as automation or builder
4. Update to an existing integration, service, or wrapper type
5. Full feature spanning backend, frontend, translations, and tests

Then inspect the closest existing example with `grep` before changing files. If
`rg` is available, it is a faster equivalent for the same patterns and target
paths.

Useful starting points:

- Backend registrations: `backend/src/baserow/contrib/integrations/apps.py`
- Frontend registrations: `web-frontend/modules/integrations/plugin.js`
- Core backend service examples: `backend/src/baserow/contrib/integrations/core/service_types.py`
- Core frontend service examples: `web-frontend/modules/integrations/core/serviceTypes.js`
- Backend integration example: `backend/src/baserow/contrib/integrations/core/integration_types.py`
- Frontend integration example: `web-frontend/modules/integrations/core/integrationTypes.js`
- Builder workflow action wrappers: `backend/src/baserow/contrib/builder/workflow_actions/workflow_action_types.py`
- Automation node wrappers: `backend/src/baserow/contrib/automation/nodes/node_types.py`
- Frontend builder workflow action wrappers: `web-frontend/modules/builder/workflowActionTypes.js`
- Frontend automation node wrappers: `web-frontend/modules/automation/nodeTypes.js`

## Backend Checklist

For a new or updated service type, check these areas:

1. Model fields exist and support the intended configuration.
2. The `ServiceType` subclass exposes the right `type`, `model_class`, `dispatch_types`, `allowed_fields`, and serializer configuration.
3. Related nested objects are handled in `after_create`, update helpers, or custom methods when needed.
4. Context/schema methods are implemented if the service emits data for downstream nodes.
5. The service is registered in `backend/src/baserow/contrib/integrations/apps.py`.
6. A migration is added if models changed.

For a new or updated integration type, check these areas:

1. The `IntegrationType` subclass defines `type`, `model_class`, serializer field names, allowed fields, and sensitive fields when relevant.
2. Any integration-specific context data or permissions behavior is preserved.
3. The integration is registered in `backend/src/baserow/contrib/integrations/apps.py`.
4. A migration is added if models changed.

Common backend files to inspect:

- `backend/src/baserow/contrib/integrations/*/models.py`
- `backend/src/baserow/contrib/integrations/*/service_types.py`
- `backend/src/baserow/contrib/integrations/*/integration_types.py`
- `backend/src/baserow/contrib/integrations/api/**`
- `backend/src/baserow/contrib/integrations/migrations/**`
- `backend/src/baserow/core/services/registries.py`
- `backend/src/baserow/contrib/builder/data_sources/**`
- `backend/src/baserow/contrib/builder/workflow_actions/**`
- `backend/src/baserow/contrib/automation/nodes/**`
- `backend/src/baserow/contrib/dashboard/**`

## Product Surface Checklist

### Builder or Dashboard data source

1. Ensure the backend service type has `DispatchTypes.DATA`.
2. Confirm `dispatch()` returns the shape expected by `get_schema()`, `get_data_schema()`, `get_result()`, or existing frontend consumers.
3. Add frontend service type behavior for data-source UX, including form component, validation, schema helpers, result helpers, and error messages.
4. Register the service in backend and frontend integration registries.
5. Check data-source create/update/dispatch serializers and tests if new fields or output shape are introduced.

### Builder workflow action

1. Ensure the backend service type has `DispatchTypes.ACTION`.
2. Add or reuse a workflow action model in `backend/src/baserow/contrib/builder/workflow_actions/models.py`.
3. Add a `BuilderWorkflowServiceActionType` subclass with `type`, `model_class`, `service_type`, and `get_pytest_params`.
4. Register it in `backend/src/baserow/contrib/builder/apps.py`.
5. Add a frontend workflow action type in `web-frontend/modules/builder/workflowActionTypes.js` that points to the service type.
6. Register it in `web-frontend/modules/builder/plugin.js`.
7. Add translations for the action label, description, validation, and form copy.

### Automation action node

1. Ensure the backend service type has `DispatchTypes.ACTION`.
2. Add or reuse an automation node model in `backend/src/baserow/contrib/automation/nodes/models.py`.
3. Add an `AutomationNodeActionNodeType` subclass with `type`, `model_class`, `service_type`, and `get_pytest_params`.
4. Register it in `backend/src/baserow/contrib/automation/apps.py`.
5. Add a frontend node type using `ActionNodeTypeMixin` in `web-frontend/modules/automation/nodeTypes.js`.
6. Register it in `web-frontend/modules/automation/plugin.js`.
7. Add translations for the node label, default label template, description, validation, and form copy.

### Automation trigger node

1. Use or implement a trigger-capable service type, usually with `TriggerServiceTypeMixin`.
2. Add or reuse an automation trigger node model and backend node type with `is_workflow_trigger` behavior via the existing trigger mixins/patterns.
3. Register the backend node type in `backend/src/baserow/contrib/automation/apps.py`.
4. Add a frontend node type using `TriggerNodeTypeMixin`.
5. Register it in `web-frontend/modules/automation/plugin.js`.
6. Confirm sample data, output schema, edge behavior, and workflow simulation behavior match existing trigger patterns.

## Frontend Checklist

If the feature is user-configurable, update the frontend in parallel with the backend:

1. Add or update the service or integration type class.
2. Register it in `web-frontend/modules/integrations/plugin.js`.
3. Add or update the form component used to configure it.
4. Add translations in `web-frontend/modules/integrations/locales/en.json`.
5. Add any supporting mixins, helpers, or assets only if the existing pattern requires them.
6. If exposed as a builder workflow action or automation node, add and register the frontend wrapper type in the relevant builder or automation module.

Common frontend files to inspect:

- `web-frontend/modules/integrations/*/serviceTypes.js`
- `web-frontend/modules/integrations/*/integrationTypes.js`
- `web-frontend/modules/integrations/*/components/services/**`
- `web-frontend/modules/integrations/*/components/integrations/**`
- `web-frontend/modules/integrations/locales/en.json`

## How To Implement

### Creating a new service type

1. Start from the closest existing service type with similar dispatch behavior:
   `ACTION`, `DATA`, or trigger behavior.
2. Add or update the backend model if the service needs persisted fields.
3. Implement or extend the backend `ServiceType` subclass.
4. Register the service in `backend/src/baserow/contrib/integrations/apps.py`.
5. Implement the frontend service type class and form component.
6. Register the service in `web-frontend/modules/integrations/plugin.js`.
7. Add product-specific wrappers only for the surfaces requested.
8. Add translations and tests.

### Exposing an existing service on another surface

1. Check the service has the required dispatch capability for the target surface.
2. Add only the missing wrapper type/model/registration for that surface.
3. Reuse the existing service form and schema helpers unless the target surface genuinely needs different UX.
4. Keep service `type` identifiers stable and choose wrapper `type` identifiers consistent with nearby examples.
5. Add targeted tests for the wrapper create/update/dispatch path.

### Creating a new integration type

1. Start from the closest existing integration type with similar auth or configuration needs.
2. Add or update the backend model if required.
3. Implement or extend the backend `IntegrationType` subclass.
4. Register the integration in `backend/src/baserow/contrib/integrations/apps.py`.
5. Implement the frontend integration type class and form component.
6. Register the integration in `web-frontend/modules/integrations/plugin.js`.
7. Add translations and tests.

### Updating an existing type

1. Find all backend and frontend registrations for the type string.
2. Check whether API serializers, nested relations, or schema generation need updates.
3. Keep existing `type` identifiers stable unless the user explicitly wants a breaking change.
4. Check whether old records need a migration or a data backfill.
5. Update tests for both create and update flows when behavior changes.

## Testing Expectations

Run the narrowest relevant tests first or create one if none exists.

Backend examples:

- Integration and Service tests in `backend/tests/baserow/api/integrations/**`
- Builder data source tests in `backend/tests/baserow/contrib/builder/data_sources/**` and API data-source tests nearby.
- Builder workflow action tests in `backend/tests/baserow/contrib/builder/workflow_actions/**` and API workflow-action tests nearby.
- Automation node tests in `backend/tests/baserow/contrib/automation/nodes/**` and API node tests nearby.
- Dashboard data-source tests in `backend/tests/baserow/contrib/dashboard/**` when the service is exposed there.

Frontend examples:

- Unit tests near `web-frontend/test/unit/integrations/**`
- Builder workflow action and data source tests near `web-frontend/test/unit/builder/**`
- Automation node tests near `web-frontend/test/unit/automation/**`

Minimum validation before finishing:

1. The type is registered on both backend and frontend when applicable.
2. The create and update flows serialize the intended fields.
3. The target product surface can create, update, serialize, import/export, and dispatch the service or wrapper.
4. Output schema/sample data is available when downstream formula/data-provider features depend on it.
5. Required translations exist.
6. Migrations are present for model changes.
7. The most relevant targeted tests pass, or the failure is reported explicitly.

## Search Patterns

Use these searches to move quickly:

Use `rg -n "<pattern>" <paths>` as a faster equivalent when `rg` is available.

- `grep -RInE "class .*ServiceType" backend/src/baserow/contrib/integrations`
- `grep -RInE "class .*IntegrationType" backend/src/baserow/contrib/integrations`
- `grep -RInE "DispatchTypes\\.(ACTION|DATA)" backend/src/baserow/contrib/integrations`
- `grep -RInE "TriggerServiceTypeMixin|ListServiceTypeMixin" backend/src/baserow/contrib/integrations`
- `grep -RInE "register\\(" backend/src/baserow/contrib/integrations/apps.py web-frontend/modules/integrations/plugin.js`
- `grep -RInE "BuilderWorkflowServiceActionType|builder_workflow_action_type_registry" backend/src/baserow/contrib/builder`
- `grep -RInE "AutomationNodeActionNodeType|TriggerNodeType|automation_node_type_registry" backend/src/baserow/contrib/automation`
- `grep -RInE "WorkflowActionType|register\\('workflowAction'" web-frontend/modules/builder`
- `grep -RInE "ActionNodeTypeMixin|TriggerNodeTypeMixin|register\\('node'" web-frontend/modules/automation`
- `grep -RInE "getType\\(\\)" web-frontend/modules/integrations`
- `grep -RInE "\"serviceType\\.|integrationType\\.\"" web-frontend/modules/integrations/locales/en.json`

## Guardrails

- Do not add a backend type without checking the matching frontend registration path.
- Do not rename a persisted `type` string casually.
- Do not forget migrations when model fields change.
- Do not expose a service as a data source unless it can be dispatched as `DispatchTypes.DATA`.
- Do not expose a service as a workflow action or action node unless it can be dispatched as `DispatchTypes.ACTION`.
- Do not add automation or builder wrappers when a plain data source service registration is sufficient.
- Do not add broad abstractions unless at least two existing implementations already need them.
- Prefer matching the nearest existing module layout over introducing a new folder structure.
