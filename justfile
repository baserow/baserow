# Baserow Project Justfile
# Run `just` to see all available commands organized by category

set unstable := true

# Import personal recipes if they exist (not tracked in git)
import? 'local.just'

# Default recipe - show help with groups
default:
    @just --list

# =============================================================================
# Help & Documentation
# =============================================================================

# Show getting started guide and documentation links
[group('0 - help')]
help:
    @echo "Baserow Development - Getting Started"
    @echo "======================================"
    @echo ""
    @echo "Choose your development approach:"
    @echo ""
    @echo "  Option 1: Local processes (faster hot-reload, requires local Python/Node)"
    @echo "  -------------------------------------------------------------------------"
    @echo "    just init           # First time: install dependencies"
    @echo "    just dev up         # Start all services (Ctrl+C stops everything)"
    @echo "    just dev up -d      # Start in background"
    @echo "    just dev stop       # Stop background services"
    @echo ""
    @echo "  Option 2: Docker containers (easier setup, everything containerized)"
    @echo "  ---------------------------------------------------------------------"
    @echo "    just dc-dev build --parallel   # First time: build images"
    @echo "    just dc-dev up -d              # Start all containers"
    @echo "    just dc-dev logs -f            # Follow logs"
    @echo "    just dc-dev down               # Stop containers"
    @echo ""
    @echo "Documentation:"
    @echo "  docs/development/justfile.md                        - Just command reference"
    @echo "  docs/development/running-the-dev-env-locally.md     - Local development setup"
    @echo "  docs/development/running-the-dev-env-with-docker.md - Docker development setup"
    @echo "  docs/development/running-tests.md                   - Running tests"
    @echo "  docs/development/code-quality.md                    - Linting and formatting"
    @echo ""
    @echo "Component-specific help:"
    @echo "  just b help           # Backend commands and docs"
    @echo "  just f help           # Frontend commands and docs"

# =============================================================================
# Getting Started (run these first!)
# =============================================================================

# Initialize the project (install all dependencies)
[group('1 - local-dev')]
[doc("First time setup: install backend + frontend dependencies")]
init:
    @just b init
    @just f install

# Local development environment management
[group('1 - local-dev')]
[doc("Local dev: just dev <up|up -d|stop|logs|ps|wipe>")]
dev *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail

    # Parse args from just
    ALLARGS=({{ ARGS }})
    CMD="${ALLARGS[0]:-}"
    REST=("${ALLARGS[@]:1}")

    case "$CMD" in
        wipe)
            just _dev-stop 2>/dev/null || true
            just dc-dev wipe
            if [ ${#REST[@]} -gt 0 ]; then
                just dev "${REST[@]}"
            fi
            ;;
        up|start)
            # Check for -d flag
            DETACHED=false
            for arg in "${REST[@]:-}"; do
                if [[ "$arg" == "-d" ]]; then
                    DETACHED=true
                fi
            done

            just _dev-start

            if [ "$DETACHED" = false ]; then
                # Trap Ctrl+C to stop services
                trap 'echo ""; echo "Stopping services..."; just _dev-stop; exit 0' INT
                echo ""
                echo "Following logs (Ctrl+C to stop all services)..."
                echo ""
                just dev logs -f backend celery frontend storybook
            fi
            ;;
        stop|down)
            just _dev-stop
            ;;
        logs)
            BACKEND_LOG="{{ backend_log_file }}"
            CELERY_LOG="{{ celery_log_file }}"
            FRONTEND_LOG="{{ frontend_log_file }}"
            STORYBOOK_LOG="{{ storybook_log_file }}"

            # Parse args: known service names go to SERVICES, everything else to OPTS
            OPTS=()
            SERVICES=()
            VALID_SERVICES="backend celery frontend storybook"
            for arg in ${REST[@]+"${REST[@]}"}; do
                if [[ " $VALID_SERVICES " == *" $arg "* ]]; then
                    SERVICES+=("$arg")
                else
                    OPTS+=("$arg")
                fi
            done

            # Show all services if none specified
            if [ ${#SERVICES[@]} -eq 0 ]; then
                SERVICES=(backend frontend celery storybook)
            fi

            # Map service names to log files
            FILES=()
            for svc in "${SERVICES[@]}"; do
                case "$svc" in
                    backend)   [ -f "$BACKEND_LOG" ] && FILES+=("$BACKEND_LOG") ;;
                    celery)    [ -f "$CELERY_LOG" ] && FILES+=("$CELERY_LOG") ;;
                    frontend)  [ -f "$FRONTEND_LOG" ] && FILES+=("$FRONTEND_LOG") ;;
                    storybook) [ -f "$STORYBOOK_LOG" ] && FILES+=("$STORYBOOK_LOG") ;;
                esac
            done

            if [ ${#FILES[@]} -gt 0 ]; then
                RED=$'\033[38;5;196m'; YLW=$'\033[38;5;214m'; GRN=$'\033[38;5;40m'; CYN=$'\033[38;5;51m'; RST=$'\033[0m'
                # Check if we're following logs or just viewing
                FOLLOWING=false
                for opt in "${OPTS[@]:-}"; do
                    [[ "$opt" == "-f" || "$opt" == "-F" ]] && FOLLOWING=true
                done
                # If not following and files are empty, show helpful message
                if [[ "$FOLLOWING" == "false" ]]; then
                    TOTAL_SIZE=0
                    for f in "${FILES[@]}"; do
                        SIZE=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
                        TOTAL_SIZE=$((TOTAL_SIZE + SIZE))
                    done
                    if [ "$TOTAL_SIZE" -eq 0 ]; then
                        echo "Log files exist but are empty - services may still be starting up."
                        echo "Use 'just dev logs -f' to follow logs as they appear."
                        exit 0
                    fi
                fi
                tail "${OPTS[@]}" "${FILES[@]}" | sed \
                    -e "s/\(ERROR\)/${RED}\1${RST}/g" \
                    -e "s/\(WARNING\)/${YLW}\1${RST}/g" \
                    -e "s/\(INFO\)/${GRN}\1${RST}/g" \
                    -e "s/\(DEBUG\)/${CYN}\1${RST}/g"
            else
                echo "No logs found."
                echo "Start the local dev environment first: just dev up"
            fi
            ;;
        ps)
            echo "==> Process Status"
            for name in backend celery frontend storybook; do
                pid_file="/tmp/baserow-${name}.pid"
                if [ -f "$pid_file" ]; then
                    PID=$(cat "$pid_file")
                    if kill -0 "$PID" 2>/dev/null; then
                        echo "  $name: running (PID: $PID)"
                    else
                        echo "  $name: stopped (stale PID file)"
                    fi
                else
                    echo "  $name: not running"
                fi
            done
            echo ""
            echo "==> Docker Services"
            just dc-dev ps redis db mailhog otel-collector 2>/dev/null || echo "  Not running"
            ;;
        tmux)
            just _dev-tmux
            ;;
        *)
            echo "Local development environment"
            echo ""
            echo "Usage: just dev <command>"
            echo ""
            echo "Commands:"
            echo "  up       Start and follow logs (Ctrl+C stops everything)"
            echo "  up -d    Start in background (detached)"
            echo "  stop     Stop all services"
            echo "  logs     View logs: just dev logs [-f] [backend|celery|frontend|storybook]"
            echo "  ps       Show running services"
            echo "  wipe     Delete database volume (wipe up to restart fresh)"
            echo "  tmux     Start tmux session with all services"
            echo ""
            echo "Examples:"
            echo "  just dev up              # Start and watch logs (Ctrl+C stops all)"
            echo "  just dev up -d           # Start in background"
            echo "  just dev logs -f backend # Follow backend logs"
            echo "  just dev stop            # Stop everything"
            echo "  just dev wipe up         # Wipe DB and start fresh"
            echo "  just dev tmux            # Start tmux session"
            [[ -n "$CMD" ]] && exit 1 || exit 0
            ;;
    esac

