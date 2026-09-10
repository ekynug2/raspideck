"""Pillow image canvas generator for pairing screen and idle waiting states."""

from __future__ import annotations

from pathlib import Path

from core.config import MEDIA_DIR


def _load_font(size: int):
    """Attempt to load system truetype fonts, fallback to default font."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    for name in ["DejaVuSans-Bold.ttf", "FreeSans.ttf", "arial.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def generate_pairing_image(code: str) -> Path:
    """Generate a 1920x1080 pairing code image and return its file path."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return Path("/dev/null")

    width, height = 1920, 1080
    img = Image.new("RGB", (width, height), (15, 23, 42))  # slate-900
    draw = ImageDraw.Draw(img)

    f_title = _load_font(72)
    f_label = _load_font(32)
    f_code = _load_font(120)
    f_sub = _load_font(24)

    # Title
    bb = draw.textbbox((0, 0), "RaspiDeck", font=f_title)
    draw.text(
        ((width - (bb[2] - bb[0])) // 2, 250),
        "RaspiDeck",
        font=f_title,
        fill=(56, 189, 248),
    )

    # Label
    bb2 = draw.textbbox((0, 0), "Pairing Code", font=f_label)
    draw.text(
        ((width - (bb2[2] - bb2[0])) // 2, 430),
        "Pairing Code",
        font=f_label,
        fill=(148, 163, 184),
    )

    # Code
    bb3 = draw.textbbox((0, 0), code, font=f_code)
    draw.text(
        ((width - (bb3[2] - bb3[0])) // 2, 500),
        code,
        font=f_code,
        fill=(255, 255, 255),
    )

    # Subtitle
    sub = "Enter this code in the web dashboard"
    bb4 = draw.textbbox((0, 0), sub, font=f_sub)
    draw.text(
        ((width - (bb4[2] - bb4[0])) // 2, 720),
        sub,
        font=f_sub,
        fill=(148, 163, 184),
    )

    tmp = MEDIA_DIR / ".pairing.png"
    img.save(str(tmp))
    return tmp


def generate_waiting_image(
    title: str = "RaspiDeck", message: str = "Waiting for Playlist..."
) -> Path:
    """Generate 1920x1080 waiting/idle screen image."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return Path("/dev/null")

    width, height = 1920, 1080
    img = Image.new("RGB", (width, height), (15, 23, 42))  # slate-900
    draw = ImageDraw.Draw(img)

    f_title = _load_font(72)
    f_badge = _load_font(28)
    f_msg = _load_font(38)
    f_sub = _load_font(24)

    # Brand Title
    bb = draw.textbbox((0, 0), title, font=f_title)
    draw.text(
        ((width - (bb[2] - bb[0])) // 2, 280),
        title,
        font=f_title,
        fill=(56, 189, 248),
    )

    # Badge: PAIRED / READY
    badge_text = "SCREEN PAIRED"
    bb_b = draw.textbbox((0, 0), badge_text, font=f_badge)
    bw, bh = bb_b[2] - bb_b[0] + 30, bb_b[3] - bb_b[1] + 16
    bx = (width - bw) // 2
    by = 420
    rect_box = [bx, by, bx + bw, by + bh]
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(
            rect_box,
            radius=8,
            fill=(34, 197, 94, 40),
            outline=(34, 197, 94),
            width=2,
        )
    else:
        draw.rectangle(
            rect_box,
            fill=(34, 197, 94, 40),
            outline=(34, 197, 94),
            width=2,
        )
    draw.text((bx + 15, by + 8), badge_text, font=f_badge, fill=(34, 197, 94))

    # Status Message
    bb_m = draw.textbbox((0, 0), message, font=f_msg)
    draw.text(
        ((width - (bb_m[2] - bb_m[0])) // 2, 540),
        message,
        font=f_msg,
        fill=(255, 255, 255),
    )

    # Subtitle
    sub = "Assign playlist & upload media from web dashboard"
    bb_s = draw.textbbox((0, 0), sub, font=f_sub)
    draw.text(
        ((width - (bb_s[2] - bb_s[0])) // 2, 630),
        sub,
        font=f_sub,
        fill=(148, 163, 184),
    )

    tmp = MEDIA_DIR / ".waiting.png"
    img.save(str(tmp))
    return tmp
