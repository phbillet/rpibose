# 📻 Radiolink: Bose SoundLink Wireless Remote Control

A lightweight, web-based remote control interface designed for Raspberry Pi to stream web radios directly to a **Bose SoundLink** (or any Bluetooth) speaker using `mpv` and Python. It supports multi-category station management (CRUD), volume control, mute/unmute toggling, dynamic Bluetooth device scanning, and live metadata sync (Title/Artist) over Bluetooth.

---

## 📋 Prerequisites

Before installing, ensure your Raspberry Pi is running a Linux distribution (such as Raspberry Pi OS) and has the following packages installed:

```bash
sudo apt update
sudo apt install -y python3 mpv socat jq bluetooth bluez bluez-tools alsa-utils

```

---

## 🗂️ Project Structure

Create a dedicated directory for your project (e.g., `/home/pi/radiolink`) and place the files inside as follows:

```text
radiolink/
├── server.py            # Python HTTP Web Server (Interface)
├── radio_backend.sh     # Bash Audio & Control Engine
├── radios.csv           # Stations database (CSV format)
└── bose.conf            # Cached Bluetooth configuration (Auto-generated)

```

### 1. Database Setup (`radios.csv`)

Initialize your station list by creating a `radios.csv` file with the following exact header:

```csv
name,url,category
"FIP","https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance","France"
"Radio Paradise","https://stream.radioparadise.com/aac-128","Eclectic"

```

---

## ⚙️ Installation & Automation Setup

To make sure the web interface and the audio engine run seamlessly in the background and start automatically when the Raspberry Pi boots, we will configure them as **Systemd User Services**.

### Step 1: Make scripts executable

```bash
chmod +x /home/pi/radiolink/radio_backend.sh

```

### Step 2: Create the Web Server Service

Create a systemd unit file for the web interface:

```bash
mkdir -p ~/.config/systemd/user/
nano ~/.config/systemd/user/radionette-web.service

```

Paste the following configuration:

```ini
[Unit]
Description=Radiolink Web Interface Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/radiolink
ExecStart=/usr/bin/python3 /home/pi/radiolink/server.py
Restart=always
StandardOutput=append:/home/pi/radionette-web.log
StandardError=append:/home/pi/radionette-web.log

[Install]
WantedBy=default.target

```

### Step 3: Create the Audio Engine Service

Create a systemd unit file for the backend bash controller:

```bash
nano ~/.config/systemd/user/radionette-audio.service

```

Paste the following configuration:

```ini
[Unit]
Description=Radiolink Audio Backend Controller
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/radiolink
ExecStart=/bin/bash /home/pi/radiolink/radio_backend.sh
Restart=always

[Install]
WantedBy=default.target

```

### Step 4: Enable and Start Services

Reload the systemd daemon configuration, enable the services for persistence on boot, and start them immediately:

```bash
# Reload systemd configuration
systemctl --user daemon-reload

# Enable services to auto-start on boot
systemctl --user enable radionette-web.service
systemctl --user enable radionette-audio.service

# Start the services right now
systemctl --user start radionette-web.service
systemctl --user start radionette-audio.service

```

*(Optional)* To allow user services to run even when you are logged out of your SSH session, run:

```bash
sudo loginctl enable-linger $USER

```

---

## 🚀 How to Use

1. Open your favorite web browser from any device connected to the same local network.
2. Navigate to your Raspberry Pi's IP address on port `8080` (e.g., `http://192.168.1.50:8080`).
3. **First-time setup:** * If no speaker is configured, click on **🔍 Scan Nearby Devices**.
* Turn your Bose SoundLink speaker on and set it to **pairing mode**.
* Select your speaker from the scanned list. The system will automatically pair, trust, and save the speaker profile.


4. Click **🟢 POWER ON BOSE** to establish the Bluetooth connection.
5. Choose any station from your categorized tabs and enjoy the music! You can add, edit, or delete stations at any time using the **⚙️ Manage Radios** dashboard.

---

## 🛠️ Troubleshooting & Logs

If the web page fails to load or the sound drops out, you can inspect live runtime logs using the following commands:

* **Check service status:**
```bash
systemctl --user status radionette-web.service
systemctl --user status radionette-audio.service

```


* **View Web interface runtime errors:**
```bash
tail -n 50 ~/radionette-web.log

```


* **Restart services after a manual code update:**
```bash
systemctl --user restart radionette-web.service radionette-audio.service

```