# Internal: Start local dev environment
[private]
_dev-start:
    #!/usr/bin/env bash
    set -euo pipefail

    # Create .env.local from example if it doesn't exist
    if [ ! -f .env.local ]; then
        if [ -f .env.local-dev.example ]; then
            echo "Creating .env.local from .env.local-dev.example..."
            cp .env.local-dev.example .env.local
            echo ""
        else
            echo "Warning: .env.local-dev.example not found, skipping .env.local creation"
            echo ""
        fi
    fi

    # Load environment variables from .env.local
    if [ -f .env.local ]; then
        set -a
        source .env.local
        set +a
    fi

    echo "Starting Baserow local development environment..."
    echo ""

    # Start docker services (redis, db, mailhog, otel-collector)
    echo "==> Starting Docker services (redis, db, mailhog, otel-collector)..."
    just dc-dev up -d --scale backend=0 --scale web-frontend=0 --scale celery=0 --scale celery-beat-worker=0 --scale celery-export-worker=0

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

    echo "==> Starting Storybook dev server..."
    (cd web-frontend && just storybook) > "{{ storybook_log_file }}" 2>&1 &
    STORYBOOK_PID=$!
    echo "    PID: $STORYBOOK_PID (log: {{ storybook_log_file }})"

    # Save PIDs
    echo "$BACKEND_PID" > /tmp/baserow-backend.pid
    echo "$CELERY_PID" > /tmp/baserow-celery.pid
    echo "$FRONTEND_PID" > /tmp/baserow-frontend.pid
    echo "$STORYBOOK_PID" > /tmp/baserow-storybook.pid

    echo ""
    echo "=============================================="
    echo "Baserow local development environment started!"
    echo "=============================================="
    echo ""
    echo "Services:"
    echo "  Backend:   http://localhost:8000"
    echo "  Frontend:  http://localhost:3000"
    echo "  Storybook: http://localhost:6006"
    echo "  Mailhog:   http://localhost:8025"
    echo ""
    echo "Commands:"
    echo "  just dev logs              # View logs"
    echo "  just dev logs -f backend   # Follow backend logs"
    echo "  just dev stop              # Stop all services"
    echo ""

