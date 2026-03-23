import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "CODE2VIDEO"
INSTALLER_NAME = "CODE2VIDEO-Setup.exe"
DIST_DIR = Path("dist")
APP_DIR = DIST_DIR / APP_NAME
ISS_FILE = Path("installer") / "CODE2VIDEO.iss"


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


def ensure_bundle() -> None:
    if APP_DIR.exists():
        return
    subprocess.run([sys.executable, "build_desktop.py"], check=True)


def main() -> int:
    if os.name != "nt":
        print("The installer build is supported on Windows only.")
        return 1

    ensure_bundle()

    if not ISS_FILE.exists():
        print(f"Missing installer script: {ISS_FILE}")
        return 1

    iscc = find_iscc()
    if not iscc:
        print("Inno Setup compiler was not found.")
        print("Install it first, then rerun: python build_installer.py")
        return 1

    subprocess.run([iscc, str(ISS_FILE)], check=True)
    output_path = DIST_DIR / INSTALLER_NAME
    print(f"Installer ready: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
