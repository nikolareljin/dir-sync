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

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
fi

run_cmd() {
  if $dry_run; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

if command -v apt-get >/dev/null 2>&1; then
  print_info "Installing dependencies with apt-get"
  run_cmd sudo apt-get update
  run_cmd sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-tk \
    rsync
elif command -v dnf >/dev/null 2>&1; then
  print_info "Installing dependencies with dnf"
  run_cmd sudo dnf install -y \
    python3 \
    python3-pip \
    python3-tkinter \
    rsync
elif command -v pacman >/dev/null 2>&1; then
  print_info "Installing dependencies with pacman"
  run_cmd sudo pacman -Sy --noconfirm \
    python \
    python-pip \
    tk \
    rsync
elif command -v brew >/dev/null 2>&1; then
  print_info "Installing dependencies with Homebrew"
  run_cmd brew install python tcl-tk rsync
else
  log_error "Unsupported package manager."
  log_error "Install manually: python3, pip, tkinter/python3-tk, rsync"
  exit 1
fi

print_success "Dependency installation completed."
