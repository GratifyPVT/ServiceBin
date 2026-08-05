#!/usr/bin/env python3
"""
Read Arduino EEPROM positions via DEBUG menu (no firmware change).
Also useful to confirm serial link after 'GRATIFY READY'.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GarbageDetection.runtime import drain_serial, open_serial


def main():
    port = os.environ.get("GRATIFY_SERIAL_PORT", "/dev/ttyUSB0")
    ser = open_serial(port)
    time.sleep(2)  # wait for boot + homing after USB connect
    drain_serial(ser, timeout=2)

    print("Entering DEBUG mode...")
    ser.write(b"DEBUG\n")
    time.sleep(0.5)

    print("Requesting config (menu option 7)...")
    ser.write(b"7")
    time.sleep(1)

    lines = []
    while ser.in_waiting:
        lines.append(ser.readline().decode(errors="ignore").rstrip())

    print("\n--- Arduino config ---")
    for line in lines:
        if line:
            print(line)

    print("\nExiting DEBUG (option 9)...")
    ser.write(b"9")
    time.sleep(0.3)
    ser.close()

    print("\nIf HOME, BIO, NONBIO are equal or zero, EEPROM positions need calibration.")
    print("If stepper never moves on N/B, check limit switches on pins 3 (HOME) and 4 (END).")


if __name__ == "__main__":
    main()
