# Code quality

The quality of the code is very important. That is why we have linters, unit tests, API
docs, in-code docs, developer docs, modular code, and have put a lot of thought into the
underlying architecture of both the backend and the web-frontend.

## Running linters and tests

If you have the [development environment](./running-the-dev-env-locally.md) up and running
you can easily run the linters using [just](./justfile.md) commands.

**Backend (from project root or `backend/` directory):**

- `just b fix`: run Ruff checks with automatic fixes and format Python code.
  Aliases: `just b format`, `just b f`.
- `just b lint`: check Python code with Ruff. Alias: `just b check`, `just b l`.

**Frontend (from project root or `web-frontend/` directory):**

- `just f lint`: check the frontend trees with ESLint (JS/TS/Vue), Stylelint
  (SCSS), and Prettier (also CSS/JSON/Markdown/HTML/YAML).
- `just f fix`: auto-fix issues with the same tools.

All of the above accept an optional list of file paths and restrict the run to
just those files:

```bash
just b fix backend/src/baserow/core/utils.py
just f fix web-frontend/modules/core/jobTypes.js
```

A few things to know when passing paths:

- **Paths must be repo-root-relative** (for example `backend/src/baserow/...`,
  not `src/baserow/...`), even when you invoke the recipe from inside
  `backend/` or `web-frontend/`. This keeps the behavior identical regardless
  of where you run it from and matches what `pre-commit` passes in.
- Paths outside the linted trees (`backend/{src,tests}`,
  `{premium,enterprise}/backend/{src,tests}`, `web-frontend/`,
  `{premium,enterprise}/web-frontend/`) are silently skipped, as are files with
  extensions the tools don't handle. This lets you pipe in a mixed file list
  without filtering it yourself.
- **With no arguments each recipe lints its full component tree** (`just b`
  walks all backend trees, `just f` walks all frontend trees; running both
  covers the monorepo). This matters when you scope to a diff with `$(...)`
  — if the diff is empty, the expansion produces no arguments and you'll
  accidentally trigger a full-tree run. Guard the call when scripting:

  ```bash
  # Scope to your branch's changes, skipping the run if nothing changed:
  files=$(git diff --name-only origin/develop...HEAD)
  if [ -n "$files" ]; then
      just b fix $files
      just f fix $files
  fi
  ```

## Running tests

There are also commands to easily run the tests.

- `just b test` (backend): run all backend Python tests with pytest.
- `just b test -n=auto` (backend): run tests in parallel for faster execution.
- `just f test` (frontend): run all frontend tests with Vitest.

## Git pre-commit hooks

Baserow uses [`pre-commit`](https://pre-commit.com/) to automatically run linters and
formatters before commits are created. This ensures your changes comply with repo-wide
code quality rules without waiting for CI feedback.

The lint/format hooks delegate to the same `just b fix` and `just f fix` recipes used
by CI and manual runs, so pre-commit will never produce changes that differ from
running `just fix` yourself.

### Installation

To set up the pre-commit hooks locally in your `.git/` folder, run the following command from the repository root:

```bash
just pre-commit-install
```

This registers a few general hygiene hooks (YAML syntax checks, merge-conflict
markers, large files) plus the backend and frontend lint/format hooks. Trailing
whitespace and end-of-file fixes are intentionally left to `ruff`/`prettier` to
avoid touching legacy files.

To remove the hooks again:

```bash
just pre-commit-uninstall
```

### Running manually

You can also run pre-commit manually at any time against all files or staged changes:

```bash
# Run against all files
just b run pre-commit run --all-files

# Run against specific files
just b run pre-commit run --files path/to/file1.py path/to/file2.js
```

#### Tip: lint everything you've touched on this branch

A normal `git commit` runs the hooks on **staged files only**, and `pre-commit run`
with no arguments does the same. To lint every file you have changed relative to
`HEAD` (staged _and_ unstaged), pass the diff explicitly:

```bash
just b run pre-commit run --files $(git diff --name-only HEAD)
```

This is handy before opening a pull request: it scopes the run to your
work-in-progress without re-linting the entire monorepo the way
`--all-files` does. Swap `HEAD` for a base ref (for example `origin/develop`) to
lint everything your branch changes:

```bash
just b run pre-commit run --files $(git diff --name-only origin/develop...HEAD)
```

If you only want to run the Ruff or ESLint/Stylelint/Prettier steps (and skip the
ancillary pre-commit hooks like `check-yaml`), call the `just` recipes directly
with the same file list — they accept a list of paths and route each file to the
appropriate tool. Remember to guard against an empty diff, otherwise an empty
expansion will lint the whole monorepo:

```bash
files=$(git diff --name-only origin/develop...HEAD)
if [ -n "$files" ]; then
    just b fix $files
    just f fix $files
fi
```

See the [pre-commit documentation](https://pre-commit.com/#usage) for more advanced
usage (skipping hooks for a commit, running a single hook, updating hook versions,
etc.).

## Continuous integration

To make sure nothing was missed during development we also have a continuous
integration pipeline that runs every time a branch is pushed. All the commands explained
above will execute in an isolated environment. In order to improve speed
they are separated by lint and test stages. It is not allowed to merge a branch if
one of these jobs fails.

The pipeline also has a build job. During this job
[plugin boilerplate](../plugins/boilerplate.md) Baserow will be installed as a
dependency to ensure that this still works.

### Running CI locally

You can run the same checks locally before pushing:

```bash
# Run all linters
just lint

# Run all tests
just test

# Or run backend/frontend separately
just b lint && just b test
just f lint && just f test
```

For Docker-based CI testing (matches the CI environment more closely):

```bash
just ci build           # Build CI images
just ci lint            # Run linters in containers
just ci test            # Run tests in containers
just ci run             # Full CI pipeline
```
