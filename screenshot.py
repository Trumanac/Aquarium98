"""
screenshot.py — headless render → PNG for README / press kit.

Usage:
    python screenshot.py

Outputs:
    docs/screenshot.png   (780 × 500 — day scene, all 8 buttons, open chest)
    docs/screenshot2.png  (780 × 500 — night scene, all 8 buttons, open chest)

Window geometry notes
---------------------
The treasure chest centre is at interior reference (72, 272) in a 448 × 274
reference space — right at the tank floor.  The key to keeping it fully visible
is to use a WIDE window so that the width (not the height) constrains the
uniform scale factor used for sprites.  At 780 × 500:

    tr.w = 780 - 48 - 16  = 716
    tr.h = 500 - 24 - 22  = 454
    rx   = 716 / 448       ≈ 1.598   ← constraining axis
    ry   = 454 / 274       ≈ 1.657
    scale = min(rx, ry)    = 1.598

    chest dw = 90 * 1.598 ≈ 143 px   (very easy to see)
    chest cy = tr.top + 272 * 1.657  ≈ 24 + 451 = 475
    chest sy = 475 - 78              ≈ 397        (well inside 454-px tank)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.environ["SDL_VIDEO_WINDOW_POS"] = "80,80"

import pygame  # noqa: E402

pygame.display.init()
pygame.font.init()

FONT_PATH = str(ROOT / "assets" / "fonts" / "MSW98UI-Regular.otf")
GLOVE_PATH = str(ROOT / "assets" / "sprites" / "ui" / "Glove.png")

# Glove cursor constants (match cursor_manager.py)
_CURSOR_H     = 48
_FRAME_COUNT  = 5
_GLOVE_HOT    = (17, 9)   # measured: topmost finger-tip pixel in scaled sprite

def _load_glove() -> pygame.Surface | None:
    """Load and scale the idle glove cursor frame (frame 0)."""
    try:
        sheet = pygame.image.load(GLOVE_PATH).convert_alpha()
    except Exception:
        return None
    fh = sheet.get_height() // _FRAME_COUNT
    fw = sheet.get_width()
    scale_w = max(1, int(fw * _CURSOR_H / fh))
    frame = sheet.subsurface(pygame.Rect(0, 0, fw, fh)).copy()
    return pygame.transform.smoothscale(frame, (scale_w, _CURSOR_H))


def _blit_cursor(surface: pygame.Surface, cursor: pygame.Surface | None,
                 tip_x: int, tip_y: int) -> None:
    """Blit *cursor* so its hotspot lands at (tip_x, tip_y)."""
    if cursor is None:
        return
    surface.blit(cursor, (tip_x - _GLOVE_HOT[0], tip_y - _GLOVE_HOT[1]))

# ---------------------------------------------------------------------------
# Fish layout — fractions of tank interior (x, y, layer, facing)
# Only common species (no uncommon/rare) so screenshots show the everyday tank.
# Species order matches _FISH_LAYOUT positions for a visually varied composition.
# ---------------------------------------------------------------------------
_FISH_LAYOUT = [
    (0.13, 0.20, 1,  1),   # upper-left
    (0.45, 0.14, 1, -1),   # upper-centre
    (0.72, 0.28, 1,  1),   # upper-right
    (0.25, 0.50, 2, -1),   # mid-left
    (0.58, 0.55, 2,  1),   # mid-centre
    (0.82, 0.48, 2, -1),   # mid-right
    (0.18, 0.78, 3,  1),   # lower-left  (near chest)
    (0.65, 0.82, 3, -1),   # lower-right
]

# Pinned common species names for each layout slot (colorful + varied)
_SCREENSHOT_SPECIES = [
    "Clownfish",   # iconic orange/white
    "RegalTang",   # vivid blue/yellow
    "YellowTang",  # solid bright yellow
    "Goldie",      # warm gold
    "Wrasse",      # teal/pink
    "Cardinal",    # red/white schooler
    "Neon",        # tiny blue/red
    "Catfish",     # bottom-dweller variety
]


def _make_frame(
    width: int,
    height: int,
    *,
    bg: int = 1,
    castle: int = 0,
    night_factor: float = 0.0,
    chest_timer: float = 0.4,          # 0.4 s → near-maximum glow pulse
    status: str = "Aquarium 98  ·  your living Windows 98 desktop fish tank",
    show_roster: bool = False,         # draw the fish roster overlay
    cursor_tip: tuple[int, int] | None = None,  # (x, y) for glove hotspot
) -> tuple[pygame.Surface, list]:
    """Render one frame and return (surface_copy, fish_list)."""
    surface = pygame.display.set_mode((width, height), pygame.NOFRAME)
    pygame.display.set_caption("Aquarium 98")

    font = pygame.font.Font(FONT_PATH, 11)

    from src.renderer import Renderer
    from src.simulation.environment import make_environment
    from src.simulation.fish import make_fish
    from src.simulation.species import SPECIES
    from src.treasure_chest import TreasureChest

    # Build a lookup of common species by name for pinned screenshot fish
    _sp_by_name = {sp["name"]: sp for sp in SPECIES
                   if not sp.get("uncommon") and not sp.get("rare")}

    renderer = Renderer(surface, font)
    renderer.bg_choice = bg
    renderer.castle_choice = castle

    tr = renderer.compute_tank_rect()
    env = make_environment(tr.w, tr.h)
    env.night_factor = night_factor

    # Bubbles — spread gently across the upper half
    for i, b in enumerate(env.bubbles[:14]):
        b.x = float(tr.w * (0.06 + i * 0.07))
        b.y = float(tr.h * (0.10 + (i % 5) * 0.12))
        b.active = True
        b.r = 2 + (i % 4)

    # Fish — staged at the positions defined above, using pinned common species
    fish_list = []
    used_names: set[str] = set()
    for i, (x_f, y_f, layer, facing) in enumerate(_FISH_LAYOUT):
        sp_name = _SCREENSHOT_SPECIES[i % len(_SCREENSHOT_SPECIES)]
        species_dict = _sp_by_name.get(sp_name)   # None → random common
        f = make_fish(
            tr.w, tr.h,
            species=species_dict,
            layer=layer,
            x=float(tr.w * x_f),
            y=float(tr.h * y_f),
            existing_names=used_names,
        )
        # Realistic mid-growth scale matching typical live-game appearance
        _scales = [0.52, 0.48, 0.55, 0.50, 0.45, 0.53, 0.49, 0.51]
        f.scale = _scales[i % len(_scales)]
        f.adult = False
        f.facing = facing
        f.hunger = 0.15
        f.health = 1.0
        # Vary moods so the roster colour dots look interesting
        moods = ["happy", "content", "content", "happy", "stressed",
                 "hungry", "content", "happy"]
        f.mood = moods[len(fish_list) % len(moods)]
        used_names.add(f.name)
        fish_list.append(f)

    # Treasure chest — fully open, maximum glow pulse
    chest = TreasureChest()
    chest.state = "open"
    chest.frame = 7.0
    chest.timer = chest_timer

    stats = {"fish": len(fish_list), "coins": 256}

    renderer.draw(
        fish_list, env,
        paused=False,
        locked=False,
        active=True,
        show_names=False,
        scan_lines=True,
        stats=stats,
        sprite_cache={},
        status_msg=status,
        chest=chest,
    )

    # Optionally draw the fish roster overlay
    if show_roster:
        from src.fish_roster_panel import FishRosterPanel
        roster = FishRosterPanel(font)
        roster.open()
        roster.draw(surface, fish_list, tr, renderer.assets.fish_sheets)

    # Draw the glove cursor on top
    glove = _load_glove()
    if cursor_tip is not None:
        _blit_cursor(surface, glove, cursor_tip[0], cursor_tip[1])

    pygame.display.flip()

    copy = pygame.Surface((width, height))
    copy.blit(surface, (0, 0))
    return copy, fish_list


def _make_menu_screenshot(base: pygame.Surface, width: int, height: int) -> pygame.Surface:
    """Overlay a right-click context menu on top of *base*."""
    import src.config as cfg_mod
    from src.context_menu import ContextMenu, feed_menu

    font = pygame.font.Font(FONT_PATH, 11)
    ctx = ContextMenu(font)

    # Build items with a few checked/toggled states for realism
    items = feed_menu()
    items[0].checked  = False  # not paused
    items[10].checked = False  # not locked
    items[11].checked = False  # not always on top
    items[12].checked = True   # pause when hidden = on
    items[13].checked = False  # show fish names = off

    # Open slightly right-of-centre; ContextMenu auto-flips up if it would overflow
    ctx.open(items, 310, 70, (width, height))
    ctx.hover = 2   # "Feed Fish" highlighted

    copy = pygame.Surface((width, height))
    copy.blit(base, (0, 0))
    ctx.draw(copy)
    # Draw glove cursor to the left of the menu (natural right-click position)
    _blit_cursor(copy, _load_glove(), 295, 105)
    return copy


def _make_settings_screenshot(base: pygame.Surface, width: int, height: int) -> pygame.Surface:
    """Overlay a settings dialog on top of *base*."""
    from src.settings_dialog import SettingsDialog
    import src.config as cfg_mod

    font = pygame.font.Font(FONT_PATH, 11)
    settings = SettingsDialog(font)
    cfg = cfg_mod.load()
    settings.open(cfg, (width, height))

    copy = pygame.Surface((width, height))
    copy.blit(base, (0, 0))
    settings.draw(copy)
    return copy


def main() -> None:
    out_dir = ROOT / "docs"
    out_dir.mkdir(exist_ok=True)

    # 640×400 fits all 8 toolbar buttons (last one is at y=308±18=326 < 400-22=378)
    # and keeps the 1.6:1 game aspect ratio.  Fish are placed at scale ~0.50 which
    # matches what the actual game looks like in a typical session.
    W, H = 640, 400

    # Glove cursor tip coordinates (tip_x, tip_y) in 640×400 space.
    # Tank interior: x=48..624 (w=576), y=24..378 (h=354).
    _DAY_CURSOR   = (460, 185)   # open water, right-centre
    _NIGHT_CURSOR = (390, 165)   # upper-right on night scene

    # --- Screenshot 1: daytime — roster open, glove cursor hovering ---
    s1, _ = _make_frame(W, H, bg=1, castle=0, night_factor=0.0,
                        show_roster=True, cursor_tip=_DAY_CURSOR,
                        status="Aquarium 98  ·  day scene")
    p1 = out_dir / "screenshot.png"
    pygame.image.save(s1, str(p1))
    print(f"Saved → {p1}")

    # --- Screenshot 2: night mode, atmospheric, glove cursor ---
    s2, _ = _make_frame(W, H, bg=2, castle=1, night_factor=0.55,
                        chest_timer=14.8, cursor_tip=_NIGHT_CURSOR,
                        status="Aquarium 98  ·  night scene")
    p2 = out_dir / "screenshot2.png"
    pygame.image.save(s2, str(p2))
    print(f"Saved → {p2}")

    # --- Screenshot 3: right-click context menu ---
    base_day, _ = _make_frame(W, H, bg=1, castle=0, night_factor=0.0,
                              status="Aquarium 98  ·  right-click context menu")
    s3 = _make_menu_screenshot(base_day, W, H)
    p3 = out_dir / "screenshot_menu.png"
    pygame.image.save(s3, str(p3))
    print(f"Saved → {p3}")

    # --- Screenshot 4: settings dialog ---
    s4 = _make_settings_screenshot(base_day, W, H)
    p4 = out_dir / "screenshot_settings.png"
    pygame.image.save(s4, str(p4))
    print(f"Saved → {p4}")

    pygame.quit()
    print("Done.")


if __name__ == "__main__":
    main()
