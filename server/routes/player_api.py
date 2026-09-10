"""Player API endpoints (heartbeat, registration, playlist sync, settings sync, OTA updates, and media serving)."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from config import MEDIA_DIR, THUMBNAILS_DIR, UPDATES_DIR
from db import get_db
from flask import Blueprint, jsonify, request, send_from_directory
from ota import PACKAGE_FILENAME, get_latest_manifest, send_resumable_file
from utils import generate_video_thumbnail
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

player_api_bp = Blueprint("player_api", __name__)

DEFAULT_SETTINGS = {
    "volume": 100,
    "rotation": "normal",
    "heartbeat_interval": 10,
    "screen_power": "on",
}


def _extract_bearer_token() -> str | None:
    """Extract Bearer token from HTTP Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None


@player_api_bp.route("/api/player/heartbeat", methods=["POST"])
def player_heartbeat():
    """Handle Raspberry Pi device heartbeat, status updates, settings sync, and OTA updates."""
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"error": "missing device_id"}), 400

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    ip_addr = request.headers.get("X-Forwarded-For", request.remote_addr)
    sys_info_obj = data.get("system_info", {})
    sys_info = json.dumps(sys_info_obj)

    # Client-reported telemetry & app version
    app_version = data.get("app_version") or sys_info_obj.get("app_version", "2.0")
    update_status = data.get("update_status") or "idle"

    bearer_token = _extract_bearer_token() or data.get("device_token")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM screens WHERE id = ?", (device_id,)
        ).fetchone()

        if not row:
            # Unregistered device: generate pairing code & device token
            pairing_code = (
                hashlib.sha256(f"{device_id}-{now_iso}".encode())
                .hexdigest()[:6]
                .upper()
            )
            device_token = secrets.token_hex(32)
            conn.execute(
                "INSERT INTO screens (id, name, pairing_code, is_paired, last_seen, ip_address, system_info, "
                "settings, app_version, update_status, device_token) "
                "VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)",
                (
                    device_id,
                    f"Screen-{(device_id.lstrip('0') or device_id)[-6:].upper()}",
                    pairing_code,
                    now_iso,
                    ip_addr,
                    sys_info,
                    json.dumps(DEFAULT_SETTINGS),
                    app_version,
                    update_status,
                    device_token,
                ),
            )
            return jsonify(
                {
                    "status": "unpaired",
                    "pairing_code": pairing_code,
                    "device_token": device_token,
                    "message": "Screen unregistered. Pair from web dashboard.",
                }
            )

        # Authenticate if device token is set on paired screen
        stored_token = row["device_token"] if "device_token" in row.keys() else None
        if not stored_token:
            # Provision token if missing on existing screen
            stored_token = secrets.token_hex(32)
            conn.execute("UPDATE screens SET device_token = ? WHERE id = ?", (stored_token, device_id))
        elif row["is_paired"] and bearer_token and bearer_token != stored_token:
            logger.warning(f"[auth] Unauthorized heartbeat for screen {device_id} (token mismatch)")
            return jsonify({"error": "unauthorized device token"}), 401

        # Check update lock timeout (15 minutes threshold)
        lock_time = row["update_lock_acquired_at"] if "update_lock_acquired_at" in row.keys() else None
        if lock_time:
            try:
                dt = datetime.fromisoformat(lock_time.replace("Z", "+00:00"))
                elapsed = (now_dt - dt).total_seconds()
                if elapsed > 900 and row["update_status"] not in ("idle", "success", "failed"):
                    logger.warning(f"[OTA] Update lock timed out for {device_id} after {elapsed:.0f}s")
                    conn.execute(
                        "UPDATE screens SET update_lock_acquired_at = NULL, update_status = 'failed: timeout' WHERE id = ?",
                        (device_id,),
                    )
                    update_status = "failed: timeout"
            except Exception:
                pass

        # Handle pending command (restart, reboot, etc.)
        cmd = row["pending_command"] if "pending_command" in row.keys() else None
        if cmd:
            conn.execute("UPDATE screens SET pending_command = NULL WHERE id = ?", (device_id,))

        # Update telemetry, IP, last seen, app version, and status
        conn.execute(
            "UPDATE screens SET last_seen = ?, ip_address = ?, system_info = ?, app_version = ?, update_status = ? WHERE id = ?",
            (now_iso, ip_addr, sys_info, app_version, update_status, device_id),
        )

        # Resolve screen-specific settings
        raw_settings = row["settings"] if "settings" in row.keys() else "{}"
        try:
            device_settings = {**DEFAULT_SETTINGS, **json.loads(raw_settings or "{}")}
        except Exception:
            device_settings = DEFAULT_SETTINGS

        # Base response payload
        resp: dict[str, Any] = {
            "status": "paired" if row["is_paired"] else "unpaired",
            "device_token": stored_token,
            "settings": device_settings,
        }

        if cmd:
            resp["command"] = cmd

        # Check for pending OTA updates
        pending_upd = row["pending_update"] if "pending_update" in row.keys() else None
        if pending_upd:
            try:
                manifest = get_latest_manifest()
                resp["update"] = {
                    "version": manifest["version"],
                    "url": manifest["download_url"],
                    "sha256": manifest["sha256"],
                    "size_bytes": manifest["size_bytes"],
                    "min_free_space_mb": manifest["min_free_space_mb"],
                }
                # Acquire lock and set status
                conn.execute(
                    "UPDATE screens SET pending_update = NULL, update_lock_acquired_at = ?, update_status = 'downloading' WHERE id = ?",
                    (now_iso, device_id),
                )
            except Exception as e:
                logger.error(f"[OTA] Failed to prepare update for {device_id}: {e}")

        # If not paired, return pairing code
        if not row["is_paired"]:
            resp["pairing_code"] = row["pairing_code"]
            resp["message"] = "Screen waiting for pairing approval."
            return jsonify(resp)

        # If paired, resolve playlist
        playlist_id = row["playlist_id"]
        if not playlist_id:
            resp["playlist"] = None
            resp["message"] = "No playlist assigned."
            return jsonify(resp)

        pl_row = conn.execute(
            "SELECT * FROM playlists WHERE id = ?", (playlist_id,)
        ).fetchone()
        if not pl_row:
            resp["playlist"] = None
            return jsonify(resp)

        try:
            items = json.loads(pl_row["items_json"])
        except (json.JSONDecodeError, TypeError):
            items = []

        # Resolve media urls
        resolved = []
        for it in items:
            m_row = conn.execute(
                "SELECT * FROM media WHERE id = ?", (it["media_id"],)
            ).fetchone()
            if m_row:
                resolved.append(
                    {
                        "id": m_row["id"],
                        "filename": m_row["filename"],
                        "original_name": m_row["original_name"],
                        "media_type": m_row["media_type"],
                        "duration": it.get("duration", 10),
                        "sha256": m_row["sha256"],
                        "url": f"/media/{m_row['filename']}",
                    }
                )

        # Build schedule config
        pl_keys = pl_row.keys()
        sched_enabled = bool(pl_row["schedule_enabled"]) if "schedule_enabled" in pl_keys else False
        sched_start = (pl_row["start_time"] if "start_time" in pl_keys and pl_row["start_time"] else "00:00")[:5]
        sched_end = (pl_row["end_time"] if "end_time" in pl_keys and pl_row["end_time"] else "23:59")[:5]
        sched_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        if "schedule_days" in pl_keys and pl_row["schedule_days"]:
            try:
                sched_days = json.loads(pl_row["schedule_days"])
            except Exception:
                pass

        resp["playlist"] = {
            "id": pl_row["id"],
            "name": pl_row["name"],
            "version": pl_row["version"],
            "schedule": {
                "enabled": sched_enabled,
                "start_time": sched_start,
                "end_time": sched_end,
                "days": sched_days,
            },
            "items": resolved,
        }
        return jsonify(resp)


