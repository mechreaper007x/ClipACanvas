"""Main editor screen — split pane with code editor and render status."""

from __future__ import annotations

import asyncio
import math
import os
import shutil
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Input,
    Button,
    Label,
    ProgressBar,
    Select,
    Static,
    TextArea,
)

from ..clipboard import read_clipboard_text
from ..preview_server import PreviewServer

HARD_MAX_DURATION_SECONDS = 60.0


class RenderComplete(Message):
    """Fired when a render finishes."""

    def __init__(
        self,
        success: bool,
        message: str,
        output_path: str = "",
        content_mode: str = "unknown",
        duration: float = 0.0,
        frame_count: int = 0,
        save_warning: str = "",
    ):
        super().__init__()
        self.success = success
        self.message = message
        self.output_path = output_path
        self.content_mode = content_mode
        self.duration = duration
        self.frame_count = frame_count
        self.save_warning = save_warning


class EditorScreen(Screen):
    """Split-pane editor screen with code on the left and render status on the right."""

    RENDER_ANIMATION_FRAMES = (
        "[=    ]",
        "[==   ]",
        "[===  ]",
        "[ === ]",
        "[  ===]",
        "[   ==]",
        "[    =]",
        "[   ==]",
        "[  ===]",
        "[ === ]",
    )

    CSS = """
    EditorScreen {
        layout: vertical;
    }

    #toolbar {
        height: auto;
        padding: 0 2;
        background: $surface-darken-2;
        layout: vertical;
    }

    #toolbar-row-core, #toolbar-row-timing, #toolbar-row-actions {
        height: 3;
        align: center middle;
    }

    #toolbar Label {
        margin: 0 1 0 0;
    }

    #toolbar Select {
        width: 16;
        margin: 0 2 0 0;
    }

    #toolbar Input {
        width: 12;
        margin: 0 2 0 0;
    }

    #toolbar Button {
        margin: 0 0 0 2;
    }

    #toolbar-hints {
        width: 1fr;
        color: $text-muted;
    }

    #main-pane {
        height: 1fr;
        layout: horizontal;
    }

    #code-pane {
        width: 1fr;
        border: solid $primary;
        padding: 1;
    }

    #code-label {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    TextArea {
        height: 1fr;
        border: none;
    }

    #status-pane {
        width: 42;
        border: solid $primary;
        padding: 1 2;
        background: $surface-darken-1;
    }

    #status-label {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #status-pane Input {
        width: 1fr;
        margin-bottom: 1;
    }

    .status-field {
        margin-bottom: 1;
    }

    #render-progress {
        margin: 2 0;
    }

    #result-text {
        margin-top: 1;
    }
    """

    DEFAULT_CODE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
html, body {
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background:
    radial-gradient(circle at top, #122033 0%, #060a12 58%, #020305 100%);
}

canvas {
  display: block;
  width: 100vw;
  height: 100vh;
}
</style>
</head>
<body>
<canvas id="scene"></canvas>
<script>
const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");

function resize() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}

resize();
window.addEventListener("resize", resize);

const blobs = Array.from({ length: 14 }, (_, index) => ({
  angle: (Math.PI * 2 * index) / 14,
  radius: 80 + index * 11,
  speed: 0.3 + index * 0.025,
  size: 8 + (index % 4) * 5,
  hue: 160 + index * 10
}));

function draw(time) {
  const t = time / 1000;
  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h / 2;

  ctx.clearRect(0, 0, w, h);

  const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) * 0.65);
  bg.addColorStop(0, "rgba(18, 34, 54, 0.14)");
  bg.addColorStop(1, "rgba(0, 0, 0, 0.34)");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  ctx.save();
  ctx.globalCompositeOperation = "lighter";

  for (const blob of blobs) {
    const orbit = blob.angle + t * blob.speed;
    const pulse = Math.sin(t * 2.2 + blob.angle * 3) * 20;
    const x = cx + Math.cos(orbit) * (blob.radius + pulse);
    const y = cy + Math.sin(orbit * 1.3) * (blob.radius * 0.45 + pulse);

    const glow = ctx.createRadialGradient(x, y, 0, x, y, blob.size * 4.5);
    glow.addColorStop(0, `hsla(${blob.hue}, 100%, 72%, 0.95)`);
    glow.addColorStop(0.35, `hsla(${blob.hue + 12}, 100%, 62%, 0.55)`);
    glow.addColorStop(1, `hsla(${blob.hue + 30}, 100%, 50%, 0)`);

    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, blob.size * 4.5, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();

  const ring = 120 + Math.sin(t * 2.4) * 14;
  ctx.strokeStyle = "rgba(170, 255, 230, 0.28)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(cx, cy, ring, 0, Math.PI * 2);
  ctx.stroke();

  ctx.fillStyle = "#d8fff4";
  ctx.font = "600 30px Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Clip.A.Canvas", cx, cy + 12);

  requestAnimationFrame(draw);
}

