# Running the Dev Environment with Docker

This guide covers running the Baserow development environment using Docker. This is the recommended approach for most developers as it requires minimal local setup and ensures a consistent environment.

## Prerequisites

### Required Tools

1. **Docker** - Install from https://docs.docker.com/desktop/ or similar alternatives. Allocate at least 4GB RAM (8GB recommended).
2. **Git** - Install from https://git-scm.com/downloads
3. **just** - Command runner
   ```bash
   # macOS
   brew install just

   # Linux
   curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
   ```

See [supported.md](../installation/supported.md) for minimum version requirements.

### Verify Installation

```bash
docker -v
docker compose version
git --version
just --version
```

## Quick Start

```bash
# Clone the repository
git clone --branch develop https://github.com/baserow/baserow.git
cd baserow

# Build and start the dev environment
just dc-dev up -d

# View logs (Ctrl+C to stop following)
just dc-dev logs -f
```

Once started, access:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/redoc/

## How It Works

The Docker dev environment runs these services:

| Service | Description | Port |
|---------|-------------|------|
| `web-frontend` | Nuxt.js frontend with hot reload | 3000 |
| `backend` | Django API server with hot reload | 8000 |
| `celery` | Background task worker | - |
| `celery-export-worker` | Export-specific worker | - |
| `celery-beat-worker` | Scheduled task runner | - |
| `db` | PostgreSQL database | 5432 |
| `redis` | Redis cache and message broker | 6379 |
| `caddy` | Reverse proxy for media files | 4000 |
| `mailhog` | Email testing UI | 8025 |
| `mjml-email-compiler` | MJML to HTML email compiler | 28101 |
| `otel-collector` | OpenTelemetry metrics | 4317 |
| `volume-permissions-fixer` | Fixes media file permissions on startup | - |
| `web-frontend-storybook` | Component development UI | 6006 |
| `celery-flower` | Celery task monitoring | 5555 |

### Docker Compose Files

- `docker-compose.yml` - Base configuration (production-like)
- `docker-compose.dev.yml` - Development overrides (hot reload, volume mounts, dev settings)

The `just dc-dev` command combines both files automatically.

## Common Commands

Shortcuts: `dcd` = `dc-dev`, `a` = `dc-attach`, `dct` = `dc-dev tabs`

### Starting and Stopping

```bash
# Start all services (detached)
just dc-dev up -d        # or: just dcd up -d

# Stop all services (preserves data)
just dc-dev stop

# Stop and remove containers (preserves volumes)
just dc-dev down

# Stop and remove everything including volumes (clean slate)
just dc-dev down -v
```

### Viewing Logs

```bash
# All logs
just dc-dev logs

# Follow logs in real-time
just dc-dev logs -f

# Specific services
just dc-dev logs backend
just dc-dev logs web-frontend
just dc-dev logs celery

# Last 100 lines of backend
just dc-dev logs -n 100 backend
```

### Running Commands in Containers

```bash
# Open a shell in a container
just a                              # Interactive container picker
just a backend                      # Direct shell into backend
just a celery                       # Interactive container picker, filtered
just dc-dev exec backend bash       # Alternative

# Run Django management commands
just dc-dev exec backend python manage.py migrate
just dc-dev exec backend python manage.py createsuperuser
just dc-dev exec backend python manage.py shell_plus

# Run tests inside the container
just dc-dev exec backend just test
just dc-dev exec web-frontend yarn test
```

### Terminal Tabs and Tmux

```bash
# Open terminal tabs for each service (like the old dev.sh)
just dc-dev tabs                    # or: just dct

# Start a tmux session with all services
just dc-dev tmux
```

### Building Images

```bash
# Build all images
just dc-dev build --parallel

# Build specific service
just dc-dev build backend

# Build without cache (when things go wrong)
just dc-dev build --no-cache --parallel

# Clear Docker builder cache completely
# WARNING: This clears ALL Docker builder cache, not just Baserow!
just prune
```

### Restarting Services

```bash
# Restart a specific service
just dc-dev restart backend

# Rebuild and restart (after Dockerfile changes)
just dc-dev up -d --build backend

# Force recreate containers
just dc-dev up -d --force-recreate
```

## Optional Services

By default, all services including optional ones are started:

| Service | Description | Port |
|---------|-------------|------|
| `web-frontend-storybook` | Component development UI | 6006 |
| `celery-flower` | Celery task monitoring | 5555 |

This is controlled by the `COMPOSE_PROFILES` variable in `.env.docker-dev`:

```bash
# Default: start all services including optional ones
COMPOSE_PROFILES=optional

# To disable optional services (save resources), set to empty:
COMPOSE_PROFILES=
```

After changing this setting, restart the services:

```bash
just dc-dev down
just dc-dev up -d
```

## Hot Reloading

Both frontend and backend support hot reloading:

- **Frontend**: Changes to `.vue`, `.js`, `.scss` files trigger automatic browser refresh
- **Backend**: Changes to `.py` files trigger automatic server restart

You don't need to restart containers when editing code.

### When to Rebuild

You need to rebuild images when:
- `Dockerfile` changes
- `package.json` or `yarn.lock` changes (frontend)
- `pyproject.toml` or `uv.lock` changes (backend)

```bash
just dc-dev build --parallel
just dc-dev up -d
```

## Database Operations

### Running Migrations

```bash
just dc-dev exec backend python manage.py migrate
```

### Creating a Superuser

```bash
just dc-dev exec backend python manage.py createsuperuser
```

### Accessing the Database

```bash
# PostgreSQL shell
just dc-dev exec db psql -U baserow

# From backend container
just dc-dev exec backend python manage.py dbshell
```

### Resetting the Database

```bash
# Stop services, remove volumes, restart
just dc-dev down -v
just dc-dev up -d
```

## Environment Configuration

### Environment Files

The `just dc-dev` command uses `.env.docker-dev` to define the environment variables used by the `dev` containers. 
This file is automatically created from `.env.docker-dev.example` if it doesn't exist.

### Customizing Settings

Look at [Configuration](../installation/configuration.md) to customize your  `.env.docker-dev`.

### UID/GID for File Permissions

The dev containers run as your host user to avoid permission issues with mounted files:

```bash
# These are set automatically by just dc-dev
UID=$(id -u)
GID=$(id -g)
```

## Troubleshooting

### Container Won't Start

```bash
# Check container status
just dc-dev ps

# View logs for failing service
just dc-dev logs backend

# Rebuild from scratch
just dc-dev down -v
just prune
just dc-dev build --no-cache --parallel
just dc-dev up -d
```

### Slow Performance on macOS

Docker on macOS can be slow with volume mounts. Try:

1. Increase Docker Desktop resources (CPU, RAM)
2. Use Docker's VirtioFS file sharing (Docker Desktop settings)
3. Consider [local development](running-the-dev-env-locally.md) for faster iteration

### Database Connection Errors

```bash
# Ensure db is running and healthy
just dc-dev ps db

# Wait for database to be ready
just dc-dev exec db pg_isready -U baserow

# Check database logs
just dc-dev logs db
```

## Further Reading

- [justfile.md](justfile.md) - Complete command reference
- [running-tests.md](running-tests.md) - Running tests in Docker
- [running-the-dev-env-locally.md](running-the-dev-env-locally.md) - Alternative: local development
- [vscode-setup.md](vscode-setup.md) - VS Code configuration
- [intellij-setup.md](intellij-setup.md) - IntelliJ/PyCharm configuration