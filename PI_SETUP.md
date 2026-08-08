# Raspberry Pi Setup Guide (working)

Use this on **32-bit Raspberry Pi OS** (`armv7l`).  
Do **not** install old Miniconda — it breaks with `conda: command not found`.

---

## 0. Remove broken old Miniconda (if present)

```bash
rm -rf ~/miniconda3
```

---

## 1. System packages

```bash
sudo apt update
sudo apt install -y git mpv python3 python3-pip python3-venv
```

---

## 2. Go to the project (already cloned)

```bash
cd ~/ServiceBin
# if your folder name/path is different, cd there instead
```

If not cloned yet:

```bash
cd ~
git clone https://github.com/GratifyPVT/ServiceBin.git
cd ServiceBin
```

---

## 3. Create venv + install Python deps

On **new Pi OS (Python 3.13)** do **not** expect `pip install tflite-runtime` to work on Pi 3A+.
Use apt for TFLite, and a venv with `--system-site-packages`.

```bash
sudo apt install -y python3-tflite-runtime mpv

# recreate cleanly if an old venv already exists
rm -rf ~/gratify-venv
python3 -m venv --system-site-packages ~/gratify-venv
source ~/gratify-venv/bin/activate
pip install -U pip
cd ~/ServiceBin
pip install numpy opencv-python-headless pyserial requests
```

Check:

```bash
python -c "import requests; print('requests OK')"
python -c "from tflite_runtime.interpreter import Interpreter; print('tflite OK')"
```

Later sessions:

```bash
source ~/gratify-venv/bin/activate
cd ~/ServiceBin
```

---

## 4. Camera / serial permissions

```bash
sudo usermod -aG video,dialout $USER
```

Then **log out and log back in** (or reboot).

---

## 5. Enable services on reboot

This installs and enables all four units so they start on every boot:
`gratify-update` → then `gratify-garbage` (ML + camera), `gratify-ads`, `gratify-waste`.

```bash
cd ~/ServiceBin
# install script auto-finds ~/gratify-venv; override if needed:
bash deploy/install-services.sh
# or:
CONDA_PYTHON=$HOME/gratify-venv/bin/python bash deploy/install-services.sh
```

Also set desktop autologin (needed for ads / mpv):

```bash
sudo raspi-config
# System Options → Boot / Auto Login → Desktop Autologin
sudo systemctl set-default graphical.target
```
---

## 6. Check services

```bash
sudo systemctl status gratify-update gratify-garbage gratify-ads gratify-waste
```

Logs:

```bash
journalctl -u gratify-garbage -f
journalctl -u gratify-ads -f
journalctl -u gratify-waste -f
journalctl -u gratify-update -f
```

---

## Stop / disable auto-start

```bash
sudo systemctl stop gratify-garbage gratify-ads gratify-waste gratify-update
sudo systemctl disable gratify-garbage gratify-ads gratify-waste gratify-update
```

---

## Notes

- Python path used by systemd: `~/gratify-venv/bin/python`
- Ads need `mpv` installed via apt
- Waste uploader runs when image count is more than 8
- GitHub update service pulls only if remote has new commits

---

## Ads starts manually but NOT after reboot

This happens when the desktop isn’t ready yet at boot, or the unit isn’t hooked to `graphical.target`.

On the Pi:

```bash
cd ~/ServiceBin

# pull latest unit files if you use git, OR copy from your PC, then:
CONDA_PYTHON=$HOME/gratify-venv/bin/python bash deploy/install-services.sh

# force enable for graphical desktop boot
sudo systemctl daemon-reload
sudo systemctl disable gratify-ads
sudo systemctl enable gratify-ads

# confirm it is linked to graphical.target
ls -l /etc/systemd/system/graphical.target.wants/gratify-ads.service

# also enable desktop auto-login
sudo raspi-config
# System Options → Boot / Auto Login → Desktop Autologin

sudo reboot
```

After reboot, check:

```bash
sudo systemctl status gratify-ads --no-pager
```

---

## If home screen only (ads not opening)

From status photo, typical meanings:

- `gratify-ads` **inactive (dead)** → ads never started (nothing on screen)
- `gratify-ads` **activating (auto-restart) / exit-code** → Python crashed (missing pip packages is #1 cause)
- `gratify-garbage` **activating (start-pre)** → waiting for Arduino serial (up to ~15–90s)
- `gratify-waste` **auto-restart / exit-code** → Python uploader crashed

### Fix now on the Pi (venv path — no Miniforge needed)

You do **not** need Miniforge if you followed this file. Services already use `~/gratify-venv`.

```bash
# 1) See the real Python error
journalctl -u gratify-ads -n 80 --no-pager

# 2) Reinstall deps into the same venv systemd uses
source ~/gratify-venv/bin/activate
cd ~/ServiceBin
pip install -U pip
pip install -r requirements.txt

# 3) Confirm imports + mpv
python -c "import requests, config; print('imports OK')"
which mpv || sudo apt install -y mpv
ls ~/ServiceBin/AdsManagement/videos/*.mp4

# 4) Manual test (Ctrl+C to stop) — must work before systemd will
cd ~/ServiceBin
python -m AdsManagement.service

# 5) If manual works, restart the service
sudo systemctl restart gratify-ads
sudo systemctl status gratify-ads --no-pager
```

If journal shows `No module named requests` (or similar), step 2 fixes it.

If journal shows display / X11 / mpv errors, enable Desktop Autologin:

```bash
sudo raspi-config
# System Options → Boot / Auto Login → Desktop Autologin
sudo reboot
```
