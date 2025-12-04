# Running the dev environment

If you want to contribute to Baserow you need to setup the development environment on
your local computer. The best way to do this is via `docker compose` so that you can
start the app with the least amount of hassle.

> **Note:** The `dev.sh` script is deprecated. Use `just` commands instead as described below.
> See [justfile.md](justfile.md) for the complete command reference.

## Quickstart

If you are familiar with git and Docker, run these commands to launch Baserow's
dev environment locally:

```bash
# Clone the repository
git clone --branch develop git@github.com:baserow/baserow.git
cd baserow

# Start the dev environment (builds images if needed)
just dc-dev up -d

# View logs
just logs -f

# Or view specific service logs
just logs -f backend
```

For more details on available commands, run `just --list` or see [justfile.md](justfile.md).

## Installing requirements

### Required tools

1. **Docker** - Install from https://docs.docker.com/desktop/
   - Minimum version: 19.03 (latest recommended)
   - Verify with: `docker -v`

2. **just** - Command runner for development tasks
   ```bash
   # macOS
   brew install just

   # Linux
   curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
   ```

3. **Git** - Install from https://git-scm.com/downloads
   - Verify with: `git --version`

4. **Node.js 24** - Required for frontend development (local only, not needed for Docker)
   ```bash
   # macOS (using nvm)
   nvm install 24
   nvm use 24

   # Or with Homebrew
   brew install node@24

   # Linux (using nvm)
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
   nvm install 24
   nvm use 24
   ```

5. **Yarn** - Package manager for frontend
   ```bash
   npm install -g yarn
   ```

6. **uv** - Fast Python package manager (for backend development)
   ```bash
   # macOS
   brew install uv

   # Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

Verify your installation:

```bash
$ docker -v
Docker version 24.0.0, build ...
$ just --version
just 1.25.0
$ git --version
git version 2.40.0
$ node -v
v24.0.0
$ yarn -v
1.22.22
$ uv --version
uv 0.5.0
```

## Starting the dev environment

> If you run into any issues starting your development environment feel free to contact
> us via the form on https://baserow.io/contact.

### Clone the repository

```bash
git clone --branch develop https://github.com/baserow/baserow.git
cd baserow
```

### Build and start containers

```bash
# Build images (first time or after Dockerfile changes)
just dc-dev build --parallel

# Start all services in detached mode
just dc-dev up -d
```

The first build may take a while as images are built from scratch. Subsequent starts will be much faster.

### Verify it's running

```bash
# Check container status
just dc-dev ps

# View logs
just logs -f
```

Your dev environment is now running! The database has been automatically migrated
and the Baserow templates have been synced. Visit http://localhost:3000 to sign up and login.

## Looking at the web API

Baserow's backend container exposes a REST API:

- **API Documentation**: http://localhost:8000/api/redoc/
- **API Root**: http://localhost:8000/api/workspaces/ (will show auth error without JWT)

## Working with the dev environment

### Viewing logs

```bash
# All logs (backend + celery)
just logs

# Follow logs in real-time
just logs -f

# Specific services
just logs backend          # Backend only
just logs celery           # All celery workers
just logs frontend         # Web frontend
just logs -f backend       # Follow backend logs
```

### Running commands in containers

```bash
# Open a shell in the backend container
just dc-dev exec backend bash

# Run Django management commands
just dc-dev exec backend python manage.py migrate
just dc-dev exec backend python manage.py createsuperuser

# Run any command
just dc-dev exec backend python manage.py shell_plus
```

### Common operations

| Task | Command |
|------|---------|
| Start environment | `just dc-dev up -d` |
| Stop environment | `just dc-dev down` |
| Rebuild images | `just dc-dev build --parallel` |
| View logs | `just logs -f` |
| Run migrations | `just dc-dev exec backend python manage.py migrate` |
| Open backend shell | `just dc-dev exec backend bash` |
| Restart a service | `just dc-dev restart backend` |

### Optional services

Some services are not started by default to reduce resource usage:

- **Storybook** - Component development UI (port 6006)
- **Celery Flower** - Celery task monitoring UI (port 5555)

To include these optional services:

```bash
# Start with optional services
just dc-dev --profile optional up -d

