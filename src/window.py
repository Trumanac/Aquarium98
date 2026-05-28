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

MIN_W, MIN_H = 384, 406    # MIN_H matches config.py floor; absolute UI minimum is 344+22=366 but 406 gives tank breathing room
MAX_W, MAX_H = 1200, 800   # practical desktop limit
ASPECT = 16 / 10   # actually 8:5 since tank is roughly 4:3 with chrome
# We honor user dragging freely but clamp inside MIN/MAX above.

RESIZE_HANDLE = 20   # bottom-right corner hot-zone size (px)
TITLE_BAR_H = 24


def _title_bar_on_screen(x: int, y: int, w: int) -> bool:
    """Return True if the window title bar is accessible on at least one monitor.

    Uses MonitorFromPoint (Windows) which correctly handles any multi-monitor
    layout including monitors to the left (negative X) or stacked vertically.
    Falls back to a generous range check on other platforms.
    """
    cx = x + w // 2   # centre of title bar
    cy = y + 12

    if platform.system() == "Windows":
        try:
            import ctypes
            import ctypes.wintypes
            MONITOR_DEFAULTTONULL = 0
            pt = ctypes.wintypes.POINT(cx, cy)
            return bool(ctypes.windll.user32.MonitorFromPoint(  # type: ignore[attr-defined]
                pt, MONITOR_DEFAULTTONULL))
        except Exception:  # noqa: BLE001
            pass  # fall through to generic check

    # Generic fallback: allow any position within 2× the combined desktop footprint
    # in both directions so left/right/above monitors are not wrongly rejected.
    try:
        sizes = pygame.display.get_desktop_sizes()
        if not sizes:
            return True
        combined_w = sum(s[0] for s in sizes)
        combined_h = sum(s[1] for s in sizes)
        return (
            -combined_w < cx < combined_w * 2
            and -combined_h < cy < combined_h * 2
        )
    except Exception:  # noqa: BLE001
        return True


