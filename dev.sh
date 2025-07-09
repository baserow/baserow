#!/bin/bash
# Bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -eo pipefail


tabname() {
  printf "\e]1;$1\a"
}

RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
NC=$(tput sgr0) # No Color

print_manual_instructions(){
  COMMAND=$1
  echo -e "\nTo inspect the now running dev environment open a new tab/terminal and run:"
  echo "    $COMMAND"
}

DOCKER_COMPOSE="docker-compose"

if docker compose version &> /dev/null; then
  DOCKER_COMPOSE="docker compose"
fi

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
          echo -e "\n${YELLOW}./dev.sh WARNING${NC}: gnome-terminal is the only currently supported way of opening
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
        echo -e "\n${WARNING}./dev.sh WARNING${NC}: The OS '$OSTYPE' is not supported yet for creating tabs to setup
        baserow's dev environment, please add support!"
        PRINT_WARNING=false
    fi
    print_manual_instructions "$COMMAND"
  fi
}

launch_tab_and_attach(){
  tab_name=$1
  service_name=$2
  container_name=$(docker inspect -f '{{.Name}}' "$($DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" ps -q "$service_name")" | cut -c2-)
  command="docker logs $container_name && docker attach $container_name"
  if [[ $(docker inspect "$container_name" --format='{{.State.ExitCode}}') -eq 0 ]]; then
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
  container_name=$(docker inspect -f '{{.Name}}' "$($DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" ps -q "$service_name")" | cut -c2-)
  command="docker exec -it $container_name $exec_command"
  new_tab "$tab_name" "$command"
}

launch_e2e_tab(){
  PWD=$(pwd)
  new_tab "e2e tests" "export BASEROW_E2E_STARTUP_MAX_WAIT_TIME_SECONDS=1200; cd $PWD/e2e-tests && bash --init-file <(echo 'history -s yarn run test-ci;./run-e2e-tests-locally.sh')"
}

show_help() {
    echo """
./dev.sh starts the baserow development environment and by default attempts to
open terminal tabs which are attached to the running dev containers.

Usage: ./dev.sh [optional start dev commands] [optional docker-compose up commands]

The ./dev.sh Commands are:
dev (default)   : Use the dev environment.
local           : Use the local environment (no source is mounted, non-dev images used).
all_in_one      : Use the all_in_one environment.
heroku          : Use the heroku environment.
cloudron        : Use the cloudron environment.
run             : Run a command inside a container. See examples below.
restart         : Stop the environment first before relaunching.
restart_wipe    : Stop the environment, delete all of the compose file named volumes.
down            : Down the environment and don't up after.
kill            : Kill the environment and don't up after.
build_only      : Build the environment and don't up after.
dont_migrate    : Disable automatic database migration on baserow startup.
dont_sync       : Disable automatic template sync on baserow startup.
dont_attach     : Don't attach to the running containers after starting them.
ignore_ownership: Don't exit if there are files in the repo owned by a different user.
attach_all      : Attach to all launched containers.
dont_build_deps : When building environments which require other environments to be
                  built first dev.sh will build them automatically, disable this by
                  passing this flag.
no_e2e          : Disabled the e2e testing tab.
help            : Show this message.

Run examples:
./dev.sh run backend help
./dev.sh run backend shell
./dev.sh run backend lint-shell
...
"""
}

function ensure_only_one_env_selected_at_once() {
  if [ "$env_set" == true ]; then
    echo "${RED}You cannot select multiple different environments at once"
    exit 1
  else
    env_set=true
  fi
}
dont_attach=false
down=false
kill=false
build=false
run=false
up=true
migrate=true
sync_templates=true
exit_if_other_owners_found=true
delete_volumes=false
attach_all=false
# Dev.sh supported environments
dev=true
local=false
all_in_one=false
all_in_one_dev=false
cloudron=false
heroku=false
env_set=false
build_deps=true
build_dependencies=()
e2e_tests=true

if [[ -f ".local/pre_devsh_hook.sh" ]]; then
  source ".local/pre_devsh_hook.sh"
fi

