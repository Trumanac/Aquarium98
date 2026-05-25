"""
tray.py — system tray icon (pystray) with show/hide/quit. Cross-platform with
graceful no-op fallback when pystray or its platform deps aren't available.

Communicates with the main thread via a thread-safe Queue of action strings.
"""
from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import pystray
    from pystray import Menu, MenuItem
    from PIL import Image
    _AVAILABLE = True
    _IMPORT_ERROR: str | None = None
except Exception as e:   # noqa: BLE001
    log.warning("pystray unavailable: %s", e, exc_info=True)
    pystray = None      # type: ignore
    _AVAILABLE = False
    _IMPORT_ERROR = repr(e)


class Tray:
    """Wraps a pystray.Icon running in a background thread."""

    def __init__(self, icon_path: Path):
        self.actions: queue.Queue[str] = queue.Queue()
        self._icon = None
        self._thread: threading.Thread | None = None
        self._icon_path = icon_path
        self._started = False

    @property
    def available(self) -> bool:
        return _AVAILABLE

    @property
    def started(self) -> bool:
        """True once the tray backend has been started for this process."""
        return self._started

    def start(self) -> None:
        self._started = False
        if not _AVAILABLE:
            log.warning("Tray not available (pystray import failed: %s)", _IMPORT_ERROR)
            return
        try:
            img = Image.open(self._icon_path)
        except Exception as e:   # noqa: BLE001
            log.warning("Tray icon load failed: %s", e, exc_info=True)
            return

        def _on(action: str):
            def _cb(icon, item):
                self.actions.put(action)
            return _cb

        menu = Menu(
            MenuItem("Show Aquarium", _on("show"), default=True),
            MenuItem("Hide Window",   _on("hide")),
            Menu.SEPARATOR,
            MenuItem("Feed Fish",     _on("feed")),
            MenuItem("Pause/Resume",  _on("pause")),
            Menu.SEPARATOR,
            MenuItem("Quit",          _on("quit")),
        )

        try:
            self._icon = pystray.Icon("Aquarium98", img, "Aquarium 98", menu)
        except Exception as e:   # noqa: BLE001
            log.warning("Tray icon init failed: %s", e)
            return

        ready = threading.Event()

        def _setup(icon):
            # CRITICAL: pystray.Icon does NOT call _show() automatically.
            # The icon is only registered with the OS tray when .visible is
            # set to True (which internally calls Shell_NotifyIcon(NIM_ADD)
            # on Windows, the equivalent on macOS/Linux).
            try:
                icon.visible = True
            except Exception as e:   # noqa: BLE001
                log.warning("Tray icon visible=True failed: %s", e, exc_info=True)
            ready.set()

        def _run():
            try:
                self._icon.run(setup=_setup)    # type: ignore[union-attr]
            except Exception as e:   # noqa: BLE001
                log.warning("Tray thread exited: %s", e, exc_info=True)

        self._thread = threading.Thread(target=_run, daemon=True, name="tray")
        self._thread.start()
        self._started = ready.wait(timeout=3.0)
        if not self._started:
            log.warning("Tray backend did not become ready within 3 s; using minimize fallback")
        else:
            log.info("Tray backend ready; icon.visible=%s",
                     getattr(self._icon, "visible", "?"))

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:   # noqa: BLE001
                pass
            self._icon = None
        self._started = False

    def poll(self) -> str | None:
        try:
            return self.actions.get_nowait()
        except queue.Empty:
            return None

    def notify(self, message: str, title: str = "Aquarium 98") -> None:
        """Show a balloon/native notification via pystray (best-effort)."""
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
            except Exception:  # noqa: BLE001
                pass
