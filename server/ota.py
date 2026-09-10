"""OTA (Over-The-Air) update packaging, validation, and manifest manager for RaspiDeck."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import py_compile
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PLAYER_SRC_DIR, UPDATES_DIR
from flask import Response, request

logger = logging.getLogger(__name__)

PACKAGE_FILENAME = "raspideck-player.tar.gz"
MANIFEST_FILENAME = "manifest.json"
VERSION_FILENAME = "VERSION"


def get_source_version() -> str:
    """Read version string from player source directory, fallback to 2.1.0."""
    v_file = PLAYER_SRC_DIR / VERSION_FILENAME
    if v_file.exists():
        try:
            return v_file.read_text().strip()
        except OSError:
            pass
    return "2.1.0"


def sanity_check_player_code() -> tuple[bool, str]:
    """Verify that Python files in player directory compile without syntax errors."""
    if not PLAYER_SRC_DIR.exists():
        return False, f"Player source dir not found: {PLAYER_SRC_DIR}"

    py_files = list(PLAYER_SRC_DIR.glob("*.py")) + list((PLAYER_SRC_DIR / "core").glob("*.py"))
    for py_file in py_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            return False, f"Syntax compilation error in {py_file.name}: {e}"
        except Exception as e:
            return False, f"Unexpected error checking {py_file.name}: {e}"

    return True, "All player Python modules compiled successfully."


def build_player_package(version: str | None = None) -> dict[str, Any]:
    """Package the player codebase into a .tar.gz archive with SHA256 checksum."""
    if not version:
        version = get_source_version()

    # 1. Run syntax sanity check
    ok, msg = sanity_check_player_code()
    if not ok:
        logger.error(f"[OTA] Cannot build player package: {msg}")
        raise ValueError(msg)

    # 2. Prepare target tar.gz path
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = UPDATES_DIR / PACKAGE_FILENAME

    # Exclusions
    exclude_patterns = {
        "__pycache__",
        ".git",
        ".DS_Store",
        "*.pyc",
        "*.pyo",
        "player.log",
        ".update.lock",
        ".staging",
        ".backup",
        "media",
        "playlist_cache.json",
        "settings.json",
    }

    def _filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
        name = os.path.basename(tarinfo.name)
        if name in exclude_patterns or any(p in tarinfo.name.split("/") for p in ("__pycache__", "media")):
            return None
        if name.endswith((".pyc", ".pyo", ".log")):
            return None
        return tarinfo

    # 3. Create compressed tar.gz
    temp_archive = UPDATES_DIR / f"{PACKAGE_FILENAME}.tmp"
    with tarfile.open(temp_archive, "w:gz") as tar:
        # Add all files from PLAYER_SRC_DIR as root contents of the tarball
        for item in PLAYER_SRC_DIR.iterdir():
            if item.name in ("media", "__pycache__", ".git", "player.log"):
                continue
            tar.add(str(item), arcname=item.name, filter=_filter)

    # Atomic rename
    temp_archive.replace(archive_path)

    # 4. Calculate SHA256 checksum
    hasher = hashlib.sha256()
    with open(archive_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    sha256_sum = hasher.hexdigest()
    size_bytes = archive_path.stat().st_size

    manifest = {
        "version": version,
        "release_date": datetime.now(timezone.utc).isoformat(),
        "filename": PACKAGE_FILENAME,
        "sha256": sha256_sum,
        "size_bytes": size_bytes,
        "min_free_space_mb": max(30, int((size_bytes * 5) / (1024 * 1024))),
        "download_url": "/api/player/update/download",
    }

    # Write manifest
    manifest_path = UPDATES_DIR / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(f"[OTA] Built player package v{version} ({size_bytes} bytes, SHA256: {sha256_sum[:8]}...)")
    return manifest


def get_latest_manifest() -> dict[str, Any]:
    """Retrieve current update manifest or build one automatically if missing."""
    manifest_path = UPDATES_DIR / MANIFEST_FILENAME
    archive_path = UPDATES_DIR / PACKAGE_FILENAME

    if manifest_path.exists() and archive_path.exists():
        try:
            return json.loads(manifest_path.read_text())
        except Exception:
            pass

    # Build fresh package if missing
    return build_player_package()


def send_resumable_file(file_path: Path) -> Response:
    """Stream a file supporting HTTP 206 Partial Content (Range requests) for resume capability."""
    if not file_path.exists():
        return Response(json.dumps({"error": "file not found"}), status=404, mimetype="application/json")

    file_size = file_path.stat().st_size
    range_header = request.headers.get("Range")

    if not range_header:
        # Full content response
        def full_stream():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        resp = Response(full_stream(), 200, mimetype="application/gzip")
        resp.headers["Content-Length"] = str(file_size)
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
        return resp

    # Parse Range: bytes=start-end
    match = re.search(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        resp = Response(status=416)
        resp.headers["Content-Range"] = f"bytes */{file_size}"
        return resp

    start_byte = int(match.group(1))
    end_byte = int(match.group(2)) if match.group(2) else file_size - 1

    if start_byte >= file_size or end_byte >= file_size or start_byte > end_byte:
        resp = Response(status=416)
        resp.headers["Content-Range"] = f"bytes */{file_size}"
        return resp

    chunk_length = end_byte - start_byte + 1

    def partial_stream():
        with open(file_path, "rb") as f:
            f.seek(start_byte)
            remaining = chunk_length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    resp = Response(partial_stream(), 206, mimetype="application/gzip")
    resp.headers["Content-Range"] = f"bytes {start_byte}-{end_byte}/{file_size}"
    resp.headers["Content-Length"] = str(chunk_length)
    resp.headers["Accept-Ranges"] = "bytes"
    resp.headers["Content-Disposition"] = f'attachment; filename="{file_path.name}"'
    return resp
