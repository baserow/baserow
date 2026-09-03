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
# The Slack action test that clicks needs the dev backend pointed at a Slack
# stub, since a click reaches slack.com otherwise. Start one on
# E2E_SLACK_STUB_PORT (default 8101) and run the dev backend with
# BASEROW_INTEGRATIONS_SLACK_API_URL=http://localhost:8101/api and
# BASEROW_INTEGRATIONS_ALLOW_PRIVATE_ADDRESS=true; the test is skipped
# unless E2E_SLACK_STUB says the backend is wired that way.
if [ "${E2E_SLACK_STUB:-}" = "yes" ]; then
    SLACK_STUB_PORT="${E2E_SLACK_STUB_PORT:-8101}"
    docker rm -f e2e-local-slack-stub >/dev/null 2>&1 || true
    docker run -d --name e2e-local-slack-stub \
        -p "${SLACK_STUB_PORT}:8080" \
        -v "$(cd "$(dirname "$0")" && pwd)/stubs/slack:/home/wiremock:ro" \
        wiremock/wiremock:3.13.1 >/dev/null
    trap 'docker rm -f e2e-local-slack-stub e2e-local-httpbin >/dev/null 2>&1 || true' EXIT
fi
# The dev stack's MailHog, which the dev environment already runs. Its API port
# is BASEROW_MAILHOG_WEB_PORT: 8025 for the default instance, 8035 and 8045 for
# the alternates in .env.local-dev.example. Export that variable, or
# E2E_MAIL_API_URL itself, when the stack under test is not the default one.
export E2E_MAIL_API_URL="${E2E_MAIL_API_URL:-http://localhost:${BASEROW_MAILHOG_WEB_PORT:-8025}}"
# What the dev backend was started with, which this script cannot set for it.
# The tests that click until they are refused are skipped without it.
export E2E_BUTTON_RATE_LIMIT="${E2E_BUTTON_RATE_LIMIT:-}"
export DEBUG="pw:api"
yarn install
yarn playwright install
./wait-for-services.sh
yarn run test-ci
