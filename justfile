# Baserow Project Justfile
# Root justfile that delegates to component-specific justfiles

# Default recipe - show help
default:
    @just --list

# =============================================================================
# Backend
# =============================================================================

# Run any backend command (e.g., just b init, just b test)
[doc("Run backend command: just b <cmd>")]
backend *args:
    @just --justfile backend/justfile --working-directory backend {{ args }}

# Shortcut alias for backend
alias b := backend

# =============================================================================
# Docker Compose
# =============================================================================

_dc_help:
    @echo "Usage: just dc <cmd> [args]       (production - uses published images)"
    @echo "       just dc-dev <cmd> [args]   (development - builds dev images)"
    @echo "       just dc-prod <cmd> [args]  (production images built locally)"
    @echo ""
    @echo "Examples:"
    @echo "  just dc-dev build --parallel     # Build all dev images"
    @echo "  just dc-dev build backend        # Build specific service"
    @echo "  just dc-dev up -d                # Start containers (detached)"
    @echo "  just dc-dev up -d backend db     # Start specific services"
    @echo "  just dc-dev stop                 # Stop containers (keep volumes)"
    @echo "  just dc-dev down                 # Stop and remove containers"
    @echo "  just dc-dev logs -f backend      # Follow logs for a service"
    @echo "  just dc-dev shell backend bash   # Open shell with correct UID/GID"
    @echo "  just dc-dev exec backend bash    # Open shell (as container user)"
    @echo "  just dc-dev ps                   # Show running containers"
    @echo ""
    @echo "Special commands (dc-dev only):"
    @echo "  shell  - Like 'exec' but with -u \$UID:\$GID for correct file permissions"
    @echo ""
    @echo "Production (uses published images from registry):"
    @echo "  just dc up -d"
    @echo "  just dc pull"
    @echo ""
    @echo "Build production images locally:"
    @echo "  just dc-prod build --parallel"

# Production compose (base docker-compose.yml only)
[doc("Docker compose (prod): just dc <cmd> [args]")]
dc *ARGS:
    #!/usr/bin/env bash
    if [ -z "{{ ARGS }}" ]; then
        just _dc_help
    else
        docker compose -f docker-compose.yml {{ ARGS }}
    fi

# Dev compose (includes docker-compose.dev.yml overlay)
# Special command: "shell" is translated to "exec -u $UID:$GID" for opening shells with correct permissions
[doc("Docker compose (dev): just dc-dev <cmd> [args]")]
dc-dev *ARGS:
    #!/usr/bin/env bash
    if [ -z "{{ ARGS }}" ]; then
        just _dc_help
    else
        if [ ! -f .env.docker-dev ] && [ -f .env.docker-dev.example ]; then
            echo "Creating .env.docker-dev from .env.docker-dev.example..."
            cp .env.docker-dev.example .env.docker-dev
        fi
        if [[ -z "$UID" ]]; then
            UID=$(id -u)
        fi
        export UID
        if [[ -z "$GID" ]]; then
            GID=$(id -g)
        fi
        export GID
        # Handle special "shell" command: translate to exec -u $UID:$GID
        ARGS="{{ ARGS }}"
        if [[ "$ARGS" == shell* ]]; then
            ARGS="exec -u $UID:$GID ${ARGS#shell}"
        fi
        docker compose --env-file .env.docker-dev -f docker-compose.yml -f docker-compose.dev.yml $ARGS
    fi

# Build production images locally (includes docker-compose.build.yml overlay)
[doc("Docker compose (prod local): just dc-prod <cmd> [args]")]
dc-prod *ARGS:
    #!/usr/bin/env bash
    if [ -z "{{ ARGS }}" ]; then
        just _dc_help
    else
        BASEROW_VERSION=latest docker compose -f docker-compose.yml -f docker-compose.build.yml {{ ARGS }}
    fi

# =============================================================================
# Frontend (placeholder for future)
# =============================================================================

# frontend *args:
#     @just --justfile web-frontend/justfile {{ args }}

# =============================================================================
# Environment
# =============================================================================

# Print command to load .env.local (use with: eval "$(just env-load)")
[doc("Print command to load .env.local: eval \"$(just env-load)\"")]
env-load:
    @echo 'set -a; source "'"$PWD"'/.env.local"; set +a'

# Print command to unset all vars from .env.local (use with: eval "$(just env-clear)")
[doc("Print command to clear .env.local vars: eval \"$(just env-clear)\"")]
env-clear:
    #!/usr/bin/env bash
    if [ -f .env.local ]; then
        vars=$(grep -v '^#' .env.local | grep -v '^$' | grep '=' | cut -d= -f1 | xargs)
        if [ -n "$vars" ]; then
            echo "unset $vars"
        fi
    else
        echo "echo 'No .env.local found'"
    fi

# =============================================================================
# Full Stack
# =============================================================================

# Initialize everything
init:
    @just b init

# Run all linters
lint:
    @just b lint

# Run all tests
test:
    @just b test

# Fix all code style
fix:
    @just b fix

# =============================================================================
# Test Database (ramdisk for fast tests)
# =============================================================================

