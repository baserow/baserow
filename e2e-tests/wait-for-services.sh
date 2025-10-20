#!/usr/bin/env bash
set -Eeo pipefail

# This script waits 60 seconds by default for the backend and web-frontend services
# to become healthy.

# Keep in sync with src/baserow/config/settings/base.py:594
DEFAULT_APPLICATION_TEMPLATES=("project-tracker" "ab_ivory_theme")

baserow_ready() {
    curlf() {
      HTTP_CODE=$(curl --silent -o /dev/null --write-out "%{http_code}" --max-time 10 "$@")
      if [[ ${HTTP_CODE} -lt 200 || ${HTTP_CODE} -gt 299 ]] ; then
        echo "$1 not ready..."
        return 22
      fi
      return 0
    }

    templates_ready(){
      TEMPLATES_JSON=$(curl --silent --max-time 10 "${PUBLIC_BACKEND_URL:-http://backend:8000}/api/templates/")
      for template in "${DEFAULT_APPLICATION_TEMPLATES[@]}"; do
        if [[ ${TEMPLATES_JSON} != *"$template"* ]] ; then
          echo "Template $template is missing..."
          return 22
        fi
      done
      return 0
    }

    if curlf "${PUBLIC_WEB_FRONTEND_URL:-http://web-frontend:3000}/_health/" && curlf "${PUBLIC_BACKEND_URL:-http://backend:8000}/api/_health/" && templates_ready; then
      return 0
    else
      return 1
    fi
}

for _ in $(seq 1 "${BASEROW_E2E_STARTUP_MAX_WAIT_TIME_SECONDS:-60}")
do
  echo 'Waiting for backend, web-frontend and synced templates to be ready'
  if baserow_ready; then
    echo 'Baserow is ready! Exiting with success code.'
    exit 0
  fi
  sleep 1
done
echo 'E2E services failed to startup in time, crashing the test.'
exit 1
