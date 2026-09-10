"""Hardware-accelerated X11/Tkinter kiosk screen manager for RaspiDeck.

Renders:
  1. Windows-style Booting screen with animated circular rotating dots loader.
  2. Loading Media screen with live download progress and spinner when paired.
  3. Pairing screen with large pairing code and instructions when unpaired.
  4. Idle / waiting screen when no playlist is assigned.
"""

from __future__ import annotations

import math
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any


def _get_windows_dot_angle(
    elapsed_time: float, dot_index: int, total_dots: int = 6, period: float = 2.6
) -> float:
    """Calculate the orbital angle for the iconic Windows rotating dots boot loader.

    In Windows 10/11, dots travel in a circle, decelerating at the top
    and whipping with high velocity around the bottom arc.
    """
    stagger = dot_index * 0.11
    tau = (elapsed_time - stagger) % period
    p = tau / period  # 0.0 to 1.0

    # Smooth cubic/sinusoidal easing with high acceleration at bottom arc
    p_smooth = p * p * (3.0 - 2.0 * p)
    p_dynamic = 0.5 * (p + p_smooth) - 0.12 * math.sin(2.0 * math.pi * p)
    return -math.pi / 2.0 + 2.0 * math.pi * p_dynamic


class PlayerScreenApp:
    """Tkinter-based fullscreen UI controller with thread-safe queue updates."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self.target_width = width
        self.target_height = height
        self._event_queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self._running = False
        self._root = None
        self._canvas = None
        self._headless = False

        # Current screen state
        self._current_state = "BOOT"
        self._state_data: dict[str, Any] = {
            "status": "Memulai RaspiDeck...",
            "detail": "Menyiapkan sistem & memeriksa koneksi...",
            "pairing_code": "------",
            "progress_pct": 0,
            "ip_address": "",
            "server_url": "",
            "device_id": "",
        }

        # Animation tracking
        self._start_time = time.time()
        self._spinner_dots: list[int] = []
        self._spinner_center = (width // 2, height // 2)
        self._spinner_radius = 36.0
        self._is_visible = True
        self._logo_cache: dict[str, Any] = {}

    def run(self, on_ready_callback=None) -> None:
        """Start the Tkinter GUI mainloop on the main thread."""
        try:
            import tkinter as tk

            # Verify display availability (especially on Linux X11)
            if os.name != "nt" and not os.environ.get("DISPLAY"):
                print("[gui] No DISPLAY environment found, running headless fallback", flush=True)
                self._headless = True
                if on_ready_callback:
                    threading.Thread(target=on_ready_callback, daemon=True).start()
                self._headless_loop()
                return

            self._root = tk.Tk()
            self._root.title("RaspiDeck")
            self._root.configure(bg="#070a13")

            # Try fullscreen on X11 / Windows
            try:
                self._root.attributes("-fullscreen", True)
            except Exception:
                self._root.geometry(f"{self.target_width}x{self.target_height}+0+0")

            # Hide cursor on kiosk display
            try:
                self._root.config(cursor="none")
            except Exception:
                pass

            # Detect actual window dimensions
            self._root.update_idletasks()
            sw = self._root.winfo_screenwidth() or self.target_width
            sh = self._root.winfo_screenheight() or self.target_height
            self.target_width = sw
            self.target_height = sh

            self._canvas = tk.Canvas(
                self._root,
                width=sw,
                height=sh,
                bg="#070a13",
                highlightthickness=0,
                bd=0,
            )
            self._canvas.pack(fill="both", expand=True)

            self._running = True
            self._start_time = time.time()

            # Render initial state
            self._redraw_screen()

            # Launch on_ready callback in background worker
            if on_ready_callback:
                threading.Thread(target=on_ready_callback, daemon=True).start()

            # Start animation & event tick loop (45 FPS)
            self._root.after(22, self._tick)
            self._root.mainloop()

        except Exception as e:
            print(f"[gui] Tkinter init fallback ({e}), running headless mode", flush=True)
            self._headless = True
            if on_ready_callback:
                threading.Thread(target=on_ready_callback, daemon=True).start()
            self._headless_loop()

    def _headless_loop(self) -> None:
        """Headless loop fallback when X11/Tkinter is not available."""
        self._running = True
        while self._running:
            try:
                cmd, data = self._event_queue.get(timeout=1.0)
                if cmd == "STATE":
                    self._current_state = data.get("state", self._current_state)
                    self._state_data.update(data)
                    print(f"[gui-headless] State -> {self._current_state}: {self._state_data}", flush=True)
                elif cmd == "PROGRESS":
                    self._state_data.update(data)
                elif cmd == "HIDE":
                    self._is_visible = False
                elif cmd == "SHOW":
                    self._is_visible = True
                elif cmd == "STOP":
                    break
            except queue.Empty:
                pass

    # -------------------------------------------------------------------------
    # Thread-Safe Public Control API (callable from any worker thread)
    # -------------------------------------------------------------------------

    def set_boot(self, status: str = "Memulai RaspiDeck...", detail: str = "Menyiapkan sistem...") -> None:
        """Switch to Windows-style boot screen."""
        self._event_queue.put(("STATE", {"state": "BOOT", "status": status, "detail": detail}))

    def set_pairing(
        self,
        pairing_code: str,
        ip_address: str = "",
        server_url: str = "",
        device_id: str = "",
    ) -> None:
        """Switch to Pairing code display."""
        self._event_queue.put(
            (
                "STATE",
                {
                    "state": "PAIRING",
                    "pairing_code": pairing_code,
                    "ip_address": ip_address,
                    "server_url": server_url,
                    "device_id": device_id,
                },
            )
        )

    def set_loading_media(
        self,
        status: str = "Memuat Media...",
        detail: str = "Menyiapkan playlist...",
        progress_pct: int = 0,
    ) -> None:
        """Switch to Loading Media screen with progress indicator."""
        self._event_queue.put(
            (
                "STATE",
                {
                    "state": "LOADING_MEDIA",
                    "status": status,
                    "detail": detail,
                    "progress_pct": progress_pct,
                },
            )
        )

    def update_progress(self, progress_pct: int, detail: str | None = None) -> None:
        """Update download/loading progress in real-time."""
        data: dict[str, Any] = {"progress_pct": max(0, min(100, progress_pct))}
        if detail:
            data["detail"] = detail
        self._event_queue.put(("PROGRESS", data))

    def set_waiting(self, message: str = "Menunggu Playlist dari Server...", detail: str | None = None) -> None:
        """Switch to Idle waiting screen with customizable detail text."""
        self._event_queue.put((
            "STATE",
            {
                "state": "WAITING",
                "status": message,
                "detail": detail or "Atur dan tetapkan playlist untuk layar ini melalui dashboard web",
            },
        ))

    def hide(self) -> None:
        """Hide the GUI window (for VLC fullscreen media playback)."""
        self._event_queue.put(("HIDE", {}))

    def show(self) -> None:
        """Unhide the GUI window."""
        self._event_queue.put(("SHOW", {}))

    def stop(self) -> None:
        """Terminate the GUI window."""
        self._running = False
        self._event_queue.put(("STOP", {}))
        if self._root:
            try:
                self._root.quit()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Internal GUI Rendering & Animation Loop (Main Thread Only)
    # -------------------------------------------------------------------------

    def _tick(self) -> None:
        """Periodic loop processing queue commands and animating the Windows loader."""
        if not self._running or self._root is None:
            return

        state_changed = False

        # Drain queued events
        while not self._event_queue.empty():
            try:
                cmd, data = self._event_queue.get_nowait()
                if cmd == "STATE":
                    new_state = data.get("state", self._current_state)
                    if new_state != self._current_state:
                        self._current_state = new_state
                        state_changed = True
                    self._state_data.update(data)
                    state_changed = True
                elif cmd == "PROGRESS":
                    self._state_data.update(data)
                    self._update_progress_display()
                elif cmd == "HIDE":
                    if self._is_visible:
                        self._is_visible = False
                        try:
                            self._root.withdraw()
                        except Exception:
                            pass
                elif cmd == "SHOW":
                    if not self._is_visible:
                        self._is_visible = True
                        try:
                            self._root.deiconify()
                            self._root.lift()
                            state_changed = True
                        except Exception:
                            pass
                elif cmd == "STOP":
                    self._running = False
                    try:
                        self._root.quit()
                        self._root.destroy()
                    except Exception:
                        pass
                    return
            except queue.Empty:
                break

        if state_changed and self._is_visible:
            self._redraw_screen()

        # Animate Windows circular loader if visible and on relevant screen
        if self._is_visible and self._current_state in ("BOOT", "WAITING"):
            self._animate_spinner()

        if self._running:
            self._root.after(22, self._tick)

    def _redraw_screen(self) -> None:
        """Full redraw of the screen canvas based on current state."""
        if self._canvas is None:
            return

        self._canvas.delete("all")
        self._spinner_dots.clear()

        w = self.target_width
        h = self.target_height
        cx = w // 2

        if self._current_state == "BOOT":
            self._draw_boot_screen(cx, h)
        elif self._current_state == "PAIRING":
            self._draw_pairing_screen(cx, h)
        elif self._current_state == "LOADING_MEDIA":
            self._draw_loading_media_screen(cx, h)
        elif self._current_state == "WAITING":
            self._draw_waiting_screen(cx, h)

    def _find_custom_logo(self) -> Path | None:
        """Search for custom user logo image file (PNG/JPG/WebP)."""
        env_p = os.environ.get("RASPIDECK_LOGO_PATH")
        if env_p and Path(env_p).is_file():
            return Path(env_p)
        candidates = [
            Path(__file__).resolve().parent.parent / "logo-badge.png",
            Path(__file__).resolve().parent.parent / "logo.png",
            Path(__file__).resolve().parent.parent / "logo.jpg",
            Path(__file__).resolve().parent.parent / "logo.jpeg",
            Path(__file__).resolve().parent.parent / "logo.webp",
            Path("/opt/raspideck/logo-badge.png"),
            Path("/opt/raspideck/logo.png"),
            Path("/opt/raspideck/logo.jpg"),
            Path("/opt/raspideck/media/logo-badge.png"),
            Path("/opt/raspideck/media/logo.png"),
        ]
        for c in candidates:
            if c.is_file():
                return c
        return None

    def _draw_logo(
        self,
        cx: int,
        cy: int,
        tile_size: int = 34,
        gap: int = 6,
        max_w: int = 240,
        max_h: int = 100,
    ) -> tuple[int, int]:
        """Draw custom logo image if provided, or fallback to Windows 4-quadrant tiles.

        Returns (width, height) of the rendered emblem.
        """
        logo_path = self._find_custom_logo()
        if logo_path and self._canvas is not None:
            try:
                from PIL import Image, ImageTk

                cache_key = f"{logo_path}_{max_w}_{max_h}"
                if cache_key not in self._logo_cache:
                    img = Image.open(str(logo_path))
                    w, h = img.size
                    ratio = min(max_w / w, max_h / h)
                    new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
                    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", getattr(Image, "ANTIALIAS", 1))
                    resized = img.resize(new_size, resample)
                    self._logo_cache[cache_key] = (ImageTk.PhotoImage(resized), resized.size[0], resized.size[1])

                photo, rw, rh = self._logo_cache[cache_key]
                self._canvas.create_image(cx, cy, image=photo, tags="logo")
                return (rw, rh)
            except Exception as e:
                print(f"[gui] Warning loading custom logo {logo_path}: {e}", flush=True)

        # Fallback to modern 4-tile Windows emblem
        self._draw_logo_tiles(cx, cy, tile_size=tile_size, gap=gap)
        tiles_span = (tile_size * 2) + gap
        return (tiles_span, tiles_span)

    def _draw_logo_tiles(self, cx: int, cy: int, tile_size: int = 34, gap: int = 6) -> None:
        """Draw modern Windows-style 4-quadrant glowing brand logo."""
        if self._canvas is None:
            return

        half = tile_size + gap // 2
        # Top-Left (Sky)
        x1, y1 = cx - half, cy - half
        self._canvas.create_rectangle(
            x1, y1, x1 + tile_size, y1 + tile_size, fill="#38bdf8", outline="", tags="logo"
        )
        # Top-Right (Light Blue)
        x2, y2 = cx + gap // 2, cy - half
        self._canvas.create_rectangle(
            x2, y2, x2 + tile_size, y2 + tile_size, fill="#60a5fa", outline="", tags="logo"
        )
        # Bottom-Left (Cyan Blue)
        x3, y3 = cx - half, cy + gap // 2
        self._canvas.create_rectangle(
            x3, y3, x3 + tile_size, y3 + tile_size, fill="#0284c7", outline="", tags="logo"
        )
        # Bottom-Right (Royal Blue)
        x4, y4 = cx + gap // 2, cy + gap // 2
        self._canvas.create_rectangle(
            x4, y4, x4 + tile_size, y4 + tile_size, fill="#2563eb", outline="", tags="logo"
        )

    def _init_spinner_dots(self, cx: int, cy: int, radius: float = 36.0, num_dots: int = 6) -> None:
        """Create the canvas circle dots for the Windows boot loader animation."""
        if self._canvas is None:
            return

        self._spinner_center = (cx, cy)
        self._spinner_radius = radius
        self._spinner_dots.clear()

        dot_r = 3.5
        for _ in range(num_dots):
            dot_id = self._canvas.create_oval(
                cx - dot_r,
                cy - dot_r,
                cx + dot_r,
                cy + dot_r,
                fill="#ffffff",
                outline="",
                tags="spinner",
            )
            self._spinner_dots.append(dot_id)

    def _animate_spinner(self) -> None:
        """Move the Windows spinner dots along the circular easing orbit."""
        if not self._spinner_dots or self._canvas is None:
            return

        cx, cy = self._spinner_center
        r = self._spinner_radius
        elapsed = time.time() - self._start_time
        dot_r = 3.5

        for i, dot_id in enumerate(self._spinner_dots):
            angle = _get_windows_dot_angle(elapsed, i, total_dots=len(self._spinner_dots))
            dx = cx + r * math.cos(angle)
            dy = cy + r * math.sin(angle)
            self._canvas.coords(dot_id, dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r)

    # -------------------------------------------------------------------------
    # Screen Renderers: BOOT, LOADING_MEDIA, PAIRING, WAITING
    # -------------------------------------------------------------------------

    def _draw_boot_screen(self, cx: int, h: int) -> None:
        """Windows-style boot screen with centered logo and circular loader."""
        logo_y = h // 2 - 130
        _, lh = self._draw_logo(cx, logo_y, tile_size=36, gap=8, max_w=220, max_h=100)

        # Brand Title placed cleanly below the logo
        title_y = (logo_y + lh // 2) + 36
        self._canvas.create_text(
            cx,
            title_y,
            text="RaspiDeck",
            font=("Segoe UI", 32, "bold"),
            fill="#f8fafc",
            tags="static",
        )

        # Windows circular loader ring
        spinner_y = title_y + 85
        self._init_spinner_dots(cx, spinner_y, radius=34.0, num_dots=6)

        # Status text below loader
        status_y = spinner_y + 60
        self._canvas.create_text(
            cx,
            status_y,
            text=self._state_data.get("status", "Memulai RaspiDeck..."),
            font=("Segoe UI", 15),
            fill="#e2e8f0",
            tags="status_label",
        )

        # Subtitle
        self._canvas.create_text(
            cx,
            status_y + 28,
            text=self._state_data.get("detail", "Menyiapkan sistem & memeriksa koneksi..."),
            font=("Segoe UI", 12),
            fill="#64748b",
            tags="detail_label",
        )

    def _draw_loading_media_screen(self, cx: int, h: int) -> None:
        """Loading Media screen shown when device is paired and downloading/loading."""
        top_y = h // 2 - 190
        _, lh = self._draw_logo(cx, top_y, tile_size=32, gap=6, max_w=180, max_h=80)

        # Title
        title_y = (top_y + lh // 2) + 32
        self._canvas.create_text(
            cx,
            title_y,
            text="RaspiDeck",
            font=("Segoe UI", 28, "bold"),
            fill="#f8fafc",
            tags="static",
        )

        # Badge: SCREEN PAIRED
        badge_y = title_y + 44
        bw, bh = 200, 32
        self._canvas.create_rectangle(
            cx - bw // 2,
            badge_y - bh // 2,
            cx + bw // 2,
            badge_y + bh // 2,
            fill="#052e16",
            outline="#22c55e",
            width=2,
            tags="static",
        )
        self._canvas.create_text(
            cx,
            badge_y,
            text="● SCREEN PAIRED",
            font=("Segoe UI", 11, "bold"),
            fill="#4ade80",
            tags="static",
        )

        # Main message
        msg_y = badge_y + 45
        self._canvas.create_text(
            cx,
            msg_y,
            text=self._state_data.get("status", "Memuat Media..."),
            font=("Segoe UI", 20, "bold"),
            fill="#ffffff",
            tags="status_label",
        )

        # Detail message (filename or step)
        detail_y = msg_y + 32
        self._canvas.create_text(
            cx,
            detail_y,
            text=self._state_data.get("detail", "Menyiapkan playlist..."),
            font=("Segoe UI", 13),
            fill="#94a3b8",
            tags="detail_label",
        )

        # Progress bar
        bar_y = detail_y + 35
        bar_w = 480
        bar_h = 8
        pct = self._state_data.get("progress_pct", 0)

        # Progress bar background track
        self._canvas.create_rectangle(
            cx - bar_w // 2,
            bar_y,
            cx + bar_w // 2,
            bar_y + bar_h,
            fill="#1e293b",
            outline="",
            tags="progress_track",
        )

        # Progress bar active fill
        fill_w = int((pct / 100.0) * bar_w)
        if fill_w > 0:
            self._canvas.create_rectangle(
                cx - bar_w // 2,
                bar_y,
                cx - bar_w // 2 + fill_w,
                bar_y + bar_h,
                fill="#38bdf8",
                outline="",
                tags="progress_fill",
            )

        # Percentage text
        self._canvas.create_text(
            cx,
            bar_y + 24,
            text=f"{pct}%",
            font=("Segoe UI", 11, "bold"),
            fill="#38bdf8",
            tags="progress_pct_label",
        )

    def _update_progress_display(self) -> None:
        """Quick canvas item updates for live download progress without full redraw."""
        if self._canvas is None or self._current_state != "LOADING_MEDIA":
            return

        pct = self._state_data.get("progress_pct", 0)
        detail = self._state_data.get("detail", "")
        status = self._state_data.get("status", "Memuat Media...")

        self._canvas.itemconfig("status_label", text=status)
        self._canvas.itemconfig("detail_label", text=detail)
        self._canvas.itemconfig("progress_pct_label", text=f"{pct}%")

        bar_w = 480
        bar_h = 8
        cx = self.target_width // 2
        bar_coords = self._canvas.coords("progress_track")
        if bar_coords and len(bar_coords) == 4:
            by = bar_coords[1]
            fill_w = int((pct / 100.0) * bar_w)
            self._canvas.delete("progress_fill")
            if fill_w > 0:
                self._canvas.create_rectangle(
                    cx - bar_w // 2,
                    by,
                    cx - bar_w // 2 + fill_w,
                    by + bar_h,
                    fill="#38bdf8",
                    outline="",
                    tags="progress_fill",
                )

    def _draw_pairing_screen(self, cx: int, h: int) -> None:
        """Pairing screen shown when device is not yet paired."""
        top_y = 100
        _, lh = self._draw_logo(cx, top_y, tile_size=32, gap=6, max_w=180, max_h=80)

        # Title cleanly below logo
        title_y = (top_y + lh // 2) + 32
        self._canvas.create_text(
            cx,
            title_y,
            text="RaspiDeck",
            font=("Segoe UI", 28, "bold"),
            fill="#f8fafc",
            tags="static",
        )

        # Badge: MENUNGGU PAIRING
        badge_y = title_y + 44
        bw, bh = 220, 32
        self._canvas.create_rectangle(
            cx - bw // 2,
            badge_y - bh // 2,
            cx + bw // 2,
            badge_y + bh // 2,
            fill="#451a03",
            outline="#f59e0b",
            width=2,
            tags="static",
        )
        self._canvas.create_text(
            cx,
            badge_y,
            text="● MENUNGGU PAIRING",
            font=("Segoe UI", 11, "bold"),
            fill="#fbbf24",
            tags="static",
        )

        # Pairing Card Box (widened to 760 and heightened to 210 for plenty of breathing room)
        card_y = badge_y + 145
        card_w, card_h = 760, 210
        self._canvas.create_rectangle(
            cx - card_w // 2,
            card_y - card_h // 2,
            cx + card_w // 2,
            card_y + card_h // 2,
            fill="#0f172a",
            outline="#0284c7",
            width=2,
            tags="static",
        )

        # Card Label
        self._canvas.create_text(
            cx,
            card_y - 66,
            text="KODE PAIRING ANDA",
            font=("Segoe UI", 13, "bold"),
            fill="#38bdf8",
            tags="static",
        )

        # Pairing Code (single space spaced, perfectly centered with generous margins)
        raw_code = self._state_data.get("pairing_code", "------")
        spaced_code = " ".join(list(raw_code.upper()))
        self._canvas.create_text(
            cx,
            card_y + 4,
            text=spaced_code,
            font=("Segoe UI", 48, "bold"),
            fill="#ffffff",
            tags="pairing_code_label",
        )

        # Pulse status
        self._canvas.create_text(
            cx,
            card_y + 68,
            text="Menunggu persetujuan dari dashboard admin web...",
            font=("Segoe UI", 12),
            fill="#94a3b8",
            tags="static",
        )

        # Step-by-step instructions box (matching 760 width)
        steps_y = card_y + 175
        step_w, step_h = 760, 125
        self._canvas.create_rectangle(
            cx - step_w // 2,
            steps_y - step_h // 2,
            cx + step_w // 2,
            steps_y + step_h // 2,
            fill="#0b1120",
            outline="#1e293b",
            width=1,
            tags="static",
        )

        steps = [
            "1. Buka dashboard web admin RaspiDeck di browser Anda",
            "2. Buka menu Layar (Screens) → Hubungkan Layar",
            "3. Masukkan kode 6 karakter di atas untuk memasangkan",
        ]
        for idx, step_text in enumerate(steps):
            self._canvas.create_text(
                cx - step_w // 2 + 35,
                steps_y - 32 + idx * 32,
                text=step_text,
                font=("Segoe UI", 12),
                fill="#cbd5e1",
                anchor="w",
                tags="static",
            )

        # Footer device info
        ip = self._state_data.get("ip_address") or "Mencari IP..."
        srv = self._state_data.get("server_url") or "Local"
        dev = self._state_data.get("device_id") or ""
        footer_text = f"Device ID: {dev}   |   IP: {ip}   |   Server: {srv}"
        self._canvas.create_text(
            cx,
            h - 45,
            text=footer_text,
            font=("Segoe UI", 11),
            fill="#475569",
            tags="static",
        )

    def _draw_waiting_screen(self, cx: int, h: int) -> None:
        """Idle waiting screen when paired but no active playlist is available."""
        mid_y = h // 2 - 50
        logo_y = mid_y - 120
        _, lh = self._draw_logo(cx, logo_y, tile_size=32, gap=6, max_w=180, max_h=80)

        title_y = (logo_y + lh // 2) + 32
        self._canvas.create_text(
            cx,
            title_y,
            text="RaspiDeck",
            font=("Segoe UI", 28, "bold"),
            fill="#f8fafc",
            tags="static",
        )

        # Spinner
        spinner_y = title_y + 75
        self._init_spinner_dots(cx, spinner_y, radius=30.0, num_dots=6)

        # Status text
        status_y = spinner_y + 58
        self._canvas.create_text(
            cx,
            status_y,
            text=self._state_data.get("status", "Menunggu Playlist dari Server..."),
            font=("Segoe UI", 18, "bold"),
            fill="#ffffff",
            tags="status_label",
        )

        self._canvas.create_text(
            cx,
            status_y + 32,
            text=self._state_data.get("detail", "Atur dan tetapkan playlist untuk layar ini melalui dashboard web"),
            font=("Segoe UI", 13),
            fill="#94a3b8",
            tags="status_detail",
        )
