"""Configuration settings and paths for RaspiDeck Server."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", BASE_DIR / "media"))
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "deck.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD env var required for production")
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    import secrets

    SECRET_KEY = secrets.token_urlsafe(32)  # generate random secret if not set

MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", "100")) * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "mp4",
    "mkv",
    "avi",
    "mov",
    "webm",
}

VIDEO_EXTENSIONS = {"mp4", "mkv", "avi", "mov", "webm"}

SPLASH_PATH = BASE_DIR.parent / "player" / "splash.png"

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAILS_DIR = Path(os.environ.get("THUMBNAILS_DIR", MEDIA_DIR / "thumbnails"))
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

UPDATES_DIR = Path(os.environ.get("UPDATES_DIR", BASE_DIR / "updates"))
UPDATES_DIR.mkdir(parents=True, exist_ok=True)
PLAYER_SRC_DIR = BASE_DIR.parent / "player"
