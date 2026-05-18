# Code quality

How the codebase is kept consistent: linters, formatters, tests, and
CI. The settings of *what* counts as a violation live with each tool's
config; this page is the operator's view.

For the broader "we do this here" rules — comments, type hints,
imports, locales — see [Project conventions](conventions.md). For the
`just` invocation styles see
[justfile reference](justfile.md#how-to-invoke-the-three-styles); the
commands below use the bare form from the component directory.

## Running linters

### Backend

From `backend/`:

```bash
just fix        # Ruff format + Ruff lint --fix (auto-fix style + lint issues)
just lint       # Ruff check only — no changes to files
```

Ruff covers format, lint, import sorting, and security checks
(`bandit`) in one tool. See [Tools — Ruff](tools.md#ruff) for the
configuration source.

### Frontend

From `web-frontend/`:

```bash
just fix        # ESLint + Stylelint + Prettier — auto-fix
just lint       # check only
```

## Running tests

### Backend (pytest)

From `backend/`:

```bash
just test                  # all tests
just test -n=auto          # parallel
just test tests/path/      # specific path
```

For the full reference (ramdisk DB, env-file mode, Docker vs local)
see [Running tests](running-tests.md).

### Frontend (Vitest)

From `web-frontend/`:

```bash
just test
just yarn test:core …      # specific test path
```

### End-to-end (Playwright)

From `e2e-tests/`:

```bash
just test
```

See [E2E testing](e2e-testing.md) for when and what to add.

## Everything at once

From the repo root, the no-prefix recipes fan out to both components:

```bash
just lint        # backend + frontend lint
just fix         # backend + frontend auto-fix
just test        # backend + frontend tests
```

This is what CI runs before allowing a merge.

## Continuous integration

CI runs every push. Lint and test stages run separately so the fast
checks fail-fast before the slower ones. A branch cannot merge while
any stage is red.

The build job also installs Baserow as a dependency to verify the
package builds cleanly.

### Running CI checks locally

The same commands as CI:

```bash
just lint                  # from repo root
just test                  # from repo root
```

For a more accurate Docker-based replica of the CI environment:

```bash
just ci build              # build CI images
just ci lint               # run linters in containers
just ci test               # run tests in containers
just ci run                # full CI pipeline
```

## Related

- [Project conventions](conventions.md) — the rules the linters
  enforce.
- [Running tests](running-tests.md) — backend test deep dive.
- [E2E testing](e2e-testing.md).
- [Tools](tools.md) — Ruff, pytest, Vitest, ESLint, Stylelint,
  Prettier, Playwright.
- [justfile reference](justfile.md) — the three invocation styles.