# Internal: Stop local dev environment
[private]
_dev-stop:
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

    if [ -f /tmp/baserow-storybook.pid ]; then
        PID=$(cat /tmp/baserow-storybook.pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping storybook (PID: $PID)..."
            kill "$PID" 2>/dev/null || true
        fi
        rm -f /tmp/baserow-storybook.pid
    fi

    # Stop docker services
    echo "Stopping Docker services..."
    just dc-dev down

    echo ""
    echo "Development environment stopped."

# =============================================================================
# Local Development (native Python/Node - faster, requires local setup)
# =============================================================================

# Start tmux dev session with all services (local processes)
[private]
_dev-tmux:
    #!/usr/bin/env bash
    set -euo pipefail

    SESSION="baserow-dev"
    ROOT="$(pwd)"

    # Helper: create window
    create_window() {
        local name=$1
        local dir=$2
        local run_cmd=${3:-}
        local run_cmd_2=${4:-}

        tmux new-window -t $SESSION -n "$name" -c "$dir"
        tmux split-window -h -t "$SESSION:$name" -c "$dir"
        if [ -n "$run_cmd" ]; then
            tmux send-keys -t "$SESSION:$name.left" "$run_cmd" Enter
        fi
        tmux select-pane -t "$SESSION:$name.right"
        if [ -n "$run_cmd_2" ]; then
            tmux send-keys -t "$SESSION:$name.right" "$run_cmd_2" Enter
        fi
    }

    just dc-dev up -d redis db mailhog otel-collector
    # Kill any existing session
    if tmux has-session -t $SESSION 2>/dev/null; then
        tmux kill-session -t $SESSION
    fi

    # Create session with a temporary window (will be closed after creating real windows)
    tmux new-session -d -s $SESSION -n _tmp -c "$ROOT"

    create_window "backend"   "$ROOT/backend"       "just run-dev-server"
    create_window "frontend"  "$ROOT/web-frontend"  "just run-dev-server"
    create_window "storybook" "$ROOT/web-frontend"  "just storybook"
    create_window "celery"    "$ROOT/backend"       "just run-dev-celery"
    create_window "db"        "$ROOT"               "just dc-dev logs -f db"       "PGPASSWORD=${DATABASE_PASSWORD:-baserow} just dc-dev exec db psql -U ${DATABASE_USER:-baserow} -d ${DATABASE_NAME:-baserow}"
    create_window "redis"     "$ROOT"               "just dc-dev logs -f redis"    "just dc-dev exec redis redis-cli -a ${REDIS_PASSWORD:-baserow}"

    # Kill the temporary window
    tmux kill-window -t $SESSION:_tmp

    # Select backend window and attach
    tmux select-window -t $SESSION:backend
    tmux attach-session -t $SESSION

# Run any backend command (e.g., just b init, just b test, just b lint)
[group('1 - local-dev')]
[doc("Run backend command: just b <cmd> (e.g., b test, b lint, b shell)")]
backend *args:
    @just --justfile backend/justfile --working-directory backend {{ args }}

# Shortcut alias for backend
alias b := backend

# Run any web-frontend command (e.g., just f lint, just f test)
[group('1 - local-dev')]
[doc("Run frontend command: just f <cmd> (e.g., f lint, f test)")]
frontend *args:
    @just --justfile web-frontend/justfile --working-directory web-frontend {{ args }}

# Shortcut alias for frontend
alias f := frontend

# Run all linters (backend + frontend)
[group('1 - local-dev')]
[doc("Lint all code (backend + frontend)")]
lint:
    @just b lint
    @just f lint

# Run all tests (backend + frontend)
[group('1 - local-dev')]
[doc("Test all code (backend + frontend)")]
test:
    @just b test
    @just f test

# Fix all code style (backend + frontend)
[group('1 - local-dev')]
[doc("Auto-fix code style (backend + frontend)")]
fix:
    @just b fix
    @just f fix

# Log files for dev servers
backend_log_file := "/tmp/baserow-backend.log"
celery_log_file := "/tmp/baserow-celery.log"
frontend_log_file := "/tmp/baserow-web-frontend.log"
storybook_log_file := "/tmp/baserow-storybook.log"

# =============================================================================
# Docker Development (everything runs in containers - easier setup)
# =============================================================================

_dc_help:
    @echo "Usage: just dc-prod <cmd> [args]  (production - uses published images)"
    @echo "       just dc-dev <cmd> [args]   (development - builds dev images)"
    @echo ""
    @echo "Examples:"
    @echo "  just dc-dev tabs                 # Open terminal tabs for each service (like dev.sh). Alias: just dct"
    @echo "  just dc-dev up -d                # Start containers (detached)"
    @echo "  just dc-dev up -d backend db     # Start specific services"
    @echo "  just dc-dev tmux                 # Start tmux session with all services"
    @echo "  just dc-dev stop                 # Stop containers (keep volumes)"
    @echo "  just dc-dev down                 # Stop and remove containers"
    @echo "  just dc-dev build --parallel     # Build all dev images"
    @echo "  just dc-dev build backend        # Build specific service"
    @echo "  just dc-dev logs -f backend      # Follow logs for a service"
    @echo "  just dc-dev exec backend bash    # Open shell in container"
    @echo "  just dc-dev ps                   # Show running containers"
    @echo ""
    @echo "Optional services (storybook, flower):"
    @echo "  Started by default via COMPOSE_PROFILES=optional in .env.docker-dev"
    @echo "  To disable: set COMPOSE_PROFILES= (empty) in .env.docker-dev"
    @echo ""
    @echo "Production (builds locally if BASEROW_VERSION is unset/latest):"
    @echo "  just dc-prod up -d                          # Build and run latest locally"
    @echo "  just dc-prod build --parallel               # Build latest images"
    @echo "  BASEROW_VERSION=1.29.0 just dc-prod up -d   # Pull and run v1.29.0 from registry"
    @echo ""
    @echo "Troubleshooting:"
    @echo "  just dc-cache-clear                  # Clear build cache if builds fail"
    @echo "  just dc-fix-network                  # Fix 'network not found' errors"

# Dev compose (includes docker-compose.dev.yml overlay)
[group('2 - docker-dev')]
[doc("Docker compose (dev): just dc-dev <build|up|down|logs|exec|ps|wipe>")]
dc-dev *ARGS:
    #!/usr/bin/env bash
    if [ -z "{{ ARGS }}" ]; then
        just _dc_help
    else
        if [ ! -f .env.docker-dev ] && [ -f .env.docker-dev.example ]; then
            echo "Creating .env.docker-dev from .env.docker-dev.example..."
            cp .env.docker-dev.example .env.docker-dev
        fi
        # Export UID/GID for docker-compose user: directive
        if [[ -z "$UID" ]]; then
            UID=$(id -u)
        fi
        export UID
        if [[ -z "$GID" ]]; then
            GID=$(id -g)
        fi
        export GID

        # Docker needs node_modules folder to exists to mount the volume inside a bind mount.
        # Let's ensure it exists before starting anything.
        if [ ! -d web-frontend/node_modules ]; then
            mkdir -p web-frontend/node_modules
        fi

        DC="docker compose --env-file .env.docker-dev -f docker-compose.yml -f docker-compose.dev.yml"
        ALLARGS=({{ ARGS }})
        CMD="${ALLARGS[0]:-}"

        REST=("${ALLARGS[@]:1}")

        case "$CMD" in
            wipe)
                echo "Wiping dev environment (down -v)..."
                $DC down -v
                if [ ${#REST[@]} -gt 0 ]; then
                    $DC "${REST[@]}"
                fi
                ;;
            tmux)
                just _dc-dev-tmux
                ;;
            tabs)
                just _dc-dev-tabs "${REST[@]}"
                ;;
            *)
                $DC {{ ARGS }}
                ;;
        esac
    fi

