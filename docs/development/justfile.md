# Justfile Command Reference

Baserow uses [just](https://github.com/casey/just) as a command runner. Commands are organized in three justfiles:

- **Root** (`/justfile`) - Docker Compose and orchestration commands
- **Backend** (`/backend/justfile`) - Python/Django commands using [uv](https://github.com/astral-sh/uv)
- **Frontend** (`/web-frontend/justfile`) - Node/Nuxt commands using yarn

## Discovering Commands

Use `just` built-in help to explore all available recipes:

```bash
# List all commands (grouped by category)
just --list

# Show getting started guide
just help

# List backend commands
just b --list
# or
cd backend && just --list

# List frontend commands
just f --list
```

Each recipe includes a description. Use `just --list` frequently to discover new commands.

## Installation

```bash
# macOS
brew install just uv

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Essential Commands

### First Time Setup

```bash
just init          # Install backend + frontend dependencies, create .env.local
```

### Local Development

```bash
just dev up        # Start everything (db, redis, backend, celery, frontend)
just dev up -d     # Start in background
just dev stop      # Stop all services
just dev logs      # View logs
just dev ps        # Show the running processes + containers (db, redis)
```

### Docker Development

```bash
just dc-dev up -d           # Start dev containers
just dcd logs -f            # Follow logs (dcd as alias of dc-dev)
just dcd exec backend bash  # Shell into container
just dcd down               # Stop containers
just dcd ps                 # SHow running containers
```

### Running Commands 

```bash
# Backend (from root)
just b test              # Run backend tests
just b lint              # Lint backend
just b shell             # Django shell
just b migrate           # Run migrations
just b manage <cmd>      # Any manage.py command

# Frontend (from root)
just f test              # Run frontend tests
just f lint              # Lint frontend
```

### Code Quality

```bash
just lint         # Lint all (backend + frontend)
just fix          # Auto-fix style issues
just test         # Run all tests
```

### Testing with Ramdisk Database

For faster tests, use an in-memory PostgreSQL:

```bash
just test-db up     # Start ramdisk db on port 5433
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just b test -n=auto
just test-db down   # Stop ramdisk db
just test-db ps     # Check status
```

## Environment Files

| File | Purpose |
|------|---------|
| `.env` | Production setup (created from `.env.example`) |
| `.env.local` | Local development (created by `just init`) |
| `.env.docker-dev` | Docker development (created by `just dc-dev`) |

## Personal Recipes

Create `local.just` for your own shortcuts (gitignored):

```bash
cp local.just.example local.just
```

Your recipes will appear in `just --list` alongside standard recipes.

## Further Reading

- [Running with Docker](running-the-dev-env-with-docker.md)
- [Running Locally](running-the-dev-env-locally.md)
- [Running Tests](running-tests.md)