# Or use the shorthand
just dc-dev-full up -d
```

### Hot reloading

Both the web-frontend and backend containers monitor file changes and update automatically.
You don't need to restart containers when making code changes - the result should appear right away.

## Alternative: Local development (without Docker)

For faster iteration, you can run the backend and frontend natively while using Docker only for services (PostgreSQL, Redis, etc.).

### Quick Start with `start-dev-local`

The easiest way to start local development is with the `start-dev-local` command:

```bash
# Initialize backend and frontend (first time only)
just init

# Start the full local development environment
just start-dev-local
```

This single command:
1. Starts Docker services: `db`, `redis`, `mailhog`, `otel-collector`
2. Waits for PostgreSQL and Redis to be ready
3. Runs database migrations
4. Starts the backend Django dev server (http://localhost:8000)
5. Starts all Celery workers (main, export, beat scheduler)
6. Starts the frontend Nuxt dev server (http://localhost:3000)

To stop everything:

```bash
just stop-dev-local
```

### Environment Configuration

The `start-dev-local` command requires environment variables from `.env.local` (created during `just init`).

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_HOST` | PostgreSQL host | `localhost` |
| `DATABASE_PORT` | PostgreSQL port | `5432` |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `SECRET_KEY` | Django secret key | (auto-generated) |

The `.env.local` file is automatically loaded by backend commands via the `_load_env` helper in the justfile.

### How `start-dev-local` Works

The `start-dev-local` command orchestrates multiple justfile recipes:

```
just start-dev-local
├── just dc-dev up -d redis db mailhog otel-collector   # Start Docker services
├── just b migrate                                       # Run database migrations
├── just b run-dev-server                                # Backend (backend/justfile)
├── just b run-dev-celery                                # Celery workers (backend/justfile)
└── just f run-dev-server                                # Frontend (web-frontend/justfile)
```

All processes log to `/tmp/baserow-*.log`:
- `/tmp/baserow-backend.log` - Django dev server
- `/tmp/baserow-celery.log` - Celery workers
- `/tmp/baserow-web-frontend.log` - Nuxt dev server

### Viewing Logs

```bash
# View all logs (backend + celery)
just logs

# Follow logs in real-time
just logs -f

# Specific services
just logs backend          # Backend only
just logs celery           # All celery workers
just logs frontend         # Nuxt frontend
just logs -f backend       # Follow backend logs
```

### Syncing Templates

To sync Baserow templates locally (creates example databases, forms, etc.):

```bash
just b manage sync_templates
```

This is disabled by default during local development for faster startup (controlled by `SYNC_TEMPLATES_ON_STARTUP=false` in `.env.local`). Run it manually when you need the templates.

### Manual Setup (Alternative)

If you prefer more control, you can start services manually:

```bash
# Start only database and redis
just dc-dev up -d db redis

# Initialize the backend (creates venv, installs deps)
just b init

# Run the development server
just b run-dev-server

# In another terminal, run Celery workers
just b run-dev-celery

# In another terminal, run the frontend
just f run-dev-server
```

See [justfile.md](justfile.md) for more details on local development.

## Further reading

- [justfile.md](justfile.md) - Complete command reference
- [running-tests.md](running-tests.md) - How to run tests
- [introduction](../technical/introduction.md) - Baserow's architecture
- [install-with-docker](../installation/install-with-docker.md) - Docker configuration options

---

## Deprecated: dev.sh

> **Warning:** `dev.sh` is deprecated and will be removed in a future release.
> Please use `just` commands instead.

The `dev.sh` script was the previous way to manage the dev environment. If you're
migrating from `dev.sh`, here are the equivalent `just` commands:

| dev.sh command | just equivalent |
|----------------|-----------------|
| `./dev.sh` | `just dc-dev up -d` |
| `./dev.sh help` | `just --list` |
| `./dev.sh build` | `just dc-dev build --parallel` |
| `./dev.sh restart` | `just dc-dev restart` |
| `./dev.sh restart --build` | `just dc-dev up -d --build` |
| `./dev.sh run backend manage migrate` | `just dc-dev exec backend python manage.py migrate` |
| `docker-compose logs` | `just logs` |

For the full dev.sh documentation (deprecated), see [dev_sh.md](dev_sh.md).
