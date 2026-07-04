#!/usr/bin/env bash
set -Eeo pipefail

# Runs the end to end tests pointed at your local dev environment.

export PUBLIC_BACKEND_URL="${PUBLIC_BACKEND_URL:-http://localhost:8000}"
export PUBLIC_WEB_FRONTEND_URL="${PUBLIC_WEB_FRONTEND_URL:-http://localhost:3000}"
export BASEROW_FRONTEND_COOKIE_PREFIX="${BASEROW_FRONTEND_COOKIE_PREFIX:-}"
export DEBUG="pw:api"
yarn install
yarn playwright install
./wait-for-services.sh
yarn run test-ci
