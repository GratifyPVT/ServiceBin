import os
import sys
import time
from datetime import datetime

from PIL import Image

import config
from GarbageDetection.classifier import predict
from GarbageDetection.runtime import (
    DEFAULT_UART_PORT,
    UART_REPLY_TIMEOUT_SEC,
    CameraBuffer,
    SerialListener,
    capture_deadline,
    find_serial_port,
    warmup_classifier,
)

IMAGE_DIR = config.IMAGE_DIR
USE_SIMULATION = config.USE_SIMULATION
CAMERA_DEVICE = int(os.environ.get("GRATIFY_CAMERA", "0"))

serial_listener = None
camera = None


def _shutdown():
    global serial_listener, camera
    if camera is not None:
        camera.close()
        camera = None
    if serial_listener is not None:
        serial_listener.close()
        serial_listener = None


def _save_frame(frame, cls, result, conf):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{cls}_{result}_{conf:.2f}.jpg"
    filepath = os.path.join(IMAGE_DIR, filename)
    # frame is BGR uint8
    rgb = frame[:, :, ::-1]
    Image.fromarray(rgb).save(filepath, format="JPEG", quality=85)
    print("Saved:", filename, "\n")


def _send(result):
    if serial_listener is not None:
        serial_listener.send(result)
    else:
        print("Simulated send:", result)


def _handle_capture(t_capture):
    global serial_listener, camera

    deadline = capture_deadline(t_capture)
    remaining = deadline - time.time()
    if remaining <= 0:
        print("CAPTURE too late — sending M")
        _send("M")
        return "M", "timeout", 0.0, None

    print(f"Running ML... ({remaining:.1f}s left before {UART_REPLY_TIMEOUT_SEC:.0f}s UART window)")
    t0 = time.time()

    ret, frame = camera.capture()
    if not ret or frame is None:
        print("Camera read failed — sending M")
        _send("M")
        return "M", "camera_error", 0.0, None

    result, cls, conf = predict(frame)
    elapsed = time.time() - t0

    if time.time() > deadline:
        print(
            f"WARNING: ML took {elapsed:.2f}s — reply may miss the "
            f"{UART_REPLY_TIMEOUT_SEC:.0f}s window; stepper may not move"
        )

    print(f"{cls} -> {result} ({conf:.2f}) in {elapsed:.2f}s")

    if result in ("B", "N") and elapsed > UART_REPLY_TIMEOUT_SEC - 0.5:
        print(
            f"WARNING: reply took {elapsed:.2f}s; controller timeout is "
            f"{UART_REPLY_TIMEOUT_SEC:.0f}s — stepper may not move"
        )
    elif result == "M":
        print("NOTE: M sent — controller drops at HOME (no stepper move to B/N).")

    _send(result)
    print(f"UART TX: {result} (total {time.time() - t0:.2f}s)")
    return result, cls, conf, frame


def _run():
    global serial_listener, camera, USE_SIMULATION

    uart_port = find_serial_port() or DEFAULT_UART_PORT
    if not USE_SIMULATION and find_serial_port() is None:
        # Under systemd there is no interactive stdin — keep retrying for serial.
        if not sys.stdin.isatty():
            print("WARNING: no serial device yet — waiting (service will keep running)")
            while find_serial_port() is None:
                time.sleep(5)
            uart_port = find_serial_port()
            print("Serial appeared:", uart_port)
        else:
            print("WARNING: no serial device found — falling back to simulation mode")
            USE_SIMULATION = True

    print("Gratify Garbage Detection (Raspberry Pi)")
    print("  simulation:", USE_SIMULATION)
    print("  uart:", uart_port if not USE_SIMULATION else "n/a")
    print("  camera:", CAMERA_DEVICE)
    print("  model:", config.MODEL_PATH)
    if os.path.isfile(config.MODEL_PATH):
        print("  model size:", round(os.path.getsize(config.MODEL_PATH) / (1024 * 1024), 2), "MB")
    else:
        print("  WARNING: model file missing")
    print("  threshold:", config.CONFIDENCE_THRESHOLD)
    print("  uart reply window:", UART_REPLY_TIMEOUT_SEC, "s")

    warmup_classifier(predict)
    camera = CameraBuffer(CAMERA_DEVICE)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    if not USE_SIMULATION:
        serial_listener = SerialListener()
        serial_listener.start()

    if USE_SIMULATION:
        print("System ready. Type CAPTURE to trigger (simulation).\n")
    else:
        print("System ready. Waiting for CAPTURE on serial.")
        print("Reply B or N within 5s to move stepper; M keeps bin at HOME.\n")

    while True:
        try:
            if USE_SIMULATION:
                msg = input("Enter 'CAPTURE' to trigger: ").strip()
                if msg.upper() != "CAPTURE":
                    continue
                t_capture = time.time()
            else:
                t_capture = serial_listener.wait_capture(timeout=0.25)
                if t_capture is None:
                    continue

            result, cls, conf, frame = _handle_capture(t_capture)
            if frame is not None and cls not in ("timeout", "camera_error"):
                _save_frame(frame, cls, result, conf)

            if not USE_SIMULATION:
                while serial_listener.pending_captures():
                    stale = serial_listener.wait_capture(timeout=0)
                    if stale is None:
                        break
                    print("Queued CAPTURE — processing next")
                    result, cls, conf, frame = _handle_capture(stale)
                    if frame is not None and cls not in ("timeout", "camera_error"):
                        _save_frame(frame, cls, result, conf)

        except Exception as e:
            print("Error:", e)
            _send("M")


def main():
    try:
        _run()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
