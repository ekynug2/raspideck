# RaspiDeck — Self-Hosted Digital Signage Platform

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%203B%2B%20%7C%204%20%7C%205%20%7C%20Zero%202W-red.svg)](https://www.raspberrypi.com/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v2.1.0-brightgreen.svg)](player/VERSION)

**RaspiDeck** is a lightweight, robust, self-hosted digital signage CMS and kiosk player system designed specifically for Raspberry Pi devices (Raspberry Pi 3 B+, 4, 5, and Zero 2 W).

It provides a centralized Web Management Dashboard on your server/VPS and an automated, hardware-accelerated playback client on your Raspberry Pi displays.

---

## Table of Contents

- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Database & Sample Data (`example.db`)](#database--sample-data-exampledb)
- [Quick Start: Server Deployment](#quick-start-server-deployment)
  - [Option 1: Docker Compose (Recommended)](#option-1-docker-compose-recommended)
  - [Option 2: Native Python / Systemd](#option-2-native-python--systemd)
  - [Reverse Proxy Setup (Nginx + SSL)](#reverse-proxy-setup-nginx--ssl)
- [Quick Start: Player Client Deployment](#quick-start-player-client-deployment)
  - [Automated MicroSD Setup (Outlet Plug-and-Play)](#automated-microsd-setup-outlet-plug-and-play)
  - [Manual Installation Script](#manual-installation-script)
- [Per-Display Settings System](#per-display-settings-system)
- [Safe Over-The-Air (OTA) Updates](#safe-over-the-air-ota-updates)
- [REST API Reference](#rest-api-reference)
- [Environment Configuration](#environment-configuration)
- [Hardware & Optimization Notes](#hardware--optimization-notes)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [License](#license)

---

## Key Features

### 🖥️ Display & Playback Management
- **Hardware-Accelerated Playback**: Uses VLC media player with hardware decoding (OMX / MMAL / DRM) for smooth 1080p/4K 60fps video playback on Raspberry Pi.
- **Offline Resilience**: The player caches all media locally with SHA-256 chunked hashing. If network or internet connectivity drops, playback continues seamlessly from local cache without black screens.
- **Independent Per-Display Settings**: Adjust Volume (0–100%), Screen Rotation (0°, 90°, 180°, 270°), Polling Interval (5s–120s), and Screen Power (DPMS Standby) **individually for each screen** directly from the web dashboard.
- **Automated Pairing Flow**: New displays show a clear 6-digit pairing code on TV. Simply approve and assign a playlist with one click from the dashboard.
- **Live Hardware Telemetry**: Monitors CPU temperature, CPU load, RAM usage, free microSD disk space, uptime, and HDMI resolution in real time.

### 🛡️ Enterprise-Grade OTA (Over-The-Air) Software Updates
- **Zero-Downtime Atomic Symlink Swap**: Installs new versions into `/opt/raspideck/versions/vX.X/` and performs an atomic symlink switch (`current -> versions/vX.X`).
- **Cryptographic Integrity & Resumable Downloads**: Checks SHA-256 signatures before installation and supports HTTP `Range` (Status 206) headers to resume partial downloads during unstable Wi-Fi connections.
- **Automated Rollback & Watchdog Protection**: If a new release fails syntax verification or crashes upon boot, the player automatically reverts to the previous stable release.
- **Remote Fleet Updates**: Update a single display or trigger a batch upgrade across all outdated screens simultaneously from the web UI.

---

## System Architecture

```
                       ┌─────────────────────────────────────────────────────────┐
                       │                     RaspiDeck Server                    │
                       │                  (Docker / VPS / Cloud)                 │
                       ├─────────────────────────────────────────────────────────┤
                       │  - Flask REST API (Gunicorn + Nginx Reverse Proxy)      │
                       │  - SQLite Database (WAL mode, deck.db / example.db)     │
                       │  - Modern Tabler UI Web Dashboard                       │
                       │  - Media Storage & OTA Package Builder (server/ota.py)  │
                       └────────────────────────────┬────────────────────────────┘
                                                    │
                                     HTTP/HTTPS REST API (JSON)
                                 - Bearer Token Authentication
                                 - Heartbeat & Dynamic Settings (30s)
                                 - Resumable Media & OTA Downloads
                                                    │
                       ┌────────────────────────────┴────────────────────────────┐
                       │               RaspiDeck Client (Raspberry Pi)           │
                       │            /opt/raspideck/current -> versions/v2.1      │
                       ├─────────────────────────────────────────────────────────┤
                       │  - Kiosk Supervisor & systemd service (player.service)  │
                       │  - Settings Daemon (xrandr rotation, ALSA volume)       │
                       │  - Playback Engine (VLC Fullscreen Loop)                │
                       │  - Local Cache (SHA-256 Verification & Fallback)        │
                       │  - Safe OTA Updater (/opt/raspideck/core/updater.py)    │
                       │  - Hardware Watchdog & Boot Splash Generator            │
                       └─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
raspi-deck/
├── .env.example                 # Example environment variables template
├── .gitignore                   # Comprehensive ignore rules (protects db, media, secrets)
├── docker-compose.yml           # VPS container deployment specification
├── example.db                   # Pre-populated demonstration database (screens, playlists, media)
├── README.md                    # Full documentation and manual
│
├── server/                      # Server application
│   ├── app.py                   # Flask server application factory
│   ├── config.py                # Server configuration & environment parsing
│   ├── db.py                    # SQLite database schema, WAL mode, migrations
│   ├── auth.py                  # Session-based authentication & route protectors
│   ├── ota.py                   # OTA package packaging, manifest, resumable downloads
│   ├── utils.py                 # Media file validation, hashing, formatting helpers
│   ├── requirements.txt         # Server Python dependencies
│   ├── Dockerfile               # Container build recipe
│   │
│   ├── routes/                  # Modular route controllers
│   │   ├── web.py               # Web dashboard & authentication views
│   │   ├── admin_api.py         # REST API for screens, playlists, media, and OTA
│   │   └── player_api.py        # Player client heartbeat, media, and update endpoints
│   │
│   ├── static/                  # Static assets
│   │   ├── css/dashboard.css    # Custom responsive dashboard styling
│   │   ├── js/                  # Frontend modular JavaScript
│   │   │   ├── app.js           # Dashboard initialization & KPI refresh
│   │   │   ├── screens.js       # Screen cards, settings modal, OTA update modals
│   │   │   ├── playlists.js     # Playlist editor & scheduler
│   │   │   └── media.js         # Drag-and-drop media uploader
│   │   └── vendor/tabler/       # Tabler UI bundle (CSS, JS, Icon fonts)
│   │
│   └── templates/               # Jinja2 HTML templates
│       ├── dashboard.html       # Main administration dashboard
│       ├── login.html           # Secure administrator login
│       └── partials/            # Component templates (screens, playlists, media, modals)
│
└── player/                      # Raspberry Pi client application
    ├── player.py                # Main kiosk playback loop & event orchestrator
    ├── VERSION                  # Current player version string (e.g. 2.1.0)
    ├── install.sh               # Complete Pi setup script (dependencies, systemd, boot)
    ├── generate_splash.py       # Standalone Pillow boot splash generator
    │
    ├── bin/
    │   └── restart-player.sh    # Restricted sudo script for safe service restarts
    │
    └── core/                    # Player modular core engines
        ├── config.py            # Device identity, token storage & server resolution
        ├── settings.py          # Atomic display settings (Volume, Rotation, DPMS, Polling)
        ├── updater.py           # OTA download, checksum, atomic swap, and rollback engine
        ├── playback.py          # Fullscreen VLC playback controller
        ├── cache.py             # Local media cache manager & SHA-256 chunk checker
        ├── api.py               # Robust HTTP client with retry & exponential backoff
        ├── screens.py           # Dynamic Pillow UI renderer (Pairing screen, Status overlay)
        └── telemetry.py         # Hardware telemetry collector (temp, ram, disk, resolution)
```

---

## Database & Sample Data (`example.db`)

RaspiDeck includes a pre-configured, clean demonstration database: [`example.db`](example.db).

### What's Inside `example.db`:
1. **Screens Table**:
   - **`screen-pi3-lobby`** (Paired): Demonstrates a landscape 1080p screen with 80% volume, 0° rotation, active telemetry, and version `2.1.0`.
   - **`screen-pi3-cafe`** (Paired): Demonstrates a portrait 90° screen with 0% volume (muted menu board), version `2.1.0`.
   - **`screen-pi3-newdevice`** (Pending): Demonstrates a new display showing pairing code `183920` running version `2.0.0` (eligible for OTA update).
2. **Playlists Table**:
   - Pre-configured 24/7 lobby playlist and scheduled daily menu board playlist.
3. **Media Table**:
   - Example metadata schema for videos and images with duration and checksum entries.

### How to Use `example.db`:
To test the dashboard immediately with sample data:
```bash
# On your server/dev machine:
cp example.db server/deck.db

# Or when using Docker Compose:
cp example.db data/deck.db
```
> [!NOTE]
> If no database file exists when the server starts, `server/db.py` automatically initializes a clean, empty `deck.db` with all tables and columns.

---

## Quick Start: Server Deployment

### Option 1: Docker Compose (Recommended)

1. Clone repository:
   ```bash
   git clone https://github.com/ekynug2/raspideck.git
   cd raspideck
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env and set a secure ADMIN_PASSWORD and SECRET_KEY
   nano .env
   ```

3. (Optional) Use the sample database:
   ```bash
   mkdir -p data/media data/updates
   cp example.db data/deck.db
   ```

4. Launch services:
   ```bash
   docker compose up -d
   ```
   Open `http://<your-server-ip>:8000` in your browser and log in with your configured password.

---

### Option 2: Native Python / Systemd

1. Install Python 3.9+ and system requirements:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-pip python3-venv ffmpeg
   ```

2. Create virtual environment & install dependencies:
   ```bash
   cd raspideck/server
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   export ADMIN_PASSWORD="your-secure-password"
   export SECRET_KEY="$(openssl rand -hex 32)"
   export PORT=8000
   ```

4. Run with Gunicorn:
   ```bash
   gunicorn --bind 0.0.0.0:8000 --workers 4 --threads 2 --timeout 60 app:app
   ```

---

### Reverse Proxy Setup (Nginx + SSL)

To serve RaspiDeck over HTTPS with Let's Encrypt, use this Nginx virtual host configuration:

```nginx
server {
    listen 80;
    server_name signage.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name signage.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/signage.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/signage.yourdomain.com/privkey.pem;

    # Allow large video uploads (e.g. 500 MB)
    client_max_body_size 500M;
    client_body_timeout 300s;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }
}
```

---

## Quick Start: Player Client Deployment

### Automated MicroSD Setup (Outlet Plug-and-Play)
Ideal for pre-configuring SD cards before shipping them to branch stores or retail outlets:

1. Flash **Raspberry Pi OS Lite (64-bit or 32-bit)** using **Raspberry Pi Imager**.
   - Configure outlet Wi-Fi and hostname in the Imager settings.
2. In the `boot` partition of the flashed microSD card, create a file named `raspideck.txt`:
   ```ini
   SERVER_URL=https://signage.yourdomain.com
   ```
3. Insert the card into the Raspberry Pi and power on.
4. The Pi automatically boots into kiosk mode, pairs with your server, and displays the 6-digit pairing code on the TV screen.

---

### Manual Installation Script

To install or update the player manually on a running Raspberry Pi:

1. Copy the `player/` directory to your Raspberry Pi:
   ```bash
   rsync -avz player/ pi@<pi-ip-address>:/home/pi/player/
   ```

2. Run the installer with your server URL:
   ```bash
   cd /home/pi/player
   chmod +x install.sh
   sudo ./install.sh https://signage.yourdomain.com
   ```

3. The installer automatically:
   - Installs VLC, X11 minimal server, Openbox window manager, ALSA sound tools, and Python dependencies.
   - Sets up `/opt/raspideck/` with version directories and atomic symlink.
   - Configures `/etc/sudoers.d/raspideck-ota` for secure service restarts without root password prompts.
   - Enables the hardware watchdog (`/dev/watchdog`) to prevent freezing.
   - Creates and activates the `raspideck.service` systemd daemon.
   - Reboots into kiosk mode.

---

## Per-Display Settings System

RaspiDeck provides granular, per-display hardware control via [`player/core/settings.py`](player/core/settings.py). Settings are synchronized during heartbeat polls and applied immediately without interrupting playback:

| Setting | Type | Range / Values | Hardware Action |
|---------|------|----------------|-----------------|
| `audio_volume` | Integer | `0` – `100` (%) | Detects active ALSA audio device (HDMI vs 3.5mm jack) and adjusts volume via `amixer`. |
| `screen_rotation` | Integer | `0`, `90`, `180`, `270` (degrees) | Dynamic display orientation switch via `xrandr -o <normal\|right\|inverted\|left>`. |
| `poll_interval` | Integer | `5` – `120` (seconds) | Adjusts heartbeat telemetry and playlist check frequency dynamically. |
| `screen_power` | Boolean | `true` / `false` | Controls HDMI display sleep / wake state via DPMS (`xset dpms force on/off`). |

### How to Change Display Settings:
1. In the Web Dashboard, navigate to the **Screens** tab.
2. Click the **⚙️ Settings** button on the screen card.
3. Adjust the volume slider, choose rotation, or toggle screen power.
4. Click **Save Settings**. The client player applies the changes on its next heartbeat.

---

## Safe Over-The-Air (OTA) Updates

The OTA update engine ([`player/core/updater.py`](player/core/updater.py) and [`server/ota.py`](server/ota.py)) guarantees seamless remote code updates:

```
[Server UI] ──(Click Update)──> [Set pending_update in DB]
                                           │
[Client Player] <──(Heartbeat receives manifest payload)
       │
       ├── 1. Check free microSD storage (min. 30MB)
       ├── 2. Download raspideck-player.tar.gz (HTTP Range resumable)
       ├── 3. Verify SHA-256 integrity against manifest
       ├── 4. Extract to /opt/raspideck/versions/vX.X/
       ├── 5. Run syntax smoke test (py_compile) on new version
       ├── 6. Atomic symlink switch: current -> versions/vX.X
       ├── 7. Call restricted restart wrapper: restart-player.sh
       └── 8. Verify boot & report 'success' status to server
              (If boot fails -> Automatic Rollback to previous version)
```

### Performing an OTA Update:
- **Single Screen**: Click **🚀 Update** on any outdated screen card in the dashboard.
- **Batch Update**: Click the **⚡ Update All Screens** button at the top of the Screens tab to upgrade all connected displays simultaneously.

---

## REST API Reference

### Player Endpoints (`/api/player/*`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/player/heartbeat` | `Bearer <token>` / Open | Sends hardware telemetry, receives playlist, per-display settings, and pending OTA manifests. |
| `GET` | `/api/player/media/<filename>` | None | Streams or downloads cached playlist media files. |
| `GET` | `/api/player/update/manifest` | `Bearer <token>` | Returns current OTA release metadata (version, hash, size). |
| `GET` | `/api/player/update/download` | `Bearer <token>` | Downloads update tarball (supports HTTP `Range` resume). |
| `POST` | `/api/player/update/status` | `Bearer <token>` | Reports OTA update progress (`downloading`, `applying`, `success`, `failed`). |

### Admin Endpoints (`/api/*`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/screens` | Session | Returns all registered screens with telemetry, settings, and versions. |
| `POST` | `/api/screens/<id>/pair` | Session | Approves 6-digit pairing code and creates device token. |
| `PATCH` | `/api/screens/<id>/settings` | Session | Updates independent display settings (volume, rotation, power, poll interval). |
| `POST` | `/api/screens/<id>/update` | Session | Schedules an OTA update for a specific screen. |
| `POST` | `/api/screens/update-all` | Session | Schedules batch OTA updates for all outdated screens. |
| `GET` | `/api/media` | Session | Lists all uploaded media files and disk consumption. |
| `POST` | `/api/media` | Session | Uploads new video or image asset. |
| `DELETE`| `/api/media/<id>` | Session | Deletes media file from storage and database. |
| `GET` | `/api/playlists` | Session | Lists all configured playlists and schedules. |
| `POST` | `/api/playlists` | Session | Creates a new playlist with ordered items. |
| `PUT` | `/api/playlists/<id>` | Session | Updates playlist order, duration, or schedule windows. |
| `DELETE`| `/api/playlists/<id>` | Session | Deletes playlist. |
| `POST` | `/api/system/player-package/build` | Session | Builds and hashes new `raspideck-player.tar.gz` package. |

---

## Environment Configuration

### Server Options (`.env` or Docker Compose)

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PASSWORD` | *Required* | Password for dashboard login (`admin` user). |
| `SECRET_KEY` | *(Auto-generated)* | Flask session signing secret key. |
| `DB_PATH` | `/data/deck.db` | Absolute path to SQLite database. |
| `MEDIA_DIR` | `/data/media` | Directory where uploaded videos/images are stored. |
| `UPDATES_DIR` | `/data/updates` | Directory where OTA `.tar.gz` packages are stored. |
| `MAX_CONTENT_LENGTH` | `100` | Max file upload size in Megabytes (e.g. `100` = 100MB). |
| `PORT` | `8000` | HTTP port the server listens on. |

### Player Options (`/boot/raspideck.txt` or Systemd Environment)

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_URL` | `http://localhost:8000` | URL of the central RaspiDeck management server. |
| `RASPIDECK_DEVICE_ID`| *(Serial number)* | Unique hardware identifier override. |
| `RASPIDECK_POLL_INTERVAL` | `30` | Heartbeat interval fallback in seconds. |

---

## Hardware & Optimization Notes

- **Raspberry Pi 3 B+**: Excellent for 1080p H.264 video loops. Memory usage remains ~130MB (30MB Python + 100MB VLC).
- **Raspberry Pi 4 / 5**: Supports dual micro-HDMI displays and 4K 60fps video playback.
- **Audio Output Selection**: If your TV does not play sound over HDMI, check `alsamixer` or ensure `hdmi_drive=2` is enabled in `/boot/config.txt`.
- **MicroSD Longevity**: RaspiDeck utilizes atomic file writes and SQLite WAL mode to reduce microSD wear. For enterprise deployments, consider high-endurance SD cards (e.g., SanDisk High Endurance or Samsung PRO Endurance).

---

## Troubleshooting & FAQ

#### Q: The screen displays the pairing code after rebooting.
**A**: Ensure you have clicked "Approve & Pair" from the dashboard. Once approved, the player saves its device token in `/opt/raspideck/device_token.txt` and starts playback immediately.

#### Q: The screen orientation did not change after updating settings.
**A**: Screen rotation requires the X11 server to support `xrandr`. Make sure the player was installed via `player/install.sh` which properly configures Openbox and X11 permissions.

#### Q: How can I check client player logs on the Raspberry Pi?
**A**: View real-time logs via systemd:
```bash
journalctl -u raspideck.service -f
```

#### Q: What happens if the Wi-Fi connection drops at a retail outlet?
**A**: The player automatically enters offline mode. It loops cached media from `/opt/raspideck/media/playlist_cache.json` indefinitely and reconnects automatically once the network returns.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
