"""Configuration, device identification, and path resolution for RaspiDeck Player."""

from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path


def load_server_url() -> str:
    """Resolve server URL from Env, /boot config, or /etc config."""
    env_url = os.environ.get("RASPIDECK_SERVER")
    if env_url:
        return env_url.strip().rstrip("/")

    # Check boot partition files (editable on Windows when SD card is inserted)
    boot_locations = [
        Path("/boot/raspideck.txt"),
        Path("/boot/firmware/raspideck.txt"),
        Path("/etc/raspideck.conf"),
        Path("/opt/raspideck/server.txt"),
    ]
    for loc in boot_locations:
        try:
            if loc.exists():
                for line in loc.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip().upper() in (
                            "SERVER_URL",
                            "SERVER",
                            "RASPIDECK_SERVER",
                        ):
                            return v.strip().strip("'\"").rstrip("/")
                    elif line.startswith(("http://", "https://")):
                        return line.rstrip("/")
        except OSError:
            pass

    return "http://localhost:8000"


_CACHED_DEVICE_ID: str = os.environ.get("RASPIDECK_DEVICE_ID", "")


def get_device_id() -> str:
    """Return stable device ID from Pi serial or fallback to MAC/hostname hash."""
    global _CACHED_DEVICE_ID
    if _CACHED_DEVICE_ID:
        return _CACHED_DEVICE_ID

    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("Serial"):
                    _CACHED_DEVICE_ID = line.strip().split(":")[-1].strip()
                    return _CACHED_DEVICE_ID
    except OSError:
        pass

    import uuid as uuid_mod

    raw = f"{platform.node()}-{uuid_mod.getnode()}"
    _CACHED_DEVICE_ID = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return _CACHED_DEVICE_ID


SERVER_URL = load_server_url()
DEVICE_ID = get_device_id()
MEDIA_DIR = Path(os.environ.get("RASPIDECK_MEDIA_DIR", "/opt/raspideck/media"))
CACHE_FILE = MEDIA_DIR / "playlist_cache.json"

# Resolve Player Base & Data Directory
_ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = _ROOT_DIR / "VERSION"


def get_app_version() -> str:
    """Read version string from local VERSION file."""
    if VERSION_FILE.exists():
        try:
            return VERSION_FILE.read_text().strip()
        except OSError:
            pass
    return "2.1.0"


APP_VERSION = get_app_version()

DATA_DIR = Path(os.environ.get("RASPIDECK_DATA_DIR", "/opt/raspideck"))
SETTINGS_FILE = DATA_DIR / "settings.json"
DEVICE_TOKEN_FILE = DATA_DIR / "device_token.txt"


def load_device_token() -> str | None:
    """Load cached device authentication token if present."""
    if DEVICE_TOKEN_FILE.exists():
        try:
            tok = DEVICE_TOKEN_FILE.read_text().strip()
            if tok:
                return tok
        except OSError:
            pass
    return None


def save_device_token(token: str) -> None:
    """Safely persist device authentication token."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = DEVICE_TOKEN_FILE.with_suffix(".tmp")
        tmp.write_text(token.strip())
        tmp.replace(DEVICE_TOKEN_FILE)
    except OSError as e:
        print(f"[config] Failed to save device token: {e}", flush=True)


try:
    POLL_INTERVAL = int(os.environ.get("RASPIDECK_POLL_INTERVAL", "30"))
except (TypeError, ValueError):
    POLL_INTERVAL = 30

HEARTBEAT_INTERVAL = 10  # Seconds between background telemetry updates

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
