---
name: add-config-env-var
description: Add a Baserow configuration environment variable for the backend, frontend, or both, and propagate it through settings, Nuxt runtime config, Docker Compose, documentation, consumers, and tests as applicable. Use when adding or reviewing any env-backed configuration value, including requests that reference `INTEGRATION_LOCAL_BASEROW_PAGE_SIZE_LIMIT` as a pattern.
---

# Add Config Env Var

Copy the closest existing variable used by the same application layer. Public
Baserow-specific env names should normally use the `BASEROW_` prefix; internal
Django setting names and Nuxt runtime-config keys do not.

Keep the change simple and explicit. Do not add abstractions for this.

## Files To Check

Check the files relevant to the variable's consumers:

- Backend: `backend/src/baserow/config/settings/base.py`
- Frontend defaults: usually `web-frontend/modules/core/module.js`
- Frontend env mapping: `web-frontend/env-remap.mjs`
- Deployment: `docker-compose.yml` and `docker-compose.no-caddy.yml`
- `docs/installation/configuration.md` — the canonical env-var reference table; add a row in the right section
- Backend or frontend code that uses the setting
- A focused test if behavior changes

## Workflow

1. Identify whether the value is consumed by the backend, frontend, or both.
   Define one clear default and keep defaults consistent across layers.

2. If the backend needs it, add the Django setting in
   `backend/src/baserow/config/settings/base.py` near the closest related
   setting.

Example:

```python
MY_SETTING = int(os.getenv("BASEROW_MY_SETTING", 123))
```

3. If the frontend needs it, declare the Nuxt runtime-config default near the
   closest related key and add the public env mapping to
   `web-frontend/env-remap.mjs`.

   Before doing so, classify every frontend consumer:

   - Runtime consumers can read `useRuntimeConfig()` or `nuxtApp.$config` after
     `env-remap.mjs` runs when the container starts.
   - Build-time consumers, including `modules/*/routes.js`, Nuxt module setup,
     and direct `process.env.NUXT_*` reads, are compiled before self-hosters
     provide container environment variables. `env-remap.mjs` cannot make those
     consumers runtime-configurable.

   Do not derive a compiled route or other build artifact from a runtime env var.
   Compile a stable structure and apply the setting at runtime instead, for
   example by filtering a catch-all route and transforming its path using runtime
   config.

4. If the variable should be configurable in Docker, add it to every service
   that consumes it and everywhere the closest example appears in:

- `docker-compose.yml`
- `docker-compose.no-caddy.yml`

5. Update consumers to use the configured value:

- Backend: `settings.MY_SETTING`
- Frontend: `useRuntimeConfig()` or `nuxtApp.$config`
- Backend tests: `override_settings(MY_SETTING=...)`

6. Add or update a targeted test if the setting changes behavior.

7. Add the related documentation in `docs/installation/configuration.md` — find the right section and add a table row matching the nearest existing entry.

8. When frontend routing, module registration, or another build artifact is
   involved, run a production `yarn build` without the deployment env var and
   inspect the generated behavior. Confirm that setting the variable only when
   the built server starts still works.

## Quick Checklist

1. Identify backend and frontend consumers
2. Add the backend setting when needed
3. Add the Nuxt default and env remap when needed
4. Check whether frontend consumers run at build time or runtime
5. Keep compiled routes and artifacts independent of runtime-only values
6. Mirror every required Docker service and Compose file
7. Update consumers and add focused tests
8. Document the public env variable

## Guardrails

- Do not add a raw `os.getenv(...)` in application code when the value belongs in Django settings.
- Do not update only one Docker location if the example appears in several places.
- Do not add a Django setting for a frontend-only value.
- Do not expose a backend-only setting to Nuxt unless the frontend actually needs it.
- Do not assume that adding a variable to `env-remap.mjs` makes build-time Nuxt
  code configurable in an official image. The remap runs when the built server
  starts, after its route table and bundles already exist.
- Prefer copying the closest existing setting instead of inventing a new pattern.
