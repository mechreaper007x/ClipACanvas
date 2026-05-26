# Marketing & Launch Strategy — Clip.A.Canvas

This document serves as the launch and promotion handbook for **Clip.A.Canvas**. It provides ready-to-use copy templates, submission instructions for registries, and high-performance visual snippets to showcase the tool.

---

## 🚀 1. The Core Value Proposition

When promoting **Clip.A.Canvas**, highlight these three core differentiators:
1. **Zero-Cloud Privacy**: It runs 100% locally. Code snippets and renders are never uploaded to a cloud server. 
2. **Three Interfaces, One Engine**: Users get a graphical Desktop App (for visual editors), a terminal TUI (for developers), and an MCP server (for AI agents like Claude/Gemini to write and render video on-the-fly).
3. **Fidelity-First Capture**: It renders inside real Chromium using Playwright and encodes frame-by-frame via FFmpeg. It does not use fragile DOM snapshotting or laggy real-time screen capture.

---

## 📦 2. MCP Registries & Submissions

To drive developer adoption, submit the MCP server to the following indexes:

### A. Smithery.ai (Already Listed!)
- **Status**: Listed at `https://smithery.ai/servers/creatorsavya/clipacanvas`.
- **Action**: Claim ownership and add a link to the badge in the repo:
  ```markdown
  [![Smithery Badge](https://smithery.ai/badge?name=clipacanvas)](https://smithery.ai/servers/creatorsavya/clipacanvas)
  ```

### B. Glama.ai
- **Registry**: `https://glama.ai/mcp/servers`
- **Submission**: Click **Submit Server** on Glama. Fill in the GitHub URL and description. Glama automatically displays a score and status badge.

### C. DotMCP (dotmcp.com)
- **Registry**: `https://dotmcp.com`
- **Submission**: Submit via the website or open a PR if they host a public JSON database.

---

## 📢 3. Launch Copy Templates

### 🐱 Product Hunt Launch

*   **Product Name**: Clip.A.Canvas
*   **Tagline**: Transform HTML, CSS, JS & SVG animations into MP4 videos locally
*   **Categories**: Developer Tools, Design Tools, Productivity
*   **Description**:
    > Clip.A.Canvas is a privacy-first, 100% local utility that renders front-end motion (CSS keyframes, SVG paths, canvas particles, and WAAPI) into production-ready MP4 videos.
    > 
    > It includes:
    > - 🖥️ **Desktop App**: A clean pywebview interface to paste, preview, and export.
    > - 📟 **Terminal TUI**: A keyboard-first Textual-based CLI with clipboard import and browser-backed live preview.
    > - 🔌 **MCP Server**: Let your local AI agents (Claude Code, Gemini CLI, Codex) write animation code and render it directly to your disk!
    > 
    > No SaaS subscriptions, no API keys, and no source code ever leaves your machine. Powered by Chromium and FFmpeg.
*   **First Comment (Maker Post)**:
    > Hey PH! 👋
    > I built Clip.A.Canvas because I was tired of recording my screen to capture simple front-end animations, or dealing with expensive, cloud-only video automation APIs. 
    >
    > I wanted a tool that respects privacy, is keyboard-friendly, and integrates directly with my AI workflows. Whether you want to output a quick UI card pulse, render complex canvas simulations, or let Claude write and record an SVG animation for you, Clip.A.Canvas handles it.
    >
    > It's open-source, runs fully offline, and is now available on PyPI! I’d love to hear your feedback on the TUI and MCP setups. Let me know what you think! 🚀

---

### 💻 Hacker News (Show HN)

