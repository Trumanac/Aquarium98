"""
how_to_play_panel.py — Win98-styled "How to Play" / welcome guide.

A multi-page illustrated guide. Auto-shown the very first time the app launches
(detected via cfg["how_to_play_seen"]). Also opens from the right-click menu.

Pages use a mix of:
  - Headed sections with body text
  - Live sprite illustrations pulled from the renderer asset cache
  - Inline icon boxes (coloured Win98-style tiles) for keyboard / mouse hints
  - Sample mini-fish drawn from real fish sheets

Navigation: ◀ Back / Next ▶ buttons + numbered page dots. Esc / X closes.
"""
from __future__ import annotations

from pathlib import Path
import pathlib
from typing import Callable

import pygame

# ── Win98 palette ────────────────────────────────────────────────────────────
WIN_GRAY   = (192, 192, 192)
WIN_LIGHT  = (255, 255, 255)
WIN_DARK   = (64,  64,  64)
WIN_MID    = (128, 128, 128)
TITLE_A    = (0,   0,   128)
TITLE_B    = (16,  132, 208)
PANEL_BG   = (192, 192, 192)
ACCENT     = (16,  132, 208)
WATER_BG   = (28,  70,  130)
WATER_TOP  = (60,  130, 200)
COIN_GOLD  = (240, 200,  60)
COIN_DARK  = (180, 140,  20)
HEART_RED  = (220,  60,  70)
LEAF_GREEN = (60,  170,  90)
SAND_BG    = (210, 180, 130)

