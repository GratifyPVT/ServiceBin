# ServiceBin (Gratify)

Smart waste bin software for Raspberry Pi. It classifies waste with on-device ML, tells an Arduino how to sort it, uploads capture photos to the cloud, and plays ads on a display.

**Target hardware:** Raspberry Pi 3A (also runs on desktop for testing)

---

## How it works

```
┌─────────────┐   CAPTURE    ┌──────────────────────┐   B / N / M    ┌─────────────┐
│   Arduino   │ ───────────► │  GarbageDetection    │ ─────────────► │   Arduino   │
│  (sensor /  │              │  camera + TFLite ML  │                │  (stepper)  │
│   trigger)  │              └──────────┬───────────┘                └─────────────┘
└─────────────┘                         │
                                        │ saves JPEG
                                        ▼
                             WasteManagement/images/
                                        │
                                        │ when > 8 images
                                        ▼
                             WasteManagement/uploader
                                        │
                                        ▼
                         Cloud API (uploadwaste)

AdsManagement/service  ◄── poll API every 10 min ──►  Cloud API (videos)
        │
        ▼
   mpv fullscreen playlist
```

Three long-running processes share `config.py` and talk to the same backend. They do not import each other.

| Service | Role |
|---------|------|
| **GarbageDetection** | Wait for `CAPTURE` → snap camera → classify → reply `B`/`N`/`M` over serial → save photo |
| **WasteManagement** | When local images exceed 8 → upload each to API → delete on success |
| **AdsManagement** | Play local ad videos with `mpv`; sync playlist from API on start and every 10 minutes |

On boot (Pi deployment), **gratify-update** runs first and pulls from GitHub only if remote has new commits.

---

## Repository layout

```
gratify/
├── config.py                 # Shared settings + env overrides
├── requirements.txt          # Python dependencies
├── GarbageDetection/
│   ├── main.py               # Main detection loop
│   ├── classifier.py         # TFLite inference
│   ├── runtime.py            # Serial + camera helpers
│   └── model/                # *.tflite models (required on Pi)
├── WasteManagement/
│   ├── uploader.py           # Batch image uploader
│   └── images/               # Captured photos (handoff folder)
├── AdsManagement/
│   ├── service.py            # Ad sync + mpv player
│   └── videos/               # Local ad .mp4 files
└── deploy/
    ├── install-services.sh   # Install systemd units
    ├── wait-for-boot.sh      # Wait for network / serial / display
    ├── update-from-github.sh # Pull updates if available
    └── systemd/              # Unit files
```

---

## Sort logic (Arduino letters)

| ML class | UART letter | Arduino behaviour |
|----------|-------------|-------------------|
| biodegradable | `B` | Move stepper (bio path) |
| glass, metal, paper, plastic | `N` | Move stepper (non-bio path) |
| e-waste | `M` | No move (stay HOME) |
| confidence &lt; 0.45 | `M` | Treated as uncertain |

Arduino must receive `B` or `N` within **5 seconds** of `CAPTURE`, or it times out at HOME.

Saved filenames look like:

```text
20260805_194318_plastic_N_0.99.jpg
│              │       │ │
│              │       │ └─ confidence
│              │       └─ UART result
│              └─ class name
└─ timestamp
```

---

## Setup

### 1. System packages

**Raspberry Pi**

```bash
sudo apt update
sudo apt install -y git mpv python3-pip
# Camera + serial as needed for your OS image
```

**Desktop (Pop!_OS / Ubuntu)** — for testing only

```bash
# mpv via conda (recommended if apt needs sudo):
conda activate mf
conda install -y -c conda-forge mpv
```

### 2. Python environment

```bash
# Example with conda (env name used by deploy scripts: mf)
conda create -n mf python=3.11 -y
conda activate mf
cd /path/to/gratify
pip install -r requirements.txt
```

`requirements.txt` installs:

- Always: `numpy`, `opencv-python-headless`, `pyserial`, `requests`
- **Pi / ARM:** `tflite-runtime` (lightweight; preferred on Pi 3A)
- **x86 desktop:** `tensorflow` (fallback when `tflite-runtime` has no wheel)

Do **not** install full TensorFlow on Pi 3A (512MB RAM).

### 3. Model files

Place under `GarbageDetection/model/`:

1. Preferred: `rls_mobilenetv3_mish_cbam_float16.tflite`
2. Fallback: `model.tflite`

---

## Running manually (PC testing)

Nothing needs to run permanently on a PC. Use three terminals; stop each with `Ctrl+C`.

Do **not** run `deploy/install-services.sh` on a PC unless you want boot auto-start.

### Terminal A — garbage detection

```bash
conda activate mf
cd /path/to/gratify
GRATIFY_SIMULATION=1 python -m GarbageDetection.main
```

Type `CAPTURE` to trigger. Without simulation, it uses `/dev/serial0` or the first `/dev/ttyUSB*` / `/dev/ttyACM*`. If no serial device exists, it falls back to simulation automatically.

