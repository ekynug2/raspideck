"""Configuration settings and paths for RaspiDeck Server."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Auto-load .env from project root if present and not already set in environment
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    try:
        with open(env_file, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k = _k.strip()
                    _v = _v.strip().strip("\"'")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

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


def parse_cors_origins() -> list[str]:
    """Parse CORS allowed origins from environment variable (JSON array or comma-separated)."""
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        return [
            "http://localhost:*",
            "http://127.0.0.1:*",
            r"http://192\.168\..*",
        ]
    origins: list[str] = []
    if raw.startswith("[") and raw.endswith("]"):
        try:
            import json

            parsed = json.loads(raw)
            if isinstance(parsed, list):
                origins = [str(item).strip().strip("\"'") for item in parsed if str(item).strip()]
        except Exception:
            pass
    if not origins:
        origins = [item.strip().strip("\"'") for item in raw.split(",") if item.strip()]

    import re

    validated: list[str] = []
    for o in origins:
        try:
            re.compile(o)
            validated.append(o)
        except re.error:
            validated.append(re.escape(o))

    return validated or [
        "http://localhost:*",
        "http://127.0.0.1:*",
        r"http://192\.168\..*",
    ]


CORS_ORIGINS = parse_cors_origins()

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