alias dcd := dc-dev

# Start tmux dev session with all services (Docker Compose)
[private]
_dc-dev-tmux:
    #!/usr/bin/env bash
    set -euo pipefail

    SESSION="baserow-dc-dev"
    ROOT="$(pwd)"

    # Helper: create window if it doesn't exist
    create_window() {
        local name=$1
        local shell_cmd=$2
        local log_cmd=$3

        tmux new-window -t $SESSION -n "$name" -c "$ROOT"
        tmux split-window -h -t "$SESSION:$name" -c "$ROOT"
        tmux send-keys -t "$SESSION:$name.left" "$shell_cmd" Enter
        tmux send-keys -t "$SESSION:$name.right" "$log_cmd" Enter
        tmux select-pane -t "$SESSION:$name.left"
    }

    # Start services if not running
    if ! docker ps --format '{{ '{{.Names}}' }}' | grep -q "^baserow.*db"; then
        just dc-dev up -d
    fi
    # Kill any existing session
    if tmux has-session -t $SESSION 2>/dev/null; then
        tmux kill-session -t $SESSION
    fi

    # Create session with a temporary window (will be closed after creating real windows)
    tmux new-session -d -s $SESSION -n _tmp -c "$ROOT"

    create_window "backend"  "just dc-dev exec backend bash"  "just dc-dev logs -f backend"
    create_window "frontend" "just dc-dev exec web-frontend bash" "just dc-dev logs -f web-frontend"
    create_window "celery"   "just dc-dev exec celery bash" "just dc-dev logs -f celery celery-beat-worker celery-export-worker"
    create_window "db"       "just dc-dev exec db psql -U baserow" "just dc-dev logs -f db"
    create_window "redis"    "just dc-dev exec redis redis-cli"   "just dc-dev logs -f redis"

    # Kill the temporary window
    tmux kill-window -t $SESSION:_tmp

    # Select backend window and attach
    tmux select-window -t $SESSION:backend
    tmux attach-session -t $SESSION

# Start dev environment with terminal tabs (like dev.sh)
[private]
_dc-dev-tabs *ARGS:
    #!/usr/bin/env bash
    set -eo pipefail

    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    NC=$(tput sgr0) # No Color

    print_manual_instructions(){
      COMMAND=$1
      echo -e "\nTo inspect the now running dev environment open a new tab/terminal and run:"
      echo "    $COMMAND"
    }

    PRINT_WARNING=true
    new_tab() {
      TAB_NAME=$1
      COMMAND=$2
      echo "Attempting to open tab with command $GREEN$COMMAND$NC"

      if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -x "$(command -v gnome-terminal)" ]; then
          gnome-terminal \
          --tab --title="$TAB_NAME" --working-directory="$(pwd)" -- /bin/bash -c "$COMMAND"
        elif [ -x "$(command -v konsole)" ]; then
          ktab=$(qdbus $KONSOLE_DBUS_SERVICE $KONSOLE_DBUS_WINDOW newSession)
          qdbus $KONSOLE_DBUS_SERVICE /Sessions/$(($ktab)) setTitle 1 "$TAB_NAME"
          qdbus $KONSOLE_DBUS_SERVICE /Sessions/$(($ktab)) runCommand "cd $(pwd); $COMMAND"
          qdbus $KONSOLE_DBUS_SERVICE $KONSOLE_DBUS_WINDOW prevSession
        else
          if $PRINT_WARNING; then
              echo -e "\n${YELLOW}WARNING${NC}: gnome-terminal is the only currently supported way of opening
              multiple tabs/terminals for linux by this script, add support for your setup!"
              PRINT_WARNING=false
          fi
          print_manual_instructions "$COMMAND"
        fi
      elif [[ "$OSTYPE" == "darwin"* ]]; then
        osascript \
            -e "tell application \"Terminal\"" \
            -e "tell application \"System Events\" to keystroke \"t\" using {command down}" \
            -e "do script \"printf '\\\e]1;$TAB_NAME\\\a'; $COMMAND\" in front window" \
            -e "end tell" > /dev/null
      else
        if $PRINT_WARNING; then
            echo -e "\n${YELLOW}WARNING${NC}: The OS '$OSTYPE' is not supported yet for creating tabs to setup
            baserow's dev environment, please add support!"
            PRINT_WARNING=false
        fi
        print_manual_instructions "$COMMAND"
      fi
    }

    launch_tab_and_attach(){
      tab_name=$1
      service_name=$2
      container_name=$(docker inspect -f '{{ '{{.Name}}' }}' "$(just dc-dev ps -q "$service_name")" | cut -c2-)
      command="docker logs $container_name && docker attach $container_name"
      if [[ $(docker inspect "$container_name" --format='{{ '{{.State.ExitCode}}' }}') -eq 0 ]]; then
        new_tab "$tab_name" "$command"
      else
        echo -e "\n${RED}$service_name crashed on launch!${NC}"
        docker logs "$container_name"
        echo -e "\n${RED}$service_name crashed on launch, see above for logs!${NC}"
      fi
    }

    launch_tab_and_exec(){
      tab_name=$1
      service_name=$2
      exec_command=$3
      container_name=$(docker inspect -f '{{ '{{.Name}}' }}' "$(just dc-dev ps -q "$service_name")" | cut -c2-)
      command="docker exec -it $container_name $exec_command"
      new_tab "$tab_name" "$command"
    }

    # Start services using dc-dev recipe
    just dc-dev up -d {{ ARGS }}

    # Open tabs for main services
    launch_tab_and_attach "backend" "backend"
    launch_tab_and_attach "web frontend" "web-frontend"
    launch_tab_and_attach "celery" "celery"
    launch_tab_and_attach "export worker" "celery-export-worker"
    launch_tab_and_attach "beat worker" "celery-beat-worker"

    # Open lint tabs
    launch_tab_and_exec "web frontend lint" \
            "web-frontend" \
            "/bin/bash /baserow/web-frontend/docker/docker-entrypoint.sh lint-fix"
    launch_tab_and_exec "backend lint" \
            "backend" \
            "/bin/bash /baserow/backend/docker/docker-entrypoint.sh lint-shell"

