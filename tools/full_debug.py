#!/usr/bin/env python3
"""Full ATmega328P UART debug session: boot, EEPROM, N/B/M stepper tests."""

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial

from GarbageDetection.runtime import open_serial


def slurp(ser, seconds, label=""):
    if label:
        print(f"\n=== {label} ({seconds}s) ===")
    end = time.time() + seconds
    lines = []
    while time.time() < end:
        while ser.in_waiting:
            raw = ser.readline()
            line = raw.decode(errors="ignore").rstrip()
            if line:
                lines.append(line)
                print(f"  << {line}")
        time.sleep(0.02)
    return lines


def wait_idle(ser, quiet_sec=2.0, max_wait=20.0):
    print(f"Waiting for idle ({quiet_sec}s quiet)...")
    last_rx = time.time()
    end = time.time() + max_wait
    while time.time() < end:
        if ser.in_waiting:
            line = ser.readline().decode(errors="ignore").rstrip()
            if line:
                print(f"  << {line}")
            last_rx = time.time()
        elif time.time() - last_rx >= quiet_sec:
            print("Arduino idle.")
            return True
        time.sleep(0.05)
    print("Idle timeout — continuing anyway.")
    return False


def reset_arduino(ser):
    print("Resetting ATmega via DTR pulse...")
    ser.dtr = False
    time.sleep(0.1)
    ser.dtr = True
    time.sleep(0.1)
    ser.dtr = False
    ser.reset_input_buffer()


def read_eeprom_config(ser):
    print("\n--- EEPROM config (DEBUG menu) ---")
    ser.reset_input_buffer()
    ser.write(b"DEBUG\n")
    ser.flush()
    menu = slurp(ser, 3, "DEBUG menu")

    if not any("GRATIFY DEBUG" in l.upper() or "ROOF" in l.upper() for l in menu):
        print("  WARN: DEBUG menu not seen — retrying...")
        ser.write(b"DEBUG\n")
        ser.flush()
        menu = slurp(ser, 3, "DEBUG retry")

    ser.write(b"7")
    ser.flush()
    config_lines = slurp(ser, 3, "config option 7")

    ser.write(b"9")
    ser.flush()
    slurp(ser, 0.5)

    all_text = "\n".join(menu + config_lines)
    positions = {}
    for line in config_lines:
        m = re.search(r"(HOME|BIO|NONBIO)\s*:\s*(-?\d+)", line, re.I)
        if m:
            positions[m.group(1).upper()] = int(m.group(2))

    if positions:
        print("\n  Parsed positions:")
        for k in ("HOME", "BIO", "NONBIO"):
            if k in positions:
                print(f"    {k}: {positions[k]}")
        vals = list(positions.values())
        if len(vals) >= 3 and len(set(vals)) < 3:
            print("\n  *** BUG: HOME/BIO/NONBIO are equal — stepper cannot move! ***")
        elif positions.get("HOME") == positions.get("NONBIO"):
            print("\n  *** BUG: HOME == NONBIO — N command will never move stepper! ***")
    else:
        print("  Could not parse positions — use Arduino Serial Monitor: DEBUG then 7")

    return positions


def stepper_test(ser, letter, timeout=75):
    print(f"\n--- Stepper test: reply {letter} on CAPTURE ({timeout}s) ---")
    print("  >> Trigger a drop now (wave near sensor)...")
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
            dt = time.time() - t0
            print(f"  >> {letter} sent in {dt:.3f}s")
            print(f"  >> WATCH BOX: should move for {letter} (B=bio, N=nonbio, M=center)")
            slurp(ser, 12, "post-drop serial")
            return True
    print(f"  Timeout — no CAPTURE in {timeout}s")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()

    try:
        ser = open_serial(args.port)
    except serial.SerialException as exc:
        print(f"Serial failed: {exc}\nTry: sudo chmod 666 {args.port}")
        raise SystemExit(1)

    print(f"Port: {args.port} @ 9600")

    try:
        if not args.no_reset:
            reset_arduino(ser)
            slurp(ser, 18, "boot + homing (watch box move)")

        wait_idle(ser)
        read_eeprom_config(ser)

        wait_idle(ser, quiet_sec=3)
        stepper_test(ser, "N")

        wait_idle(ser, quiet_sec=5)
        stepper_test(ser, "B")

        wait_idle(ser, quiet_sec=5)
        stepper_test(ser, "M")

        print("\n=== DEBUG SESSION DONE ===")
        print("Report: did box move on N? on B? on M?")

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
