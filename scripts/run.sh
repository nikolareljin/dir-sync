#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_HELPERS_DIR="${SCRIPT_HELPERS_DIR:-$SCRIPT_DIR/script-helpers}"
# shellcheck source=/dev/null
source "$SCRIPT_HELPERS_DIR/helpers.sh"
shlib_import logging

PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist"
LINUX_BIN="$DIST_DIR/dir-sync"
WINDOWS_BIN="$DIST_DIR/dir-sync.exe"

find_existing_binary() {
  local candidate
  for candidate in "$LINUX_BIN" "$WINDOWS_BIN"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

launch_target() {
  local binary="$1"
  print_info "Launching $binary"
  exec "$binary" "${RUN_ARGS[@]}"
}

RUN_ARGS=("$@")

if ! TARGET_BIN="$(find_existing_binary)"; then
  log_warn "No existing dir-sync binary found in $DIST_DIR; building one now"
  "$SCRIPT_DIR/build.sh"
  TARGET_BIN="$(find_existing_binary)" || {
    log_error "Build completed but dir-sync binary is still missing"
    exit 1
  }
fi

launch_target "$TARGET_BIN"