# Shortcut for dc-dev tabs
[private]
dct *ARGS:
    @just dc-dev tabs {{ ARGS }}

# Attach to a running container (interactive shell)
[group('2 - docker-dev')]
[doc("Attach to running container: just dc-attach [filter]")]
dc-attach container="":
    #!/usr/bin/env bash
    set -euo pipefail

    # Colors
    CYAN='\033[0;36m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    DIM='\033[2m'
    BOLD='\033[1m'
    NC='\033[0m' # No Color

    # Get running containers, optionally filtered by name
    if [ -n "{{ container }}" ]; then
        mapfile -t containers < <(docker ps --format '{{ '{{.Names}}\t{{.Image}}\t{{.Status}}' }}' | grep -i "{{ container }}" || true)
    else
        mapfile -t containers < <(docker ps --format '{{ '{{.Names}}\t{{.Image}}\t{{.Status}}' }}')
    fi

    if [ ${#containers[@]} -eq 0 ]; then
        if [ -n "{{ container }}" ]; then
            echo -e "${YELLOW}No running containers matching '{{ container }}'.${NC}"
        else
            echo -e "${YELLOW}No running containers found.${NC}"
        fi
        exit 1
    fi

    # If only one container, attach immediately
    if [ ${#containers[@]} -eq 1 ]; then
        name=$(echo "${containers[0]}" | cut -f1)
        echo -e "Attaching to ${GREEN}${name}${NC}..."
        docker exec -it "$name" bash
        exit 0
    fi

    # Multiple containers - show selection menu
    echo -e "${BOLD}Running containers:${NC}"
    echo ""
    for i in "${!containers[@]}"; do
        name=$(echo "${containers[$i]}" | cut -f1)
        image=$(echo "${containers[$i]}" | cut -f2)
        status=$(echo "${containers[$i]}" | cut -f3)
        printf "  ${CYAN}%2d)${NC} ${GREEN}%-30s${NC} ${DIM}%-40s${NC} ${YELLOW}%s${NC}\n" "$((i+1))" "$name" "$image" "$status"
    done
    echo ""
    echo -e "  ${DIM}q)  Quit${NC}"
    echo ""

    # Read single character without waiting for Enter
    printf "Select container [1-${#containers[@]}]: "
    read -rsn1 choice

    # Handle ESC (reads as empty with -s, or as escape sequence)
    if [[ "$choice" == $'\x1b' || -z "$choice" ]]; then
        echo ""
        exit 0
    fi

    # Handle quit
    if [[ "$choice" == "q" || "$choice" == "Q" ]]; then
        echo "$choice"
        exit 0
    fi

    # For numbers, check if valid single digit selection
    if [[ "$choice" =~ ^[0-9]$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le ${#containers[@]} ]; then
        echo "$choice"
        name=$(echo "${containers[$((choice-1))]}" | cut -f1)
        docker exec -it "$name" bash
    else
        echo "$choice"
        echo -e "${YELLOW}Invalid selection${NC}"
        exit 1
    fi

# Shortcut alias for dc-attach
alias a := dc-attach

# Clear Docker BuildKit cache
# WARNING: This clears ALL Docker builder cache, not just Baserow!
[group('2 - docker-dev')]
[doc("Clear ALL Docker builder cache (not just Baserow)")]
dc-cache-clear:
    @echo "WARNING: This will clear ALL Docker builder cache, not just Baserow."
    @echo "This affects all projects on your system."
    @echo ""
    docker builder prune -a -f

alias prune := dc-cache-clear

# Fix Docker network issues (removes containers referencing missing networks)
[group('2 - docker-dev')]
[doc("Fix 'network not found' errors")]
dc-fix-network:
    #!/usr/bin/env bash
    echo "Stopping and removing Baserow containers with stale network references..."
    docker compose -f docker-compose.yml -f docker-compose.dev.yml down --remove-orphans 2>/dev/null || true
    # Remove any containers still referencing the old network
    docker ps -aq --filter "name=baserow" | xargs -r docker rm -f 2>/dev/null || true
    echo ""
    echo "Done. You can now run: just dc-dev up -d"

# =============================================================================
# Production Images (build & test production Docker images)
# =============================================================================

# Production compose (builds locally if BASEROW_VERSION is unset/latest, otherwise pulls images)
[group('3 - production')]
[doc("Docker compose (production images): just dc-prod <build|up|down|logs>")]
dc-prod *ARGS:
    #!/usr/bin/env bash
    if [ -z "{{ ARGS }}" ]; then
        just _dc_help
    else
        VERSION="${BASEROW_VERSION:-latest}"
        if [ "$VERSION" = "latest" ] || [ -z "$BASEROW_VERSION" ]; then
            # Build locally for latest/unset
            BASEROW_VERSION="$VERSION" docker compose -f docker-compose.yml -f docker-compose.build.yml {{ ARGS }}
        else
            # Pull from registry for specific versions
            BASEROW_VERSION="$VERSION" docker compose -f docker-compose.yml {{ ARGS }}
        fi
    fi

alias dcp := dc-prod

# Build deployment images
[group('3 - production')]
[doc("Build image: backend, web-frontend, all-in-one, heroku, cloudron, etc.")]
build target="" tag="latest" *ARGS:
    #!/usr/bin/env bash
    set -eo pipefail

    # Parse args - check for --multi flag
    MULTI=false
    BUILD_ARGS=()
    for arg in {{ ARGS }}; do
        if [[ "$arg" == "--multi" ]]; then
            MULTI=true
        else
            BUILD_ARGS+=("$arg")
        fi
    done

    # Set up build command
    if [[ "$MULTI" == "true" ]]; then
        echo "Multi-platform build enabled (linux/amd64, linux/arm64)"
        # Ensure buildx builder exists
        if ! docker buildx inspect baserow-multiarch >/dev/null 2>&1; then
            echo "Creating buildx builder 'baserow-multiarch'..."
            docker buildx create --name baserow-multiarch --use
        else
            docker buildx use baserow-multiarch
        fi
        BUILD_CMD="docker buildx build --platform linux/amd64,linux/arm64"
        # Check if --push or --output is specified, warn if not
        if [[ ! " ${BUILD_ARGS[*]} " =~ " --push " ]] && [[ ! " ${BUILD_ARGS[*]} " =~ " --output " ]]; then
            echo ""
            echo "WARNING: Multi-platform builds require --push or --output to export."
            echo "         Add --push to push to registry, or --output type=tar,dest=image.tar"
            echo ""
        fi
    else
        BUILD_CMD="docker build"
    fi

    case "{{ target }}" in
        "backend")
            TARGET_ARG=""
            UID_GID_ARGS=""
            NAME_ARG=""
            if [[ "{{ tag }}" == "ci" || "{{ tag }}" == "dev" || "{{ tag }}" == "prod" || "{{ tag }}" == "local" ]]; then
                TARGET_ARG="--target={{ tag }}"
            fi
            if [[ "{{ tag }}" == "dev" ]]; then
                UID_GID_ARGS="--build-arg UID=$(id -u) --build-arg GID=$(id -g)"
            fi
            NAME_ARG="baserow/backend:{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" $UID_GID_ARGS -f backend/Dockerfile $TARGET_ARG -t $NAME_ARG .
            ;;
        "web-frontend")
            TARGET_ARG=""
            UID_GID_ARGS=""
            if [[ "{{ tag }}" == "ci" || "{{ tag }}" == "dev" || "{{ tag }}" == "prod" || "{{ tag }}" == "local" || "{{ tag }}" == "local-base" ]]; then
                TARGET_ARG="--target={{ tag }}"
            fi
            if [[ "{{ tag }}" == "dev" ]]; then
                UID_GID_ARGS="--build-arg UID=$(id -u) --build-arg GID=$(id -g)"
            fi
            NAME_ARG="baserow/web-frontend:{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" $UID_GID_ARGS -f web-frontend/Dockerfile $TARGET_ARG -t $NAME_ARG .
            ;;
        "all-in-one")
            echo "Building backend (prod)..."
            $BUILD_CMD "${BUILD_ARGS[@]}" -f backend/Dockerfile --target prod -t baserow/backend:{{ tag }} .
            BUILD_ARGS+=("--build-arg" "BACKEND_IMAGE=baserow/backend:{{ tag }}")
            echo "Building web-frontend (prod)..."
            $BUILD_CMD "${BUILD_ARGS[@]}" -f web-frontend/Dockerfile --target prod -t baserow/web-frontend:{{ tag }} .
            BUILD_ARGS+=("--build-arg" "WEB_FRONTEND_IMAGE=baserow/web-frontend:{{ tag }}")
            echo "Building all-in-one..."
            NAME_ARG="baserow/baserow:{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" -f deploy/all-in-one/Dockerfile --target prod -t $NAME_ARG .
            ;;
        "all-in-one-lite")
            echo "Building backend (prod)..."
            $BUILD_CMD "${BUILD_ARGS[@]}" -f backend/Dockerfile --target prod -t baserow/backend:{{ tag }} .
            BUILD_ARGS+=("--build-arg" "BACKEND_IMAGE=baserow/backend:{{ tag }}")
            echo "Building web-frontend (prod)..."
            $BUILD_CMD "${BUILD_ARGS[@]}" -f web-frontend/Dockerfile --target prod -t baserow/web-frontend:{{ tag }} .
            BUILD_ARGS+=("--build-arg" "WEB_FRONTEND_IMAGE=baserow/web-frontend:{{ tag }}")
            echo "Building all-in-one-lite (no postgres/redis)..."
            NAME_ARG="baserow/baserow:lite-{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" -f deploy/all-in-one/Dockerfile --target prod-lite -t $NAME_ARG .
            ;;
        "heroku")
            NAME_ARG="baserow/heroku:{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" -f heroku.Dockerfile -t $NAME_ARG .
            ;;
        "cloudron")
            NAME_ARG="baserow/cloudron:{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" -f deploy/cloudron/Dockerfile -t $NAME_ARG .
            ;;
        "render")
            NAME_ARG="baserow/render:{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" -f deploy/render/Dockerfile -t $NAME_ARG .
            ;;
        "apache")
            NAME_ARG="baserow/apache:{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" -f deploy/apache/recommended/Dockerfile -t  $NAME_ARG deploy/apache/recommended/
            ;;
        "apache-no-caddy")
            NAME_ARG="baserow/apache-no-caddy:{{ tag }}"
            $BUILD_CMD "${BUILD_ARGS[@]}" -f deploy/apache/no-caddy/Dockerfile -t $NAME_ARG deploy/apache/no-caddy/
            ;;
        *)
            echo "Build deployment images"
            echo ""
            echo "Usage: just build <target> [tag] [--multi] [docker-args]"
            echo ""
            echo "Targets:"
            echo "  backend         - Backend API server"
            echo "  web-frontend    - Nuxt web frontend"
            echo "  all-in-one      - Single container (production)"
            echo "  all-in-one-lite - Single container without postgres/redis"
            echo "  heroku          - Heroku platform"
            echo "  cloudron        - Cloudron marketplace"
            echo "  render          - Render.com platform"
            echo "  apache          - Apache reverse proxy"
            echo "  apache-no-caddy - Apache reverse proxy (no Caddy)"
            echo ""
            echo "Options:"
            echo "  --multi         - Build for linux/amd64 and linux/arm64 (requires --push or --output)"
            echo ""
            echo "Examples:"
            echo "  just build all-in-one                        # Local build, current platform"
            echo "  just build all-in-one 2.0.0                  # Tag as :2.0.0"
            echo "  just build all-in-one latest --multi --push  # Multi-platform, push to registry"
            echo "  just build backend"
            [[ -n "{{ target }}" ]] && exit 1 || exit 0
            ;;
    esac
    echo ""
    if [[ "$MULTI" != "true" ]]; then
        echo "Built: $NAME_ARG"
    else
        echo "Multi-platform build complete."
    fi