*   **Title**: Show HN: Clip.A.Canvas – Local HTML/SVG to MP4 renderer (Desktop, TUI, and MCP)
*   **Body**:
    > Hey HN,
    > 
    > I wanted a clean way to turn browser animations into videos without paying for cloud rendering APIs or manually using screen recorders. So I built Clip.A.Canvas: https://github.com/mechreaper007x/ClipACanvas
    > 
    > Under the hood, it starts a local headless Chromium instance via Playwright, loads the page, hooks into the animation timers (or requestAnimationFrame), captures the frames, and pipes them directly into a local FFmpeg encoder.
    > 
    > I packaged it into three formats:
    > 1. A PyInstaller-wrapped Windows/macOS Desktop app.
    > 2. An interactive Textual TUI (`pipx install clipacanvas-tui`) featuring an editor, live preview server, and Windows Controlled Folder Access setup.
    > 3. An MCP server (`uvx clipacanvas-mcp`) so agents like Claude Code or Codex can generate SVG or Canvas loops and render them directly to your local file system.
    > 
    > The rendering is deterministic: instead of real-time capture (which drops frames if your CPU lags), it steps through virtual time to ensure every single frame is exported with perfect 60 FPS quality.
    > 
    > It's fully open-source (MIT). I'd love to hear feedback, especially on the virtual-time injection and the TUI terminal layout!

---

### 👾 Reddit Launch Kit

#### r/selfhosted (Focus on local-only, self-contained architecture)
*   **Title**: Self-Hosted/Local: Renders HTML, CSS, SVG, and Canvas animations to MP4 (no cloud)
*   **Post**:
    > If you do front-end development, make motion graphics, or use AI agents, you might like this: **Clip.A.Canvas** is a local utility to render HTML animations into MP4 videos on your own machine.
    > 
    > - **No Cloud**: Rendering is done via a local Playwright/Chromium instance, and video encoding is handled on-device with FFmpeg.
    > - **TUI included**: `pipx install clipacanvas-tui` gets you an interactive editor and control deck inside the terminal.
    > - **MCP Server**: Register it via `uvx clipacanvas-mcp` so your terminal LLM agents can write visual assets and save them locally.
    > 
    > Repository: https://github.com/mechreaper007x/ClipACanvas
    > 
    > It is MIT licensed and written in Python. Perfect for making marketing videos, portfolio items, or letting agents show you what they built.

#### r/webdev (Focus on showcase, portfolio, and front-end animation)
*   **Title**: Showoff Saturday: I made a tool to render CSS, SVG, and Canvas animations into MP4s
*   **Post**:
    > Hey r/webdev,
    > I built Clip.A.Canvas to make it easy to export HTML/CSS/JS animations to video. Rather than screen-recording a browser tab and trimming it, you just paste your code and export.
    >
    > It uses headless Chromium to guarantee that CSS keyframes, SVG animations, WAAPI, GSAP, and canvas requestAnimationFrame renders look exactly as they would in the browser. 
    >
    > Check it out here: https://github.com/mechreaper007x/ClipACanvas
    > The web project is deployed at: https://clipacanvas.vercel.app

---

### 🐦 Twitter/X Launch Thread

1. **Tweet 1 (Hook)**:
   > Stop recording your browser window to share web animations. 
   > 
   > Clip.A.Canvas turns HTML, CSS, JS, SVG, and Canvas snippets into editor-ready MP4 videos locally. 
   > 
   > Renders in Chromium. Encoded with FFmpeg. 100% offline. 🧵👇
   > [Attach app_screenshot_updated.png or a demo video]

2. **Tweet 2 (TUI)**:
   > Keyboard-first? The terminal TUI is built with Textual:
   > - Split-pane editor & status panel
   > - Live browser preview
   > - OS clipboard importer (`Ctrl+V` & `F6`)
   > 
   > Run:
   > `pipx install clipacanvas-tui`
   > `clipacanvas-tui --clipboard --preview`
   > [Attach a gif of the TUI rendering]

3. **Tweet 3 (MCP)**:
   > Let AI agents render videos. The MCP server integrates with Claude Code, Codex, and Gemini. 
   >
   > Ask Claude: "Write a bouncing ball animation and render it to video." 
   >
   > Install:
   > `claude mcp add -s user clipacanvas -- uvx clipacanvas-mcp`

4. **Tweet 4 (CTA)**:
   > Grab the Windows installer/portable ZIP, read the documentation, or inspect the source code on GitHub.
   > 
   > 🌐 Website: https://clipacanvas.vercel.app
   > 📦 GitHub: https://github.com/mechreaper007x/ClipACanvas
   > 
   > Give it a star if you find it useful! ⭐

---

