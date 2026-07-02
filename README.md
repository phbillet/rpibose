# 📻 rpibose: Bose SoundLink Wireless Remote Control

`rpibose` is a lightweight, web-based remote control system designed for Raspberry Pi to stream web radios directly to a **Bose SoundLink** (or any Bluetooth) speaker. Driven by a fast Python web interface and a robust Bash audio engine powered by `mpv`, it supports multi-category station management (CRUD), volume control, mute/unmute toggling, dynamic Bluetooth device scanning, and live metadata synchronization (Title/Artist) over Bluetooth.

---

## 🚀 Quick Installation

Setting up `rpibose` on your Raspberry Pi is entirely automated. The installation script takes care of system dependencies, folder permissions, named communication pipes, and systemd background services.

### One-Command Setup

Open your terminal and run the following command:

```bash
git clone https://github.com/phbillet/rpibose.git && cd rpibose && ./install.sh

```

---

## 📂 Project Structure

Once installed, your application layout inside the `~/rpibose` directory looks like this:

```text
rpibose/
├── install.sh           # Automated one-click installer
├── server.py            # Python HTTP Web Server (Web Interface)
├── radio_backend.sh     # Bash Audio & Control Engine
├── radios.csv           # Stations database (CSV format)
├── radio_pipe           # Named Pipe (FIFO) for inter-process communication
└── bose.conf            # Cached Bluetooth config (Auto-generated)

```

> **Note on Data:** Your stations database file `radios.csv` uses a clean comma-separated structure with the required English header:
> ```csv
> name,url,category
> "FIP","https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance","France"
> 
> ```
> 
> 

---

## 🎮 How to Use

1. Open any web browser on a device connected to the same local network as your Raspberry Pi.
2. Navigate to your Raspberry Pi's IP address on port `8080` (e.g., `[http://192.168.1.50:8080](http://192.168.1.50:8080)`).
3. **First-time configuration:**
* Put your Bose SoundLink speaker into **pairing mode**.
* Click on **🔍 Scan Nearby Devices** on the web page.
* Select your speaker from the list. The system will automatically pair and trust the device.


4. Click **🟢 POWER ON BOSE** to connect, then choose a station from your categorized tabs and enjoy!

You can add, edit, or delete web radios at any time directly through the **⚙️ Manage Radios** dashboard.

---

## 🛠️ Management & Troubleshooting

Both the web server and the audio engine run continuously in the background as **Systemd User Services**, meaning they automatically restart on boot and run headlessly without needing an active SSH login.

### Service Control

```bash
# Check if services are running properly
systemctl --user status radionette-web.service
systemctl --user status radionette-audio.service

# Restart the application after code adjustments
systemctl --user restart radionette-web.service radionette-audio.service

```

### Inspecting Runtime Logs

If you encounter streaming stability issues or web server crashes, check the dedicated log files located right inside your project directory:

```bash
# View recent audio engine logs (mpv / bluetooth)
tail -n 50 ~/rpibose/radionette-audio.log

# View recent web server logs (Python)
tail -n 50 ~/rpibose/radionette-web.log

```

