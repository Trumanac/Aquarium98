#!/usr/bin/env bash
# ===========================================================
#  Aquarium 98 - Linux/macOS launcher
#  Creates .venv on first run, installs deps, then launches.
#
#  Linux users: system tray needs GTK AppIndicator. If missing:
#    Ubuntu/Debian: sudo apt install libappindicator3-1 gir1.2-appindicator3-0.1
#    Fedora:        sudo dnf install libappindicator-gtk3
#    Arch:          sudo pacman -S libappindicator-gtk3
#  Without it the app still runs but with no tray icon.
# ===========================================================
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "ERROR: python3 is not installed or not on PATH."
    echo "Install Python 3.9+ from https://www.python.org/downloads/"
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Creating virtual environment..."
    "$PY" -m venv .venv
    echo "Installing dependencies..."
    .venv/bin/python -m pip install --upgrade pip >/dev/null
    .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python aquarium.py "$@"
