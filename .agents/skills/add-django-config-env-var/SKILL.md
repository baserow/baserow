---
name: add-django-config-env-var
description: Add a new environment variable for a Django setting in Baserow and propagate it to the few repo files that usually need it. Use this when a request says a config env var must be added in several places or references `INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT` as the pattern to follow.
---

# Add Django Config Env Var

Use `INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT` as the template. The env var name should be prefixed with `BASEROW_` but the internal var isn't.

Keep the change simple and explicit. Do not add abstractions for this.

## Files To Check

When adding a new setting, usually check these files:

- `backend/src/baserow/config/settings/base.py`
- `docker-compose.yml`
- `docker-compose.no-caddy.yml`
- `web-frontend/env-remap.mjs`
- Backend or frontend code that uses the setting
- A focused test if behavior changes

## Workflow

1. Add the Django setting in `backend/src/baserow/config/settings/base.py` near the closest related setting.

Example:

```python
MY_SETTING = int(os.getenv("BASEROW_MY_SETTING", 123))
```

2. If the variable should be configurable in Docker, add it everywhere the similar example appears in:

- `docker-compose.yml`
- `docker-compose.no-caddy.yml`

3. If the frontend needs it at runtime, add it to `web-frontend/env-remap.mjs`.

4. Update consumers to use the setting:

- Backend: `settings.MY_SETTING`
- Tests: `override_settings(MY_SETTING=...)`

5. Add or update a targeted test if the setting changes behavior.

6. Add the related documentation

## Quick Checklist

1. Add it in `base.py`
2. Mirror the matching Docker entries
3. Add the Nuxt remap if frontend code needs it
4. Use `settings.<NAME>` in code
5. Add a focused test if needed
6. Add the documentation

## Guardrails

- Do not add a raw `os.getenv(...)` in application code when the value belongs in Django settings.
- Do not update only one Docker location if the example appears in several places.
- Do not expose a backend-only setting to Nuxt unless the frontend actually needs it.
- Prefer copying the closest existing setting instead of inventing a new pattern.