while true; do
case "${1:-noneleft}" in
    dont_migrate)
        echo "./dev.sh: Automatic migration on startup has been disabled."
        shift
        migrate=false
    ;;
    dont_sync)
        echo "./dev.sh: Automatic template syncing on startup has been disabled."
        shift
        sync_templates=false
    ;;
    dont_attach)
        echo "./dev.sh: Configured to not attach to running dev containers."
        shift
        dont_attach=true
    ;;
    restart)
        echo "./dev.sh: Restarting Dev Environment"
        shift
        down=true
        up=true
    ;;
    down)
        echo "./dev.sh: Stopping Dev Environment"
        shift
        up=false
        down=true
    ;;
    kill)
        echo "./dev.sh: Killing Dev Environment"
        shift
        up=false
        kill=true
    ;;
    run)
        echo "./dev.sh: docker-compose running the provided commands"
        shift
        up=false
        dont_attach=true
        run=true
    ;;
    build_only)
        echo "./dev.sh: Disabled docker-compose up at end"
        shift
        build=true
        up=false
    ;;
    all_in_one)
        echo "./dev.sh: Switching to all in one image"
        ensure_only_one_env_selected_at_once
        all_in_one=true
        dev=false
        build_dependencies=(local)
        shift
    ;;
    all_in_one_dev)
        echo "./dev.sh: Switching to all in one image"
        ensure_only_one_env_selected_at_once
        all_in_one_dev=true
        dev=false
        build_dependencies=(all_in_one)
        shift
    ;;
    cloudron)
        echo "./dev.sh: Building cloudron image"
        ensure_only_one_env_selected_at_once
        cloudron=true
        dev=false
        build_dependencies=(local all_in_one)
        shift
    ;;
    heroku)
        echo "./dev.sh: Switching to heroku"
        ensure_only_one_env_selected_at_once
        heroku=true
        dev=false
        build_dependencies=(local all_in_one)
        shift
    ;;
    dev)
        echo "./dev.sh: Using dev env"
        ensure_only_one_env_selected_at_once
        dev=true
        shift
    ;;
    local)
        echo "./dev.sh: Using local instead of dev overrides"
        ensure_only_one_env_selected_at_once
        local=true
        dev=false
        shift
    ;;
    restart_wipe)
        echo "./dev.sh: Restarting Env and Wiping baserow_pgdata volume if exists"
        shift
        down=true
        up=true
        delete_volumes=true
    ;;
    ignore_ownership)
        echo "./dev.sh: Continuing if files in repo are not owned by $USER."
        shift
        exit_if_other_owners_found=false
    ;;
    attach_all)
        shift
        attach_all=true
    ;;
    dont_build_deps)
        build_deps=false
        shift
    ;;
    no_e2e)
        e2e_tests=false
        shift
    ;;
    help)
        echo "Command given was $*"
        show_help
        exit 0
    ;;
    *)
        break
    ;;
esac
done

OWNERS=$(find . ! -user "$USER")

if [[ $OWNERS ]]; then
if [[ "$exit_if_other_owners_found" = true ]]; then
echo "${RED}./dev.sh ERROR${NC}: Files not owned by your current user: $USER found in this repo.
This will cause file permission errors when Baserow starts up.

They are probably build files created by the old Baserow Docker images owned by root.
Run the following command to show which files are causing this:
  find . ! -user $USER

Please run the following command to fix file permissions in this repository before using ./dev.sh:
  ${GREEN}sudo chown $USER -R .${NC}

OR you can ignore this check by running with the ignore_ownership arg:
  ${YELLOW}./dev.sh ignore_ownership ...${NC}"
exit;
else

echo "${YELLOW}./dev.sh WARNING${NC}: Files not owned by your current user: $USER found in this repo.
Continuing as 'ignore_ownership' argument provided."
fi

fi

# Set various env variables to sensible defaults if they have not already been set by
# the user.
if [[ -z "$UID" ]]; then
UID=$(id -u)
fi
export UID

if [[ -z "$GID" ]]; then
GID=$(id -g)
fi
export GID


if [[ -z "${MIGRATE_ON_STARTUP:-}" ]]; then
if [ "$migrate" = true ] ; then
export MIGRATE_ON_STARTUP="true"
else
# Because of the defaults set in the docker-compose file we need to explicitly turn
# this off as just not setting it will get the default "true" value.
export MIGRATE_ON_STARTUP="false"
fi
else
  echo "./dev.sh Using the already set value for the env variable MIGRATE_ON_STARTUP = $MIGRATE_ON_STARTUP"
fi

if [[ -z "${BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION:-}" ]]; then
if [ "$sync_templates" = true ] ; then
export BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION="true"
else
# Because of the defaults set in the docker-compose file we need to explicitly turn
# this off as just not setting it will get the default "true" value.
export BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION="false"
fi
else
  echo "./dev.sh Using the already set value for the env variable BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION = $BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION"
fi

# Enable buildkit for faster builds with better caching.
export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_BUILDKIT=1

