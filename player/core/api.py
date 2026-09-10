"""HTTP network communication and media download manager for player."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from core.cache import compute_sha256
from core.config import APP_VERSION, MEDIA_DIR, SERVER_URL, load_device_token, save_device_token


def api_post(path: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """POST JSON data to the RaspiDeck server and return parsed response."""
    url = f"{SERVER_URL}{path}"
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        print(f"[player] Refusing invalid URL scheme: {url}", flush=True)
        return None

    payload = json.dumps(data).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"RaspiDeck-Player/{APP_VERSION}",
        "Accept": "application/json",
    }
    token = load_device_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            res_data = json.loads(resp.read().decode())
            if isinstance(res_data, dict) and res_data.get("device_token"):
                save_device_token(res_data["device_token"])
            return res_data
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"[player] API error on {path}: {e}", flush=True)
        return None


def download_media(
    item: dict[str, Any],
    progress_callback: Any = None,
) -> Path | None:
    """Download media file if not present or hash mismatch."""
    local_path = MEDIA_DIR / item["filename"]
    if local_path.exists():
        existing_hash = compute_sha256(local_path)
        if existing_hash == item.get("sha256"):
            if progress_callback:
                progress_callback(100, 100)
            return local_path

    url = f"{SERVER_URL}{item['url']}"
    if not url.startswith(("http://", "https://")):
        print(f"[player] Refusing non-HTTP URL: {url}", flush=True)
        return None

    print(f"[player] Downloading {item['filename']}...", flush=True)
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "RaspiDeck-Player/1.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp, open(
            local_path, "wb"
        ) as out:
            total_bytes = 0
            try:
                cl = resp.headers.get("Content-Length")
                if cl:
                    total_bytes = int(cl)
            except (ValueError, TypeError):
                total_bytes = 0

            downloaded_bytes = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                downloaded_bytes += len(chunk)
                if progress_callback and total_bytes > 0:
                    progress_callback(downloaded_bytes, total_bytes)

        downloaded_hash = compute_sha256(local_path)
        if item.get("sha256") and downloaded_hash != item["sha256"]:
            print(
                f"[player] SHA256 mismatch for {item['filename']}, removing",
                flush=True,
            )
            local_path.unlink(missing_ok=True)
            return None
        if progress_callback:
            progress_callback(100, 100)
    except (urllib.error.URLError, OSError) as e:
        print(f"[player] Download failed for {item['filename']}: {e}", flush=True)
        return None

    return local_path
