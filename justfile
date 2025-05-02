# .env.local-dev
# SECRET_KEY=baserow
# DATABASE_HOST=localhost
# DATABASE_USER=baserow
# DATABASE_PASSWORD=baserow
# REDIS_HOST=localhost
# REDIS_PASSWORD=baserow
# PYTHONPATH=backend/src/:backend/tests:premium/backend/src/:premium/backend/tests:enterprise/backend/src/:enterprise/backend/tests:$PYTHONPATH
# DJANGO_SETTINGS_MODULE=baserow.config.settings.dev
# BASEROW_BACKEND_DEBUGGER_ENABLED=true
# MEDIA_ROOT=media/
# NODE_OPTIONS="--max_old_space_size=4096"
# VENV_PATH=$HOME/.pyenv/versions/3.11.4/envs/baserow
# NODE_PATH=$HOME/.nvm/versions/node/v21.7.3/bin/node

set dotenv-load := true
set dotenv-filename := ".env.local-dev"

up-db:
    @echo "Starting PostgreSQL database..."
    @docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d redis db

_drop-db:
    @echo "Stopping and removing PostgreSQL database..."
    @docker compose -f docker-compose.yml -f docker-compose.dev.yml down --volumes

migrate:
    @echo "Running database migrations..."
    just backend migrate --noinput

wipe: _drop-db up-db migrate

run-dev-backend: up-db
    @echo "Running backend in development mode..."
    @cd backend && \
    echo "Starting backend server..." && \
    ./baserow migrate --noinput && \
    ./baserow runserver 0.0.0.0:8000

run-b: run-dev-backend

run-dev-celery:
    @echo "Running Celery worker..."
    @cd backend && \
    echo "Starting Celery worker..." && \
    watchmedo auto-restart -d src/ -d ../premium/backend/src/ -d ../enterprise/backend/src --pattern="*.py" --recursive -- python -m debugpy --listen 0.0.0.0:5679 /baserow/venv/bin/celery -A baserow worker -B -S redbeat.RedBeatScheduler -l info --pool=solo --concurrency=4 -Q celery,export

run-c: run-dev-celery

run-dev-frontend:
    @echo "Running frontend in development mode..."
    @cd web-frontend && \
    echo "Starting frontend server..." && \
    yarn install && \
    yarn run dev

run-f: run-dev-frontend

shell:
    @echo "Starting backend shell..."
    just backend shell_plus --print-sql

backend *ARGS:
    @cd backend && ./baserow {{ARGS}}

pytest *ARGS:
    @cd backend && TEST_ENV_FILE='.env.testing-local' pytest {{ARGS}}

jest *ARGS:
    @cd web-frontend && TZ=UTC yarn test


frontend-lint-fix:
    #!/usr/bin/env bash
    set -euo pipefail
    
    cd web-frontend
    
    js_files=$(git diff --name-only develop | grep -E '\.(js|jsx|ts|tsx|vue)$' | sed 's|^|../|' || true)
    css_files=$(git diff --name-only develop | grep -E '\.(css|scss)$' | sed 's|^|../|' || true)
    
    if [ -n "$js_files" ]; then
        npx prettier $js_files -w && \
        npx eslint -c .eslintrc.js --fix $js_files
    else
        echo "No JS files to lint"
    fi
    
    if [ -n "$css_files" ]; then
        npx prettier $css_files -w && \
        npx stylelint --fix $css_files
    else
        echo "No CSS files to lint"
    fi

f-fix: frontend-lint-fix

backend-lint-fix:
    #!/usr/bin/env bash
    set -euo pipefail
    
    cd backend
    py_files=$(git diff --name-only develop | grep -E '\.py$' | sed 's|^|../|' || true)
    
    # Check if there are changed Python files
    if [ -n "$py_files" ]; then
        python -m autoflake -i --remove-unused-variables --remove-all-unused-imports ${py_files}
        python -m isort --skip generated --overwrite-in-place ${py_files}      
        python -m black --config=pyproject.toml ${py_files}
    else
        echo "No Python files changed. Skipping backend linting."
    fi

b-fix: backend-lint-fix

fix: frontend-lint-fix backend-lint-fix