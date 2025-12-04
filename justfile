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
# Web-Frontend
# =============================================================================

# Run any web-frontend command (e.g., just f lint, just f test)
[doc("Run frontend command: just f <cmd>")]
frontend *args:
    @just --justfile web-frontend/justfile --working-directory web-frontend {{ args }}

# Shortcut alias for frontend
alias f := frontend

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

# Run docker compose for specific deployment configurations
[doc("Docker compose for deployments: just dc-deploy <name> <cmd>")]
dc-deploy name="" *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{ name }}" in
        "all-in-one")
            docker compose -f deploy/all-in-one/docker-compose.yml {{ ARGS }}
            ;;
        "all-in-one-dev")
            if [[ -z "${UID:-}" ]]; then
                UID=$(id -u)
            fi
            export UID
            if [[ -z "${GID:-}" ]]; then
                GID=$(id -g)
            fi
            export GID
            # Handle special "shell" command: translate to exec -u $UID:$GID
            ARGS="{{ ARGS }}"
            if [[ "$ARGS" == shell* ]]; then
                ARGS="exec -u $UID:$GID ${ARGS#shell}"
            fi
            docker compose -f deploy/all-in-one/docker-compose.yml -f deploy/all-in-one/docker-compose.dev.yml {{ ARGS }}
            ;;
        "cloudron")
            docker compose -f deploy/cloudron/docker-compose.yml {{ ARGS }}
            ;;
        "heroku")
            docker compose -f deploy/heroku/docker-compose.yml {{ ARGS }}
            ;;
        "traefik")
            docker compose -f deploy/traefik/docker-compose.yml {{ ARGS }}
            ;;
        "nginx")
            docker compose -f deploy/nginx/recommended/docker-compose.yml {{ ARGS }}
            ;;
        "apache")
            docker compose -f deploy/apache/recommended/docker-compose.yml {{ ARGS }}
            ;;
        "local-testing")
            docker compose -f deploy/local_testing/docker-compose.local.yml {{ ARGS }}
            ;;
        *)
            echo "Run docker compose for deployment configurations"
            echo ""
            echo "Usage: just dc-deploy <name> <cmd> [args]"
            echo ""
            echo "Deployments:"
            echo "  all-in-one      - All-in-one container (production)"
            echo "  all-in-one-dev  - All-in-one container (development)"
            echo "  cloudron        - Cloudron deployment"
            echo "  heroku          - Heroku deployment"
            echo "  traefik         - Traefik reverse proxy"
            echo "  nginx           - Nginx reverse proxy"
            echo "  apache          - Apache reverse proxy"
            echo "  local-testing   - Local testing setup"
            echo ""
            echo "Examples:"
            echo "  just dc-deploy cloudron up -d"
            echo "  just dc-deploy all-in-one logs -f"
            echo "  just dc-deploy heroku build"
            [[ -n "{{ name }}" ]] && exit 1 || exit 0
            ;;
    esac

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
    @just f install

# Run all linters (backend + frontend)
lint:
    @just b lint
    @just f lint

# Run all tests (backend + frontend)
test:
    @just b test
    @just f test

# Fix all code style (backend + frontend)
fix:
    @just b fix
    @just f fix

# =============================================================================
# Full Development Environment
# =============================================================================

# Log files for dev servers (shared with logs recipe below)
backend_log_file := "/tmp/baserow-backend.log"
celery_log_file := "/tmp/baserow-celery.log"
frontend_log_file := "/tmp/baserow-web-frontend.log"

