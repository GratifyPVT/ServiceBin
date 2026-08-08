import glob
import os
import queue
import subprocess
import threading
import time

import numpy as np
import serial

import config

# Prefer shared config (GRATIFY_SERIAL_PORT / /dev/serial0), then USB, then Pi UART
DEFAULT_UART_PORT = config.SERIAL_PORT

PI_UART_PORTS = ("/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0")
CAMERA_CAPTURE_WAIT_SEC = 0.35
UART_REPLY_MARGIN_SEC = 0.35
UART_REPLY_TIMEOUT_SEC = float(
    os.environ.get("GRATIFY_UART_TIMEOUT", str(config.ARDUINO_PI_TIMEOUT_SEC))
)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480


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
    """Open the first usable serial port."""
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
    """Keep latest webcam frame ready using system ffmpeg (no OpenCV)."""

    def __init__(self, device=0):
        if isinstance(device, int):
            self._device = f"/dev/video{device}"
        else:
            self._device = str(device)

        if not os.path.exists(self._device):
            raise RuntimeError(f"Camera device missing: {self._device}")

        self._w = CAMERA_WIDTH
        self._h = CAMERA_HEIGHT
        self._frame_nbytes = self._w * self._h * 3
        self._proc = None
        self._lock = threading.Lock()
        self._latest = None
        self._frame_id = 0
        self._stop = threading.Event()
        self._open_capture()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        if not self._wait_for_frame(timeout=8.0):
            raise RuntimeError(f"Camera {self._device} opened but no frames received")

    def _open_capture(self):
        if self._proc is not None:
            self._proc.kill()
            try:
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "v4l2",
            "-video_size",
            f"{self._w}x{self._h}",
            "-i",
            self._device,
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-an",
            "-",
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self._frame_nbytes * 2,
        )
        print(f"Camera open via ffmpeg: {self._device} ({self._w}x{self._h})")

    def _wait_for_frame(self, timeout=2.0):
        end = time.time() + timeout
        while time.time() < end:
            with self._lock:
                if self._latest is not None:
                    return True
            time.sleep(0.05)
        return False

    def _read_frame(self):
        if self._proc is None or self._proc.stdout is None:
            return None
        buf = b""
        while len(buf) < self._frame_nbytes:
            chunk = self._proc.stdout.read(self._frame_nbytes - len(buf))
            if not chunk:
                return None
            buf += chunk
        return np.frombuffer(buf, dtype=np.uint8).reshape((self._h, self._w, 3)).copy()

    def _recover_capture(self):
        with self._lock:
            self._latest = None
        time.sleep(0.25)
        self._open_capture()
        print("Camera reopened after read failure")

    def _worker(self):
        failures = 0
        # Discard a few frames (flush)
        for _ in range(max(0, int(config.SERIAL_CAPTURE_FLUSH))):
            self._read_frame()

        while not self._stop.is_set():
            frame = self._read_frame()
            if frame is not None:
                failures = 0
                with self._lock:
                    self._latest = frame
                    self._frame_id += 1
            else:
                failures += 1
                if failures >= 5:
                    failures = 0
                    try:
                        self._recover_capture()
                    except Exception as exc:
                        print("Camera recovery failed:", exc)
                        time.sleep(0.5)

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
        if self._thread is not None:
            self._thread.join(timeout=1)
        if self._proc is not None:
            self._proc.kill()
            try:
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None


def warmup_classifier(predict_fn):
    """First TFLite invoke is slower; run before CAPTURE arrives on UART."""
    dummy = np.zeros((CAMERA_HEIGHT, CAMERA_WIDTH, 3), dtype=np.uint8)
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
