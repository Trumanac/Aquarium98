# Aquarium 98 — Packaging & Distribution Guide

## Overview

| Platform | Tool | Output |
|----------|------|--------|
| Windows 10/11 (x64) | PyInstaller + Inno Setup | `Aquarium98-Setup-X.Y.Z.exe` |
| Linux (x86_64) | PyInstaller + AppImage | `Aquarium98-X.Y.Z-x86_64.AppImage` |
| macOS 10.15+ | PyInstaller + hdiutil/create-dmg | `Aquarium98-X.Y.Z.dmg` |

Builds happen automatically on GitHub Actions when you push a version tag.
You can also build locally on each platform.

---

## Automated Builds (GitHub Actions)

### 1. Tag a release

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow (`.github/workflows/build-release.yml`) runs three parallel jobs
(Windows / Linux / macOS), packages the outputs, and creates a **draft** GitHub
Release with all artifacts and SHA256 checksums attached.

Review the draft release, edit the description if needed, then **Publish**.

### 2. Manual trigger

Go to **Actions → Build & Release → Run workflow** in the GitHub UI.
Enter a version string (e.g. `1.0.0`) and click **Run workflow**.

---

## Local Builds

### Prerequisites (all platforms)

```bash
pip install -r requirements.txt pyinstaller

# Generate icon files before bundling (only needed once in dev)
python -c "from src.icon_gen import ensure_icons; ensure_icons()"
```

### Windows

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php) (free).
2. Run PyInstaller:
   ```bat
   pyinstaller aquarium98.spec
   ```
3. Build the installer:
   ```bat
   "C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer\aquarium98.iss
   ```
4. Installer output: `installer\Output\Aquarium98-Setup-1.0.0.exe`

### Linux

```bash
pyinstaller aquarium98.spec
chmod +x installer/build_appimage.sh
installer/build_appimage.sh 1.0.0
# Output: dist/Aquarium98-1.0.0-x86_64.AppImage
```

System packages needed (Ubuntu/Debian):
```bash
sudo apt-get install libsdl2-dev libfuse2 file
```

### macOS

```bash
pyinstaller aquarium98.spec
chmod +x installer/create_dmg.sh
installer/create_dmg.sh 1.0.0
# Output: dist/Aquarium98-1.0.0.dmg
```

Optional: `brew install create-dmg` for a prettier installer DMG with
background image and an /Applications shortcut drag target.

---

## Code Signing

### Windows

Without a certificate, Windows SmartScreen shows:
> *"Windows protected your PC — Microsoft Defender SmartScreen prevented an
> unrecognized app from starting."*

**User workaround:** Click **More info → Run anyway**.  
This warning disappears naturally as more users install the app and reputation builds.

**To suppress the warning entirely:**  
Subscribe to [Azure Trusted Signing](https://azure.microsoft.com/en-us/products/trusted-signing)
(~$9.99/month). Then uncomment the signing step in the GitHub Actions workflow
and add the required secrets to the repository:

| Secret | Description |
|--------|-------------|
| `AZURE_TENANT_ID` | Azure AD tenant |
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_CLIENT_SECRET` | Service principal secret |
| `AZURE_SIGNING_ENDPOINT` | Trusted Signing endpoint URL |
| `AZURE_SIGNING_ACCOUNT` | Trusted Signing account name |
| `AZURE_CERT_PROFILE` | Certificate profile name |

### Linux

No signing required. SHA256 checksums (`SHA256SUMS.txt`) are included in every
release so users can verify the download is untampered.

### macOS

The `create_dmg.sh` script applies **ad-hoc signing**
(`codesign --force --deep --sign -`) which is free and suppresses the
*"damaged app, move to Trash"* Gatekeeper error that affects unsigned
bundles downloaded from the internet.

**User workaround (if Gatekeeper blocks the app):**

Option A — Right-click the `.app` and choose **Open** on first launch.

Option B — Run in Terminal:
```bash
xattr -dr com.apple.quarantine /Applications/Aquarium98.app
```

**For full notarization (no warnings at all):**  
Requires an [Apple Developer Program](https://developer.apple.com/programs/)
membership ($99/yr). Set `CODESIGN_IDENTITY` to your Developer ID string and
follow the notarisation instructions printed by `create_dmg.sh`.

---

## File Structure

```
aquarium98.spec              PyInstaller build spec
installer/
  aquarium98.iss             Inno Setup script (Windows installer)
  build_appimage.sh          AppImage builder (Linux)
  create_dmg.sh              DMG builder (macOS)
  entitlements.plist         macOS hardened-runtime entitlements
.github/
  workflows/
    build-release.yml        GitHub Actions CI/CD workflow
```

---

## User Data Locations

The app never writes to its own install directory. All user data goes here:

| Platform | Path |
|----------|------|
| Windows | `%USERPROFILE%\Documents\Aquarium98\` |
| macOS | `~/Documents/Aquarium98/` |
| Linux | `~/.local/share/Aquarium98/` (respects `$XDG_DATA_HOME`) |

Files stored there: `config.json`, `fish_state.json`, `logs/`.
Uninstalling the app does **not** delete user data — users keep their fish.

---

## Version Bumping

Before tagging a release, update the version string in:

1. `installer/aquarium98.iss` — `#define MyAppVersion`
2. `aquarium98.spec` — `CFBundleShortVersionString` / `CFBundleVersion`
3. Any `__version__` in the Python source (if added)

The GitHub Actions workflow auto-reads the version from the git tag, so
those file edits are mainly for local builds and human readability.
