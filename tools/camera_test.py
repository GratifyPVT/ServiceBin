#!/usr/bin/env python3
"""Capture from laptop camera and run one classification (no Arduino required)."""

import os
import sys
import time

import cv2

# Run from gratify/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from GarbageDetection.classifier import predict


def capture_frame(cap):
    for _ in range(config.CAMERA_FLUSH_FRAMES):
        cap.read()
    time.sleep(0.1)
    return cap.read()


def main():
    device = int(os.environ.get("GRATIFY_CAMERA", "0"))
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(f"Could not open camera {device}")
        raise SystemExit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("Model:", config.MODEL_PATH)
    print("Threshold:", config.CONFIDENCE_THRESHOLD)
    print("Warming up camera...")

    for _ in range(5):
        cap.read()

    ret, frame = capture_frame(cap)
    cap.release()

    if not ret:
        print("Camera read failed")
        raise SystemExit(1)

    result, cls, conf = predict(frame)
    print(f"\nResult: {cls} -> {result} (confidence {conf:.3f})")

    out_dir = config.IMAGE_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"camera_test_{cls}_{result}_{conf:.2f}.jpg")
    cv2.imwrite(path, frame)
    print("Saved:", path)


if __name__ == "__main__":
    main()
