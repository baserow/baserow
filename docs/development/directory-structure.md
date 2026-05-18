# Directory structure

Everything ships from a single repository. This makes it easier to set up a demo or
development environment and to land cross-cutting changes in one pull request.

## Top-level layout

| Folder | What lives here |
|---|---|
| `backend` | Python/Django backend for core + contrib. |
| `web-frontend` | Nuxt/Vue frontend for core + contrib. |
| `premium` | Plugin containing premium-licensed features (backend + web-frontend). |
| `enterprise` | Plugin containing enterprise-licensed features (backend + web-frontend). |
| `integrations` | External integrations (currently Zapier; automation integrations will land here). |
| `e2e-tests` | Playwright end-to-end tests. The only place where we use TypeScript today. |
| `deploy` | One sub-folder per deployment target (all-in-one image, Heroku, Cloudron, …). |
| `docs` | Developer, installation, operations, and technical documentation. The MkDocs navigation lives in `mkdocs.yml`. |
| `changelog` | Source for the changelog generator used when opening a pull request. |
| `config` | Per-IDE starter configurations. |
| `formula` | Formula language grammar/parser source. |
| `embeddings` | Embeddings/AI server source. |
| `tests` | Repository-wide test helpers. |

Top-level files include the editor config, CI config, the root `justfile`,
`docker-compose.*.yml` files, `CHANGELOG.md`, `README.md`, and `LICENSE`.

## core and contrib

Inside `backend/src/baserow/` (and analogously in `web-frontend/modules/`) the code
is split into two layers:

- **core** — the framework: users, workspaces, applications, undo/redo,
  notifications, trash, search, permissions, jobs, telemetry, and every base
  class/registry that other code extends.
- **contrib** — concrete Baserow application types built on top of core. Today
  contrib contains `database`, `builder`, `automation`, `dashboard`, and
  `integrations`. The Automation Builder application will also live here.

Import rule: **contrib can import from core, core must never import from contrib.**
Core code should know nothing about specific application types. The same rule
applies between core/contrib and `premium`/`enterprise`: the plugins import from
core and contrib, never the other way around.

Note that Baserow application types are not Django apps. A single Django app can
host multiple Baserow application types, and one Baserow application type may span
multiple Django apps.

## api vs business logic

Inside both core and contrib we separate the HTTP-facing layer from the business
logic:

- `api/` — DRF urls, views, serializers and exception mappings.
- everything else — handlers, services, actions, registries, models.

The api layer can (and should) import from the business logic. The business logic
must not import from the api layer. The reason is straightforward: handlers must be
callable from the shell, management commands, Celery tasks and tests without going
through HTTP.

For the layered shape of a typical request, see
[Architectural patterns](../patterns/architecture.md).

## backend

In the backend directory you will find some files that are related only to the backend.
This whole directory is also added to the backend container.

* `pyproject.toml`: Python project configuration including dependencies managed by uv;
  also holds the Ruff lint/format configuration (`[tool.ruff]`).
* `uv.lock`: lockfile for reproducible dependency installation.
* `baserow`: is actually a python file, that just calls the management.py file in the
  source directory. This file is registered as a command via the `pyproject.toml`. When
  someone adds Baserow as a dependency they can use the command `baserow migrate` which
  is the same as `python src/baserow/manage.py migrate`.
* `Dockerfile`: Builds an image containing just the backend service, build with
   `--target dev` to instead get a dev ready image.
* `justfile`: contains commands to install dependencies, run the linter, run tests,
  and start development servers.
* `pytest.ini`: pytest configuration when running the tests.

### src

The src directory contains the full source code of the Baserow backend module.

* `api`: is a Django app that exposes Baserow via a REST API. Even though it is an
  optional app it is installed by default. It's highly recommended to use this package.
  It contains several directories each with their urls, views, serializers, and errors
  related to a specific part. For example, the workspaces and application both have their
  own directory. There are also several modules that contain some generic classes,
  functions, and decorators that are reused throughout the code. The `urls.py` module
  is included by the root url config under the namespace `api`.
* `config`: is a module that contains base settings and some settings that are for
   specific environments. It also contains the root url config that includes the api
   under the namespace `api`. There is
   also a wsgi.py file which can be used to expose the applications.
* `contrib`: contains the Baserow application types built on top of `core`. Today
  it holds `database`, `builder`, `automation`, `dashboard` and `integrations`.
  Each application type has its own handlers, registries, models, api and
  migrations.
* `core`: the framework. Contains users, workspaces, applications, undo/redo,
  notifications, trash, search, permissions, jobs, telemetry and every base class
  and registry that contrib code extends. `core` must not import from `contrib`.
* `manage.py`: the Django manage.py file to execute management commands.

### tests

The tests folder contains a baserow folder which matches the directory structure of
the `src/baserow` folder. Instead of it containing the source files it contains
the tests. The files always start with `test_` to ensure they are picked up by
pytest. They always end with the name of the related file in the source directory.

There is also a fixtures directory which contains modules with classes that have small
helpers to create data. For example if you quickly want to write a test related to a
database table text field you can quickly create one by doing something like in your
test.

```python
def test_something_important(data_fixture):
    # A table, database and workspace have also been created because the text field depends
    # on them.
    field = data_fixture.create_text_field()
```

## web-frontend

In the web-frontend directory you will find files related only to the Nuxt/Vue
frontend. This whole directory is also added to the web-frontend container.

* `Dockerfile`: builds an image containing just the web-frontend service; use
  `--target dev` for the development image.
* `eslint.config.mjs` (repo root): ESLint flat config for JavaScript and Vue files.
* `web-frontend/stylelint.config.mjs`: Stylelint configuration for SCSS.
* Prettier runs through the frontend `just` recipes and package scripts.
* `nuxt.config.ts`: Nuxt entry point.
* `config/`: environment-specific Nuxt config files.
* `vitest.config.ts` and `vitest.config.base.ts`: Vitest test configuration.
* `package.json`: package config and frontend dependencies.
* `yarn.lock`: lockfile for dependencies installed via yarn.
* `justfile`: commands to install dependencies, run linting, and run tests.

### config

The config directory contains base Nuxt settings plus environment-specific
overrides for development, production and tests.

### modules

All modules follow Nuxt's module-oriented structure: `module.js`, `plugin.js`,
components, pages, services, store modules, realtime handlers, assets and
locales.

### tests

Frontend unit tests live under `web-frontend/test/` and run with Vitest. Tests
mirror the source area where possible and use the shared `TestApp` fixture.

## docs

The docs folder contains Markdown files for developer, installation,
operations and technical documentation. The sidebar order is controlled by
`mkdocs.yml`.

