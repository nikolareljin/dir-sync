#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_HELPERS_DIR="${SCRIPT_HELPERS_DIR:-$SCRIPT_DIR/script-helpers}"
if [[ ! -f "$SCRIPT_HELPERS_DIR/helpers.sh" ]]; then
  echo "Missing submodule: script-helpers" >&2
  echo "Run ./scripts/update.sh to set it up first." >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$SCRIPT_HELPERS_DIR/helpers.sh"
shlib_import logging

BIN_DIR="${DIRSYNC_BIN_DIR:-$HOME/.local/bin}"
TARGET="$BIN_DIR/dir-sync"

if [[ ! -e "$TARGET" ]]; then
  log_warn "No dir-sync launcher found at $TARGET"
  exit 0
fi

if ! grep -q "Managed by dir-sync scripts/install.sh" "$TARGET" 2>/dev/null; then
  log_warn "$TARGET was not created by this project; not removing."
  exit 1
fi

rm -f "$TARGET"
print_success "Removed dir-sync launcher from $TARGET"
