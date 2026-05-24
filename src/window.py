"""
window.py — frameless pygame window with Win98 chrome, drag/resize, opacity.

Uses pygame._sdl2.Window for cross-platform always-on-top, opacity, and
window position control (replaces pywin32 — works on Win/macOS/Linux).
"""
from __future__ import annotations

import logging
import os
import platform
import sys
from typing import Callable

import pygame

log = logging.getLogger(__name__)

MIN_W, MIN_H = 384, 366    # MIN_H = last toolbar btn bottom (344) + status bar (22)
MAX_W, MAX_H = 1200, 800   # practical desktop limit
ASPECT = 16 / 10   # actually 8:5 since tank is roughly 4:3 with chrome
# We honor user dragging freely but clamp inside MIN/MAX above.

RESIZE_HANDLE = 20   # bottom-right corner hot-zone size (px)
TITLE_BAR_H = 24


def init_window(cfg: dict) -> tuple[pygame.Surface, object | None, pygame.font.Font]:
    """Initialize pygame window and return (surface, sdl_window_or_None, font)."""
    os.environ.setdefault("SDL_VIDEO_CENTERED", "0")

    pygame.display.init()
    pygame.font.init()

    # Place at saved position via env hint (must be set BEFORE set_mode)
    x = int(cfg.get("window_x", 100))
    y = int(cfg.get("window_y", 100))
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"

    w = max(MIN_W, min(MAX_W, int(cfg.get("window_w", 512))))
    h = max(MIN_H, min(MAX_H, int(cfg.get("window_h", 320))))

    flags = pygame.NOFRAME | pygame.RESIZABLE
    try:
        surface = pygame.display.set_mode((w, h), flags)
    except pygame.error as e:
        log.warning("Falling back to plain window mode: %s", e)
        surface = pygame.display.set_mode((w, h), pygame.NOFRAME)

    pygame.display.set_caption("Aquarium 98")

    # Try to get SDL window handle for opacity / always-on-top
    sdl_win = None
    try:
        from pygame._sdl2 import Window  # type: ignore
        sdl_win = Window.from_display_module()
        try:
            sdl_win.opacity = float(cfg.get("opacity", 1.0))
        except Exception as e:   # noqa: BLE001
            log.debug("opacity unsupported: %s", e)
        try:
            if cfg.get("always_on_top", False):
                sdl_win.always_on_top = True
        except Exception as e:   # noqa: BLE001
            log.debug("always_on_top unsupported: %s", e)
    except Exception as e:   # noqa: BLE001
        log.warning("pygame._sdl2 unavailable: %s", e)

    # Off-screen guard: if saved position is outside all displays, recenter.
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            total_w = sum(s[0] for s in sizes)
            max_h = max(s[1] for s in sizes)
            if x > total_w - 50 or y > max_h - 50 or x < -w + 50 or y < -h + 50:
                log.info("Saved window position off-screen; recentering")
                if sdl_win is not None:
                    try:
                        first = sizes[0]
                        sdl_win.position = ((first[0] - w) // 2, (first[1] - h) // 2)
                    except Exception:   # noqa: BLE001
                        pass
    except Exception:   # noqa: BLE001
        pass

    # Load font (fallback chain)
    font = _load_font()

    # Apply window icon
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon", "icon.png")
        if os.path.exists(icon_path):
            icon = pygame.image.load(icon_path)
            pygame.display.set_icon(icon)
    except Exception as e:   # noqa: BLE001
        log.debug("Window icon set failed: %s", e)

    return surface, sdl_win, font


def _load_font() -> pygame.font.Font:
    from pathlib import Path
    fonts_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    # Try fonts in preference order: new Win98 UI font, then legacy retro.ttf
    for name, size in [("MSW98UI-Regular.otf", 11), ("retro.ttf", 11)]:
        candidate = fonts_dir / name
        if candidate.exists():
            try:
                return pygame.font.Font(str(candidate), size)
            except pygame.error:
                pass
    # SysFont fallback chain — pygame walks the comma-separated list
    return pygame.font.SysFont(
        "tahoma,mssansserif,lucidagrande,dejavusans", 11
    )


def set_opacity(sdl_win, value: float) -> None:
    if sdl_win is None:
        return
    try:
        sdl_win.opacity = max(0.3, min(1.0, float(value)))
    except Exception as e:   # noqa: BLE001
        log.debug("set_opacity failed: %s", e)


def set_always_on_top(sdl_win, on: bool) -> None:
    if sdl_win is None:
        return
    try:
        sdl_win.always_on_top = bool(on)
    except Exception as e:   # noqa: BLE001
        log.debug("set_always_on_top failed: %s", e)


_xlib_display = None  # cached Xlib.display.Display for Linux cursor queries


def _get_xlib_display():
    """Lazily initialise a cached Xlib Display for Linux global cursor queries."""
    global _xlib_display
    if _xlib_display is None:
        try:
            from Xlib import display as _xdisp  # noqa: PLC0415
            _xlib_display = _xdisp.Display()
        except Exception as e:  # noqa: BLE001
            log.debug("Xlib display unavailable (cursor fallback active): %s", e)
            _xlib_display = False  # mark permanently unavailable
    return _xlib_display if _xlib_display else None


def get_screen_cursor() -> tuple[int, int]:
    """Return the cursor position in absolute screen (desktop) coordinates.

    On Windows calls GetCursorPos via ctypes.
    On Linux queries the X11 root window pointer via python-xlib.
    Both avoid the backwards ev.rel feedback loop that causes drag jitter on
    borderless windows.  Falls back to (0, 0) when unavailable (macOS, Wayland).
    """
    _sys = platform.system()
    if _sys == "Windows":
        import ctypes  # noqa: PLC0415
        class _PT(ctypes.Structure):                        # pylint: disable=invalid-name
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = _PT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))  # type: ignore[attr-defined]
        return int(pt.x), int(pt.y)
    if _sys == "Linux":
        d = _get_xlib_display()
        if d is not None:
            try:
                r = d.screen().root.query_pointer()
                return r.root_x, r.root_y
            except Exception:  # noqa: BLE001
                pass
    # macOS / Wayland / fallback
    return (0, 0)


def get_position(sdl_win) -> tuple[int, int] | None:
    if sdl_win is None:
        return None
    try:
        return tuple(sdl_win.position)   # type: ignore[return-value]
    except Exception:   # noqa: BLE001
        return None


def set_position(sdl_win, x: int, y: int) -> None:
    if sdl_win is None:
        return
    try:
        sdl_win.position = (int(x), int(y))
    except Exception as e:   # noqa: BLE001
        log.debug("set_position failed: %s", e)


def resize_surface(w: int, h: int) -> pygame.Surface:
    w = max(MIN_W, min(MAX_W, int(w)))
    h = max(MIN_H, min(MAX_H, int(h)))
    return pygame.display.set_mode((w, h), pygame.NOFRAME | pygame.RESIZABLE)


def in_title_bar(x: int, y: int, w: int, h: int) -> bool:
    return 0 <= x <= w and 0 <= y <= TITLE_BAR_H


def in_resize_handle(x: int, y: int, w: int, h: int) -> bool:
    return (w - RESIZE_HANDLE) <= x <= w and (h - RESIZE_HANDLE) <= y <= h
