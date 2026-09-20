#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVE_PAGES="$SCRIPT_DIR/script-helpers/bin/serve-pages"

if [[ ! -x "$SERVE_PAGES" ]]; then
  echo "Missing submodule helper: $SERVE_PAGES" >&2
  echo "Run ./scripts/update.sh to set it up first." >&2
  exit 1
fi

exec "$SERVE_PAGES" "$PROJECT_ROOT/site" "$@"
