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

print_info "Installing dir-sync launcher to $TARGET"
mkdir -p "$BIN_DIR"

cat > "$TARGET" <<EOF
#!/usr/bin/env bash
set -euo pipefail
# Managed by dir-sync scripts/install.sh
ROOT_DIR="$ROOT_DIR"
export PYTHONPATH="\$ROOT_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m dirsync.app "\$@"
EOF

chmod +x "$TARGET"
print_success "Installed dir-sync launcher."

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  log_warn "$BIN_DIR is not in PATH."
  log_warn "Add this to your shell config: export PATH=\"$BIN_DIR:\$PATH\""
fi
