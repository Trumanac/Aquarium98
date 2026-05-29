"""
web/window_web.py — Browser-compatible replacement for src/window.py.

Injected into sys.modules["src.window"] by web_main.py before any game
code is imported.  Provides the same public API as the desktop module but:
  - No frameless / always-on-top / opacity (browser canvas cannot do this)
  - No ctypes / platform / SDL2 chrome — just pygame.display
  - All in_*() hit-test functions return False (no window dragging in browser)
  - Chrome *_rect() helpers still return correct positions so tooltips work
    (the renderer draws Win98 chrome purely from its own constants)

Desktop code is completely unaffected — this file is never imported on desktop.
"""
from __future__ import annotations

from pathlib import Path

import pygame

# ── constants (mirror src/window.py exactly) ──────────────────────────────────
MIN_W, MIN_H   = 384, 406
MAX_W, MAX_H   = 1200, 800
ASPECT         = 16 / 10
RESIZE_HANDLE  = 20
TITLE_BAR_H    = 24

_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


# ── font loader (identical logic to desktop) ──────────────────────────────────
def _load_font() -> pygame.font.Font:
    for name, size in [("MSW98UI-Regular.otf", 11), ("retro.ttf", 11)]:
        candidate = _FONTS_DIR / name
        if candidate.exists():
            try:
                return pygame.font.Font(str(candidate), size)
            except pygame.error:
                pass
    return pygame.font.SysFont("tahoma,mssansserif,lucidagrande,dejavusans", 11)


# ── window init ───────────────────────────────────────────────────────────────
def init_window(cfg: dict) -> tuple[pygame.Surface, None, pygame.font.Font]:
    """Create a standard pygame display surface for the browser canvas."""
    w = max(MIN_W, min(MAX_W, int(cfg.get("window_w", 512))))
    h = max(MIN_H, min(MAX_H, int(cfg.get("window_h", 384))))

    pygame.display.init()
    pygame.font.init()

    surface = pygame.display.set_mode((w, h))
    pygame.display.set_caption("Aquarium 98")

    # Set window icon if available (no-op if it fails in WASM)
    try:
        icon_path = _FONTS_DIR.parent / "icon" / "icon.png"
        if icon_path.exists():
            pygame.display.set_icon(pygame.image.load(str(icon_path)))
    except Exception:  # noqa: BLE001
        pass

    font = _load_font()
    return surface, None, font


# ── display surface resize ────────────────────────────────────────────────────
def resize_surface(w: int, h: int, sdl_win=None, *, clamp: bool = True) -> pygame.Surface:
    if clamp:
        w = max(MIN_W, min(MAX_W, int(w)))
        h = max(MIN_H, min(MAX_H, int(h)))
    return pygame.display.set_mode((w, h))


# ── SDL window handle — always None in browser ────────────────────────────────
def get_sdl_window():
    return None


# ── position / size — no-ops in browser ──────────────────────────────────────
def get_position(sdl_win) -> tuple[int, int] | None:
    return (0, 0)


def set_position(sdl_win, x: int, y: int) -> None:
    pass


def set_window_size(sdl_win, w: int, h: int, *, clamp: bool = True) -> None:
    pass


# ── opacity / always-on-top — no-ops in browser ───────────────────────────────
def set_opacity(sdl_win, value: float) -> None:
    pass


def set_always_on_top(sdl_win, on: bool) -> None:
    pass


# ── cursor ────────────────────────────────────────────────────────────────────
def cursor_available() -> bool:
    """Browser cannot supply absolute screen coords; use rel-accumulation path."""
    return False


def get_screen_cursor() -> tuple[int, int]:
    """Return canvas-relative cursor position as a fallback."""
    return pygame.mouse.get_pos()


# ── monitor rect ──────────────────────────────────────────────────────────────
def get_monitor_rect_for_window(sdl_win) -> tuple[int, int, int, int]:
    surf = pygame.display.get_surface()
    if surf is not None:
        w, h = surf.get_size()
    else:
        w, h = 512, MIN_H
    return (0, 0, w, h)


# ── chrome button rects (same values as desktop so tooltips align correctly) ──
def close_button_rect(w: int, h: int) -> pygame.Rect:
    return pygame.Rect(w - 21, 4, 18, 16)


def fullscreen_button_rect(w: int, h: int) -> pygame.Rect:
    return pygame.Rect(w - 40, 4, 18, 16)


def minimize_button_rect(w: int, h: int) -> pygame.Rect:
    return pygame.Rect(w - 59, 4, 18, 16)


def toolbar_toggle_btn_rect(w: int, h: int) -> pygame.Rect:
    return pygame.Rect(3, 4, 14, 16)


# ── hit-test functions — all False; window chrome is non-interactive in browser
def in_close_button(x: int, y: int, w: int, h: int) -> bool:
    return False


def in_fullscreen_button(x: int, y: int, w: int, h: int) -> bool:
    return False


def in_minimize_button(x: int, y: int, w: int, h: int) -> bool:
    return False


def in_toolbar_toggle_btn(x: int, y: int, w: int, h: int) -> bool:
    return False


def in_title_bar(x: int, y: int, w: int, h: int) -> bool:
    return False


def in_resize_handle(x: int, y: int, w: int, h: int) -> bool:
    return False
