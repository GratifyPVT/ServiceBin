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
  compgen -G "/dev/ttyUSB*" > /dev/null || compgen -G "/dev/serial0" > /dev/null
}

display_ready() {
  [[ -S /tmp/.X11-unix/X0 ]] || [[ -S /tmp/.X11-unix/X1 ]]
}

wait_for "$INTERNET_WAIT" "Waiting for internet" internet_ready

case "$MODE" in
  garbage)
    wait_for "$EXTRA_WAIT" "Waiting for Arduino serial port" serial_ready
    ;;
  ads)
    wait_for "$EXTRA_WAIT" "Waiting for desktop display" display_ready
    ;;
  *)
    echo "Usage: $0 {garbage|ads} [internet_wait_sec] [extra_wait_sec]" >&2
    exit 1
    ;;
esac

echo "Ready."
