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


def set_window_size(sdl_win, w: int, h: int) -> None:
    """Resize the native OS window without touching the pygame surface.

    This is step-1 of a flash-free resize: it moves the OS window to the new
    size and queues a ``pygame.WINDOWRESIZED`` event, but does NOT call
    ``set_mode()`` or touch the renderer.  The caller should:
      1. Call this function.
      2. Call ``pygame.event.pump()`` to flush the SDL event.
      3. Drain the queued ``WINDOWRESIZED`` via ``pygame.event.get(pygame.WINDOWRESIZED)``.
      4. Call ``resize_surface(w, h)`` — because the SDL window already has the
         target size, ``set_mode()`` only updates the renderer in-place instead
         of recreating the window, so there is no black flash and no grab loss.
    """
    if sdl_win is None:
        return
    w = max(MIN_W, min(MAX_W, int(w)))
    h = max(MIN_H, min(MAX_H, int(h)))
    try:
        sdl_win.size = (w, h)
    except Exception as e:   # noqa: BLE001
        log.debug("set_window_size failed: %s", e)


def resize_surface(w: int, h: int, sdl_win=None) -> pygame.Surface:
    """Resize the pygame display surface to (w, h).

    For a smooth, flash-free resize call ``set_window_size(sdl_win, w, h)``
    first so the SDL window already has the target dimensions.  When
    ``set_mode()`` is called and the SDL window is already at (w, h), SDL2
    updates the renderer backing-store in-place instead of recreating the
    window — eliminating the black-flash and preserving event-grab state.
    """
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


def close_button_rect(w: int, h: int) -> "pygame.Rect":
    """Win98-style close button in the top-right corner of the title bar."""
    return pygame.Rect(w - 21, 4, 18, 16)


def in_close_button(x: int, y: int, w: int, h: int) -> bool:
    return close_button_rect(w, h).inflate(8, 8).collidepoint(x, y)


def in_title_bar(x: int, y: int, w: int, h: int) -> bool:
    # Exclude the close button so clicking it doesn't start a drag.
    return 0 <= x < w and 0 <= y < TITLE_BAR_H and not in_close_button(x, y, w, h)


def in_resize_handle(x: int, y: int, w: int, h: int) -> bool:
    return (w - RESIZE_HANDLE) <= x < w and (h - RESIZE_HANDLE) <= y < h
