"""screenshot_tool.py — Generate README screenshots for Aquarium 98.

Usage:
    python screenshot_tool.py

Saves four PNG files to the  screenshots/  folder in the project root.
No rare or super-rare species are used; no achievements panel is shown.
"""
from __future__ import annotations

import os
import random
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame

from src import window as win_mod
from src.renderer import Renderer
from src.context_menu import ContextMenu, feed_menu
from src.settings_dialog import SettingsDialog
from src.simulation.environment import make_environment
from src.simulation.fish import make_fish
from src.simulation.species import common_species

# ---------------------------------------------------------------------------
WIN_W, WIN_H = 700, 560
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")

# A representative cfg dict for the Settings screenshot
_SETTINGS_CFG = {
    "opacity":          1.0,
    "sound_volume":     0.7,
    "sound_muted":      False,
    "max_bubbles":      12,
    "castle_choice":    1,
    "bg_choice":        1,
    "plant_choice":     1,
    "difficulty":       2,
    "always_on_top":    False,
    "locked":           False,
    "pause_when_hidden": True,
    "scan_lines":       True,
    "show_names":       False,
    "show_moods":       False,
    "open_on_startup":  True,
    "performance_mode": False,
    "stat_total_days":  4.0,
    "stat_total_fish":  22,
    "stat_peak_fish":   11,
    "coins":            317,
}


def _make_fish_list(tank_w: int, tank_h: int, count: int, seed: int) -> list:
    """Create *count* common fish at varied positions with a fixed random seed."""
    rng = random.Random(seed)
    common = common_species()
    # Spread positions across the tank, avoiding the far edges
    xs = [int(tank_w * f) for f in (0.10, 0.25, 0.45, 0.62, 0.78, 0.90,
                                      0.18, 0.55, 0.35, 0.70)]
    ys = [int(tank_h * f) for f in (0.25, 0.55, 0.35, 0.65, 0.20, 0.45,
                                      0.75, 0.30, 0.50, 0.60)]
    layers = [1, 2, 3, 1, 2, 3, 2, 1, 3, 2]

    fish_list = []
    species_pool = common[:]
    for i in range(min(count, len(xs))):
        sp = rng.choice(species_pool)
        x = float(xs[i % len(xs)]) + rng.uniform(-10, 10)
        y = float(ys[i % len(ys)]) + rng.uniform(-8, 8)
        x = max(20.0, min(float(tank_w - 20), x))
        y = max(15.0, min(float(tank_h - 20), y))
        fish_list.append(make_fish(tank_w, tank_h,
                                   species=sp, layer=layers[i % len(layers)],
                                   x=x, y=y))
    return fish_list


