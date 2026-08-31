#!/usr/bin/env bash
set -Eeo pipefail

# Runs the end to end tests pointed at your local dev environment.

export PUBLIC_BACKEND_URL="${PUBLIC_BACKEND_URL:-http://localhost:8000}"
export PUBLIC_WEB_FRONTEND_URL="${PUBLIC_WEB_FRONTEND_URL:-http://localhost:3000}"
export BASEROW_FRONTEND_COOKIE_PREFIX="${BASEROW_FRONTEND_COOKIE_PREFIX:-}"
# The HTTP actions need an endpoint to call, and a dev stack runs no stub of
# its own. A stub started here is only reachable if the dev backend runs with
# BASEROW_INTEGRATIONS_ALLOW_PRIVATE_ADDRESS=true, so that is what decides
# between it and the public httpbin, which serves the same paths. Set
# E2E_HTTP_STUB_URL yourself to point at a stub of your own.
if [ -z "${E2E_HTTP_STUB_URL:-}" ]; then
    if [ "${BASEROW_INTEGRATIONS_ALLOW_PRIVATE_ADDRESS:-}" = "true" ]; then
        STUB_PORT="${E2E_HTTP_STUB_PORT:-8100}"
        docker rm -f e2e-local-httpbin >/dev/null 2>&1 || true
        docker run -d --name e2e-local-httpbin \
            -p "${STUB_PORT}:80" kennethreitz/httpbin@sha256:599fe5e5073102dbb0ee3dbb65f049dab44fa9fc251f6835c9990f8fb196a72b >/dev/null
        trap 'docker rm -f e2e-local-httpbin >/dev/null 2>&1 || true' EXIT
        export E2E_HTTP_STUB_URL="http://localhost:${STUB_PORT}"
    else
        echo "Warning: the HTTP action tests will call the public httpbin.org."
        echo "Run the dev backend with BASEROW_INTEGRATIONS_ALLOW_PRIVATE_ADDRESS=true"
        echo "and set the same variable here to use a local stub instead."
        export E2E_HTTP_STUB_URL="https://httpbin.org"
    fi
fi
# What the dev backend was started with, which this script cannot set for it.
# The tests that click until they are refused are skipped without it.
export E2E_BUTTON_RATE_LIMIT="${E2E_BUTTON_RATE_LIMIT:-}"
export DEBUG="pw:api"
yarn install
yarn playwright install
./wait-for-services.sh
yarn run test-ci
