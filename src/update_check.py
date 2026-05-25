"""
update_check.py — Non-blocking background version check against GitHub Releases.

Runs in a daemon thread started once on startup.  All network errors are
swallowed silently — this feature is purely a convenience and must never
affect normal app behaviour.

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
import threading
import urllib.request
from urllib.error import URLError

_RELEASES_URL  = "https://api.github.com/repos/trumanac/Aquarium98/releases/latest"
_GITHUB_PAGE   = "https://github.com/trumanac/Aquarium98/releases"

_result: dict = {}
_lock = threading.Lock()


def start(current_version: str) -> None:
    """Kick off a background version check.  Safe to call multiple times."""
    t = threading.Thread(
        target=_worker,
        args=(current_version,),
        daemon=True,
        name="aquarium-update-check",
    )
    t.start()


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
