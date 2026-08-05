#!/usr/bin/env python3
"""Interactive ATmega328P debugger over USB-UART (no firmware changes)."""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial

from GarbageDetection.runtime import open_serial


def read_lines(ser, seconds=2.0):
    end = time.time() + seconds
    lines = []
    while time.time() < end:
        if ser.in_waiting:
            line = ser.readline().decode(errors="ignore").rstrip()
            if line:
                lines.append(line)
                print(f"  << {line}")
        else:
            time.sleep(0.05)
    return lines


def enter_debug(ser):
    print("\n[1] Sending DEBUG...")
    ser.reset_input_buffer()
    ser.write(b"DEBUG\n")
    ser.flush()
    time.sleep(0.8)
    read_lines(ser, 2.0)


def read_config(ser):
    print("\n[2] Requesting config (key 7)...")
    ser.write(b"7")
    ser.flush()
    time.sleep(0.3)
    return read_lines(ser, 2.0)


def exit_debug(ser):
    print("\n[3] Exiting DEBUG (key 9)...")
    ser.write(b"9")
    ser.flush()
    time.sleep(0.3)
    read_lines(ser, 0.5)


def wait_boot(ser, timeout=15):
    print(f"Waiting up to {timeout}s for boot (GRATIFY READY)...")
    end = time.time() + timeout
    while time.time() < end:
        if ser.in_waiting:
            line = ser.readline().decode(errors="ignore").rstrip()
            if line:
                print(f"  << {line}")
                if "GRATIFY READY" in line.upper():
                    print("Boot complete.")
                    return True
        else:
            time.sleep(0.05)
    print("No GRATIFY READY seen (may already be running).")
    return False


def monitor_homing(ser, seconds=20):
    print(f"\nMonitoring serial for {seconds}s — power-cycle Arduino now if you want to watch homing...")
    read_lines(ser, seconds)


def capture_test(ser, letter="N", timeout=90):
    print(f"\nListening for CAPTURE — will reply {letter} instantly (trigger a drop)...")
    end = time.time() + timeout
    while time.time() < end:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        print(f"  << {line}")
        if line.upper() == "CAPTURE":
            t0 = time.time()
            ser.write((letter + "\n").encode())
            ser.flush()
            print(f"  >> {letter}  ({time.time() - t0:.3f}s after CAPTURE)")
            return True
    print("No CAPTURE received.")
    return False


def main():
    parser = argparse.ArgumentParser(description="ATmega328P serial debugger")
    parser.add_argument("--port", default=os.environ.get("GRATIFY_SERIAL_PORT", "/dev/ttyUSB0"))
    parser.add_argument("--boot", action="store_true", help="Monitor boot/homing messages")
    parser.add_argument("--config", action="store_true", help="Read DEBUG EEPROM positions")
    parser.add_argument("--test-n", action="store_true", help="Reply N on CAPTURE")
    parser.add_argument("--test-b", action="store_true", help="Reply B on CAPTURE")
    parser.add_argument("--all", action="store_true", help="Run boot wait + config + test N")
    args = parser.parse_args()

    if args.all:
        args.boot = args.config = args.test_n = True

    try:
        ser = open_serial(args.port)
    except serial.SerialException as exc:
        print(f"Cannot open {args.port}: {exc}")
        print("Run: sudo chmod 666 /dev/ttyUSB0")
        raise SystemExit(1)

    print(f"Open {args.port} @ 9600 (DTR off)")

    try:
        if args.boot:
            wait_boot(ser)
            monitor_homing(ser, 8)

        if args.config:
            enter_debug(ser)
            lines = read_config(ser)
            exit_debug(ser)

            text = "\n".join(lines)
            for key in ("HOME", "BIO", "NONBIO"):
                for line in lines:
                    if key in line.upper():
                        print(f"  CONFIG: {line.strip()}")

            if "HOME" in text and "NONBIO" in text:
                import re

                nums = re.findall(r":\s*(-?\d+)", text)
                if len(nums) >= 3:
                    home, bio, nonbio = map(int, nums[:3])
                    if home == nonbio or home == bio or bio == nonbio:
                        print("\n  *** PROBLEM: positions are equal — stepper will NOT move! ***")
                    if nonbio != 4600 or home != 2200 or bio != 0:
                        print("\n  NOTE: values differ from factory defaults (2200 / 0 / 4600)")

        if args.test_n:
            capture_test(ser, "N")
        if args.test_b:
            capture_test(ser, "B")

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
