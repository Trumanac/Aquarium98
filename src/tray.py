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
except Exception as e:   # noqa: BLE001
    log.info("pystray unavailable: %s", e)
    pystray = None      # type: ignore
    _AVAILABLE = False


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
            return
        try:
            img = Image.open(self._icon_path)
        except Exception as e:   # noqa: BLE001
            log.warning("Tray icon load failed: %s", e)
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

        def _run():
            try:
                self._icon.run(setup=lambda _icon: ready.set())    # type: ignore[union-attr]
            except Exception as e:   # noqa: BLE001
                log.warning("Tray thread exited: %s", e)

        self._thread = threading.Thread(target=_run, daemon=True, name="tray")
        self._thread.start()
        self._started = ready.wait(timeout=1.0)
        if not self._started:
            log.warning("Tray backend did not become ready; using minimize fallback")

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