requestAnimationFrame(draw);
</script>
</body>
</html>"""

    def __init__(
        self,
        initial_code: str | None = None,
        auto_open_preview: bool = False,
    ):
        super().__init__()
        self.initial_code = initial_code or self.DEFAULT_CODE
        self.auto_open_preview = auto_open_preview
        self.render_worker: Any = None
        self.preview_server = PreviewServer(self.initial_code)
        self.render_feedback_timer: Any = None
        self.render_started_at: float | None = None
        self.render_estimate_seconds: float | None = None
        self.render_animation_index = 0
        self.render_work_units: float | None = None
        self.render_perf_samples: list[float] = []

    def compose(self) -> ComposeResult:
        yield Container(
            Horizontal(
                Label("Res"),
                Select(
                    options=[
                        ("540×960", "540x960"),
                        ("720×1280", "720x1280"),
                        ("1080×1920", "1080x1920"),
                        ("1920×1080", "1920x1080"),
                    ],
                    value="540x960",
                    id="resolution-select",
                ),
                Label("Rate"),
                Select(
                    options=[
                        ("2M", "2M"),
                        ("5M", "5M"),
                        ("10M", "10M"),
                    ],
                    value="5M",
                    id="bitrate-select",
                ),
                id="toolbar-row-core",
            ),
            Horizontal(
                Label("Clip"),
                Select(
                    options=[
                        ("Auto", "auto"),
                        ("Custom", "manual"),
                    ],
                    value="auto",
                    id="duration-mode-select",
                ),
                Label("Secs"),
                Input(value="", placeholder="auto", id="duration-input"),
                id="toolbar-row-timing",
            ),
            Horizontal(
                Static(
                    "Preview Ctrl+P  Clipboard F6  Fix Save F7  Open Ctrl+O",
                    id="toolbar-hints",
                ),
                Button("Clipboard", id="clipboard-btn"),
                Button("▶ Render", id="render-btn", variant="primary"),
                id="toolbar-row-actions",
            ),
            id="toolbar",
        )
        yield Horizontal(
            Horizontal(
                Container(
                    Static("CODE", id="code-label"),
                    TextArea(
                        self.initial_code,
                        id="code-editor",
                    ),
                    id="code-pane",
                ),
                Container(
                    Static("RENDER STATUS", id="status-label"),
                    Static("Output Path", classes="status-field"),
                    Input(
                        value="",
                        placeholder="Custom folder or .mp4 path",
                        id="output-path-input",
                    ),
                    Static("Preview: starting…", id="preview-url", classes="status-field"),
                    Static("Output: —", id="output-path", classes="status-field"),
                    Static(
                        "Resolution: 540×960", id="disp-resolution", classes="status-field"
                    ),
                    Static("Bitrate: 5M", id="disp-bitrate", classes="status-field"),
                    Static("Duration: Auto", id="disp-duration", classes="status-field"),
                    Static("Estimate: —", id="disp-estimate", classes="status-field"),
                    Static("Elapsed: —", id="disp-elapsed", classes="status-field"),
                    Static("Activity: idle", id="render-activity", classes="status-field"),
                    Static("Status: Ready", id="render-status", classes="status-field"),
                    ProgressBar(id="render-progress", show_percentage=False),
                    Static("", id="result-text"),
                    id="status-pane",
                ),
                id="main-pane",
            )
        )

    def on_mount(self) -> None:
        editor = self.query_one("#code-editor", TextArea)
        editor.focus()
        self.preview_server.start()
        self.preview_server.update_code(editor.text)
        self.query_one("#preview-url", Static).update(f"Preview: {self.preview_server.url}")
        self._sync_output_display()
        if self.auto_open_preview:
            self.action_preview()

    def on_unmount(self) -> None:
        self._stop_render_feedback()
        self.preview_server.stop()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    @on(Select.Changed, "#resolution-select")
    def on_resolution_change(self, event: Select.Changed) -> None:
        self.query_one("#disp-resolution", Static).update(
            f"Resolution: {event.value or '540x960'}"
        )

    @on(Select.Changed, "#bitrate-select")
    def on_bitrate_change(self, event: Select.Changed) -> None:
        self.query_one("#disp-bitrate", Static).update(f"Bitrate: {event.value}")

    @on(Select.Changed, "#duration-mode-select")
    def on_duration_mode_change(self, _: Select.Changed) -> None:
        self._sync_duration_display()

    @on(Input.Changed, "#duration-input")
    def on_duration_change(self, event: Input.Changed) -> None:
        if event.value.strip():
            mode = self.query_one("#duration-mode-select", Select)
            if mode.value != "manual":
                mode.value = "manual"
                return
        self._sync_duration_display()

    @on(Input.Changed, "#output-path-input")
    def on_output_path_change(self, _: Input.Changed) -> None:
        self._sync_output_display()

    @on(Button.Pressed, "#render-btn")
    def on_render_pressed(self) -> None:
        self.action_render()

    @on(Button.Pressed, "#clipboard-btn")
    def on_clipboard_pressed(self) -> None:
        self.action_load_clipboard()

    @on(TextArea.Changed, "#code-editor")
    def on_editor_changed(self, event: TextArea.Changed) -> None:
        self.preview_server.update_code(event.text_area.text)
        self.query_one("#preview-url", Static).update(f"Preview: {self.preview_server.url}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_render(self) -> None:
        ta = self.query_one("#code-editor", TextArea)
        code = ta.text
        if not code.strip():
            self._set_status("Nothing to render — paste some HTML first.", error=True)
            return

        res_select = self.query_one("#resolution-select", Select)
        bitrate_select = self.query_one("#bitrate-select", Select)
        resolution = res_select.value or "540x960"
        bitrate = bitrate_select.value or "5M"
        width, height = map(int, resolution.split("x"))
        duration = self._resolve_duration(code)
        if duration is None:
            self._set_status(
                f"Enter a duration between 0.5 and {HARD_MAX_DURATION_SECONDS:.0f} seconds.",
                error=True,
            )
            return

        if self.render_worker and self.render_worker.is_running:
            self._set_status("Render already in progress.", error=True)
            return

        requested_output_path = self._resolve_output_path()
        if requested_output_path is None:
            self._set_status(
                "Enter a custom output folder or .mp4 path.",
                error=True,
            )
            return

        output_ok, path_notice = self._validate_output_target(requested_output_path)
        if not output_ok:
            if path_notice and "Controlled Folder Access" in path_notice:
                path_notice = f"{path_notice}\nPress F7 to open the Windows allow-list prompt."
            self._set_status("Selected folder is blocked.", error=True)
            self.query_one("#output-path", Static).update(f"Output: {requested_output_path}")
            self.query_one("#result-text", Static).update(path_notice)
            return

        output_path = requested_output_path
        content_mode = self._detect_render_mode(code)
        estimate_seconds = self._estimate_render_seconds(
            width=width,
            height=height,
            bitrate=str(bitrate),
            clip_duration=float(duration["max_duration"]),
            content_mode=content_mode,
        )
        self._set_status(
            f"Rendering at {resolution} {bitrate} for {duration['label']}...",
            busy=True,
        )
        self._start_render_feedback(
            estimate_seconds=estimate_seconds,
            width=width,
            height=height,
            clip_duration=float(duration["max_duration"]),
        )
        self.query_one("#output-path", Static).update(f"Output: {output_path}")
        self.query_one("#disp-duration", Static).update(f"Duration: {duration['label']}")

        self.render_worker = self._render_worker(
            code=code,
            width=width,
            height=height,
            bitrate=bitrate,
            min_duration=duration["min_duration"],
            max_duration=duration["max_duration"],
            output_path=str(output_path),
            path_notice="",
        )

    def action_clear_editor(self) -> None:
        self.query_one("#code-editor", TextArea).text = ""

    def action_load_clipboard(self) -> None:
        try:
            text = read_clipboard_text()
        except Exception as exc:
            self._set_status(f"Clipboard load failed: {exc}", error=True)
            self.notify(f"Clipboard load failed: {exc}", severity="error")
            return

        editor = self.query_one("#code-editor", TextArea)
        editor.text = text
        self.preview_server.update_code(text)
        self.query_one("#preview-url", Static).update(f"Preview: {self.preview_server.url}")
        self._set_status("Loaded code from clipboard.", busy=False)
        self.notify("Loaded code from clipboard.")
        editor.focus()

    def action_preview(self) -> None:
        editor = self.query_one("#code-editor", TextArea)
        self.preview_server.update_code(editor.text)
        url = self.preview_server.url
        self.query_one("#preview-url", Static).update(f"Preview: {url}")
        opened = webbrowser.open(url)
        if opened:
            self._set_status("Preview opened in browser.", busy=False)
        else:
            self._set_status("Preview server ready. Open the URL shown on the right.", busy=False)

    def action_enable_protected_saves(self) -> None:
        try:
            from .. import playwright_render

            launched, message = playwright_render.launch_controlled_folder_access_setup()
        except Exception as exc:
            self._set_status(f"Protected save setup failed: {exc}", error=True)
            self.notify(f"Protected save setup failed: {exc}", severity="error")
            return

        if launched:
            self._set_status(message, busy=False)
            self.notify(message)
        else:
            self._set_status(message, error=True)
            self.notify(message, severity="error")

    # ------------------------------------------------------------------
    # Render worker
    # ------------------------------------------------------------------

    @work(exclusive=True)
    async def _render_worker(
        self,
        code: str,
        width: int,
        height: int,
        bitrate: str,
        min_duration: float,
        max_duration: float,
        output_path: str,
        path_notice: str = "",
    ) -> None:
        video_path = Path(output_path)
        video_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "code": code,
            "width": width,
            "height": height,
            "bitrate": bitrate,
            "frameRate": 60,
            "maxDuration": max_duration,
            "minDuration": min_duration,
            "settleWindow": 0.45,
        }

        try:
            from .. import playwright_render

            loop = asyncio.get_running_loop()
            ffmpeg_exe = self._resolve_ffmpeg()
            result = await loop.run_in_executor(
                None,
                lambda: playwright_render.render_payload(
                    payload, str(video_path), ffmpeg_exe=ffmpeg_exe
                ),
            )

            duration = result.get("duration", 0.0)
            frame_count = result.get("frameCount", 0)
            mode = result.get("contentMode", "unknown")
            final_output_path = result.get("outputPath", str(video_path))
            save_warning = result.get("saveWarning", "")
            message_lines = [
                f"Rendered {duration:.2f}s  |  {frame_count} frames  |  mode: {mode}",
                f"Saved to: {final_output_path}",
            ]
            if path_notice:
                message_lines.append("")
                message_lines.append(path_notice)
            if save_warning:
                message_lines.append("")
                message_lines.append(save_warning)

            self.post_message(
                RenderComplete(
                    success=True,
                    message="\n".join(message_lines),
                    output_path=str(final_output_path),
                    content_mode=mode,
                    duration=duration,
                    frame_count=frame_count,
                    save_warning=save_warning,
                )
            )
        except Exception as exc:
            self.post_message(
                RenderComplete(
                    success=False,
                    message=f"Render failed: {exc}",
                    output_path=str(video_path),
                )
            )

    def on_render_complete(self, message: RenderComplete) -> None:
        actual_elapsed = self._stop_render_feedback()
        self.render_worker = None
        progress = self.query_one("#render-progress", ProgressBar)
        if message.success:
            self._record_render_sample(actual_elapsed)
            self._set_status("Ready", busy=False)
            progress.update(total=1, progress=1)
            self.query_one("#render-status", Static).update("✓ Render complete")
            self.query_one("#output-path", Static).update(f"Output: {message.output_path}")
            self.query_one("#render-activity", Static).update("Activity: done")
            if actual_elapsed is not None and self.render_estimate_seconds is not None:
                self.query_one("#disp-estimate", Static).update(
                    f"Estimate: {self._format_time(self.render_estimate_seconds)}  |  Actual: {self._format_time(actual_elapsed)}"
                )
                self.query_one("#disp-elapsed", Static).update(
                    f"Elapsed: {self._format_time(actual_elapsed)}"
                )
            el = self.query_one("#result-text", Static)
            el.update(message.message)
            el.remove_class("error")
        else:
            self._set_status("Ready", busy=False)
            progress.update(total=1, progress=0)
            self.query_one("#render-status", Static).update("✗ Render failed")
            self.query_one("#output-path", Static).update(f"Output: {message.output_path}")
            self.query_one("#render-activity", Static).update("Activity: failed")
            if actual_elapsed is not None:
                self.query_one("#disp-elapsed", Static).update(
                    f"Elapsed: {self._format_time(actual_elapsed)}"
                )
            el = self.query_one("#result-text", Static)
            el.update(message.message)
            el.add_class("error")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(
        self, message: str, busy: bool = False, error: bool = False
    ) -> None:
        el = self.query_one("#render-status", Static)
        if error:
            el.update(f"✗ {message}")
        elif busy:
            el.update(f"⏳ {message}")
        else:
            el.update(message)

    def _resolve_output_path(self) -> Path | None:
        raw = self.query_one("#output-path-input", Input).value.strip().strip('"').strip("'")
        if not raw:
            return None

        candidate = Path(raw).expanduser()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"clipacanvas_tui_{stamp}.mp4"

        if candidate.exists() and candidate.is_dir():
            return candidate / default_name

        if candidate.suffix.lower() == ".mp4":
            return candidate

        if raw.endswith(("\\", "/")) or not candidate.suffix:
            return candidate / default_name

        return candidate.with_suffix(".mp4")

    def _resolve_ffmpeg(self) -> str | None:
        env = (
            os.environ.get("CLIPACANVAS_FFMPEG_EXE")
            or os.environ.get("FFMPEG_EXE")
        )
        if env:
            return env

        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

        return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")

    def _estimate_render_seconds(
        self,
        width: int,
        height: int,
        bitrate: str,
        clip_duration: float,
        content_mode: str,
    ) -> float:
        frame_count = int(math.ceil(clip_duration * 60)) + 2
        megapixel_frames = max(1.0, (width * height * frame_count) / 1_000_000)
        mode_factor = 1.12 if content_mode == "canvas" else 0.96
        bitrate_factor = {"2M": 0.95, "5M": 1.0, "10M": 1.08}.get(bitrate, 1.0)
        baseline_seconds_per_unit = 0.055
        learned_seconds_per_unit = (
            sum(self.render_perf_samples) / len(self.render_perf_samples)
            if self.render_perf_samples
            else baseline_seconds_per_unit
        )
        estimated = 1.25 + (
            megapixel_frames
            * learned_seconds_per_unit
            * mode_factor
            * bitrate_factor
        )
        return max(2.0, estimated)

    def _start_render_feedback(
        self,
        estimate_seconds: float,
        width: int,
        height: int,
        clip_duration: float,
    ) -> None:
        self._stop_render_feedback()
        self.render_started_at = time.perf_counter()
        self.render_estimate_seconds = estimate_seconds
        self.render_animation_index = 0
        self.render_work_units = max(
            1.0,
            (width * height * (int(math.ceil(clip_duration * 60)) + 2)) / 1_000_000,
        )
        self.query_one("#render-progress", ProgressBar).update(total=100, progress=0)
        self.query_one("#disp-estimate", Static).update(
            f"Estimate: ~{self._format_time(estimate_seconds)}"
        )
        self.query_one("#disp-elapsed", Static).update("Elapsed: 0.0s")
        self.query_one("#render-activity", Static).update(
            f"Activity: {self.RENDER_ANIMATION_FRAMES[0]}"
        )
        self.query_one("#result-text", Static).update(
            "Preparing browser, frames, and encoder..."
        )
        self.render_feedback_timer = self.set_interval(0.12, self._tick_render_feedback)

    def _tick_render_feedback(self) -> None:
        if self.render_started_at is None or self.render_estimate_seconds is None:
            return

        elapsed = max(0.0, time.perf_counter() - self.render_started_at)
        remaining = max(0.0, self.render_estimate_seconds - elapsed)
        progress = min(96, int((elapsed / max(self.render_estimate_seconds, 0.1)) * 100))
        self.query_one("#render-progress", ProgressBar).update(total=100, progress=progress)
        self.query_one("#disp-elapsed", Static).update(
            f"Elapsed: {self._format_time(elapsed)}  |  Left: ~{self._format_time(remaining)}"
        )
        frame = self.RENDER_ANIMATION_FRAMES[
            self.render_animation_index % len(self.RENDER_ANIMATION_FRAMES)
        ]
        self.render_animation_index += 1
        self.query_one("#render-activity", Static).update(f"Activity: {frame}")
        self.query_one("#render-status", Static).update(f"{frame} Rendering...")

    def _stop_render_feedback(self) -> float | None:
        elapsed: float | None = None
        if self.render_started_at is not None:
            elapsed = max(0.0, time.perf_counter() - self.render_started_at)

        timer = self.render_feedback_timer
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass

        self.render_feedback_timer = None
        self.render_started_at = None
        return elapsed

    def _record_render_sample(self, actual_elapsed: float | None) -> None:
        if actual_elapsed is None or actual_elapsed <= 0 or not self.render_work_units:
            return

        seconds_per_unit = actual_elapsed / self.render_work_units
        self.render_perf_samples.append(seconds_per_unit)
        self.render_perf_samples = self.render_perf_samples[-6:]

    def _format_time(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        if seconds < 10:
            return f"{seconds:.1f}s"
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes = int(seconds // 60)
        remainder = int(round(seconds % 60))
        return f"{minutes}m {remainder:02d}s"

    def _validate_output_target(self, requested_output_path: Path) -> tuple[bool, str]:
        try:
            from .. import playwright_render

            return playwright_render.validate_output_target(requested_output_path)
        except Exception:
            return True, ""

    def _resolve_duration(self, code: str) -> dict[str, float | str] | None:
        mode = self.query_one("#duration-mode-select", Select).value or "auto"
        raw = self.query_one("#duration-input", Input).value.strip()
        if mode != "manual":
            mode = self._detect_render_mode(code)
            max_duration = 12.0 if mode == "canvas" else 6.0
            return {
                "label": f"Auto ({max_duration:.0f}s cap)",
                "min_duration": 0.35,
                "max_duration": max_duration,
            }

        if not raw:
            return None

        try:
            seconds = float(raw)
        except ValueError:
            return None

        if seconds < 0.5:
            return None

        seconds = min(HARD_MAX_DURATION_SECONDS, seconds)
        return {
            "label": f"{seconds:.2f}s",
            "min_duration": seconds,
            "max_duration": seconds,
        }

    def _describe_duration(self, raw: str) -> str:
        mode = self.query_one("#duration-mode-select", Select).value or "auto"
        if mode != "manual":
            return "Auto"

        value = raw.strip()
        if not value:
            return "Enter seconds"

        try:
            seconds = float(value)
        except ValueError:
            return "Invalid"

        if seconds < 0.5:
            return "Invalid"

        return f"{min(HARD_MAX_DURATION_SECONDS, seconds):.2f}s"

    def _detect_render_mode(self, code: str) -> str:
        text = str(code or "")
        if (
            "<canvas" in text.lower()
            or "getContext(" in text
            or "OffscreenCanvas" in text
        ):
            return "canvas"
        return "dom"

    def _sync_duration_display(self) -> None:
        value = self.query_one("#duration-input", Input).value
        self.query_one("#disp-duration", Static).update(
            f"Duration: {self._describe_duration(value)}"
        )

    def _sync_output_display(self) -> None:
        resolved = self._resolve_output_path()
        if resolved is not None:
            self.query_one("#output-path", Static).update(f"Output: {resolved}")
            return

        self.query_one("#output-path", Static).update("Output: Enter a folder or .mp4 path")
