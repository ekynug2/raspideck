"""Display configuration and hardware settings manager for RaspiDeck Player (Pi 3 / 3B+)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from typing import Any

from core.config import DATA_DIR, SETTINGS_FILE

DEFAULT_SETTINGS: dict[str, Any] = {
    "volume": 100,
    "rotation": "normal",
    "heartbeat_interval": 10,
    "screen_power": "on",
}

_CACHED_ALSA_CARD: int | None = None
_CACHED_XRANDR_OUTPUT: str | None = None


def compute_settings_hash(settings: dict[str, Any]) -> str:
    """Compute deterministic SHA256 hash of settings object."""
    normalized = json.dumps(settings, sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def load_settings() -> dict[str, Any]:
    """Load settings from local JSON file atomically, merged with defaults."""
    if SETTINGS_FILE.exists():
        try:
            raw = SETTINGS_FILE.read_text()
            data = json.loads(raw)
            return {**DEFAULT_SETTINGS, **data}
        except (OSError, json.JSONDecodeError) as e:
            print(f"[settings] Failed to parse {SETTINGS_FILE}, using defaults: {e}", flush=True)
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict[str, Any]) -> bool:
    """Atomically write settings to disk using a temporary file and os.replace."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp_file = SETTINGS_FILE.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(settings, indent=2))
        os.replace(tmp_file, SETTINGS_FILE)
        return True
    except OSError as e:
        print(f"[settings] Failed to save settings atomically: {e}", flush=True)
        return False


def detect_alsa_card() -> int:
    """Detect HDMI or primary audio output card index on Raspberry Pi 3 via aplay -l."""
    global _CACHED_ALSA_CARD
    if _CACHED_ALSA_CARD is not None:
        return _CACHED_ALSA_CARD

    try:
        res = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            # Look for HDMI card first
            for line in res.stdout.splitlines():
                if "card" in line.lower() and "hdmi" in line.lower():
                    m = re.search(r"card\s+(\d+):", line, re.IGNORECASE)
                    if m:
                        _CACHED_ALSA_CARD = int(m.group(1))
                        return _CACHED_ALSA_CARD
            # Fallback to first card found
            m = re.search(r"card\s+(\d+):", res.stdout, re.IGNORECASE)
            if m:
                _CACHED_ALSA_CARD = int(m.group(1))
                return _CACHED_ALSA_CARD
    except Exception:
        pass

    _CACHED_ALSA_CARD = 0
    return _CACHED_ALSA_CARD


def detect_xrandr_output() -> str | None:
    """Detect connected display output name from xrandr query (e.g. HDMI-1, HDMI-2)."""
    global _CACHED_XRANDR_OUTPUT
    if _CACHED_XRANDR_OUTPUT:
        return _CACHED_XRANDR_OUTPUT

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    try:
        res = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, env=env, timeout=3)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if " connected" in line:
                    parts = line.split()
                    if parts:
                        _CACHED_XRANDR_OUTPUT = parts[0]
                        return _CACHED_XRANDR_OUTPUT
    except Exception:
        pass

    return None


def apply_volume(volume: int) -> None:
    """Set system audio volume (0-100%) on Raspberry Pi."""
    vol = max(0, min(100, int(volume)))
    card = detect_alsa_card()

    # Try setting Master control on detected card
    cmds = [
        ["amixer", "-c", str(card), "sset", "Master", f"{vol}%"],
        ["amixer", "-c", str(card), "sset", "PCM", f"{vol}%"],
        ["amixer", "sset", "Master", f"{vol}%"],
        ["amixer", "sset", "PCM", f"{vol}%"],
    ]

    applied = False
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=2)
            if res.returncode == 0:
                applied = True
                break
        except Exception:
            continue

    if applied:
        print(f"[settings] Audio volume set to {vol}% (card {card})", flush=True)


def apply_rotation(rotation: str) -> None:
    """Rotate X11 screen display (normal, right, inverted, left) via xrandr."""
    rot = str(rotation).strip().lower()
    if rot not in ("normal", "right", "inverted", "left"):
        rot = "normal"

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    output = detect_xrandr_output()
    applied = False

    if output:
        try:
            res = subprocess.run(
                ["xrandr", "--output", output, "--rotate", rot],
                capture_output=True,
                env=env,
                timeout=5,
            )
            if res.returncode == 0:
                applied = True
        except Exception:
            pass

    if not applied:
        # Fallback orientation flag
        try:
            res = subprocess.run(
                ["xrandr", "-o", rot],
                capture_output=True,
                env=env,
                timeout=5,
            )
            if res.returncode == 0:
                applied = True
        except Exception:
            pass

    if applied:
        print(f"[settings] Display rotation applied: {rot}", flush=True)


def apply_screen_power(power: Any) -> None:
    """Turn display on or off via X11 DPMS power management, preventing auto-blanking."""
    if isinstance(power, bool):
        is_on = power
    else:
        pwr = str(power).strip().lower()
        is_on = pwr in ("on", "true", "1")

    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":0"

    if is_on:
        try:
            # Wake monitor and completely disable idle DPMS power-down & screen blanking
            subprocess.run(["xset", "s", "off"], capture_output=True, env=env, timeout=3)
            subprocess.run(["xset", "s", "noblank"], capture_output=True, env=env, timeout=3)
            subprocess.run(["xset", "-dpms"], capture_output=True, env=env, timeout=3)
            subprocess.run(["xset", "dpms", "0", "0", "0"], capture_output=True, env=env, timeout=3)
            subprocess.run(["xset", "dpms", "force", "on"], capture_output=True, env=env, timeout=3)
            print("[settings] Screen power state set to on (DPMS timers disabled)", flush=True)
        except Exception as e:
            print(f"[settings] Warning applying screen power on: {e}", flush=True)
    else:
        try:
            # Put monitor into power-saving standby
            subprocess.run(["xset", "+dpms"], capture_output=True, env=env, timeout=3)
            subprocess.run(["xset", "dpms", "force", "off"], capture_output=True, env=env, timeout=3)
            print("[settings] Screen power state set to off (DPMS standby)", flush=True)
        except Exception as e:
            print(f"[settings] Warning applying screen power off: {e}", flush=True)


def apply_all_settings(new_settings: dict[str, Any]) -> None:
    """Apply complete configuration set to hardware/system."""
    if "volume" in new_settings:
        apply_volume(new_settings["volume"])
    if "rotation" in new_settings:
        apply_rotation(new_settings["rotation"])
    if "screen_power" in new_settings:
        apply_screen_power(new_settings["screen_power"])
