# Claude Code Guidelines for Baserow

This file provides context to Claude Code (and other AI assistants) for working with this codebase.

## Project Structure

- `backend/` - Django backend (Python, uv) - see [backend/CLAUDE.md](backend/CLAUDE.md)
- `web-frontend/` - Nuxt frontend (Node, yarn)
- `premium/` - Premium features (backend + frontend)
- `enterprise/` - Enterprise features (backend + frontend)

## Development Commands

Use `just` from project root or `backend/` directory:

```bash
# Backend (from project root)
just b init          # Initialize backend venv
just b lint          # Run linters (flake8, black, isort, bandit)
just b format        # Format code with black
just b sort          # Sort imports with isort
just b fix           # Fix all (sort + format)
just b test          # Run tests
just b test -n=auto  # Run tests in parallel

# Docker (from project root)
just dc-dev build --parallel  # Build dev images
just dc-dev up -d             # Start dev containers
just dc-dev exec backend bash # Shell into container
```

## Viewing Logs

Use `just logs` to view logs (works with both Docker and local processes):

```bash
just logs                  # All logs (backend + celery)
just logs backend          # Backend only
just logs celery           # Celery workers
just logs frontend         # Web frontend
just logs -f               # Follow logs
just logs -n 100 backend   # Last 100 lines of backend
```

## Python Environment

The backend uses `uv` for package management. The venv location is determined by:

1. `UV_PROJECT_ENVIRONMENT` env var (if set)
2. Default: `../.venv` (relative to `backend/`)

In Docker containers, `UV_PROJECT_ENVIRONMENT=/baserow/venv`.

## Testing

```bash
# Run specific test
just b test tests/baserow/core/test_models.py

# Run with coverage
just b test-coverage

# Fast tests with ramdisk DB (2-5x faster)
just start-test-db  # Start postgres with tmpfs
DATABASE_URL=postgres://baserow:baserow@localhost:5433/baserow just b test

# Test settings: DATABASE_* and REDIS_* vars can be passed via env vars
# Other settings are hardcoded in test.py for consistency
```

