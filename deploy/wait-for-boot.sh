#!/usr/bin/env bash
# Wait for internet + Pi hardware before starting services after reboot.
set -euo pipefail

MODE="${1:-}"
INTERNET_WAIT="${2:-180}"
EXTRA_WAIT="${3:-90}"

wait_for() {
  local timeout="$1"
  local msg="$2"
  shift 2
  local deadline=$((SECONDS + timeout))
  echo "$msg (up to ${timeout}s)..."
  while (( SECONDS < deadline )); do
    if "$@"; then
      return 0
    fi
    sleep 3
  done
  return 1
}

internet_ready() {
  ping -c1 -W3 8.8.8.8 &>/dev/null || ping -c1 -W3 1.1.1.1 &>/dev/null
}

serial_ready() {
  compgen -G "/dev/ttyUSB*" > /dev/null \
    || compgen -G "/dev/ttyACM*" > /dev/null \
    || compgen -G "/dev/serial0" > /dev/null \
    || [[ -e /dev/serial0 ]]
}

display_ready() {
  # X11 socket or Wayland display for the graphical session
  [[ -S /tmp/.X11-unix/X0 ]] \
    || [[ -S /tmp/.X11-unix/X1 ]] \
    || [[ -n "${WAYLAND_DISPLAY:-}" ]] \
    || [[ -S /run/user/$(id -u)/wayland-0 ]] \
    || compgen -G "/run/user/*/wayland-0" > /dev/null
}

wait_for "$INTERNET_WAIT" "Waiting for internet" internet_ready || {
  echo "WARNING: internet not ready, continuing anyway"
}

case "$MODE" in
  garbage)
    if (( EXTRA_WAIT > 0 )); then
      if ! wait_for "$EXTRA_WAIT" "Waiting for Arduino serial port" serial_ready; then
        echo "WARNING: no serial port yet — GarbageDetection will use simulation if needed"
      fi
    fi
    ;;
  ads)
    if (( EXTRA_WAIT > 0 )); then
      if ! wait_for "$EXTRA_WAIT" "Waiting for desktop display" display_ready; then
        echo "WARNING: display not ready yet, continuing anyway"
      fi
    fi
    ;;
  waste|update)
    # Only needs internet (already waited above)
    ;;
  *)
    echo "Usage: $0 {garbage|ads|waste|update} [internet_wait_sec] [extra_wait_sec]" >&2
    exit 1
    ;;
esac

echo "Ready."