# Run docker compose for specific deployment configurations
[group('3 - production')]
[doc("Docker compose for different deployments methods (all-in-one, heroku, etc.): just dc-deploy <name> <cmd>")]
dc-deploy name="" *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail

    case "{{ name }}" in
        "all-in-one")
            docker compose -f deploy/all-in-one/docker-compose.yml {{ ARGS }}
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
# Testing (fast test database, E2E tests)
# =============================================================================

# Test DB settings
test_db_name := "baserow-test-db"
test_db_port := env("TEST_DB_PORT", "5431")
test_db_image := "pgvector/pgvector:pg${POSTGRES_IMAGE_VERSION:-14}"

# Ramdisk PostgreSQL for fast tests (2-5x faster)
[group('4 - testing')]
[doc("Manage a ramdisk database container for faster backend tests: just test-db <up|down|ps>")]
test-db cmd="":
    #!/usr/bin/env bash
    case "{{ cmd }}" in
        up|start)
            just _test-db-start
            ;;
        down|stop)
            just _test-db-stop
            ;;
        ps)
            just _test-db-ps
            ;;
        *)
            echo "Ramdisk PostgreSQL for fast tests (2-5x faster)"
            echo ""
            echo "Usage: just test-db <command>"
            echo ""
            echo "Commands:"
            echo "  up, start    Start test database on port {{ test_db_port }}"
            echo "  down, stop   Stop and remove test database"
            echo "  ps       Check if test database is running"
            echo ""
            echo "Example:"
            echo "  just test-db up"
            echo "  DATABASE_URL=postgres://baserow:baserow@localhost:{{ test_db_port }}/baserow just b test -n=auto"
            echo "  just test-db down"
            ;;
    esac

