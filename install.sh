#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "📦 1. Installing system and audio dependencies..."
sudo apt update
# Notice the addition of bluez-alsa-utils for ALSA-pure Bluetooth audio bridges
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
# Unlock physical bluetooth interface
sudo rfkill unblock bluetooth || true

# Add current user to essential groups to permit hardware and audio socket manipulation
sudo usermod -aG bluetooth $USER
sudo usermod -aG audio $USER

# NEW: Allow user to shutdown/reboot the Pi without a password prompt
echo "   -> Granting passwordless shutdown privileges..."
echo "$USER ALL=(ALL) NOPASSWD: /sbin/poweroff, /sbin/shutdown, /sbin/reboot" | sudo tee /etc/sudoers.d/99-rpibose-shutdown > /dev/null
sudo chmod 0440 /etc/sudoers.d/99-rpibose-shutdown

# Force bluez-alsa to accept connections from the 'audio' group
# if [ -f /lib/systemd/system/bluez-alsa.service ]; then
#     echo "   -> Patching bluez-alsa.service permissions..."
#     # Ensure --group=audio is appended to the ExecStart execution line
#     if ! grep -q -- "--group=audio" /lib/systemd/system/bluez-alsa.service; then
#         sudo sed -i 's|ExecStart=/usr/bin/bluealsa|ExecStart=/usr/bin/bluealsa --group=audio|' /lib/systemd/system/bluez-alsa.service
#         sudo systemctl daemon-reload
#     fi
# fi

# Patch bluealsa.service permissions dynamically using systemctl
if systemctl list-unit-files | grep -q "bluealsa.service"; then
    echo "   -> Patching bluealsa.service permissions..."
    SERVICE_PATH=$(systemctl show -p FragmentPath bluealsa | cut -d= -f2)
    if [ -f "$SERVICE_PATH" ] && ! grep -q -- "--group=audio" "$SERVICE_PATH"; then
        sudo sed -i 's|ExecStart=/usr/bin/bluealsa|ExecStart=/usr/bin/bluealsa --group=audio|' "$SERVICE_PATH"
        sudo systemctl daemon-reload
    fi
fi

# Enable and start the low-level system services
sudo systemctl enable --now bluetooth
sudo systemctl enable --now bluez-alsa

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

echo "👑 8. Enabling lingering (allows user services to run headlessly without SSH login)..."
sudo loginctl enable-linger $USER

echo "--------------------------------------------------------"
echo "🎉 INSTALLATION COMPLETE SUCCESSFUL!"
echo "--------------------------------------------------------"
echo "⚠️  IMPORTANT: Please run 'sudo reboot' to apply new security group permissions."
echo "--------------------------------------------------------"
echo "📻 Web Interface available at: http://$(hostname -I | awk '{print $1}'):8080"
echo "📝 Audio logs: ~/rpibose/radionette-audio.log"
echo "📝 Web logs:   ~/rpibose/radionette-web.log"
echo "--------------------------------------------------------"
