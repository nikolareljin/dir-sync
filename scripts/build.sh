#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_HELPERS_DIR="${SCRIPT_HELPERS_DIR:-$SCRIPT_DIR/script-helpers}"
# shellcheck source=/dev/null
source "$SCRIPT_HELPERS_DIR/helpers.sh"
shlib_import logging

print_info "Building standalone executable via PyInstaller"

PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_VENV="$PROJECT_ROOT/.venv"
FALLBACK_VENV="${PYINSTALLER_VENV:-$PROJECT_ROOT/.pyinstaller-venv}"
ENTRY_SCRIPT="$PROJECT_ROOT/scripts/pyinstaller_entry.py"
if [ ! -f "$ENTRY_SCRIPT" ]; then
  log_error "Missing PyInstaller entry script at $ENTRY_SCRIPT"
  exit 1
fi

# Determine which virtualenv provides project dependencies.
if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
  DEP_ENV="$VIRTUAL_ENV"
elif [[ -x "$DEFAULT_VENV/bin/python" ]]; then
  DEP_ENV="$DEFAULT_VENV"
else
  log_error "No virtual environment detected. Create one via docs/BUILD.md before building."
  exit 1
fi

DEP_PYTHON="$DEP_ENV/bin/python"
log_info "Using project environment at $DEP_ENV for dependencies"

MISSING_MODULES="$("$DEP_PYTHON" - <<'PY'
import importlib.util

missing = []
for name in ("typer", "pystray", "PIL", "plyer", "croniter", "yaml", "psutil"):
    if importlib.util.find_spec(name) is None:
        missing.append(name)

if missing:
    print(" ".join(missing))
PY
)"

if [[ -n "${MISSING_MODULES// }" ]]; then
  log_error "Missing required packages in $DEP_ENV: $MISSING_MODULES"
  log_error "Activate the environment and run: pip install -e .[dev]   (see docs/BUILD.md)."
  exit 1
fi

# Bring PyInstaller into the dependency environment (or borrow it from fallback).
PYINSTALLER_PYTHON="$DEP_PYTHON"
EXTRA_IMPORT_PATHS=()
if ! "$PYINSTALLER_PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
  FALLBACK_PYTHON="$FALLBACK_VENV/bin/python"
  if [ ! -d "$FALLBACK_VENV" ]; then
    log_warn "PyInstaller not found; creating helper env at $FALLBACK_VENV"
    python -m venv "$FALLBACK_VENV"
  fi

  if ! "$FALLBACK_PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    log_warn "Installing PyInstaller into $FALLBACK_VENV"
    if ! "$FALLBACK_PYTHON" -m pip install --upgrade pip >/dev/null; then
      log_error "Failed to upgrade pip inside $FALLBACK_VENV"
      exit 1
    fi
    if ! "$FALLBACK_PYTHON" -m pip install pyinstaller >/dev/null; then
      log_error "Unable to install PyInstaller (requires network connectivity once)."
      exit 1
    fi
  fi

  FALLBACK_SITE_PACKAGES="$("$FALLBACK_PYTHON" - <<'PY'
import sysconfig
print(sysconfig.get_paths()["purelib"])
PY
)"
  EXTRA_IMPORT_PATHS+=("$FALLBACK_SITE_PACKAGES")
  log_warn "Borrowing PyInstaller from $FALLBACK_VENV"
fi

# Always ensure the project source directory is at the front of sys.path.
EXTRA_IMPORT_PATHS+=("$PROJECT_ROOT/src")

PY_PATH="$(IFS=:; echo "${EXTRA_IMPORT_PATHS[*]}")"
if [[ -n "${PYTHONPATH:-}" ]]; then
  PY_PATH="$PY_PATH:$PYTHONPATH"
fi

HIDDEN_IMPORTS=(
  "plyer.platforms.linux"
  "plyer.platforms.linux.notification"
  "plyer.platforms.win.notification"
  "plyer.platforms.macosx.notification"
  "plyer.platforms.android.notification"
)

PYINSTALLER_ARGS=(--noconfirm --name dir-sync --windowed --onefile)
for module in "${HIDDEN_IMPORTS[@]}"; do
  PYINSTALLER_ARGS+=(--hidden-import "$module")
done
PYINSTALLER_ARGS+=("$ENTRY_SCRIPT")

PYTHONPATH="$PY_PATH" "$PYINSTALLER_PYTHON" -m PyInstaller "${PYINSTALLER_ARGS[@]}"
print_success "Artifacts available in dist/"
