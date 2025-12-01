#!/bin/bash
# Bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail

show_help(){
    echo """
Usage: uninstall_plugin.sh <plugin_name>
  -h, --help                          Show this help message and exit.

Uninstalling a plugin will remove the plugin and it's dependencies from the system.
If the plugin has 'backend/uninstall.sh' or 'web-frontend/uninstall.sh' scripts, they
will also be run to do any custom per plugin uninstallation.
"""
}

source /baserow/plugins/utils.sh

plugin_name="$1"

if [[ -z "$plugin_name" ]]; then
  error "The plugin name must be provided as the first argument."
fi


folder="$BASEROW_PLUGIN_DIR/$plugin_name"

if [[ ! -d "$folder" ]]; then
    error "Plugin '$plugin_name' not found."
    exit 1
fi


check_and_run_script(){
    if [[ -f "$1/$2" ]]; then
        log "Running ${plugin_name}'s custom $2 script"
        bash "$1/$2"
    fi
}

run_as_docker_user(){
  CURRENT_USER=$(whoami)
  if [[ "$CURRENT_USER" != "$DOCKER_USER" ]]; then
    su-exec "$DOCKER_USER" "$@"
  else
    "$@"
  fi
}


PLUGIN_BACKEND_FOLDER="$folder/backend"

package_name=$(echo "$plugin_name" | tr '_' '-')
found_sub_module="false"
if [[ -d "/baserow/backend" && -d "$PLUGIN_BACKEND_FOLDER" ]]; then
    log "Un-installing plugin $plugin_name from the backend..."
    . /baserow/venv/bin/activate
    cd /baserow/backend
    check_and_run_script "$PLUGIN_BACKEND_FOLDER" uninstall.sh
    run_as_docker_user pip3 uninstall -y "$package_name"
    rm -f /baserow/container_markers/"$plugin_name".backend-built
    rm -f /baserow/container_markers/"$plugin_name".backend-runtime-setup
    found_sub_module="true"
fi

PLUGIN_WEBFRONTEND_FOLDER="$folder/web-frontend"
if [[ -d "/baserow/web-frontend" && -d "$PLUGIN_WEBFRONTEND_FOLDER" ]]; then
    log "Un-installing plugin $plugin_name from the web-frontend..."
    cd /baserow/web-frontend
    check_and_run_script "$PLUGIN_WEBFRONTEND_FOLDER" uninstall.sh
    run_as_docker_user yarn remove "$package_name"

    # We must delete the web-frontend plugin entirely so the build-local doesn't
    # pick it up and build it.
    rm -rf "$PLUGIN_WEBFRONTEND_FOLDER"
    # We need to rebuild to ensure nuxt no longer has the plugin.
    run_as_docker_user /baserow/web-frontend/docker/docker-entrypoint.sh build-local
    rm -f /baserow/container_markers/"$plugin_name".web-frontend-built
    rm -f /baserow/container_markers/"$plugin_name".web-frontend-runtime-setup
    found_sub_module="true"
fi

if [[ "$found_sub_module" == "true" ]]; then
  log "Deleting ${plugin_name}'s folder..."
  rm -rf "$folder"
  log_success "Successfully uninstalled ${plugin_name}."
else
  error "Failed to find any backend or web-frontend app or module to uninstall for $plugin_name."
  exit 1
fi
