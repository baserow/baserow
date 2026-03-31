#!/bin/bash
# Production entrypoint for the web-frontend container.
# Starts the Nitro/Nuxt production server when no command is given or when a
# known legacy command is used. Otherwise, executes the provided command so the
# image remains usable for one-off commands and debugging.
set -euo pipefail

start_server() {
    exec node --import ./env-remap.mjs .output/server/index.mjs
}

# No command provided: start the server.
if [[ $# -eq 0 ]]; then
    start_server
fi

# Catch legacy commands that were used in v2.0 and before to start the
# production server (nuxt, nuxt-local) and redirect them to the new Nitro
# server. This ensures backward compatibility with custom docker-compose or
# helm charts that still override the container command.
case "$1" in
    nuxt*)
        echo "WARNING: legacy command '$1' detected. Starting the Nuxt/Nitro server instead. You can safely remove the 'command' override from your docker-compose file." >&2
        start_server
        ;;
    *)
        exec "$@"
        ;;
esac
