"""Admin REST API endpoints for managing screens, media assets, and playlists."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from auth import require_auth
from config import MEDIA_DIR
from db import get_db
from flask import Blueprint, jsonify, request
from ota import build_player_package, get_latest_manifest
from utils import allowed_file, delete_thumbnail, generate_video_thumbnail, get_thumbnail_path, is_video
from werkzeug.utils import secure_filename

admin_api_bp = Blueprint("admin_api", __name__)


# --- SCREENS MANAGEMENT ---


@admin_api_bp.route("/api/screens", methods=["GET"])
def list_screens():
    """List all registered screens ordered by last seen."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    with get_db() as conn:
        screens = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM screens ORDER BY last_seen DESC"
            ).fetchall()
        ]
    return jsonify(screens)


@admin_api_bp.route("/api/screens/<screen_id>/pair", methods=["POST"])
def pair_screen(screen_id: str):
    """Approve screen pairing and optionally assign a custom name."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    with get_db() as conn:
        if name:
            conn.execute(
                "UPDATE screens SET is_paired = 1, pairing_code = NULL, name = ? WHERE id = ?",
                (name, screen_id),
            )
        else:
            conn.execute(
                "UPDATE screens SET is_paired = 1, pairing_code = NULL WHERE id = ?",
                (screen_id,),
            )
    return jsonify({"success": True})


@admin_api_bp.route("/api/screens/<screen_id>/unpair", methods=["POST"])
def unpair_screen(screen_id: str):
    """Unpair screen and generate a new pairing code so player shows pairing screen."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    with get_db() as conn:
        row = conn.execute("SELECT id FROM screens WHERE id = ?", (screen_id,)).fetchone()
        if not row:
            return jsonify({"error": "screen not found"}), 404
        now_iso = datetime.now(timezone.utc).isoformat()
        new_code = hashlib.sha256(f"{screen_id}-{now_iso}".encode()).hexdigest()[:6].upper()
        conn.execute(
            "UPDATE screens SET is_paired = 0, pairing_code = ?, playlist_id = NULL WHERE id = ?",
            (new_code, screen_id),
        )
    return jsonify({"success": True, "pairing_code": new_code})


@admin_api_bp.route("/api/screens/<screen_id>/ping", methods=["POST"])
def ping_screen(screen_id: str):
    """Check connectivity and telemetry recency of the screen terminal."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    with get_db() as conn:
        row = conn.execute("SELECT * FROM screens WHERE id = ?", (screen_id,)).fetchone()
        if not row:
            return jsonify({"error": "screen not found"}), 404
        ip = row["ip_address"]
        last_seen = row["last_seen"]
        diff_sec = None
        if last_seen:
            try:
                dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                diff_sec = (datetime.now(timezone.utc) - dt).total_seconds()
            except Exception:
                pass

        is_online = bool(diff_sec is not None and diff_sec < 45)
        latency_ms = None
        if ip and ip not in ("127.0.0.1", "localhost"):
            import socket, time
            start = time.time()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect_ex((ip, 22))
                sock.close()
                latency_ms = round((time.time() - start) * 1000, 1)
            except Exception:
                pass

        return jsonify(
            {
                "success": True,
                "screen_id": screen_id,
                "ip": ip or "127.0.0.1",
                "is_online": is_online,
                "last_seen_seconds": round(diff_sec, 1) if diff_sec is not None else None,
                "latency_ms": latency_ms,
            }
        )


@admin_api_bp.route("/api/screens/<screen_id>/restart", methods=["POST"])
def restart_screen(screen_id: str):
    """Queue a restart command for the client player terminal."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    with get_db() as conn:
        row = conn.execute("SELECT id, name FROM screens WHERE id = ?", (screen_id,)).fetchone()
        if not row:
            return jsonify({"error": "screen not found"}), 404
        conn.execute(
            "UPDATE screens SET pending_command = 'restart' WHERE id = ?",
            (screen_id,),
        )
    return jsonify({
        "success": True,
        "message": f"Perintah restart berhasil dikirim ke {row['name'] or screen_id}. Player akan memulai ulang sesaat lagi."
    })


