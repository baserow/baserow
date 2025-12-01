#!/bin/bash
# Bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail

# The Docker entrypoint script which provides a basic CLI, ensures the environment is
# setup and any runtime setup like file permissions is done.

# ========================
# =  HELPER FUNCTIONS
# ========================
show_help() {
    echo """
Usage: docker run --rm -it [-v baserow:$DATA_DIR] baserow COMMAND_FROM_BELOW
Commands
start         : Launches baserow with all services running internally in a single
                container.
start-only-db : Starts up only the embedded postgres server and makes it available
                for external connections if you expose port 5432 using
                the extra docker run argument of '-p 5432:5432'. Useful for if you
                need to manually inspect Baserows database etc.
                > You can find the postgres users password by separately running
                > docker exec -it baserow cat /baserow/data/.pgpass

backend-cmd CMD      : Runs the specified backend command, use the help command to
                       show all available.
backend-cmd-with-db  : Starts the embedded postgres database and then runs any supplied
                       backend command normally. Useful for running one off commands
                       that require the database like backups and restores.
web-frontend-cmd CMD : Runs the specified web-frontend command, use help to show all
install-plugin   CMD : Installs a plugin (append --help for more info).
uninstall-plugin CMD : Un-installs a plugin (append --help for more info).
list-plugins     CMD : Lists currently installed plugins.
help                 : Show this message.
"""
}
if [[ -z "${1:-}" ]]; then
  echo "Must provide arguments to baserow"
  show_help
  exit 1
fi


# From https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh
# usage: file_env VAR [DEFAULT]
#    ie: file_env 'XYZ_DB_PASSWORD' 'example'
# (will allow for "$XYZ_DB_PASSWORD_FILE" to fill in the value of
#  "$XYZ_DB_PASSWORD" from a file, especially for Docker's secrets feature)
file_env() {
	local var="$1"
	local fileVar="${var}_FILE"
	local def="${2:-}"
	if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
		echo >&2 "error: both $var and $fileVar are set (but are exclusive)"
		exit 1
	fi
	local val="$def"
	if [ "${!var:-}" ]; then
		val="${!var}"
	elif [ "${!fileVar:-}" ]; then
		val="$(< "${!fileVar}")"
	fi
	export "$var"="$val"
	unset "$fileVar"
}

startup_echo(){
  /baserow/supervisor/wrapper.sh GREEN STARTUP echo -e "\e[32m$*\e[0m"
}

create_secret_env_if_missing(){
  SECRET_FILE="$DATA_DIR/$1"
  if [[ -z "${!2:-}" ]]; then
    if [[ ! -f $SECRET_FILE ]]; then
        startup_echo "Creating $2 secret in $SECRET_FILE"
        echo "export $2=$(tr -dc 'a-z0-9' < /dev/urandom | head -c50)" > "$SECRET_FILE"
        chmod 600 "$SECRET_FILE"
    fi
    startup_echo "Importing $2 secret from $SECRET_FILE"
    # shellcheck disable=SC1090
    source "$SECRET_FILE"
  fi
}
# ========================
# =  SOURCE ENVIRONMENT SETUP FILES
# ========================

