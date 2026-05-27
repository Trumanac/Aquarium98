"""
update_check.py — Non-blocking background version check and in-app updater.

Version check runs in a daemon thread started once on startup.  All network
errors are swallowed silently — this feature must never affect normal app
behaviour.

Download/install flow (Windows: Inno Setup installer; macOS: DMG;
Linux: AppImage):
  1. update_check.start(APP_VERSION)      — background API poll
  2. update_check.get_result()            — {"newer": True, "latest": "1.2.0"}
  3. update_check.start_download()        — download installer to temp dir
  4. update_check.get_download_state()    — {"status": "ready", "progress": 1.0}
  5. update_check.launch_installer()      — launch installer, caller should quit

Usage::
    import src.update_check as update_check
    update_check.start("1.0.0")
    ...
    result = update_check.get_result()
    # result == {}                     — check still pending
    # result == {"newer": False, ...}  — already up to date
    # result == {"newer": True, "latest": "1.2.0", "url": "https://..."}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

_RELEASES_URL  = "https://api.github.com/repos/trumanac/Aquarium98/releases/latest"
_GITHUB_PAGE   = "https://github.com/trumanac/Aquarium98/releases"
_DL_BASE       = "https://github.com/trumanac/Aquarium98/releases/download"

_result: dict = {}
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Version check
# ---------------------------------------------------------------------------

def start(current_version: str) -> None:
    """Kick off a background version check.  Safe to call multiple times."""
    t = threading.Thread(
        target=_worker,
        args=(current_version,),
        daemon=True,
        name="aquarium-update-check",
    )
    t.start()


def recheck(current_version: str) -> None:
    """Reset the cached result and re-run the background check."""
    global _result
    with _lock:
        _result = {}
    start(current_version)


def get_result() -> dict:
    """Return a copy of the check result.

    Keys (only present once the check completes):
      ``latest`` — latest release tag without leading 'v', e.g. ``"1.2.0"``
      ``url``    — HTML URL of the release page
      ``newer``  — ``True`` if the latest release is newer than *current_version*
    """
    with _lock:
        return dict(_result)


# ---------------------------------------------------------------------------
# Download & install
# ---------------------------------------------------------------------------

# dl_status values: "idle" | "downloading" | "ready" | "failed"
_dl_state: dict = {"status": "idle", "progress": 0.0, "path": "", "error": ""}
_dl_lock = threading.Lock()


def _asset_name() -> str:
    """Platform-specific installer asset name as published on GitHub Releases."""
    if sys.platform == "win32":
        return "Aquarium98-Setup.exe"
    if sys.platform == "darwin":
        return "Aquarium98.dmg"
    return "Aquarium98-x86_64.AppImage"


def get_download_url() -> str:
    """Return the direct download URL for the latest release on this platform."""
    with _lock:
        latest = _result.get("latest", "")
    if not latest:
        return ""
    return f"{_DL_BASE}/v{latest}/{_asset_name()}"


def get_download_state() -> dict:
    """Return a copy of the current download state dict."""
    with _dl_lock:
        return dict(_dl_state)


def start_download() -> None:
    """Begin downloading the update installer in a background thread.
    No-op if a download is already in progress."""
    url = get_download_url()
    if not url:
        with _dl_lock:
            _dl_state.update({"status": "failed", "error": "No download URL (check not complete)"})
        return
    with _dl_lock:
        if _dl_state["status"] == "downloading":
            return
        _dl_state.update({"status": "downloading", "progress": 0.0, "path": "", "error": ""})
    t = threading.Thread(target=_dl_worker, args=(url,), daemon=True,
                         name="aquarium-updater")
    t.start()


def _dl_worker(url: str) -> None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Aquarium98"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            suffix = Path(url).suffix or ".exe"
            tmp = tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False, prefix="aquarium98_upd_"
            )
            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                tmp.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    with _dl_lock:
                        _dl_state["progress"] = downloaded / total
            tmp.close()
        with _dl_lock:
            _dl_state.update({
                "status": "ready", "progress": 1.0,
                "path": tmp.name, "error": "",
            })
    except Exception as exc:  # noqa: BLE001
        with _dl_lock:
            _dl_state.update({"status": "failed", "error": str(exc)})


def launch_installer() -> bool:
    """Launch the downloaded installer/package.  Returns True if launched.

    On Windows a detached PowerShell helper is also spawned that waits for the
    installer to finish and then restarts the app automatically, so the caller
    just needs to call ``pygame.quit()`` and exit normally.
    """
    with _dl_lock:
        path = _dl_state.get("path", "")
    if not path or not os.path.exists(path):
        return False
    try:
        if sys.platform == "win32":
            # Inno Setup: /SILENT = no wizard UI, /NORESTART = don't reboot PC
            proc = subprocess.Popen(
                [path, "/SILENT", "/NORESTART"],
                creationflags=subprocess.DETACHED_PROCESS,
            )
            _schedule_restart_win32(proc.pid)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            import stat as _stat
            os.chmod(path, os.stat(path).st_mode | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)
            subprocess.Popen([path])
        return True
    except Exception:  # noqa: BLE001
        return False


def _schedule_restart_win32(installer_pid: int) -> None:
    """Spawn a detached PowerShell helper that restarts the app once the
    Inno Setup installer exits.

    The helper runs completely independently of this process:
    1. Waits for the installer (identified by PID) to exit (up to 5 min).
    2. Sleeps 2 s as a safety buffer.
    3. Starts the freshly-installed executable at the same path.

    This is a best-effort feature — any failure is silently ignored so it
    never interferes with the installer launch itself.
    """
    exe = sys.executable  # e.g. C:\\Program Files\\Aquarium98\\aquarium98.exe
    ps = (
        f"Wait-Process -Id {installer_pid} -Timeout 300 -ErrorAction SilentlyContinue; "
        f"Start-Sleep -Seconds 2; "
        f"Start-Process \"{exe}\""
    )
    try:
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
        )
    except Exception:  # noqa: BLE001
        pass  # restart is best-effort; never block the installer launch


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _parse_version(v: str) -> tuple[int, ...]:
    """Convert a semver-ish string to a tuple of ints for comparison."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except (ValueError, AttributeError):
        return (0,)


def _worker(current_version: str) -> None:
    try:
        req = urllib.request.Request(
            _RELEASES_URL,
            headers={
                "User-Agent": "Aquarium98",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
        latest = data.get("tag_name", "").lstrip("v")
        url    = data.get("html_url", _GITHUB_PAGE)
        newer  = _parse_version(latest) > _parse_version(current_version)
        with _lock:
            _result["latest"] = latest
            _result["url"]    = url
            _result["newer"]  = newer
    except Exception:  # noqa: BLE001 — truly want silent failure here
        pass
