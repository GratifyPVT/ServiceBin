"""TFLite waste classifier for Raspberry Pi (Pi 3A-friendly)."""
import os

import cv2
import numpy as np

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
                "Need tflite-runtime (Pi) or tensorflow (desktop). "
                "Install with: pip install -r requirements.txt"
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
    """Match MobileNetV3 training preprocess: RGB + scale to [-1, 1]."""
    img = cv2.resize(frame, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32)
    img = (img / 127.5) - 1.0
    return np.expand_dims(img, axis=0)


def predict(frame):
    """
    Classify a BGR OpenCV frame.

    Returns:
        (uart_letter, class_name, confidence)
        uart_letter is B / N / M from config.CATEGORY_MAPPING
        (M when confidence is below threshold).
    """
    interpreter, input_detail, output_detail = _get_interpreter()
    tensor = _preprocess(frame)

    # Cast to model input dtype (float16 models still accept float32 input often)
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
