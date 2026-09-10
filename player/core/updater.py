"""Safe Over-The-Air (OTA) updater for RaspiDeck Player with atomic swap and rollback."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from core.config import APP_VERSION, DATA_DIR, SERVER_URL, load_device_token

LOCK_FILE = DATA_DIR / ".update.lock"
STAGING_DIR = DATA_DIR / ".staging"
VERSIONS_DIR = DATA_DIR / "versions"
CURRENT_LINK = DATA_DIR / "current"
PREVIOUS_VERSION_FILE = DATA_DIR / ".previous_version.txt"


def acquire_lock() -> bool:
    """Acquire local filesystem lock to prevent concurrent update processes."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if LOCK_FILE.exists():
            # Check lock staleness (> 20 mins)
            mtime = LOCK_FILE.stat().st_mtime
            if time.time() - mtime < 1200:
                print("[updater] Update lock active, another update is running.", flush=True)
                return False
        LOCK_FILE.write_text(str(os.getpid()))
        return True
    except OSError as e:
        print(f"[updater] Failed to acquire lock: {e}", flush=True)
        return False


def release_lock() -> None:
    """Release the local update lock."""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except OSError:
        pass


def check_disk_space(min_mb: int = 50) -> bool:
    """Ensure sufficient free disk space on root/data partition before downloading."""
    try:
        total, used, free = shutil.disk_usage(DATA_DIR)
        free_mb = free / (1024 * 1024)
        if free_mb < min_mb:
            print(f"[updater] Insufficient disk space: {free_mb:.1f}MB free, {min_mb}MB required.", flush=True)
            return False
        return True
    except OSError as e:
        print(f"[updater] Failed to check disk space: {e}", flush=True)
        return True


def report_status_to_server(
    status: str,
    version: str | None = None,
    detail: str = "",
) -> None:
    """Report real-time update progress to server."""
    from core.api import api_post
    from core.config import DEVICE_ID

    payload = {
        "device_id": DEVICE_ID,
        "status": status,
        "version": version or APP_VERSION,
        "detail": detail,
    }
    try:
        api_post("/api/player/update/status", payload)
    except Exception as e:
        print(f"[updater] Failed to report status to server: {e}", flush=True)


