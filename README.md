# RaspiDeck — Self-Hosted Digital Signage Platform

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%203B%2B%20%7C%204%20%7C%205%20%7C%20Zero%202W-red.svg)](https://www.raspberrypi.com/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)
[![Version](https://img.shields.io/badge/version-v2.2.7-brightgreen.svg)](player/VERSION)

**RaspiDeck** adalah platform Digital Signage CMS dan Kiosk Player *self-hosted* yang dirancang khusus untuk lini perangkat Raspberry Pi (Raspberry Pi 3 Model B/B+, 4, 5, dan Zero 2 W).

Sistem ini menggabungkan **Web Management Dashboard** terpusat di server (dilengkapi integrasi Cloudflare Tunnel) dengan **Kiosk Player** berbasis LibVLC yang berakselerasi hardware, tahan pemadaman jaringan (offline resilience), dapat dipantau visualnya secara *real-time* via snapshot, serta mendukung pembaruan kode atomik Over-The-Air (OTA).

---

## 🚀 Fitur Utama

### 🖥️ Display & Playback Management
- **Hardware-Accelerated Video**: Pemutaran video 1080p/4K 60 FPS menggunakan LibVLC dengan akselerasi decoding hardware (OMX / MMAL / DRM).
- **Offline Resilience**: Cache media lokal dengan verifikasi chunked hashing SHA-256. Konten tetap tayang tanpa henti meskipun internet atau koneksi ke server terputus.
- **Pengaturan Per-Display Mandiri**: Atur volume audio, rotasi layar, interval heartbeat, dan status daya display langsung dari dashboard web per masing-masing layar.
- **Playlist Scheduling**: Atur durasi tayang tiap item media serta jadwal aktif playlist (jam mulai/selesai dan pilihan hari dalam seminggu).
- **Automated Pairing Flow**: Layar baru otomatis menampilkan 6-digit kode pairing di TV untuk aktivasi cepat 1-klik dari dashboard.
- **Urutan Display Stabil**: Tampilan kartu terminal di dashboard diurutkan rapi berdasarkan nama sehingga posisi kartu tidak melompat saat pembaruan data.
- **Aksi Kontrol Jarak Jauh**: Restart player service, lewati media (*skip*), ping/identifikasi layar, dan unpair display langsung dari web UI.

### 📸 Visual Screen Snapshot & Playback Health
- **Live Visual Screen Snapshot**: Tangkap frame tampilan aktual yang sedang tayang di layar monitor Raspberry Pi secara langsung via LibVLC frame grab (resolusi jernih hingga 1280x720) dari menu *Device Diagnostics & Info*.
- **Deteksi Otomatis Video Freeze**: Memantau pergerakan timestamp pemutaran. Sistem mendeteksi otomatis jika video macet atau berhenti berjalan.
- **Deteksi Shuttering / Patah-patah (Frame Drop)**: Mengukur performa decoding video secara akurat:
  - 🟢 **NORMAL / LANCAR**: Drop rate < 1.0% (playback mulus)
  - 🟡 **SHUTTERING / PATAH-PATAH**: Tingginya frame drop (> 1.5%) karena beban decoding/CPU
  - 🔴 **VIDEO MACET / FREEZE**: Frame tidak bergerak maju (> 350ms)
  - Statistik lengkap: Video FPS, frame drop / hilang, frame tertayang, dan posisi pemutaran.

### 🛡️ Enterprise Safe OTA (Over-The-Air) Updates
- **Zero-Downtime Atomic Symlink Swap**: Update kode diekstrak ke direktori `/opt/raspideck/versions/vX.X/` lalu ditukar secara atomik (`current -> versions/vX.X`).
- **Integritas SHA-256 & Resumable Download**: Verifikasi checksum kriptografi dan dukungan HTTP `Range` untuk melanjutkan unduhan paket update saat jaringan tidak stabil.
- **Proteksi Hardware Watchdog & Rollback**: Jika versi baru gagal boot atau bermasalah, player otomatis kembali (*rollback*) ke versi stabil sebelumnya.
- **Batch Upgrade**: Update satu layar atau seluruh layar sekaligus dalam satu klik dari dashboard.

---

## 🏗️ Arsitektur Sistem

```
                      ┌─────────────────────────────────────────────────────────┐
                      │                    RaspiDeck Server                     │
                      │                 (Docker / VPS / Local)                  │
                      ├─────────────────────────────────────────────────────────┤
                      │  - Flask REST API (Gunicorn + Event Handlers)           │
                      │  - SQLite Database (WAL Mode, /data/deck.db)            │
                      │  - Modern Web Dashboard (Tabler UI, Dark/Light Mode)    │
                      │  - Cloudflare Tunnel (raspideck-tunnel)                 │
                      │  - Storage: /data/media, /data/snapshots, /data/updates │
                      └────────────────────────────┬────────────────────────────┘
                                                   │
                                    HTTP/HTTPS REST API (JSON / Base64)
                                - Bearer Token Auth & Polling Heartbeat
                                - Command Queue (Snapshot, Restart, Skip)
                                - Resumable Media & OTA Downloads
                                                   │
                      ┌────────────────────────────┴────────────────────────────┐
                      │             RaspiDeck Player (Raspberry Pi)             │
                      │           /opt/raspideck/current -> versions/v2.2.7     │
                      ├─────────────────────────────────────────────────────────┤
                      │  - Kiosk Supervisor (raspideck.service via systemd)     │
                      │  - Playback Engine (LibVLC Fullscreen Loop)             │
                      │  - Live Frame Capture & Playback Health Diagnostic      │
                      │  - Settings Manager (xrandr, amixer ALSA, DPMS xset)    │
                      │  - Plymouth Boot Splash & Quiet Boot (Tanpa flicker)    │
                      │  - Local Cache (SHA-256 Verification & Fallback)        │
                      │  - Safe OTA Updater & Hardware Watchdog Protection      │
                      └─────────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Direktori

```
raspi-deck/
├── docker-compose.yml           # Orkestrasi Docker (Server + Cloudflare Tunnel)
├── example.db                   # Database demonstrasi awal (opsional)
├── server/                      # Aplikasi Server & Web Dashboard
│   ├── app.py                   # Inisialisasi aplikasi Flask
│   ├── config.py                # Parsing environment & konfigurasi path
│   ├── db.py                    # Schema SQLite, auto-migrasi kolom, WAL mode
│   ├── auth.py                  # Autentikasi sesi admin & rate limiting login
│   ├── ota.py                   # Build & verifikasi paket OTA (raspideck-player.tar.gz)
│   ├── routes/
│   │   ├── web.py               # Halaman web dashboard, login/logout, preview splash
│   │   ├── admin_api.py         # REST API screens, settings, snapshot, media, playlist
│   │   └── player_api.py        # REST API komunikasi player (heartbeat, snapshot, OTA)
│   ├── static/                  # Asset CSS, JS modular (screens, playlists, media), vendor
│   └── templates/               # Template Jinja2 Tabler UI
└── player/                      # Client Player Raspberry Pi
    ├── player.py                # Main loop player, snapshot handler, command poller
    ├── VERSION                  # Versi player (v2.2.7)
    ├── install.sh               # Skrip instalasi otomatis Raspberry Pi OS
    ├── generate_splash.py       # Generator gambar splash boot (Pillow)
    ├── bin/
    │   └── restart-player.sh    # Wrapper sudo terbatas untuk restart aman service
    └── core/
        ├── config.py            # Deteksi Device ID, resolusi server URL & token
        ├── playback.py          # Engine LibVLC, frame capture & diagnosa performa
        ├── settings.py          # Eksekusi setting hardware (volume, rotation, DPMS)
        ├── telemetry.py         # Pengumpul metrik hardware (CPU, RAM, suhu, disk, HDMI)
        ├── updater.py           # Engine download OTA, symlink swap & rollback
        ├── cache.py             # Manajemen file cache lokal media
        └── screens.py           # Render visual pairing code & status overlay
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
   nano .env
   ```
   *Atur `ADMIN_PASSWORD`, `SECRET_KEY`, dan `CLOUDFLARE_TUNNEL_TOKEN` (opsional jika menggunakan Cloudflare Tunnel).*

3. Jalankan container:
   ```bash
   docker compose up -d
   ```
   Buka `http://<IP-SERVER>:8000` di browser Anda dan masuk menggunakan password admin yang telah dikonfigurasi.

---

### 2. Player Deployment (Raspberry Pi)

#### Metode A: Plug-and-Play MicroSD (Direkomendasikan untuk Cabang / Outlet)
1. Flash **Raspberry Pi OS Lite (64-bit / 32-bit)** ke microSD menggunakan **Raspberry Pi Imager**.
   - Pada setelan Imager, aktifkan SSH dan masukkan konfigurasi Wi-Fi.
2. Di partisi `boot` microSD (dapat dibuka langsung di Windows/Mac), buat file teks bernama `raspideck.txt`:
   ```ini
   SERVER_URL=http://<IP-SERVER>:8000
   ```
3. Pasang microSD ke Raspberry Pi dan hidupkan perangkat.
4. Player otomatis boot dengan boot splash RaspiDeck dan menampilkan 6-digit kode pairing di layar TV.

#### Metode B: Instalasi Manual via SSH
1. Salin folder `player/` ke Raspberry Pi:
   ```bash
   rsync -avz player/ pi@<IP-PI>:/home/pi/player/
   ```
2. Jalankan skrip installer:
   ```bash
   cd /home/pi/player
   chmod +x install.sh
   sudo ./install.sh http://<IP-SERVER>:8000
   ```
   Skrip installer otomatis:
   - Menginstal VLC, X11 minimal kiosk stack (`matchbox-window-manager`, `unclutter`), dan library Python.
   - Mengonfigurasi boot splash Plymouth tema RaspiDeck dan quiet boot tanpa teks log kernel.
   - Mengalokasikan 512MB GPU memory dan 512MB swap.
   - Mendaftarkan dan mengaktifkan service `raspideck.service`.
   - Mengatur hak akses restart aman di `/etc/sudoers.d/raspideck-ota`.

---

## ⚙️ Pengaturan Per-Display & Diagnostik

Setiap display terminal dapat diatur secara independen melalui modal **Settings** di web dashboard:

| Kunci Setting | Tipe Data | Nilai yang Didukung | Aksi Hardware / Sistem |
|---|---|---|---|
| `volume` | Integer | `0` – `100` (%) | Menyesuaikan volume audio ALSA (`amixer`) pada output aktif (HDMI / Jack 3.5mm). |
| `rotation` | String | `'normal'`, `'right'`, `'inverted'`, `'left'` | Mengubah rotasi orientasi layar (0°, 90°, 180°, 270°) via `xrandr`. |
| `screen_power` | String | `'on'`, `'off'` | Mengaktifkan atau menidurkan sinyal display via DPMS (`xset dpms force on/off`). |
| `heartbeat_interval` | Integer | `5` – `120` (detik) | Mengatur frekuensi pengiriman telemetri dan sinkronisasi perintah player. |

### Menggunakan Visual Snapshot & Playback Diagnostic:
1. Buka tab **Displays**, klik tombol **Device Diagnostic & Info** pada kartu outlet yang diinginkan.
2. Klik tombol **"Ambil Snapshot Baru"**.
3. Dalam 3–5 detik:
   - Foto tampilan visual TV monitor terkini akan langsung tampil (dapat diklik untuk melihat ukuran penuh).
   - Indikator **Status Kualitas Layar** menampilkan evaluasi kesehatan video:
     - 🟢 **NORMAL / LANCAR**: Drop rate < 1.0%
     - 🟡 **SHUTTERING / PATAH-PATAH**: Tingginya frame drop karena beban decoding
     - 🔴 **VIDEO MACET / FREEZE**: Frame tidak bergerak maju
   - Ringkasan metrik menampilkan: Video FPS, Jumlah Frame Drop, Frame Tertayang, dan Durasi Pemutaran.

---

## 📡 REST API Reference

### Player Endpoints
| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/api/player/heartbeat` | Mengirim telemetri hardware, menerima playlist aktif, settings dinamis, dan manifest OTA. |
| `POST` | `/api/player/snapshot` | Mengunggah gambar tangkapan layar (base64) beserta data evaluasi kesehatan pemutaran. |
| `GET` | `/api/player/command` | Memeriksa antrean perintah pending (`snapshot`, `restart`, `skip`, `ping`). |
| `GET` | `/media/<filename>` | Mengunduh atau men-stream file aset media playlist. |
| `GET` | `/media/thumbnails/<filename>` | Mengambil gambar thumbnail preview media. |
| `GET` | `/api/player/update/manifest` | Memeriksa metadata versi OTA terbaru server (versi, hash SHA-256, ukuran). |
| `GET` | `/api/player/update/download` | Mengunduh paket update `raspideck-player.tar.gz` (mendukung HTTP `Range` resume). |
| `POST` | `/api/player/update/status` | Melaporkan status tahapan instalasi update OTA (`downloading`, `applying`, `success`, `failed`). |

### Admin Management Endpoints
| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/api/screens` | Daftar semua display terdaftar beserta telemetri, pengaturan, dan status update. |
| `POST` | `/api/screens/<id>/pair` | Memverifikasi dan menyetujui kode pairing display baru. |
| `POST` | `/api/screens/<id>/unpair` | Menghapus status pairing dan mereset token display. |
| `PATCH` | `/api/screens/<id>` | Mengubah nama display atau menetapkan playlist aktif. |
| `DELETE`| `/api/screens/<id>` | Menghapus terminal display dari sistem. |
| `GET` / `PATCH` | `/api/screens/<id>/settings` | Mengambil atau memperbarui pengaturan individual display (`volume`, `rotation`, dll). |
| `POST` | `/api/screens/<id>/snapshot` | Mengirim perintah antrean capture screenshot ke display. |
| `GET` | `/api/screens/<id>/snapshot` | Mengambil status ketersediaan snapshot dan diagnosa performa video. |
| `GET` | `/api/screens/<id>/snapshot.jpg` | Menampilkan file gambar JPEG tangkapan layar monitor. |
| `POST` | `/api/screens/<id>/restart` | Memicu restart aman service player di Raspberry Pi. |
| `POST` | `/api/screens/<id>/skip` | Melompati media yang sedang diputar ke item playlist berikutnya. |
| `POST` | `/api/screens/<id>/ping` | Mengidentifikasi layar dengan menampilkan overlay visual sekejap. |
| `POST` | `/api/screens/<id>/update` | Menjadwalkan update kode OTA untuk display tertentu. |
| `POST` | `/api/screens/update-all` | Menjadwalkan update kode OTA serentak untuk semua display yang versinya usang. |
| `GET` | `/api/system/player-version` | Melihat versi paket player yang siap didistribusikan di server. |
| `POST` | `/api/system/player-package/build` | Mem-build ulang arsip paket `raspideck-player.tar.gz` di server. |
| `GET` / `POST` | `/api/media` | Mengambil daftar file media atau mengunggah video/gambar baru. |
| `DELETE`| `/api/media/<id>` | Menghapus file media dari database dan disk server. |
| `GET` / `POST` | `/api/playlists` | Mengambil daftar playlist atau membuat playlist baru. |
| `PUT` / `DELETE`| `/api/playlists/<id>` | Memperbarui urutan/jadwal playlist atau menghapus playlist. |

---

## 🔧 Konfigurasi Environment (`.env`)

### Konfigurasi Server
| Variabel | Default | Deskripsi |
|---|---|---|
| `ADMIN_PASSWORD` | *(Wajib)* | Kata sandi untuk masuk ke web dashboard admin. |
| `SECRET_KEY` | *(Otomatis)* | Kunci rahasia untuk enkripsi session cookie Flask. |
| `DB_PATH` | `/data/deck.db` | Jalur absolut lokasi file database SQLite. |
| `MEDIA_DIR` | `/data/media` | Direktori penyimpanan file video dan gambar playlist. |
| `SNAPSHOTS_DIR` | `/data/snapshots` | Direktori penyimpanan tangkapan layar monitor dari player. |
| `UPDATES_DIR` | `/data/updates` | Direktori penyimpanan file paket pembaruan OTA. |
| `MAX_CONTENT_LENGTH` | `100` | Batas maksimum ukuran unggahan media dalam Megabytes (MB). |
| `HTTPS_ONLY` | `false` | Menyetel atribut secure cookie saat server diakses via HTTPS. |
| `CORS_ORIGINS` | *(Local & LAN)* | Daftar origin atau regex pola yang diizinkan mengakses API. |
| `CLOUDFLARE_TUNNEL_TOKEN` | *(Opsional)* | Token Cloudflare Tunnel untuk publikasi dashboard tanpa port-forwarding. |
| `PORT` | `8000` | Port HTTP yang digunakan oleh Gunicorn/Server. |

### Konfigurasi Player Raspberry Pi (`/boot/raspideck.txt` atau Systemd)
| Variabel / Kunci | Default | Deskripsi |
|---|---|---|
| `SERVER_URL` | `http://localhost:8000` | Alamat URL server RaspiDeck (dapat ditulis di file boot microSD). |
| `RASPIDECK_SERVER` | *(Dari boot file)* | Variabel environment URL server pada systemd. |
| `RASPIDECK_MEDIA_DIR` | `/opt/raspideck/media` | Direktori cache media lokal di Raspberry Pi. |
| `RASPIDECK_POLL_INTERVAL`| `30` | Interval fallback polling heartbeat (detik). |
| `RASPIDECK_DEVICE_ID` | *(Serial Pi)* | Pengenal unik perangkat (otomatis membaca serial hardware Pi). |

---

## ❓ FAQ & Pemecahan Masalah

#### Q: Bagaimana cara melihat log langsung di Raspberry Pi?
Gunakan perintah systemd berikut via SSH terminal Raspberry Pi:
```bash
journalctl -u raspideck.service -f
```
Atau lihat file log lokal:
```bash
tail -f /opt/raspideck/player.log
```

#### Q: Apa yang terjadi jika Wi-Fi atau internet mati?
Player otomatis beralih ke mode offline. Player akan memutar seluruh aset dari direktori cache lokal (`/opt/raspideck/media/`) secara terus-menerus tanpa gangguan layar hitam. Saat jaringan kembali normal, player otomatis tersambung kembali ke server.

#### Q: Mengapa suara video tidak keluar dari speaker TV?
Pastikan output audio HDMI dipilih. Skrip installer secara default menyetel ALSA card 0 untuk HDMI di `/etc/asound.conf`. Anda juga dapat menyesuaikan volume melalui modal **Settings** display di web dashboard atau memeriksa `alsamixer`.

#### Q: Mengapa rotasi layar tidak berfungsi setelah diubah?
Rotasi layar dijalankan via utilitas X11 `xrandr`. Pastikan instalasi player dilakukan melalui `player/install.sh` sehingga display manager dan sesi Openbox terkonfigurasi dengan hak akses yang sesuai.
