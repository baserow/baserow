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

Verify your installation:

```bash
$ docker -v
Docker version 24.0.0, build ...
$ just --version
just 1.25.0
$ git --version
git version 2.40.0
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
just dc-dev shell backend bash

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
| Open backend shell | `just dc-dev shell backend bash` |
| Restart a service | `just dc-dev restart backend` |

### Hot reloading

Both the web-frontend and backend containers monitor file changes and update automatically.
You don't need to restart containers when making code changes - the result should appear right away.

## Alternative: Local development (without Docker)

For faster iteration, you can run the backend natively while using Docker only for services (PostgreSQL, Redis):

```bash
# Start only database and redis
just dc-dev up -d db redis

# Initialize the backend (creates venv, installs deps)
just b init

# Run the development server
just b run-dev-server

# In another terminal, run Celery workers
just b run-dev-celery
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
