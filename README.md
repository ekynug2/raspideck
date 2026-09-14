# RaspiDeck — Self-Hosted Digital Signage Platform

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%203B%2B%20%7C%204%20%7C%205%20%7C%20Zero%202W-red.svg)](https://www.raspberrypi.com/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)
[![Version](https://img.shields.io/badge/version-v2.2.7-brightgreen.svg)](player/VERSION)

**RaspiDeck** adalah sistem Digital Signage CMS dan Kiosk Player *self-hosted* yang dirancang khusus untuk Raspberry Pi (3 B+, 4, 5, dan Zero 2 W). 

Menyediakan Web Management Dashboard terpusat di server Anda serta client pemutar video/gambar berakselerasi hardware yang stabil, tahan offline, dan dapat dipantau dari jarak jauh secara visual.

---

## 🚀 Fitur Utama

### 🖥️ Display & Playback Management
- **Hardware-Accelerated Playback**: Pemutaran video 1080p/4K 60 FPS yang mulus menggunakan engine VLC dengan decoding hardware (OMX / MMAL / DRM).
- **Offline Resilience**: Cache media lokal dengan verifikasi SHA-256 chunked hashing. Tampilan tetap berjalan lancar tanpa layar hitam meskipun koneksi internet/LAN terputus.
- **Granular Per-Display Settings**: Atur Volume (0–100%), Rotasi Layar (0°, 90°, 180°, 270°), Polling Interval (5s–120s), dan Power Layar (DPMS Standby) secara independen per display langsung dari dashboard web.
- **Automated Pairing Flow**: Layar baru otomatis menampilkan 6-digit pairing code di TV untuk aktivasi cepat 1-klik dari dashboard.
- **Urutan Display Stabil**: Posisi kartu monitor di dashboard diurutkan rapi berdasarkan nama sehingga tidak melompat saat refresh atau polling API.

### 📸 Visual Screen Snapshot & Playback Health (Fitur Baru)
- **Real-Time Visual Snapshot**: Tangkap tampilan aktual yang sedang tayang di layar TV monitor Raspberry Pi secara langsung via LibVLC frame grab (resolusi jernih hingga 1280x720) dari menu *Device Diagnostics & Info*.
- **Deteksi Otomatis Video Freeze**: Memantau pergerakan timestamp pemutaran secara realtime. Notifikasi otomatis jika video macet atau berhenti berjalan.
- **Deteksi Shuttering / Patah-patah (Dropped Frames)**: Mengukur statistik decoding video secara presisi:
  - Drop Rate (%) & akumulasi frame hilang
  - Video FPS aktual
  - Total frame yang berhasil ditampilkan
  - Posisi waktu pemutaran berjalan

### 🛡️ Enterprise OTA (Over-The-Air) Update
- **Zero-Downtime Atomic Symlink Swap**: Pembaruan sistem aman ke direktori versi baru dengan pertukaran symlink atomik (`current -> versions/vX.X`).
- **Integritas Kriptografi & Resumable Download**: Verifikasi checksum SHA-256 dan dukungan HTTP `Range` untuk melanjutkan download jika koneksi tidak stabil.
- **Auto Rollback & Watchdog**: Otomatis kembali ke versi stabil sebelumnya jika rilis baru gagal boot atau bermasalah.
- **Batch Upgrade**: Update satu layar atau seluruh layar sekaligus dalam satu klik.

---

## 🏗️ Arsitektur Sistem

```
                      ┌─────────────────────────────────────────────────────────┐
                      │                    RaspiDeck Server                     │
                      │                 (Docker / VPS / Local)                  │
                      ├─────────────────────────────────────────────────────────┤
                      │  - Flask REST API (Gunicorn + Event Handlers)           │
                      │  - SQLite Database (WAL Mode, deck.db)                  │
                      │  - Modern Web Dashboard (Tabler UI)                     │
                      │  - Snapshot Storage (/data/snapshots) & OTA Builder     │
                      └────────────────────────────┬────────────────────────────┘
                                                   │
                                    HTTP/HTTPS REST API (JSON / Base64)
                                - Bearer Token Auth & Polling Heartbeat
                                - Command Queue (Snapshot, Reload, Update)
                                - Resumable Media & OTA Downloads
                                                   │
                      ┌────────────────────────────┴────────────────────────────┐
                      │             RaspiDeck Player (Raspberry Pi)             │
                      │           /opt/raspideck/current -> versions/v2.2.7     │
                      ├─────────────────────────────────────────────────────────┤
                      │  - Kiosk Supervisor & systemd (raspideck.service)       │
                      │  - Playback Engine (LibVLC Fullscreen Loop)             │
                      │  - Live Frame Capture & Playback Health Diagnostic      │
                      │  - Settings Daemon (xrandr rotation, ALSA volume, DPMS) │
                      │  - Local Cache (SHA-256 Checksum & Offline Fallback)    │
                      │  - Safe OTA Updater & Hardware Watchdog Protection      │
                      └─────────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Direktori

```
raspi-deck/
├── docker-compose.yml           # Konfigurasi container deployment
├── example.db                   # Database demonstrasi awal (opsional)
├── server/                      # Server Management Dashboard & API
│   ├── app.py                   # Inisialisasi Flask server
│   ├── config.py                # Konfigurasi server & path storage
│   ├── db.py                    # Schema SQLite, migrasi kolom & WAL mode
│   ├── ota.py                   # Build & verifikasi paket update OTA
│   ├── routes/
│   │   ├── web.py               # Rute halaman dashboard & login
│   │   ├── admin_api.py         # REST API pengelolaan screens, media, snapshot
│   │   └── player_api.py        # REST API komunikasi player (heartbeat, snapshot)
│   ├── static/js/               # Frontend logic (screens.js, playlists.js, media.js)
│   └── templates/               # Template tampilan dashboard
└── player/                      # Client Player Raspberry Pi
    ├── player.py                # Main loop player, snapshot uploader & scheduler
    ├── VERSION                  # Versi player saat ini (v2.2.7)
    ├── install.sh               # Skrip instalasi otomatis Raspberry Pi OS
    └── core/
        ├── playback.py          # Kontrol LibVLC, screen grab & analisis freeze/stutter
        ├── settings.py          # Eksekutor rotasi, volume, dan power layar
        ├── telemetry.py         # Pengumpul metrik CPU, RAM, suhu, dan disk
        ├── updater.py           # OTA download, symlink swap & rollback
        ├── cache.py             # Manajemen file cache lokal media
        └── screens.py           # Generator visual pairing code & splash screen
```

---

## ⚡ Panduan Instalasi Cepat

### 1. Server Deployment (Docker Compose)

1. Clone repositori:
   ```bash
   git clone https://github.com/ekynug2/raspideck.git
   cd raspi-deck
   ```

2. Siapkan file environment:
   ```bash
   cp .env.example .env
   # Buka dan sesuaikan ADMIN_PASSWORD dan SECRET_KEY
   nano .env
   ```

3. Jalankan container:
   ```bash
   docker compose up -d
   ```
   Akses dashboard melalui browser di `http://<IP-SERVER>:8000`.

---

### 2. Player Client Deployment (Raspberry Pi)

#### Metode A: Plug-and-Play MicroSD (Praktis untuk Cabang / Outlet)
1. Flash **Raspberry Pi OS Lite (64-bit / 32-bit)** menggunakan **Raspberry Pi Imager** (isi setelan Wi-Fi outlet pada opsi OS Customization).
2. Di partisi `boot` microSD yang telah di-flash, buat file bernama `raspideck.txt`:
   ```ini
   SERVER_URL=http://<IP-SERVER>:8000
   ```
3. Masukkan microSD ke Raspberry Pi dan hidupkan daya.
4. Player otomatis boot ke mode kiosk dan menampilkan 6-digit kode pairing di layar TV.

#### Metode B: Instalasi Manual via SSH
1. Salin folder `player/` ke Raspberry Pi:
   ```bash
   rsync -avz player/ pi@<IP-RASPBERRY-PI>:/home/pi/player/
   ```
2. Jalankan skrip installer:
   ```bash
   cd /home/pi/player
   chmod +x install.sh
   sudo ./install.sh http://<IP-SERVER>:8000
   ```
   Sistem akan menginstal dependensi (VLC, Openbox, Python dependencies), mendaftarkan systemd service `raspideck.service`, dan me-reboot ke tampilan digital signage.

---

## ⚙️ Pengaturan Per-Display & Diagnostik

Setiap layar yang terhubung dapat dikontrol secara spesifik melalui Web Dashboard:

| Pengaturan | Tipe | Nilai | Aksi Hardware |
|---|---|---|---|
| `audio_volume` | Integer | `0` – `100` (%) | Menyesuaikan volume output audio aktif (HDMI/Jack) via ALSA `amixer`. |
| `screen_rotation` | Integer | `0`, `90`, `180`, `270` | Memutar orientasi tampilan TV secara dinamis via `xrandr`. |
| `screen_power` | Boolean | `true` / `false` | Menghidupkan/mematikan sinyal layar (standby hemat daya) via DPMS. |
| `poll_interval` | Integer | `5` – `120` (detik) | Interval pengiriman heartbeat dan sinkronisasi playlist. |

### Menggunakan Visual Snapshot & Playback Diagnostic:
1. Buka dashboard web, klik tombol **Device Diagnostic & Info** pada kartu layar yang diinginkan.
2. Klik tombol **"Ambil Snapshot Baru"**.
3. Dalam hitungan detik:
   - **Tangkapan Layar TV** muncul (klik untuk memperbesar).
   - **Status Kualitas Layar** menampilkan evaluasi:
     - 🟢 **NORMAL / LANCAR**: Drop rate < 1.0%
     - 🟡 **SHUTTERING / PATAH-PATAH**: Tingginya frame drop karena decoding berat
     - 🔴 **VIDEO MACET / FREEZE**: Frame tidak bergerak maju
   - Tampilan rincian FPS, frame drop, frame tertayang, dan durasi video.

---

## 📡 REST API Ringkas

### Endpoint Player (`/api/player/*`)
- `POST /api/player/heartbeat`: Kirim telemetri hardware & terima playlist/settings.
- `POST /api/player/snapshot`: Unggah tangkapan layar monitor & data diagnosa pemutaran.
- `GET /api/player/media/<filename>`: Unduh/stream file media aset playlist.
- `GET /api/player/update/manifest`: Cek metadata rilis OTA terbaru.
- `GET /api/player/update/download`: Unduh file tarball OTA (mendukung resume `Range`).
- `POST /api/player/update/status`: Lapor progres instalasi OTA.

### Endpoint Manajemen Admin (`/api/*`)
- `GET /api/screens`: Daftar layar terhubung, telemetri, dan status kualitas.
- `POST /api/screens/<id>/pair`: Verifikasi dan setujui kode pairing layar.
- `PATCH /api/screens/<id>/settings`: Simpan perubahan volume, rotasi, atau daya layar.
- `POST /api/screens/<id>/snapshot`: Kirim instruksi capture snapshot ke layar.
- `GET /api/screens/<id>/snapshot`: Ambil status ketersediaan snapshot & diagnosa video.
- `GET /api/screens/<id>/snapshot.jpg`: Tampilkan file gambar tangkapan layar monitor.
- `POST /api/screens/<id>/update`: Jadwalkan OTA update untuk display tertentu.
- `POST /api/screens/update-all`: Jadwalkan OTA update serentak untuk semua display.
- `GET|POST|DELETE /api/media`: Manajemen upload dan hapus aset video/gambar.
- `GET|POST|PUT|DELETE /api/playlists`: Manajemen urutan dan jadwal tayang playlist.

---

## 🔧 Variabel Konfigurasi (`.env`)

| Variabel | Default | Keterangan |
|---|---|---|
| `ADMIN_PASSWORD` | *(Wajib)* | Password masuk dashboard admin. |
| `SECRET_KEY` | *(Otomatis)* | Kunci enkripsi session Flask. |
| `DB_PATH` | `/data/deck.db` | Lokasi file database SQLite. |
| `MEDIA_DIR` | `/data/media` | Lokasi penyimpanan file video/gambar. |
| `SNAPSHOTS_DIR`| `/data/snapshots` | Lokasi penyimpanan gambar snapshot monitor. |
| `UPDATES_DIR` | `/data/updates` | Lokasi penyimpanan arsip paket OTA. |
| `MAX_CONTENT_LENGTH` | `500` | Batas maksimum upload file (MB). |
| `PORT` | `8000` | Port layanan HTTP dashboard. |

---

## ❓ FAQ & Pemecahan Masalah

#### Q: Bagaimana cara melihat log langsung di Raspberry Pi?
```bash
journalctl -u raspideck.service -f
```

#### Q: Apa yang terjadi jika Wi-Fi atau internet mati?
Player otomatis beralih ke mode offline dan terus memutar playlist dari cache lokal tanpa henti. Saat jaringan kembali online, player akan otomatis tersambung kembali ke server.

#### Q: Mengapa rotasi layar tidak berubah?
Pastikan player diinstal menggunakan `player/install.sh` agar server X11 dan Openbox terkonfigurasi dengan hak akses `xrandr` yang tepat.
