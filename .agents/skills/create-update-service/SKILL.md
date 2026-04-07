---
name: Integrations and Services
description: Create or update Baserow integration types and service types in `contrib/integrations`. Use when adding a new ServiceType/IntegrationType subclass, registering one in `apps.py` or `plugin.js`, or updating an existing dispatch/auth flow.
version: 1.0.0
---

# Create Or Update Baserow Services And Integrations

Use this skill when a task involves creating or updating a Baserow integration type or service type in the `contrib/integrations` stack.

This repo already has the core patterns. Prefer copying an existing implementation close to the target behavior instead of inventing a new structure.

Integrations and services are shared by the Application builder and the Automation tool. Each of them should be compatible with both tools.

## First Step

Before editing, identify which of these applies:

1. New integration type only
2. New service type attached to an existing integration
3. Update to an existing integration or service
4. Full feature spanning backend, frontend, translations, and tests

Then inspect the closest existing example with `rg` before changing files.

Useful starting points:

- Backend registrations: `backend/src/baserow/contrib/integrations/apps.py`
- Frontend registrations: `web-frontend/modules/integrations/plugin.js`
- Core backend service examples: `backend/src/baserow/contrib/integrations/core/service_types.py`
- Core frontend service examples: `web-frontend/modules/integrations/core/serviceTypes.js`
- Backend integration example: `backend/src/baserow/contrib/integrations/core/integration_types.py`
- Frontend integration example: `web-frontend/modules/integrations/core/integrationTypes.js`

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

## Frontend Checklist

If the feature is user-configurable, update the frontend in parallel with the backend:

1. Add or update the service or integration type class.
2. Register it in `web-frontend/modules/integrations/plugin.js`.
3. Add or update the form component used to configure it.
4. Add translations in `web-frontend/modules/integrations/locales/en.json`.
5. Add any supporting mixins, helpers, or assets only if the existing pattern requires them.

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
7. Add translations and tests.

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

Frontend examples:

- Unit tests near `web-frontend/test/unit/integrations/**`

Minimum validation before finishing:

1. The type is registered on both backend and frontend when applicable.
2. The create and update flows serialize the intended fields.
3. Required translations exist.
4. Migrations are present for model changes.
5. The most relevant targeted tests pass, or the failure is reported explicitly.

## Search Patterns

Use these searches to move quickly:

- `rg -n "class .*ServiceType" backend/src/baserow/contrib/integrations`
- `rg -n "class .*IntegrationType" backend/src/baserow/contrib/integrations`
- `rg -n "register\\(" backend/src/baserow/contrib/integrations/apps.py web-frontend/modules/integrations/plugin.js`
- `rg -n "getType\\(\\)" web-frontend/modules/integrations`
- `rg -n "\"serviceType\\.|integrationType\\.\"" web-frontend/modules/integrations/locales/en.json`

## Guardrails

- Do not add a backend type without checking the matching frontend registration path.
- Do not rename a persisted `type` string casually.
- Do not forget migrations when model fields change.
- Do not add broad abstractions unless at least two existing implementations already need them.
- Prefer matching the nearest existing module layout over introducing a new folder structure.
