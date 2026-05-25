#!/usr/bin/env bash
# installer/create_dmg.sh
# -----------------------
# Package Aquarium98.app into a distributable DMG for macOS.
#
# Usage:
#   ./installer/create_dmg.sh [VERSION]
#   VERSION defaults to "1.0.0" if not supplied.
#
# Prerequisites:
#   - PyInstaller has already produced  dist/Aquarium98.app
#   - hdiutil  (ships with macOS — no install needed)
#   - create-dmg  (optional but produces prettier DMGs):
#       brew install create-dmg
#
# Output:
#   dist/Aquarium98-<VERSION>.dmg
#
# Code signing notes
# ------------------
# Ad-hoc signing  (default, free):
#   `codesign --force --deep --sign -` stamps a self-derived identity.
#   This suppresses the "damaged app, move to Trash" Gatekeeper error.
#   Users still see "unidentified developer" on first launch.
#   Workaround: right-click → Open  OR  xattr -dr com.apple.quarantine
#
# Apple Developer ID signing  (optional, $99/yr):
#   Set the CODESIGN_IDENTITY env var to your Developer ID string, e.g.:
#     export CODESIGN_IDENTITY="Developer ID Application: Your Name (XXXXXXXXXX)"
#   Then also notarise:
#     xcrun notarytool submit Aquarium98-1.0.0.dmg \
#       --apple-id "$APPLE_ID" --team-id "$TEAM_ID" --password "$APP_PASS" --wait
#     xcrun stapler staple Aquarium98-1.0.0.dmg

set -euo pipefail

VERSION="${1:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
APP_BUNDLE="$REPO_ROOT/dist/Aquarium98.app"
OUTPUT="$REPO_ROOT/dist/Aquarium98-${VERSION}.dmg"
IDENTITY="${CODESIGN_IDENTITY:--}"   # default: ad-hoc (-)

# ── Sanity check ─────────────────────────────────────────────────────────────
if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "ERROR: .app bundle not found at $APP_BUNDLE"
  echo "       Run:  pyinstaller aquarium98.spec"
  exit 1
fi

# ── Code-sign the app bundle ──────────────────────────────────────────────────
echo ">> Code-signing $APP_BUNDLE with identity: ${IDENTITY}"
codesign \
  --force \
  --deep \
  --sign "$IDENTITY" \
  --options runtime \
  "$APP_BUNDLE"

echo ">> Verifying signature…"
codesign --verify --verbose "$APP_BUNDLE" && echo "   Signature OK"

# ── Create DMG ────────────────────────────────────────────────────────────────
rm -f "$OUTPUT"

if command -v create-dmg &>/dev/null; then
  # Pretty DMG with background, icon layout, and /Applications shortcut
  echo ">> Using create-dmg…"
  create-dmg \
    --volname "Aquarium 98 ${VERSION}" \
    --volicon "$REPO_ROOT/assets/icon/icon.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 128 \
    --icon "Aquarium98.app" 160 185 \
    --hide-extension "Aquarium98.app" \
    --app-drop-link 430 185 \
    --no-internet-enable \
    "$OUTPUT" \
    "$APP_BUNDLE"
else
  # Fallback: plain hdiutil DMG (no Finder styling, but always available)
  echo ">> create-dmg not found — using plain hdiutil (install 'brew install create-dmg' for a prettier DMG)"
  STAGING="$REPO_ROOT/dist/_dmg_staging"
  rm -rf "$STAGING"
  mkdir -p "$STAGING"
  cp -r "$APP_BUNDLE" "$STAGING/"
  ln -s /Applications "$STAGING/Applications"
  hdiutil create \
    -volname "Aquarium 98 ${VERSION}" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$OUTPUT"
  rm -rf "$STAGING"
fi

# ── Also sign the DMG itself (ad-hoc or Developer ID) ────────────────────────
echo ">> Signing DMG: $OUTPUT"
codesign --force --sign "$IDENTITY" "$OUTPUT"

echo ""
echo "✓ DMG created: $OUTPUT"
echo ""
echo "─────────────────────────────────────────────────────────────"
echo "macOS distribution notes"
echo "─────────────────────────────────────────────────────────────"
echo ""
echo "Ad-hoc signed (no Apple Developer account):"
echo "  • Users will see 'unidentified developer' on first launch."
echo "  • Fix: right-click the app → Open   (or tell users to run):"
echo "      xattr -dr com.apple.quarantine /Applications/Aquarium98.app"
echo ""
echo "For full Gatekeeper clearance (no warnings, no workarounds):"
echo "  1. Join Apple Developer Program (\$99/yr)"
echo "  2. Set CODESIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'"
echo "  3. Re-run this script, then notarise:"
echo "       xcrun notarytool submit $OUTPUT \\"
echo "         --apple-id \$APPLE_ID --team-id \$TEAM_ID --password \$APP_PASS --wait"
echo "       xcrun stapler staple $OUTPUT"
echo "─────────────────────────────────────────────────────────────"
