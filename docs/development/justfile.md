# Justfile reference

Baserow uses [just](https://github.com/casey/just) as the canonical
command runner. Every workflow — install, run, test, lint, format,
build, migrate, deploy — has a `just` recipe. **Run things through
`just`, not the underlying tool**; the recipes set the environment
variables, paths, and Python/Node versions the underlying tools
expect.

There are three justfiles:

| File | Purpose |
|---|---|
| `/justfile` | Root. Orchestration (`init`, `dev up`, `dc-dev`, `test`, `lint`, …) and the cross-component delegators. |
| `/backend/justfile` | Backend (Python / Django / `uv`). |
| `/web-frontend/justfile` | Frontend (Node / Nuxt / `yarn`). |

## How to invoke — the three styles

This is the convention used across the docs. **Pick one; stay
consistent within a workflow.**

### 1. From a component directory — bare command

The terse form. `cd` into the right folder once and just run the
recipe name:

```bash
cd backend
just test        # → backend tests
just lint        # → backend lint
just fix         # → backend format + auto-fix

cd ../web-frontend
just test        # → frontend tests
just lint        # → frontend lint
```

This is what most code editors / IDE tasks call. Use it during
focused work in one component.

### 2. From the repo root — `b` and `f` prefix

The root justfile re-exports the backend recipes under `b` and the
frontend ones under `f`. So from the project root:

```bash
just b test      # backend tests
just b lint      # backend lint
just f test      # frontend tests
just f fix       # frontend auto-fix
just b migrate   # backend manage.py migrate
```

Useful when you're jumping between components or running ad-hoc from
a fresh shell.

### 3. From the repo root — no prefix, fans out to both

For recipes that exist with the same name in both justfiles (`lint`,
`fix`, `test`), the root recipe of the same name runs both:

```bash
just lint        # backend lint + frontend lint
just fix         # backend fix + frontend fix
just test        # backend tests + frontend tests
```

Use this before pushing — runs the same checks CI does, in one shot.

### Which to use in the docs

When a doc shows a command, the convention is:

- Mention which directory you should be in: *"from `backend/`"* or
  *"from `web-frontend/`"*.
- Use the bare form (style 1): `just test`, `just lint`, `just fix`.
- For repo-root commands that fan out (style 3) or use the `b`/`f`
  prefix (style 2), just show the command — the prefix or its
  absence is self-describing.

## Discovering commands

```bash
just --list             # from the current directory, list its recipes
just b --list           # backend recipes (from root)
just f --list           # frontend recipes (from root)
just help               # root quick-start
```

Every recipe has a one-line description. `just --list` is the
authoritative inventory — this page is a tour, not the full list.

## Installation

```bash
# macOS
brew install just uv

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Essential commands

### First-time setup

```bash
just init          # install backend + frontend deps, create .env.local
```

### Run the dev stack

```bash
# Local (Postgres + Redis in Docker; backend, celery, frontend native)
just dev up
just dev up -d     # detached
just dev stop
just dev logs
just dev ps

# Everything in Docker
just dc-dev up -d
just dcd logs -f                  # dcd is an alias for dc-dev
just dcd exec backend bash
just dcd down
just dcd ps
```

### Backend (from `backend/`, or with `b` from root)

```bash
just test              # all tests
just lint              # check
just fix               # format + auto-fix
just shell             # Django shell
just migrate           # run migrations
just manage <cmd>      # any manage.py command
```

### Frontend (from `web-frontend/`, or with `f` from root)

```bash
just test              # all tests (Vitest)
just lint              # ESLint + Stylelint + Prettier check
just fix               # auto-fix
just storybook         # run Storybook on :6006
```

### Tests with a ramdisk DB

For faster backend tests, use an in-memory Postgres:

```bash
just test-db up                                                           # from repo root
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just test  # from backend/
just test-db down
just test-db ps
```

### Code quality across the project

```bash
# From repo root — fan out to both components
just lint
just fix
just test
```

This is what CI runs.

## Environment files

| File | Purpose |
|------|---------|
| `.env` | Production setup (created from `.env.example`) |
| `.env.local` | Local development (created by `just init`) |
| `.env.docker-dev` | Docker development (created on first `just dc-dev` run) |

## Personal recipes

`local.just` (gitignored) is for your own shortcuts:

```bash
cp local.just.example local.just
```

Recipes you add there appear in `just --list` alongside the standard
ones.

## Related

- [Project conventions](conventions.md) — the broader "we do this
  here" rules, including the "always via `just`" mandate.
- [Tools](tools.md) — what `just` recipes wrap (Ruff, pytest, Vitest,
  ESLint, …).
- [Running with Docker](running-the-dev-env-with-docker.md).
- [Running locally](running-the-dev-env-locally.md).
- [Running tests](running-tests.md).