# --- OTA UPDATE ENDPOINTS ---


@player_api_bp.route("/api/player/update/manifest", methods=["GET"])
def player_update_manifest():
    """Return the current player release manifest with SHA256 checksum."""
    try:
        manifest = get_latest_manifest()
        return jsonify(manifest)
    except Exception as e:
        return jsonify({"error": f"Failed to get update manifest: {e}"}), 500


@player_api_bp.route("/api/player/update/download", methods=["GET"])
def player_update_download():
    """Stream player tarball with HTTP Range support for resumable downloads."""
    tar_path = UPDATES_DIR / PACKAGE_FILENAME
    if not tar_path.exists():
        try:
            get_latest_manifest()  # Triggers auto-build if missing
        except Exception as e:
            return jsonify({"error": f"Update package not built: {e}"}), 404

    return send_resumable_file(tar_path)


@player_api_bp.route("/api/player/update/status", methods=["POST"])
def player_update_status():
    """Receive real-time progress reports from player during OTA update process."""
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id")
    status = data.get("status", "idle")
    version = data.get("version")
    detail = data.get("detail", "")

    if not device_id:
        return jsonify({"error": "missing device_id"}), 400

    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        row = conn.execute("SELECT * FROM screens WHERE id = ?", (device_id,)).fetchone()
        if not row:
            return jsonify({"error": "screen not found"}), 404

        # Validate token
        bearer_token = _extract_bearer_token() or data.get("device_token")
        if row["device_token"] and bearer_token and bearer_token != row["device_token"]:
            return jsonify({"error": "unauthorized"}), 401

        is_terminal = status.startswith("success") or status.startswith("failed") or status.startswith("rolled_back")

        # Update last_update_log if terminal
        if is_terminal:
            try:
                logs = json.loads(row["last_update_log"] or "[]")
            except Exception:
                logs = []

            logs.insert(0, {
                "timestamp": now_iso,
                "version": version or row["app_version"],
                "status": status,
                "detail": detail,
            })
            logs = logs[:10]  # Keep last 10 entries
            logs_json = json.dumps(logs)

            new_version = version if status == "success" and version else row["app_version"]
            conn.execute(
                "UPDATE screens SET update_status = ?, update_lock_acquired_at = NULL, app_version = ?, last_update_log = ? WHERE id = ?",
                (status, new_version, logs_json, device_id),
            )
        else:
            conn.execute(
                "UPDATE screens SET update_status = ? WHERE id = ?",
                (status, device_id),
            )

    return jsonify({"success": True})


# --- MEDIA SERVING ---


@player_api_bp.route("/media/<filename>")
def serve_media(filename: str):
    """Serve uploaded media file to player or web dashboard."""
    return send_from_directory(MEDIA_DIR, secure_filename(filename))


@player_api_bp.route("/media/thumbnails/<filename>")
def serve_thumbnail(filename: str):
    """Serve cached video/image thumbnail snapshot with aggressive caching."""
    safe_name = secure_filename(filename)
    thumb_path = THUMBNAILS_DIR / safe_name

    # If thumbnail doesn't exist yet on disk, generate it on demand
    if not thumb_path.exists():
        media_id = safe_name.rsplit(".", 1)[0]
        for ext in ("mp4", "mkv", "avi", "mov", "webm"):
            video_candidate = MEDIA_DIR / f"{media_id}.{ext}"
            if video_candidate.exists():
                generate_video_thumbnail(video_candidate, thumb_path)
                break

    if thumb_path.exists():
        response = send_from_directory(THUMBNAILS_DIR, safe_name)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    return jsonify({"error": "thumbnail not found"}), 404