# ── Layout constants ─────────────────────────────────────────────────────────
_TB_H      = 18      # title bar
_PAD       = 10
_BTN_W     = 70
_BTN_H     = 22
_FOOTER_H  = 36      # bottom button strip
_DOT_R     = 4       # page-indicator radius


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft, (r.left, r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


def _sunken(surf: pygame.Surface, r: pygame.Rect, fill: tuple = WIN_LIGHT) -> None:
    pygame.draw.rect(surf, fill, r)
    pygame.draw.line(surf, WIN_DARK,  r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, WIN_DARK,  r.topleft, (r.left, r.bottom - 1))
    pygame.draw.line(surf, WIN_LIGHT, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, WIN_LIGHT, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


def _wrap(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    """Word-wrap respecting explicit '\\n' line breaks."""
    out: list[str] = []
    for raw in text.split("\n"):
        words = raw.split()
        if not words:
            out.append("")
            continue
        cur: list[str] = []
        for w in words:
            trial = " ".join(cur + [w])
            if font.size(trial)[0] <= max_w:
                cur.append(w)
            else:
                if cur:
                    out.append(" ".join(cur))
                cur = [w]
        if cur:
            out.append(" ".join(cur))
    return out


def _title_gradient(surf: pygame.Surface, r: pygame.Rect) -> None:
    for i in range(r.h):
        t = i / max(1, r.h - 1)
        c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
             int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
             int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
        pygame.draw.line(surf, c, (r.left, r.top + i), (r.right - 1, r.top + i))


# ── Decorative illustrations ─────────────────────────────────────────────────

def _draw_water_scene(surf: pygame.Surface, r: pygame.Rect) -> None:
    """Pretty mini aquarium: water gradient + sandy floor + drawn castle/plants."""
    pygame.draw.rect(surf, WATER_BG, r)
    # Vertical water gradient
    for i in range(r.h):
        t = i / max(1, r.h - 1)
        c = (int(WATER_TOP[0] + (WATER_BG[0] - WATER_TOP[0]) * t),
             int(WATER_TOP[1] + (WATER_BG[1] - WATER_TOP[1]) * t),
             int(WATER_TOP[2] + (WATER_BG[2] - WATER_TOP[2]) * t))
        pygame.draw.line(surf, c, (r.left, r.top + i), (r.right - 1, r.top + i))
    # Sandy floor
    sand_h = max(6, r.h // 6)
    pygame.draw.rect(surf, SAND_BG, pygame.Rect(r.left, r.bottom - sand_h, r.w, sand_h))
    pygame.draw.line(surf, (170, 140, 90), (r.left, r.bottom - sand_h),
                     (r.right - 1, r.bottom - sand_h))
    _bevel(surf, r, pressed=True)


def _draw_coin(surf: pygame.Surface, cx: int, cy: int, radius: int = 8) -> None:
    pygame.draw.circle(surf, COIN_DARK, (cx, cy), radius)
    pygame.draw.circle(surf, COIN_GOLD, (cx, cy), radius - 1)
    pygame.draw.circle(surf, COIN_DARK, (cx, cy), radius - 1, 1)


def _draw_heart(surf: pygame.Surface, cx: int, cy: int, size: int = 8) -> None:
    pygame.draw.circle(surf, HEART_RED, (cx - size // 2, cy - 1), size // 2)
    pygame.draw.circle(surf, HEART_RED, (cx + size // 2, cy - 1), size // 2)
    pts = [(cx - size, cy), (cx + size, cy), (cx, cy + size)]
    pygame.draw.polygon(surf, HEART_RED, pts)


def _draw_bubble(surf: pygame.Surface, cx: int, cy: int, r: int = 6) -> None:
    pygame.draw.circle(surf, (180, 220, 255), (cx, cy), r, 1)
    pygame.draw.circle(surf, WIN_LIGHT,        (cx - r // 3, cy - r // 3), max(1, r // 3))


def _draw_food_flake(surf: pygame.Surface, cx: int, cy: int) -> None:
    pygame.draw.rect(surf, (220, 160, 60), pygame.Rect(cx - 3, cy - 2, 6, 4))


def _draw_simple_fish(surf: pygame.Surface, cx: int, cy: int,
                      body_color: tuple = (240, 140, 60),
                      facing_right: bool = True) -> None:
    """Tiny clownfish-style icon used in body text."""
    dx = 1 if facing_right else -1
    body = pygame.Rect(cx - 9, cy - 5, 18, 10)
    pygame.draw.ellipse(surf, body_color, body)
    # Tail
    tail_x = body.left if facing_right else body.right
    tip_x = tail_x - 7 * dx
    pygame.draw.polygon(surf, body_color, [
        (tail_x, cy), (tip_x, cy - 5), (tip_x, cy + 5)
    ])
    # White stripe
    pygame.draw.rect(surf, WIN_LIGHT, pygame.Rect(cx - 1, cy - 5, 3, 10))
    # Eye
    eye_x = cx + 5 * dx
    pygame.draw.circle(surf, WIN_LIGHT, (eye_x, cy - 1), 2)
    pygame.draw.circle(surf, (20, 20, 20), (eye_x, cy - 1), 1)


def _draw_chest(surf: pygame.Surface, cx: int, cy: int) -> None:
    body = pygame.Rect(cx - 12, cy - 4, 24, 14)
    lid  = pygame.Rect(cx - 12, cy - 12, 24, 10)
    pygame.draw.rect(surf, (130,  80,  40), body)
    pygame.draw.rect(surf, (160, 100,  50), lid)
    pygame.draw.rect(surf, (220, 180,  60), pygame.Rect(cx - 2, cy - 6, 4, 8))
    pygame.draw.rect(surf, WIN_DARK, body, 1)
    pygame.draw.rect(surf, WIN_DARK, lid, 1)


def _draw_key_cap(surf: pygame.Surface, font: pygame.font.Font,
                  label: str, x: int, y: int,
                  w: int | None = None, h: int = 22) -> pygame.Rect:
    """Draw a Win98 keyboard cap. Returns its rect (for layout flow)."""
    text = font.render(label, True, (0, 0, 0))
    cap_w = w if w is not None else max(22, text.get_width() + 12)
    r = pygame.Rect(x, y, cap_w, h)
    pygame.draw.rect(surf, WIN_GRAY, r)
    _bevel(surf, r)
    surf.blit(text, (r.left + (r.w - text.get_width()) // 2,
                     r.top  + (r.h - text.get_height()) // 2))
    return r


def _draw_mouse(surf: pygame.Surface, x: int, y: int,
                left_active: bool = False, right_active: bool = False) -> pygame.Rect:
    """Tiny mouse icon. Highlights the relevant button."""
    r = pygame.Rect(x, y, 28, 38)
    pygame.draw.rect(surf, WIN_GRAY, r, border_radius=10)
    _bevel(surf, r)
    # Buttons
    lb = pygame.Rect(r.left + 2, r.top + 2, (r.w - 5) // 2, 12)
    rb = pygame.Rect(lb.right + 1, r.top + 2, (r.w - 5) // 2, 12)
    pygame.draw.rect(surf, ACCENT if left_active  else (150, 150, 150), lb)
    pygame.draw.rect(surf, ACCENT if right_active else (150, 150, 150), rb)
    pygame.draw.rect(surf, WIN_DARK, lb, 1)
    pygame.draw.rect(surf, WIN_DARK, rb, 1)
    # Scroll wheel
    pygame.draw.rect(surf, WIN_DARK, pygame.Rect(r.centerx - 1, r.top + 16, 3, 6))
    return r


# ── Real-sprite helpers ───────────────────────────────────────────────────────
_SPRITES_DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "sprites"
_PROJ_DIR    = pathlib.Path(__file__).resolve().parent.parent
_sprite_cache: dict = {}


def _scale_fit(surf, max_w: int, max_h: int):
    """Scale a surface to fit max_w x max_h keeping aspect ratio."""
    import pygame as _pg
    sw, sh = surf.get_size()
    ratio = min(max_w / max(1, sw), max_h / max(1, sh))
    return _pg.transform.smoothscale(surf, (max(1, int(sw * ratio)), max(1, int(sh * ratio))))


def _load_sprite(rel: str, target_size: tuple | None = None) -> "pygame.Surface | None":
    key = f"{rel}@{target_size}"
    if key not in _sprite_cache:
        try:
            import pygame as _pg
            s = _pg.image.load(str(_SPRITES_DIR / rel)).convert_alpha()
            if target_size:
                s = _pg.transform.smoothscale(s, target_size)
        except Exception:
            s = None
        _sprite_cache[key] = s
    return _sprite_cache[key]


def _fish_frame(sheet_name: str, size: tuple) -> "pygame.Surface | None":
    """First frame (top-left cell) of a 3x3 fish spritesheet, scaled to size."""
    key = f"fish_frame:{sheet_name}@{size}"
    if key not in _sprite_cache:
        try:
            import pygame as _pg
            sheet = _pg.image.load(str(_SPRITES_DIR / "fish" / sheet_name)).convert_alpha()
            fw, fh = sheet.get_width() // 3, sheet.get_height() // 3
            frame = sheet.subsurface(_pg.Rect(0, 0, fw, fh)).copy()
            _sprite_cache[key] = _pg.transform.smoothscale(frame, size)
        except Exception:
            _sprite_cache[key] = None
    return _sprite_cache[key]


def _fish_frame_at(sheet_name: str, row: int, col: int, size: tuple) -> "pygame.Surface | None":
    """Specific cell (row, col) of a 3x3 fish spritesheet, scaled to size."""
    key = f"fish_frame_at:{sheet_name}:{row}:{col}@{size}"
    if key not in _sprite_cache:
        try:
            import pygame as _pg
            sheet = _pg.image.load(str(_SPRITES_DIR / "fish" / sheet_name)).convert_alpha()
            fw, fh = sheet.get_width() // 3, sheet.get_height() // 3
            frame = sheet.subsurface(_pg.Rect(col * fw, row * fh, fw, fh)).copy()
            _sprite_cache[key] = _pg.transform.smoothscale(frame, size)
        except Exception:
            _sprite_cache[key] = None
    return _sprite_cache[key]


def _chest_frame(size: tuple) -> "pygame.Surface | None":
    """First frame of the TreasureChest 3x3 spritesheet, scaled to size."""
    key = f"chest_frame@{size}"
    if key not in _sprite_cache:
        try:
            import pygame as _pg
            sheet = _pg.image.load(
                str(_SPRITES_DIR / "decor" / "TreasureChest.png")
            ).convert_alpha()
            fw, fh = sheet.get_width() // 3, sheet.get_height() // 3
            frame = sheet.subsurface(_pg.Rect(0, 0, fw, fh)).copy()
            _sprite_cache[key] = _pg.transform.smoothscale(frame, size)
        except Exception:
            _sprite_cache[key] = None
    return _sprite_cache[key]


def _btn_icon(btn_idx: int, size: tuple) -> "pygame.Surface | None":
    """Extract a toolbar button icon from Buttons.png by index, scaled to size."""
    _DEFS = [
        (59,  284), (350, 276), (633, 269), (909, 251), (1166, 251),
        (1422, 250), (1675, 252), (1930, 251), (2203, 138), (2345, 153), (2504, 98),
    ]
    key = f"btn_icon:{btn_idx}@{size}"
    if key not in _sprite_cache:
        try:
            import pygame as _pg
            sheet = _pg.image.load(
                str(_SPRITES_DIR / "ui" / "Buttons.png")
            ).convert_alpha()
            fy, fh = _DEFS[btn_idx]
            crop = sheet.subsurface(_pg.Rect(42, fy, 298, fh)).copy()
            _sprite_cache[key] = _pg.transform.smoothscale(crop, size)
        except Exception:
            _sprite_cache[key] = None
    return _sprite_cache[key]


# ── Pages ────────────────────────────────────────────────────────────────────
# Each page is (title, draw_fn). draw_fn(surf, body_rect, font) renders inside
# the page area; ``font`` is the dialog''s base font.

def _page_welcome(surf: pygame.Surface, r: pygame.Rect,
                  font: pygame.font.Font) -> None:
    # Banner — official Aquarium 98 splash screen, scaled to fill full width
    banner = pygame.Rect(r.left, r.top, r.w, max(70, r.h // 3))
    try:
        import pygame as _pg
        _sp = _pg.image.load(str(_PROJ_DIR / "assets" / "icon" / "SplashScreen.png")).convert_alpha()
        _sp_w, _sp_h = _sp.get_size()
        # Scale to full panel width; derive height from aspect ratio
        _natural_h = int(r.w * _sp_h / max(1, _sp_w))
        # Banner as tall as the splash image, but never too tall to leave room for text
        _banner_h = max(70, min(_natural_h, r.h - 55))
        banner = pygame.Rect(r.left, r.top, r.w, _banner_h)
        pygame.draw.rect(surf, (18, 50, 90), banner)
        _sp_scaled = _pg.transform.smoothscale(_sp, (r.w, _natural_h))
        # Vertically centre-crop into banner
        _sy = banner.top - max(0, (_natural_h - _banner_h) // 2)
        surf.blit(_sp_scaled, (banner.left, _sy))
    except Exception:
        pygame.draw.rect(surf, WATER_BG, banner)
    _bevel(surf, banner, pressed=True)
    # Body
    body_y = banner.bottom + 10
    lines = _wrap(font,
        "Your tiny Windows 98 desktop fish tank. Fish swim, breed, eat, age, "
        "and pass on naturally — just like the real thing.\n\n"
        "This guide walks you through everything you can do. Use Next ▶ and "
        "◀ Back to flip pages, or press Esc to dive right in.",
        r.w - _PAD)
    for ln in lines:
        ts = font.render(ln, True, (0, 0, 0))
        surf.blit(ts, (r.left + 4, body_y))
        body_y += font.get_height() + 3


def _page_controls(surf: pygame.Surface, r: pygame.Rect,
                   font: pygame.font.Font) -> None:
    # Header
    big = pygame.font.SysFont("ms sans serif,arial", 14, bold=True)
    surf.blit(big.render("Controls at a glance", True, ACCENT),
              (r.left + 4, r.top + 2))

    # Mouse illustration column
    mouse_x = r.left + 16
    mouse_y = r.top + 28
    _draw_mouse(surf, mouse_x, mouse_y, left_active=True)
    surf.blit(font.render("Left-click", True, (0, 0, 0)),
              (mouse_x + 36, mouse_y + 2))
    surf.blit(font.render("Feed / clean / pop bubbles",  True, WIN_DARK),
              (mouse_x + 36, mouse_y + 2 + font.get_height() + 1))

    _draw_mouse(surf, mouse_x, mouse_y + 60, right_active=True)
    surf.blit(font.render("Right-click", True, (0, 0, 0)),
              (mouse_x + 36, mouse_y + 62))
    surf.blit(font.render("Open the action menu anywhere",  True, WIN_DARK),
              (mouse_x + 36, mouse_y + 62 + font.get_height() + 1))

    # Keyboard caps column
    key_y = mouse_y + 130
    captions = [
        ("Space", "Pause / resume the simulation"),
        ("F",     "Feed the fish (drop food)"),
        ("C",     "Clean algae from the glass"),
        ("E",     "Open Settings"),
        ("Esc",   "Minimise to system tray"),
    ]
    for label, desc in captions:
        cap = _draw_key_cap(surf, font, label, r.left + 16, key_y, w=40)
        surf.blit(font.render(desc, True, (0, 0, 0)),
                  (cap.right + 10, key_y + 4))
        key_y += cap.h + 4


def _page_feed_clean(surf: pygame.Surface, r: pygame.Rect,
                     font: pygame.font.Font) -> None:
    big = pygame.font.SysFont("ms sans serif,arial", 14, bold=True)
    surf.blit(big.render("Feeding & cleaning", True, ACCENT),
              (r.left + 4, r.top + 2))

    # Demo: load feed screenshot, scale to fill width preserving aspect ratio.
    # Cap height so there is still room for the text below.
    _demo_w = r.w - 8
    _max_demo_h = r.h - 106   # reserve space for title (22px) + gap + text (~84px)
    _demo_img = None
    try:
        _raw = pygame.image.load(str(_PROJ_DIR / "screenshots" / "screenshot_feed.png")).convert()
        _iw, _ih = _raw.get_size()
        _natural_h = max(1, int(_demo_w * _ih / max(1, _iw)))
        if _natural_h <= _max_demo_h:
            # Image fits — scale to full width, natural height
            _demo_img = pygame.transform.smoothscale(_raw, (_demo_w, _natural_h))
        else:
            # Too tall — crop to top portion (water surface + fish area) then scale
            _src_crop_h = max(1, int(_ih * _max_demo_h / _natural_h))
            _crop = _raw.subsurface(pygame.Rect(0, 0, _iw, min(_src_crop_h, _ih))).copy()
            _demo_img = pygame.transform.smoothscale(_crop, (_demo_w, _max_demo_h))
    except Exception:
        pass
    if _demo_img is None:
        try:
            _raw2 = pygame.image.load(str(_PROJ_DIR / "docs" / "screenshot2.png")).convert()
            _demo_img = _scale_fit(_raw2, _demo_w, _max_demo_h)
        except Exception:
            pass

    _demo_h = _demo_img.get_height() if _demo_img else max(100, _max_demo_h // 2)
    demo = pygame.Rect(r.left + 4, r.top + 22, _demo_w, _demo_h)
    if _demo_img:
        surf.blit(_demo_img, demo.topleft)
    else:
        pygame.draw.rect(surf, WATER_BG, demo)
    _bevel(surf, demo, pressed=True)

    body_y = demo.bottom + 8
    lines = _wrap(font,
        "Press F (or use the toolbar) to scatter food across the surface. "
        "Fish that aren''t hungry ignore it; well-fed fish are happy fish — "
        "and happy fish breed.\n\n"
        "Algae slowly grows on the glass. Press C to scrub it clean. Skip it "
        "too long and your fish will get sick.",
        r.w - _PAD)
    for ln in lines:
        ts = font.render(ln, True, (0, 0, 0))
        surf.blit(ts, (r.left + 4, body_y))
        body_y += font.get_height() + 3


def _page_mood_rarity(surf: pygame.Surface, r: pygame.Rect,
                      font: pygame.font.Font) -> None:
    big = pygame.font.SysFont("ms sans serif,arial", 14, bold=True)
    surf.blit(big.render("Fish Mood & Rarity", True, ACCENT),
              (r.left + 4, r.top + 2))

    y = r.top + 20
    lh = font.get_height() + 5

    # ── Mood section ──────────────────────────────────────────────
    surf.blit(big.render("Mood  (right edge of each fish row)", True, WIN_DARK),
              (r.left + 4, y))
    y += lh + 1
    _MOODS = [
        ((30,  200, 60),  "Happy   ", "well-fed, clean water, low stress"),
        ((220, 200, 40),  "Content ", "normal healthy state"),
        ((220, 60,  60),  "Stressed", "overcrowded or dirty water"),
        ((220, 160, 20),  "Hungry  ", "needs food — health will drop if ignored"),
    ]
    for _col, _lbl, _desc in _MOODS:
        pygame.draw.circle(surf, _col,   (r.left + 10, y + font.get_height() // 2), 6)
        pygame.draw.circle(surf, WIN_DARK,(r.left + 10, y + font.get_height() // 2), 6, 1)
        surf.blit(font.render(f"{_lbl} — {_desc}", True, (0, 0, 0)),
                  (r.left + 22, y))
        y += lh

    y += 10

    # ── Rarity section ──────────────────────────────────────────
    surf.blit(big.render("Rarity  (dot in Fish List & Fish Profile)", True, WIN_DARK),
              (r.left + 4, y))
    y += lh + 1
    _RARITIES = [
        ((160, 160, 160), "Common    ", "seen frequently"),
        ((60,  210, 80),  "Uncommon  ", "appears less often; slightly pricier"),
        ((80,  150, 255), "Rare      ", "hard to find; unlocks an encyclopaedia entry"),
        ((180, 70,  240), "Epic      ", "extremely unusual — check your Event Log!"),
    ]
    for _col, _lbl, _desc in _RARITIES:
        pygame.draw.circle(surf, _col,    (r.left + 10, y + font.get_height() // 2), 6)
        pygame.draw.circle(surf, WIN_DARK, (r.left + 10, y + font.get_height() // 2), 6, 1)
        surf.blit(font.render(f"{_lbl} — {_desc}", True, (0, 0, 0)),
                  (r.left + 22, y))
        y += lh


def _page_coins(surf: pygame.Surface, r: pygame.Rect,
                font: pygame.font.Font) -> None:
    big = pygame.font.SysFont("ms sans serif,arial", 14, bold=True)
    surf.blit(big.render("Coins, treasure & the Fish Shoppe", True, ACCENT),
              (r.left + 4, r.top + 2))

    row_y = r.top + 22
    # Closed chest — frame 0 of TreasureChest.png, aspect-ratio correct, centred
    _ch_fit = None
    try:
        import pygame as _pg
        _cs = _pg.image.load(str(_SPRITES_DIR / "decor" / "TreasureChest.png")).convert_alpha()
        _cfw2, _cfh2 = _cs.get_width() // 3, _cs.get_height() // 3
        _cf0 = _cs.subsurface(pygame.Rect(0, 0, _cfw2, _cfh2)).copy()
        _ch_fit = _scale_fit(_cf0, min(r.w - 16, 130), 60)
        _ch_x = r.left + (r.w - _ch_fit.get_width()) // 2
        surf.blit(_ch_fit, (_ch_x, row_y))
    except Exception:
        pass
    # Gold coins scattered on each side of the chest
    _coin_surf = None
    try:
        import pygame as _pg
        _gc = _pg.image.load(str(_SPRITES_DIR / "ui" / "GoldCoin.png")).convert_alpha()
        _coin_surf = _scale_fit(_gc, 36, 36)
    except Exception:
        pass
    if _coin_surf:
        _cw = _coin_surf.get_width()
        # Left side: 3 coins with slight vertical variation
        for _cx_off, _cy_off in [(-2, 18), (-2 + _cw + 4, 6), (-2 + (_cw + 4) * 2, 22)]:
            surf.blit(_coin_surf, (r.left + 6 + _cx_off, row_y + _cy_off))
        # Right side: 3 coins mirrored
        for _cx_off, _cy_off in [(2, 8), (2 - _cw - 4, 22), (2 - (_cw + 4) * 2, 12)]:
            surf.blit(_coin_surf, (r.right - 6 - _cw + _cx_off, row_y + _cy_off))

    body_y = row_y + 70
    bullets = [
        "Pop bubbles, feed fish, and unlock achievements to earn coins.",
        "A treasure chest appears periodically on the floor — click it!",
        "Spend coins in the Fish Shoppe to buy new species.",
        "Sell unwanted fish back for a partial refund.",
    ]
    for b in bullets:
        # Bullet dot
        pygame.draw.circle(surf, ACCENT, (r.left + 8, body_y + font.get_height() // 2), 2)
        lines = _wrap(font, b, r.w - 20)
        for ln in lines:
            ts = font.render(ln, True, (0, 0, 0))
            surf.blit(ts, (r.left + 16, body_y))
            body_y += font.get_height() + 1
        body_y += 4


def _page_panels(surf: pygame.Surface, r: pygame.Rect,
                 font: pygame.font.Font) -> None:
    big = pygame.font.SysFont("ms sans serif,arial", 14, bold=True)
    surf.blit(big.render("The toolbar panels", True, ACCENT),
              (r.left + 4, r.top + 2))

    items = [
        ("Fish List",    "Live table of every fish — health, hunger, mood.", (120, 180, 230)),
        ("Event Log",    "Timestamped history of births, deaths, feeds…",    (200, 200, 100)),
        ("Achievements", "20+ milestones with coin rewards.",                  (240, 200,  60)),
        ("Encyclopaedia","All species you''ve seen, with fun facts.",         (140, 200, 140)),
        ("Graveyard",    "A memorial for every fish that has passed.",        (180, 150, 200)),
        ("Fish Shoppe",  "Buy new species, sell ones you don''t want.",       (240, 140, 140)),
    ]
    # Button icon indices: 2=roster,3=event_log,4=achievements,5=encyclopedia,6=graveyard,7=store
    _icon_idxs = [2, 3, 4, 5, 6, 7]
    y = r.top + 28
    for (name, desc, _), btn_idx in zip(items, _icon_idxs):
        tile = pygame.Rect(r.left + 4, y, 30, 26)
        pygame.draw.rect(surf, WIN_GRAY, tile)
        _bevel(surf, tile)
        icon = _btn_icon(btn_idx, (tile.w, tile.h))
        if icon:
            surf.blit(icon, tile.topleft)
        # Label + desc
        ns = font.render(name, True, (0, 0, 0))
        ds = font.render(desc, True, WIN_DARK)
        surf.blit(ns, (tile.right + 8, y + 1))
        surf.blit(ds, (tile.right + 8, y + 2 + font.get_height()))
        y += 30


def _page_window(surf: pygame.Surface, r: pygame.Rect,
                 font: pygame.font.Font) -> None:
    big = pygame.font.SysFont("ms sans serif,arial", 14, bold=True)
    surf.blit(big.render("Living on your desktop", True, ACCENT),
              (r.left + 4, r.top + 2))

    # Screenshot crop: top 45% of the actual app (title bar + fish list + tank top)
    win_r = pygame.Rect(r.left + 4, r.top + 24, r.w - 8, 80)
    _win_bg = None
    try:
        import pygame as _pg
        _ss1 = _pg.image.load(str(_PROJ_DIR / "screenshots" / "01_active_tank.png")).convert()
        _sw1, _sh1 = _ss1.get_size()
        _crop_h1 = int(_sh1 * 0.46)
        _win_bg = pygame.transform.smoothscale(
            _ss1.subsurface(pygame.Rect(0, 0, _sw1, _crop_h1)).copy(),
            (win_r.w, win_r.h)
        )
    except Exception:
        pass
    if _win_bg:
        surf.blit(_win_bg, win_r.topleft)
    else:
        pygame.draw.rect(surf, WATER_BG, win_r)
    _bevel(surf, win_r, pressed=True)

    body_y = win_r.bottom + 10
    lines = _wrap(font,
        "Drag the title bar to move the tank anywhere on your desktop. Drag "
        "the bottom-right corner to resize it.\n\n"
        "From the right-click menu you can pin it Always on Top, Lock it in "
        "place so you don''t bump it, adjust Opacity for a ghostly look, or "
        "Minimise to Tray to keep it running quietly in the background.",
        r.w - _PAD)
    for ln in lines:
        ts = font.render(ln, True, (0, 0, 0))
        surf.blit(ts, (r.left + 4, body_y))
        body_y += font.get_height() + 3


def _page_tips(surf: pygame.Surface, r: pygame.Rect,
               font: pygame.font.Font) -> None:
    big = pygame.font.SysFont("ms sans serif,arial", 14, bold=True)
    surf.blit(big.render("Tips for happy fish", True, ACCENT),
              (r.left + 4, r.top + 2))

    # Fish sprite banner — real art from the actual game
    iy = r.top + 20
    _tip_fish = ["Clown_Fish.png", "Betta_Fish.png", "Angel_Fish.png",
                 "Neon_Fish.png", "Puffer_Fish.png"]
    slot_w = (r.w - 8) // len(_tip_fish)
    for _i, _fname in enumerate(_tip_fish):
        # Show fully-puffed puffer (row 2, col 2 = round ball with spines)
        if _fname == "Puffer_Fish.png":
            _fr = _fish_frame_at(_fname, 2, 2, (slot_w - 6, 38))
        else:
            _fr = _fish_frame(_fname, (slot_w - 6, 38))
        if _fr:
            surf.blit(_fr, (r.left + 4 + _i * slot_w + (slot_w - _fr.get_width()) // 2, iy))

    tips = [
        "Feed often — hunger above 85% causes health to slowly decline.",
        "Scrub algae with C before it hits 65% — dirty water stresses all fish.",
        "Avoid overcrowding — a full tank stresses every fish. Leave some space!",
        "Well-fed healthy adults breed automatically — give them food and room.",
        "Toggle fish names and mood dots: right-click → Show Names / Moods.",
        "Rare & Epic fish can't breed true — spot them or buy from the Shoppe.",
        "Change castle and plant style anytime via right-click → Settings.",
    ]
    y = iy + 52
    for t in tips:
        pygame.draw.circle(surf, ACCENT, (r.left + 8, y + font.get_height() // 2), 2)
        lines = _wrap(font, t, r.w - 20)
        for ln in lines:
            surf.blit(font.render(ln, True, (0, 0, 0)), (r.left + 16, y))
            y += font.get_height() + 1
        y += 4

    # Bottom hint
    hint = font.render("Have fun — and remember: you can re-open this guide from the right-click menu.", True, WIN_DARK)
    surf.blit(hint, (r.left + (r.w - hint.get_width()) // 2,
                     r.bottom - hint.get_height() - 2))


def _page_shortcuts(surf: pygame.Surface, r: pygame.Rect,
                    font: pygame.font.Font) -> None:
    """Quick Reference — keyboard shortcuts and mouse controls cheat sheet."""
    big = pygame.font.SysFont("ms sans serif,arial", 14, bold=True)
    surf.blit(big.render("Quick Reference", True, ACCENT),
              (r.left + 4, r.top + 2))

    y    = r.top + 22
    half = r.w // 2
    col2 = r.left + 80   # description column (left-half mouse rows)
    fh   = font.get_height()

    # ----- Keyboard shortcuts (2-column grid, 3 keys per column) -----
    sub = pygame.font.SysFont("ms sans serif,arial", 11, bold=True)
    surf.blit(sub.render("Keyboard", True, WIN_DARK), (r.left + 4, y))
    y += sub.get_height() + 2

    keys_l = [
        ("F",      "Feed fish (toggle)"),
        ("C",      "Clean algae"),
        ("Space",  "Pause / resume"),
    ]
    keys_r = [
        ("E",      "Open Settings"),
        ("Esc",    "Minimise to tray"),
        ("Ctrl+Q", "Quit"),
    ]
    for (lbl_l, desc_l), (lbl_r, desc_r) in zip(keys_l, keys_r):
        cap_l = _draw_key_cap(surf, font, lbl_l, r.left + 4, y)
        surf.blit(font.render(desc_l, True, (0, 0, 0)),
                  (r.left + 4 + cap_l.w + 6, y + 4))
        cap_r = _draw_key_cap(surf, font, lbl_r, r.left + half + 4, y)
        desc_s = font.render(desc_r, True, (0, 0, 0))
        dx = r.left + half + 4 + cap_r.w + 6
        avail = r.right - dx - 2
        surf.blit(desc_s, (dx, y + 4),
                  area=(0, 0, min(desc_s.get_width(), avail), fh))
        y += cap_l.h + 2
    y += 4

    # ----- Mouse controls -----
    surf.blit(sub.render("Mouse", True, WIN_DARK), (r.left + 4, y))
    y += sub.get_height() + 2

    mouse_rows = [
        (True,  False, "Click inside tank",  "Drop food / clean / pop bubbles"),
        (False, True,  "Right-click",        "Open context menu (anywhere)"),
        (False, False, "Drag title bar",     "Move the window"),
        (False, False, "Drag corner",        "Resize the window"),
        (False, False, "Click fish",         "Open fish profile panel"),
    ]
    for left, right, label, desc in mouse_rows:
        if left or right:
            mr = _draw_mouse(surf, r.left + 8, y, left_active=left, right_active=right)
            surf.blit(font.render(label, True, (0, 0, 0)), (col2, y + 2))
            surf.blit(font.render(desc, True, WIN_DARK), (col2, y + 2 + fh + 1))
            y += mr.h + 3
        else:
            lmb = _draw_key_cap(surf, font, "LMB", r.left + 6, y + 2, h=16)
            surf.blit(font.render(f"{label}  \u2014  {desc}", True, (0, 0, 0)), (col2, y + 3))
            y += max(lmb.h, fh) + 5


_PAGES: list[tuple[str, Callable[[pygame.Surface, pygame.Rect, pygame.font.Font], None]]] = [
    ("Welcome",        _page_welcome),
    ("Controls",       _page_controls),
    ("Feed & Clean",   _page_feed_clean),
    ("Fish & Mood",    _page_mood_rarity),
    ("Coins & Shoppe", _page_coins),
    ("Toolbar Panels", _page_panels),
    ("Window & Tray",  _page_window),
    ("Tips",           _page_tips),
    ("Quick Reference", _page_shortcuts),
]


class HowToPlayPanel:
    """Modal, draggable, multi-page illustrated guide."""

    def __init__(self, font: pygame.font.Font):
        self.font = font
        self.visible = False
        self._page = 0
        # Panel size: large enough for art but fits any window via clamping
        self._pw = 420
        self._ph = 360
        self._rect = pygame.Rect(0, 0, self._pw, self._ph)
        # Cached sub-rects
        self._title_bar = pygame.Rect(0, 0, 0, 0)
        self._close_btn = pygame.Rect(0, 0, 0, 0)
        self._back_btn  = pygame.Rect(0, 0, 0, 0)
        self._next_btn  = pygame.Rect(0, 0, 0, 0)
        self._dots: list[pygame.Rect] = []
        self._back_press = False
        self._next_press = False
        self._close_press = False
        # Drag
        self._dragging = False
        self._drag_offset = (0, 0)

    # ------------------------------------------------------------------
    def open(self, screen_w: int, screen_h: int, page: int = 0) -> None:
        self._page = max(0, min(len(_PAGES) - 1, page))
        # Fit within current window with a small margin
        pw = min(self._pw, max(280, screen_w - 20))
        ph = min(self._ph, max(220, screen_h - 20))
        self._rect = pygame.Rect(
            (screen_w - pw) // 2, (screen_h - ph) // 2, pw, ph
        )
        self._layout()
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def toggle(self, screen_w: int, screen_h: int) -> None:
        if self.visible:
            self.close()
        else:
            self.open(screen_w, screen_h)

    # ------------------------------------------------------------------
    def _layout(self) -> None:
        r = self._rect
        self._title_bar = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        # Close X in title bar
        self._close_btn = pygame.Rect(
            self._title_bar.right - _TB_H + 1,
            self._title_bar.top + 1,
            _TB_H - 2, _TB_H - 2,
        )
        # Footer buttons
        fy = r.bottom - _PAD - _BTN_H
        self._back_btn = pygame.Rect(r.left + _PAD, fy, _BTN_W, _BTN_H)
        self._next_btn = pygame.Rect(r.right - _PAD - _BTN_W, fy, _BTN_W, _BTN_H)
        # Page dots centered between buttons
        n = len(_PAGES)
        spacing = 14
        total_w = (n - 1) * spacing
        cx = r.centerx
        cy = fy + _BTN_H // 2
        self._dots = [
            pygame.Rect(cx - total_w // 2 + i * spacing - _DOT_R,
                        cy - _DOT_R, _DOT_R * 2, _DOT_R * 2)
            for i in range(n)
        ]

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event) -> str | None:
        """Returns "closed" when the panel just closed, else None."""
        if not self.visible:
            return None

        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.close(); return "closed"
            if ev.key in (pygame.K_RIGHT, pygame.K_PAGEDOWN, pygame.K_SPACE):
                if self._page < len(_PAGES) - 1:
                    self._page += 1
                else:
                    self.close(); return "closed"
                return None
            if ev.key in (pygame.K_LEFT, pygame.K_PAGEUP, pygame.K_BACKSPACE):
                self._page = max(0, self._page - 1)
                return None
            if ev.key == pygame.K_HOME:
                self._page = 0; return None
            if ev.key == pygame.K_END:
                self._page = len(_PAGES) - 1; return None

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            pos = ev.pos
            if self._close_btn.inflate(8, 8).collidepoint(pos):
                self._close_press = True; return None
            if self._back_btn.collidepoint(pos) and self._page > 0:
                self._back_press = True;  return None
            if self._next_btn.collidepoint(pos):
                self._next_press = True;  return None
            # Click a page dot to jump
            for i, d in enumerate(self._dots):
                # Generous hit area
                hit = d.inflate(8, 8)
                if hit.collidepoint(pos):
                    self._page = i
                    return None
            # Drag from title bar
            if self._title_bar.collidepoint(pos) and not self._close_btn.inflate(8, 8).collidepoint(pos):
                self._dragging = True
                self._drag_offset = (pos[0] - self._rect.left,
                                     pos[1] - self._rect.top)
                return None
            # Click outside panel ⇒ close (modal feel without dimming whole screen)
            if not self._rect.collidepoint(pos):
                self.close(); return "closed"

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            pos = ev.pos
            self._dragging = False
            if self._close_press and self._close_btn.inflate(8, 8).collidepoint(pos):
                self._close_press = False
                self.close(); return "closed"
            if self._back_press and self._back_btn.collidepoint(pos):
                self._back_press = False
                self._page = max(0, self._page - 1)
                return None
            if self._next_press and self._next_btn.collidepoint(pos):
                self._next_press = False
                if self._page < len(_PAGES) - 1:
                    self._page += 1
                else:
                    self.close(); return "closed"
                return None
            self._close_press = self._back_press = self._next_press = False

        if ev.type == pygame.MOUSEMOTION and self._dragging:
            nx = ev.pos[0] - self._drag_offset[0]
            ny = ev.pos[1] - self._drag_offset[1]
            self._rect.topleft = (nx, ny)
            self._layout()

        return None

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        r = self._rect
        fnt = self.font

        # Soft dim of the rest of the window so the guide feels modal
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 80))
        surface.blit(veil, (0, 0))

        # Panel
        pygame.draw.rect(surface, PANEL_BG, r); _bevel(surface, r)

        # Title bar
        _title_gradient(surface, self._title_bar)
        title_label = f"How to Play  —  {_PAGES[self._page][0]}"
        ts = fnt.render(title_label, True, WIN_LIGHT)
        surface.blit(ts, (self._title_bar.left + 6,
                          self._title_bar.top + (self._title_bar.h - ts.get_height()) // 2))

        # Close button — red, Windows-style
        cb = self._close_btn
        close_col = (170, 30, 30) if self._close_press else (200, 40, 40)
        pygame.draw.rect(surface, close_col, cb)
        _bevel(surface, cb, pressed=self._close_press)
        x_lbl = fnt.render("X", True, WIN_LIGHT)
        surface.blit(x_lbl, (cb.left + (cb.w - x_lbl.get_width()) // 2,
                             cb.top  + (cb.h - x_lbl.get_height()) // 2))

        # Page body area
        body = pygame.Rect(
            r.left + _PAD, r.top + _TB_H + _PAD,
            r.w - _PAD * 2, r.h - _TB_H - _PAD * 2 - _FOOTER_H,
        )
        _PAGES[self._page][1](surface, body, fnt)

        # Footer separator
        sep_y = r.bottom - _FOOTER_H
        pygame.draw.line(surface, WIN_DARK,  (r.left + 4,  sep_y),
                         (r.right - 4, sep_y))
        pygame.draw.line(surface, WIN_LIGHT, (r.left + 4,  sep_y + 1),
                         (r.right - 4, sep_y + 1))

        # Back / Next buttons
        back_on = self._page > 0
        for btn, label, pressed, enabled in (
            (self._back_btn, "◀ Back",
                self._back_press, back_on),
            (self._next_btn,
                "Done" if self._page == len(_PAGES) - 1 else "Next ▶",
                self._next_press, True),
        ):
            col = WIN_GRAY if enabled else (210, 210, 210)
            pygame.draw.rect(surface, col, btn)
            _bevel(surface, btn, pressed)
            lc = (0, 0, 0) if enabled else WIN_MID
            ls = fnt.render(label, True, lc)
            surface.blit(ls, (btn.left + (btn.w - ls.get_width()) // 2,
                              btn.top  + (btn.h - ls.get_height()) // 2))

        # Page dots
        for i, d in enumerate(self._dots):
            col = ACCENT if i == self._page else WIN_MID
            pygame.draw.circle(surface, col, d.center, _DOT_R)
            pygame.draw.circle(surface, WIN_DARK, d.center, _DOT_R, 1)
