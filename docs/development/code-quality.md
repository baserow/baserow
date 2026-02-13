# Code quality

The quality of the code is very important. That is why we have linters, unit tests, API
docs, in-code docs, developer docs, modular code, and have put a lot of thought into the
underlying architecture of both the backend and the web-frontend.

## Running linters and tests

If you have the [development environment](./running-the-dev-env-locally.md) up and running
you can easily run the linters using [just](./justfile.md) commands.

**Backend (from project root or `backend/` directory):**
* `just b format`: auto format all Python code using black.
* `just b sort`: sort imports using isort.
* `just b fix`: run both format and sort.
* `just b lint`: check Python code with flake8, black, isort, and bandit.

**Frontend (from project root or `web-frontend/` directory):**
* `just f lint`: check JavaScript with eslint and SCSS with stylelint.
* `just f fix`: auto-fix code style issues.

## Running tests

There are also commands to easily run the tests.

* `just b test` (backend): run all backend Python tests with pytest.
* `just b test -n=auto` (backend): run tests in parallel for faster execution.
* `just f test` (frontend): run all frontend tests with Jest.

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