export REDIS_PASSWORD=baserow
export DATABASE_PASSWORD=baserow
export SECRET_KEY=baserow
if [[ "$dev" = true ]]; then
  # Caddy will just be the media server so change its port to match the MEDIA_URL
  export WEB_FRONTEND_PORT=4000
  export WEB_FRONTEND_SSL_PORT=4443

  export BASEROW_PUBLIC_URL=
  export PUBLIC_BACKEND_URL=${PUBLIC_BACKEND_URL:-http://localhost:8000}
  export PUBLIC_WEB_FRONTEND_URL=${PUBLIC_WEB_FRONTEND_URL:-http://localhost:3000}

  export MEDIA_URL=http://localhost:4000/media/
  export BASEROW_DEPLOYMENT_ENV="development-$USER"
fi


echo "./dev.sh running docker-compose commands:
------------------------------------------------
"

CORE_FILE=docker-compose.yml

if [ "$local" = true ] ; then
  OVERRIDE_FILE=(-f deploy/local_testing/docker-compose.local.yml)
else
  OVERRIDE_FILE=(-f docker-compose.dev.yml)

  # Detect and use gitignored dev specific docker-compose override file
  if [[ -f ".local/docker-compose.dev.local.yml" ]]; then
    OVERRIDE_FILE=(-f docker-compose.dev.yml -f .local/docker-compose.dev.local.yml)
  fi
fi

if [ "$all_in_one" = true ] ; then
  CORE_FILE=deploy/all-in-one/"$CORE_FILE"
  OVERRIDE_FILE=()
fi

if [ "$all_in_one_dev" = true ] ; then
  CORE_FILE=deploy/all-in-one/docker-compose.dev.yml
  OVERRIDE_FILE=()
fi

if [ "$cloudron" = true ] ; then
  CORE_FILE=deploy/cloudron/"$CORE_FILE"
  OVERRIDE_FILE=()
fi

if [ "$heroku" = true ] ; then
  CORE_FILE=deploy/heroku/"$CORE_FILE"
  OVERRIDE_FILE=()
fi

set -x

if [ "$down" = true ] ; then
# Remove the containers and remove the anonymous volumes for cleanliness sake.
$DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" rm -s -v -f
$DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" down --remove-orphans
fi

if [ "$kill" = true ] ; then
$DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" kill
fi

if [ "$build" = true ] ; then
  if [ "$build_deps" = true ]; then
    for dep in "${build_dependencies[@]}"
    do
      ${BASH_SOURCE[0]} "$dep" build_only
    done
  fi

  $DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" build "$@"
fi

if [ "$delete_volumes" = true ] ; then
  $DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" down -v
fi

if [ "$up" = true ] ; then
$DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" up -d "$@"
fi

if [ "$run" = true ] ; then
$DOCKER_COMPOSE -f "$CORE_FILE" "${OVERRIDE_FILE[@]}" run "$@"
fi

set +x

if [ "$dont_attach" != true ] && [ "$up" = true ] ; then

  if [ "$all_in_one" = true ]; then
    launch_tab_and_attach "baserow_all_in_one" "baserow_all_in_one"
    launch_tab_and_attach "mailhog" "mailhog"
  fi

  if [ "$all_in_one_dev" = true ]; then
    launch_tab_and_attach "baserow_all_in_one_dev" "baserow_all_in_one_dev"
    launch_tab_and_exec "web frontend lint" \
            "baserow_all_in_one_dev" \
            "/bin/bash /baserow.sh web-frontend-cmd lint-fix"
    launch_tab_and_exec "backend lint" \
            "baserow_all_in_one_dev" \
            "/bin/bash /baserow.sh backend-cmd lint-shell"
    launch_tab_and_attach "mailhog" "mailhog"
  fi

  if [ "$cloudron" = true ]; then
    launch_tab_and_attach "baserow_cloudron" "baserow_cloudron"
    if [ "$attach_all" = true ] ; then
      launch_tab_and_attach "db" "db"
      launch_tab_and_attach "mailhog" "mailhog"
    fi
  fi

  if [ "$heroku" = true ]; then
    launch_tab_and_attach "baserow_heroku" "baserow_heroku"
    if [ "$attach_all" = true ] ; then
      launch_tab_and_attach "db" "db"
      launch_tab_and_attach "redis" "redis"
      launch_tab_and_attach "mailhog" "mailhog"
    fi
  fi

  if [ "$local" = true ] || [ "$dev" = true ]; then
    launch_tab_and_attach "backend" "backend"
    launch_tab_and_attach "web frontend" "web-frontend"
    launch_tab_and_attach "celery" "celery"
    launch_tab_and_attach "export worker" "celery-export-worker"
    launch_tab_and_attach "beat worker" "celery-beat-worker"

    if [ "$dev" = true ] ; then
      launch_tab_and_exec "web frontend lint" \
              "web-frontend" \
              "/bin/bash /baserow/web-frontend/docker/docker-entrypoint.sh lint-fix"
      launch_tab_and_exec "backend lint" \
              "backend" \
              "/bin/bash /baserow/backend/docker/docker-entrypoint.sh lint-shell"
      if [ "$e2e_tests" = true ]; then
        launch_e2e_tab
      fi
    fi

    if [ "$attach_all" = true ] ; then
      launch_tab_and_attach "caddy" "caddy"
      launch_tab_and_attach "db" "db"
      launch_tab_and_attach "redis" "redis"
      launch_tab_and_attach "mailhog" "mailhog"
      launch_tab_and_attach "otel-collector" "otel-collector"
      if [ "$dev" = true ] ; then
        launch_tab_and_attach "mjml compiler" "mjml-email-compiler"
      fi
    fi
  fi
fi

if [[ -f ".local/post_devsh_hook.sh" ]]; then
  source ".local/post_devsh_hook.sh"
fi
