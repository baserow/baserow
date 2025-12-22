#!/bin/bash
# Bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail

# ======================================================
# ENVIRONMENT VARIABLES USED DIRECTLY BY THIS ENTRYPOINT
# ======================================================

export BASEROW_VERSION="2.0.6"

# Used by docker-entrypoint.sh to start the dev server
# If not configured you'll receive this: CommandError: "0.0.0.0:" is not a valid port number or address:port pair.
BASEROW_BACKEND_PORT="${BASEROW_BACKEND_PORT:-8000}"

# Database environment variables used to check the Postgresql connection.
DATABASE_USER="${DATABASE_USER:-baserow}"
DATABASE_HOST="${DATABASE_HOST:-db}"
DATABASE_PORT="${DATABASE_PORT:-5432}"
DATABASE_NAME="${DATABASE_NAME:-baserow}"
DATABASE_PASSWORD="${DATABASE_PASSWORD:-baserow}"
DATABASE_OPTIONS="${DATABASE_OPTIONS:-}"
# Or you can provide a Postgresql connection url
DATABASE_URL="${DATABASE_URL:-}"

BASEROW_POSTGRES_STARTUP_CHECK_ATTEMPTS="${BASEROW_POSTGRES_STARTUP_CHECK_ATTEMPTS:-5}"

# Backend server related variables
MIGRATE_ON_STARTUP=${MIGRATE_ON_STARTUP:-true}
SYNC_TEMPLATES_ON_STARTUP=${SYNC_TEMPLATES_ON_STARTUP:-true}
BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION=${BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION:-$SYNC_TEMPLATES_ON_STARTUP}
BASEROW_BACKEND_BIND_ADDRESS=${BASEROW_BACKEND_BIND_ADDRESS:-0.0.0.0}
BASEROW_BACKEND_LOG_LEVEL=${BASEROW_BACKEND_LOG_LEVEL:-INFO}
BASEROW_ENABLE_SECURE_PROXY_SSL_HEADER=${BASEROW_ENABLE_SECURE_PROXY_SSL_HEADER:-}

BASEROW_AMOUNT_OF_WORKERS=${BASEROW_AMOUNT_OF_WORKERS:-}
BASEROW_AMOUNT_OF_GUNICORN_WORKERS=${BASEROW_AMOUNT_OF_GUNICORN_WORKERS:-3}

# Celery related variables
BASEROW_RUN_MINIMAL=${BASEROW_RUN_MINIMAL:-}
BASEROW_CELERY_BEAT_STARTUP_DELAY=${BASEROW_CELERY_BEAT_STARTUP_DELAY:-15}
BASEROW_CELERY_BEAT_DEBUG_LEVEL=${BASEROW_CELERY_BEAT_DEBUG_LEVEL:-INFO}


# ======================================================
# HELPER FUNCTIONS
# ======================================================

postgres_ready() {
  if [ -z "$DATABASE_URL" ]; then
DATABASE_NAME=$DATABASE_NAME \
DATABASE_USER=$DATABASE_USER \
DATABASE_HOST=$DATABASE_HOST \
DATABASE_PORT=$DATABASE_PORT \
DATABASE_PASSWORD=$DATABASE_PASSWORD \
DATABASE_OPTIONS=$DATABASE_OPTIONS \
python3 << END
import sys
try:
    import psycopg
except ImportError:
    import psycopg2 as psycopg
import json
import os
DATABASE_NAME=os.getenv('DATABASE_NAME')
DATABASE_USER=os.getenv('DATABASE_USER')
DATABASE_HOST=os.getenv('DATABASE_HOST')
DATABASE_PORT=os.getenv('DATABASE_PORT')
DATABASE_PASSWORD=os.getenv('DATABASE_PASSWORD')
DATABASE_OPTIONS=os.getenv('DATABASE_OPTIONS')
try:
    options = json.loads(DATABASE_OPTIONS or "{}")
    psycopg.connect(
        dbname=DATABASE_NAME,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        **options
    )
except Exception as e:
    print(f"Error: Failed to connect to the postgresql database at {DATABASE_HOST}")
    print("Please see the error below for more details:")
    print(e)
    print("Trying again without any DATABASE_OPTIONS:")
    try:
      psycopg.connect(
          dbname=DATABASE_NAME,
          user=DATABASE_USER,
          password=DATABASE_PASSWORD,
          host=DATABASE_HOST,
          port=DATABASE_PORT,
      )
    except Exception as e:
      print(f"Error: Failed to connect to the postgresql database at {DATABASE_HOST} without the {DATABASE_OPTIONS}")
      print("Please see the error below for more details:")
      print(e)
      sys.exit(-1)
sys.exit(0)
END
else
  echo "Checking the provided DATABASE_URL"
DATABASE_URL=$DATABASE_URL \
python3 << END
import sys
try:
    import psycopg
except ImportError:
    import psycopg2 as psycopg
import os
DATABASE_URL=os.getenv('DATABASE_URL')
try:
    psycopg.connect(
        DATABASE_URL
    )
except psycopg.OperationalError as e:
    print(f"Error: Failed to connect to the postgresql database at {DATABASE_URL}")
    print("Please see the error below for more details:")
    print(e)
    sys.exit(-1)
sys.exit(0)
END
  fi
}

