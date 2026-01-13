#!/usr/bin/env sh

# Execute the node command like if we were a level up.
# needed for some commands like eslint that don't
# want to go out of current root directory

set -e

# Resolve the directory of this script (portable)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Repo root is two levels up from web-frontend/
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# Forward all arguments
exec "$@"
