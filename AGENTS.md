# Repository Guidelines

## Project Structure & Module Organization

Baserow is a monorepo. Core Django code lives in `backend/src`, shared backend tests in `backend/tests`, and the main Nuxt app in `web-frontend/` (`modules/`, `server/`, `test/`, `stories/`). Paid extensions mirror that layout in `premium/backend`, `premium/web-frontend`, `enterprise/backend`, and `enterprise/web-frontend`. End-to-end coverage lives in `e2e-tests/`. Product and contributor docs are in `docs/`, while deployment recipes are under `deploy/`.

## Build, Test, and Development Commands

Use `just` from the repo root; it wraps the backend and frontend workflows consistently for local and Docker setups.

- `just init` installs dependencies and creates `.env.local`.
- `just dev up` starts the local stack; `just dc-dev up -d` runs the Docker dev environment.
- `just b test -n=auto` runs backend pytest suites in parallel.
- `just f test` runs frontend Vitest suites.
- `just lint` runs both backend and frontend linters; `just fix` applies auto-fixes.
- `just b migrate` runs Django migrations.

For direct package-manager use, backend commands run through `uv` and frontend commands through `yarn`.

## Coding Style & Naming Conventions

Python targets Python 3.14, uses 4-space indentation, and is formatted and linted with Ruff (`ruff check`, `ruff format`) with an 88-character line length. Follow existing Django app/module naming and keep new tests in `test_*.py` or `*_test.py` files. Frontend code uses ESLint, Stylelint, and Prettier; SCSS should follow BEM-style naming already used in `web-frontend/modules`.

## Testing Guidelines

Backend tests use `pytest` with `pytest-django`; frontend tests use `vitest`; browser flows live in `e2e-tests/`. Add unit tests for backend changes and targeted frontend tests for component or store behavior. 

Examples: `just b test backend/tests/path/`, `just b test-coverage`, `just f test -- --coverage`, `just f yarn test:core path/to/test`.

## Commit & Pull Request Guidelines

Recent history favors short, imperative subjects, often with Conventional Commit prefixes such as `fix:`, `feat:`, and `chore(deps):`. Branch from `develop`, keep PRs focused, and link the related issue or discussion. Include a clear summary, note schema or env changes, attach screenshots for UI work, add a changelog entry when required, and make sure the relevant lint and test commands pass before opening the PR.

## Project Skills

Reusable skills live in `.agents/skills/`. Each subdirectory is a self-contained skill with a `SKILL.md` that describes when and how to apply it. Use these instead of re-deriving the same workflow from scratch.

| Skill directory | When to use |
|---|---|
| `add-django-config-env-var` | Adding a new Django setting backed by an env var and propagating it to `base.py`, docker-compose files, `env-remap.mjs`, and `docs/installation/configuration.md` |
| `write-frontend-unit-test` | Writing or fixing frontend unit tests in `web-frontend`, `premium/web-frontend`, or `enterprise/web-frontend` |
| `create-update-service` | Creating or updating an integration type or service type in `contrib/integrations` |

## Security & Configuration Tips

Do not commit secrets or local overrides. Use `.env.local` for development, keep production settings in the documented deploy configs, and report vulnerabilities privately via the contact path in `CONTRIBUTING.md` rather than opening a public issue.
