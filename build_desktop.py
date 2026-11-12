#!/usr/bin/env python3

import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

APP_NAME = "ClipACanvas"
ENTRY_POINT = "desktop_app.py"
DIST_DIR = Path("dist")
BUILD_DIR = Path("build")
ICON_FILE = Path("assets") / "custom_app_icon.ico"
PORTABLE_EXE = DIST_DIR / f"{APP_NAME}.exe"
PORTABLE_ZIP = DIST_DIR / f"{APP_NAME}-windows.zip"
LEGACY_APP_DIR = DIST_DIR / APP_NAME

def clean():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    DIST_DIR.mkdir(exist_ok=True)
    for artifact in [PORTABLE_EXE, PORTABLE_ZIP]:
        if artifact.exists():
            artifact.unlink()

    if LEGACY_APP_DIR.exists():
        try:
            shutil.rmtree(LEGACY_APP_DIR)
        except PermissionError:
            print(f"WARNING: Could not remove locked legacy folder: {LEGACY_APP_DIR}")

def create_portable_zip(exe_path: Path) -> None:
    print(f"Creating ZIP archive at {PORTABLE_ZIP}...")
    with zipfile.ZipFile(PORTABLE_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(exe_path, arcname=exe_path.name)

def build_windows():
    print(f"Building {APP_NAME} for Windows...")

    sep = ";"
    add_data = [
        ("clipacanvas.html", "."),
        ("logo_neon_preview-removebg-preview.png", "."),
        ("logo_neon_overlay.png", "."),
        ("serve.py", "."),
        ("playwright_render.py", "."),
        ("playwright_render.mjs", "."),
    ]

    monaco_src = Path("node_modules") / "monaco-editor" / "min" / "vs"
    if monaco_src.exists():
        add_data.append((str(monaco_src), "monaco/min/vs"))
    else:
        print("WARNING: node_modules/monaco-editor/min/vs not found. The editor will fall back to a plain textarea.")

    fonts_src = Path("fonts")
    if fonts_src.exists():
        add_data.append((str(fonts_src), "fonts"))
    else:
        print("WARNING: fonts/ folder not found. Bundled fonts (JetBrains Mono, Fira Code) will not be available.")

    local_bin = Path("bin")
    if local_bin.exists():
        # Bundle the preloaded Chromium/FFmpeg payload into the onefile build.
        add_data.append((str(local_bin), "bin"))
    else:
        print("WARNING: bin/ folder not found. Portable build will fall back to local FFmpeg/Playwright.")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--icon", str(ICON_FILE),
        "--collect-all", "playwright",
        "--collect-all", "webview",
        "--hidden-import", "playwright_render",
        "--hidden-import", "serve",
    ]

    for source, destination in add_data:
        cmd.extend(["--add-data", f"{source}{sep}{destination}"])

    cmd.append(ENTRY_POINT)
    subprocess.run(cmd, check=True)

    if not PORTABLE_EXE.exists():
        raise FileNotFoundError(f"Expected portable executable was not created: {PORTABLE_EXE}")

    create_portable_zip(PORTABLE_EXE)

def build_mac():
    print(f"Building {APP_NAME} for macOS...")
    # Note: For proper macOS bundles, use build_mac_app.py instead
    sep = ":"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", APP_NAME,
        "--add-data", f"clipacanvas.html{sep}.",
        "--add-data", f"logo_neon_preview-removebg-preview.png{sep}.",
        "--add-data", f"logo_neon_overlay.png{sep}.",
        "--add-data", f"serve.py{sep}.",
        "--add-data", f"playwright_render.py{sep}.",
        "--add-data", f"playwright_render.mjs{sep}.",
        "--osx-bundle-identifier", "com.clipacanvas.app",
        ENTRY_POINT
    ]
    subprocess.run(cmd, check=True)

def verify_environment():
    """Fail fast on problems that would otherwise ship a broken executable."""
    problems = []

    try:
        import webview  # noqa: F401
    except ImportError:
        problems.append(
            "pywebview is not installed. The packaged app cannot open a window without it "
            "(install with: pip install \"pywebview>=6,<7\")."
        )

    # The bundled Chromium revision must match what the Python playwright
    # package expects, otherwise rendering fails at runtime inside the exe.
    browsers_dir = Path("bin") / "browsers"
    if browsers_dir.exists():
        try:
            import json

            import playwright

            manifest = (
                Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
            )
            expected = {
                entry["revision"]
                for entry in json.loads(manifest.read_text(encoding="utf-8"))["browsers"]
                if entry["name"] == "chromium-headless-shell"
            }
            present = {p.name.rsplit("-", 1)[-1] for p in browsers_dir.iterdir() if p.is_dir()}
            missing = expected - present
            if missing:
                problems.append(
                    "bin/browsers is missing Chromium revision "
                    f"{', '.join(sorted(missing))} required by the installed playwright "
                    f"package. Run: PLAYWRIGHT_BROWSERS_PATH=bin/browsers "
                    "python -m playwright install chromium"
                )
        except Exception as exc:  # pragma: no cover - best effort guard
            print(f"WARNING: Could not verify bundled browser revision: {exc}")

    if problems:
        print("\nBUILD BLOCKED:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)


def main():
    verify_environment()
    clean()
    if platform.system() == "Windows":
        build_windows()
    elif platform.system() == "Darwin":
        build_mac()
    else:
        print(f"Unsupported OS: {platform.system()}")

if __name__ == "__main__":
    main()
