"""
Unified ads service: polls the API, downloads new videos in the background,
keeps playing the current playlist until replacements are fully ready, then
swaps and starts playback automatically.
"""
import os
import shutil
import subprocess
import threading
import time

import requests

import config

API = config.ADS_API_URL
VIDEO_DIR = config.VIDEO_DIR
STAGING_DIR = os.path.join(VIDEO_DIR, ".staging")
POLL_INTERVAL = config.ADS_POLL_INTERVAL  # seconds between API checks

os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(STAGING_DIR, exist_ok=True)

_update_lock = threading.Lock()
_pending_playlist = None  # sorted list of filenames ready in staging
_update_ready = threading.Event()

_mpv_lock = threading.Lock()
_mpv_process = None


def fetch_videos():
    try:
        res = requests.get(API, timeout=5)
        res.raise_for_status()
        data = res.json()
        if not data.get("success"):
            print("API returned failure")
            return None
        return data
    except Exception as e:
        print("API error:", e)
        return None


def _active_videos():
    return sorted(f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4"))


def _staging_complete(valid_names):
    return all(
        os.path.isfile(os.path.join(STAGING_DIR, name)) for name in valid_names
    )


def _clear_staging():
    for name in os.listdir(STAGING_DIR):
        path = os.path.join(STAGING_DIR, name)
        if os.path.isfile(path):
            os.remove(path)


def _download_file(url, dest_path):
    part_path = dest_path + ".part"
    try:
        print("Downloading:", os.path.basename(dest_path))
        res = requests.get(url, timeout=30)
        res.raise_for_status()
        with open(part_path, "wb") as f:
            f.write(res.content)
        os.replace(part_path, dest_path)
        return True
    except Exception as e:
        print("Download failed:", os.path.basename(dest_path), e)
        if os.path.exists(part_path):
            os.remove(part_path)
        return False


def _prepare_staging(videos):
    """Download the full target playlist into staging without touching active files."""
    valid_names = sorted(v["url"].split("/")[-1] for v in videos)
    url_by_name = {v["url"].split("/")[-1]: v["url"] for v in videos}

    for name in valid_names:
        staging_path = os.path.join(STAGING_DIR, name)
        if os.path.isfile(staging_path):
            continue

        active_path = os.path.join(VIDEO_DIR, name)
        if os.path.isfile(active_path):
            print("Staging from active:", name)
            shutil.copy2(active_path, staging_path)
            continue

        if not _download_file(url_by_name[name], staging_path):
            return None

    if not _staging_complete(valid_names):
        return None

    return valid_names


def _apply_update(valid_names):
    """Replace the active playlist with staged files and remove old videos."""
    print("Applying update:", valid_names)

    for name in os.listdir(VIDEO_DIR):
        if name.endswith(".mp4") and name not in valid_names:
            path = os.path.join(VIDEO_DIR, name)
            try:
                os.remove(path)
                print("Removed old video:", name)
            except Exception as e:
                print("Remove failed:", name, e)

    for name in valid_names:
        src = os.path.join(STAGING_DIR, name)
        dst = os.path.join(VIDEO_DIR, name)
        if os.path.isfile(src):
            shutil.move(src, dst)

    _clear_staging()
    print("Update applied.\n")


def _stop_mpv():
    global _mpv_process
    with _mpv_lock:
        if _mpv_process is None:
            return
        if _mpv_process.poll() is None:
            _mpv_process.terminate()
            try:
                _mpv_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _mpv_process.kill()
                _mpv_process.wait()
        _mpv_process = None


def _start_mpv(paths):
    global _mpv_process
    with _mpv_lock:
        print("Playing:", ", ".join(os.path.basename(p) for p in paths))
        _mpv_process = subprocess.Popen(
            [
                "mpv",
                "--fs",
                "--no-terminal",
                "--loop-playlist=inf",
                "--no-osc",
                "--no-input-default-bindings",
                *paths,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _mpv_running():
    with _mpv_lock:
        return _mpv_process is not None and _mpv_process.poll() is None


def _queue_update(videos):
    target = sorted(v["url"].split("/")[-1] for v in videos)
    active = _active_videos()

    if target == active:
        return False

    print("New ads detected. Downloading while current ads keep playing...")
    prepared = _prepare_staging(videos)
    if prepared is None:
        print("Staging incomplete — keeping current ads.\n")
        return False

    with _update_lock:
        global _pending_playlist
        _pending_playlist = prepared
    _update_ready.set()
    print("New ads ready to play.\n")
    return True


def _sync_once():
    data = fetch_videos()
    if not data:
        return

    videos = data.get("videos", [])
    if not videos:
        return

    _queue_update(videos)


def sync_and_apply():
    """One-shot sync for manual use — download and apply immediately."""
    data = fetch_videos()
    if not data:
        return

    videos = data.get("videos", [])
    if not videos:
        return

    target = sorted(v["url"].split("/")[-1] for v in videos)
    active = _active_videos()

    if target == active:
        print("Ads already up to date.\n")
        return

    print("Syncing ads...")
    prepared = _prepare_staging(videos)
    if prepared is None:
        print("Sync failed.\n")
        return

    _apply_update(prepared)
    print("Sync complete.\n")


def _sync_worker():
    while True:
        try:
            _sync_once()
        except Exception as e:
            print("Sync error:", e)
        time.sleep(POLL_INTERVAL)


def _player_loop():
    global _pending_playlist

    while True:
        try:
            if _update_ready.is_set():
                with _update_lock:
                    playlist = list(_pending_playlist or [])
                    _pending_playlist = None
                _update_ready.clear()

                if playlist:
                    _stop_mpv()
                    _apply_update(playlist)

            active = _active_videos()
            if not active:
                if _mpv_running():
                    _stop_mpv()
                print("No videos found. Waiting...")
                time.sleep(5)
                continue

            if not _mpv_running():
                paths = [os.path.join(VIDEO_DIR, f) for f in active]
                _start_mpv(paths)

            time.sleep(1)

        except Exception as e:
            print("Player error:", e)
            time.sleep(5)


def main():
    print("Ads Service Started")
    print(f"Video dir: {VIDEO_DIR}")
    print(f"Polling API every {POLL_INTERVAL}s\n")

    threading.Thread(target=_sync_worker, daemon=True).start()
    _sync_once()  # check immediately on startup
    _player_loop()


if __name__ == "__main__":
    main()
