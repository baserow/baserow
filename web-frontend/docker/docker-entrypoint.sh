#!/bin/bash
# Bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail

export BASEROW_VERSION="2.0.6"
BASEROW_WEBFRONTEND_PORT="${BASEROW_WEBFRONTEND_PORT:-3000}"

show_help() {
    echo """
The available Baserow web-frontend related commands and services are shown below:

COMMANDS:
nuxt-dev     : Start a normal nuxt development server
nuxt         : Start a non-dev prod ready nuxt server
nuxt-local   : Start a non-dev prod ready nuxt server using the preset local config
storybook-dev: Start a storybook dev server
bash         : Start a bash shell
build-local  : Triggers a nuxt re-build of Baserow's web-frontend.

DEV COMMANDS:
lint            : Run all the linting
lint-fix        : Run eslint fix
stylelint       : Run stylelint
eslint          : Run eslint
test            : Run jest tests
ci-test         : Run ci tests with reporting
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
      attachable_exec_retry yarn run dev
    ;;
    nuxt-dev-no-attach)
      startup_plugin_setup
      setup_additional_modules
      exec yarn run dev
    ;;
    nuxt)
      startup_plugin_setup
      setup_additional_modules
      exec ./node_modules/.bin/nuxt start --hostname "${BASEROW_WEBFRONTEND_BIND_ADDRESS:-0.0.0.0}" --port "$BASEROW_WEBFRONTEND_PORT" "${@:2}"
    ;;
    nuxt-local)
      startup_plugin_setup
      setup_additional_modules
      exec ./node_modules/.bin/nuxt start --hostname "${BASEROW_WEBFRONTEND_BIND_ADDRESS:-0.0.0.0}" --port "$BASEROW_WEBFRONTEND_PORT" --config-file ./config/nuxt.config.local.js "${@:2}"
    ;;
    storybook-dev)
      startup_plugin_setup
      setup_additional_modules
      exec yarn run storybook
    ;;
    lint)
      exec make lint-javascript
    ;;
    lint-fix)
      attachable_exec yarn run eslint --fix
    ;;
    eslint)
      exec make eslint
    ;;
    stylelint)
      exec make eslint
    ;;
    test)
      exec make jest
    ;;
    ci-test)
      exec make ci-test-javascript
    ;;
    bash)
      exec /bin/bash -c "${@:2}"
    ;;
    build-local)
      setup_additional_modules
      exec yarn run build-local
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
