#!/usr/bin/env python3
"""Send B/N/M over UART to verify stepper routing (no camera/ML)."""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial

from GarbageDetection.runtime import drain_serial, open_serial, send_result


def main():
    parser = argparse.ArgumentParser(description="Send a single B/N/M command to Arduino")
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--letter", choices=["B", "N", "M"], required=True)
    parser.add_argument(
        "--wait-capture",
        action="store_true",
        help="Wait for CAPTURE from Arduino, then reply (like Pi)",
    )
    parser.add_argument(
        "--loops",
        type=int,
        default=1,
        help="How many CAPTURE cycles to answer (use with --wait-capture)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Seconds to wait for each CAPTURE",
    )
    args = parser.parse_args()

    try:
        ser = open_serial(args.port)
    except serial.SerialException as exc:
        print(f"Cannot open {args.port}: {exc}", file=sys.stderr)
        print("Try: sudo chmod 666 /dev/ttyUSB0", file=sys.stderr)
        raise SystemExit(1)

    drain_serial(ser, timeout=0.5)

    if args.wait_capture:
        print(f"Listening {args.timeout}s x {args.loops} — trigger Arduino (no camera/ML)")
        print(f"Will reply with: {args.letter}\n")
        answered = 0
        while answered < args.loops:
            end = time.time() + args.timeout
            while time.time() < end:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                print("RX:", line)
                if line.upper() == "CAPTURE":
                    send_result(ser, args.letter)
                    answered += 1
                    print(f"TX: {args.letter} (#{answered}) — stepper should move\n")
                    break
            else:
                print("Timeout waiting for CAPTURE")
                break
    else:
        send_result(ser, args.letter)
        print(f"Sent {args.letter}")

    ser.close()


if __name__ == "__main__":
    main()
