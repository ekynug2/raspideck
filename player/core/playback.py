"""Hardware-accelerated VLC playback engine for fullscreen videos and images."""

from __future__ import annotations

import time
from pathlib import Path

from core.config import POLL_INTERVAL
from core.screens import generate_pairing_image, generate_waiting_image

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
    """Load media into VLC player, play fullscreen, and wait until ended."""
    if not _VLC_AVAILABLE or VLC_PLAYER is None or VLC_INSTANCE is None:
        print(f"[player-mock] Playing: {path.name}", flush=True)
        time.sleep(2)
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
    # Wait until ended or error (with max duration safeguard)
    while VLC_PLAYER.get_state() != _STATE_ENDED:
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
    time.sleep(0.2)


def play_image(path: Path, duration: int) -> None:
    """Show image fullscreen for duration seconds via VLC without closing window."""
    if not _VLC_AVAILABLE or VLC_PLAYER is None or VLC_INSTANCE is None:
        print(f"[player-mock] Showing image {path.name} for {duration}s", flush=True)
        time.sleep(min(duration, 2))
        return

    media = VLC_INSTANCE.media_new_path(str(path))  # type: ignore[union-attr]
    media.add_option(f":image-duration={duration}")
    VLC_PLAYER.set_media(media)
    if not VLC_PLAYER.get_fullscreen():
        VLC_PLAYER.set_fullscreen(True)
    VLC_PLAYER.play()

    # Image displays for duration seconds
    time.sleep(duration)
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
    """Stop active playback gracefully."""
    if _VLC_AVAILABLE and VLC_PLAYER is not None:
        try:
            VLC_PLAYER.stop()
        except (OSError, AttributeError) as e:
            print(f"[player] Warning during VLC stop: {e}", flush=True)