# Test DB settings
test_db_name := "baserow-test-db"
test_db_port := env("TEST_DB_PORT", "5433")
test_db_image := "pgvector/pgvector:pg13"

# Start PostgreSQL with tmpfs (ramdisk) for fast backend tests
# Data is stored in RAM - 2-5x faster than disk-based tests
[doc("Start ramdisk PostgreSQL for fast tests")]
test-db:
    #!/usr/bin/env bash
    set -euo pipefail
    # Always remove and recreate to get fresh tmpfs
    if docker ps -a --format '{{ '{{.Names}}' }}' | grep -q "^{{ test_db_name }}$"; then
        echo "Removing existing container to get fresh tmpfs..."
        docker rm -f {{ test_db_name }} > /dev/null
    fi
    echo "Creating test database container with tmpfs (ramdisk)..."
    docker run -d \
        --name {{ test_db_name }} \
        -e POSTGRES_USER=baserow \
        -e POSTGRES_PASSWORD=baserow \
        -e POSTGRES_DB=baserow \
        -p {{ test_db_port }}:5432 \
        --tmpfs /var/lib/postgresql/data:size=8G \
        {{ test_db_image }} \
        -c shared_buffers=512MB \
        -c fsync=off \
        -c full_page_writes=off \
        -c synchronous_commit=off \
        -c max_locks_per_transaction=512 \
        -c logging_collector=off \
        -c log_statement=none \
        -c log_duration=off \
        -c log_min_duration_statement=-1 \
        -c log_checkpoints=off \
        -c log_connections=off \
        -c log_disconnections=off \
        -c log_lock_waits=off \
        -c log_temp_files=-1 \
        -c checkpoint_timeout=1h \
        -c max_wal_size=10GB \
        -c min_wal_size=1GB \
        -c wal_level=minimal \
        -c max_wal_senders=0 \
        -c autovacuum=off \
        -c random_page_cost=1.0 \
        -c effective_io_concurrency=200 \
        -c work_mem=256MB \
        -c maintenance_work_mem=512MB
    echo ""
    echo "Test database running on port {{ test_db_port }}"
    echo ""
    echo "Run tests with:"
    echo "  DATABASE_URL=postgres://baserow:baserow@localhost:{{ test_db_port }}/baserow just b test -n=auto"

# Stop the ramdisk test database
[doc("Stop ramdisk PostgreSQL")]
test-db-stop:
    docker rm -f {{ test_db_name }} 2>/dev/null || true

# =============================================================================
# Logs
# =============================================================================

# Log files for local dev servers
backend_log_file := "/tmp/baserow-backend.log"
celery_log_file := "/tmp/baserow-celery.log"
frontend_log_file := "/tmp/baserow-web-frontend.log"

# View logs (works with Docker or local processes)
# Usage: just logs [options] [services...]
# Options: -f (follow), -n 100 (last 100 lines), etc.
# Services: backend, celery, frontend (default: backend celery)
[doc("View logs: just logs [-f] [-n 100] [backend] [celery] [frontend]")]
logs *ARGS:
    #!/usr/bin/env bash
    BACKEND_LOG="{{ backend_log_file }}"
    CELERY_LOG="{{ celery_log_file }}"
    FRONTEND_LOG="{{ frontend_log_file }}"

    # Parse args: separate options (start with -) from services
    OPTS=()
    SERVICES=()
    for arg in {{ ARGS }}; do
        if [[ "$arg" == -* ]]; then
            OPTS+=("$arg")
        else
            SERVICES+=("$arg")
        fi
    done

    # Default to backend and celery if none specified
    if [ ${#SERVICES[@]} -eq 0 ]; then
        SERVICES=(backend celery)
    fi

    # Check if docker backend is running
    if just dc-dev ps backend 2>/dev/null | grep -q "Up"; then
        echo "==> Logs from Docker containers"
        # Expand service names to docker compose service names
        DOCKER_SERVICES=()
        for svc in "${SERVICES[@]}"; do
            case "$svc" in
                backend)  DOCKER_SERVICES+=(backend) ;;
                celery)   DOCKER_SERVICES+=(celery celery-export-worker celery-beat-worker) ;;
                frontend) DOCKER_SERVICES+=(web-frontend) ;;
            esac
        done
        just dc-dev logs "${OPTS[@]}" "${DOCKER_SERVICES[@]}"
        exit 0
    fi

    # Map service names to log files
    FILES=()
    for svc in "${SERVICES[@]}"; do
        case "$svc" in
            backend)  [ -f "$BACKEND_LOG" ] && FILES+=("$BACKEND_LOG") ;;
            celery)   [ -f "$CELERY_LOG" ] && FILES+=("$CELERY_LOG") ;;
            frontend) [ -f "$FRONTEND_LOG" ] && FILES+=("$FRONTEND_LOG") ;;
        esac
    done

    if [ ${#FILES[@]} -gt 0 ]; then
        echo "==> Logs from local files"
        tail "${OPTS[@]}" "${FILES[@]}"
    else
        echo "No logs found."
        echo "If running locally, start with: just b run-dev-server"
        echo "If running in Docker, start with: just dc-dev up backend"
    fi