wait_for_postgres() {
for i in $( seq 0 "$BASEROW_POSTGRES_STARTUP_CHECK_ATTEMPTS" )
do
  if ! postgres_ready; then
    echo "Waiting for PostgreSQL to become available attempt " \
         "$i/$BASEROW_POSTGRES_STARTUP_CHECK_ATTEMPTS ..."
    sleep 2
  else
    echo 'PostgreSQL is available'
    return 0
  fi
done
echo 'PostgreSQL did not become available in time...'
exit 1
}



show_help() {
    echo """
The available Baserow backend related commands, services and healthchecks are shown
below:

ADMIN COMMANDS:
bash            : Start a bash shell with the correct env setup
manage          : Manage Baserow and its database
setup           : Runs all setup commands (migrate and update_formulas)
backup          : Backs up Baserow's database to DATA_DIR/backups by default
restore         : Restores Baserow's database restores from DATA_DIR/backups by default
python          : Run a python command
shell           : Start a Django Python shell
wait_for_db     : Waits BASEROW_POSTGRES_STARTUP_CHECK_ATTEMPTS attempts for the
                  configured db to become available.
install-plugin  : Installs a plugin (append --help for more info).
uninstall-plugin: Un-installs a plugin (append --help for more info).
list-plugins    : Lists currently installed plugins.
help            : Show this message

SERVICE COMMANDS:
gunicorn            : Start Baserow backend django using a prod ready gunicorn server:
                         * Waits for the postgres database to be available first
                           checking BASEROW_POSTGRES_STARTUP_CHECK_ATTEMPTS times (default 5)
                           before exiting.
                         * Automatically migrates the database on startup unless
                           MIGRATE_ON_STARTUP is set to something other than 'true'.
                         * Binds to BASEROW_BACKEND_BIND_ADDRESS which defaults to 0.0.0.0
gunicorn-wsgi       : Same as gunicorn but runs a wsgi server which does not support WS
celery-worker       : Start the celery worker queue which runs important async tasks
celery-exportworker : Start the celery worker queue which runs slower async tasks
celery-beat         : Start the celery beat service used to schedule periodic jobs

HEALTHCHECK COMMANDS (exit with non zero when unhealthy, zero when healthy)
backend-healthcheck             : Checks the gunicorn/django-dev service health
celery-worker-healthcheck       : Checks the celery-worker health
celery-exportworker-healthcheck : Checks the celery-exportworker health

DEV COMMANDS (most will only work in the baserow_backend_dev image):
django-dev      : Start a normal Baserow backend django development server, performs
                  the same checks and setup as the gunicorn command above.
lint-shell      : Run the linting (only available if using dev target)
lint            : Run the linting and exit (only available if using dev target)
test:           : Run the tests (only available if using dev target)
ci-test:        : Run the tests for ci including various reports (dev only)
ci-check-startup: Start up a single gunicorn and timeout after 10 seconds for ci (dev)
watch-py CMD    : Auto reruns the provided CMD whenever python files change
install-plugin  : Installs a baserow plugin.
"""
}

