"""RaspiDeck Player core module."""

from __future__ import annotations

from core.api import api_post, download_media
from core.cache import compute_sha256, load_cached_playlist, save_cached_playlist
from core.config import (
    CACHE_FILE,
    DEVICE_ID,
    HEARTBEAT_INTERVAL,
    MEDIA_DIR,
    POLL_INTERVAL,
    SERVER_URL,
    get_device_id,
    load_server_url,
)
from core.playback import (
    play_image,
    play_video,
    show_pairing_screen,
    show_waiting_screen,
    stop_playback,
)
from core.screens import generate_pairing_image, generate_waiting_image
from core.telemetry import get_system_info

__all__ = [
    "CACHE_FILE",
    "DEVICE_ID",
    "HEARTBEAT_INTERVAL",
    "MEDIA_DIR",
    "POLL_INTERVAL",
    "SERVER_URL",
    "api_post",
    "compute_sha256",
    "download_media",
    "generate_pairing_image",
    "generate_waiting_image",
    "get_device_id",
    "get_system_info",
    "load_cached_playlist",
    "load_server_url",
    "play_image",
    "play_video",
    "save_cached_playlist",
    "show_pairing_screen",
    "show_waiting_screen",
    "stop_playback",
]
