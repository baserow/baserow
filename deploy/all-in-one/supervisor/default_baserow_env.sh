#!/usr/bin/env bash

# Sets up all of the environment variables used by Baserow all in one with defaults
# or what the user has provided.

set -euo pipefail

export DOCKER_USER=${DOCKER_USER:-baserow_docker_user}
export DATA_DIR=${DATA_DIR:-/baserow/data}
export BASEROW_PLUGIN_DIR=${BASEROW_PLUGIN_DIR:-$DATA_DIR/plugins}

export BASEROW_AMOUNT_OF_WORKERS=${BASEROW_AMOUNT_OF_WORKERS:-1}
export BASEROW_AMOUNT_OF_GUNICORN_WORKERS=${BASEROW_AMOUNT_OF_GUNICORN_WORKERS:-3}

export BASEROW_ENABLE_SECURE_PROXY_SSL_HEADER=${BASEROW_ENABLE_SECURE_PROXY_SSL_HEADER:-}

export PYTHONUNBUFFERED=1
export PYTHONPATH="${PYTHONPATH:-}:/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src"
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export TMPDIR=${TMPDIR:-/dev/shm}

export DATABASE_PASSWORD="${DATABASE_PASSWORD:-}"
export DATABASE_NAME="${DATABASE_NAME:-baserow}"
export DATABASE_USER="${DATABASE_USER:-baserow}"
export DATABASE_HOST="${DATABASE_HOST:-embed}"
export DATABASE_PORT="${DATABASE_PORT:-5432}"
export PGDATA="$DATA_DIR/postgres/"
export EXTRA_POSTGRES_ARGS="${EXTRA_POSTGRES_ARGS:-}"
export DISABLE_EMBEDDED_PSQL="${DISABLE_EMBEDDED_PSQL:-}"
export BASEROW_RUN_MINIMAL="${BASEROW_RUN_MINIMAL:-}"

export REDIS_HOST="${REDIS_HOST:-embed}"

export BASEROW_PUBLIC_URL="${BASEROW_PUBLIC_URL:-http://localhost}"
export BASEROW_CADDY_ADDRESSES="${BASEROW_CADDY_ADDRESSES:-":80"}"
export BASEROW_CADDY_GLOBAL_CONF="${BASEROW_CADDY_GLOBAL_CONF:-}"

export PRIVATE_BACKEND_URL='http://localhost:8000'
export PRIVATE_WEB_FRONTEND_URL='http://localhost:3000'
export BASEROW_BACKEND_BIND_ADDRESS=127.0.0.1
export BASEROW_WEBFRONTEND_BIND_ADDRESS=127.0.0.1
export BASEROW_EXTRA_ALLOWED_HOSTS="${BASEROW_EXTRA_ALLOWED_HOSTS:-}"

export SYNC_TEMPLATES_ON_STARTUP=${SYNC_TEMPLATES_ON_STARTUP:-true}
export BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION=${BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION:-$SYNC_TEMPLATES_ON_STARTUP}
export MIGRATE_ON_STARTUP=${MIGRATE_ON_STARTUP:-true}
export MEDIA_ROOT="$DATA_DIR/media"
export BASEROW_ICAL_VIEW_MAX_EVENTS=${BASEROW_ICAL_VIEW_MAX_EVENTS:-}

export BASEROW_GROUP_STORAGE_USAGE_QUEUE="${BASEROW_GROUP_STORAGE_USAGE_QUEUE:-}"

if [[ "${BASEROW_ALL_IN_ONE_DEV_MODE:-}" == "true"  ]]; then
  export BASEROW_BACKEND_DEBUG="${BASEROW_BACKEND_DEBUG:-on}"
  DEFAULT_DJANGO_SETTINGS_MODULE='baserow.config.settings.dev'
  DEFAULT_WEB_FRONTEND_STARTUP_COMMAND='nuxt-dev-no-attach'
  DEFAULT_BACKEND_STARTUP_COMMAND='django-dev-no-attach'
  DEFAULT_CELERY_WORKER_STARTUP_COMMAND='watch-py celery-worker'
  DEFAULT_CELERY_EXPORT_WORKER_STARTUP_COMMAND='watch-py celery-exportworker'
  DEFAULT_CELERY_BEAT_STARTUP_COMMAND='celery-beat'
else
  DEFAULT_DJANGO_SETTINGS_MODULE='baserow.config.settings.base'
  DEFAULT_WEB_FRONTEND_STARTUP_COMMAND='nuxt-local'
  DEFAULT_BACKEND_STARTUP_COMMAND='gunicorn'
  DEFAULT_CELERY_WORKER_STARTUP_COMMAND='celery-worker'
  DEFAULT_CELERY_EXPORT_WORKER_STARTUP_COMMAND='celery-exportworker'
  DEFAULT_CELERY_BEAT_STARTUP_COMMAND='celery-beat'
fi

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-$DEFAULT_DJANGO_SETTINGS_MODULE}
export BASEROW_WEB_FRONTEND_STARTUP_COMMAND="${BASEROW_WEB_FRONTEND_STARTUP_COMMAND:-$DEFAULT_WEB_FRONTEND_STARTUP_COMMAND}"
export BASEROW_BACKEND_STARTUP_COMMAND="${BASEROW_BACKEND_STARTUP_COMMAND:-$DEFAULT_BACKEND_STARTUP_COMMAND}"
export BASEROW_CELERY_WORKER_STARTUP_COMMAND="${BASEROW_CELERY_WORKER_STARTUP_COMMAND:-$DEFAULT_CELERY_WORKER_STARTUP_COMMAND}"
export BASEROW_CELERY_EXPORT_WORKER_STARTUP_COMMAND="${BASEROW_CELERY_EXPORT_WORKER_STARTUP_COMMAND:-$DEFAULT_CELERY_EXPORT_WORKER_STARTUP_COMMAND}"
export BASEROW_CELERY_BEAT_STARTUP_COMMAND="${BASEROW_CELERY_BEAT_STARTUP_COMMAND:-$DEFAULT_CELERY_BEAT_STARTUP_COMMAND}"
export XDG_CONFIG_HOME=/home/$DOCKER_USER/
export HOME=/home/$DOCKER_USER/

# By default we run all other sub-supervisor processes as a non root user. However for
# now we want to default just Caddy to a root user so it can bind to the privileged
# port of 80.
#
# Until the latest version of Docker engine is more available if we want
# Caddy to be able to bind to the privileged port of 80 it must be root. It was fixed
# in 2020 (https://github.com/moby/moby/pull/41030) but we have many users who are
# running older versions (often packaged by other software) who hit this error.
# Even the official Caddy image runs as root currently to get around this problem:
# (https://github.com/caddyserver/caddy-docker/issues/104)
export BASEROW_CADDY_USER="${BASEROW_CADDY_USER:-root}"