### Terminal B — waste uploader

```bash
conda activate mf
cd /path/to/gratify
python -m WasteManagement.uploader
```

Uploads only when there are **more than 8** `.jpg` files in `WasteManagement/images/`.

### Terminal C — ads

```bash
conda activate mf
cd /path/to/gratify
python -m AdsManagement.service
```

Plays local videos immediately. Checks the ads API on start; if the playlist is unchanged, it skips download. Polls again every **10 minutes**.

---

## Deploy on Raspberry Pi (auto-start on boot)

```bash
conda activate mf   # or your deploy env
cd /path/to/gratify
pip install -r requirements.txt
bash deploy/install-services.sh
```

Default conda env name is `mf`. Override if needed:

```bash
CONDA_ENV_NAME=tfenv bash deploy/install-services.sh
# or
CONDA_PYTHON=/home/pi/miniconda3/envs/mf/bin/python bash deploy/install-services.sh
```

### Boot order

1. `gratify-update` — fetch GitHub; pull only if updates exist  
2. `gratify-garbage` / `gratify-ads` / `gratify-waste` — start in parallel after update  

### Useful commands

```bash
sudo systemctl status gratify-update gratify-garbage gratify-ads gratify-waste
journalctl -u gratify-garbage -f
journalctl -u gratify-ads -f
journalctl -u gratify-waste -f
journalctl -u gratify-update -f
```

### Stop / disable auto-start

```bash
sudo systemctl stop gratify-garbage gratify-ads gratify-waste gratify-update
sudo systemctl disable gratify-garbage gratify-ads gratify-waste gratify-update
```

### GitHub auto-update notes

- Remote: `origin` / branch `main` (override with `GRATIFY_GIT_REMOTE`, `GRATIFY_GIT_BRANCH`)
- If already up to date → no action
- If remote is ahead and fast-forward is possible → `git pull --ff-only`
- If auth fails or local branch diverged → keeps current code; services still start
- Private repos need SSH deploy key or credentials on the Pi

---

## Configuration

Shared settings live in `config.py`. Many can be overridden with environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `GRATIFY_SIMULATION` | `0` | `1` = keyboard `CAPTURE` (no Arduino) |
| `GRATIFY_SERIAL_PORT` | `/dev/serial0` | UART device |
| `GRATIFY_CONFIDENCE_THRESHOLD` | `0.45` | Below this → send `M` |
| `GRATIFY_TFLITE_THREADS` | `2` | TFLite threads |
| `GRATIFY_SERIAL_CAPTURE_FLUSH` | `2` | Camera flush before capture |
| `GRATIFY_COOLDOWN` | `0` | Optional trigger cooldown (seconds) |
| `GRATIFY_ADS_POLL_INTERVAL` | `600` | Ads API poll interval (seconds) |
| `GRATIFY_IMAGE_DIR` | `WasteManagement/images` | Capture folder |

Also in `config.py` (edit directly):

| Setting | Purpose |
|---------|---------|
| `BIN_ID` | Bin identity for APIs |
| `WASTE_API_URL` | `…/api/uploadwaste` |
| `ADS_API_URL` | `…/api/videos/{BIN_ID}` |
| `CLASSES` / `CATEGORY_MAPPING` | Labels → `B`/`N`/`M` |

Waste uploader threshold (`UPLOAD_THRESHOLD = 8`) is in `WasteManagement/uploader.py`.

---

## Cloud APIs

- **Waste upload:** `POST` multipart to  
  `https://gratify-ads-management.vercel.app/api/uploadwaste`  
  Fields: `image` (file), `type` (class name), `binlocation` (`BIN_ID`)

- **Ads playlist:** `GET`  
  `https://gratify-ads-management.vercel.app/api/videos/{BIN_ID}`  
  Returns video URLs; service stages new files, then swaps the playlist without interrupting playback until ready.

---

## Arduino protocol (summary)

1. Arduino sends line: `CAPTURE`
2. Pi captures + runs ML (must reply within ~5s)
3. Pi sends line: `B`, `N`, or `M`
4. Arduino moves only on `B` or `N`

Serial defaults: **9600 baud**, DTR left low to avoid accidental MCU reset.

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| `No module named tflite_runtime` / `tensorflow` | `pip install -r requirements.txt` in the correct conda env |
| Serial `/dev/serial0` missing (desktop) | Use `GRATIFY_SIMULATION=1`, or plug USB-UART |
| Camera failed to open | Check `/dev/video0`, user in `video` group |
| Ads service starts but no video | Install `mpv`, put `.mp4` in `AdsManagement/videos/` |
| Uploader never uploads | Need **more than 8** images in `WasteManagement/images/` |
| GitHub update fetch fails | Public repo, or SSH remote + deploy key |
| Reply too slow / stepper never moves | Keep inference under 5s; warmup runs at start |

---

## License / project

Repository: [GratifyPVT/ServiceBin](https://github.com/GratifyPVT/ServiceBin)
