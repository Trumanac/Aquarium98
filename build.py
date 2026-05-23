"""
Local build helper for Aquarium 98 releases.

Usage:
    python build.py --version 1.0.0
    python build.py --version 1.0.0 --push     # also git tag + push

Outputs (in dist/):
    Aquarium98-v{version}.zip        — cross-platform source bundle
    Aquarium98-v{version}.zip.sha256 — SHA-256 checksum
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"

EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", "logs", "dist", "build",
                ".github", ".vscode", ".idea"}
EXCLUDE_FILES = {"config.json", "state.json", ".DS_Store", "Thumbs.db",
                 "aquarium98.lock", "fish_state.json"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".zip"}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def make_zip(version: str) -> Path:
    DIST.mkdir(exist_ok=True)
    zip_path = DIST / f"Aquarium98-v{version}.zip"
    if zip_path.exists():
        zip_path.unlink()

    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fname in files:
                fp = Path(root) / fname
                rel = fp.relative_to(ROOT)
                if should_skip(rel):
                    continue
                zf.write(fp, Path("Aquarium98") / rel)
                count += 1
    print(f"Built {zip_path}  ({count} files, {zip_path.stat().st_size // 1024} KB)")
    return zip_path


def write_checksum(zip_path: Path) -> Path:
    """Write a .sha256 sidecar file for *zip_path* and return its path."""
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    chk_path = zip_path.with_suffix(".zip.sha256")
    chk_path.write_text(f"{sha}  {zip_path.name}\n", encoding="utf-8")
    print(f"SHA-256 {chk_path.name}: {sha}")
    return chk_path


def git_tag_push(version: str) -> None:
    tag = f"v{version}"
    subprocess.run(["git", "tag", tag], check=True)
    subprocess.run(["git", "push"], check=True)
    subprocess.run(["git", "push", "origin", tag], check=True)
    print(f"Pushed tag {tag}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Aquarium 98 release zip.")
    ap.add_argument("--version", required=True, help="Release version (e.g. 1.0.0)")
    ap.add_argument("--push", action="store_true",
                    help="Also git tag and push to origin")
    args = ap.parse_args()

    zip_path = make_zip(args.version)
    write_checksum(zip_path)
    if args.push:
        git_tag_push(args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