def init_window(cfg: dict) -> tuple[pygame.Surface, object | None, pygame.font.Font]:
    """Initialize pygame window and return (surface, sdl_window_or_None, font)."""
    os.environ.setdefault("SDL_VIDEO_CENTERED", "0")

    pygame.display.init()
    pygame.font.init()

    x = int(cfg.get("window_x", 100))
    y = int(cfg.get("window_y", 100))
    w = max(MIN_W, min(MAX_W, int(cfg.get("window_w", 512))))
    h = max(MIN_H, min(MAX_H, int(cfg.get("window_h", 320))))

    # SDL_VIDEO_WINDOW_POS is a best-effort hint for the initial set_mode call.
    # We also explicitly set sdl_win.position below, which is authoritative.
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"

    flags = pygame.NOFRAME | pygame.RESIZABLE
    try:
        surface = pygame.display.set_mode((w, h), flags)
    except pygame.error as e:
        log.warning("Falling back to plain window mode: %s", e)
        surface = pygame.display.set_mode((w, h), pygame.NOFRAME)

    pygame.display.set_caption("Aquarium 98")

    # Try to get SDL window handle for opacity / always-on-top / position
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

    # Restore exact saved position via SDL_SetWindowPosition — authoritative,
    # works on any monitor layout (negative X for left monitors, etc.).
    # Fall back to primary-monitor centre only if the title bar would be
    # completely off all screens.
    if sdl_win is not None:
        try:
            if _title_bar_on_screen(x, y, w):
                sdl_win.position = (x, y)
            else:
                log.info("Saved window position off all screens; recentering")
                sizes = pygame.display.get_desktop_sizes()
                pw, ph = sizes[0] if sizes else (1920, 1080)
                sdl_win.position = ((pw - w) // 2, (ph - h) // 2)
        except Exception as e:  # noqa: BLE001
            log.debug("set initial position failed: %s", e)

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


_macos_sdl2_fn = None  # cached SDL_GetGlobalMouseState callable for macOS


def _get_macos_sdl2_fn():
    """Find SDL_GetGlobalMouseState from SDL2 on macOS.

    Searches homebrew paths and the pygame package bundle so it works with
    system, homebrew, and pip-installed pygame-ce on both x86 and arm64.
    Returns a ready-to-call ctypes function or None if SDL2 cannot be found.
    """
    global _macos_sdl2_fn
    if _macos_sdl2_fn is None:
        import ctypes, ctypes.util, os, glob  # noqa: PLC0415
        candidates: list[str] = []
        found = ctypes.util.find_library("SDL2")
        if found:
            candidates.append(found)
        candidates += [
            "/opt/homebrew/lib/libSDL2.dylib",   # arm64 homebrew
            "/usr/local/lib/libSDL2.dylib",       # x86 homebrew
        ]
        # pygame-ce bundles its own SDL2 inside the package directory
        try:
            import pygame as _pg  # noqa: PLC0415
            _pkg = os.path.dirname(_pg.__file__)
            candidates += glob.glob(os.path.join(_pkg, "libSDL2*.dylib"))
            candidates += glob.glob(os.path.join(_pkg, ".dylibs", "libSDL2*.dylib"))
        except Exception:  # noqa: BLE001
            pass
        for name in candidates:
            if not name:
                continue
            try:
                lib = ctypes.CDLL(name)
                fn = lib.SDL_GetGlobalMouseState
                fn.restype = ctypes.c_uint32
                fn.argtypes = [
                    ctypes.POINTER(ctypes.c_int),
                    ctypes.POINTER(ctypes.c_int),
                ]
                # Quick probe to confirm it's callable
                _x, _y = ctypes.c_int(0), ctypes.c_int(0)
                fn(ctypes.byref(_x), ctypes.byref(_y))
                _macos_sdl2_fn = fn
                log.debug("macOS SDL2 cursor: using %s", name)
                break
            except Exception:  # noqa: BLE001
                continue
        if _macos_sdl2_fn is None:
            log.debug("macOS SDL2 cursor unavailable; drag will use rel fallback")
            _macos_sdl2_fn = False  # mark permanently unavailable
    return _macos_sdl2_fn if _macos_sdl2_fn else None


def get_screen_cursor() -> tuple[int, int]:
    """Return the cursor position in absolute screen (desktop) coordinates.

    Windows  — GetCursorPos via ctypes.
    Linux    — X11 root window pointer via python-xlib.
    macOS    — SDL_GetGlobalMouseState via ctypes (from bundled or system SDL2).
    All three avoid the backwards ev.rel feedback loop on borderless windows.
    Falls back to (0, 0) when unavailable (Wayland without X, no SDL2 found).
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
    if _sys == "Darwin":
        import ctypes  # noqa: PLC0415
        fn = _get_macos_sdl2_fn()
        if fn is not None:
            x, y = ctypes.c_int(0), ctypes.c_int(0)
            fn(ctypes.byref(x), ctypes.byref(y))
            return x.value, y.value
    return (0, 0)


def cursor_available() -> bool:
    """Return True if get_screen_cursor() can return real screen coordinates.

    Call once after pygame is initialised to decide whether to use the
    absolute-cursor drag path or the rel-accumulation fallback.
    """
    _sys = platform.system()
    if _sys == "Windows":
        return True
    if _sys == "Linux":
        return _get_xlib_display() is not None
    if _sys == "Darwin":
        return _get_macos_sdl2_fn() is not None
    return False


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


def set_window_size(sdl_win, w: int, h: int, *, clamp: bool = True) -> None:
    """Resize the native OS window without touching the pygame surface.

    Pass ``clamp=False`` for windowed-fullscreen where dimensions may exceed
    the normal MAX_W/MAX_H limits.
    """
    if sdl_win is None:
        return
    if clamp:
        w = max(MIN_W, min(MAX_W, int(w)))
        h = max(MIN_H, min(MAX_H, int(h)))
    try:
        sdl_win.size = (w, h)
    except Exception as e:   # noqa: BLE001
        log.debug("set_window_size failed: %s", e)


def resize_surface(w: int, h: int, sdl_win=None, *, clamp: bool = True) -> pygame.Surface:
    """Resize the pygame display surface to (w, h).

    Pass ``clamp=False`` for windowed-fullscreen where w/h may exceed
    the normal MAX_W/MAX_H limits.
    """
    if clamp:
        w = max(MIN_W, min(MAX_W, int(w)))
        h = max(MIN_H, min(MAX_H, int(h)))
    return pygame.display.set_mode((w, h), pygame.NOFRAME | pygame.RESIZABLE)


def get_sdl_window():
    """Return a fresh SDL Window handle for the current display.

    Must be called after every pygame.display.set_mode() call (including
    resize_surface) because set_mode() recreates the underlying SDL window,
    invalidating any previously held Window object.
    """
    try:
        from pygame._sdl2 import Window  # noqa: PLC0415
        return Window.from_display_module()
    except Exception as e:  # noqa: BLE001
        log.debug("get_sdl_window failed: %s", e)
        return None


def get_monitor_rect_for_window(sdl_win) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) of the monitor that currently contains sdl_win.

    Uses MonitorFromPoint + GetMonitorInfoW on Windows for accuracy across any
    multi-monitor layout (including vertical stacks and negative-X monitors).
    Falls back to estimating via cumulative widths on other platforms.
    """
    pos = get_position(sdl_win)
    px, py = pos if pos else (0, 0)

    if platform.system() == "Windows":
        try:
            import ctypes
            import ctypes.wintypes
            # Use a point near the window's top-left to locate the monitor
            pt = ctypes.wintypes.POINT(px + 60, py + 30)
            MONITOR_DEFAULTTONEAREST = 2
            mon = ctypes.windll.user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)  # type: ignore[attr-defined]

            class _MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize",    ctypes.c_ulong),
                    ("rcMonitor", ctypes.wintypes.RECT),
                    ("rcWork",    ctypes.wintypes.RECT),
                    ("dwFlags",   ctypes.c_ulong),
                ]

            mi = _MONITORINFO()
            mi.cbSize = ctypes.sizeof(_MONITORINFO)
            ctypes.windll.user32.GetMonitorInfoW(mon, ctypes.byref(mi))  # type: ignore[attr-defined]
            r = mi.rcMonitor
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        except Exception:  # noqa: BLE001
            pass  # fall through to generic fallback

    # Generic fallback: assume monitors are arranged left-to-right and find
    # which one the window's left edge falls in.
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            offset = 0
            for sw, sh in sizes:
                if offset <= px < offset + sw:
                    return (offset, 0, sw, sh)
                offset += sw
            # Past the last monitor — use the last one
            return (offset - sizes[-1][0], 0, sizes[-1][0], sizes[-1][1])
    except Exception:  # noqa: BLE001
        pass

    sizes = pygame.display.get_desktop_sizes()
    w, h = sizes[0] if sizes else (1920, 1080)
    return (0, 0, w, h)


