"""
startup.py — cross-platform auto-start (run on login) helper.

Platform strategies
-------------------
Windows : HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run registry key
          pointing at run.bat.

macOS   : LaunchAgent plist at
          ~/Library/LaunchAgents/com.trumanac.aquarium98.plist
          loaded immediately via `launchctl load`.

Linux   : XDG autostart .desktop file at
          ~/.config/autostart/aquarium98.desktop
          (recognised by GNOME, KDE, XFCE, and most modern DE environments).

All public functions always return a bool (True = success) and are safe
no-ops if they encounter an unexpected error.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_ROOT      = Path(__file__).resolve().parent.parent
_APP_NAME  = "Aquarium98"
_BUNDLE_ID = "com.trumanac.aquarium98"

# Platform-specific launchers (all live next to aquarium.py)
_WIN_LAUNCHER   = _ROOT / "run.bat"
_POSIX_LAUNCHER = _ROOT / "run.sh"

# Windows registry
_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = _APP_NAME

# macOS Launch Agent plist path
_MACOS_PLIST_DIR  = Path.home() / "Library" / "LaunchAgents"
_MACOS_PLIST_PATH = _MACOS_PLIST_DIR / f"{_BUNDLE_ID}.plist"

# Linux XDG autostart path
_XDG_AUTOSTART_DIR  = Path(
    os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
) / "autostart"
_LINUX_DESKTOP_PATH = _XDG_AUTOSTART_DIR / "aquarium98.desktop"


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _win_set(enabled: bool) -> bool:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        if enabled:
            cmd = f'"{_WIN_LAUNCHER}"'
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, cmd)
            log.info("startup: registered '%s' → %s", _REG_NAME, cmd)
        else:
            try:
                winreg.DeleteValue(key, _REG_NAME)
                log.info("startup: removed '%s' from Run key", _REG_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("startup: Windows registry error: %s", exc)
        return False


def _win_check() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, _REG_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------

_MACOS_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{bundle_id}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{launcher}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/aquarium98_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/aquarium98_stderr.log</string>
</dict>
</plist>
"""


def _macos_set(enabled: bool) -> bool:
    try:
        if enabled:
            _MACOS_PLIST_DIR.mkdir(parents=True, exist_ok=True)
            plist_content = _MACOS_PLIST_TEMPLATE.format(
                bundle_id=_BUNDLE_ID,
                launcher=str(_POSIX_LAUNCHER),
            )
            _MACOS_PLIST_PATH.write_text(plist_content, encoding="utf-8")
            # Make the launcher executable
            _POSIX_LAUNCHER.chmod(0o755)
            # Register with launchctl (best-effort — may fail if not on a session)
            subprocess.run(
                ["launchctl", "load", str(_MACOS_PLIST_PATH)],
                check=False, capture_output=True
            )
            log.info("startup: macOS LaunchAgent written → %s", _MACOS_PLIST_PATH)
        else:
            if _MACOS_PLIST_PATH.exists():
                subprocess.run(
                    ["launchctl", "unload", str(_MACOS_PLIST_PATH)],
                    check=False, capture_output=True
                )
                _MACOS_PLIST_PATH.unlink(missing_ok=True)
                log.info("startup: macOS LaunchAgent removed")
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("startup: macOS error: %s", exc)
        return False


def _macos_check() -> bool:
    return _MACOS_PLIST_PATH.exists()


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------

_LINUX_DESKTOP_TEMPLATE = """\
[Desktop Entry]
Type=Application
Name={app_name}
Comment=Your living Windows 98 desktop fish tank
Exec=/bin/bash {launcher}
Icon={icon}
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""


def _linux_set(enabled: bool) -> bool:
    try:
        if enabled:
            _XDG_AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            icon_path = str(_ROOT / "assets" / "icon" / "icon.png")
            desktop_content = _LINUX_DESKTOP_TEMPLATE.format(
                app_name=_APP_NAME,
                launcher=str(_POSIX_LAUNCHER),
                icon=icon_path,
            )
            _LINUX_DESKTOP_PATH.write_text(desktop_content, encoding="utf-8")
            # Make the launcher executable
            _POSIX_LAUNCHER.chmod(0o755)
            log.info("startup: Linux autostart entry written → %s", _LINUX_DESKTOP_PATH)
        else:
            _LINUX_DESKTOP_PATH.unlink(missing_ok=True)
            log.info("startup: Linux autostart entry removed")
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("startup: Linux error: %s", exc)
        return False


def _linux_check() -> bool:
    return _LINUX_DESKTOP_PATH.exists()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_startup(enabled: bool) -> bool:
    """Enable or disable launch-at-login. Returns True on success."""
    if sys.platform == "win32":
        return _win_set(enabled)
    if sys.platform == "darwin":
        return _macos_set(enabled)
    if sys.platform.startswith("linux"):
        return _linux_set(enabled)
    log.debug("startup: unsupported platform '%s', skipping", sys.platform)
    return False


def is_startup_enabled() -> bool:
    """Return True if launch-at-login is currently registered."""
    if sys.platform == "win32":
        return _win_check()
    if sys.platform == "darwin":
        return _macos_check()
    if sys.platform.startswith("linux"):
        return _linux_check()
    return False