[private]
_test-db-start:
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

[private]
_test-db-stop:
    docker rm -f {{ test_db_name }} 2>/dev/null || true

[private]
_test-db-ps:
    #!/usr/bin/env bash
    if docker ps --format '{{ '{{.Names}}' }}' | grep -q "^{{ test_db_name }}$"; then
        echo "Test database is running on port {{ test_db_port }}"
        echo ""
        echo "DATABASE_URL=postgres://baserow:baserow@localhost:{{ test_db_port }}/baserow"
    elif docker ps -a --format '{{ '{{.Names}}' }}' | grep -q "^{{ test_db_name }}$"; then
        echo "Test database exists but is stopped"
        echo "Run 'just test-db up' to start it"
    else
        echo "Test database is not running"
        echo "Run 'just test-db up' to start it"
    fi

# Run E2E commands (delegates to e2e-tests/justfile)
[group('4 - testing')]
[doc("E2E tests: just e2e <build|up|down|test|logs|run|db-dump>")]
e2e *ARGS:
    @just --justfile e2e-tests/justfile {{ ARGS }}

# =============================================================================
# Environment & Utilities
# =============================================================================

# Print command to load .env.local (use with: eval "$(just env-load)")
[group('5 - utilities')]
[doc("Print command to load .env.local: eval \"$(just env-load)\"")]
env-load:
    @echo 'set -a; source "'"$PWD"'/.env.local"; set +a'

# Print command to unset all vars from .env.local (use with: eval "$(just env-clear)")
[group('5 - utilities')]
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
# CI Docker Image Testing
# =============================================================================

# CI image names
ci_backend_image := "baserow_backend:ci"
ci_frontend_image := "baserow_frontend:ci"

