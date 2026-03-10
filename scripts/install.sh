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

ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_DIR="${DIRSYNC_BIN_DIR:-$HOME/.local/bin}"
TARGET="$BIN_DIR/dir-sync"
VENV_DIR="${DIRSYNC_VENV_DIR:-$ROOT_DIR/.venv}"

ensure_runtime_env() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    print_info "Creating runtime virtualenv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi

  local runtime_python="$VENV_DIR/bin/python"
  if ! "$runtime_python" -c "import dirsync, croniter, yaml, psutil, pystray, PIL, plyer" >/dev/null 2>&1; then
    print_info "Installing dir-sync runtime dependencies into $VENV_DIR"
    "$runtime_python" -m pip install -U pip
    "$runtime_python" -m pip install -e "$ROOT_DIR"
  fi
}

print_info "Installing dir-sync launcher to $TARGET"
mkdir -p "$BIN_DIR"
ensure_runtime_env

cat > "$TARGET" <<EOF
#!/usr/bin/env bash
set -euo pipefail
# Managed by dir-sync scripts/install.sh
ROOT_DIR="$ROOT_DIR"
export PYTHONPATH="\$ROOT_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$VENV_DIR/bin/python" -m dirsync.app "\$@"
EOF

chmod +x "$TARGET"
print_success "Installed dir-sync launcher."

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  log_warn "$BIN_DIR is not in PATH."
  log_warn "Add this to your shell config: export PATH=\"$BIN_DIR:\$PATH\""
fi
