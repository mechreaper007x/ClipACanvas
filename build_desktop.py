import os
import sys
import shutil
import subprocess
from pathlib import Path

# --- CONFIGURATION ---
APP_NAME = "CODE2VIDEO"
ENTRY_POINT = "desktop_app.py"
DIST_DIR = Path("dist")
BUILD_DIR = Path("build")
BIN_DIR = Path("bin")

def run_command(cmd, msg):
    print(f"[*] {msg}...")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Error: {e.stderr}")
        sys.exit(1)

def main():
    # 1. Clean up old builds
    if DIST_DIR.exists(): shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists(): shutil.rmtree(BUILD_DIR)
    if BIN_DIR.exists(): shutil.rmtree(BIN_DIR)
    BIN_DIR.mkdir()

    print(f"=== Building {APP_NAME} Distributable ===")

    # 2. Get FFmpeg Binary
    print("[*] Locating FFmpeg...")
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    shutil.copy(ffmpeg_exe, BIN_DIR / "ffmpeg.exe")
    print(f"    -> Copied FFmpeg to {BIN_DIR}")

    # 3. Get Playwright Chromium Binary
    print("[*] Installing/Locating Chromium...")
    # Set a local path for browsers so we know where they are
    local_browsers = BIN_DIR / "browsers"
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(local_browsers)
    
    # Run playwright install to ensure we have the binary locally
    run_command([sys.executable, "-m", "playwright", "install", "chromium"], "Downloading Chromium to bin/browsers")
    
    # 4. Prepare PyInstaller Command
    # We bundle:
    # - code2video.html
    # - playwright_render.py (module)
    # - serve.py (module)
    # - bin/ (ffmpeg and browsers)
    
    pyinstaller_cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile", # We can use --onedir for faster startup, but --onefile is cleaner for distribution
        "--windowed", # No console window
        "--name", APP_NAME,
        "--add-data", "code2video.html;.",
        "--add-data", "bin;bin",
        "--collect-all", "playwright",
        "--collect-all", "webview",
        "--hidden-import", "playwright_render",
        "--hidden-import", "serve",
        "--icon", "NONE", # Add icon path here if you have one
        ENTRY_POINT
    ]

    print("[*] Running PyInstaller (this may take a few minutes)...")
    subprocess.run(pyinstaller_cmd, check=True)

    print("\n" + "="*40)
    print(f"🎉 SUCCESS! {APP_NAME} is ready.")
    print(f"📂 Location: {DIST_DIR / (APP_NAME + '.exe')}")
    print("="*40)

if __name__ == "__main__":
    main()