## 🎨 4. Stunning Showcase Test Snippets

Provide these snippets to users to test the rendering capabilities immediately. They demonstrate different rendering paths (CSS, SVG, Canvas) and look gorgeous in the output video.

### Snippet 1: CSS Cyberpunk Radar (DOM/CSS path)
A futuristic glassmorphic radar scanning sweeps. Perfect for showing off gradients and rotations.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body {
      margin: 0;
      height: 100vh;
      display: grid;
      place-items: center;
      background: #020617;
      font-family: monospace;
      overflow: hidden;
    }
    .radar {
      position: relative;
      width: 320px;
      height: 320px;
      border-radius: 50%;
      border: 2px solid #00f0ff;
      box-shadow: 0 0 20px rgba(0, 240, 255, 0.2);
      background: radial-gradient(circle, rgba(0, 240, 255, 0.05) 0%, transparent 70%);
      overflow: hidden;
    }
    .radar::before {
      content: '';
      position: absolute;
      width: 100%;
      height: 100%;
      top: 0; left: 0;
      background: conic-gradient(from 0deg, #00f0ff 0deg, transparent 90deg, transparent 360deg);
      border-radius: 50%;
      animation: sweep 3s linear infinite;
      transform-origin: center;
    }
    .blip {
      position: absolute;
      width: 12px;
      height: 12px;
      background: #d7ff43;
      border-radius: 50%;
      box-shadow: 0 0 15px #d7ff43;
      top: 30%; left: 65%;
      animation: ping 1.5s ease-in-out infinite alternate;
    }
    @keyframes sweep {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    @keyframes ping {
      0% { transform: scale(0.8); opacity: 0.4; }
      100% { transform: scale(1.3); opacity: 1; }
    }
  </style>
</head>
<body>
  <div class="radar">
    <div class="blip"></div>
  </div>
</body>
</html>
```

### Snippet 2: Neon Orbiting Rings (SVG path)
Tests SVG dash arrays, gradients, and composite filters.

```html
<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      height: 100vh;
      background: #090d16;
      display: grid;
      place-items: center;
      overflow: hidden;
    }
    svg {
      width: 300px;
      height: 300px;
      filter: drop-shadow(0 0 15px rgba(215, 255, 67, 0.4));
    }
    .ring-outer {
      fill: none;
      stroke: #d7ff43;
      stroke-width: 4;
      stroke-dasharray: 400;
      animation: spin 4s linear infinite;
      transform-origin: center;
    }
    .ring-inner {
      fill: none;
      stroke: #00f0ff;
      stroke-width: 2;
      stroke-dasharray: 200;
      animation: spin-reverse 3s linear infinite;
      transform-origin: center;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @keyframes spin-reverse {
      to { transform: rotate(-360deg); }
    }
  </style>
</head>
<body>
  <svg viewBox="0 0 200 200">
    <circle cx="100" cy="100" r="80" class="ring-outer" />
    <circle cx="100" cy="100" r="50" class="ring-inner" />
    <circle cx="100" cy="100" r="10" fill="#fff" />
  </svg>
</body>
</html>
```

### Snippet 3: Canvas Digital Rain (Canvas path)
Tests requestAnimationFrame loop rendering, fading tail trails, and high particle density.

```html
<!DOCTYPE html>
<html>
<body style="margin:0;background:#000;overflow:hidden">
  <canvas id="canvas"></canvas>
  <script>
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 540;
    canvas.height = 960;

    const columns = Math.floor(canvas.width / 20);
    const yPositions = Array(columns).fill(0);

    function draw() {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.fillStyle = '#d7ff43';
      ctx.font = '15px monospace';

      for (let i = 0; i < yPositions.length; i++) {
        const char = String.fromCharCode(33 + Math.random() * 93);
        const x = i * 20;
        const y = yPositions[i];
        
        ctx.fillText(char, x, y);

        if (y > canvas.height && Math.random() > 0.975) {
          yPositions[i] = 0;
        } else {
          yPositions[i] += 20;
        }
      }
      requestAnimationFrame(draw);
    }
    requestAnimationFrame(draw);
  </script>
</body>
</html>
```
