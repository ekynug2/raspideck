# RaspiDeck — Self-hosted Digital Signage

Custom Yodeck-like digital signage for Raspberry Pi 3 B+.  
VPS = web dashboard + API. Pi = VLC player (fullscreen loop).

## Architecture

```
VPS (docker-compose)              Pi 3 B+
┌───────────────────┐           ┌──────────────────┐
│ nginx / gunicorn  │◄──poll──► │ player.py         │
│   Flask API       │  30s      │   VLC fullscreen  │
│   SQLite DB       │  heartbeat│   media cache     │
│   media volume    │           │   auto-download   │
│   web dashboard   │           │   pairing code    │
└───────────────────┘           └──────────────────┘
```

## Features

- **Web Dashboard** — upload media, create playlists, manage screens
- **Screen Pairing** — Pi shows pairing code, admin approves from dashboard
- **VLC Playback** — hardware-accelerated video, fullscreen images
- **Auto-Sync** — player polls server, downloads new media (SHA256 verified)
- **Multi-Screen** — each Pi gets own playlist assignment
- **Docker Deploy** — one `docker compose up` on VPS

## Quick Start

### 1. VPS Setup

```bash
# Clone to your VPS
git clone <this-repo> raspideck && cd raspideck

# IMPORTANT: Change default credentials
# Edit docker-compose.yml:
#   ADMIN_PASSWORD=your-secure-password
#   SECRET_KEY=your-random-secret-key

docker compose up -d
# Dashboard at http://your-vps-ip:8000
```

### 2. Pi Setup (Multi-Outlet Deployment)

```bash
# On your dev machine: generate boot splash image (optional)
pip install Pillow
cd player && python generate_splash.py && cd ..

# Copy player/ folder to Pi, then run installer:
chmod +x player/install.sh
sudo ./player/install.sh https://your-vps-domain.com

# Reboot to see custom boot splash & start kiosk
sudo reboot
```

#### Drop-In Outlet Deployment (SD Card Plug-and-Play)
When preparing MicroSD cards to ship to different retail outlets:
1. Flash Raspberry Pi OS Lite (Bullseye or Bookworm) using **Raspberry Pi Imager** (set outlet WiFi credentials in Imager settings).
2. Open the MicroSD `boot` drive in Windows Explorer / Mac Finder.
3. Edit or create `raspideck.txt`:
   ```ini
   SERVER_URL=https://your-vps-domain.com
   ```
4. Insert the SD card into the Pi at the outlet and power on.
5. The Pi automatically connects to WiFi, shows the pairing code on the TV, and syncs playlist.
6. **Offline Resilience**: If the outlet internet goes down, the Pi automatically falls back to cached local media (`/opt/raspideck/media/playlist_cache.json`) without any black screens.


### 3. Pair & Play

1. Pi shows pairing code on screen / terminal
2. Open dashboard → Screens → click "Approve & Pair"
3. Go to Media → upload images/videos
4. Go to Playlists → create playlist, add media items
5. Screens → assign playlist to paired screen
6. Pi auto-downloads media, starts playing

## File Structure

```
raspi-deck/
├── docker-compose.yml      # VPS deployment
├── server/
│   ├── app.py              # Flask server entrypoint (gunicorn app:app)
│   ├── config.py           # Paths & environment configuration
│   ├── db.py               # SQLite schema & database connection
│   ├── auth.py             # Session authentication helpers
│   ├── utils.py            # File extension & media helpers
│   ├── routes/             # Modular API & web routes
│   │   ├── web.py          # Dashboard & login views
│   │   ├── player_api.py   # Heartbeat & media endpoints
│   │   └── admin_api.py    # Screens, media, playlists CRUD
│   ├── templates/          # Modern HTML/CSS/JS frontend
│   │   ├── login.html
│   │   └── dashboard.html
│   ├── Dockerfile
│   └── requirements.txt
├── player/
│   ├── player.py           # VLC player orchestrator (kiosk playback loop)
│   ├── core/               # Player modular components
│   │   ├── config.py       # Hardware ID & server discovery
│   │   ├── telemetry.py    # Accurate Pi CPU/RAM/HDMI metrics
│   │   ├── cache.py        # Offline playlist & SHA256 chunk hasher
│   │   ├── api.py          # HTTP client & media downloader
│   │   ├── screens.py      # Pillow UI pairing & status generator
│   │   └── playback.py     # VLC fullscreen player controller
│   ├── install.sh          # Pi installer + boot splash
│   └── generate_splash.py  # Generate boot splash PNG
└── data/                   # Created at runtime
    ├── deck.db             # SQLite database
    └── media/              # Uploaded media files
```

## Environment Variables

### Server (docker-compose.yml)

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PASSWORD` | `admin123` | Dashboard login password |
| `SECRET_KEY` | (weak default) | Flask session secret |
| `MEDIA_DIR` | `/data/media` | Media storage path |
| `DB_PATH` | `/data/deck.db` | SQLite database path |
| `PORT` | `8000` | Server port |

### Player (systemd or env)

| Variable | Default | Description |
|----------|---------|-------------|
| `RASPIDECK_SERVER` | `http://localhost:8000` | Server URL |
| `RASPIDECK_DEVICE_ID` | (auto from Pi serial) | Override device ID |
| `RASPIDECK_MEDIA_DIR` | `/opt/raspideck/media` | Local media cache |
| `RASPIDECK_POLL_INTERVAL` | `30` | Seconds between server polls |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/player/heartbeat` | Player heartbeat + get playlist |
| GET | `/api/screens` | List all screens |
| POST | `/api/screens/:id/pair` | Pair a screen |
| PATCH/DELETE | `/api/screens/:id` | Update/delete screen |
| GET/POST | `/api/media` | List/upload media |
| DELETE | `/api/media/:id` | Delete media |
| GET/POST | `/api/playlists` | List/create playlists |
| PUT/DELETE | `/api/playlists/:id` | Update/delete playlist |

## Reverse Proxy (Nginx)

For HTTPS on VPS:

```nginx
server {
    listen 443 ssl;
    server_name deck.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/deck.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/deck.yourdomain.com/privkey.pem;
    
    client_max_body_size 500M;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

## Pi 3 B+ Notes

- VLC uses hardware decode (OMX on Pi 3), smooth 1080p video
- 1GB RAM: player ~30MB footprint, VLC ~100MB during playback
- Image duration = VLC `--image-duration` flag
- Video plays full length (duration field = max timeout)
- Media cached locally, survives reboot, re-downloaded on hash mismatch
