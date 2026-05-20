# Code quality

The quality of the code is very important. That is why we have linters, unit tests, API
docs, in-code docs, developer docs, modular code, and have put a lot of thought into the
underlying architecture of both the backend and the web-frontend.

## Running linters and tests

If you have the [development environment](./running-the-dev-env-locally.md) up and running
you can easily run the linters using [just](./justfile.md) commands.

**Backend (from project root or `backend/` directory):**

- `just b format`: auto-format all Python code using Ruff formatter.
- `just b fix`: run Ruff checks with automatic fixes and format Python code.
- `just b lint`: check Python code with Ruff.

**Frontend (from project root or `web-frontend/` directory):**

- `just f lint`: check JavaScript and SCSS files with ESLint and Stylelint.
- `just f fix`: auto-fix code style issues.

## Running tests

There are also commands to easily run the tests.

- `just b test` (backend): run all backend Python tests with pytest.
- `just b test -n=auto` (backend): run tests in parallel for faster execution.
- `just f test` (frontend): run all frontend tests with Jest.

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
