"""System telemetry and hardware metric collection for Raspberry Pi."""

from __future__ import annotations

import platform
import shutil
import socket
from pathlib import Path
from typing import Any

from core.config import APP_VERSION, MEDIA_DIR
from core.settings import compute_settings_hash, load_settings


def get_system_info(current_playing: dict[str, str | None] | None = None) -> dict[str, Any]:
    """Collect comprehensive, accurate hardware, system, and playback metrics."""
    cur_settings = load_settings()
    info: dict[str, Any] = {
        "hostname": platform.node(),
        "platform": platform.machine(),
        "app_version": APP_VERSION,
        "settings_hash": compute_settings_hash(cur_settings),
        "settings": cur_settings,
    }

    # 1. Hardware Model (e.g., Raspberry Pi 3 Model B Rev 1.2)
    try:
        model_path = Path("/proc/device-tree/model")
        if model_path.exists():
            info["model"] = model_path.read_text().strip("\x00").strip()
    except OSError:
        pass
    if "model" not in info:
        info["model"] = f"{platform.system()} {platform.machine()}"

    # 2. CPU Temperature (Celsius)
    try:
        temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
        if temp_path.exists():
            info["temp"] = round(int(temp_path.read_text().strip()) / 1000.0, 1)
    except (OSError, ValueError):
        pass

    # 3. System Uptime (seconds)
    try:
        uptime_path = Path("/proc/uptime")
        if uptime_path.exists():
            info["uptime"] = int(float(uptime_path.read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        pass

    # 4. RAM Usage (MemTotal, MemAvailable)
    try:
        total_kb, avail_kb = 0, 0
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail_kb = int(line.split()[1])
        if total_kb > 0:
            used_kb = total_kb - avail_kb
            info["mem"] = {
                "total_mb": round(total_kb / 1024),
                "used_mb": round(used_kb / 1024),
                "percent": round((used_kb / total_kb) * 100, 1),
            }
            info["mem_total_kb"] = total_kb
    except (OSError, ValueError, IndexError):
        pass

    # 5. Disk Storage Usage on /opt/raspideck
    try:
        total_b, used_b, _ = shutil.disk_usage(MEDIA_DIR)
        info["disk"] = {
            "total_gb": round(total_b / (1024**3), 1),
            "used_gb": round(used_b / (1024**3), 1),
            "percent": round((used_b / total_b) * 100, 1),
        }
    except OSError:
        pass

    # 6. Display & HDMI Status
    try:
        hdmi_status = "disconnected"
        resolution = "unknown"
        # Check DRM HDMI connections
        for drm_path in Path("/sys/class/drm").glob("card*-HDMI-A-*"):
            status_file = drm_path / "status"
            if status_file.exists() and status_file.read_text().strip() == "connected":
                hdmi_status = "connected"
                modes_file = drm_path / "modes"
                if modes_file.exists():
                    modes = modes_file.read_text().strip().splitlines()
                    if modes:
                        resolution = modes[0].strip()
                break

        # Check framebuffer virtual size (actual active resolution e.g. 1920x1080, 1280x720)
        fb_path = Path("/sys/class/graphics/fb0/virtual_size")
        if fb_path.exists():
            fb_res = fb_path.read_text().strip().replace(",", "x")
            if fb_res and "x" in fb_res:
                resolution = fb_res

        info["display"] = {
            "hdmi": hdmi_status,
            "resolution": resolution,
        }
    except Exception:
        pass

    # 7. Local IP Address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        info["local_ip"] = s.getsockname()[0]
        s.close()
    except OSError:
        pass

    # 8. Currently Playing Media
    if current_playing and current_playing.get("filename"):
        info["playing"] = current_playing["filename"]
        info["title"] = current_playing.get("title") or current_playing["filename"]
        info["media_type"] = current_playing.get("media_type")

    return info