@admin_api_bp.route("/api/screens/<screen_id>/command", methods=["POST"])
def send_screen_command(screen_id: str):
    """Queue a control command (restart or reboot) for the client player terminal."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    cmd = data.get("command", "restart").strip().lower()
    if cmd not in ("restart", "reboot"):
        return jsonify({"error": "Perintah tidak valid. Gunakan 'restart' atau 'reboot'."}), 400
    with get_db() as conn:
        row = conn.execute("SELECT id, name FROM screens WHERE id = ?", (screen_id,)).fetchone()
        if not row:
            return jsonify({"error": "screen not found"}), 404
        conn.execute(
            "UPDATE screens SET pending_command = ? WHERE id = ?",
            (cmd, screen_id),
        )
    label = "Restart Aplikasi" if cmd == "restart" else "Reboot Sistem"
    return jsonify({
        "success": True,
        "message": f"Perintah {label} berhasil dikirim ke {row['name'] or screen_id}."
    })


@admin_api_bp.route("/api/screens/<screen_id>", methods=["PATCH", "DELETE"])
def manage_screen(screen_id: str):
    """Update screen metadata (name, playlist assignment) or delete screen."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    with get_db() as conn:
        if request.method == "DELETE":
            conn.execute("DELETE FROM screens WHERE id = ?", (screen_id,))
            return jsonify({"success": True})
        data = request.get_json(silent=True) or {}
        if "name" in data:
            conn.execute(
                "UPDATE screens SET name = ? WHERE id = ?", (data["name"], screen_id)
            )
        if "playlist_id" in data:
            conn.execute(
                "UPDATE screens SET playlist_id = ? WHERE id = ?",
                (data["playlist_id"], screen_id),
            )
    return jsonify({"success": True})


