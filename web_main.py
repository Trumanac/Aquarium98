"""
web_main.py — pygbag / WebAssembly entry point for Aquarium 98.

Injects lightweight stubs for OS-only integrations (system tray, startup
registration, auto-update checker) and swaps in a browser-safe window
module before any game code is imported.  The normal desktop path
(aquarium.py -> src/window.py etc.) is completely unaffected.

Local dev server (visit http://localhost:8000):
    python -m pygbag --port 8000 web_main.py

Production build (output -> build/web/):
    python -m pygbag --build web_main.py
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))   # exposes window_web.py

# ── inject stubs BEFORE any game module is imported ───────────────────────────

# --- src.tray: no system tray in the browser ---
_tray_mod = types.ModuleType("src.tray")


class _NoopTray:
    available = False
    started   = False

    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def poll(self):
        return None

    def notify(self, *args, **kwargs):
        pass


_tray_mod.Tray = _NoopTray
sys.modules["src.tray"] = _tray_mod

# --- src.startup: no OS startup registration in the browser ---
_startup_mod = types.ModuleType("src.startup")
_startup_mod.is_startup_enabled = lambda: False
_startup_mod.set_startup        = lambda enabled: None
sys.modules["src.startup"] = _startup_mod

# --- src.update_check: no background HTTP checks in the browser ---
_update_mod = types.ModuleType("src.update_check")
_update_mod.start              = lambda version: None
_update_mod.get_result         = lambda: {}
_update_mod.recheck            = lambda version: None
_update_mod.get_download_state = lambda: {"status": "idle", "progress": 0.0, "path": "", "error": ""}
_update_mod.start_download     = lambda: None
_update_mod.launch_installer   = lambda: False
sys.modules["src.update_check"] = _update_mod

# --- src.window: swap in the browser-safe window implementation ---
import window_web as _window_web  # noqa: E402  (from web/ on sys.path above)
sys.modules["src.window"] = _window_web

# --- src.splash: skip the splash screen in the browser ---
_splash_mod = types.ModuleType("src.splash")
_splash_mod.show_splash = lambda: None
sys.modules["src.splash"] = _splash_mod

# --- src.icon_gen: no icon file generation needed in the browser ---
_icon_gen_mod = types.ModuleType("src.icon_gen")
_icon_gen_mod.ensure_icons = lambda: None
sys.modules["src.icon_gen"] = _icon_gen_mod

# ── import and run the game ───────────────────────────────────────────────────
try:
    import aquarium as _game  # noqa: E402
    _IMPORT_ERROR: Exception | None = None
except Exception as _exc:  # noqa: BLE001
    import traceback as _tb
    _IMPORT_ERROR = _exc
    print("FATAL: failed to import aquarium:", _exc)
    print(_tb.format_exc())
    _game = None  # type: ignore[assignment]


# pygbag requires a callable named `main` in the entry file.
async def main() -> int:
    import traceback as _tb
    # Draw a "Starting..." splash immediately so the canvas is not grey.
    print("web: starting — drawing startup splash")
    _render_status("Starting Aquarium 98...")
    await asyncio.sleep(0)   # yield so the canvas updates before heavy init

    if _game is None:
        msg = type(_IMPORT_ERROR).__name__ + ": " + str(_IMPORT_ERROR)
        print("web: import failed:", msg)
        _render_fatal(msg)
        while True:
            await asyncio.sleep(1)

    print("web: calling _game.main()")
    try:
        result = await _game.main()
    except asyncio.CancelledError:
        raise  # let pygbag handle task cancellation normally
    except BaseException as _exc:  # noqa: BLE001 — catch SystemExit, Exception, etc.
        msg = _tb.format_exc()
        print("web: FATAL:", msg)
        _render_fatal(msg)
        while True:
            await asyncio.sleep(1)
        return 1  # unreachable

    # If we reach here the game exited cleanly (return 0/1).
    # Keep showing the canvas so the user sees the last frame; if the screen
    # is grey that means a silent early-exit occurred.
    print(f"web: game exited with code {result}")
    _render_fatal(
        f"Game exited (code {result}).\n\n"
        "This is a bug — please report it.\n\n"
        "Open browser console (F12) for details."
    )
    while True:
        await asyncio.sleep(1)
    return result  # unreachable


def _render_status(message: str) -> None:
    """Draw a simple 'Starting...' splash on the canvas."""
    print("web: _render_status:", message)
    try:
        import pygame as _pg
        _pg.init()  # full init so display + font subsystems are both ready
        surf = _pg.display.get_surface()
        if surf is None:
            surf = _pg.display.set_mode((512, 384))
        surf.fill((0, 0, 128))
        try:
            font = _pg.font.Font(
                str(ROOT / "assets" / "fonts" / "MSW98UI-Regular.otf"), 14
            )
        except Exception:  # noqa: BLE001
            font = _pg.font.SysFont("monospace", 13)
        rendered = font.render(message, True, (255, 255, 255))
        surf.blit(rendered, (20, 20))
        _pg.display.flip()
    except Exception as _e:  # noqa: BLE001
        print("web: _render_status failed:", _e)


def _render_fatal(message: str) -> None:
    """Display a fatal-error traceback on the pygame canvas."""
    print("web: _render_fatal:", message[:400])
    try:
        import pygame as _pg
        _pg.init()  # full init so subsystems are ready
        surf = _pg.display.get_surface()
        if surf is None:
            surf = _pg.display.set_mode((800, 480))
        surf.fill((0, 0, 0))
        try:
            font = _pg.font.Font(
                str(ROOT / "assets" / "fonts" / "MSW98UI-Regular.otf"), 14
            )
        except Exception:  # noqa: BLE001
            font = _pg.font.SysFont("monospace", 13)
        lines = message.splitlines()
        y = 8
        for line in lines[:30]:
            rendered = font.render(line[:100], True, (255, 80, 80))
            surf.blit(rendered, (8, y))
            y += 18
        _pg.display.flip()
    except Exception as _e:  # noqa: BLE001
        print("web: _render_fatal display failed:", _e)


asyncio.run(main())
