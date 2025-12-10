# Justfile Development Workflow

Baserow uses [just](https://github.com/casey/just) as a command runner. There are three justfiles:

- **Root justfile** (`/justfile`) - Docker Compose commands and delegates to component justfiles
- **Backend justfile** (`/backend/justfile`) - Backend-specific commands using [uv](https://github.com/astral-sh/uv) for Python
- **Frontend justfile** (`/web-frontend/justfile`) - Frontend-specific commands using yarn

## Installation

### macOS

```bash
# Install just
brew install just

# Install uv (for backend development)
brew install uv
```

### Linux

```bash
# Install just
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin

# Install uv (for backend development)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Ensure `~/.local/bin` is in your PATH.

### Windows (WSL)

Use the Linux instructions above within WSL.

## Project Root Commands

From the project root, you can run Docker Compose commands and delegate to backend commands.

### Docker Compose

Two flexible commands that pass through to `docker compose`:

| Command | Description |
|---------|-------------|
| `just dc <cmd> [args]` | Production compose (docker-compose.yml) |
| `just dc-dev <cmd> [args]` | Dev compose (includes docker-compose.dev.yml) |

Examples:

```bash
# Build dev images
just dc-dev build --parallel

# Start dev environment (detached)
just dc-dev up -d

# Start specific services only
just dc-dev up -d backend db redis

# View logs (follow mode)
just dc-dev logs -f backend

# Open shell in container (with correct UID/GID for file permissions)
just dc-dev shell backend bash

# Open shell as container user (may have permission issues with mounted files)
just dc-dev exec backend bash

# Run command in container
just dc-dev exec backend python baserow migrate

# Stop containers
just dc-dev down

# Show running containers
just dc-dev ps

# Restart a service
just dc-dev restart backend

# Production commands
just dc up -d
just dc build --parallel
```

### Viewing Logs

The `just logs` command provides a unified way to view logs from Docker containers or local processes:

```bash
# View all backend logs (backend + celery)
just logs

# View specific services
just logs backend          # Backend only
just logs celery           # All celery workers
just logs frontend         # Web frontend
just logs backend celery   # Multiple services

# With options
just logs -f               # Follow logs (like tail -f)
just logs -n 100           # Last 100 lines
just logs -f backend       # Follow backend logs only
```

The command automatically detects whether you're running Docker or local processes:
- **Docker**: Uses `docker compose logs` (celery expands to celery + celery-export-worker + celery-beat-worker)
- **Local**: Tails log files from `/tmp/baserow-*.log`

### Full Local Development Environment

Start the entire local dev stack with a single command:

| Command | Description |
|---------|-------------|
| `just dev up` | Start and follow logs (Ctrl+C stops everything) |
| `just dev up -d` | Start in background (detached) |
| `just dev stop` | Stop all services |
| `just dev logs` | View logs (same as `just logs`) |
| `just dev status` | Show running services |

```bash
# Start everything and follow logs (Ctrl+C stops all)
just dev up

# Start in background
just dev up -d

# Check what's running
just dev status

# View logs (when running in background)
just dev logs -f backend

# Stop everything (when running in background)
just dev stop
```

The `just dev up` command:
1. Starts Docker services: `db`, `redis`, `mailhog`, `otel-collector`
2. Waits for PostgreSQL and Redis to be ready
3. Runs database migrations (`just b migrate`)
4. Starts backend dev server → http://localhost:8000
5. Starts Celery workers (main + export + beat)
6. Starts frontend dev server → http://localhost:3000

**Prerequisites:**
- Run `just init` first (creates `.env.local` and installs dependencies)
- Docker must be running (for db, redis, etc.)

**Environment variables** are loaded from `.env.local` in the project root. Key variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_HOST` | PostgreSQL host | `localhost` |
| `DATABASE_PORT` | PostgreSQL port | `5432` |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `SECRET_KEY` | Django secret | (from `.env.local.example`) |

**Log files** are written to `/tmp/`:
- `/tmp/baserow-backend.log`
- `/tmp/baserow-celery.log`
- `/tmp/baserow-web-frontend.log`

Use `just dev logs` or `just logs` to view them (see [Viewing Logs](#viewing-logs)).

### Calling Backend Commands from Root

You can call any backend command from the project root using `just b`:

```bash
# Run backend commands from project root
just b init        # Initialize backend
just b test        # Run tests
just b lint        # Run linter
just b run-dev-server  # Start dev server

# These are equivalent
just b init
just backend init
```

---

## Backend Commands

The following commands are available in the backend justfile. Run them from the `backend/` directory, or from the project root using `just b <command>`.

### Quick Start

```bash
cd backend

# Initialize everything (creates venv, locks deps, installs)
just init

# Run the development server
just run-dev-server

# Run Celery workers (in another terminal)
just run-dev-celery
```

Or from project root:

```bash
just b init
just b run-dev-server
just b run-dev-celery
```

### Environment Configuration

Baserow uses different env files for different purposes:

| File | Purpose | Created by |
|------|---------|------------|
| `.env.local` | Local development (native Python) | Auto-created by `just b init` |
| `.env.docker-dev` | Docker development | Auto-created by `just dc-dev` |
| `.env` | Production Docker | Copy from `.env.example` |

**For local development** (running Python natively):
- `just b init` creates `.env.local` from `.env.local.example`
- All `just b` commands automatically source `.env.local` if present
- Contains: `DATABASE_HOST=localhost`, `REDIS_HOST=localhost`, debug settings

**For Docker development**:
- `just dc-dev` creates `.env.docker-dev` from `.env.docker-dev.example`
- Contains: UID/GID for permissions, Docker networking URLs

#### Using direnv (optional)

For automatic environment loading when entering the directory, use [direnv](https://direnv.net/):

```bash
# Install direnv
brew install direnv  # macOS
# or: apt install direnv  # Linux

# Add to your shell config (~/.bashrc or ~/.zshrc)
eval "$(direnv hook bash)"  # or zsh

# Allow the project's .envrc
direnv allow
```

The `.envrc` file loads `.env.local` and activates the venv automatically.

### Setup & Installation

| Command | Description |
|---------|-------------|
| `just init` | Initialize: create venv, lock deps, install everything |
| `just install` | Install dependencies (alias for sync) |
| `just sync` | Sync all dependencies from uv.lock |
| `just sync-prod` | Sync production dependencies only |
| `just activate` | Print command to activate the venv |

### Development

| Command | Description |
|---------|-------------|
| `just run-dev-server` | Run Django development server (0.0.0.0:8000) |
| `just run-asgi` | Run production ASGI server (gunicorn + uvicorn) |
| `just run-wsgi` | Run production WSGI server (gunicorn) |
| `just run-celery` | Run production Celery worker (main queues) |
| `just run-celery-export` | Run production Celery export worker |
| `just run-celery-beat` | Run production Celery beat scheduler |
| `just run-dev-celery` | Run all Celery workers and beat together (dev) |
| `just manage <cmd>` | Run Django manage.py commands |
| `just m <cmd>` | Shortcut for manage |
| `just migrate` | Run database migrations |
| `just shell` | Open Django shell_plus with SQL logging |
| `just run <cmd>` | Run any command in the venv |

### Code Quality

| Command | Description |
|---------|-------------|
| `just lint` | Run all lint checks (flake8, black, isort, bandit) |
| `just format` | Format code with black |
| `just sort` | Sort imports with isort |
| `just fix` | Fix code style (sort + format) |

### Testing

| Command | Description |
|---------|-------------|
| `just test` | Run tests |
| `just test -n=auto` | Run tests in parallel |
| `just test tests/path` | Run specific tests |
| `just test-coverage` | Run tests with coverage report |
| `just test-builder` | Run builder-specific tests |
| `just test-automation` | Run automation-specific tests |

#### Test Settings

Test settings (`settings/test.py`) are designed for consistency and flexibility:

- **DATABASE_* and REDIS_*** vars can be passed via environment variables
- **All other settings** are hardcoded in test.py to ensure consistent test behavior
- **Optional TEST_ENV_FILE** can be used to load settings from a file

```bash
# Pass database directly via env var
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just b test

# Or use an env file
TEST_ENV_FILE=.env.testing-local just b test
```

This allows tests to run identically inside Docker (using container hostnames) and locally (using localhost).

### Test Database (Ramdisk)

For significantly faster tests, use a PostgreSQL container with tmpfs (in-memory storage). This eliminates disk I/O and can speed up tests by 2-5x.

> **Note:** The `just test-db` command is **host-only**. It starts a separate Docker container and cannot be run from inside another container. When running tests inside the backend container, use the existing `db` service instead.

```bash
# Start test database on port 5433 (always recreates for fresh state)
just test-db up

# Stop and remove the test database
just test-db down
```

The test database runs with optimized settings:
- **tmpfs storage**: All data in RAM (8GB allocated)
- **Disabled fsync/WAL**: No durability overhead
- **Disabled autovacuum**: No background maintenance
- **Large shared_buffers**: 512MB for better caching

#### Running Tests Against the Ramdisk Database

```bash
# Pass DATABASE_URL directly
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just b test

# Run parallel tests against ramdisk
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just b test -n=auto
```

#### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_DB_PORT` | 5433 | Host port for the test database |

```bash
# Use a different port
TEST_DB_PORT=5434 just test-db up
```

The container is named `baserow-test-db` and uses the `pgvector/pgvector:pg13` image.

To stop the test database:

```bash
just test-db down
```

### Dependency Management

| Command | Description |
|---------|-------------|
| `just lock` | Generate/update uv.lock from pyproject.toml |
| `just deps-upgrade` | Upgrade all dependencies |
| `just deps-upgrade-package <pkg>` | Upgrade a specific package |
| `just deps-add <pkg>` | Add a new dependency |
| `just deps-add-dev <pkg>` | Add a new dev dependency |
| `just deps-remove <pkg>` | Remove a dependency |

### Translations

| Command | Description |
|---------|-------------|
| `just make-translations` | Generate translation files |
| `just compile-translations` | Compile translation files |

### Build & Package

| Command | Description |
|---------|-------------|
| `just package-build` | Build wheel packages |
| `just docker-build` | Build Docker image |

### Cleanup

| Command | Description |
|---------|-------------|
| `just clean` | Remove build artifacts |
| `just venv-clean` | Remove virtual environment |
| `just lock-clean` | Remove lock file |
| `just clean-all` | Remove all (artifacts + venv + lock) |

---

## Frontend Commands

The following commands are available in the frontend justfile. Run them from the `web-frontend/` directory, or from the project root using `just f <command>`.

### Quick Start

```bash
cd web-frontend

# Install dependencies
just install

# Run the development server
just run-dev-server
```

Or from project root:

```bash
just f install
just f run-dev-server
```

### Setup

| Command | Description |
|---------|-------------|
| `just install` | Install yarn dependencies |

### Development

| Command | Description |
|---------|-------------|
| `just run-dev-server` | Run Nuxt development server |
| `just storybook` | Run Storybook for component development |

Aliases: `just dev`, `just serve`

### Code Quality

| Command | Description |
|---------|-------------|
| `just lint` | Run ESLint + Stylelint |
| `just fix` | Auto-fix code style issues |
| `just format-scss` | Format SCSS files with Prettier |

Alias: `just l` for lint

### Testing

| Command | Description |
|---------|-------------|
| `just test` | Run Jest tests |
| `just test --watch` | Run tests in watch mode |
| `just ci-test` | Run tests with coverage (for CI) |
| `just update-snapshots` | Update Jest snapshots |

Alias: `just t` for test

### Build

| Command | Description |
|---------|-------------|
| `just build-nuxt` | Build Nuxt for local development |

### Cleanup

| Command | Description |
|---------|-------------|
| `just clean-nuxt` | Remove Nuxt build artifacts (.nuxt/, dist/) |
| `just clean-all` | Remove all (build artifacts + node_modules) |

### Passthrough

| Command | Description |
|---------|-------------|
| `just yarn <args>` | Pass-through to yarn |
| `just npm <args>` | Pass-through to npm |

---

## Tmux Development Sessions

For a more integrated development experience, Baserow provides tmux-based sessions that open multiple panes with shells and logs.

### Local Development with Tmux

```bash
just dev tmux
```

Starts a tmux session with:
- Backend shell + dev server logs
- Celery shell + worker logs
- Database shell + logs
- Redis logs
- Frontend shell + dev server logs

### Docker Development with Tmux

```bash
just dc-dev tmux
```

Starts a tmux session with Docker containers:
- Backend container shell + logs
- Celery container shell + logs (4 panes: shell, redbeat, worker, export worker)
- Database shell + logs
- Redis shell + logs
- Frontend container shell + logs

### Terminal Tabs (like dev.sh)

```bash
just dc-dev tabs
```

Opens terminal tabs for each service (similar to the old `dev.sh` behavior). Works with:
- macOS Terminal.app
- iTerm2
- GNOME Terminal
- Konsole

---

## Examples

### Starting Fresh (Local Development)

```bash
cd backend
just init
# Edit .env.local as needed
just run-dev-server
```

### Starting Fresh (Docker)

```bash
# From project root
just dc-dev build --parallel
just dc-dev up -d
just dc-dev logs -f
```

### Running Tests

```bash
# All tests
just test

# Parallel execution
just test -n=auto

# Specific test file
just test tests/baserow/core/test_models.py

# With coverage
just test-coverage
```

### Adding a Dependency

```bash
# Production dependency
just deps-add httpx

# Dev dependency
just deps-add-dev pytest-benchmark
```

### Django Commands

```bash
# Make migrations
just m makemigrations

# Create superuser
just m createsuperuser

# Custom management command
just m my_custom_command
```

### Celery Development

The `run-dev-celery` command runs all Celery components together with colored output:

- **WORKER** (blue): Main worker for celery and automation_workflow queues
- **EXPORT** (orange): Export worker
- **BEAT** (purple): Scheduler with redbeat

Press Ctrl+C to stop all workers.

To adjust log level or pool type:

```bash
CELERY_LOG_LEVEL=DEBUG just run-dev-celery
CELERY_POOL=threads just run-dev-celery
```

## Differences from Docker Development

| Aspect | Justfile (local) | Docker |
|--------|------------------|--------|
| Python env | Local venv via uv | Container venv |
| Services | External (Redis, PostgreSQL) | docker-compose managed |
| Hot reload | Native file watching | Volume mounts |
| Debugging | Direct IDE integration | Remote debugging |

For services like Redis and PostgreSQL, either:
- Run them locally
- Use `just dc-dev up db redis` to start just the services
- Use the test database: `just test-db up`

## Shell Completion

### The Tradeoff

`just` provides convenient, documented commands but **does not support shell tab-completion** for command arguments. This is because tab completion happens in your shell *before* the command runs, so the shell doesn't know that `just b test` will eventually run `pytest`.

For example, when you type:
```bash
just b test ../enterpr<TAB>   # No completion - shell doesn't know about pytest
```

If you need tab completion (e.g., for file paths), use the underlying command directly from the `backend/` directory:
```bash
source ../.env.local && uv run pytest ../enterpr<TAB>   # Completes to ../enterprise/
```

### Running Commands Directly

For local development with bash completion, you can bypass `just` and run commands directly. You'll need to:

1. **Load environment variables** from `.env.local` (in project root)
2. **Use `uv run`** to execute in the venv

From the `backend/` directory:

```bash
# Option 1: Source env and run (one-liner)
source ../.env.local && uv run pytest ../enterprise/backend/tests/

# Option 2: Use direnv (automatic - recommended)
# If you have direnv set up, .env.local is already loaded
uv run pytest ../enterprise/backend/tests/

# Option 3: Activate venv first
source ../.venv/bin/activate
source ../.env.local  # or use direnv
pytest ../enterprise/backend/tests/
```

### Loading and Clearing Environment Variables

Use these just recipes to manage environment variables in your shell:

```bash
# Load .env.local into current shell
eval "$(just env-load)"

# Clear all variables from .env.local
eval "$(just env-clear)"

# Alternative: start a fresh shell (loses all changes)
exec bash
```

**Note:** The recipes output commands that you `eval` because just runs in a subshell and can't modify your parent shell directly.

If using **direnv**, it automatically loads/unsets variables when you enter/leave the directory.

### When to Use Each Approach

| Use `just` when... | Use direct commands when... |
|-------------------|----------------------------|
| Running standard tasks | You need tab completion for paths |
| Sharing commands with teammates | Debugging/exploring interactively |
| CI/CD scripts | You know the exact command already |
| You don't need completion | IDE integration |

### Installing just Completions

While `just` can't complete *arguments* to the underlying commands, it can complete recipe names:

```bash
# Bash
just --completions bash > ~/.local/share/bash-completion/completions/just

# Zsh
just --completions zsh > ~/.zfunc/_just
# Add to ~/.zshrc: fpath=(~/.zfunc $fpath)

# Fish
just --completions fish > ~/.config/fish/completions/just.fish
```

After installation, `just b <TAB>` will complete recipe names like `test`, `lint`, `run-dev-server`, etc.

## Personal Recipes

You can add your own custom recipes that aren't tracked in git. This is useful for personal shortcuts, project-specific commands, or experimental recipes.

### Setup

```bash
# Copy the example file
cp local.just.example local.just

# Edit with your own recipes
vim local.just
```

The `local.just` file is automatically imported by the main justfile (using `import? 'local.just'`). Your recipes will appear in `just --list` alongside the standard recipes.

### Example local.just

```just
# Personal recipes - not tracked in git

# Quick test for a specific module I'm working on
my-test:
    just b test tests/baserow/contrib/builder/

# My preferred dev startup (services only, no frontend)
my-dev:
    just dc-dev up -d redis db mailhog
    just b run-dev-server

# Reset my local database
my-reset:
    just dc-dev exec db psql -U baserow -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    just b migrate
```

### Per-Component Recipes

You can also create `local.just` in component directories:

- `backend/local.just` - Backend-specific personal recipes
- `web-frontend/local.just` - Frontend-specific personal recipes

Each component's justfile imports its own `local.just` independently.

### Notes

- All `local.just` files are gitignored
- Use `local.just.example` in the project root as a starting template
- Your recipes can call other recipes using `just <recipe>`

## Troubleshooting

### "Dev environment not found"

Run `just init` to set up the environment.

### Import errors after pulling changes

```bash
just sync  # Re-sync dependencies
```

### Permission errors

Ensure you own the `.venv` directory:

```bash
just venv-clean
just init
```

### Celery crashes on macOS

The justfile defaults to `solo` pool on macOS to avoid fork() issues. If you need different behavior:

```bash
CELERY_POOL=threads just run-dev-celery
```
