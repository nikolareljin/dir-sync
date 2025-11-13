#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_HELPERS_DIR="${SCRIPT_HELPERS_DIR:-$SCRIPT_DIR/script-helpers}"
# shellcheck source=/dev/null
source "$SCRIPT_HELPERS_DIR/helpers.sh"
shlib_import logging

print_info "Building standalone executable via PyInstaller"
if ! command -v pyinstaller >/dev/null 2>&1; then
  log_warn "pyinstaller not found; installing temporarily"
  python -m pip install --upgrade pyinstaller
fi

pyinstaller --noconfirm --name dir-sync --windowed --onefile src/dirsync/app.py
print_success "Artifacts available in dist/"
