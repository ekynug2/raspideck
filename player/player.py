#!/usr/bin/env python3
"""RaspiDeck Pi Player — polls server, displays Windows boot loader, loading media, and plays media."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure player directory is in sys.path
PLAYER_DIR = Path(__file__).resolve().parent
if str(PLAYER_DIR) not in sys.path:
    sys.path.insert(0, str(PLAYER_DIR))

from core.api import api_get, api_post, download_media
from core.cache import compute_sha256, load_cached_playlist, save_cached_playlist
from core.config import (
    APP_VERSION,
    HEARTBEAT_INTERVAL,
    MEDIA_DIR,
    SERVER_URL,
    get_device_id,
    load_server_url,
)
from core.gui import PlayerScreenApp
from core.playback import (
    play_image,
    play_video,
    request_skip,
    stop_playback,
)
from core.settings import (
    apply_all_settings,
    compute_settings_hash,
    load_settings,
    save_settings,
)
from core.telemetry import get_system_info
from core.updater import execute_update

# Shared state between playback, GUI, and heartbeat threads
PLAYLIST_LOCK = threading.Lock()
LATEST_PLAYLIST: dict[str, Any] | None = None
LATEST_STATUS: str | None = None
LATEST_PAIRING_CODE: str | None = None
IS_ONLINE: bool = True
CURRENT_PLAYING: dict[str, str | None] = {"filename": None, "media_type": None}
CURRENT_UPDATE_STATUS: str = "idle"
DYNAMIC_HEARTBEAT_INTERVAL: int = HEARTBEAT_INTERVAL

# Global GUI instance (managed on main thread)
SCREEN_APP = PlayerScreenApp()


def handle_remote_command(cmd: str) -> None:
    """Handle remote command from dashboard (skip media, restart player, or reboot pi)."""
    if cmd == "skip":
        print("[player] Received SKIP command from server. Skipping current media...", flush=True)
        request_skip()
        return

    stop_playback()
    if cmd == "reboot":
        print("[player] Received REBOOT command from server. Rebooting system...", flush=True)
        try:
            SCREEN_APP.show()
            SCREEN_APP.set_boot(
                status="Memulai Ulang Raspberry Pi...",
                detail="Perintah reboot dari web dashboard...",
            )
        except Exception:
            pass
        time.sleep(1.5)
        os.system("sudo reboot")
    elif cmd == "restart":
        print("[player] Received RESTART command from server. Restarting player...", flush=True)
        try:
            SCREEN_APP.show()
            SCREEN_APP.set_boot(
                status="Memulai Ulang Player...",
                detail="Perintah restart dari web dashboard...",
            )
        except Exception:
            pass
        time.sleep(1.5)
        os.system("sudo systemctl restart raspideck &")
        sys.exit(0)


def command_worker(device_id: str) -> None:
    """Fast background thread polling remote commands (skip, restart, reboot) with low latency."""
    while True:
        try:
            load_server_url()
            resp = api_get(f"/api/player/command?device_id={device_id}")
            if resp and resp.get("command"):
                cmd = resp.get("command")
                handle_remote_command(cmd)
                if cmd in ("reboot", "restart"):
                    return
        except Exception:
            pass
        time.sleep(1.5)


def is_within_schedule(schedule: dict[str, Any] | None) -> tuple[bool, str]:
    """Check if current local time is within the playlist schedule.

    Returns (is_active, status_message).
    All times in strict 24-hour HH:MM format (00:00 - 23:59).
    """
    if not schedule or not schedule.get("enabled"):
        return True, "Jadwal selalu aktif (24 jam non-stop)"

    start_str = str(schedule.get("start_time") or "00:00").strip()[:5]
    end_str = str(schedule.get("end_time") or "23:59").strip()[:5]
    active_days = schedule.get("days") or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    now = datetime.now()
    cur_day = now.strftime("%a").lower()[:3]  # mon, tue, wed, thu, fri, sat, sun
    if cur_day not in active_days:
        day_names = {
            "mon": "Senin", "tue": "Selasa", "wed": "Rabu", "thu": "Kamis",
            "fri": "Jumat", "sat": "Sabtu", "sun": "Minggu"
        }
        return False, f"Hari {day_names.get(cur_day, cur_day.upper())} tidak dijadwalkan tayang"

    cur_hm = now.strftime("%H:%M")  # 24-hour format

    # Same-day interval (e.g. 08:00 to 22:00)
    if start_str <= end_str:
        if start_str <= cur_hm <= end_str:
            return True, f"Dalam jam tayang ({start_str} - {end_str})"
        return False, f"Di luar jam tayang ({start_str} - {end_str})"

    # Overnight interval (e.g. 22:00 to 04:00)
    if cur_hm >= start_str or cur_hm <= end_str:
        return True, f"Dalam jam tayang semalam ({start_str} - {end_str})"
    return False, f"Di luar jam tayang semalam ({start_str} - {end_str})"


def heartbeat_worker(device_id: str) -> None:
    """Continuous background thread reporting hardware telemetry, applying settings, and executing OTA updates."""
    global IS_ONLINE, LATEST_PAIRING_CODE, LATEST_PLAYLIST, LATEST_STATUS, CURRENT_UPDATE_STATUS, DYNAMIC_HEARTBEAT_INTERVAL
    while True:
        try:
            load_server_url()
            info = get_system_info(CURRENT_PLAYING)
            resp = api_post(
                "/api/player/heartbeat",
                {
                    "device_id": device_id,
                    "system_info": info,
                    "app_version": APP_VERSION,
                    "update_status": CURRENT_UPDATE_STATUS,
                },
            )
            if resp and resp.get("command"):
                cmd = resp.get("command")
                handle_remote_command(cmd)
                if cmd in ("reboot", "restart"):
                    return

            # 1. Synchronize Display Settings
            if resp and resp.get("settings"):
                srv_settings = resp.get("settings")
                if isinstance(srv_settings, dict):
                    loc_settings = load_settings()
                    if compute_settings_hash(srv_settings) != compute_settings_hash(loc_settings):
                        print("[player] Received updated display settings from server. Applying...", flush=True)
                        save_settings(srv_settings)
                        apply_all_settings(srv_settings)
                    if "heartbeat_interval" in srv_settings:
                        try:
                            DYNAMIC_HEARTBEAT_INTERVAL = int(srv_settings["heartbeat_interval"])
                        except (ValueError, TypeError):
                            pass

            # 2. Handle OTA Software Update
            if resp and resp.get("update"):
                upd_manifest = resp.get("update")
                if isinstance(upd_manifest, dict):
                    target_ver = upd_manifest.get("version")
                    if target_ver and target_ver != APP_VERSION:
                        print(f"[player] OTA update received (v{APP_VERSION} -> v{target_ver}). Starting updater...", flush=True)
                        CURRENT_UPDATE_STATUS = "downloading"
                        stop_playback()
                        try:
                            SCREEN_APP.show()
                            SCREEN_APP.set_boot(
                                status="Memperbarui Sistem...",
                                detail=f"Menyiapkan pembaruan software v{target_ver}...",
                            )
                        except Exception:
                            pass

                        def _update_progress_cb(pct: int, detail: str):
                            try:
                                SCREEN_APP.update_progress(pct, detail=detail)
                            except Exception:
                                pass

                        def _do_update():
                            global CURRENT_UPDATE_STATUS
                            success = execute_update(upd_manifest, gui_progress_cb=_update_progress_cb)
                            if not success:
                                CURRENT_UPDATE_STATUS = "failed"

                        upd_thread = threading.Thread(target=_do_update, daemon=True)
                        upd_thread.start()
                        return

            with PLAYLIST_LOCK:
                if resp:
                    IS_ONLINE = True
                    LATEST_STATUS = resp.get("status")
                    LATEST_PAIRING_CODE = resp.get("pairing_code")
                    new_pl = resp.get("playlist")
                    if new_pl and new_pl.get("items"):
                        save_cached_playlist(new_pl)
                        LATEST_PLAYLIST = new_pl
                    elif LATEST_STATUS == "unpaired":
                        LATEST_PLAYLIST = None
                    else:
                        LATEST_PLAYLIST = {}
                else:
                    IS_ONLINE = False
        except OSError as e:
            print(f"[player-telemetry] Network/system error: {e}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[player-telemetry] Heartbeat error: {e}", flush=True)

        # Check faster (5s) if waiting for pairing, otherwise dynamic interval
        interval = 5 if LATEST_STATUS == "unpaired" else DYNAMIC_HEARTBEAT_INTERVAL
        time.sleep(interval)


def orchestrator_worker(device_id: str) -> None:
    """Main player orchestrator running in background worker thread."""
    global IS_ONLINE, LATEST_PAIRING_CODE, LATEST_PLAYLIST, LATEST_STATUS
    print(f"[player] Orchestrator started for device: {device_id}", flush=True)

    # 1. Start telemetry daemon and fast command poller threads
    hb_thread = threading.Thread(
        target=heartbeat_worker, args=(device_id,), daemon=True
    )
    hb_thread.start()

    cmd_thread = threading.Thread(
        target=command_worker, args=(device_id,), daemon=True
    )
    cmd_thread.start()

    # 2. Boot phase: display Windows boot screen with rotating dots loader
    boot_start = time.time()
    SCREEN_APP.set_boot(
        status="Memulai RaspiDeck...",
        detail="Memeriksa konfigurasi sistem & jaringan...",
    )

    # Fetch initial hardware info & IP address
    initial_info = get_system_info(CURRENT_PLAYING)
    local_ip = initial_info.get("local_ip", "")

    # Initial sync request with server
    try:
        resp = api_post(
            "/api/player/heartbeat",
            {
                "device_id": device_id,
                "system_info": initial_info,
            },
        )
        if resp and resp.get("command"):
            handle_remote_command(resp.get("command"))
            return

        with PLAYLIST_LOCK:
            if resp:
                IS_ONLINE = True
                LATEST_STATUS = resp.get("status")
                LATEST_PAIRING_CODE = resp.get("pairing_code")
                new_pl = resp.get("playlist")
                if new_pl and new_pl.get("items"):
                    save_cached_playlist(new_pl)
                    LATEST_PLAYLIST = new_pl
                elif LATEST_STATUS == "unpaired":
                    LATEST_PLAYLIST = None
                else:
                    LATEST_PLAYLIST = {}
            else:
                IS_ONLINE = False
    except OSError as e:
        print(f"[player] Initial sync failed: {e}", flush=True)

    # Brief initial boot phase to allow network handshake
    boot_elapsed = time.time() - boot_start
    if boot_elapsed < 1.0:
        time.sleep(1.0 - boot_elapsed)

    current_version = -1

    while True:
        with PLAYLIST_LOCK:
            status = LATEST_STATUS
            pairing_code = LATEST_PAIRING_CODE
            playlist = LATEST_PLAYLIST
            online = IS_ONLINE

        # State 1: UNPAIRED -> Show Pairing Code Screen
        if status == "unpaired":
            CURRENT_PLAYING["filename"] = None
            CURRENT_PLAYING["media_type"] = None
            stop_playback()
            SCREEN_APP.show()
            SCREEN_APP.set_pairing(
                pairing_code=pairing_code or "------",
                ip_address=local_ip,
                server_url=SERVER_URL,
                device_id=device_id,
            )
            time.sleep(2)
            continue

        # State 2: PAIRED but no playlist assigned yet
        if not playlist or not playlist.get("items"):
            if not online:
                cached = load_cached_playlist()
                if cached and cached.get("items"):
                    playlist = cached
                    print(
                        f"[player] Offline mode: playing cached playlist '{playlist.get('name')}' (v{playlist.get('version')})",
                        flush=True,
                    )
                else:
                    CURRENT_PLAYING["filename"] = None
                    CURRENT_PLAYING["media_type"] = None
                    stop_playback()
                    SCREEN_APP.show()
                    SCREEN_APP.set_waiting("Server Tidak Terjangkau (Mode Offline)")
                    time.sleep(3)
                    continue
            else:
                CURRENT_PLAYING["filename"] = None
                CURRENT_PLAYING["media_type"] = None
                stop_playback()
                SCREEN_APP.show()
                SCREEN_APP.set_waiting("Menunggu Playlist dari Server...")
                time.sleep(3)
                continue

        # State 3: PAIRED with Playlist
        version = playlist.get("version", 0)
        items = playlist.get("items", [])
        total_items = len(items)

        # 1. Check which media items actually need downloading
        missing_indices: list[int] = []
        for idx, item in enumerate(items):
            fname = item.get("filename")
            if not fname:
                missing_indices.append(idx)
                continue
            lpath = MEDIA_DIR / fname
            if not lpath.exists() or lpath.stat().st_size == 0:
                missing_indices.append(idx)
            elif item.get("sha256") and compute_sha256(lpath) != item.get("sha256"):
                missing_indices.append(idx)

        needs_download = len(missing_indices) > 0

        # Only show Loading/Downloading screen if there are ACTUALLY files to download!
        if needs_download:
            SCREEN_APP.show()
            SCREEN_APP.set_loading_media(
                status="Mengunduh Media...",
                detail=f"Mengunduh {len(missing_indices)} dari {total_items} konten...",
                progress_pct=5,
            )

        local_items = []
        missing_count = len(missing_indices)
        downloaded_count = 0

        for idx, item in enumerate(items):
            title = item.get("original_name") or item.get("filename")

            if idx in missing_indices:
                def make_progress_cb(item_num: int, item_title: str):
                    def _cb(downloaded_bytes: int, total_bytes: int):
                        if total_bytes > 0:
                            file_pct = int((downloaded_bytes / total_bytes) * 100)
                            item_fraction = downloaded_bytes / total_bytes
                            overall = int(((item_num + item_fraction) / max(1, missing_count)) * 90) + 5
                            SCREEN_APP.update_progress(
                                overall,
                                detail=f"Mengunduh ({item_num + 1}/{missing_count}): {item_title} ({file_pct}%)",
                            )
                        else:
                            overall = int((item_num / max(1, missing_count)) * 90) + 5
                            SCREEN_APP.update_progress(
                                overall,
                                detail=f"Mengunduh ({item_num + 1}/{missing_count}): {item_title}...",
                            )
                    return _cb

                cb = make_progress_cb(downloaded_count, title)
                downloaded_count += 1
            else:
                cb = None

            local_path = download_media(item, progress_callback=cb)
            if local_path and local_path.exists() and local_path.stat().st_size > 0:
                local_items.append({**item, "local_path": local_path})

        if not local_items:
            CURRENT_PLAYING["filename"] = None
            CURRENT_PLAYING["media_type"] = None
            stop_playback()
            SCREEN_APP.show()
            SCREEN_APP.set_waiting("Media Belum Tersedia di Penyimpanan Lokal")
            time.sleep(3)
            continue

        if needs_download:
            print(
                f"[player] Playlist media downloaded: v{version}, {len(local_items)} items ready",
                flush=True,
            )
            SCREEN_APP.update_progress(100, detail="Media siap. Memulai pemutaran...")
            time.sleep(0.5)

        current_version = version

        # Check 24-hour playlist operating schedule
        schedule = playlist.get("schedule")
        is_active, sched_msg = is_within_schedule(schedule)
        if not is_active:
            CURRENT_PLAYING["filename"] = None
            CURRENT_PLAYING["media_type"] = None
            stop_playback()
            start_t = schedule.get("start_time", "00:00") if schedule else "00:00"
            end_t = schedule.get("end_time", "23:59") if schedule else "23:59"
            SCREEN_APP.show()
            SCREEN_APP.set_waiting(
                message="Di Luar Jam Tayang",
                detail=f"Jadwal operasional: pk {start_t} - {end_t} (Format 24 Jam)",
            )
            time.sleep(5)
            continue

        # Hide GUI before active VLC playback
        SCREEN_APP.hide()

        # Play items sequentially
        for item in local_items:
            with PLAYLIST_LOCK:
                if LATEST_STATUS == "unpaired":
                    print("[player] Unpaired detected during playback", flush=True)
                    break
                if (
                    LATEST_PLAYLIST
                    and LATEST_PLAYLIST.get("version") != current_version
                ):
                    print("[player] Playlist updated in background, transitioning...", flush=True)
                    break

            # Check schedule before each item (stops promptly when schedule window ends)
            is_active, _ = is_within_schedule(schedule)
            if not is_active:
                print(f"[player] Schedule window ended ({sched_msg}), pausing playback...", flush=True)
                break

            path = item["local_path"]
            duration = item.get("duration", 10)
            media_type = item.get("media_type", "image")
            title = item.get("original_name") or item.get("filename")

            CURRENT_PLAYING["filename"] = title
            CURRENT_PLAYING["title"] = title
            CURRENT_PLAYING["media_type"] = media_type

            print(
                f"[player] Playing: {title} ({media_type}, {duration}s)",
                flush=True,
            )

            try:
                if media_type == "video":
                    play_video(path, duration)
                else:
                    play_image(path, duration)
            except Exception as e:  # noqa: BLE001
                print(
                    f"[player] Playback error on {item['filename']}: {e}",
                    flush=True,
                )
                time.sleep(0.5)


def main() -> None:
    """Initialize player and launch GUI mainloop."""
    device_id = get_device_id()
    print(f"[player] Version: {APP_VERSION}", flush=True)
    print(f"[player] Device ID: {device_id}", flush=True)
    print(f"[player] Server: {SERVER_URL}", flush=True)
    print(f"[player] Media dir: {MEDIA_DIR}", flush=True)

    # Load and apply stored display settings on startup
    init_settings = load_settings()
    apply_all_settings(init_settings)

    # Start Tkinter GUI on main thread, launching orchestrator in background worker
    SCREEN_APP.run(on_ready_callback=lambda: orchestrator_worker(device_id))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop_playback()
        SCREEN_APP.stop()
        print("\n[player] Stopped.", flush=True)
        sys.exit(0)
