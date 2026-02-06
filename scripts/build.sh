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

PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python interpreter not found. Install python3 or set PYTHON." >&2
    exit 1
  fi
fi

print_info "Building standalone executable via PyInstaller"
print_info "Ensuring dir-sync runtime dependencies are installed"
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -e .

if ! command -v pyinstaller >/dev/null 2>&1; then
  log_warn "pyinstaller not found; installing temporarily"
  "$PYTHON_BIN" -m pip install --upgrade pyinstaller
fi

pyinstaller --noconfirm --name dir-sync --windowed --onefile src/dirsync/app.py
print_success "Artifacts available in dist/"
