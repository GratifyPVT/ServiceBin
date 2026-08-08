import glob
import os
import queue
import threading
import time

import serial

import config

# Prefer shared config (GRATIFY_SERIAL_PORT / /dev/serial0), then USB, then Pi UART
DEFAULT_UART_PORT = config.SERIAL_PORT

# Optional fallbacks if the default path is missing
PI_UART_PORTS = ("/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0")
CAMERA_CAPTURE_WAIT_SEC = 0.35
UART_REPLY_MARGIN_SEC = 0.35
UART_REPLY_TIMEOUT_SEC = float(
    os.environ.get("GRATIFY_UART_TIMEOUT", str(config.ARDUINO_PI_TIMEOUT_SEC))
)


def _candidate_ports(preferred=None):
    """Preferred port first, then USB adapters, then Pi onboard UART."""
    preferred = preferred or DEFAULT_UART_PORT
    candidates = []
    if preferred:
        candidates.append(preferred)
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*"):
        for path in sorted(glob.glob(pattern)):
            if path not in candidates:
                candidates.append(path)
    for path in PI_UART_PORTS:
        if path not in candidates:
            candidates.append(path)
    return candidates


def find_serial_port():
    """Return the first existing serial device path."""
    for path in _candidate_ports():
        if os.path.exists(path):
            return path
    return None


def pick_serial_port(preferred=None):
    """Open the first usable serial port (defaults to /dev/ttyUSB0 on Pi)."""
    errors = []
    for candidate in _candidate_ports(preferred):
        if not os.path.exists(candidate):
            continue
        try:
            probe = serial.Serial(
                candidate,
                config.BAUD_RATE,
                timeout=0.1,
                dsrdtr=False,
                rtscts=False,
            )
            probe.dtr = False
            probe.close()
            time.sleep(0.1)
            return candidate
        except serial.SerialException as exc:
            errors.append(f"{candidate}: {exc}")

    tried = ", ".join(_candidate_ports(preferred)) or "(none found)"
    detail = "; ".join(errors) if errors else "no serial devices found"
    raise serial.SerialException(
        f"Could not open serial port ({detail}). Tried: {tried}. "
        "Check USB cable, run: ls -l /dev/ttyUSB* "
        "and: sudo usermod -aG dialout $USER"
    )


def open_serial(port=None, baud=None):
    """Open USB/UART serial link to the dustbin controller."""
    chosen = pick_serial_port(port)
    baud = baud or config.BAUD_RATE
    preferred = port or DEFAULT_UART_PORT

    ser = serial.Serial(chosen, baud, timeout=0.1, dsrdtr=False, rtscts=False)
    ser.dtr = False
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    if chosen != preferred:
        print(f"UART {preferred} unavailable — using {chosen}")
    else:
        print(f"UART open: {chosen} @ {baud}")

    return ser


def verify_serial_link(ser, timeout=3.0):
    """Legacy helper used by debug tools."""
    print(f"UART ready on {ser.port}")
    return True


def drain_serial(ser, timeout=1.0):
    end = time.time() + timeout
    while time.time() < end:
        if ser.in_waiting:
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                print("UART (drain):", line)
        else:
            time.sleep(0.05)


def send_result(ser, result):
    if ser and ser.is_open:
        ser.write((result + "\n").encode())
        ser.flush()
    else:
        print("Simulated send:", result)


class SerialListener:
    """Background Pi UART reader — keeps listening while camera/ML runs."""

    def __init__(self, port=None, baud=None):
        self._port_hint = port
        self._baud = baud or config.BAUD_RATE
        self.ser = None
        self._captures = queue.Queue()
        self._stop = threading.Event()
        self._thread = None

    @property
    def port(self):
        return self.ser.port if self.ser else self._port_hint

    def start(self):
        self.ser = open_serial(self._port_hint)
        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        print("UART listener running — waiting for CAPTURE")

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
            except (serial.SerialException, OSError) as exc:
                print("UART read error:", exc)
                time.sleep(0.2)
                continue

            if not line:
                continue

            print("UART RX:", line)
            if line.upper() == "CAPTURE":
                self._captures.put(time.time())

    def wait_capture(self, timeout=0.25):
        try:
            return self._captures.get(timeout=timeout)
        except queue.Empty:
            return None

    def pending_captures(self):
        return self._captures.qsize()

    def send(self, result):
        send_result(self.ser, result)

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        close_serial(self.ser)
        self.ser = None


class CameraBuffer:
    """Keep the latest Pi camera frame ready so UART replies stay within 5s."""

    def __init__(self, device=0):
        import cv2

        self._cv2 = cv2
        self._device = device
        self._cap = self._open_capture(device)
        self._lock = threading.Lock()
        self._latest = None
        self._frame_id = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        if not self._wait_for_frame(timeout=5.0):
            raise RuntimeError(f"Camera {device} opened but no frames received")

    def _open_capture(self, device):
        cap = None
        for backend in (self._cv2.CAP_V4L2, self._cv2.CAP_ANY):
            try:
                cap = self._cv2.VideoCapture(device, backend)
            except Exception:
                cap = self._cv2.VideoCapture(device)
            if cap is not None and cap.isOpened():
                break
            if cap is not None:
                cap.release()
            cap = None

        if cap is None or not cap.isOpened():
            raise RuntimeError(f"Camera {device} failed to open")

        cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 480)
        try:
            cap.set(self._cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        for _ in range(max(0, int(config.SERIAL_CAPTURE_FLUSH))):
            cap.read()

        return cap

    def _wait_for_frame(self, timeout=2.0):
        end = time.time() + timeout
        while time.time() < end:
            with self._lock:
                if self._latest is not None:
                    return True
            time.sleep(0.05)
        return False

    def _recover_capture(self):
        with self._lock:
            if self._cap is not None:
                self._cap.release()
            self._latest = None

        time.sleep(0.25)
        self._cap = self._open_capture(self._device)
        print("Camera reopened after read failure")

    def _worker(self):
        failures = 0
        while not self._stop.is_set():
            ret, frame = self._cap.read()
            if ret:
                failures = 0
                with self._lock:
                    self._latest = frame.copy()
                    self._frame_id += 1
            else:
                failures += 1
                if failures >= 20:
                    failures = 0
                    try:
                        self._recover_capture()
                    except Exception as exc:
                        print("Camera recovery failed:", exc)
                        time.sleep(0.5)
            time.sleep(0.005)

    def capture(self, max_wait=None):
        max_wait = max_wait if max_wait is not None else CAMERA_CAPTURE_WAIT_SEC

        with self._lock:
            start_id = self._frame_id

        end = time.time() + max_wait
        while time.time() < end:
            with self._lock:
                if self._frame_id > start_id and self._latest is not None:
                    return True, self._latest.copy()
            time.sleep(0.01)

        with self._lock:
            if self._latest is not None:
                return True, self._latest.copy()

        return False, None

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def warmup_classifier(predict_fn):
    """First TFLite invoke is slower; run before CAPTURE arrives on UART."""
    import numpy as np

    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    predict_fn(dummy)
    print("Model warmup done")


def close_serial(ser):
    if ser and ser.is_open:
        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception:
            pass
        ser.close()
        time.sleep(0.1)


def capture_deadline(t_capture):
    return t_capture + UART_REPLY_TIMEOUT_SEC - UART_REPLY_MARGIN_SEC
