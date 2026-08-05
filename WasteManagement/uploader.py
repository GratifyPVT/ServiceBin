import os
import time
import requests
import config

IMAGE_DIR = config.IMAGE_DIR
API_URL = config.WASTE_API_URL
BIN_LOCATION = config.BIN_ID

CHECK_INTERVAL = 5  # seconds


# ---------------- PARSE ----------------
def parse_filename(filename):
    try:
        name = filename.replace(".jpg", "")
        parts = name.split("_")

        timestamp = parts[0] + "_" + parts[1]
        cls = parts[2]   # <-- THIS is what we send
        result = parts[3]
        confidence = float(parts[4])

        return timestamp, cls, result, confidence

    except:
        return None


# ---------------- UPLOAD ----------------
def upload_file(filepath):
    filename = os.path.basename(filepath)

    parsed = parse_filename(filename)
    if not parsed:
        print("Skipping invalid file:", filename)
        return False

    timestamp, cls, result, confidence = parsed

    try:
        time.sleep(0.3)  # avoid partial write

        with open(filepath, "rb") as f:
            files = {
                "image": (filename, f, "image/jpeg")
            }

            data = {
                "type": cls,                # ✅ FIXED (send actual class)
                "binlocation": BIN_LOCATION
            }

            response = requests.post(
                API_URL,
                files=files,
                data=data,
                timeout=5
            )

        if response.status_code == 200:
            print("Uploaded:", filename)
            return True
        else:
            print("Upload failed:", response.status_code)
            print(response.text)
            return False

    except Exception as e:
        print("Error uploading:", filename, "|", e)
        return False


# ---------------- MAIN LOOP ----------------
print("Uploader started...")

while True:
    try:
        files = os.listdir(IMAGE_DIR)

        for file in files:
            if not file.endswith(".jpg"):
                continue

            filepath = os.path.join(IMAGE_DIR, file)

            success = upload_file(filepath)

            if success:
                os.remove(filepath)
                print("Deleted:", file)

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Uploader error:", e)
        time.sleep(5)