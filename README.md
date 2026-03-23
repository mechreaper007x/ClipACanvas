# CODE2VIDEO ⚡

**CODE2VIDEO** is a high-performance, memory-efficient rendering engine designed to turn HTML/CSS/JS animations into high-quality MP4 videos. 

Built with **Playwright (Chromium)** and **FFmpeg**, it provides a seamless "code-to-video" pipeline that works directly through memory pipes, making it up to **50% faster** than traditional disk-based rendering methods.

---

## ✨ Key Features

- **🚀 Speed-First Architecture:** Uses an `image2pipe` stream from Chromium directly into FFmpeg. No intermediate PNG files are ever written to your disk.
- **🧠 Lean Memory Mode:** Custom Chromium flags and explicit Garbage Collection (GC) keep peak RAM usage under 1.3 GB even during 1080p renders.
- **🎨 Pixel-Perfect Output:** Renders exactly what you see in the browser using the Chromium engine.
- **📱 Vertical Video Support:** Optimized for 9:16 reels, shorts, and TikTok content with built-in presets (540p, 720p, 1080p).
- **🖥️ Desktop Shell:** Includes a `pywebview` wrapper for a native desktop experience with a "Choose Save Location" file dialog.

---

## 🏗️ Technical Stack

- **Frontend:** HTML5, CSS3, Vanilla JS (for the UI)
- **Backend:** Python (Flask/WSGI)
- **Rendering Engine:** Playwright (Chromium)
- **Video Encoder:** FFmpeg (`libx264`)
- **Desktop Wrapper:** `pywebview` (Native OS WebView)

---

## ⚙️ Installation

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

## 🚀 Usage

### Desktop Mode (Recommended)
Launch the standalone desktop application:
```bash
launch_desktop.bat
# or
python desktop_app.py
```

### Web Mode
Run the server and access via `http://localhost:5000`:
```bash
python server.py
```

---

## 🛠️ How it Works (Optimization Details)

Traditional rendering usually follows this slow path:
`Browser -> Save PNG to Disk -> Wait -> Read PNG from Disk -> FFmpeg -> Video`

**CODE2VIDEO** uses a high-speed "Lean Mode" pipeline:
1. **Chromium** takes a frame screenshot in memory.
2. The pixel data is **piped directly** to FFmpeg's `stdin`.
3. **FFmpeg** encodes the frame while the next one is being captured.
4. **Memory Guard:** Chromium's JS engine is capped at 256MB, and `gc.collect()` forces immediate RAM release after the render.

---

## 📄 License
MIT · Built with ❤️ for the AI Creative Community.
