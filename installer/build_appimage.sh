#!/usr/bin/env bash
# installer/build_appimage.sh
# ----------------------------
# Wrap the PyInstaller onedir output in a portable Linux AppImage.
#
# Usage:
#   ./installer/build_appimage.sh [VERSION]
#   VERSION defaults to "1.0.0" if not supplied.
#
# Prerequisites (CI installs these; for local builds):
#   sudo apt-get install file fuse libfuse2
#   appimagetool is downloaded automatically if not on PATH.
#
# Output:
#   dist/Aquarium98-<VERSION>-x86_64.AppImage

set -euo pipefail

VERSION="${1:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$REPO_ROOT/dist/Aquarium98"         # PyInstaller onedir output
APPDIR="$REPO_ROOT/dist/Aquarium98.AppDir"
OUTPUT="$REPO_ROOT/dist/Aquarium98-${VERSION}-x86_64.AppImage"

# ── Sanity check ────────────────────────────────────────────────────────────
if [[ ! -f "$BUILD_DIR/Aquarium98" ]]; then
  echo "ERROR: PyInstaller output not found at $BUILD_DIR/Aquarium98"
  echo "       Run:  pyinstaller aquarium98.spec"
  exit 1
fi

# ── Grab appimagetool ───────────────────────────────────────────────────────
APPIMAGETOOL="$(command -v appimagetool 2>/dev/null || true)"
if [[ -z "$APPIMAGETOOL" ]]; then
  echo ">> appimagetool not found — downloading…"
  APPIMAGETOOL="$REPO_ROOT/dist/appimagetool-x86_64.AppImage"
  curl -fsSL \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
    -o "$APPIMAGETOOL"
  chmod +x "$APPIMAGETOOL"
fi

# ── Build AppDir structure ───────────────────────────────────────────────────
echo ">> Assembling AppDir at $APPDIR"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/aquarium98"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy the entire onedir bundle into usr/share/aquarium98/
cp -r "$BUILD_DIR/"* "$APPDIR/usr/share/aquarium98/"

# Symlink the real executable into usr/bin so AppRun can find it
ln -sr "$APPDIR/usr/share/aquarium98/Aquarium98" "$APPDIR/usr/bin/aquarium98"

# Icon (AppImage spec requires a top-level .png and one under hicolor)
ICON_SRC="$BUILD_DIR/assets/icon/icon.png"
if [[ ! -f "$ICON_SRC" ]]; then
  ICON_SRC="$REPO_ROOT/assets/icon/icon.png"
fi
cp "$ICON_SRC" "$APPDIR/aquarium98.png"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/aquarium98.png"

# .desktop file (AppImage spec requires a top-level one too)
cat > "$APPDIR/aquarium98.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Aquarium 98
Comment=Your living Windows 98 desktop fish tank
Exec=aquarium98
Icon=aquarium98
Terminal=false
Categories=Game;Simulation;
Keywords=fish;aquarium;retro;desktop;
StartupNotify=false
DESKTOP
cp "$APPDIR/aquarium98.desktop" "$APPDIR/usr/share/aquarium98/aquarium98.desktop"

# AppRun entry-point script
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/bash
# AppRun — executed by the AppImage runtime as the entry point
HERE="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
export LD_LIBRARY_PATH="${HERE}/usr/share/aquarium98:${LD_LIBRARY_PATH:-}"
exec "${HERE}/usr/share/aquarium98/Aquarium98" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# ── Package into AppImage ────────────────────────────────────────────────────
echo ">> Running appimagetool…"
# ARCH must be set for appimagetool to produce a correctly-named output
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"

echo ""
echo "✓ AppImage created: $OUTPUT"
echo ""
echo "To distribute:"
echo "  chmod +x $OUTPUT"
echo "  ./$(basename "$OUTPUT")"
echo ""
echo "Optional: generate SHA256 checksum:"
echo "  sha256sum $OUTPUT > $(basename "$OUTPUT").sha256"
