"""Database access and schema management for RaspiDeck Server."""

from __future__ import annotations

import sqlite3

from config import DB_PATH


def get_db() -> sqlite3.Connection:
    """Return a SQLite connection with Row factory and WAL mode enabled for high concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db() -> None:
    """Initialize database tables if they do not exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                items_json TEXT NOT NULL DEFAULT '[]',
                version INTEGER NOT NULL DEFAULT 1,
                schedule_enabled INTEGER NOT NULL DEFAULT 0,
                start_time TEXT DEFAULT '00:00',
                end_time TEXT DEFAULT '23:59',
                schedule_days TEXT DEFAULT '["mon","tue","wed","thu","fri","sat","sun"]',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS screens (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                pairing_code TEXT,
                is_paired INTEGER NOT NULL DEFAULT 0,
                playlist_id TEXT,
                last_seen TEXT,
                ip_address TEXT,
                system_info TEXT DEFAULT '{}',
                pending_command TEXT,
                settings TEXT DEFAULT '{}',
                app_version TEXT DEFAULT '2.0',
                update_status TEXT DEFAULT 'idle',
                pending_update TEXT DEFAULT NULL,
                device_token TEXT DEFAULT NULL,
                update_lock_acquired_at TEXT DEFAULT NULL,
                last_update_log TEXT DEFAULT '[]',
                FOREIGN KEY(playlist_id) REFERENCES playlists(id) ON DELETE SET NULL
            );
        """)

        # Migration: ensure pending_command and OTA columns exist in existing screens tables
        cols = [col[1] for col in conn.execute("PRAGMA table_info(screens)").fetchall()]
        if "pending_command" not in cols:
            conn.execute("ALTER TABLE screens ADD COLUMN pending_command TEXT")
        if "settings" not in cols:
            conn.execute("ALTER TABLE screens ADD COLUMN settings TEXT DEFAULT '{}'")
        if "app_version" not in cols:
            conn.execute("ALTER TABLE screens ADD COLUMN app_version TEXT DEFAULT '2.0'")
        if "update_status" not in cols:
            conn.execute("ALTER TABLE screens ADD COLUMN update_status TEXT DEFAULT 'idle'")
        if "pending_update" not in cols:
            conn.execute("ALTER TABLE screens ADD COLUMN pending_update TEXT DEFAULT NULL")
        if "device_token" not in cols:
            conn.execute("ALTER TABLE screens ADD COLUMN device_token TEXT DEFAULT NULL")
        if "update_lock_acquired_at" not in cols:
            conn.execute("ALTER TABLE screens ADD COLUMN update_lock_acquired_at TEXT DEFAULT NULL")
        if "last_update_log" not in cols:
            conn.execute("ALTER TABLE screens ADD COLUMN last_update_log TEXT DEFAULT '[]'")

        # Migration: ensure schedule columns exist in existing playlists tables
        pl_cols = [col[1] for col in conn.execute("PRAGMA table_info(playlists)").fetchall()]
        if "schedule_enabled" not in pl_cols:
            conn.execute("ALTER TABLE playlists ADD COLUMN schedule_enabled INTEGER NOT NULL DEFAULT 0")
        if "start_time" not in pl_cols:
            conn.execute("ALTER TABLE playlists ADD COLUMN start_time TEXT DEFAULT '00:00'")
        if "end_time" not in pl_cols:
            conn.execute("ALTER TABLE playlists ADD COLUMN end_time TEXT DEFAULT '23:59'")
        if "schedule_days" not in pl_cols:
            conn.execute("ALTER TABLE playlists ADD COLUMN schedule_days TEXT DEFAULT '[\"mon\",\"tue\",\"wed\",\"thu\",\"fri\",\"sat\",\"sun\"]'")