def _render(renderer: Renderer, fish_list: list, env,
            *, algae_pct: int = 0, night: float = 0.0,
            scan_lines: bool = True, status: str = "") -> None:
    env.algae = algae_pct
    env.night_factor = night
    stats = {
        "fish":      len(fish_list),
        "algae_pct": algae_pct,
        "coins":     317,
    }
    renderer.draw(
        fish_list, env,
        paused=False, locked=False, active=True,
        show_names=False, show_moods=False, scan_lines=scan_lines,
        encyclopedia_seen=0,
        stats=stats, sprite_cache={},
        status_msg=status, chest=None, coin_popups=[],
    )


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    pygame.init()
    surface = pygame.display.set_mode((WIN_W, WIN_H), pygame.NOFRAME)
    pygame.display.set_caption("Aquarium 98 — screenshot mode")

    font = win_mod._load_font()
    renderer = Renderer(surface, font)
    tr = renderer.compute_tank_rect()
    TW, TH = tr.w, tr.h

    # ── 1. Active Tank ───────────────────────────────────────────────────────
    env1   = make_environment(TW, TH)
    fish1  = _make_fish_list(TW, TH, count=9, seed=42)
    _render(renderer, fish1, env1,
            algae_pct=6, scan_lines=True,
            status="9 fish swimming — ready to explore!")
    path1 = os.path.join(OUT_DIR, "01_active_tank.png")
    pygame.image.save(surface, path1)
    print(f"Saved: {path1}")

    # ── 2. Night Mode ────────────────────────────────────────────────────────
    env2  = make_environment(TW, TH)
    fish2 = _make_fish_list(TW, TH, count=6, seed=17)
    _render(renderer, fish2, env2,
            algae_pct=2, night=0.22, scan_lines=True,
            status="Night mode — the tank dims after hours.")
    path2 = os.path.join(OUT_DIR, "02_night_mode.png")
    pygame.image.save(surface, path2)
    print(f"Saved: {path2}")

    # ── 3. Right-click Context Menu ──────────────────────────────────────────
    env3  = make_environment(TW, TH)
    fish3 = _make_fish_list(TW, TH, count=7, seed=7)
    _render(renderer, fish3, env3, algae_pct=4, scan_lines=True)

    ctx   = ContextMenu(font)
    items = feed_menu()
    for it in items:                        # realistic toggle state
        if it.action == "toggle_phide":
            it.checked = True
    ctx.open(items, 260, 60, (WIN_W, WIN_H))
    ctx.draw(surface)

    path3 = os.path.join(OUT_DIR, "03_context_menu.png")
    pygame.image.save(surface, path3)
    print(f"Saved: {path3}")

    # ── 4. Settings Dialog ───────────────────────────────────────────────────
    env4  = make_environment(TW, TH)
    fish4 = _make_fish_list(TW, TH, count=6, seed=99)
    _render(renderer, fish4, env4, algae_pct=2, scan_lines=True)

    settings = SettingsDialog(font)
    settings.open(_SETTINGS_CFG, (WIN_W, WIN_H))
    settings.draw(surface)

    path4 = os.path.join(OUT_DIR, "04_settings.png")
    pygame.image.save(surface, path4)
    print(f"Saved: {path4}")

    # ── 5. Feed Screenshot (shaker cursor baked in; used by How-to-Play guide) ───────
    env5  = make_environment(TW, TH)
    fish5 = _make_fish_list(TW, TH, count=9, seed=42)
    _render(renderer, fish5, env5, algae_pct=3, scan_lines=True,
            status="")
    # Draw shaker cursor: load Shaker.png sheet, extract frame 0 (idle pose)
    _ui_dir   = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "assets", "sprites", "ui")
    _shaker_p = os.path.join(_ui_dir, "Shaker.png")
    try:
        _sheet = pygame.image.load(_shaker_p)
        try:
            _sheet = _sheet.convert_alpha()
        except Exception:
            _sheet = _sheet.convert()
            _sheet.set_colorkey((255, 255, 255))
        _FRAMES   = 5
        _CURS_H   = 48
        _fh = _sheet.get_height() // _FRAMES
        _fw = _sheet.get_width()
        _sw = max(1, int(_fw * _CURS_H / _fh))
        _frame0 = pygame.transform.smoothscale(
            _sheet.subsurface(pygame.Rect(0, 0, _fw, _fh)).copy(),
            (_sw, _CURS_H)
        )
        # Hotspot for feed mode: (22, 4) = shaker cap top
        # Position cursor so it looks like feeding near the tank surface
        _hx, _hy = 22, 4
        _cx = tr.left + int(TW * 0.62)
        _cy = tr.top  + 10
        surface.blit(_frame0, (_cx - _hx, _cy - _hy))
    except Exception as _e:
        print(f"  Warning: shaker cursor not drawn — {_e}")
    # Crop to tank area only (no chrome) and save alongside other screenshots
    path5 = os.path.join(OUT_DIR, "screenshot_feed.png")
    pygame.image.save(surface.subsurface(tr), path5)
    print(f"Saved: {path5}")

    pygame.quit()
    print(f"\nAll screenshots saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
