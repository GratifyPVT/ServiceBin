#!/usr/bin/env python3
"""
Full laptop test: listen for Arduino CAPTURE on USB-UART, classify via webcam, reply B/N/M.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

import config
from GarbageDetection.classifier import predict
from GarbageDetection.runtime import (
    CameraBuffer,
    drain_serial,
    open_serial,
    send_result,
    warmup_classifier,
)

PORT = os.environ.get("GRATIFY_SERIAL_PORT", "/dev/ttyUSB0")
CAMERA = int(os.environ.get("GRATIFY_CAMERA", "0"))
IMAGE_DIR = config.IMAGE_DIR


def main():
    print("Integrated test: UART + laptop camera")
    print("  serial:", PORT)
    print("  camera:", CAMERA)
    print("  model:", config.MODEL_PATH)
    print("  threshold:", config.CONFIDENCE_THRESHOLD)
    print("  arduino timeout:", config.ARDUINO_PI_TIMEOUT_SEC, "s")

    try:
        ser = open_serial(PORT)
    except Exception as exc:
        print(f"\nSerial open failed: {exc}")
        print("Fix: sudo chmod 666 /dev/ttyUSB0")
        print("Or:  docker run --rm --device=/dev/ttyUSB0 ... (see tools/serial_test.py)")
        raise SystemExit(1)

    warmup_classifier(predict)
    camera = CameraBuffer(CAMERA)
    drain_serial(ser)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    print("\nReady. Trigger Arduino — hold waste at laptop camera when roof closes.")
    print("Stepper only moves if B or N arrives within 5s.\n")

    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            print(f"RX: {line}")

            if line.upper() != "CAPTURE":
                continue

            t0 = time.time()
            ret, frame = camera.capture()
            if not ret:
                print("Camera failed -> sending M")
                send_result(ser, "M")
                continue

            result, cls, conf = predict(frame)
            elapsed = time.time() - t0
            print(f"  -> {cls} = {result} ({conf:.3f}) in {elapsed:.2f}s")

            if result in ("B", "N") and elapsed > config.ARDUINO_PI_TIMEOUT_SEC - 0.5:
                print("  WARNING: may miss Arduino 5s window — stepper might not move!")

            send_result(ser, result)
            print(f"TX: {result} (total {time.time() - t0:.2f}s)")

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(IMAGE_DIR, f"{ts}_{cls}_{result}_{conf:.2f}.jpg")
            cv2.imwrite(path, frame)
            print(f"  saved {path}\n")

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        camera.close()
        ser.close()


if __name__ == "__main__":
    main()