@admin_api_bp.route("/api/screens/<screen_id>/settings", methods=["GET", "PATCH"])
def screen_settings(screen_id: str):
    """Retrieve or update individual display configuration for a screen."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401

    default_settings = {
        "volume": 100,
        "rotation": "normal",
        "heartbeat_interval": 10,
        "screen_power": "on",
    }

    with get_db() as conn:
        row = conn.execute("SELECT id, name, settings FROM screens WHERE id = ?", (screen_id,)).fetchone()
        if not row:
            return jsonify({"error": "screen not found"}), 404

        cur_settings = dict(default_settings)
        try:
            if row["settings"]:
                cur_settings.update(json.loads(row["settings"]))
        except Exception:
            pass

        if request.method == "GET":
            return jsonify({"success": True, "settings": cur_settings})

        # PATCH
        data = request.get_json(silent=True) or {}
        if "volume" in data:
            try:
                cur_settings["volume"] = max(0, min(100, int(data["volume"])))
            except (ValueError, TypeError):
                pass
        if "rotation" in data:
            rot = str(data["rotation"]).strip().lower()
            if rot in ("normal", "right", "inverted", "left"):
                cur_settings["rotation"] = rot
        if "heartbeat_interval" in data:
            try:
                cur_settings["heartbeat_interval"] = max(5, min(120, int(data["heartbeat_interval"])))
            except (ValueError, TypeError):
                pass
        if "screen_power" in data:
            pwr = str(data["screen_power"]).strip().lower()
            if pwr in ("on", "off"):
                cur_settings["screen_power"] = pwr

        conn.execute("UPDATE screens SET settings = ? WHERE id = ?", (json.dumps(cur_settings), screen_id))
        return jsonify({"success": True, "settings": cur_settings, "message": "Pengaturan display berhasil disimpan."})


@admin_api_bp.route("/api/screens/<screen_id>/update", methods=["POST"])
def update_screen_code(screen_id: str):
    """Queue an OTA software code update for a specific client player."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401

    with get_db() as conn:
        row = conn.execute("SELECT * FROM screens WHERE id = ?", (screen_id,)).fetchone()
        if not row:
            return jsonify({"error": "screen not found"}), 404

        # Check update lock
        lock_at = row["update_lock_acquired_at"] if "update_lock_acquired_at" in row.keys() else None
        if lock_at:
            try:
                dt = datetime.fromisoformat(lock_at.replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                if elapsed < 900 and row["update_status"] in ("downloading", "applying", "restarting", "verifying"):
                    return jsonify({
                        "error": "Proses update sedang berjalan pada layar ini. Harap tunggu hingga selesai atau timeout."
                    }), 409
            except Exception:
                pass

        try:
            manifest = get_latest_manifest()
        except Exception as e:
            return jsonify({"error": f"Gagal membaca paket pembaruan server: {e}"}), 500

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            logs = json.loads(row["last_update_log"] or "[]")
        except Exception:
            logs = []

        logs.insert(0, {
            "timestamp": now_iso,
            "admin_user": "admin",
            "action": "trigger_ota",
            "from_version": row["app_version"] or "2.0",
            "target_version": manifest["version"],
            "status": "pending",
            "detail": "Pembaruan dijadwalkan oleh admin",
        })
        logs_json = json.dumps(logs[:10])

        pending_json = json.dumps({
            "version": manifest["version"],
            "timestamp": now_iso,
        })

        conn.execute(
            "UPDATE screens SET pending_update = ?, update_status = 'pending', last_update_log = ? WHERE id = ?",
            (pending_json, logs_json, screen_id),
        )

    return jsonify({
        "success": True,
        "message": f"Pembaruan software ke versi {manifest['version']} telah dijadwalkan untuk {row['name'] or screen_id}."
    })


@admin_api_bp.route("/api/screens/update-all", methods=["POST"])
def update_all_screens():
    """Trigger OTA code update for all paired screens running an outdated version."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401

    try:
        manifest = get_latest_manifest()
    except Exception as e:
        return jsonify({"error": f"Gagal membaca paket pembaruan server: {e}"}), 500

    target_version = manifest["version"]
    now_iso = datetime.now(timezone.utc).isoformat()
    queued_count = 0

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, app_version, update_status, update_lock_acquired_at, last_update_log FROM screens WHERE is_paired = 1"
        ).fetchall()

        for r in rows:
            if r["app_version"] == target_version and r["update_status"] == "success":
                continue

            # Check lock
            lock_at = r["update_lock_acquired_at"] if "update_lock_acquired_at" in r.keys() else None
            if lock_at:
                try:
                    dt = datetime.fromisoformat(lock_at.replace("Z", "+00:00"))
                    elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                    if elapsed < 900 and r["update_status"] in ("downloading", "applying", "restarting", "verifying"):
                        continue
                except Exception:
                    pass

            try:
                logs = json.loads(r["last_update_log"] or "[]")
            except Exception:
                logs = []

            logs.insert(0, {
                "timestamp": now_iso,
                "admin_user": "admin",
                "action": "trigger_ota_batch",
                "from_version": r["app_version"] or "2.0",
                "target_version": target_version,
                "status": "pending",
                "detail": "Pembaruan massal dijadwalkan oleh admin",
            })
            logs_json = json.dumps(logs[:10])

            conn.execute(
                "UPDATE screens SET pending_update = ?, update_status = 'pending', last_update_log = ? WHERE id = ?",
                (json.dumps({"version": target_version, "timestamp": now_iso}), logs_json, r["id"]),
            )
            queued_count += 1

    return jsonify({
        "success": True,
        "queued_count": queued_count,
        "target_version": target_version,
        "message": f"Pembaruan ke versi {target_version} telah dijadwalkan untuk {queued_count} layar."
    })


@admin_api_bp.route("/api/system/player-version", methods=["GET"])
def system_player_version():
    """Get latest player software release version and package details."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    try:
        manifest = get_latest_manifest()
        return jsonify({"success": True, "manifest": manifest})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_api_bp.route("/api/system/player-package/build", methods=["POST"])
def build_player_release():
    """Manually trigger compilation sanity check and repackage player bundle."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    custom_ver = data.get("version")
    try:
        manifest = build_player_package(version=custom_ver)
        return jsonify({
            "success": True,
            "manifest": manifest,
            "message": f"Paket rilis player v{manifest['version']} berhasil dibangun."
        })
    except Exception as e:
        return jsonify({"error": f"Gagal membuat paket rilis: {e}"}), 400



# --- MEDIA MANAGEMENT ---


@admin_api_bp.route("/api/media", methods=["GET", "POST"])
def manage_media():
    """Upload media file (POST) or list existing media (GET)."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401

    if request.method == "POST":
        if "file" not in request.files:
            return jsonify({"error": "no file uploaded"}), 400
        file = request.files["file"]
        if not file.filename or not allowed_file(file.filename):
            return jsonify({"error": "invalid file format"}), 400

        orig_name = secure_filename(file.filename)
        media_id = str(uuid.uuid4())
        ext = orig_name.rsplit(".", 1)[1].lower()
        storage_filename = f"{media_id}.{ext}"
        target_path = MEDIA_DIR / storage_filename

        try:
            sha256_hash = hashlib.sha256()
            size = 0
            with open(target_path, "wb") as f:
                while True:
                    chunk = file.stream.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha256_hash.update(chunk)
                    size += len(chunk)
            sha256 = sha256_hash.hexdigest()
        except OSError as e:
            if target_path.exists():
                target_path.unlink()
            return jsonify({"error": f"Failed to save file: {e}"}), 500

        media_type = "video" if is_video(orig_name) else "image"
        now_iso = datetime.now(timezone.utc).isoformat()

        # If video, generate static snapshot thumbnail immediately
        if media_type == "video":
            thumb_path = get_thumbnail_path(media_id)
            generate_video_thumbnail(target_path, thumb_path)

        with get_db() as conn:
            conn.execute(
                "INSERT INTO media (id, filename, original_name, media_type, size, sha256, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    media_id,
                    storage_filename,
                    orig_name,
                    media_type,
                    size,
                    sha256,
                    now_iso,
                ),
            )

        return jsonify({"success": True, "id": media_id, "filename": storage_filename})

    with get_db() as conn:
        media_list = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM media ORDER BY created_at DESC"
            ).fetchall()
        ]
        # Append persistent thumbnail URL for each asset
        for m in media_list:
            if m.get("media_type") == "video":
                m["thumbnail_url"] = f"/media/thumbnails/{m['id']}.jpg"
            else:
                m["thumbnail_url"] = f"/media/{m['filename']}"
    return jsonify(media_list)