def close_button_rect(w: int, h: int) -> "pygame.Rect":
    """Win98-style close button in the top-right corner of the title bar."""
    return pygame.Rect(w - 21, 4, 18, 16)


def fullscreen_button_rect(w: int, h: int) -> pygame.Rect:
    """Win98-style fullscreen/restore button — second from right in the title bar."""
    return pygame.Rect(w - 40, 4, 18, 16)


def minimize_button_rect(w: int, h: int) -> pygame.Rect:
    """Win98-style minimize button — third from right in the title bar."""
    return pygame.Rect(w - 59, 4, 18, 16)


def toolbar_toggle_btn_rect(w: int, h: int) -> pygame.Rect:
    """Toolbar collapse/expand toggle — left of the title bar."""
    return pygame.Rect(3, 4, 14, 16)


def in_close_button(x: int, y: int, w: int, h: int) -> bool:
    return close_button_rect(w, h).inflate(8, 8).collidepoint(x, y)


def in_fullscreen_button(x: int, y: int, w: int, h: int) -> bool:
    return fullscreen_button_rect(w, h).inflate(8, 8).collidepoint(x, y)


def in_minimize_button(x: int, y: int, w: int, h: int) -> bool:
    return minimize_button_rect(w, h).inflate(8, 8).collidepoint(x, y)


def in_toolbar_toggle_btn(x: int, y: int, w: int, h: int) -> bool:
    return toolbar_toggle_btn_rect(w, h).inflate(4, 8).collidepoint(x, y)


def in_title_bar(x: int, y: int, w: int, h: int) -> bool:
    # Exclude all chrome buttons so clicking them doesn't start a drag.
    return (0 <= x < w and 0 <= y < TITLE_BAR_H
            and not in_close_button(x, y, w, h)
            and not in_fullscreen_button(x, y, w, h)
            and not in_minimize_button(x, y, w, h)
            and not in_toolbar_toggle_btn(x, y, w, h))


def in_resize_handle(x: int, y: int, w: int, h: int) -> bool:
    return (w - RESIZE_HANDLE) <= x < w and (h - RESIZE_HANDLE) <= y < h
