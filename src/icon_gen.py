"""
icon_gen.py — icon helper for Aquarium 98.

Provides ensure_icons() which returns the path to the bundled icon.png and,
on macOS, generates icon.icns via iconutil (required by PyInstaller BUNDLE).
icon.png and icon.ico are committed assets and are never regenerated here.
"""
from __future__ import annotations

import sys
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icon"


def ensure_icons() -> Path:
    """Return the icon.png path; generate icon.icns on macOS if not present."""
    png_path = ICON_DIR / "icon.png"

    # In a frozen (PyInstaller) bundle the assets dir is read-only — skip.
    if getattr(sys, "frozen", False):
        return png_path

    icns_path = ICON_DIR / "icon.icns"
    if not icns_path.exists() and sys.platform == "darwin":
        import shutil
        import subprocess
        from PIL import Image
        iconset = ICON_DIR / "icon.iconset"
        iconset.mkdir(exist_ok=True)
        base = Image.open(png_path)
        for s in [16, 32, 128, 256, 512]:
            base.resize((s, s), Image.LANCZOS).save(iconset / f"icon_{s}x{s}.png")
            base.resize((s * 2, s * 2), Image.LANCZOS).save(iconset / f"icon_{s}x{s}@2x.png")
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
            check=True,
        )
        shutil.rmtree(iconset)

    return png_path


if __name__ == "__main__":
    p = ensure_icons()
    print(f"Icon path: {p}")
