# CODE2VIDEO

**CODE2VIDEO** turns HTML/CSS/JS animations into MP4 videos through a local desktop app.

It uses **Playwright (Chromium)** for rendering and **FFmpeg** for encoding, so users get browser-accurate output without depending on any hosted backend.

Website: https://code2video.vercel.app

Downloads: https://github.com/mechreaper007x/code2video-renderer/releases/tag/v1.0.0

---

## Release Trust

- Windows builds are currently unsigned, so SmartScreen or Defender reputation warnings can appear on first run.
- Ship downloads only through GitHub Releases.
- Generate `SHA256SUMS.txt` from the current `dist/` artifacts before publishing:

```bash
python build_release_assets.py --version v1.0.0
```

- Upload these generated files with each release:
  - `dist/SHA256SUMS.txt`
  - `dist/RELEASE_NOTES.md`

---

## Key Features

- **Desktop-first workflow:** Launch as a native desktop app through `pywebview`.
- **Bundled renderer stack:** Desktop builds ship with Chromium and FFmpeg.
- **Pixel-accurate output:** Final video is rendered in Chromium, not from a DOM screenshot hack.
- **Save anywhere:** Desktop mode opens a native "Save As" dialog for the finished MP4.

---

## Technical Stack

- **Frontend:** HTML5, CSS3, Vanilla JS (for the UI)
- **Backend:** Python HTTP server
- **Rendering Engine:** Playwright (Chromium)
- **Video Encoder:** FFmpeg (`libx264`)
- **Desktop Wrapper:** `pywebview` (Native OS WebView)

---

## Installation

### 1. Clone & Dependencies
```bash
git clone https://github.com/your-repo/code2video.git
cd code2video
pip install -r requirements.txt
pip install -r desktop_requirements.txt
```

### 2. Install Chromium (Playwright)
```bash
playwright install chromium
```

---

## Usage

### Desktop Mode (Recommended)
Launch the local desktop application:
```bash
launch_desktop.bat
# or
python desktop_app.py
```

On macOS:
```bash
chmod +x launch_desktop.command
./launch_desktop.command
```

### Build a Windows Distributable Folder
```bash
python build_desktop.py
```

Output:
- `dist/CODE2VIDEO/CODE2VIDEO.exe`
- `dist/CODE2VIDEO-windows.zip`

### Build a Windows Installer
```bash
python build_installer.py
```

Output:
- `dist/CODE2VIDEO-Setup.exe`

### Build a macOS App
Run this on a Mac:
```bash
python3 build_mac_app.py
```

Output:
- `dist/CODE2VIDEO.app`
- `dist/CODE2VIDEO-macos.zip`

### One-File macOS Build
If you want a single safe helper file on Mac:
```bash
chmod +x build_mac_safe.command
./build_mac_safe.command
```

### Build macOS on GitHub
This repo now includes a GitHub Actions workflow at `.github/workflows/build-macos-app.yml`.

You can trigger it from the GitHub Actions tab with `Build macOS App`, or let it run on pushes to `main` when the Mac build files change. The workflow uploads:
- `dist/CODE2VIDEO-macos.zip`
- `dist/CODE2VIDEO.app`

## Notes

- The packaged app must keep the full `CODE2VIDEO` folder together with `_internal`.
- The installer is the easier option for non-technical users.
- macOS packaging must be built on macOS; it cannot be cross-compiled from Windows.
- Development can still run locally with `python desktop_app.py`.

---

## License
MIT. Built for the AI Creative Community.
