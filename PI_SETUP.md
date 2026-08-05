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

```bash
python3 -m venv ~/gratify-venv
source ~/gratify-venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

Later sessions, activate with:

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

```bash
cd ~/ServiceBin
CONDA_PYTHON=$HOME/gratify-venv/bin/python bash deploy/install-services.sh
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

## If home screen only (ads not opening)

From status photo, typical meanings:

- `gratify-ads` **inactive (dead)** → ads never started (nothing on screen)
- `gratify-garbage` **activating (start-pre)** → waiting for Arduino serial (up to ~15–90s)
- `gratify-waste` **auto-restart / exit-code** → Python uploader crashed

### Fix now on the Pi

```bash
# see exact errors
journalctl -u gratify-ads -n 50 --no-pager
journalctl -u gratify-waste -n 50 --no-pager

# make sure deps + mpv exist
source ~/gratify-venv/bin/activate
pip install -r ~/ServiceBin/requirements.txt
which mpv

# ensure a video exists (or wait for API download)
ls ~/ServiceBin/AdsManagement/videos/

# restart after desktop is visible
sudo systemctl restart gratify-ads gratify-waste gratify-garbage
sudo systemctl status gratify-ads gratify-waste gratify-garbage --no-pager
```

Enable desktop auto-login so ads can use the screen after reboot:

```bash
sudo raspi-config
# System Options → Auto Login → Desktop
```
