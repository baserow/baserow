# Running the Dev Environment with Docker

This guide covers running the Baserow development environment using Docker. This is the recommended approach for most developers as it requires minimal local setup and ensures a consistent environment.

## Prerequisites

### Required Tools

1. **Docker**
   - Install from https://docs.docker.com/desktop/ or similar alternatives
   - Minimum version: Docker 19.03+, Compose 2.0+
   - Allocate at least 4GB RAM to Docker (8GB recommended)

2. **Git**
   - Install from https://git-scm.com/downloads

3. **just** - Command runner
   ```bash
   # macOS
   brew install just

   # Linux
   curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
   ```

### Verify Installation

```bash
docker -v          # Docker version 24.0.0 or higher
docker compose version  # Docker Compose version v2.0.0 or higher
git --version      # git version 2.x
just --version     # just 1.x
```

## Quick Start

```bash
# Clone the repository
git clone --branch develop https://github.com/baserow/baserow.git
cd baserow

# Build and start the dev environment
just dc-dev up -d

# View logs (Ctrl+C to stop following)
just logs -f
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
| `mailhog` | Email testing UI | 8025 |
| `otel-collector` | OpenTelemetry metrics | 4317 |

### Docker Compose Files

- `docker-compose.yml` - Base configuration (production-like)
- `docker-compose.dev.yml` - Development overrides (hot reload, volume mounts, dev settings)

The `just dc-dev` command combines both files automatically.

## Common Commands

### Starting and Stopping

```bash
# Start all services (detached)
just dc-dev up -d

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
just logs

# Follow logs in real-time
just logs -f

# Specific services
just logs backend
just logs frontend
just logs celery

# Last 100 lines of backend
just logs -n 100 backend
```

### Running Commands in Containers

```bash
# Open a shell in a container
just a                              # Interactive container picker
just a backend                      # Direct shell into backend
just dc-dev exec backend bash       # Alternative

# Run Django management commands
just dc-dev exec backend python manage.py migrate
just dc-dev exec backend python manage.py createsuperuser
just dc-dev exec backend python manage.py shell_plus

# Run tests inside the container
just dc-dev exec backend just test
just dc-dev exec web-frontend yarn test
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
| `storybook` | Component development UI | 6006 |
| `flower` | Celery task monitoring | 5555 |

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

| File | Purpose |
|------|---------|
| `.env.docker-dev` | Docker dev environment (auto-created from `.env.docker-dev.example`) |
| `.env` | Production Docker (copy from `.env.example`) |

The `just dc-dev` command automatically creates `.env.docker-dev` if it doesn't exist.

### Customizing Settings

Edit `.env.docker-dev` to customize:

```bash
# Example customizations
BASEROW_PUBLIC_URL=http://localhost:3000
DEBUG=on
BASEROW_AMOUNT_OF_WORKERS=2
```

### UID/GID for File Permissions

The dev containers run as your host user to avoid permission issues with mounted files:

```bash
# These are set automatically by just dc-dev
UID=1000
GID=1000
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

### Permission Errors on Mounted Files

The dev containers are configured to match your host UID/GID. If you still have issues:

```bash
# Check your UID/GID
id -u  # UID
id -g  # GID

# Ensure .env.docker-dev has correct values
echo "UID=$(id -u)" >> .env.docker-dev
echo "GID=$(id -g)" >> .env.docker-dev
```

### Port Already in Use

```bash
# Find what's using the port
lsof -i :3000
lsof -i :8000

# Stop the conflicting process or change the port in docker-compose.dev.yml
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

## IDE Integration

### VS Code

See [vscode-setup.md](vscode-setup.md) for:
- Remote Containers extension setup
- Python/JavaScript debugging configuration
- Recommended extensions

### IntelliJ/PyCharm

See [intellij-setup.md](intellij-setup.md) for:
- Docker interpreter configuration
- Remote debugging setup

## Further Reading

- [justfile.md](justfile.md) - Complete command reference
- [running-tests.md](running-tests.md) - Running tests in Docker
- [running-the-dev-env-locally.md](running-the-dev-env-locally.md) - Alternative: local development
