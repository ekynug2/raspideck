"""Hardware-accelerated VLC playback engine for fullscreen videos and images."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from core.config import POLL_INTERVAL
from core.screens import generate_pairing_image, generate_waiting_image

# Skip event flag to abort current playback and advance immediately
SKIP_REQUESTED = threading.Event()


def request_skip() -> None:
    """Signal active media playback to stop immediately and advance to next playlist item."""
    print("[player-playback] Skip signal received! Aborting current media...", flush=True)
    SKIP_REQUESTED.set()
    if _VLC_AVAILABLE and VLC_PLAYER is not None:
        try:
            VLC_PLAYER.stop()
        except Exception:
            pass


try:
    import platform

    import vlc  # type: ignore[import-unresolved]

    _VLC_AVAILABLE = True
    vlc_args = [
        "--no-video-title-show",
        "--no-osd",
        "--no-mouse-events",
        "--no-keyboard-events",
        "--avcodec-hw=auto",
        "--no-sub-autodetect-file",
        "--file-caching=1000",
        "--quiet",
    ]
    if platform.system() == "Linux":
        vlc_args.extend([
            "--vout=xcb_x11",
            "--aout=alsa",
            "--no-dbus",
            "--x11-display=:0",
        ])

    VLC_INSTANCE = vlc.Instance(*vlc_args)  # type: ignore[attr-defined]
    VLC_PLAYER = VLC_INSTANCE.media_player_new()  # type: ignore[union-attr]
    VLC_PLAYER.set_fullscreen(True)
    _STATE_PLAYING = vlc.State.Playing  # type: ignore[attr-defined]
    _STATE_ENDED = vlc.State.Ended  # type: ignore[attr-defined]
    _STATE_ERROR = vlc.State.Error  # type: ignore[attr-defined]
    _WAIT_STATES = {_STATE_PLAYING, _STATE_ENDED, _STATE_ERROR}
except (ImportError, OSError, AttributeError) as e:
    _VLC_AVAILABLE = False
    VLC_INSTANCE = None
    VLC_PLAYER = None
    _STATE_PLAYING = 3
    _STATE_ENDED = 6
    _STATE_ERROR = 7
    _WAIT_STATES = {3, 6, 7}
    print(f"[player] Warning: VLC engine initialization fallback ({e})", flush=True)


def vlc_play_and_wait(path: Path, max_duration: int = 0) -> None:
    """Load media into VLC player, play fullscreen, and wait until ended or skipped."""
    SKIP_REQUESTED.clear()
    if not _VLC_AVAILABLE or VLC_PLAYER is None or VLC_INSTANCE is None:
        print(f"[player-mock] Playing: {path.name}", flush=True)
        end_t = time.time() + 2
        while time.time() < end_t:
            if SKIP_REQUESTED.is_set():
                SKIP_REQUESTED.clear()
                break
            time.sleep(0.05)
        return

    media = VLC_INSTANCE.media_new_path(str(path))  # type: ignore[union-attr]
    VLC_PLAYER.set_media(media)
    if not VLC_PLAYER.get_fullscreen():
        VLC_PLAYER.set_fullscreen(True)
    VLC_PLAYER.audio_set_mute(False)

    # Sync volume from local display settings
    try:
        from core.settings import load_settings

        vol = int(load_settings().get("volume", 100))
        VLC_PLAYER.audio_set_volume(max(0, min(100, vol)))
    except Exception:
        VLC_PLAYER.audio_set_volume(100)

    VLC_PLAYER.play()

    # Wait for playback to start (max 5s)
    wait = 0
    while VLC_PLAYER.get_state() not in _WAIT_STATES:
        if SKIP_REQUESTED.is_set():
            SKIP_REQUESTED.clear()
            try:
                VLC_PLAYER.stop()
            except Exception:
                pass
            return
        time.sleep(0.05)
        wait += 1
        if wait > 100:
            print(f"[player] Timeout starting: {path.name}", flush=True)
            try:
                VLC_PLAYER.stop()
            except Exception:
                pass
            return

    start_time = time.time()
    # Wait until ended, error, or skip requested
    while VLC_PLAYER.get_state() != _STATE_ENDED:
        if SKIP_REQUESTED.is_set():
            print(f"[player] Skip requested: advancing past {path.name}", flush=True)
            SKIP_REQUESTED.clear()
            break
        if VLC_PLAYER.get_state() == _STATE_ERROR:
            print(f"[player] Error playing: {path.name}", flush=True)
            break
        if max_duration > 0 and (time.time() - start_time) >= (max_duration + 2):
            break
        time.sleep(0.05)

    # Stop and clean up player before next media to prevent freeze in Ended state
    try:
        VLC_PLAYER.stop()
    except Exception:
        pass
    time.sleep(0.15)


def play_image(path: Path, duration: int) -> None:
    """Show image fullscreen for duration seconds via VLC without closing window (interruptible by skip)."""
    SKIP_REQUESTED.clear()
    if not _VLC_AVAILABLE or VLC_PLAYER is None or VLC_INSTANCE is None:
        print(f"[player-mock] Showing image {path.name} for {duration}s", flush=True)
        end_t = time.time() + min(duration, 2)
        while time.time() < end_t:
            if SKIP_REQUESTED.is_set():
                SKIP_REQUESTED.clear()
                break
            time.sleep(0.05)
        return

    media = VLC_INSTANCE.media_new_path(str(path))  # type: ignore[union-attr]
    media.add_option(f":image-duration={duration}")
    VLC_PLAYER.set_media(media)
    if not VLC_PLAYER.get_fullscreen():
        VLC_PLAYER.set_fullscreen(True)
    VLC_PLAYER.play()

    # Wait for image duration with responsive skip check
    end_t = time.time() + duration
    while time.time() < end_t:
        if SKIP_REQUESTED.is_set():
            print(f"[player] Skip requested: advancing past image {path.name}", flush=True)
            SKIP_REQUESTED.clear()
            break
        time.sleep(0.05)

    try:
        VLC_PLAYER.stop()
    except Exception:
        pass
    time.sleep(0.1)


def play_video(path: Path, duration: int = 0) -> None:
    """Play video fullscreen via VLC python binding until ended."""
    vlc_play_and_wait(path, max_duration=duration)


def show_waiting_screen(message: str = "Waiting for Playlist...") -> None:
    """Display waiting screen fullscreen on Pi via VLC."""
    print(f"[player] Idle: {message}", flush=True)
    waiting_img = generate_waiting_image(message=message)
    if waiting_img.exists() and waiting_img.stat().st_size > 0:
        play_image(waiting_img, duration=POLL_INTERVAL)


def show_pairing_screen(code: str) -> None:
    """Display pairing code fullscreen on Pi via VLC."""
    print(f"[player] Pairing Code: {code}", flush=True)
    pairing_img = generate_pairing_image(code)
    if pairing_img.exists() and pairing_img.stat().st_size > 0:
        play_image(pairing_img, duration=POLL_INTERVAL)
    else:
        # Terminal fallback if image cannot be shown
        print(f"\n{'=' * 40}")
        print(f"  PAIRING CODE: {code}")
        print("  Enter this code in the web dashboard")
        print(f"{'=' * 40}\n", flush=True)


def stop_playback() -> None:
    """Stop active playback gracefully and signal any wait loops."""
    SKIP_REQUESTED.set()
    if _VLC_AVAILABLE and VLC_PLAYER is not None:
        try:
            VLC_PLAYER.stop()
        except (OSError, AttributeError) as e:
            print(f"[player] Warning during VLC stop: {e}", flush=True)


def format_ms_time(ms: int) -> str:
    """Format milliseconds into MM:SS format."""
    if not ms or ms < 0:
        return "00:00"
    total_sec = int(ms / 1000)
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins:02d}:{secs:02d}"


def get_playback_health() -> dict[str, Any]:
    """Inspect realtime video playback quality, freeze status, and shuttering/dropped frames."""
    if not _VLC_AVAILABLE or VLC_PLAYER is None:
        return {
            "status": "standby",
            "message": "Player engine offline / belum aktif",
            "is_playing": False,
            "media_type": "none",
            "fps": 0.0,
            "freeze_detected": False,
            "stutter_detected": False,
            "displayed_frames": 0,
            "lost_frames": 0,
            "drop_rate_pct": 0.0,
        }

    try:
        raw_state = VLC_PLAYER.get_state()
        is_playing = bool(raw_state == _STATE_PLAYING)
        time_ms = int(VLC_PLAYER.get_time() or 0)
        length_ms = int(VLC_PLAYER.get_length() or 0)
        fps = round(float(VLC_PLAYER.get_fps() or 0.0), 1)

        displayed = 0
        lost = 0
        decoded = 0
        media = VLC_PLAYER.get_media()
        if media:
            try:
                stats = vlc.MediaStats()
                if media.get_stats(stats):
                    displayed = int(stats.displayed_pictures or 0)
                    lost = int(stats.lost_pictures or 0)
                    decoded = int(stats.decoded_video or 0)
            except Exception:
                pass

        if not is_playing:
            return {
                "status": "standby",
                "message": "Player dalam keadaan idle / tidak sedang memutar video",
                "is_playing": False,
                "media_type": "none",
                "time_ms": time_ms,
                "length_ms": length_ms,
                "fps": fps,
                "freeze_detected": False,
                "stutter_detected": False,
                "displayed_frames": displayed,
                "lost_frames": lost,
                "drop_rate_pct": 0.0,
            }

        # 1. Freeze Detection: Check whether playback timestamp advances over 350ms
        freeze_detected = False
        t_start = time_ms
        disp_start = displayed
        time.sleep(0.35)
        t_now = int(VLC_PLAYER.get_time() or 0)

        disp_now = displayed
        if media:
            try:
                stats = vlc.MediaStats()
                if media.get_stats(stats):
                    disp_now = int(stats.displayed_pictures or 0)
                    lost = int(stats.lost_pictures or 0)
            except Exception:
                pass

        if length_ms > 2000 and t_now == t_start and (disp_now == disp_start):
            time.sleep(0.3)
            t_confirm = int(VLC_PLAYER.get_time() or 0)
            if t_confirm == t_start and VLC_PLAYER.get_state() == _STATE_PLAYING:
                freeze_detected = True

        # 2. Shuttering / Dropped Frames Detection
        total_frames = disp_now + lost
        drop_rate = round((lost / total_frames * 100.0), 2) if total_frames > 0 else 0.0
        stutter_detected = bool(lost > 3 and drop_rate > 1.5)

        # 3. Status & Diagnostic Message
        if freeze_detected:
            status = "frozen"
            msg = f"PERINGATAN: Video macet (freeze). Frame terhenti pada posisi {format_ms_time(t_now)}."
        elif stutter_detected:
            status = "stuttering"
            msg = f"PERINGATAN: Video shuttering / patah-patah ({lost} frame drop, {drop_rate}% frame hilang)."
        else:
            status = "smooth"
            msg = f"Pemutaran lancar tanpa lag ({disp_now} frame tertayang, {drop_rate}% drop)."

        return {
            "status": status,
            "message": msg,
            "is_playing": True,
            "media_type": "video",
            "time_ms": t_now,
            "length_ms": length_ms,
            "position": round(float(VLC_PLAYER.get_position() or 0.0), 3),
            "fps": fps,
            "freeze_detected": freeze_detected,
            "stutter_detected": stutter_detected,
            "displayed_frames": disp_now,
            "lost_frames": lost,
            "decoded_frames": decoded,
            "drop_rate_pct": drop_rate,
        }
    except Exception as e:
        return {
            "status": "unknown",
            "message": f"Evaluasi playback error: {e}",
            "is_playing": False,
            "freeze_detected": False,
            "stutter_detected": False,
        }


def capture_display_snapshot(target_path: Path) -> bool:
    """Capture current monitor display image (VLC video frame or X11 screen)."""
    import os
    import shutil
    import subprocess

    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        try:
            target_path.unlink()
        except OSError:
            pass

    def _normalize_image(src: Path) -> bool:
        try:
            if src.exists() and src.stat().st_size > 512:
                from PIL import Image

                with Image.open(src) as im:
                    rgb = im.convert("RGB")
                    if rgb.width > 1280 or rgb.height > 720:
                        rgb.thumbnail((1280, 720), getattr(Image.Resampling, "LANCZOS", Image.LANCZOS))
                    rgb.save(str(target_path), "JPEG", quality=80)
                if src != target_path:
                    src.unlink(missing_ok=True)
                return bool(target_path.exists() and target_path.stat().st_size > 512)
        except Exception as err:
            print(f"[playback] Image normalization error: {err}", flush=True)
        return False

    # Method 1: If VLC is currently playing, use native LibVLC snapshot (0, 0 = original resolution)
    if _VLC_AVAILABLE and VLC_PLAYER is not None:
        try:
            state = VLC_PLAYER.get_state()
            if state in (_STATE_PLAYING, getattr(vlc.State, "Paused", 4)):
                temp_png = target_path.with_suffix(".png")
                temp_png.unlink(missing_ok=True)
                # Try PNG first as LibVLC always bundles PNG encoder
                VLC_PLAYER.video_take_snapshot(0, str(temp_png), 0, 0)
                for _ in range(20):
                    if temp_png.exists() and temp_png.stat().st_size > 512:
                        if _normalize_image(temp_png):
                            return True
                    time.sleep(0.1)

                # Fallback: direct to target_path
                VLC_PLAYER.video_take_snapshot(0, str(target_path), 0, 0)
                for _ in range(15):
                    if target_path.exists() and target_path.stat().st_size > 512:
                        return True
                    time.sleep(0.1)
        except Exception as e:
            print(f"[playback] VLC video snapshot error: {e}", flush=True)

    # Method 2: X11 screen capture via scrot
    env = {**os.environ, "DISPLAY": ":0"}
    if shutil.which("scrot"):
        try:
            tmp_scrot = target_path.with_suffix(".scrot.jpg")
            subprocess.run(
                ["scrot", "-z", "-q", "80", str(tmp_scrot)],
                env=env,
                capture_output=True,
                timeout=3,
            )
            if _normalize_image(tmp_scrot):
                return True
        except Exception:
            pass

    # Method 3: xwd + convert or PIL
    if shutil.which("xwd"):
        try:
            xwd_out = target_path.with_suffix(".xwd")
            subprocess.run(
                ["xwd", "-root", "-silent", "-out", str(xwd_out)],
                env=env,
                capture_output=True,
                timeout=3,
            )
            if _normalize_image(xwd_out):
                return True
        except Exception:
            pass

    # Method 4: ffmpeg x11grab (single frame)
    if shutil.which("ffmpeg"):
        try:
            tmp_ff = target_path.with_suffix(".ff.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "x11grab", "-video_size", "1280x720", "-i", ":0.0", "-vframes", "1", "-q:v", "3", str(tmp_ff)],
                env=env,
                capture_output=True,
                timeout=4,
            )
            if _normalize_image(tmp_ff):
                return True
        except Exception:
            pass

    # Method 5: PIL ImageGrab
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()
        if img:
            rgb = img.convert("RGB")
            if rgb.width > 1280 or rgb.height > 720:
                rgb.thumbnail((1280, 720), getattr(Image.Resampling, "LANCZOS", Image.LANCZOS))
            rgb.save(str(target_path), "JPEG", quality=80)
            if target_path.exists() and target_path.stat().st_size > 512:
                return True
    except Exception:
        pass

    return False


