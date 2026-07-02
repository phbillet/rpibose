#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "📦 1. Installing system and audio dependencies..."
sudo apt update
sudo apt install -y python3 mpv socat jq bluetooth bluez bluez-tools alsa-utils bluez-alsa-utils

echo "📂 2. Setting up project directory and permissions..."
cd "$HOME/rpibose"
chmod +x radio_backend.sh

echo "🔀 3. Creating Named Pipe (FIFO) for inter-process communication..."
if [ ! -p "radio_pipe" ]; then
    rm -f radio_pipe
    mkfifo radio_pipe
    echo "   -> radio_pipe created successfully."
else
    echo "   -> radio_pipe already exists."
fi

echo "🛡️ 4. Configuring Bluetooth Audio & Security Groups..."
sudo rfkill unblock bluetooth || true

# Add current user to essential groups
sudo usermod -aG bluetooth $USER
sudo usermod -aG audio $USER

# Grant passwordless shutdown privileges
echo "   -> Granting passwordless shutdown privileges..."
echo "$USER ALL=(ALL) NOPASSWD: /sbin/poweroff, /sbin/shutdown, /sbin/reboot" | sudo tee /etc/sudoers.d/99-rpibose-shutdown > /dev/null
sudo chmod 0440 /etc/sudoers.d/99-rpibose-shutdown

# Enable and start the low-level system services
sudo systemctl enable --now bluetooth
sudo systemctl enable --now bluealsa

echo "⚙️ 5. Creating Systemd User Services..."
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$USER_SYSTEMD_DIR"

# Writing radionette-audio.service
cat << 'SERVICE_AUDIO' > "$USER_SYSTEMD_DIR/radionette-audio.service"
[Unit]
Description=Radionette - Moteur Audio MPV
After=network.target

[Service]
ExecStart=/bin/bash %h/rpibose/radio_backend.sh
WorkingDirectory=%h/rpibose
Restart=always
StandardOutput=append:%h/rpibose/radionette-audio.log
StandardError=append:%h/rpibose/radionette-audio.log

[Install]
WantedBy=default.target
SERVICE_AUDIO

# Writing radionette-web.service
cat << 'SERVICE_WEB' > "$USER_SYSTEMD_DIR/radionette-web.service"
[Unit]
Description=Radionette - Serveur Interface Web
After=network.target

[Service]
ExecStart=/usr/bin/python3 %h/rpibose/server.py
WorkingDirectory=%h/rpibose
Restart=always
StandardOutput=append:%h/rpibose/radionette-web.log
StandardError=append:%h/rpibose/radionette-web.log

[Install]
WantedBy=default.target
SERVICE_WEB

echo "🔄 6. Reloading Systemd and enabling user services..."
systemctl --user daemon-reload
systemctl --user enable radionette-audio.service
systemctl --user enable radionette-web.service

echo "🚀 7. Starting services right now..."
systemctl --user restart radionette-audio.service radionette-web.service

echo "👑 8. Enabling lingering..."
sudo loginctl enable-linger $USER

echo "--------------------------------------------------------"
echo "🎉 INSTALLATION COMPLETE SUCCESSFUL!"
echo "--------------------------------------------------------"
echo "⚠️  IMPORTANT: Please run 'sudo reboot' to apply group permissions."
echo "--------------------------------------------------------"
