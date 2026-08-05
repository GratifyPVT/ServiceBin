#!/bin/bash
# One-time fix so Python can open /dev/ttyUSB0 without sudo.
# Usage: sudo bash tools/fix_serial_permissions.sh

set -e
PORT="${1:-/dev/ttyUSB0}"
USER_NAME="${SUDO_USER:-$USER}"

usermod -aG dialout "$USER_NAME"
chmod 666 "$PORT" 2>/dev/null || true

echo "Added $USER_NAME to dialout group."
echo "Temporary access on $PORT granted until unplug."
echo "Log out and back in for dialout group to apply permanently."
