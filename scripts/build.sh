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

PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_VENV="${BUILD_VENV:-$PROJECT_ROOT/.venv}"
PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$BUILD_VENV/bin/python" ]]; then
    PYTHON_BIN="$BUILD_VENV/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python interpreter not found. Install python3 or set PYTHON." >&2
    exit 1
  fi
fi

# Avoid installing packages into externally-managed system Python (PEP 668).
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.prefix != getattr(sys, "base_prefix", sys.prefix) else 1)' >/dev/null 2>&1; then
  if [[ ! -x "$BUILD_VENV/bin/python" ]]; then
    log_warn "No virtualenv detected; creating build env at $BUILD_VENV"
    "$PYTHON_BIN" -m venv "$BUILD_VENV"
  fi
  PYTHON_BIN="$BUILD_VENV/bin/python"
fi

print_info "Building standalone executable via PyInstaller"
print_info "Ensuring required Python modules are available"

ensure_module() {
  local module_name="$1"
  local pip_name="$2"
  if "$PYTHON_BIN" -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('${module_name}') else 1)" >/dev/null 2>&1; then
    return 0
  fi
  log_warn "Missing Python module: ${module_name} (installing ${pip_name})"
  "$PYTHON_BIN" -m pip install "$pip_name"
}

ensure_module "croniter" "croniter>=1.4"
ensure_module "PIL" "pillow>=10.0"
ensure_module "plyer" "plyer>=2.1"
ensure_module "psutil" "psutil>=5.9"
ensure_module "pystray" "pystray>=0.19"
ensure_module "yaml" "pyyaml>=6.0"
ensure_module "typer" "typer>=0.12"

if ! "$PYTHON_BIN" -c "import tkinter" >/dev/null 2>&1; then
  log_warn "tkinter is missing for $PYTHON_BIN"
  print_info "Attempting to install OS dependencies automatically"
  if "$SCRIPT_DIR/install_deps.sh"; then
    if ! "$PYTHON_BIN" -c "import tkinter" >/dev/null 2>&1; then
      echo "tkinter is still missing after dependency install." >&2
      echo "Install python3-tk manually and rebuild." >&2
      exit 1
    fi
    print_success "tkinter dependency installed successfully."
  else
    echo "Automatic dependency installation failed." >&2
    echo "Run ./scripts/install_deps.sh manually and rebuild." >&2
    exit 1
  fi
fi

if ! "$PYTHON_BIN" -c "import PyInstaller" >/dev/null 2>&1; then
  log_warn "pyinstaller not found; installing temporarily"
  "$PYTHON_BIN" -m pip install pyinstaller
fi

"$PYTHON_BIN" -m PyInstaller \
  --clean \
  --noconfirm \
  --name dir-sync \
  --windowed \
  --onefile \
  --hidden-import tkinter \
  --hidden-import tkinter.filedialog \
  --hidden-import tkinter.messagebox \
  src/dirsync/app.py
print_success "Artifacts available in dist/"
