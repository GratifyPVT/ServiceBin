import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Set GRATIFY_SIMULATION=1 for keyboard testing without Arduino
USE_SIMULATION = os.environ.get("GRATIFY_SIMULATION", "0").lower() in ("1", "true", "yes")

SERIAL_PORT = os.environ.get("GRATIFY_SERIAL_PORT", "/dev/serial0")
BAUD_RATE = 9600

_MODEL_FLOAT16 = os.path.join(
    BASE_DIR, "GarbageDetection", "model", "rls_mobilenetv3_mish_cbam_float16.tflite"
)
_MODEL_LEGACY = os.path.join(BASE_DIR, "GarbageDetection", "model", "model.tflite")
MODEL_PATH = _MODEL_FLOAT16 if os.path.isfile(_MODEL_FLOAT16) else _MODEL_LEGACY

IMAGE_DIR = os.environ.get(
    "GRATIFY_IMAGE_DIR", os.path.join(BASE_DIR, "WasteManagement", "images")
)
VIDEO_DIR = os.path.join(BASE_DIR, "AdsManagement", "videos")

BIN_ID = "69dc815589f10ee239238d51"
WASTE_API_URL = "https://gratify-ads-management.vercel.app/api/uploadwaste"
ADS_API_URL = "https://gratify-ads-management.vercel.app/api/videos/" + BIN_ID

CLASSES = ["biodegradable", "e-waste", "glass", "metal", "paper", "plastic"]

CATEGORY_MAPPING = {
    "biodegradable": "B",
    "e-waste": "M",
    "glass": "N",
    "metal": "N",
    "paper": "N",
    "plastic": "N",
}

CONFIDENCE_THRESHOLD = float(os.environ.get("GRATIFY_CONFIDENCE_THRESHOLD", "0.45"))
TFLITE_NUM_THREADS = int(os.environ.get("GRATIFY_TFLITE_THREADS", "2"))
CAMERA_FLUSH_FRAMES = 8
# Fewer flushes when Arduino is waiting (5s PI_TIMEOUT on MCU)
SERIAL_CAPTURE_FLUSH = int(os.environ.get("GRATIFY_SERIAL_CAPTURE_FLUSH", "2"))
ARDUINO_PI_TIMEOUT_SEC = 5.0
# Cooldown only applies in simulation; serial mode must always reply
COOLDOWN_SEC = float(os.environ.get("GRATIFY_COOLDOWN", "0"))
