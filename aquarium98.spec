# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Aquarium 98.

Prerequisites
-------------
    pip install pyinstaller
    pip install -r requirements.txt

    # Run aquarium.py at least once in dev to generate icon files:
    python aquarium.py   (or:  python src/icon_gen.py)

Build (all platforms — run on the TARGET OS):
    pyinstaller aquarium98.spec

Outputs (in dist/):
    dist/Aquarium98/          one-directory bundle (Windows + Linux)
    dist/Aquarium98.app/      macOS .app bundle (macOS only)

Then:
    Windows : wrap dist/Aquarium98/ with Inno Setup (installer/aquarium98.iss)
    Linux   : wrap dist/Aquarium98/ with AppImage   (installer/build_appimage.sh)
    macOS   : wrap dist/Aquarium98.app with DMG     (installer/create_dmg.sh)
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821  (SPECPATH injected by PyInstaller)

block_cipher = None

# ---------------------------------------------------------------------------
# Analysis — discover all imports and collect data files
# ---------------------------------------------------------------------------
a = Analysis(
    [str(ROOT / "aquarium.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Bundle the entire assets tree and the shipped config defaults.
        # At runtime these land in sys._MEIPASS (same relative layout).
        (str(ROOT / "assets"), "assets"),
        (str(ROOT / "config.default.json"), "."),
    ],
    hiddenimports=[
        # pystray dynamically loads its platform backend at runtime.
        # Module names confirmed against installed pystray package structure.
        "pystray._base",
        "pystray._win32",           # Windows tray backend
        "pystray._util.win32",      # Win32 helpers
        "pystray._darwin",          # macOS tray backend
        "pystray._appindicator",    # Linux (libappindicator)
        "pystray._gtk",             # Linux (GTK fallback)
        "pystray._xorg",            # Linux (XOrg fallback)
        "pystray._dummy",           # No-op fallback
        # six is a pystray dependency; six.moves is a virtual package that
        # PyInstaller cannot trace statically — list both explicitly.
        "six",
        "six.moves",
        # Pillow encoders/decoders sometimes missed by the hook
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageOps",
        "PIL.PngImagePlugin",
        "PIL.IcoImagePlugin",
        "PIL.BmpImagePlugin",
    ],
    hookspath=[],
    hooksconfig={
        # Tell PyInstaller's pygame hook to collect all pygame data
        # (fonts, default icon, etc.)
        "pygame": {"collect_data": True},
    },
    runtime_hooks=[],
    # Trim packages that are definitely not used to keep the bundle lean
    excludes=["tkinter", "_tkinter", "matplotlib", "numpy", "scipy",
              "IPython", "notebook", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

# ---------------------------------------------------------------------------
# EXE — the actual executable (kept separate from collected files for onedir)
# ---------------------------------------------------------------------------
_icon = str(
    ROOT / "assets" / "icon" / (
        "icon.icns" if sys.platform == "darwin" else
        "icon.ico"  if sys.platform == "win32"  else
        "icon.png"
    )
)

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],                         # no embedded binaries — those go into COLLECT
    exclude_binaries=True,
    name="Aquarium98",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                   # compress with UPX if available (smaller bundle)
    console=False,              # no terminal window on any platform
    disable_windowed_traceback=False,
    argv_emulation=False,       # macOS: keep False; SDL2 handles its own events
    target_arch=None,
    codesign_identity=None,     # set via env in CI (see build-release.yml)
    entitlements_file=(
        str(ROOT / "installer" / "entitlements.plist")
        if sys.platform == "darwin" else None
    ),
    icon=_icon if Path(_icon).exists() else None,
)

# ---------------------------------------------------------------------------
# COLLECT — gather exe + all dependencies into dist/Aquarium98/
# ---------------------------------------------------------------------------
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Aquarium98",
)

# ---------------------------------------------------------------------------
# BUNDLE — macOS .app wrapper (only generated on macOS)
# ---------------------------------------------------------------------------
if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name="Aquarium98.app",
        icon=str(ROOT / "assets" / "icon" / "icon.icns") if (ROOT / "assets" / "icon" / "icon.icns").exists() else None,
        bundle_identifier="com.trumanac.aquarium98",
        info_plist={
            "CFBundleDisplayName":     "Aquarium 98",
            "CFBundleShortVersionString": "1.0.4",
            "CFBundleVersion":         "1.0.4",
            "NSHighResolutionCapable": True,
            "NSPrincipalClass":        "NSApplication",
            "NSAppleScriptEnabled":    False,
            "LSMinimumSystemVersion":  "10.15.0",
            # Allow the app to be treated as a regular GUI app, not a daemon
            "LSUIElement":             False,
        },
    )