# CI Docker commands: build, lint, test, run (full pipeline)
# Usage:
#   just ci build                # Build both CI images
#   just ci build backend        # Build backend CI image only
#   just ci build frontend       # Build frontend CI image only
#   just ci lint                 # Lint both
#   just ci lint backend         # Lint backend only
#   just ci test                 # Test both
#   just ci test frontend        # Test frontend only
#   just ci run                  # Full pipeline for both
#   just ci run backend          # Full pipeline for backend only
[group('6 - ci')]
[doc("CI Docker: just ci <build|lint|test|run> [backend|frontend]")]
ci cmd="" target="":
    #!/usr/bin/env bash
    set -euo pipefail

    # Helper: should we run for backend?
    run_backend() {
        [[ -z "{{ target }}" || "{{ target }}" == "backend" || "{{ target }}" == "b" ]]
    }

    # Helper: should we run for frontend?
    run_frontend() {
        [[ -z "{{ target }}" || "{{ target }}" == "frontend" || "{{ target }}" == "f" ]]
    }

    # Build backend CI image
    build_backend() {
        echo "Building backend CI image..."
        docker build -t {{ ci_backend_image }} -f backend/Dockerfile --target ci .
        echo "Backend CI image built: {{ ci_backend_image }}"
    }

    # Build frontend CI image
    build_frontend() {
        echo "Building frontend CI image..."
        docker build -t {{ ci_frontend_image }} -f web-frontend/Dockerfile --target ci .
        echo "Frontend CI image built: {{ ci_frontend_image }}"
    }

    # Lint backend
    lint_backend() {
        build_backend
        echo "Running lint in backend CI image..."
        docker run --rm {{ ci_backend_image }} lint
    }

    # Lint frontend
    lint_frontend() {
        build_frontend
        echo "Running lint in frontend CI image..."
        docker run --rm {{ ci_frontend_image }} lint
    }

    # Test backend (needs postgres + redis)
    test_backend() {
        build_backend

        # Create a temporary network for the test
        NETWORK="baserow-ci-test-$$"

        # Clean up any leftover containers from previous runs
        docker rm -f ci-test-db ci-test-redis 2>/dev/null || true

        cleanup() {
            echo "Cleaning up..."
            docker rm -f ci-test-db ci-test-redis 2>/dev/null || true
            docker network rm "$NETWORK" 2>/dev/null || true
        }
        trap cleanup EXIT

        echo "Creating test network..."
        docker network create "$NETWORK" 2>/dev/null || true

        echo "Starting PostgreSQL..."
        docker run -d --name ci-test-db --network "$NETWORK" \
            -e POSTGRES_USER=baserow \
            -e POSTGRES_PASSWORD=baserow \
            -e POSTGRES_DB=baserow \
            ${test_db_image}

        echo "Starting Redis..."
        docker run -d --name ci-test-redis --network "$NETWORK" \
            redis:7 redis-server --requirepass baserow

        # Wait for postgres to be ready
        echo "Waiting for PostgreSQL to be ready..."
        for i in {1..30}; do
            if docker exec ci-test-db pg_isready -U baserow > /dev/null 2>&1; then
                echo "PostgreSQL is ready!"
                break
            fi
            if [ $i -eq 30 ]; then
                echo "PostgreSQL failed to start"
                exit 1
            fi
            sleep 1
        done

        # Wait for redis to be ready
        echo "Waiting for Redis to be ready..."
        for i in {1..30}; do
            if docker exec ci-test-redis redis-cli -a baserow ping 2>/dev/null | grep -q PONG; then
                echo "Redis is ready!"
                break
            fi
            if [ $i -eq 30 ]; then
                echo "Redis failed to start"
                exit 1
            fi
            sleep 1
        done

        # Run tests
        echo "Running tests in backend CI image..."
        docker run --rm --network "$NETWORK" \
            -e DATABASE_HOST=ci-test-db \
            -e DATABASE_PORT=5432 \
            -e DATABASE_NAME=baserow \
            -e DATABASE_USER=baserow \
            -e DATABASE_PASSWORD=baserow \
            -e REDIS_HOST=ci-test-redis \
            -e REDIS_PORT=6379 \
            -e REDIS_PASSWORD=baserow \
            -e PYTEST_SPLITS=1 \
            -e PYTEST_SPLIT_GROUP=1 \
            {{ ci_backend_image }} ci-test
    }

    # Test frontend (no external services needed)
    test_frontend() {
        build_frontend
        echo "Running tests in frontend CI image..."
        docker run --rm {{ ci_frontend_image }} ci-test
    }

    # Full pipeline for backend
    run_backend_pipeline() {
        echo "=== Running backend CI pipeline ==="
        echo ""
        echo "Step 1/2: Lint"
        lint_backend
        echo ""
        echo "Step 2/2: Tests"
        test_backend
        echo ""
        echo "=== Backend CI pipeline completed successfully ==="
    }

    # Full pipeline for frontend
    run_frontend_pipeline() {
        echo "=== Running frontend CI pipeline ==="
        echo ""
        echo "Step 1/2: Lint"
        lint_frontend
        echo ""
        echo "Step 2/2: Tests"
        test_frontend
        echo ""
        echo "=== Frontend CI pipeline completed successfully ==="
    }

    case "{{ cmd }}" in
        build)
            if run_backend; then build_backend; fi
            if run_frontend; then build_frontend; fi
            ;;
        lint)
            if run_backend; then lint_backend; fi
            if run_frontend; then lint_frontend; fi
            ;;
        test)
            if run_backend; then test_backend; fi
            if run_frontend; then test_frontend; fi
            ;;
        run)
            if run_backend; then run_backend_pipeline; fi
            if run_frontend; then run_frontend_pipeline; fi
            ;;
        *)
            echo "CI Docker commands for testing in containers"
            echo ""
            echo "Usage: just ci <command> [target]"
            echo ""
            echo "Commands:"
            echo "  build        Build CI Docker image(s)"
            echo "  lint         Build and run lint checks"
            echo "  test         Build and run tests"
            echo "  run          Run full CI pipeline (build + lint + test)"
            echo ""
            echo "Targets (optional, defaults to both):"
            echo "  backend, b   Backend only"
            echo "  frontend, f  Frontend only"
            echo ""
            echo "Examples:"
            echo "  just ci build              # Build both CI images"
            echo "  just ci build backend      # Build backend CI image only"
            echo "  just ci lint frontend      # Lint frontend only"
            echo "  just ci test               # Test both"
            echo "  just ci run backend        # Full pipeline for backend"
            [[ -n "{{ cmd }}" ]] && exit 1 || exit 0
            ;;
    esac
