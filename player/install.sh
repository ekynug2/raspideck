#!/usr/bin/env bash
# RaspiDeck Pi Player Installer (with boot splash)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_URL="${1:-http://your-vps-ip:8000}"

echo "========================================="
echo "  RaspiDeck Pi 3 B+ Installer"
echo "  Server: $SERVER_URL"
echo "========================================="

# 0. Clean up conflicting legacy services & player processes
echo "[0/6] Cleaning up conflicting legacy services..."
sudo systemctl stop videoplayer.service 2>/dev/null || true
sudo systemctl disable videoplayer.service 2>/dev/null || true
sudo systemctl mask videoplayer.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/videoplayer.service 2>/dev/null || true
sudo systemctl daemon-reload 2>/dev/null || true
sudo systemctl stop lightdm.service 2>/dev/null || true
sudo systemctl disable lightdm.service 2>/dev/null || true
sudo killall -9 -q python3 vlc xinit Xorg matchbox-window-manager unclutter 2>/dev/null || true

# 1. Update & install VLC + X11 kiosk dependencies
echo "[1/6] Installing VLC, X11, and required packages..."
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    vlc \
    xserver-xorg \
    xserver-xorg-legacy \
    xinit \
    x11-xserver-utils \
    matchbox-window-manager \
    unclutter \
    python3 \
    python3-pip \
    python3-pil \
    python3-pil.imagetk \
    python3-tk \
    python3-vlc \
    plymouth \
    plymouth-themes \
    psmisc \
    curl \
    sed

# Allow anybody to start Xorg with root rights (needed for kiosk mode from systemd)
echo -e "allowed_users=anybody\nneeds_root_rights=yes" | sudo tee /etc/X11/Xwrapper.config >/dev/null

# Install python-vlc binding if missing
sudo pip3 install --break-system-packages python-vlc 2>/dev/null || pip3 install python-vlc || true

TARGET_USER="${SUDO_USER:-$USER}"
[ "$TARGET_USER" = "root" ] && [ -d "/home/pi" ] && TARGET_USER="pi"

# 2. Setup directory, player script, boot config, and kiosk start script
echo "[2/6] Setting up player directory & configs..."
sudo mkdir -p /opt/raspideck/media
sudo chown -R "$TARGET_USER":"$TARGET_USER" /opt/raspideck

# Save server URL to boot partition (editable in Windows when SD card is inserted)
BOOT_CONF="/boot/raspideck.txt"
[ -d "/boot/firmware" ] && BOOT_CONF="/boot/firmware/raspideck.txt"
echo "SERVER_URL=$SERVER_URL" | sudo tee "$BOOT_CONF" >/dev/null
echo "  Server URL saved to $BOOT_CONF"

# Configure ALSA default audio to HDMI (card 0)
echo -e "defaults.pcm.card 0\ndefaults.ctl.card 0" | sudo tee /etc/asound.conf >/dev/null

