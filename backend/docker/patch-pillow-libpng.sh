#!/bin/bash
# Replace the bundled libpng in Pillow's .libs/ directory with the patched version.
# Pillow 12.1.1 bundles libpng 1.6.53 which has known vulnerabilities.
# Remove this script once Pillow ships a release with libpng >= 1.6.55.
#
# Usage: patch-pillow-libpng.sh <path-to-new-libpng-so> <venv-path>

set -euo pipefail

NEW_LIBPNG="$1"
VENV_PATH="$2"

PILLOW_LIBS=$(find "$VENV_PATH" -type d -name "pillow.libs" | head -1)

if [ -z "$PILLOW_LIBS" ]; then
    echo "Warning: pillow.libs directory not found, skipping libpng patch" >&2
    exit 0
fi

OLD_LIBPNG=$(find "$PILLOW_LIBS" -name 'libpng16*' -type f | head -1)

if [ -z "$OLD_LIBPNG" ]; then
    echo "Warning: no libpng16 found in $PILLOW_LIBS, skipping libpng patch" >&2
    exit 0
fi

cp "$NEW_LIBPNG" "$OLD_LIBPNG"
echo "Patched Pillow libpng: replaced $(basename "$OLD_LIBPNG") in $PILLOW_LIBS"
