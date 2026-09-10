"""Local media cache and playlist persistence for offline playback resilience."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.config import CACHE_FILE, MEDIA_DIR


def compute_sha256(path: Path) -> str:
    """Compute sha256 checksum in chunks to avoid high RAM usage on 1GB Pi."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def save_cached_playlist(playlist: dict) -> None:
    """Save playlist to local disk cache for offline fallback."""
    try:
        tmp_file = MEDIA_DIR / ".playlist_cache.tmp"
        tmp_file.write_text(json.dumps(playlist, indent=2))
        tmp_file.replace(CACHE_FILE)
    except OSError as e:
        print(f"[player] Warning: could not cache playlist: {e}", flush=True)


def load_cached_playlist() -> dict | None:
    """Load cached playlist if exists and valid."""
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"[player] Warning: could not read cached playlist: {e}", flush=True)
    return None
