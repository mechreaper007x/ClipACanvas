#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "ClipACanvas"
INSTALLER_NAME = "ClipACanvas-Setup.exe"
DIST_DIR = Path("dist")
PORTABLE_EXE = DIST_DIR / f"{APP_NAME}.exe"
ISS_FILE = Path("installer") / "ClipACanvas.iss"

def find_iscc() -> str | None:
    candidates = [
        shutil.which("iscc"),
        shutil.which("ISCC.exe"),
        str(Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe"),
        str(Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None

def ensure_portable_exe() -> None:
    if PORTABLE_EXE.exists():
        return
    print(f"{PORTABLE_EXE} not found. Building desktop executable first...")
    subprocess.run([sys.executable, "build_desktop.py"], check=True)

def build_installer():
    """Run Inno Setup to create the Windows installer."""
    print(f"Building {APP_NAME} Installer...")

    if not ISS_FILE.exists():
        print(f"ERROR: Inno Setup script not found at {ISS_FILE}")
        return

    ensure_portable_exe()
    iscc = find_iscc()
    if not iscc:
        print("ERROR: Inno Setup compiler not found.")
        print("Please install Inno Setup 6 or update the path in build_installer.py")
        return

    cmd = [str(iscc), str(ISS_FILE)]
    try:
        subprocess.run(cmd, check=True)
        print(f"Installer created: dist/{INSTALLER_NAME}")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Inno Setup failed with exit code {e.returncode}")

if __name__ == "__main__":
    if os.name != 'nt':
        print("Installer build is only supported on Windows.")
    else:
        build_installer()
