#!/usr/bin/env bash
# Install Gratify systemd services so they start automatically on boot.
# Uses conda env mf by default (override with CONDA_ENV_NAME=tfenv).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRATIFY_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
GRATIFY_USER="${SUDO_USER:-$(whoami)}"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-mf}"
SYSTEMD_DIR="/etc/systemd/system"

SERVICES=(
  gratify-update.service
  gratify-garbage.service
  gratify-ads.service
  gratify-waste.service
)

find_conda_python() {
  local user="$1"
  local env="$2"

  if [[ -n "${CONDA_PYTHON:-}" && -x "$CONDA_PYTHON" ]]; then
    echo "$CONDA_PYTHON"
    return 0
  fi

  local py=""
  py="$(sudo -u "$user" bash -lc "conda run -n $env which python 2>/dev/null" || true)"
  if [[ -n "$py" && -x "$py" ]]; then
    echo "$py"
    return 0
  fi

  local home
  home="$(getent passwd "$user" | cut -d: -f6)"
  local base
  for base in \
    "$home/miniconda3" \
    "$home/anaconda3" \
    "$home/mambaforge" \
    "$home/miniforge3" \
    "/opt/conda"; do
    if [[ -x "$base/envs/$env/bin/python" ]]; then
      echo "$base/envs/$env/bin/python"
      return 0
    fi
  done

  return 1
}

if [[ "$EUID" -ne 0 ]]; then
  echo "Re-running with sudo..."
  exec sudo GRATIFY_USER="$GRATIFY_USER" CONDA_ENV_NAME="$CONDA_ENV_NAME" \
    CONDA_PYTHON="${CONDA_PYTHON:-}" bash "$0" "$@"
fi

if ! CONDA_PYTHON="$(find_conda_python "$GRATIFY_USER" "$CONDA_ENV_NAME")"; then
  echo "Error: conda env '$CONDA_ENV_NAME' not found for user $GRATIFY_USER"
  echo "Create it first:  conda create -n $CONDA_ENV_NAME python=3.12"
  echo "Or set path manually:  CONDA_PYTHON=/path/to/env/bin/python bash deploy/install-services.sh"
  exit 1
fi

echo "Using conda python: $CONDA_PYTHON ($CONDA_ENV_NAME)"

chmod +x "$GRATIFY_HOME/deploy/wait-for-boot.sh" "$GRATIFY_HOME/deploy/update-from-github.sh"

render() {
  local src="$1"
  local dest="$2"
  sed \
    -e "s|@GRATIFY_HOME@|$GRATIFY_HOME|g" \
    -e "s|@GRATIFY_USER@|$GRATIFY_USER|g" \
    -e "s|@CONDA_PYTHON@|$CONDA_PYTHON|g" \
    "$src" > "$dest"
}

echo "Installing services for user=$GRATIFY_USER home=$GRATIFY_HOME"

render "$SCRIPT_DIR/systemd/gratify-update.service" "$SYSTEMD_DIR/gratify-update.service"
render "$SCRIPT_DIR/systemd/gratify-garbage.service" "$SYSTEMD_DIR/gratify-garbage.service"
render "$SCRIPT_DIR/systemd/gratify-ads.service" "$SYSTEMD_DIR/gratify-ads.service"
render "$SCRIPT_DIR/systemd/gratify-waste.service" "$SYSTEMD_DIR/gratify-waste.service"

systemctl daemon-reload
systemctl enable "${SERVICES[@]}"
systemctl restart gratify-update.service
systemctl restart gratify-garbage.service gratify-ads.service gratify-waste.service

echo ""
echo "Done. Services enabled and started (conda env: $CONDA_ENV_NAME)."
echo "Boot order: update-from-github → garbage + ads + waste"
echo "  sudo systemctl status gratify-update gratify-garbage gratify-ads gratify-waste"
echo "  journalctl -u gratify-update -f"