def download_package_resumable(
    url_path: str,
    target_path: Path,
    expected_sha256: str,
    progress_cb: Callable[[int, str], None] | None = None,
    max_retries: int = 3,
) -> bool:
    """Download update package with Range header resume support and retry backoff."""
    full_url = f"{SERVER_URL}{url_path}"
    token = load_device_token()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, max_retries + 1):
        try:
            downloaded = target_path.stat().st_size if target_path.exists() else 0
            headers: dict[str, str] = {"User-Agent": f"RaspiDeck-Player/{APP_VERSION}"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"

            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                mode = "ab" if (downloaded > 0 and resp.status == 206) else "wb"
                if mode == "wb":
                    downloaded = 0

                content_len = resp.headers.get("Content-Length")
                total_bytes = (int(content_len) + downloaded) if content_len else 0

                with open(target_path, mode) as out:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        out.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total_bytes > 0:
                            pct = int((downloaded / total_bytes) * 100)
                            progress_cb(pct, f"Mengunduh paket pembaruan ({pct}%)...")

            # Validate SHA256
            hasher = hashlib.sha256()
            with open(target_path, "rb") as f:
                while c := f.read(65536):
                    hasher.update(c)
            actual_sha = hasher.hexdigest()

            if actual_sha != expected_sha256:
                print(f"[updater] SHA256 mismatch (got {actual_sha}, expected {expected_sha256}), retrying...", flush=True)
                target_path.unlink(missing_ok=True)
                time.sleep(2 * attempt)
                continue

            return True

        except (urllib.error.URLError, OSError) as e:
            print(f"[updater] Download attempt {attempt} failed: {e}", flush=True)
            time.sleep(2 ** attempt)

    return False


def smoke_test_version(version_dir: Path) -> bool:
    """Run syntax sanity check on new version files before activating."""
    main_py = version_dir / "player.py"
    if not main_py.exists():
        print("[updater] Smoke test failed: player.py not found in version dir", flush=True)
        return False

    try:
        res = subprocess.run(
            [sys.executable, "-m", "py_compile", str(main_py)],
            capture_output=True,
            timeout=10,
        )
        return res.returncode == 0
    except Exception as e:
        print(f"[updater] Smoke test execution error: {e}", flush=True)
        return False


def cleanup_old_versions(keep_count: int = 2) -> None:
    """Retain only the last N versions in versions/ to save SD card storage."""
    if not VERSIONS_DIR.exists():
        return

    try:
        all_dirs = [d for d in VERSIONS_DIR.iterdir() if d.is_dir()]
        all_dirs.sort(key=lambda d: d.stat().st_mtime)
        while len(all_dirs) > keep_count:
            oldest = all_dirs.pop(0)
            print(f"[updater] Pruning old version directory: {oldest.name}", flush=True)
            shutil.rmtree(oldest, ignore_errors=True)
    except Exception as e:
        print(f"[updater] Version cleanup notice: {e}", flush=True)


def rollback() -> bool:
    """Atomic rollback to previous version if boot validation fails."""
    if not PREVIOUS_VERSION_FILE.exists():
        print("[updater] No previous version record found for rollback.", flush=True)
        return False

    try:
        prev_dir_str = PREVIOUS_VERSION_FILE.read_text().strip()
        prev_dir = Path(prev_dir_str)
        if not prev_dir.exists():
            print(f"[updater] Previous version dir does not exist: {prev_dir}", flush=True)
            return False

        print(f"[updater] Initiating safe rollback to {prev_dir.name}...", flush=True)
        report_status_to_server("rolled_back", detail=f"Rollback to {prev_dir.name}")

        # Atomic symlink swap
        tmp_link = CURRENT_LINK.with_suffix(".tmp_rb")
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()

        os.symlink(prev_dir, tmp_link)
        os.replace(tmp_link, CURRENT_LINK)

        # Trigger restart
        restart_script = DATA_DIR / "bin" / "restart-player.sh"
        if restart_script.exists():
            subprocess.run(["sudo", str(restart_script), "restart"], check=False)
        else:
            subprocess.run(["sudo", "systemctl", "restart", "raspideck"], check=False)

        return True
    except Exception as e:
        print(f"[updater] Rollback error: {e}", flush=True)
        return False


def execute_update(
    manifest: dict[str, Any],
    gui_progress_cb: Callable[[int, str], None] | None = None,
) -> bool:
    """Execute complete staging, validation, atomic swap, and service restart."""
    target_version = manifest.get("version", "unknown")
    download_url = manifest.get("url") or manifest.get("download_url")
    sha256_hash = manifest.get("sha256")
    min_space = manifest.get("min_free_space_mb", 50)

    if not download_url or not sha256_hash:
        print("[updater] Invalid update manifest missing url or sha256", flush=True)
        return False

    if not acquire_lock():
        return False

    try:
        # 1. Disk check
        if not check_disk_space(min_space):
            report_status_to_server("failed: disk_full", target_version, "Penyimpanan microSD penuh")
            release_lock()
            return False

        # 2. Download to staging
        report_status_to_server("downloading", target_version, "Mengunduh paket pembaruan...")
        if gui_progress_cb:
            gui_progress_cb(10, "Mengunduh pembaruan...")

        staging_tar = STAGING_DIR / f"player-v{target_version}.tar.gz"
        ok = download_package_resumable(
            download_url,
            staging_tar,
            sha256_hash,
            progress_cb=gui_progress_cb,
        )

        if not ok:
            report_status_to_server("failed: download_failed", target_version, "Gagal mengunduh paket atau checksum tidak cocok")
            release_lock()
            return False

        # 3. Extract to versioned directory
        report_status_to_server("applying", target_version, "Mengekstrak file pembaruan...")
        if gui_progress_cb:
            gui_progress_cb(75, "Mengekstrak file sistem...")

        target_version_dir = VERSIONS_DIR / f"v{target_version}"
        target_version_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(staging_tar, "r:gz") as tar:
            tar.extractall(target_version_dir)

        # 4. Smoke test
        if not smoke_test_version(target_version_dir):
            report_status_to_server("failed: smoke_test_failed", target_version, "Validasi sintaks versi baru gagal")
            shutil.rmtree(target_version_dir, ignore_errors=True)
            release_lock()
            return False

        # 5. Record previous version before swap
        if CURRENT_LINK.exists() and CURRENT_LINK.is_symlink():
            try:
                resolved = CURRENT_LINK.resolve()
                PREVIOUS_VERSION_FILE.write_text(str(resolved))
            except Exception:
                pass

        # 6. Atomic swap symlink
        if gui_progress_cb:
            gui_progress_cb(90, "Mengaktifkan versi baru...")

        tmp_link = CURRENT_LINK.with_suffix(".tmp_swap")
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink()

        try:
            os.symlink(target_version_dir, tmp_link)
            os.replace(tmp_link, CURRENT_LINK)
            print(f"[updater] Symlink swapped to {target_version_dir}", flush=True)
        except OSError as e:
            # Fallback for systems not using symlinks: sync into live folder
            print(f"[updater] Symlink swap notice: {e}. Syncing directory contents...", flush=True)
            for item in target_version_dir.iterdir():
                dest = DATA_DIR / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

        # Clean staging archive
        staging_tar.unlink(missing_ok=True)
        cleanup_old_versions(keep_count=2)

        # 7. Restart service
        report_status_to_server("success", target_version, f"Versi v{target_version} berhasil dipasang")
        if gui_progress_cb:
            gui_progress_cb(100, "Update selesai! Memulai ulang player...")

        time.sleep(1)
        release_lock()

        restart_script = DATA_DIR / "bin" / "restart-player.sh"
        if restart_script.exists():
            subprocess.Popen(["sudo", str(restart_script), "restart"])
        else:
            subprocess.Popen(["sudo", "systemctl", "restart", "raspideck"])

        sys.exit(0)
        return True

    except Exception as e:
        print(f"[updater] Update failed with exception: {e}", flush=True)
        report_status_to_server(f"failed: {e}", target_version, str(e))
        release_lock()
        return False