# Start full local development environment (docker services + backend + celery + frontend)
[doc("Start local dev env: docker services + backend + celery + frontend")]
start-dev-local:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Starting Baserow local development environment..."
    echo ""

    # Start docker services (redis, db, mailhog, otel-collector)
    echo "==> Starting Docker services (redis, db, mailhog, otel-collector)..."
    just dc-dev up -d redis db mailhog otel-collector

    # Wait for services to be ready
    echo "==> Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if just dc-dev exec -T db pg_isready -U baserow >/dev/null 2>&1; then
            echo "    PostgreSQL is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "    ERROR: PostgreSQL did not become ready in time"
            exit 1
        fi
        sleep 1
    done

    echo "==> Waiting for Redis to be ready..."
    for i in {1..30}; do
        if just dc-dev exec -T redis redis-cli ping >/dev/null 2>&1; then
            echo "    Redis is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "    ERROR: Redis did not become ready in time"
            exit 1
        fi
        sleep 1
    done

    # Run database migrations
    echo ""
    echo "==> Running database migrations..."
    (cd backend && just migrate)

    # Clear log files
    > "{{ backend_log_file }}"
    > "{{ celery_log_file }}"
    > "{{ frontend_log_file }}"

    echo ""
    echo "==> Starting backend dev server..."
    (cd backend && just run-dev-server) > "{{ backend_log_file }}" 2>&1 &
    BACKEND_PID=$!
    echo "    PID: $BACKEND_PID (log: {{ backend_log_file }})"

    echo "==> Starting Celery workers..."
    (cd backend && just run-dev-celery) > "{{ celery_log_file }}" 2>&1 &
    CELERY_PID=$!
    echo "    PID: $CELERY_PID (log: {{ celery_log_file }})"

    echo "==> Starting frontend dev server..."
    (cd web-frontend && just run-dev-server) > "{{ frontend_log_file }}" 2>&1 &
    FRONTEND_PID=$!
    echo "    PID: $FRONTEND_PID (log: {{ frontend_log_file }})"

    # Save PIDs for stop-dev-local
    echo "$BACKEND_PID" > /tmp/baserow-backend.pid
    echo "$CELERY_PID" > /tmp/baserow-celery.pid
    echo "$FRONTEND_PID" > /tmp/baserow-frontend.pid

    echo ""
    echo "=============================================="
    echo "Baserow local development environment started!"
    echo "=============================================="
    echo ""
    echo "Services:"
    echo "  Backend:   http://localhost:8000"
    echo "  Frontend:  http://localhost:3000"
    echo "  Mailhog:   http://localhost:8025"
    echo ""
    echo "Commands:"
    echo "  just logs                  # View all logs"
    echo "  just logs -f backend       # Follow backend logs"
    echo "  just logs -f frontend      # Follow frontend logs"
    echo "  just stop-dev-local        # Stop all services"
    echo ""

