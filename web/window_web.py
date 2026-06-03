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
# No hard upper bound for the web — the browser viewport determines the size.
MAX_W, MAX_H   = 7680, 4320
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
    pygame.display.init()
    pygame.font.init()

    # Read the actual browser viewport at startup so the canvas immediately
    # fills the window — no blank-and-resize flash waiting for WINDOWRESIZED.
    w, h = 1280, 720  # safe fallback
    try:
        import platform as _plt
        vw = int(_plt.window.innerWidth)
        vh = int(_plt.window.innerHeight)
        if vw >= MIN_W and vh >= MIN_H:
            w, h = vw, vh
    except Exception:
        w = max(MIN_W, min(MAX_W, int(cfg.get("window_w", 1280))))
        h = max(MIN_H, min(MAX_H, int(cfg.get("window_h", 720))))

    surface = pygame.display.set_mode((w, h))
    pygame.display.set_caption("Aquarium 98")

    # Strip the browser page's default margins/padding so the canvas sits
    # flush at (0, 0) with no scrollbars.
    try:
        import platform as _plt
        _style = _plt.document.createElement("style")
        _style.textContent = (
            "html,body{margin:0;padding:0;overflow:hidden;"
            "width:100%;height:100%;background:#000;}"
            "canvas{display:block;}"
        )
        _plt.document.head.appendChild(_style)
    except Exception:  # noqa: BLE001
        pass

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
    else:
        w = max(MIN_W, int(w))
        h = max(MIN_H, int(h))
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


# ── hit-test functions ────────────────────────────────────────────────────────
def in_close_button(x: int, y: int, w: int, h: int) -> bool:
    return False  # browser handles tab/window close


def in_fullscreen_button(x: int, y: int, w: int, h: int) -> bool:
    return pygame.Rect(w - 40, 4, 18, 16).collidepoint(x, y)


def in_minimize_button(x: int, y: int, w: int, h: int) -> bool:
    return False  # no taskbar in browser


def in_toolbar_toggle_btn(x: int, y: int, w: int, h: int) -> bool:
    return pygame.Rect(3, 4, 14, 16).collidepoint(x, y)


def in_title_bar(x: int, y: int, w: int, h: int) -> bool:
    return False  # no window dragging in browser


def in_resize_handle(x: int, y: int, w: int, h: int) -> bool:
    return False  # browser handles window sizing


def toggle_web_fullscreen() -> None:
    """Toggle the browser's native HTML5 fullscreen via the JS document API."""
    try:
        import platform as _plt
        if _plt.document.fullscreenElement:
            _plt.document.exitFullscreen()
        else:
            _plt.document.documentElement.requestFullscreen()
    except Exception:
        pass
