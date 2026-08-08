#!/usr/bin/env bash
# Install Gratify systemd services so they start automatically on boot.
# Prefers: CONDA_PYTHON override → ~/gratify-venv → conda env (default: mf).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRATIFY_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
GRATIFY_USER="${SUDO_USER:-${GRATIFY_USER:-$(whoami)}}"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-mf}"
SYSTEMD_DIR="/etc/systemd/system"

SERVICES=(
  gratify-update.service
  gratify-garbage.service
  gratify-ads.service
  gratify-waste.service
)

find_python() {
  local user="$1"
  local env="$2"
  local home
  home="$(getent passwd "$user" | cut -d: -f6)"

  if [[ -n "${CONDA_PYTHON:-}" && -x "$CONDA_PYTHON" ]]; then
    echo "$CONDA_PYTHON"
    return 0
  fi

  # PI_SETUP.md path — preferred on Raspberry Pi
  if [[ -x "$home/gratify-venv/bin/python" ]]; then
    echo "$home/gratify-venv/bin/python"
    return 0
  fi

  # Project-local venv
  if [[ -x "$GRATIFY_HOME/.venv/bin/python" ]]; then
    echo "$GRATIFY_HOME/.venv/bin/python"
    return 0
  fi

  local py=""
  py="$(sudo -u "$user" bash -lc "command -v conda >/dev/null && conda run -n $env which python 2>/dev/null" || true)"
  if [[ -n "$py" && -x "$py" ]]; then
    echo "$py"
    return 0
  fi

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

if ! CONDA_PYTHON="$(find_python "$GRATIFY_USER" "$CONDA_ENV_NAME")"; then
  echo "Error: no Python env found for user $GRATIFY_USER"
  echo "Create one (recommended on Pi):"
  echo "  python3 -m venv \$HOME/gratify-venv"
  echo "  source \$HOME/gratify-venv/bin/activate"
  echo "  pip install -r $GRATIFY_HOME/requirements.txt"
  echo "Or set path manually:"
  echo "  CONDA_PYTHON=/path/to/env/bin/python bash deploy/install-services.sh"
  exit 1
fi

if [[ ! -f "$GRATIFY_HOME/GarbageDetection/main.py" ]]; then
  echo "Error: GarbageDetection/main.py missing under $GRATIFY_HOME"
  echo "The ML service cannot start without it."
  exit 1
fi

if [[ ! -f "$GRATIFY_HOME/GarbageDetection/model/rls_mobilenetv3_mish_cbam_float16.tflite" \
   && ! -f "$GRATIFY_HOME/GarbageDetection/model/model.tflite" ]]; then
  echo "Error: no TFLite model in GarbageDetection/model/"
  echo "Expected: rls_mobilenetv3_mish_cbam_float16.tflite (or model.tflite)"
  exit 1
fi

USER_HOME="$(getent passwd "$GRATIFY_USER" | cut -d: -f6)"
echo "Using python: $CONDA_PYTHON"
echo "User home:   $USER_HOME"

chmod +x "$GRATIFY_HOME/deploy/wait-for-boot.sh" "$GRATIFY_HOME/deploy/update-from-github.sh"

# Ensure runtime dirs exist and are writable by the service user
install -d -o "$GRATIFY_USER" -g "$GRATIFY_USER" \
  "$GRATIFY_HOME/WasteManagement/images" \
  "$GRATIFY_HOME/AdsManagement/videos"

render() {
  local src="$1"
  local dest="$2"
  sed \
    -e "s|@GRATIFY_HOME@|$GRATIFY_HOME|g" \
    -e "s|@GRATIFY_USER@|$GRATIFY_USER|g" \
    -e "s|@CONDA_PYTHON@|$CONDA_PYTHON|g" \
    -e "s|@USER_HOME@|$USER_HOME|g" \
    "$src" > "$dest"
}

echo "Installing services for user=$GRATIFY_USER home=$GRATIFY_HOME"

render "$SCRIPT_DIR/systemd/gratify-update.service" "$SYSTEMD_DIR/gratify-update.service"
render "$SCRIPT_DIR/systemd/gratify-garbage.service" "$SYSTEMD_DIR/gratify-garbage.service"
render "$SCRIPT_DIR/systemd/gratify-ads.service" "$SYSTEMD_DIR/gratify-ads.service"
render "$SCRIPT_DIR/systemd/gratify-waste.service" "$SYSTEMD_DIR/gratify-waste.service"

systemctl daemon-reload
systemctl enable "${SERVICES[@]}"

# Ensure graphical target is default so ads can start on a Pi desktop image
if systemctl list-unit-files graphical.target &>/dev/null; then
  current="$(systemctl get-default || true)"
  if [[ "$current" != "graphical.target" ]]; then
    echo "NOTE: default target is '$current' (ads need graphical.target + desktop autologin)"
  fi
fi

systemctl restart gratify-update.service || true
systemctl restart gratify-garbage.service gratify-ads.service gratify-waste.service

echo ""
echo "Done. Services enabled and started."
echo "Boot order: update-from-github → garbage + ads + waste (ML loads with garbage)"
echo "  sudo systemctl status gratify-update gratify-garbage gratify-ads gratify-waste"
echo "  journalctl -u gratify-garbage -f"
