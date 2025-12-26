#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_HELPERS_DIR="${SCRIPT_HELPERS_DIR:-$SCRIPT_DIR/script-helpers}"
# shellcheck source=/dev/null
source "$SCRIPT_HELPERS_DIR/helpers.sh"
shlib_import logging docker

PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_IMAGE="${PYTHON_IMAGE:-python:3.11-slim}"
PIP_CACHE_DIR="${PIP_CACHE_DIR:-$HOME/.cache/pip}"
HOST_UID="${HOST_UID:-$(id -u)}"
HOST_GID="${HOST_GID:-$(id -g)}"

print_info "Running tests inside Docker ($PYTHON_IMAGE)"
check_docker || exit 1

DOCKER_VOLUMES=(-v "$PROJECT_ROOT":/workspace)
[[ -d "$PIP_CACHE_DIR" ]] && DOCKER_VOLUMES+=(-v "$PIP_CACHE_DIR":/root/.cache/pip)

docker run --rm -t \
  -w /workspace \
  -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
  -e HOST_UID="$HOST_UID" \
  -e HOST_GID="$HOST_GID" \
  "${DOCKER_VOLUMES[@]}" \
  "$PYTHON_IMAGE" /bin/bash -s -- "$@" <<'EOF'
set -euo pipefail
PYTEST_ARGS=("$@")

apt-get update >/dev/null
apt-get install -y --no-install-recommends build-essential rsync >/dev/null

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e .[dev] >/dev/null

python -m pytest "${PYTEST_ARGS[@]}"

if [[ -n "${HOST_UID:-}" && -n "${HOST_GID:-}" ]]; then
  chown -R "$HOST_UID:$HOST_GID" .venv || true
fi
EOF