# Stop full local development environment
[doc("Stop local dev env started with start-dev-local")]
stop-dev-local:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Stopping Baserow development environment..."

    # Stop backend processes
    if [ -f /tmp/baserow-backend.pid ]; then
        PID=$(cat /tmp/baserow-backend.pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping backend (PID: $PID)..."
            kill "$PID" 2>/dev/null || true
        fi
        rm -f /tmp/baserow-backend.pid
    fi

    if [ -f /tmp/baserow-celery.pid ]; then
        PID=$(cat /tmp/baserow-celery.pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping celery (PID: $PID)..."
            kill "$PID" 2>/dev/null || true
            # Also kill child processes (celery workers)
            pkill -P "$PID" 2>/dev/null || true
        fi
        rm -f /tmp/baserow-celery.pid
    fi

    if [ -f /tmp/baserow-frontend.pid ]; then
        PID=$(cat /tmp/baserow-frontend.pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping frontend (PID: $PID)..."
            kill "$PID" 2>/dev/null || true
        fi
        rm -f /tmp/baserow-frontend.pid
    fi

    # Stop docker services
    echo "Stopping Docker services..."
    just dc-dev stop redis db mailhog otel-collector

    echo ""
    echo "Development environment stopped."

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
# E2E Tests
# =============================================================================

# Run E2E commands (delegates to e2e-tests/justfile)
# Usage: just e2e <command> [args]
# Commands: build, up, down, test, logs, run, db-dump, db-restore
[doc("E2E tests: just e2e <build|up|down|test|logs|run|db-dump>")]
e2e *ARGS:
    @just --justfile e2e-tests/justfile {{ ARGS }}

# =============================================================================
# Logs
# =============================================================================

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
        RED=$'\033[38;5;196m'; YLW=$'\033[38;5;214m'; GRN=$'\033[38;5;40m'; CYN=$'\033[38;5;51m'; RST=$'\033[0m'
        tail "${OPTS[@]}" "${FILES[@]}" | sed \
            -e "s/\(ERROR\)/${RED}\1${RST}/g" \
            -e "s/\(WARNING\)/${YLW}\1${RST}/g" \
            -e "s/\(INFO\)/${GRN}\1${RST}/g" \
            -e "s/\(DEBUG\)/${CYN}\1${RST}/g"
    else
        echo "No logs found."
        echo "If running locally, start with: just b run-dev-server"
        echo "If running in Docker, start with: just dc-dev up backend"
    fi

# =============================================================================
# Build
# =============================================================================

# Build deployment images
# Usage: just build <target> [tag]
[doc("Build image: backend, web-frontend, all-in-one, all-in-one-lite, heroku, cloudron, render, apache")]
build target="" tag="latest":
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{ target }}" in
        "backend")
            docker build -f backend/Dockerfile --target prod -t baserow/backend:{{ tag }} .
            ;;
        "web-frontend")
            docker build -f web-frontend/Dockerfile --target prod -t baserow/web-frontend:{{ tag }} .
            ;;
        "all-in-one")
            echo "Building backend (prod)..."
            docker build -f backend/Dockerfile --target prod -t baserow_backend:latest .
            echo "Building web-frontend (prod)..."
            docker build -f web-frontend/Dockerfile --target prod -t baserow_web-frontend:latest .
            echo "Building all-in-one..."
            docker build -f deploy/all-in-one/Dockerfile --target prod -t baserow/baserow:{{ tag }} .
            ;;
        "all-in-one-lite")
            echo "Building backend (prod)..."
            docker build -f backend/Dockerfile --target prod -t baserow_backend:latest .
            echo "Building web-frontend (prod)..."
            docker build -f web-frontend/Dockerfile --target prod -t baserow_web-frontend:latest .
            echo "Building all-in-one-lite (no postgres/redis)..."
            docker build -f deploy/all-in-one/Dockerfile --target prod-lite -t baserow/baserow:lite-{{ tag }} .
            ;;
        "all-in-one-dev")
            echo "Building backend (dev)..."
            docker build -f backend/Dockerfile --target dev -t baserow_backend:dev .
            echo "Building web-frontend (dev)..."
            docker build -f web-frontend/Dockerfile --target dev -t baserow_web-frontend:dev .
            echo "Building all-in-one-dev..."
            docker build -f deploy/all-in-one/Dockerfile --target dev -t baserow/baserow:dev-{{ tag }} .
            ;;
        "heroku")
            docker build -f heroku.Dockerfile -t baserow/heroku:{{ tag }} .
            ;;
        "cloudron")
            docker build -f deploy/cloudron/Dockerfile -t baserow/cloudron:{{ tag }} .
            ;;
        "render")
            docker build -f deploy/render/Dockerfile -t baserow/render:{{ tag }} .
            ;;
        "apache")
            docker build -f deploy/apache/recommended/Dockerfile -t baserow/apache:{{ tag }} deploy/apache/recommended/
            ;;
        "apache-no-caddy")
            docker build -f deploy/apache/no-caddy/Dockerfile -t baserow/apache-no-caddy:{{ tag }} deploy/apache/no-caddy/
            ;;
        *)
            echo "Build deployment images"
            echo ""
            echo "Usage: just build <target> [tag]"
            echo ""
            echo "Targets:"
            echo "  backend         - Backend API server"
            echo "  web-frontend    - Nuxt web frontend"
            echo "  all-in-one      - Single container (production)"
            echo "  all-in-one-lite - Single container without postgres/redis"
            echo "  all-in-one-dev  - Single container (development)"
            echo "  heroku          - Heroku platform"
            echo "  cloudron        - Cloudron marketplace"
            echo "  render          - Render.com platform"
            echo "  apache          - Apache reverse proxy"
            echo "  apache-no-caddy - Apache reverse proxy (no Caddy)"
            echo ""
            echo "Examples:"
            echo "  just build all-in-one           # Tags as :latest"
            echo "  just build all-in-one 2.0.0     # Tags as :2.0.0"
            echo "  just build backend"
            [[ -n "{{ target }}" ]] && exit 1 || exit 0
            ;;
    esac
    echo ""
    echo "Built: $(docker images --format '{{ '{{.Repository}}:{{.Tag}}' }}' | grep -m1 'baserow')"
