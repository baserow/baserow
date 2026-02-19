#!/bin/bash
# Bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail

export BASEROW_VERSION="2.1.0"
BASEROW_WEBFRONTEND_PORT="${BASEROW_WEBFRONTEND_PORT:-3000}"

show_help() {
    echo """
The available Baserow web-frontend related commands and services are shown below:

COMMANDS:
nuxt-prepare            : Prepare nuxt (generate .nuxt directory)
nuxt-dev                : Start a normal nuxt development server
nuxt-dev-with-storybook : Start nuxt dev + storybook in parallel
storybook-dev           : Start a storybook dev server
nuxt-prod               : Start a production nuxt server
bash                    : Start a bash shell
build                   : Triggers a nuxt re-build of Baserow's web-frontend.

DEV COMMANDS:
lint            : Run all linters (eslint, stylelint, prettier)
lint-fix        : Run all linter fixes
eslint          : Run eslint
stylelint       : Run stylelint
test            : Run vitest tests
ci-test         : Run tests with coverage reporting
install-plugin  : Installs a plugin (append --help for more info).
uninstall-plugin: Un-installs a plugin (append --help for more info).
list-plugins    : Lists currently installed plugins.
help            : Show this message
"""
}

# Lets devs attach to this container running the passed command, press ctrl-c and only
# the command will stop. Additionally they will be able to use bash history to
# re-run the containers command after they have done what they want.
attachable_exec(){
    echo "$@"
    exec bash --init-file <(echo "history -s $*; $*")
}

attachable_exec_retry(){
    echo "$@"
    exec bash --init-file <(echo "history -s $*; while true; do $* && break; done")
}

if [[ -z "${1:-}" ]]; then
  echo "Must provide arguments to docker-entrypoint.sh"
  show_help
  exit 1
fi

source /baserow/plugins/utils.sh

shopt -s nullglob

setup_additional_modules(){
  # Tell nuxt that all built plugins are additional modules to be loaded.
  # We only want to include the built ones as we might have not yet installed the
  # dependencies or some plugins yet and we don't want nuxt building those ones.
  ADDITIONAL_MODULES="${ADDITIONAL_MODULES:-}"
  for plugin_dir in "$BASEROW_PLUGIN_DIR"/*; do
      if [[ -d "${plugin_dir}/web-frontend/" ]]; then
        plugin_name="$(basename -- "$plugin_dir")"
        package_name=$(echo "$plugin_name" | tr '_' '-')
        WEBFRONTEND_BUILT_MARKER=/baserow/container_markers/$plugin_name.web-frontend-built
        if [[ -f "$WEBFRONTEND_BUILT_MARKER" ]]; then
          ADDITIONAL_MODULES="${ADDITIONAL_MODULES:-},$plugin_dir/web-frontend/modules/$package_name/module.js"
        fi
      fi
  done
  export ADDITIONAL_MODULES
}


case "$1" in
    nuxt-dev)
      startup_plugin_setup
      setup_additional_modules
      # Retry the command over and over to work around heap crash.
      attachable_exec_retry yarn dev
    ;;
    nuxt-dev-no-attach)
      startup_plugin_setup
      setup_additional_modules
      exec yarn dev
    ;;
    nuxt-prod)
      startup_plugin_setup
      setup_additional_modules
      export NITRO_HOST="${BASEROW_WEBFRONTEND_BIND_ADDRESS:-0.0.0.0}"
      export NITRO_PORT="$BASEROW_WEBFRONTEND_PORT"
      exec node --import ./env-remap.mjs .output/server/index.mjs "${@:2}"
    ;;
    nuxt-prepare)
      setup_additional_modules
      exec ./node_modules/.bin/nuxt prepare "${@:2}"
    ;;
    nuxt-dev-with-storybook)
      startup_plugin_setup
      setup_additional_modules
      # Start Storybook in background and Nuxt in foreground
      yarn storybook &
      attachable_exec_retry yarn dev
    ;;
    storybook-dev)
      startup_plugin_setup
      setup_additional_modules
      # Retry the command over and over to work around heap crash.
      attachable_exec_retry yarn storybook
    ;;
    lint)
      exec yarn lint
    ;;
    lint-fix)
      attachable_exec yarn fix
    ;;
    eslint)
      exec yarn eslint
    ;;
    stylelint)
      exec yarn stylelint
    ;;
    test)
      exec yarn test
    ;;
    ci-test)
      exec yarn test:coverage
    ;;
    bash)
      exec /bin/bash -c "${@:2}"
    ;;
    build)
      setup_additional_modules
      exec yarn build
    ;;
    install-plugin)
      exec /baserow/plugins/install_plugin.sh "${@:2}"
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
