"""
icon_gen.py — generate a pixel-art "Aquarium 98" icon via Pillow.

Builds a 256x256 PNG depicting a tiny Win98 window framing a mini aquarium
(blue water, sand, two colorful fish, bubbles), then derives multi-size .ico
(Windows) and .icns (macOS) files.

Only runs if the icon files don't already exist (cached on disk).
"""
from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icon"


def _draw_pixel_fish(draw: ImageDraw.ImageDraw, x: int, y: int,
                     body: tuple[int, int, int], fin: tuple[int, int, int],
                     facing_right: bool = True) -> None:
    """Draw a tiny pixel fish ~24x14 px at (x, y) top-left."""
    d = 1 if facing_right else -1
    ox = x + (12 if not facing_right else 0)

    body_px = [
        (4, 4), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 4), (11, 4),
        (3, 5), (4, 5), (5, 5), (6, 5), (7, 5), (8, 5), (9, 5), (10, 5), (11, 5), (12, 5),
        (3, 6), (4, 6), (5, 6), (6, 6), (7, 6), (8, 6), (9, 6), (10, 6), (11, 6), (12, 6),
        (4, 7), (5, 7), (6, 7), (7, 7), (8, 7), (9, 7), (10, 7), (11, 7),
        (5, 8), (6, 8), (7, 8), (8, 8), (9, 8), (10, 8),
    ]
    fin_px = [(1, 5), (1, 6), (2, 4), (2, 5), (2, 6), (2, 7),
              (0, 4), (0, 7)]
    eye_px = [(10, 5)]
    if not facing_right:
        body_px = [(13 - bx, by) for bx, by in body_px]
        fin_px = [(13 - bx, by) for bx, by in fin_px]
        eye_px = [(13 - bx, by) for bx, by in eye_px]

    for bx, by in body_px:
        draw.point((x + bx, y + by), fill=body)
    for bx, by in fin_px:
        draw.point((x + bx, y + by), fill=fin)
    for bx, by in eye_px:
        draw.point((x + bx, y + by), fill=(20, 20, 20))


def _make_256() -> Image.Image:
    W = H = 256
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Win98 window: gray border + title bar + sunken inset.
    GRAY = (192, 192, 192)
    DARK = (64, 64, 64)
    LIGHT = (255, 255, 255)
    TITLE_DARK = (0, 0, 128)
    TITLE_LIGHT = (64, 128, 200)

    # Outer drop shadow (rounded rect feel via 1-px offset)
    d.rectangle([4, 4, W - 1, H - 1], fill=(0, 0, 0, 100))

    # Window body
    d.rectangle([0, 0, W - 5, H - 5], fill=GRAY)
    # Outer bevel: light top-left, dark bottom-right
    d.line([(0, 0), (W - 5, 0)], fill=LIGHT)
    d.line([(0, 0), (0, H - 5)], fill=LIGHT)
    d.line([(W - 5, 0), (W - 5, H - 5)], fill=DARK)
    d.line([(0, H - 5), (W - 5, H - 5)], fill=DARK)
    # Inner bevel
    d.line([(1, 1), (W - 6, 1)], fill=GRAY)
    d.line([(W - 6, 1), (W - 6, H - 6)], fill=(128, 128, 128))
    d.line([(1, H - 6), (W - 6, H - 6)], fill=(128, 128, 128))

    # Title bar gradient
    tb_top = 3
    tb_h = 30
    for i in range(tb_h):
        t = i / max(1, tb_h - 1)
        r = int(TITLE_DARK[0] * (1 - t) + TITLE_LIGHT[0] * t)
        g = int(TITLE_DARK[1] * (1 - t) + TITLE_LIGHT[1] * t)
        b = int(TITLE_DARK[2] * (1 - t) + TITLE_LIGHT[2] * t)
        d.line([(3, tb_top + i), (W - 8, tb_top + i)], fill=(r, g, b))

    # Title text "98"
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    d.text((10, 5), "Aquarium 98", fill=(255, 255, 255), font=font)

    # Tank interior frame (sunken)
    tank = (10, 40, W - 14, H - 14)
    d.rectangle(tank, fill=(20, 60, 110))
    d.line([(tank[0], tank[1]), (tank[2], tank[1])], fill=DARK)
    d.line([(tank[0], tank[1]), (tank[0], tank[3])], fill=DARK)
    d.line([(tank[2], tank[1]), (tank[2], tank[3])], fill=LIGHT)
    d.line([(tank[0], tank[3]), (tank[2], tank[3])], fill=LIGHT)

    # Water gradient inside tank
    for y in range(tank[1] + 1, tank[3]):
        t = (y - tank[1]) / (tank[3] - tank[1])
        r = int(40 * (1 - t) + 10 * t)
        g = int(110 * (1 - t) + 30 * t)
        b = int(180 * (1 - t) + 70 * t)
        d.line([(tank[0] + 1, y), (tank[2] - 1, y)], fill=(r, g, b))

    # Sand floor
    sand_y = tank[3] - 30
    for y in range(sand_y, tank[3]):
        t = (y - sand_y) / 30
        r = int(196 * (1 - t * 0.3))
        g = int(168 * (1 - t * 0.3))
        b = int(108 * (1 - t * 0.3))
        d.line([(tank[0] + 1, y), (tank[2] - 1, y)], fill=(r, g, b))

    # Scale fish (drawn at base size then upscaled via paste)
    fish_layer = Image.new("RGBA", (28, 18), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fish_layer)
    # Orange clownfish
    _draw_pixel_fish(fd, 0, 0, (255, 140, 30), (255, 255, 255), facing_right=True)
    big_fish = fish_layer.resize((28 * 4, 18 * 4), Image.NEAREST)
    img.paste(big_fish, (60, 95), big_fish)

    fish2_layer = Image.new("RGBA", (28, 18), (0, 0, 0, 0))
    fd2 = ImageDraw.Draw(fish2_layer)
    _draw_pixel_fish(fd2, 0, 0, (40, 90, 220), (255, 220, 40), facing_right=False)
    big_fish2 = fish2_layer.resize((28 * 4, 18 * 4), Image.NEAREST)
    img.paste(big_fish2, (140, 150), big_fish2)

    # Bubbles
    for cx, cy, r in [(200, 70, 5), (210, 95, 4), (195, 115, 3), (90, 80, 4)]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  outline=(220, 240, 255, 220), fill=(180, 220, 255, 80))

    # Plant tuft (simple green strokes)
    for i, x in enumerate([45, 50, 56, 220, 226, 232]):
        d.line([(x, tank[3] - 8), (x + (1 if i % 2 else -1), sand_y - 5)],
               fill=(60, 150, 70), width=2)

    return img


def ensure_icons() -> Path:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    png_path = ICON_DIR / "icon.png"
    ico_path = ICON_DIR / "icon.ico"

    if not png_path.exists():
        img = _make_256()
        img.save(png_path, "PNG")

    if not ico_path.exists():
        base = Image.open(png_path)
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        icons = [base.resize(s, Image.LANCZOS) for s in sizes]
        icons[0].save(ico_path, format="ICO",
                      sizes=[i.size for i in icons], append_images=icons[1:])

    return png_path


if __name__ == "__main__":
    p = ensure_icons()
    print(f"Icon written to {p}")
