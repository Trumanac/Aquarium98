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
import aquarium as _game  # noqa: E402


# pygbag requires a callable named `main` in the entry file.
async def main() -> int:
    return await _game.main()


asyncio.run(main())
