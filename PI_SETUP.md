# Raspberry Pi Setup Guide

Commands to install everything and enable Gratify services on reboot.

---

## 1. System packages

```bash
sudo apt update
sudo apt install -y git mpv python3-pip
```

---

## 2. Check CPU architecture

```bash
uname -m
```

- `aarch64` → use **64-bit** Miniconda below  
- `armv7l` → use **32-bit** Miniconda below  

---

## 3. Install Miniconda (conda)

### 64-bit (`aarch64`)

```bash
cd ~
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh -O miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/etc/profile.d/conda.sh
conda init bash
source ~/.bashrc
conda --version
```

### 32-bit (`armv7l`)

```bash
cd ~
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-armv7l.sh -O miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/etc/profile.d/conda.sh
conda init bash
source ~/.bashrc
conda --version
```

### Accept Terms of Service (if asked)

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

---

## 4. Create conda env

```bash
conda create -n mf python=3.11 -y
conda activate mf
```

---

## 5. Clone the repo

```bash
cd ~
git clone https://github.com/GratifyPVT/ServiceBin.git
cd ServiceBin
```

Private repo (SSH):

```bash
git clone git@github.com:GratifyPVT/ServiceBin.git
cd ServiceBin
```

---

## 6. Install Python dependencies

```bash
conda activate mf
cd ~/ServiceBin
pip install -r requirements.txt
```

---

## 7. Camera / serial permissions

```bash
sudo usermod -aG video,dialout $USER
```

Log out and log back in (or reboot) so group changes apply.

Enable camera if needed:

```bash
sudo raspi-config
```

Interface Options → Camera → Enable

---

## 8. Enable services on reboot

```bash
conda activate mf
cd ~/ServiceBin
bash deploy/install-services.sh
```

If your conda env is not named `mf`:

```bash
CONDA_ENV_NAME=your_env_name bash deploy/install-services.sh
```

---

## 9. Check services

```bash
sudo systemctl status gratify-update gratify-garbage gratify-ads gratify-waste
```

Follow logs:

```bash
journalctl -u gratify-garbage -f
journalctl -u gratify-ads -f
journalctl -u gratify-waste -f
journalctl -u gratify-update -f
```

---

## Stop / disable auto-start (optional)

```bash
sudo systemctl stop gratify-garbage gratify-ads gratify-waste gratify-update
sudo systemctl disable gratify-garbage gratify-ads gratify-waste gratify-update
```

---

## Boot order

1. `gratify-update` — pull from GitHub only if updates exist  
2. `gratify-garbage` — waste detection + Arduino  
3. `gratify-ads` — ad player (`mpv`)  
4. `gratify-waste` — upload images when count &gt; 8  
