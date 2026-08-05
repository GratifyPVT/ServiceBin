import os
import time

import requests

import config

IMAGE_DIR = config.IMAGE_DIR
API_URL = config.WASTE_API_URL
BIN_LOCATION = config.BIN_ID

CHECK_INTERVAL = 5  # seconds
UPLOAD_THRESHOLD = 8  # upload + delete only when more than this many images


def list_images():
    return sorted(
        f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg")
    )


def parse_filename(filename):
    try:
        name = filename.replace(".jpg", "")
        parts = name.split("_")

        timestamp = parts[0] + "_" + parts[1]
        cls = parts[2]
        result = parts[3]
        confidence = float(parts[4])

        return timestamp, cls, result, confidence

    except Exception:
        return None


def upload_file(filepath):
    filename = os.path.basename(filepath)

    parsed = parse_filename(filename)
    if not parsed:
        print("Skipping invalid file:", filename)
        return False

    _timestamp, cls, _result, _confidence = parsed

    try:
        time.sleep(0.3)  # avoid partial write

        with open(filepath, "rb") as f:
            files = {"image": (filename, f, "image/jpeg")}
            data = {
                "type": cls,
                "binlocation": BIN_LOCATION,
            }
            response = requests.post(
                API_URL,
                files=files,
                data=data,
                timeout=15,
            )

        if response.status_code == 200:
            print("Uploaded:", filename)
            return True

        print("Upload failed:", response.status_code)
        print(response.text)
        return False

    except Exception as e:
        print("Error uploading:", filename, "|", e)
        return False


def upload_batch(images):
    print(f"Batch upload starting ({len(images)} images) -> {API_URL}")
    for file in images:
        filepath = os.path.join(IMAGE_DIR, file)
        if not os.path.isfile(filepath):
            continue
        if upload_file(filepath):
            os.remove(filepath)
            print("Deleted:", file)
    print("Batch upload done.\n")


def main():
    print("Uploader started...")
    print(f"Image dir: {IMAGE_DIR}")
    print(f"Upload when count > {UPLOAD_THRESHOLD}\n")
    os.makedirs(IMAGE_DIR, exist_ok=True)

    while True:
        try:
            images = list_images()
            count = len(images)

            if count > UPLOAD_THRESHOLD:
                upload_batch(images)
            else:
                print(f"Waiting: {count}/{UPLOAD_THRESHOLD + 1} images before upload")

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print("Uploader error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