run_setup_commands_if_configured(){
  startup_plugin_setup
  if [ "$MIGRATE_ON_STARTUP" = "true" ] ; then
    if [ "${BASEROW_DISABLE_LOCKED_MIGRATIONS:-}" = "true" ] ; then
      migration_command="migrate"
    else
      migration_command="locked_migrate"
    fi
    echo "python /baserow/backend/src/baserow/manage.py $migration_command"
    OTEL_SERVICE_NAME=backend-migrate python /baserow/backend/src/baserow/manage.py "$migration_command"
  fi
}

start_celery_worker(){
  startup_plugin_setup
  if [[ -n "$BASEROW_RUN_MINIMAL" ]]; then
    EXTRA_CELERY_ARGS=(--without-heartbeat --without-gossip --without-mingle)
  else
    EXTRA_CELERY_ARGS=()
  fi
  if [[ -n "$BASEROW_AMOUNT_OF_WORKERS" ]]; then
    EXTRA_CELERY_ARGS+=(--concurrency "$BASEROW_AMOUNT_OF_WORKERS")
  fi
  exec celery -A baserow worker "${EXTRA_CELERY_ARGS[@]}" -l INFO "$@"
}

# Lets devs attach to this container running the passed command, press ctrl-c and only
# the command will stop. Additionally they will be able to use bash history to
# re-run the containers command after they have done what they want.
attachable_exec(){
    echo "$@"
    exec bash --init-file <(echo "history -s $*; $*")
}

run_backend_server(){
  wait_for_postgres
  run_setup_commands_if_configured

  if [[ -n "$BASEROW_ENABLE_SECURE_PROXY_SSL_HEADER" ]]; then
    EXTRA_GUNICORN_ARGS=(--forwarded-allow-ips='*')
  else
    EXTRA_GUNICORN_ARGS=()
  fi

  if [[ "$1" = "wsgi" ]]; then
    STARTUP_ARGS=(baserow.config.wsgi:application)
  elif [[ "$1" = "asgi" ]]; then
    STARTUP_ARGS=(-k uvicorn.workers.UvicornWorker baserow.config.asgi:application)
  else
    echo -e "\e[31mUnknown run_backend_server argument $1 \e[0m" >&2
    exit 1
  fi
  # Gunicorn args explained in order:
  #
  # 1. See https://docs.gunicorn.org/en/stable/faq.html#blocking-os-fchmod for
  #    why we set worker-tmp-dir to /dev/shm by default.
  # 2. Log to stdout
  # 3. Log requests to stdout
  exec gunicorn --workers="$BASEROW_AMOUNT_OF_GUNICORN_WORKERS" \
    --worker-tmp-dir "${TMPDIR:-/dev/shm}" \
    --log-file=- \
    --access-logfile=- \
    --capture-output \
    "${EXTRA_GUNICORN_ARGS[@]}" \
    -b "${BASEROW_BACKEND_BIND_ADDRESS:-0.0.0.0}":"${BASEROW_BACKEND_PORT}" \
    --log-level="${BASEROW_BACKEND_LOG_LEVEL}" \
    "${STARTUP_ARGS[@]}" \
    "${@:2}"
}

setup_otel_vars(){
  # These key value pairs will be exported on every log/metric/trace by any otel
  # exporters running in subprocesses launched by this script.
  EXTRA_OTEL_RESOURCE_ATTRIBUTES="service.namespace=Baserow,"
  EXTRA_OTEL_RESOURCE_ATTRIBUTES+="service.version=${BASEROW_VERSION},"
  EXTRA_OTEL_RESOURCE_ATTRIBUTES+="deployment.environment=${BASEROW_DEPLOYMENT_ENV:-unknown}"

  if [[ -n "${OTEL_RESOURCE_ATTRIBUTES:-}" ]]; then
    # If the container has been launched with some extra otel attributes, make sure not
    # to override them with our Baserow specific ones.
    OTEL_RESOURCE_ATTRIBUTES="${EXTRA_OTEL_RESOURCE_ATTRIBUTES},${OTEL_RESOURCE_ATTRIBUTES}"
  else
    OTEL_RESOURCE_ATTRIBUTES="$EXTRA_OTEL_RESOURCE_ATTRIBUTES"
  fi
  export OTEL_RESOURCE_ATTRIBUTES
  echo "OTEL_RESOURCE_ATTRIBUTES=$OTEL_RESOURCE_ATTRIBUTES"
}