# Copy player script and core modules
sudo mkdir -p /opt/raspideck/bin /opt/raspideck/versions
if [ -f "$SCRIPT_DIR/player.py" ]; then
    cp -r "$SCRIPT_DIR"/* /opt/raspideck/
elif [ -d "$SCRIPT_DIR/player" ]; then
    cp -r "$SCRIPT_DIR"/player/* /opt/raspideck/
elif [ -d "./player" ]; then
    cp -r ./player/* /opt/raspideck/
fi
chmod +x /opt/raspideck/player.py 2>/dev/null || true
chmod +x /opt/raspideck/bin/*.sh 2>/dev/null || true

# Setup restricted sudoers entry for restart script (safe OTA privilege)
echo "$TARGET_USER ALL=(ALL) NOPASSWD: /opt/raspideck/bin/restart-player.sh" | sudo tee /etc/sudoers.d/raspideck-ota >/dev/null
sudo chmod 0440 /etc/sudoers.d/raspideck-ota

# Create kiosk startup script
cat <<'STARTSCRIPT' | sudo tee /opt/raspideck/start.sh >/dev/null
#!/usr/bin/env bash
# RaspiDeck Kiosk Start Script (X11 mode)
# NOTE: Do NOT use set -e — xsetroot may fail harmlessly

export DISPLAY=:0

# Wait for X server to be ready
sleep 1

# Disable screen blanking & DPMS
xset s off 2>/dev/null || true
xset -dpms 2>/dev/null || true
xset dpms 0 0 0 2>/dev/null || true
xset s noblank 2>/dev/null || true

# Pure black background to prevent any flash or visible borders
BG_COLOR="#000000"
xsetroot -solid "$BG_COLOR" 2>/dev/null || true

# Hide mouse cursor
unclutter -idle 0.1 -root &

# Minimal window manager for borderless fullscreen
matchbox-window-manager -use_titlebar no &

# Force VLC to use X11 output (not Wayland) and suppress dbus errors
export VLC_PLUGIN_PATH=/usr/lib/vlc/plugins
export DBUS_SESSION_BUS_ADDRESS=/dev/null

# Start player unbuffered with real-time log (from symlink 'current' if present, or direct)
TARGET_EXEC="/opt/raspideck/player.py"
[ -f "/opt/raspideck/current/player.py" ] && TARGET_EXEC="/opt/raspideck/current/player.py"

/usr/bin/python3 -u "$TARGET_EXEC" 2>&1 | tee -a /opt/raspideck/player.log
STARTSCRIPT
sudo chmod +x /opt/raspideck/start.sh
sudo chown "$TARGET_USER":"$TARGET_USER" /opt/raspideck/start.sh


# 3. Create systemd service
echo "[3/6] Creating systemd service..."
cat <<EOF | sudo tee /etc/systemd/system/raspideck.service
[Unit]
Description=RaspiDeck Digital Signage Player
After=network-online.target time-sync.target sound.target
Wants=network-online.target
StartLimitBurst=3
StartLimitIntervalSec=300

[Service]
Type=simple
User=$TARGET_USER
Group=$TARGET_USER
PAMName=login
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$TARGET_USER/.Xauthority
Environment=RASPIDECK_SERVER=$SERVER_URL
Environment=RASPIDECK_MEDIA_DIR=/opt/raspideck/media
Environment=RASPIDECK_POLL_INTERVAL=15
Environment=DBUS_SESSION_BUS_ADDRESS=/dev/null
ExecStartPre=/bin/sh -c '/usr/bin/killall -q vlc xinit Xorg matchbox-window-manager unclutter || true'
ExecStartPre=/bin/sleep 1
ExecStart=/usr/bin/xinit /opt/raspideck/start.sh -- :0 vt1 -nocursor -keeptty
SuccessExitStatus=1 143
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable raspideck.service

# Disable desktop display manager (LightDM) & console login so no login screen ever appears
sudo systemctl stop lightdm.service 2>/dev/null || true
sudo systemctl disable lightdm.service 2>/dev/null || true
sudo systemctl mask lightdm.service 2>/dev/null || true
sudo systemctl set-default multi-user.target 2>/dev/null || true
sudo systemctl mask getty@tty1.service 2>/dev/null || true

# Configure OS to boot to console and disable screen blanking
sudo raspi-config nonint do_boot_behaviour B1 2>/dev/null || true
sudo raspi-config nonint do_blanking 1 2>/dev/null || true

# 4. Install boot splash (Plymouth theme)
echo "[4/6] Installing boot splash..."
THEME_DIR=/usr/share/plymouth/themes/raspideck
sudo mkdir -p "$THEME_DIR"

# Copy splash image
if [ -f "$SCRIPT_DIR/splash.png" ]; then
    sudo cp "$SCRIPT_DIR/splash.png" "$THEME_DIR/"
elif [ -f "$SCRIPT_DIR/player/splash.png" ]; then
    sudo cp "$SCRIPT_DIR/player/splash.png" "$THEME_DIR/"
elif [ -f "./player/splash.png" ]; then
    sudo cp ./player/splash.png "$THEME_DIR/"
elif [ -f "./splash.png" ]; then
    sudo cp ./splash.png "$THEME_DIR/"
else
    echo "  WARNING: splash.png not found. Run: pip install Pillow && python generate_splash.py"
    echo "  Then copy splash.png to $THEME_DIR/"
fi

# Plymouth theme descriptor
cat <<'THEME' | sudo tee "$THEME_DIR/raspideck.plymouth"
[Plymouth Theme]
Name=RaspiDeck
Description=RaspiDeck digital signage boot splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/raspideck
ScriptFile=/usr/share/plymouth/themes/raspideck/raspideck.script
THEME

# Plymouth script (Plymouth's own scripting language, NOT shell)
cat <<'PLYSCRIPT' | sudo tee "$THEME_DIR/raspideck.script"
# RaspiDeck Plymouth boot animation script
# Plymouth scripting language — see freedesktop.org/wiki/Software/Plymouth

# Load and center the splash image (auto-scale if display resolution is smaller than 1080p)
splash = Image("splash.png");
screen_w = Window.GetWidth();
screen_h = Window.GetHeight();

if (screen_w < splash.GetWidth() || screen_h < splash.GetHeight()) {
    scale_w = screen_w / splash.GetWidth();
    scale_h = screen_h / splash.GetHeight();
    scale = scale_w;
    if (scale_h < scale_w) scale = scale_h;
    new_w = splash.GetWidth() * scale;
    new_h = splash.GetHeight() * scale;
    splash = splash.Scale(new_w, new_h);
}

img_w = splash.GetWidth();
img_h = splash.GetHeight();
x = (screen_w - img_w) / 2;
y = (screen_h - img_h) / 2;

sprite = Sprite(splash);
sprite.SetX(x);
sprite.SetY(y);
sprite.SetZ(0);

# Simple progress callback — no-op, splash stays static
fun progress_callback(time, progress) {
}
Plymouth.SetBootProgressFunction(progress_callback);

# Hide password prompt styling (not used on signage Pi)
fun quit_callback() {
}
Plymouth.SetQuitFunction(quit_callback);
PLYSCRIPT

# Register theme
sudo update-alternatives --install \
    /usr/share/plymouth/themes/default.plymouth default.plymouth \
    "$THEME_DIR/raspideck.plymouth" 200
sudo update-alternatives --set default.plymouth \
    "$THEME_DIR/raspideck.plymouth"

# 5. Quiet boot — hide kernel text, cursor, rainbow square
echo "[5/6] Configuring quiet boot & display..."

# /boot/cmdline.txt — single line, append options if not present
CMDLINE_FILE="/boot/cmdline.txt"
# Try /boot/firmware/cmdline.txt for newer Raspberry Pi OS (Bookworm+)
[ -f "/boot/firmware/cmdline.txt" ] && CMDLINE_FILE="/boot/firmware/cmdline.txt"

for opt in quiet splash plymouth.ignore-serial-consoles logo.nologo vt.global_cursor_default=0 loglevel=1 rd.systemd.show_status=0 consoleblank=0; do
    if ! grep -q "$opt" "$CMDLINE_FILE"; then
        sudo sed -i.bak "s/$/ $opt/" "$CMDLINE_FILE"
    fi
done

# Clean up harmful or stale cmdline params if previously injected
sudo sed -i 's/plymouth.enable=0//g' "$CMDLINE_FILE" 2>/dev/null || true
sudo sed -i 's/fbcon=map:3//g' "$CMDLINE_FILE" 2>/dev/null || true
sudo sed -i 's/fsck.mode=skip//g' "$CMDLINE_FILE" 2>/dev/null || true
sudo sed -i 's/  */ /g' "$CMDLINE_FILE" 2>/dev/null || true

