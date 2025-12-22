#!/usr/bin/env bash
set -Eeo pipefail

# Sets up and starts Baserow and all of its required services using supervisord.

# Use https://manytools.org/hacker-tools/ascii-banner/ and the font ANSI Banner / Wide / Wide to generate
cat << EOF
=========================================================================================

██████╗  █████╗ ███████╗███████╗██████╗  ██████╗ ██╗    ██╗
██╔══██╗██╔══██╗██╔════╝██╔════╝██╔══██╗██╔═══██╗██║    ██║
██████╔╝███████║███████╗█████╗  ██████╔╝██║   ██║██║ █╗ ██║
██╔══██╗██╔══██║╚════██║██╔══╝  ██╔══██╗██║   ██║██║███╗██║
██████╔╝██║  ██║███████║███████╗██║  ██║╚██████╔╝╚███╔███╔╝
╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚══╝╚══╝

Version 2.0.6

=========================================================================================
EOF
cat /baserow/supervisor/STARTUP_README.md

startup_echo(){
  /baserow/supervisor/wrapper.sh GREEN STARTUP echo -e "\e[32m$*\e[0m"
}

# ========================
# = SETUP BLANK INITIAL EMBEDDED DATABASE IF TURNED ON
# ========================

SUPERVISOR_DISABLED_CONF_DIR=/baserow/supervisor/includes/disabled
SUPERVISOR_ENABLED_CONF_DIR=/baserow/supervisor/includes/enabled

if [[ "$DATABASE_HOST" == "localhost" && -z "${DATABASE_URL:-}" ]]; then
  startup_echo "Running setup of embedded baserow database."

  # Update the postgres config to point at the DATA_DIR which must be done here as
  # DATA_DIR can change at runtime.
  sed -i "s;/var/lib/postgresql/$POSTGRES_VERSION/main;$DATA_DIR/postgres;g" "$POSTGRES_LOCATION"/postgresql.conf
  chown postgres:postgres "$POSTGRES_LOCATION"/postgresql.conf

  # Setup an empty baserow database with the provided user and password.
  POSTGRES_SETUP_SCRIPT_COMMAND=${POSTGRES_SETUP_SCRIPT_COMMAND:-setup}
  ./baserow/supervisor/wrapper.sh GREEN POSTGRES_INIT ./baserow/supervisor/docker-postgres-setup.sh ${POSTGRES_SETUP_SCRIPT_COMMAND}

  # Enable the embedded postgres by moving it into the directory from which supervisor
  # includes all .conf files it finds.
  if [ ! -f "$SUPERVISOR_ENABLED_CONF_DIR/embedded-postgres.conf" ]; then
    mv "$SUPERVISOR_DISABLED_CONF_DIR/embedded-postgres.conf" "$SUPERVISOR_ENABLED_CONF_DIR/embedded-postgres.conf"
  fi
elif [ -f "$SUPERVISOR_ENABLED_CONF_DIR/embedded-postgres.conf" ]; then
  # Disable the embedded postgres if somehow the conf is in the enabled folder
  mv "$SUPERVISOR_ENABLED_CONF_DIR/embedded-postgres.conf" "$SUPERVISOR_DISABLED_CONF_DIR/embedded-postgres.conf" 2>/dev/null || true
fi

# ========================
# = SETUP EMBEDDED REDIS IF TURNED ON
# ========================
if [[ "$REDIS_HOST" == "localhost" && -z "${REDIS_URL:-}" ]]; then
  # Enable the embedded redis by moving it into the directory from which supervisor
  # includes all .conf files it finds.
  if [ ! -f "$SUPERVISOR_ENABLED_CONF_DIR/embedded-redis.conf" ]; then
    mv "$SUPERVISOR_DISABLED_CONF_DIR/embedded-redis.conf" "$SUPERVISOR_ENABLED_CONF_DIR/embedded-redis.conf"
  fi
elif [ -f "$SUPERVISOR_ENABLED_CONF_DIR/embedded-redis.conf" ]; then
  # Disable the embedded redis if somehow the conf is in the enabled folder
  mv "$SUPERVISOR_ENABLED_CONF_DIR/embedded-redis.conf" "$SUPERVISOR_DISABLED_CONF_DIR/embedded-redis.conf" 2>/dev/null || true
fi

# ========================
# = LOG ABOUT URL
# ========================
if [[ "$BASEROW_PUBLIC_URL" == "http://localhost"* ]]; then
  startup_echo "No BASEROW_PUBLIC_URL environment variable provided. Starting baserow locally at http://localhost without automatic https."
else
  startup_echo "Starting Baserow using addresses $BASEROW_PUBLIC_URL, if any are https automatically Caddy will attempt to setup HTTPS automatically."
fi

# ========================
# = INSTALL PLUGINS
# ========================

source /baserow/plugins/utils.sh
startup_plugin_setup

# ========================
# = STARTUP SUPERVISOR
# ========================
startup_echo "Starting all Baserow processes:"
exec /usr/bin/supervisord --configuration "${SUPERVISOR_CONF:-/baserow/supervisor/supervisor.conf}"
