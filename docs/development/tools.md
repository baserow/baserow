# Development tools

The toolchain Baserow actually uses today. If you're seeing a tool here for
the first time, this is the entry that explains *what* and *why*. The
config and conventions for each live in their own places (see links).

## Backend

### Python 3.14

Baserow's backend targets Python **3.14** (pinned in
`backend/pyproject.toml` as `requires-python = "==3.14.*"`). Don't try to
install the project under an older interpreter — runtime errors are subtle
and not always immediate.

### uv

Backend dependencies are managed with [**uv**](https://docs.astral.sh/uv/),
not pip / pipenv / poetry. The lockfile is `backend/uv.lock`. All `just`
recipes call through `uv run` so you generally don't run `uv` directly.

### Django

The backend is a [Django](https://www.djangoproject.com/) application,
currently on 5.2.x. Django gives us the ORM, the admin, the migrations
framework, and authentication primitives. The `core` package is laid out
around Django apps; user-facing application types (database, builder,
automation, dashboard, integrations) live under `contrib/`.

### Django REST Framework

[DRF](https://www.django-rest-framework.org/) is at the base of every REST
endpoint: serializers, viewsets, authentication, throttling. Most views
are `APIView` or `GenericAPIView` subclasses with `map_exceptions` wired
in for the domain-exception → HTTP-status mapping.

### Django Channels

[Channels](https://channels.readthedocs.io/) powers the WebSocket layer.
We use `channels[daphne]` for the ASGI server and `channels-redis` as the
channel layer. See [WebSockets](../technical/websockets.md) for the
realtime architecture.

### Celery + Redbeat

Long-running and periodic backend work runs on
[Celery](https://docs.celeryq.dev/). Broker: Redis. Periodic tasks use
`celery-redbeat` (Redis-backed schedule store, survives restarts).
`celery-singleton` provides single-flight task locks for jobs that must
not run concurrently. See [Celery](../technical/celery.md) and
[Jobs](../technical/jobs.md).

### Redis

Multipurpose: Celery broker, Channels layer, Django cache backend,
and session store. Single Redis instance with separate logical databases
— see [Caching](../technical/caching.md).

### PostgreSQL

The persistent store. Baserow uses Postgres features heavily: dynamic
tables for user data, `tsvector` for search, `GIN` indexes, advisory
locks for migrations, `jsonb` for formula-result snapshots. See
[Dynamic models](../technical/dynamic-models.md),
[Table rows search](../technical/table-rows-search.md), and
[PostgreSQL locks](../technical/postgresql-locks.md).

### loguru

[loguru](https://loguru.readthedocs.io/) is the logging library. **Always
use `from loguru import logger`** — never the stdlib `logging` module. See
[Project conventions](conventions.md#logging-always-loguru).

### Ruff

[Ruff](https://docs.astral.sh/ruff/) replaces black, flake8, isort, and
bandit in a single fast tool. It's our formatter, linter, import sorter,
and security scanner. Configured in `backend/pyproject.toml` under
`[tool.ruff]`. 88-character line length.

From `backend/`:

```bash
just fix       # auto-format + auto-fix lint issues
just lint      # check only
```

### pytest

[pytest](https://docs.pytest.org/) with `pytest-django` is the backend
test runner. Common plugins in use: `pytest-xdist` (parallel), `pytest-cov`
(coverage), `pytest-mock`, `pytest-asyncio`, `pytest-retry`,
`pytest-testmon`. Always run through `just`. From `backend/`:

```bash
just test                              # everything
just test -n=auto                      # parallel
just test tests/path/                  # specific path
just test-coverage                     # with coverage
```

Never invoke `pytest` directly — the recipe sets `PYTHONPATH` and env vars
that the bare binary won't. See
[Project conventions: tests](conventions.md#tests-always-via-just).

Skill: [`write-backend-unit-test`](https://github.com/baserow/baserow/blob/develop/.agents/skills/write-backend-unit-test/SKILL.md).

### drf-spectacular

OpenAPI schema generation from DRF code. The schema feeds the redoc page
served at `/api/redoc/` and the user-facing API docs. Configured in
`backend/src/baserow/config/settings/base.py`.

### ItsDangerous

Token signing for things like password reset links and form-submission
tokens. Third-party library; nothing Baserow-specific.

### django-storages

Pluggable file storage for user-uploaded files (file fields, exports,
imports). Supports local disk, S3, Azure Blob, and Google Cloud Storage.
See `installation/secure-file-serve.md` for the production setup.

### Backend internationalisation

Backend strings use Django's `gettext` / `gettext_lazy`. To update message
files for English, from `backend/`:

```bash
just make-translations
```

Translations for non-English locales are filled in by **Weblate** before
each release. Do not manually edit non-English `.po` files.

## Frontend

### Vue 3

[Vue 3](https://vuejs.org/) is the UI framework. Note the version —
render functions must use Vue 3 semantics (`import { h } from 'vue'`).
See [Project conventions: Vue](conventions.md#vue-3-render-functions).

### Nuxt 3

[Nuxt 3](https://nuxt.com/) is the meta-framework: routing, SSR, modules,
build pipeline. We organise the frontend as Nuxt modules under
`web-frontend/modules/`, mirroring the backend `contrib/` packages.

### Vite

Nuxt 3 uses [Vite](https://vitejs.dev/) as the build tool (replacing
webpack used by Nuxt 2). JSX-bearing files must use `.jsx` or `.tsx`
extensions so Vite can parse them. See
[Project conventions: JSX](conventions.md#jsx-file-extensions).

### yarn

Frontend dependencies are managed with [yarn](https://yarnpkg.com/). The
lockfile is `web-frontend/yarn.lock`. As with `uv`, the `just` recipes
wrap yarn; you rarely call it directly.

### ESLint

[ESLint 9](https://eslint.org/) for JavaScript / Vue files. Configured in
`eslint.config.mjs` at the repo root (flat config). From `web-frontend/`:

```bash
just lint    # check
just fix     # auto-fix
```

### Stylelint

[Stylelint](https://stylelint.io/) for SCSS. BEM-style naming is the
convention — see [Project conventions: SCSS](conventions.md#scss-bem-naming).

### Prettier

[Prettier](https://prettier.io/) for code formatting (run as part of
`just lint` / `just fix` in `web-frontend/`).

### Vitest

[Vitest](https://vitest.dev/) is the frontend test runner, paired with
[Vue Test Utils](https://test-utils.vuejs.org/) and our `TestApp`
fixtures. Replaces Jest (which Baserow used before the Nuxt-3 / Vite
migration). From `web-frontend/`:

```bash
just test                  # all frontend tests
just yarn test:core path/  # specific test
just yarn test:premium     # premium suite
```

Snapshot tests are supported; we use them for stable component output.

Skill: [`write-frontend-unit-test`](https://github.com/baserow/baserow/blob/develop/.agents/skills/write-frontend-unit-test/SKILL.md).

### Storybook

[Storybook 9](https://storybook.js.org/) hosts the component library.
Stories live in `web-frontend/stories/`. Run it locally with
`yarn storybook` (port 6006) or visit the deployed version at
[baserow.io/style-guide](https://baserow.io/style-guide).

### axios

HTTP client for browser → backend calls. The frontend "service" layer is a
typed wrapper around axios — see
[Architectural patterns](../patterns/architecture.md#service). Tests use
`axios-mock-adapter` to stub responses.

### Frontend internationalisation

[`@nuxtjs/i18n`](https://i18n.nuxtjs.org/) handles runtime locale
switching. Source strings live in `en.json`; **only edit `en.json`** —
Weblate manages every other locale. See
[Project conventions: locales](conventions.md#locales-only-edit-enjson).

### SCSS / Sass

[SCSS](https://sass-lang.com/) for styles. BEM naming. Tokens are
centralised; use them rather than hard-coded values.

### Iconoir

[Iconoir](https://iconoir.com/) is the icon set used throughout the UI.

### Sentry

Frontend error reporting via [`@sentry/nuxt`](https://docs.sentry.io/).
Backend uses `sentry-sdk[django]`. The default Sentry organisation is
`baserow-eu` (region `https://de.sentry.io`).

## End-to-end

### Playwright

[Playwright](https://playwright.dev/) drives browser-level tests in
`e2e-tests/`. TypeScript-only directory in the repo.

```bash
just e2e test
```

See [E2E testing](e2e-testing.md). Never invoke `playwright` directly.

## Cross-cutting

### just

[just](https://github.com/casey/just) is the command runner that wraps
every workflow (lint, test, dev server, migrations, docs, e2e, …). All
recipes are in `justfile` files at the repo root and inside each major
component. See [justfile reference](justfile.md) for the full list.

**Run tests, linters, and builds through `just`, not the underlying
tools** — the recipes set the environment variables and paths the tools
expect. See [Project conventions: tests](conventions.md#tests-always-via-just).

### Docker

[Docker](https://docker.com/) backs the optional containerised dev
environment and every deployment recipe. The `docker-compose.*.yml` files
in the repo root cover dev, build, and the all-in-one image. See
[Running with Docker](running-the-dev-env-with-docker.md).

### Changelog generator

Each PR that adds a user-visible change needs a changelog entry. Don't
write the YAML by hand — the generator handles classification and
formatting:

```bash
just changelog add
```

Skill: [`create-changelog`](https://github.com/baserow/baserow/blob/develop/.agents/skills/create-changelog/SKILL.md). See also
`changelog/README.md` in the repo root.

### Django Silk (dev only)

[Silk](https://github.com/jazzband/django-silk) is a request/SQL profiler
enabled in development via `BASEROW_ENABLE_SILK`. It records every
request, its SQL queries, and Python stack traces into Postgres. Use
when chasing slow endpoints or N+1 queries.

Skill: [`silk-profiler`](https://github.com/baserow/baserow/blob/develop/.agents/skills/silk-profiler/SKILL.md).

## Related

- [Project conventions](conventions.md) — the rules for using these tools.
- [Code quality](code-quality.md) — what CI runs.
- [Skills index](skills-index.md) — reusable workflow recipes.
- [justfile reference](justfile.md) — every `just` command.
