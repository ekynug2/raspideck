#!/usr/bin/env python3
"""Generate RaspiDeck Windows-style boot splash PNG (1920x1080).

Run on any machine with Pillow:
    pip install Pillow
    python generate_splash.py

Output: splash.png — used for Plymouth boot screen on Raspberry Pi
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
BG_COLOR = (7, 10, 19)  # #070a13 — rich obsidian dark
ACCENT_SKY = (56, 189, 248)  # #38bdf8
ACCENT_BLUE = (96, 165, 250)  # #60a5fa
ACCENT_CYAN = (2, 132, 199)  # #0284c7
ACCENT_ROYAL = (37, 99, 235)  # #2563eb
TEXT_COLOR = (248, 250, 252)  # #f8fafc
DIM_COLOR = (148, 163, 184)  # #94a3b8
MUTED_COLOR = (100, 116, 139)  # #64748b

img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
draw = ImageDraw.Draw(img)


# Try system fonts, fallback to default
def get_font(size: int):
    for name in ["SegoeUI-Bold.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf", "arial.ttf", "FreeSans.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


font_brand = get_font(44)
font_status = get_font(18)
font_sub = get_font(14)

cx = WIDTH // 2
logo_y = HEIGHT // 2 - 90

def find_custom_logo():
    import os
    env_p = os.environ.get("RASPIDECK_LOGO_PATH")
    if env_p and Path(env_p).is_file():
        return Path(env_p)
    for p in [
        Path(__file__).resolve().parent / "logo-badge.png",
        Path(__file__).resolve().parent / "logo.png",
        Path(__file__).resolve().parent / "logo.jpg",
        Path(__file__).resolve().parent / "logo.jpeg",
        Path(__file__).resolve().parent / "logo.webp",
        Path("/opt/raspideck/logo-badge.png"),
        Path("/opt/raspideck/logo.png"),
        Path("/opt/raspideck/logo.jpg"),
        Path("/opt/raspideck/media/logo-badge.png"),
        Path("/opt/raspideck/media/logo.png"),
    ]:
        if p.is_file():
            return p
    return None


custom_logo_path = find_custom_logo()
has_custom_logo = False
logo_bottom = logo_y + 40

if custom_logo_path:
    try:
        c_img = Image.open(str(custom_logo_path))
        w, h = c_img.size
        max_w, max_h = 240, 130
        ratio = min(max_w / w, max_h / h)
        new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", getattr(Image, "ANTIALIAS", 1))
        resized_logo = c_img.resize(new_size, resample)
        lw, lh = resized_logo.size
        px, py = cx - lw // 2, logo_y - lh // 2
        if resized_logo.mode == "RGBA":
            img.paste(resized_logo, (px, py), mask=resized_logo)
        else:
            img.paste(resized_logo, (px, py))
        has_custom_logo = True
        logo_bottom = py + lh
        print(f"Using custom logo: {custom_logo_path} ({lw}x{lh})")
    except Exception as e:
        print(f"Warning loading custom logo: {e}")
        has_custom_logo = False

def draw_round_rect(box, radius, fill):
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(box, radius=radius, fill=fill)
    else:
        draw.rectangle(box, fill=fill)

if not has_custom_logo:
    # 1. Draw Windows-style 4-tile glowing emblem
    tile = 42
    gap = 8
    half = tile + gap // 2

    # Top-Left (Sky)
    draw_round_rect(
        [cx - half, logo_y - half, cx - half + tile, logo_y - half + tile],
        radius=6,
        fill=ACCENT_SKY,
    )
    # Top-Right (Light Blue)
    draw_round_rect(
        [cx + gap // 2, logo_y - half, cx + gap // 2 + tile, logo_y - half + tile],
        radius=6,
        fill=ACCENT_BLUE,
    )
    # Bottom-Left (Cyan)
    draw_round_rect(
        [cx - half, logo_y + gap // 2, cx - half + tile, logo_y + gap // 2 + tile],
        radius=6,
        fill=ACCENT_CYAN,
    )
    # Bottom-Right (Royal Blue)
    draw_round_rect(
        [cx + gap // 2, logo_y + gap // 2, cx + gap // 2 + tile, logo_y + gap // 2 + tile],
        radius=6,
        fill=ACCENT_ROYAL,
    )
    logo_bottom = logo_y + half

# 2. Brand Title
title = "RaspiDeck"
bbox = draw.textbbox((0, 0), title, font=font_brand)
tw = bbox[2] - bbox[0]
title_y = logo_bottom + 38
draw.text(((WIDTH - tw) // 2, title_y), title, fill=TEXT_COLOR, font=font_brand)

# 3. Windows-style Circular Rotating Dots Loader
spinner_y = title_y + 110
r = 36.0
num_dots = 6

# Draw 6 circular dots in an arc resembling the Windows boot spinner
for i in range(num_dots):
    # Orbital arc spacing
    angle = -math.pi / 2.0 + (i * 0.42)
    dx = cx + r * math.cos(angle)
    dy = spinner_y + r * math.sin(angle)
    dot_r = 4.0
    draw.ellipse(
        [dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r],
        fill=(255, 255, 255),
    )

# 4. Status Text
status = "Starting RaspiDeck..."
bbox_st = draw.textbbox((0, 0), status, font=font_status)
sw = bbox_st[2] - bbox_st[0]
draw.text(((WIDTH - sw) // 2, spinner_y + 65), status, fill=TEXT_COLOR, font=font_status)

# Subtitle
sub = "Digital Signage Platform"
bbox_sub = draw.textbbox((0, 0), sub, font=font_sub)
sub_w = bbox_sub[2] - bbox_sub[0]
draw.text(((WIDTH - sub_w) // 2, spinner_y + 98), sub, fill=MUTED_COLOR, font=font_sub)

out_file = Path(__file__).resolve().parent / "splash.png"
img.save(str(out_file))
print(f"Generated Windows-style boot splash: {out_file} ({WIDTH}x{HEIGHT})")