# Import extra settings first so they don't inherit from the default ones.
shopt -s nullglob
for f in /baserow/supervisor/env/*.sh; do
   startup_echo "Importing extra settings from $f"
    # shellcheck disable=SC1090
    source "$f";
done

if [[ -z "$DATA_DIR" ]]; then
  export DATA_DIR=/baserow/data
fi

for f in "$DATA_DIR"/env/*.sh; do
   startup_echo "Importing extra data dir settings from $f"
    # shellcheck disable=SC1090
   source "$f";
done

# Source the default env file + any optionally provided ones.
source /baserow/supervisor/default_baserow_env.sh

# ========================
# =  VOLUME CHECK
# ========================

if [[ -z "${DISABLE_VOLUME_CHECK:-}" ]]; then
  mountVar=$(mount | grep "$DATA_DIR" || true)
  if [ -z "$mountVar" ]
  then
  echo -e "\e[33mPlease run baserow with a mounted data folder " \
          "'docker run -v " \
          "baserow_data:/baserow/data ...', otherwise your data will be lost between " \
          "runs. To disable this check set the DISABLE_VOLUME_CHECK env variable to " \
          "'yes' (docker run -e DISABLE_VOLUME_CHECK=yes ...). \e[0m" 2>&1
  exit 1
  fi
fi

# Ensure the data dir exists
if [[ ! -d "$DATA_DIR" ]]; then
  mkdir -p "$DATA_DIR"
  chown "$DOCKER_USER": "$DATA_DIR"
fi

# ========================
# = CHECK IF DATABASE IS INCORRECTLY LOCALHOST
# ========================
if [[ "$DATABASE_HOST" == *"localhost"* && -z "${DISABLE_LOCALHOST_CHECK:-}" ]]; then
  echo -e "\e[31mERROR: You have set DATABASE_HOST to localhost but this will mean "\
          "localhost in the Baserow container and not on your host machine. "\
          "To connect Baserow to a db running on your host instead then you need to"\
          " run docker with the following flags: \n\n"\
          "--add-host host.docker.internal:host-gateway "\
          "-e DATABASE_HOST=host.docker.internal\n\n To disable this check set " \
          "-e DISABLE_LOCALHOST_CHECK=yes. "\
          "\e[0m"
  exit 1
fi

if [[ "$DATABASE_HOST" == "embed" && -z "${DATABASE_URL:-}" ]]; then
  if [[ -n "${DISABLE_EMBEDDED_PSQL:-}" ]]; then
    echo -e "\e[31mFATAL: DISABLE_EMBEDDED_PSQL is set but neither DATABASE_HOST or "\
            "DATABASE_URL is provided.\e[0m"
    exit 1
  fi
  startup_echo "No DATABASE_HOST or DATABASE_URL provided, using embedded postgres."
  export DATABASE_HOST=localhost
  export BASEROW_EMBEDDED_PSQL=true
else
  if [ ! -z "${DATABASE_URL:-}" ] && [ "${POSTGRES_SETUP_SCRIPT_COMMAND:-}" = "upgrade" ]; then
      startup_echo "===================================================================================="
      startup_echo "This image should only be used to update the data folder of the embedded PostgreSQL."
      startup_echo "===================================================================================="
      exit 1
  fi
  startup_echo "Using provided external postgres at ${DATABASE_HOST:-} or the " \
               "DATABASE_URL"
  export BASEROW_EMBEDDED_PSQL=false
fi

# ========================
# = CHECK IF REDIS IS INCORRECTLY LOCALHOST
# ========================
if [[ "$REDIS_HOST" == *"localhost"* && -z "${DISABLE_LOCALHOST_CHECK:-}" ]]; then
  echo -e "\e[31mERROR: You have set REDIS_HOST to localhost but this will mean "\
          "localhost in the Baserow container and not on your host machine. "\
          "To connect Baserow to a redis running on your host instead then you need to"\
          " run docker with the following flags: \n\n"\
          "--add-host host.docker.internal:host-gateway "\
          "-e REDIS_HOST=host.docker.internal\n\n To disable this check set " \
          "-e DISABLE_LOCALHOST_CHECK=yes . "\
          "\e[0m"
fi

if [[ "$REDIS_HOST" == "embed" && -z "${REDIS_URL:-}" ]]; then
  export REDIS_HOST="localhost"
  startup_echo "Using embedded baserow redis as no REDIS_HOST or REDIS_URL provided. "
else
  startup_echo "Using provided external redis at ${REDIS_HOST:-} or at the REDIS_URL"
fi

# ========================
# =  SECRETS SETUP
# ========================
# Allow users to set secrets via mounted in files, docker secrets or env variables.
if [[ -z "${REDIS_URL:-}" ]]; then
  file_env REDIS_PASSWORD
  create_secret_env_if_missing .redispass REDIS_PASSWORD
else
  echo "Not loading REDIS_PASSWORD as REDIS_URL is set and it should be included there"\
       " instead"
fi

file_env SECRET_KEY
create_secret_env_if_missing .secret SECRET_KEY

file_env BASEROW_JWT_SIGNING_KEY
create_secret_env_if_missing .jwt_signing_key BASEROW_JWT_SIGNING_KEY

if [[ -z "${DATABASE_URL:-}" && -z "${DISABLE_EMBEDDED_SQL:-}" ]]; then
  file_env DATABASE_PASSWORD
  create_secret_env_if_missing .pgpass DATABASE_PASSWORD
else
  echo "Not loading DATABASE_PASSWORD as DATABASE_URL or DISABLED_EMBEDDED_SQL is set."
fi

file_env EMAIL_SMTP_PASSWORD

# ========================
# = DATA DIR SETUP
# ========================
# Setup the various folders in the data mount with the correct permissions.
# We do this here instead of in the docker image in-case the user mounts in a host
# directory as a volume, which will not be auto setup by docker with the containers
# underlying structure.

if [[ -z "${DISABLE_EMBEDDED_REDIS:-}" ]]; then
  mkdir -p "$DATA_DIR"/redis
  chown -R redis:redis "$DATA_DIR"/redis
fi

if [[ -z "${DISABLE_EMBEDDED_PSQL:-}" ]]; then
  mkdir -p "$DATA_DIR"/postgres
  chown -R postgres:postgres "$DATA_DIR"/postgres
fi

mkdir -p "$DATA_DIR"/caddy
chown -R "$DOCKER_USER": "$DATA_DIR"/caddy
mkdir -p "$DATA_DIR"/media
chown -R "$DOCKER_USER": "$DATA_DIR"/media
mkdir -p "$DATA_DIR"/env
chown -R "$DOCKER_USER": "$DATA_DIR"/env
mkdir -p "$DATA_DIR"/backups
chown -R "$DOCKER_USER": "$DATA_DIR"/backups

# ========================
# = COMMAND LINE ARG HANDLER
# ========================

docker_safe_exec(){
    # When running one off commands we want to become the docker user + ensure signals
    # are handled correctly. This function achieves both by using tini and su-exec.
    CURRENT_USER=$(whoami)
    if [[ "$CURRENT_USER" != "$DOCKER_USER" ]]; then
      exec tini -s -- su-exec "$DOCKER_USER" "$@"
    else
      exec tini -s -- "$@"
    fi
}

check_can_start_embedded_services(){
    if [[ -n "${DISABLE_EMBEDDED_PSQL:-}" ]]; then
      echo >&2 "Cannot start the embedded postgres as DISABLE_EMBEDDED_PSQL is set"
      exit 1
    fi
}

run_cmd_with_db(){
    if [[ $(pgrep -f "redis") && $(pgrep -f "bin/postgres") ]]; then
      # We already have a redis and postgres running, just execute the command.
      startup_echo "Found an existing embedded postgres + redis running so running command immediately."
      startup_echo "======== RUNNING COMMAND ========="
      "$@"
      startup_echo "=================================="
    else
      check_can_start_embedded_services

      startup_echo "Didn't find an existing postgres + redis running, starting them up now."
      export SUPERVISOR_CONF=/baserow/supervisor/supervisor_include_only.conf
      /baserow/supervisor/start.sh "${@:2}" &
      SUPERVISORD_PID=$!

      function finish {
        startup_echo "======== Cleaning up after Command =========="
        (sleep 1; kill $SUPERVISORD_PID) &
        wait $SUPERVISORD_PID
      }
      trap finish EXIT
      /baserow/backend/docker/docker-entrypoint.sh wait_for_db
      startup_echo "======== RUNNING COMMAND ========="
      # Ensure we run the finish cleanup even if the command exits with a non zero exit
      # code
      set +e
      "$@"
      retval=$?
      set -e
      startup_echo "=================================="
      exit $retval
    fi
}

case "$1" in
    start)
      exec /baserow/supervisor/start.sh "${@:2}"
    ;;
    backend-cmd-with-db)
      run_cmd_with_db su-exec "$DOCKER_USER" /baserow/backend/docker/docker-entrypoint.sh "${@:2}"
    ;;
    start-only-db)
      check_can_start_embedded_services
      # Run this temporary server with its own pg_hba.conf so if the above check somehow
      # fails we don't accidentally edit the pg_hba.conf of the normal embedded postgres
      # which we don't want exposed at all.
      TMP_HBA_FILE="$POSTGRES_LOCATION"/pg_hba_temp.conf
      cp -p "$POSTGRES_LOCATION"/pg_hba.conf "$TMP_HBA_FILE"

      HBA_ENTRY="host    all             all             all                     md5"
      echo "$HBA_ENTRY" \
        | tee -a "$TMP_HBA_FILE"

      export EXTRA_POSTGRES_ARGS="-c listen_addresses='*' -c hba_file=$TMP_HBA_FILE"
      export SUPERVISOR_CONF=/baserow/supervisor/supervisor_include_only.conf
      startup_echo "INFO: You can find the baserow database user's password by running"
      startup_echo "docker exec -it baserow cat $DATA_DIR/.pgpass"
      exec /baserow/supervisor/start.sh "${@:2}"
    ;;
    backend-cmd)
      cd /baserow/backend
      docker_safe_exec /baserow/backend/docker/docker-entrypoint.sh "${@:2}"
    ;;
    web-frontend-cmd)
      cd /baserow/web-frontend
      docker_safe_exec /baserow/web-frontend/docker/docker-entrypoint.sh "${@:2}"
    ;;
    install-plugin)
      exec /baserow/plugins/install_plugin.sh --runtime "${@:2}"
    ;;
    uninstall-plugin)
      export BASEROW_DISABLE_PLUGIN_INSTALL_ON_STARTUP="on"
      # We need the database to uninstall as the plugin might need to unapply migrations
      # Whereas when installing any database changes can just be normal migrations which
      # will then be run on startup.
      run_cmd_with_db /baserow/plugins/uninstall_plugin.sh "${@:2}"
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