# ======================================================
# COMMANDS
# ======================================================

if [[ -z "${1:-}" ]]; then
  echo "Must provide arguments to docker-entrypoint.sh"
  show_help
  exit 1
fi

source /baserow/venv/bin/activate
source /baserow/plugins/utils.sh

setup_otel_vars

case "$1" in
    django-dev)
        wait_for_postgres
        run_setup_commands_if_configured
        echo "Running Development Server on 0.0.0.0:${BASEROW_BACKEND_PORT}"
        echo "Press CTRL-p CTRL-q to close this session without stopping the container."
        export OTEL_SERVICE_NAME=backend-dev
        attachable_exec python /baserow/backend/src/baserow/manage.py runserver "${BASEROW_BACKEND_BIND_ADDRESS:-0.0.0.0}:${BASEROW_BACKEND_PORT}"
    ;;
    django-dev-no-attach)
        wait_for_postgres
        run_setup_commands_if_configured
        echo "Running Development Server on 0.0.0.0:${BASEROW_BACKEND_PORT}"
        export OTEL_SERVICE_NAME=backend-dev
        python /baserow/backend/src/baserow/manage.py runserver "${BASEROW_BACKEND_BIND_ADDRESS:-0.0.0.0}:${BASEROW_BACKEND_PORT}"
    ;;
    gunicorn)
      export OTEL_SERVICE_NAME="backend-asgi"
      run_backend_server asgi "${@:2}"
    ;;
    gunicorn-wsgi)
      export OTEL_SERVICE_NAME="backend-wsgi"
      run_backend_server wsgi "${@:2}"
    ;;
    backend-healthcheck)
      echo "Running backend healthcheck..."
      curlf() {
        HTTP_CODE=$(curl --silent -o /dev/null --write-out "%{http_code}" --max-time 10 "$@")
        if [[ ${HTTP_CODE} -lt 200 || ${HTTP_CODE} -gt 299 ]] ; then
          return 22
        fi
        return 0
      }
      curlf "http://localhost:$BASEROW_BACKEND_PORT/api/_health/"
    ;;
    bash)
        exec /bin/bash -c "${@:2}"
    ;;
    manage)
        export OTEL_SERVICE_NAME=backend-manage
        exec python3 /baserow/backend/src/baserow/manage.py "${@:2}"
    ;;
    python)
        exec python3 "${@:2}"
    ;;
    setup)
      echo "python3 /baserow/backend/src/baserow/manage.py migrate"
      OTEL_SERVICE_NAME=backend-migrate DONT_UPDATE_FORMULAS_AFTER_MIGRATION=yes python3 /baserow/backend/src/baserow/manage.py migrate
      echo "python3 /baserow/backend/src/baserow/manage.py update_formulas"
      OTEL_SERVICE_NAME=backend-update-formulas python3 /baserow/backend/src/baserow/manage.py update_formulas
    ;;
    shell)
        export OTEL_SERVICE_NAME=backend-shell
        exec python3 /baserow/backend/src/baserow/manage.py shell
    ;;
    lint-shell)
        attachable_exec make lint-python
    ;;
    lint)
        exec make lint-python
    ;;
    ci-test)
        exec make ci-test-python PYTEST_SPLITS="${PYTEST_SPLITS:-1}" PYTEST_SPLIT_GROUP="${PYTEST_SPLIT_GROUP:-1}" PYTEST_EXTRA_ARGS="${*:2}"
    ;;
    ci-check-startup)
        exec make ci-check-startup-python
    ;;
    ci-check-startup-oss-only)
        exec make ci-check-startup-python-oss-only
    ;;
    celery-worker)
      if [[ -n "${BASEROW_RUN_MINIMAL}" && $BASEROW_AMOUNT_OF_WORKERS == "1" ]]; then
        export OTEL_SERVICE_NAME="celery-worker-combined"
        echo "Starting combined celery and export worker..."
        start_celery_worker -Q celery,export,automation_workflow -n default-worker@%h "${@:2}"
      else
        export OTEL_SERVICE_NAME="celery-worker"
        start_celery_worker -Q celery,automation_workflow -n default-worker@%h "${@:2}"
      fi
    ;;
    celery-worker-healthcheck)
      echo "Running celery worker healthcheck..."
      exec celery -A baserow inspect ping -d "default-worker@$HOSTNAME" -t 10 "${@:2}"
    ;;
    celery-exportworker)
      if [[ -n "${BASEROW_RUN_MINIMAL}" && $BASEROW_AMOUNT_OF_WORKERS == "1" ]]; then
        echo "Not starting export worker as the other worker will handle both queues " \
             "to reduce memory usage"
        while true; do sleep 2073600; done
      else
        export OTEL_SERVICE_NAME="celery-exportworker"
        start_celery_worker -Q export -n export-worker@%h "${@:2}"
      fi
    ;;
    celery-exportworker-healthcheck)
      echo "Running celery export worker healthcheck..."
      exec celery -A baserow inspect ping -d "export-worker@$HOSTNAME" -t 10 "${@:2}"
    ;;
    celery-beat)
      # Delay the beat startup as there seems to be bug where the other celery workers
      # starting up interfere with or break the lock obtained by it. Without this the
      # second time beat extends its lock it will crash and have to be restarted.
      echo "Sleeping for $BASEROW_CELERY_BEAT_STARTUP_DELAY before starting beat to prevent "\
           "startup errors."
      sleep "$BASEROW_CELERY_BEAT_STARTUP_DELAY"
      export OTEL_SERVICE_NAME="celery-beat"
      exec celery -A baserow beat -l "${BASEROW_CELERY_BEAT_DEBUG_LEVEL}" -S redbeat.RedBeatScheduler "${@:2}"
    ;;
    celery-flower)
      exec celery -A baserow flower "$@"
    ;;
    watch-py)
        # Ensure we watch all possible python source code locations for changes.
        directory_args=''
        for i in $(echo "$PYTHONPATH" | tr ":" "\n")
        do
          directory_args="$directory_args -d=$i"
        done

        attachable_exec watchmedo auto-restart "$directory_args" --pattern="*.py" --recursive -- bash "${BASH_SOURCE[0]} ${*:2}"
    ;;
    backup)
        if [[ -n "$DATABASE_URL" ]]; then
          echo -e "\e[31mThe backup command is currently incompatible with DATABASE_URL, "\
            "please set the DATABASE_{HOST,USER,PASSWORD,NAME,PORT} variables manually"\
            " instead. \e[0m" >&2
          exit 1
        fi
        if [[ -n "${DATA_DIR:-}" ]]; then
          cd "$DATA_DIR"/backups || true
        fi
        export PGPASSWORD=$DATABASE_PASSWORD
        exec python3 /baserow/backend/src/baserow/manage.py backup_baserow \
            -h "$DATABASE_HOST" \
            -d "$DATABASE_NAME" \
            -U "$DATABASE_USER" \
            -p "$DATABASE_PORT" \
            "${@:2}"
    ;;
    restore)
        if [[ -n "$DATABASE_URL" ]]; then
          echo -e "\e[31mThe restore command is currently incompatible with DATABASE_URL, "\
            "please set the DATABASE_{HOST,USER,PASSWORD,NAME,PORT} variables manually"\
            " instead. \e[0m" >&2
          exit 1
        fi
        if [[ -n "${DATA_DIR:-}" ]]; then
          cd "$DATA_DIR"/backups || true
        fi
        export PGPASSWORD=$DATABASE_PASSWORD
        exec python3 /baserow/backend/src/baserow/manage.py restore_baserow \
            -h "$DATABASE_HOST" \
            -d "$DATABASE_NAME" \
            -U "$DATABASE_USER" \
            -p "$DATABASE_PORT" \
            "${@:2}"
    ;;
    wait_for_db)
      wait_for_postgres
    ;;
    install-plugin)
      exec /baserow/plugins/install_plugin.sh --runtime "${@:2}"
    ;;
    uninstall-plugin)
      exec /baserow/plugins/uninstall_plugin.sh "${@:2}"
    ;;
    list-plugins)
      exec /baserow/plugins/list_plugins.sh "${@:2}"
    ;;
    *)
        echo "Command given was $*"
        show_help
        exit 1
    ;;
esac
