#!/usr/bin/env python3

import os
import subprocess
import shutil
import platform
import tempfile
from pathlib import Path

APP_NAME = "ClipACanvas"
ENTRY_POINT = "desktop_app.py"
DIST_DIR = Path("dist")
BUILD_DIR = Path("build")
PNG_ICON = Path("assets") / "clipacanvas.png"
ICNS_ICON = Path("assets") / "clipacanvas.icns"

def clean():
    """Remove build and dist folders."""
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)

def create_icns():
    """Convert PNG to ICNS using iconutil (macOS only)."""
    if not PNG_ICON.exists():
        print(f"WARNING: {PNG_ICON} not found. App will have default icon.")
        return None

    if ICNS_ICON.exists():
        return ICNS_ICON

    print("Generating .icns from .png...")
    with tempfile.TemporaryDirectory() as temp_dir:
        iconset_dir = Path(temp_dir) / "clipacanvas.iconset"
        iconset_dir.mkdir()
        
        sizes = [16, 32, 64, 128, 256, 512]
        for size in sizes:
            # Normal
            subprocess.run([
                "sips", "-z", str(size), str(size),
                str(PNG_ICON), "--out", str(iconset_dir / f"icon_{size}x{size}.png")
            ], check=True, capture_output=True)
            # Retina
            subprocess.run([
                "sips", "-z", str(size*2), str(size*2),
                str(PNG_ICON), "--out", str(iconset_dir / f"icon_{size}x{size}@2x.png")
            ], check=True, capture_output=True)

        subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(ICNS_ICON)], check=True)
    return ICNS_ICON

def build_mac_bundle():
    """Create a proper macOS .app bundle using PyInstaller."""
    print(f"Building {APP_NAME}.app...")
    
    icon_path = create_icns()
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", APP_NAME,
        "--add-data", "clipacanvas.html:.",
        "--add-data", "logo_neon_preview-removebg-preview.png:.",
        "--add-data", "serve.py:.",
        "--add-data", "playwright_render.py:.",
        "--add-data", "playwright_render.mjs:.",
        "--hidden-import", "playwright_render",
        "--hidden-import", "serve",
        "--osx-bundle-identifier", "com.clipacanvas.app",
    ]

    if icon_path:
        cmd.extend(["--icon", str(icon_path)])

    cmd.append(ENTRY_POINT)
    
    subprocess.run(cmd, check=True)

    # Bundle binaries
    app_path = DIST_DIR / f"{APP_NAME}.app"
    resources_dir = app_path / "Contents" / "Resources" / "bin"
    resources_dir.mkdir(parents=True, exist_ok=True)

    local_bin = Path("bin")
    if local_bin.exists():
        print("Copying bundled binaries to App Resources...")
        shutil.copytree(local_bin, resources_dir, dirs_exist_ok=True)

    print("Creating ZIP archive...")
    shutil.make_archive(str(DIST_DIR / f"{APP_NAME}-macos"), 'zip', DIST_DIR, f"{APP_NAME}.app")

def main():
    if platform.system() != "Darwin":
        print("Error: build_mac_app.py must be run on macOS.")
        return

    clean()
    build_mac_bundle()

if __name__ == "__main__":
    main()