# Disable terminal login prompt on tty1 to prevent any text flashing before kiosk GUI loads
sudo systemctl mask getty@tty1.service 2>/dev/null || true

# Suppress harmless fbturbo Sunxi 2D accelerator modprobe error on Broadcom Pi
echo "install g2d_23 /bin/true" | sudo tee /etc/modprobe.d/blacklist-g2d.conf >/dev/null

# /boot/config.txt — disable GPU rainbow splash, boot delay, & configure display
CONFIG_FILE="/boot/config.txt"
[ -f "/boot/firmware/config.txt" ] && CONFIG_FILE="/boot/firmware/config.txt"
sudo grep -q '^disable_splash=' "$CONFIG_FILE" || echo 'disable_splash=1' | sudo tee -a "$CONFIG_FILE" >/dev/null
sudo grep -q '^boot_delay=' "$CONFIG_FILE" || echo 'boot_delay=0' | sudo tee -a "$CONFIG_FILE" >/dev/null
sudo grep -q '^avoid_warnings=' "$CONFIG_FILE" || echo 'avoid_warnings=1' | sudo tee -a "$CONFIG_FILE" >/dev/null

# Remove dangerous initramfs injection that halts the GPU firmware bootloader
sudo sed -i '/^initramfs/d' "$CONFIG_FILE" 2>/dev/null || true

# Remove hardcoded 1080p modes so any display (720p, 1080p, PC monitors) auto-negotiates via EDID
sudo sed -i '/^hdmi_group=/d' "$CONFIG_FILE" 2>/dev/null || true
sudo sed -i '/^hdmi_mode=/d' "$CONFIG_FILE" 2>/dev/null || true

# Force HDMI signal even if TV is turned on after Pi boots, route audio to HDMI, & allocate 512MB GPU memory
for setting in "hdmi_force_hotplug=1" "hdmi_drive=2" "gpu_mem=512"; do 
    key=$(echo "$setting" | cut -d= -f1)
    if ! grep -q "^$key=" "$CONFIG_FILE"; then
        echo "$setting" | sudo tee -a "$CONFIG_FILE" >/dev/null
    else
        sudo sed -i "s/^$key=.*/$setting/" "$CONFIG_FILE"
    fi
done

# Configure 512MB swap for safe video decoding headroom without thrashing SD card
if [ -f "/etc/dphys-swapfile" ]; then
    sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
    sudo dphys-swapfile swapoff 2>/dev/null || true
    sudo dphys-swapfile setup 2>/dev/null || true
    sudo dphys-swapfile swapon 2>/dev/null || true
fi

# Set timezone to Asia/Jakarta (WIB) & ensure NTP is active
echo "Configuring timezone & time synchronization..."
sudo timedatectl set-timezone Asia/Jakarta 2>/dev/null || true
sudo timedatectl set-ntp true 2>/dev/null || true

# 6. Update initramfs with new Plymouth theme
echo "[6/6] Updating initramfs..."
sudo update-initramfs -u 2>/dev/null || true

echo ""
echo "========================================="
echo "  Installation Complete!"
echo ""
echo "  Boot splash: RaspiDeck (Plymouth)"
echo "  Start player: sudo systemctl start raspideck"
echo "  Check logs:   journalctl -u raspideck -f"
echo "  Reboot to see splash: sudo reboot"
echo "========================================="
