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

if [[ -x "$SCRIPT_DIR/../.venv/bin/ruff" && -x "$SCRIPT_DIR/../.venv/bin/black" ]]; then
  ruff_bin="$SCRIPT_DIR/../.venv/bin/ruff"
  black_bin="$SCRIPT_DIR/../.venv/bin/black"
else
  ruff_bin="${RUFF_BIN:-ruff}"
  black_bin="${BLACK_BIN:-black}"
fi

print_info "Running Ruff"
"$ruff_bin" check src tests

print_info "Running Black"
"$black_bin" --check src tests