@admin_api_bp.route("/api/media/<media_id>", methods=["DELETE"])
def delete_media(media_id: str):
    """Delete a media asset and remove file and thumbnail from disk."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401
    with get_db() as conn:
        row = conn.execute(
            "SELECT filename FROM media WHERE id = ?", (media_id,)
        ).fetchone()
        if row:
            file_path = MEDIA_DIR / row["filename"]
            if file_path.exists():
                file_path.unlink()
            # Also delete cached thumbnail snapshot from disk
            delete_thumbnail(media_id)
            conn.execute("DELETE FROM media WHERE id = ?", (media_id,))
    return jsonify({"success": True})


# --- PLAYLIST MANAGEMENT ---


@admin_api_bp.route("/api/playlists", methods=["GET", "POST"])
def manage_playlists():
    """Create a new playlist (POST) or list existing playlists (GET)."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401

    if request.method == "POST":
        data = request.get_json() or {}
        name = data.get("name", "New Playlist")
        items = data.get("items", [])
        schedule_enabled = 1 if data.get("schedule_enabled") else 0
        start_time = str(data.get("start_time") or "00:00").strip()[:5]
        end_time = str(data.get("end_time") or "23:59").strip()[:5]
        raw_days = data.get("schedule_days")
        if isinstance(raw_days, list):
            schedule_days = json.dumps(raw_days)
        else:
            schedule_days = '["mon","tue","wed","thu","fri","sat","sun"]'

        pl_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO playlists (id, name, items_json, version, schedule_enabled, start_time, end_time, schedule_days, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)",
                (pl_id, name, json.dumps(items), schedule_enabled, start_time, end_time, schedule_days, now_iso),
            )
        return jsonify({"success": True, "id": pl_id})

    with get_db() as conn:
        media_rows = {
            r["id"]: r["original_name"]
            for r in conn.execute("SELECT id, original_name FROM media").fetchall()
        }
        playlists = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM playlists ORDER BY updated_at DESC"
            ).fetchall()
        ]
        for p in playlists:
            try:
                p["items"] = json.loads(p["items_json"])
            except (json.JSONDecodeError, TypeError):
                p["items"] = []
            for item in p["items"]:
                m_id = item.get("media_id")
                if m_id and m_id in media_rows:
                    item["original_name"] = media_rows[m_id]
                elif not item.get("original_name"):
                    item["original_name"] = item.get("filename", "")
            p["schedule_enabled"] = bool(p.get("schedule_enabled", 0))
            p["start_time"] = p.get("start_time") or "00:00"
            p["end_time"] = p.get("end_time") or "23:59"
            try:
                p["schedule_days"] = json.loads(p.get("schedule_days") or '["mon","tue","wed","thu","fri","sat","sun"]')
            except Exception:
                p["schedule_days"] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    return jsonify(playlists)


@admin_api_bp.route("/api/playlists/<pl_id>", methods=["PUT", "DELETE"])
def update_playlist(pl_id: str):
    """Update or delete a playlist."""
    if not require_auth():
        return jsonify({"error": "unauthorized"}), 401

    with get_db() as conn:
        if request.method == "DELETE":
            conn.execute("DELETE FROM playlists WHERE id = ?", (pl_id,))
            return jsonify({"success": True})

        data = request.get_json() or {}
        now_iso = datetime.now(timezone.utc).isoformat()

        updates = ["version = version + 1", "updated_at = ?"]
        params: list[Any] = [now_iso]

        if "name" in data and data["name"] is not None:
            updates.append("name = ?")
            params.append(str(data["name"]).strip())

        if "items" in data and data["items"] is not None:
            updates.append("items_json = ?")
            params.append(json.dumps(data["items"]))

        if "schedule_enabled" in data:
            updates.append("schedule_enabled = ?")
            params.append(1 if data["schedule_enabled"] else 0)

        if "start_time" in data and data["start_time"]:
            updates.append("start_time = ?")
            params.append(str(data["start_time"]).strip()[:5])

        if "end_time" in data and data["end_time"]:
            updates.append("end_time = ?")
            params.append(str(data["end_time"]).strip()[:5])

        if "schedule_days" in data:
            updates.append("schedule_days = ?")
            raw_days = data["schedule_days"]
            params.append(json.dumps(raw_days if isinstance(raw_days, list) else ["mon","tue","wed","thu","fri","sat","sun"]))

        params.append(pl_id)
        query = f"UPDATE playlists SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, tuple(params))

    return jsonify({"success": True})
