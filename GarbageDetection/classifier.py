"""TFLite waste classifier for Raspberry Pi (no OpenCV — Trixie-safe)."""
import os

import numpy as np
from PIL import Image

import config

INPUT_SIZE = 224


def _load_interpreter(model_path):
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        try:
            from tensorflow.lite.python.interpreter import Interpreter
        except ImportError as exc:
            raise ImportError(
                "Need tflite-runtime in the ML Python 3.11 venv. "
                "See ml.txt"
            ) from exc

    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    interpreter = Interpreter(
        model_path=model_path,
        num_threads=max(1, int(config.TFLITE_NUM_THREADS)),
    )
    interpreter.allocate_tensors()
    return interpreter


_INTERPRETER = None
_INPUT = None
_OUTPUT = None


def _get_interpreter():
    global _INTERPRETER, _INPUT, _OUTPUT
    if _INTERPRETER is None:
        _INTERPRETER = _load_interpreter(config.MODEL_PATH)
        _INPUT = _INTERPRETER.get_input_details()[0]
        _OUTPUT = _INTERPRETER.get_output_details()[0]
    return _INTERPRETER, _INPUT, _OUTPUT


def _preprocess(frame):
    """Match MobileNetV3 training preprocess: RGB + scale to [-1, 1].

    `frame` is BGR uint8 HxWx3 (same layout we used with OpenCV).
    """
    if frame is None or getattr(frame, "size", 0) == 0:
        raise ValueError("empty frame")

    # BGR -> RGB
    rgb = frame[:, :, ::-1]
    img = Image.fromarray(rgb).resize((INPUT_SIZE, INPUT_SIZE), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32)
    arr = (arr / 127.5) - 1.0
    return np.expand_dims(arr, axis=0)


def predict(frame):
    """
    Classify a BGR uint8 frame.

    Returns:
        (uart_letter, class_name, confidence)
    """
    interpreter, input_detail, output_detail = _get_interpreter()
    tensor = _preprocess(frame)

    dtype = input_detail["dtype"]
    if dtype != tensor.dtype:
        tensor = tensor.astype(dtype)

    interpreter.set_tensor(input_detail["index"], tensor)
    interpreter.invoke()
    preds = interpreter.get_tensor(output_detail["index"])[0]
    preds = np.asarray(preds, dtype=np.float32).reshape(-1)

    idx = int(np.argmax(preds))
    conf = float(preds[idx])
    classes = config.CLASSES
    if idx < 0 or idx >= len(classes):
        return "M", "unknown", conf

    cls = classes[idx]
    if conf < config.CONFIDENCE_THRESHOLD:
        return "M", cls, conf

    letter = config.CATEGORY_MAPPING.get(cls, "M")
    return letter, cls, conf
