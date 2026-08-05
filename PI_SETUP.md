# Raspberry Pi Setup Guide

## Important

- Do **not** use old Continuum Miniconda (Python 3.4). It will fail with `conda: command not found`.
- Modern conda does **not** support 32-bit Pi OS (`armv7l`).
- Prefer **64-bit Raspberry Pi OS** + Miniforge.
- If you must stay on 32-bit, skip conda and use `venv`.

Check your OS:

```bash
uname -m
# aarch64 = 64-bit  → use Section A
# armv7l  = 32-bit  → use Section B
```

---

## Remove broken old Miniconda (if installed)

```bash
rm -rf ~/miniconda3
```

---

## Section A — 64-bit OS (`aarch64`) — recommended

### 1. System packages

```bash
sudo apt update
sudo apt install -y git mpv python3-pip
```

### 2. Install Miniforge (conda)

```bash
cd ~
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh -O miniforge.sh
bash miniforge.sh -b -p $HOME/miniforge3
source $HOME/miniforge3/etc/profile.d/conda.sh
conda init bash
source ~/.bashrc
conda --version
```

If `conda: command not found`:

```bash
source $HOME/miniforge3/etc/profile.d/conda.sh
```

### 3. Create env

```bash
conda create -n mf python=3.11 -y
conda activate mf
```

### 4. Clone repo

```bash
cd ~
git clone https://github.com/GratifyPVT/ServiceBin.git
cd ServiceBin
```

Private repo:

```bash
git clone git@github.com:GratifyPVT/ServiceBin.git
cd ServiceBin
```

### 5. Install Python deps

```bash
conda activate mf
cd ~/ServiceBin
pip install -r requirements.txt
```

### 6. Camera / serial permissions

```bash
sudo usermod -aG video,dialout $USER
```

Log out and back in (or reboot).

### 7. Enable services on reboot

```bash
conda activate mf
cd ~/ServiceBin
bash deploy/install-services.sh
```

If conda is Miniforge and the script can’t find `mf`, set the python path:

```bash
CONDA_PYTHON=$HOME/miniforge3/envs/mf/bin/python bash deploy/install-services.sh
```

### 8. Check

```bash
sudo systemctl status gratify-update gratify-garbage gratify-ads gratify-waste
```

---

## Section B — 32-bit OS (`armv7l`) — no conda

Use system Python + venv.

### 1. System packages

```bash
sudo apt update
sudo apt install -y git mpv python3 python3-pip python3-venv
```

### 2. Clone repo

```bash
cd ~
git clone https://github.com/GratifyPVT/ServiceBin.git
cd ServiceBin
```

### 3. Create venv + install deps

```bash
python3 -m venv ~/gratify-venv
source ~/gratify-venv/bin/activate
pip install -U pip
cd ~/ServiceBin
pip install -r requirements.txt
```

### 4. Camera / serial permissions

```bash
sudo usermod -aG video,dialout $USER
```

Log out and back in (or reboot).

### 5. Enable services on reboot

```bash
cd ~/ServiceBin
CONDA_PYTHON=$HOME/gratify-venv/bin/python bash deploy/install-services.sh
```

### 6. Check

```bash
sudo systemctl status gratify-update gratify-garbage gratify-ads gratify-waste
```

---

## Stop / disable auto-start

```bash
sudo systemctl stop gratify-garbage gratify-ads gratify-waste gratify-update
sudo systemctl disable gratify-garbage gratify-ads gratify-waste gratify-update
```

---

## Logs

```bash
journalctl -u gratify-garbage -f
journalctl -u gratify-ads -f
journalctl -u gratify-waste -f
journalctl -u gratify-update -f
```
