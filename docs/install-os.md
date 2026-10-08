# Installation Guide

Follow these steps to turn any machine into a dedicated, headless OCloud server.

## Step 1: Install the Base OS

Set up a clean, minimal installation of **[Arch Linux](https://wiki.archlinux.org/title/Installation_guide)** on your target machine. You do not need a desktop environment.

## Step 2: Install Dependencies & Clone Project

Log into your new Arch system, install the core system requirements, and grab the source code:

```bash
sudo pacman -S git python docker python-pip

sudo systemctl enable --now docker

git clone https://github.com/mk-2015/OCloud.git /root/OCloud
cd /root/ocloud

python -m venv .mvenv
source .mvenv/bin/activate
pip install -r server/requirements.txt
```

## Step 3: Vim Magic (Systemd Configuration)

To make OCloud automatically launch in headless mode every time the computer turns on, create a system background service.

1. Open a new service file using Vim:

```bash
sudo vim /etc/systemd/system/ocloud.service
```

1. Paste the following configuration inside (press `i` to insert, then `Ctrl+Shift+V` or right-click to paste):

```ini
[Unit]
Description=OCloud Core Daemon Engine
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/OCloud
ExecStart=/root/OCloud/.mvenv/bin/python server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

*(Save and exit Vim by pressing `Esc`, typing `:wq`, and hitting `Enter`.)*

## Step 4: Fire It Up

Tell the system to register your new background service, set it to turn on automatically on boot, and restart the machine:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ocloud.service
sudo reboot
```

# > [!NOTE]
>
> # If your computer catches fire while installing, please don't open a GitHub issue
