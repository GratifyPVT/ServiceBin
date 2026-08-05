#!/usr/bin/env python3
"""
Monitor or simulate Pi serial traffic with the Arduino over USB-UART.

Usage on PC (Linux):
  python3 tools/serial_test.py --port /dev/ttyUSB0 --monitor

Simulate Pi reply when Arduino sends CAPTURE:
  python3 tools/serial_test.py --port /dev/ttyUSB0 --reply N
"""

import argparse
import sys
import time

import serial


def main():
    parser = argparse.ArgumentParser(description="Gratify UART test tool")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port path")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument(
        "--monitor", action="store_true", help="Print all lines from Arduino"
    )
    parser.add_argument(
        "--reply",
        choices=["B", "N", "M"],
        help="Auto-reply when CAPTURE is received",
    )
    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as exc:
        print(f"Could not open {args.port}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Listening on {args.port} @ {args.baud}")
    if args.reply:
        print(f"Will reply with {args.reply} on CAPTURE")
    if args.monitor:
        print("Monitor mode: printing all incoming lines (Ctrl+C to stop)")

    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            if args.monitor or args.reply:
                print(f"RX: {line}")

            if args.reply and line.upper() == "CAPTURE":
                ser.write((args.reply + "\n").encode())
                ser.flush()
                print(f"TX: {args.reply}")

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
