#!/bin/bash
# Production entrypoint for the web-frontend container.
# Always starts the Nitro/Nuxt production server regardless of any CMD arguments
# passed to the container. This ensures backward compatibility with custom
# docker-compose files that may still pass legacy commands like "nuxt-prod".
set -euo pipefail

if [[ $# -gt 0 ]]; then
    echo "WARNING: command '$*' was passed but is ignored. The web-frontend production image always starts the Nuxt/Nitro server. You can safely remove the 'command' override from your docker-compose file."
fi

exec node --import ./env-remap.mjs .output/server/index.mjs
