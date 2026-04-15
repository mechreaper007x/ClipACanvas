#!/usr/bin/env python3

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import gc
import base64
from functools import lru_cache
from pathlib import Path

from playwright.sync_api import sync_playwright

HARD_MAX_DURATION_SECONDS = 60.0


CONTROL_SCRIPT = r"""
(() => {
  const __state = {
    timeMs: 0,
    nextId: 1,
    timers: new Map(),
    rafQueue: []
  };

  const __RealDate = Date;

  function __MockDate(...args) {
    return args.length ? new __RealDate(...args) : new __RealDate(__state.timeMs);
  }

  __MockDate.UTC = __RealDate.UTC;
  __MockDate.parse = __RealDate.parse;
  __MockDate.now = () => __state.timeMs;
  __MockDate.prototype = __RealDate.prototype;
  window.Date = __MockDate;

  try {
    Object.defineProperty(window.performance, 'now', {
      configurable: true,
      value: () => __state.timeMs
    });
  } catch (_) {}

  function __scheduleTimer(cb, delay, repeat, args) {
    const id = __state.nextId++;
    const wait = Math.max(0, Number(delay) || 0);
    __state.timers.set(id, {
      id,
      cb,
      args,
      repeat,
      delay: repeat ? Math.max(1, wait) : wait,
      nextTime: __state.timeMs + wait
    });
    return id;
  }

  function __runCallback(cb, args) {
    try {
      if (typeof cb === 'function') cb(...args);
      else new Function(String(cb))();
    } catch (err) {
      console.error(err);
    }
  }

  function __runDueTimers(targetMs) {
    while (true) {
      let nextTimer = null;
      for (const timer of __state.timers.values()) {
        if (timer.nextTime <= targetMs && (!nextTimer || timer.nextTime < nextTimer.nextTime)) {
          nextTimer = timer;
        }
      }
      if (!nextTimer) break;
      __state.timeMs = nextTimer.nextTime;
      __runCallback(nextTimer.cb, nextTimer.args);
      if (nextTimer.repeat) nextTimer.nextTime += nextTimer.delay;
      else __state.timers.delete(nextTimer.id);
    }
  }

  function __flushAnimationFrame(nowMs) {
    const queue = __state.rafQueue.slice();
    __state.rafQueue.length = 0;
    queue.forEach(entry => {
      try {
        entry.cb(nowMs);
      } catch (err) {
        console.error(err);
      }
    });
  }

  function __syncAnimations(targetMs) {
    if (!document.getAnimations) return;
    document.getAnimations({ subtree: true }).forEach(anim => {
      try {
        anim.pause();
        anim.currentTime = targetMs;
      } catch (_) {}
    });
  }

  window.requestAnimationFrame = function(cb) {
    const id = __state.nextId++;
    __state.rafQueue.push({ id, cb });
    return id;
  };

  window.cancelAnimationFrame = function(id) {
    __state.rafQueue = __state.rafQueue.filter(entry => entry.id !== id);
  };

  window.setTimeout = function(cb, delay, ...args) {
    return __scheduleTimer(cb, delay, false, args);
  };

  window.setInterval = function(cb, delay, ...args) {
    return __scheduleTimer(cb, delay, true, args);
  };

  window.clearTimeout = function(id) {
    __state.timers.delete(id);
  };

  window.clearInterval = window.clearTimeout;

  window.__clipacanvasSetTime = function(seconds) {
    const targetMs = Math.max(0, (Number(seconds) || 0) * 1000);
    __runDueTimers(targetMs);
    __state.timeMs = targetMs;
    __syncAnimations(targetMs);
    __flushAnimationFrame(targetMs);
    return targetMs;
  };

  window.__clipacanvasCaptureMeta = function() {
    const animations = document.getAnimations ? document.getAnimations({ subtree: true }) : [];
    let activeAnimations = 0;
    let hasInfiniteAnimation = false;
    let suggestedDurationMs = 0;

    animations.forEach(anim => {
      try {
        const timing = anim.effect && typeof anim.effect.getComputedTiming === 'function'
          ? anim.effect.getComputedTiming()
          : null;
        const rawTiming = anim.effect && typeof anim.effect.getTiming === 'function'
          ? anim.effect.getTiming()
          : null;
        if (!timing) return;

        const delay = Math.max(0, Number(rawTiming && rawTiming.delay) || 0);
        const endDelay = Math.max(0, Number(rawTiming && rawTiming.endDelay) || 0);
        const duration = Math.max(0, Number(rawTiming && rawTiming.duration) || 0);
        const previewLoopMs = Math.max(250, delay + duration + endDelay);

        if (Number.isFinite(timing.endTime)) {
          suggestedDurationMs = Math.max(suggestedDurationMs, timing.endTime);
          if (__state.timeMs < timing.endTime) activeAnimations++;
        } else {
          activeAnimations++;
          hasInfiniteAnimation = true;
          suggestedDurationMs = Math.max(suggestedDurationMs, previewLoopMs);
        }
      } catch (_) {}
    });

    return {
      activeAnimations,
      hasInfiniteAnimation,
      suggestedDurationMs
    };
  };
})();
"""


def hash_frame(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def inject_control_script(code: str) -> str:
    script_tag = f"<script>{CONTROL_SCRIPT}</script>"
    lower = code.lower()

    head_index = lower.find("<head")
    if head_index != -1:
        head_end = code.find(">", head_index)
        if head_end != -1:
            return f"{code[:head_end + 1]}{script_tag}{code[head_end + 1:]}"

    html_index = lower.find("<html")
    if html_index != -1:
        html_end = code.find(">", html_index)
        if html_end != -1:
            return f"{code[:html_end + 1]}<head>{script_tag}</head>{code[html_end + 1:]}"

    return f"{script_tag}{code}"


def launch_chromium(playwright):
    launch_args = [
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--mute-audio",
        "--disable-gpu",
        "--js-flags=--max-old-space-size=256",
    ]

    try:
        return playwright.chromium.launch(headless=True, args=launch_args)
    except Exception as exc:
        message = str(exc)
        if "Executable doesn't exist" not in message and "playwright install" not in message:
            raise

        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )
        return playwright.chromium.launch(headless=True, args=launch_args)


def resolve_ffmpeg(ffmpeg_exe: str | None = None) -> str:
    ffmpeg_exe = (
        ffmpeg_exe
        or os.environ.get("CLIPACANVAS_FFMPEG_EXE")
        or os.environ.get("FFMPEG_EXE")
    )
    if ffmpeg_exe:
        return ffmpeg_exe

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    ffmpeg_exe = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg_exe:
        return ffmpeg_exe

    raise RuntimeError(
        "FFmpeg was not found. Install FFmpeg, or set CLIPACANVAS_FFMPEG_EXE / FFMPEG_EXE."
    )


def ensure_output_parent_exists(output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Could not prepare output folder: {output_path.parent} ({exc})"
        ) from exc


def move_encoded_video(temp_output_path: Path, output_path: Path) -> None:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
    except OSError as exc:
        raise RuntimeError(
            f"Could not prepare output path: {output_path} ({exc})"
        ) from exc

    try:
        temp_output_path.replace(output_path)
        return
    except OSError:
        pass

    try:
        shutil.copy2(temp_output_path, output_path)
        temp_output_path.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Failed to save rendered video to {output_path} ({exc})"
        ) from exc


def probe_output_parent_writable(output_path: Path) -> tuple[bool, str]:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"Could not prepare output folder: {output_path.parent} ({exc})"

    probe_handle: int | None = None
    probe_path: str | None = None
    try:
        probe_handle, probe_path = tempfile.mkstemp(
            prefix="clipacanvas_probe_",
            suffix=".tmp",
            dir=str(output_path.parent),
        )
        return True, ""
    except OSError as exc:
        return False, str(exc)
    finally:
        if probe_handle is not None:
            os.close(probe_handle)
        if probe_path:
            try:
                os.remove(probe_path)
            except OSError:
                pass


@lru_cache(maxsize=1)
def controlled_folder_access_enabled() -> bool:
    if not sys.platform.startswith("win"):
        return False

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-MpPreference).EnableControlledFolderAccess",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False

    return result.stdout.strip() == "1"


def protected_windows_library_names() -> set[str]:
    return {"Documents", "Pictures", "Videos", "Music"}


def is_under_protected_windows_library(path: Path) -> bool:
    if not sys.platform.startswith("win"):
        return False

    try:
        relative = path.resolve().relative_to(Path.home())
    except Exception:
        return False

    return bool(relative.parts) and relative.parts[0] in protected_windows_library_names()


def controlled_folder_access_note(requested_output_path: Path) -> str:
    if not controlled_folder_access_enabled():
        return ""
    if not is_under_protected_windows_library(requested_output_path):
        return ""

    return (
        "Windows Controlled Folder Access is enabled and is blocking direct saves "
        f"to this folder. To save here directly, allow this app/interpreter in "
        f"Windows Security: {current_process_image_path()}"
    )


def current_process_image_path() -> str:
    if not sys.platform.startswith("win"):
        return sys.executable

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        query_full_process_image_name = kernel32.QueryFullProcessImageNameW
        query_full_process_image_name.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        query_full_process_image_name.restype = wintypes.BOOL

        current_process = kernel32.GetCurrentProcess()
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        ok = query_full_process_image_name(
            current_process,
            0,
            buffer,
            ctypes.byref(size),
        )
        if ok:
            return buffer.value
    except Exception:
        pass

    return sys.executable


def build_controlled_folder_access_allow_script() -> str:
    runtime_path = current_process_image_path().replace("'", "''")
    return (
        f"Add-MpPreference -ControlledFolderAccessAllowedApplications '{runtime_path}'"
    )


def launch_controlled_folder_access_setup() -> tuple[bool, str]:
    if not sys.platform.startswith("win"):
        return False, "Controlled Folder Access setup is only available on Windows."

    script = build_controlled_folder_access_allow_script()
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Start-Process PowerShell "
                    "-Verb RunAs "
                    f"-ArgumentList @('-NoProfile','-EncodedCommand','{encoded}')"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        return False, f"Could not launch Windows setup helper: {exc}"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if stderr:
            return False, stderr
        return False, "Could not launch Windows setup helper."

    return (
        True,
        "Windows setup prompt opened. Approve the admin prompt, then rerun the render.",
    )


def validate_output_target(requested_output_path: Path) -> tuple[bool, str]:
    writable, reason = probe_output_parent_writable(requested_output_path)
    if writable:
        return True, ""

    cfa_note = controlled_folder_access_note(requested_output_path)
    if cfa_note:
        return (
            False,
            "Windows is blocking direct saves to this folder.\n"
            "Press F7 to allow Clip.A.Canvas in Controlled Folder Access, "
            "then render again.\n"
            f"{cfa_note}",
        )

    return (
        False,
        f"Selected output folder is not writable.\nReason: {reason}",
    )


def render_payload(payload: dict, output_path: str | Path, ffmpeg_exe: str | None = None) -> dict:
    ffmpeg_exe = resolve_ffmpeg(ffmpeg_exe)

    output_path = Path(output_path)
    ensure_output_parent_exists(output_path)
    code = payload["code"]
    width = int(payload["width"])
    height = int(payload["height"])
    bitrate = payload.get("bitrate", "5M")
    content_mode = payload.get("contentMode", "auto")
    frame_rate = int(payload.get("frameRate", 60))
    max_duration = min(
        HARD_MAX_DURATION_SECONDS,
        max(0.35, float(payload.get("maxDuration", 12))),
    )
    min_duration = min(max_duration, max(0.0, float(payload.get("minDuration", 0.35))))
    settle_window = float(payload.get("settleWindow", 0.45))

    with tempfile.TemporaryDirectory(prefix="clipacanvas_render_") as temp_dir:
        encoded_output_path = Path(temp_dir) / "render.mp4"

        # Encode to a temp file first, then move it to the final destination.
        # This avoids FFmpeg writing directly into Windows media folders that may
        # reject unknown executables even when Python can move files there.
        ffmpeg_cmd = [
            ffmpeg_exe,
            "-y",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-r", str(frame_rate),
            "-i", "-",  # read from stdin
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "faster",
            "-b:v", bitrate,
            "-maxrate", bitrate,
            "-bufsize", bitrate,
            str(encoded_output_path),
        ]

        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        frame_times: list[float] = []
        last_signature = ""
        last_change_time = 0.0
        capped = True

        try:
            with sync_playwright() as playwright:
                browser = launch_chromium(playwright)
                try:
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        screen={"width": width, "height": height},
                        device_scale_factor=1,
                        color_scheme="dark",
                    )
                    page = context.new_page()
                    page.set_content(inject_control_script(code), wait_until="load")
                    page.evaluate(
                        """async () => {
                            try {
                                if (document.fonts && document.fonts.ready) {
                                    await document.fonts.ready;
                                }
                            } catch (_) {}
                        }"""
                    )
                    meta = page.evaluate(
                        "() => (window.__clipacanvasCaptureMeta ? window.__clipacanvasCaptureMeta() : { activeAnimations: 0, suggestedDurationMs: 0 })"
                    )
                    suggested_duration = max(
                        min_duration,
                        float(meta.get("suggestedDurationMs", 0) or 0) / 1000.0,
                    )
                    if content_mode != "canvas" and suggested_duration <= min_duration:
                        suggested_duration = max(min_duration, min(max_duration, 6.0))
                    elif suggested_duration > min_duration:
                        suggested_duration = min(max_duration, suggested_duration + 0.25)
                    target_duration = min(
                        max_duration, max(min_duration, suggested_duration)
                    )
                    frame_total = int(math.ceil(target_duration * frame_rate)) + 2

                    for index in range(frame_total):
                        t = round(index / frame_rate, 4)
                        page.evaluate(
                            "s => { if (window.__clipacanvasSetTime) window.__clipacanvasSetTime(s); }",
                            t,
                        )

                        content = page.screenshot(type="png")
                        signature = hash_frame(content)

                        if not last_signature or signature != last_signature:
                            last_signature = signature
                            last_change_time = t

                        if not ffmpeg_proc.stdin:
                            raise RuntimeError("FFmpeg pipe closed unexpectedly.")
                        ffmpeg_proc.stdin.write(content)
                        frame_times.append(t)

                        meta = page.evaluate(
                            "() => (window.__clipacanvasCaptureMeta ? window.__clipacanvasCaptureMeta() : { activeAnimations: 0, suggestedDurationMs: 0 })"
                        )
                        idle_for = t - last_change_time
                        if (
                            t >= min_duration
                            and idle_for >= settle_window
                            and meta["activeAnimations"] == 0
                        ):
                            capped = False
                            break
                finally:
                    browser.close()
                    gc.collect()  # Immediate cleanup

            if ffmpeg_proc.stdin and not ffmpeg_proc.stdin.closed:
                ffmpeg_proc.stdin.close()
            stderr = ffmpeg_proc.stderr.read() if ffmpeg_proc.stderr else b""
            if ffmpeg_proc.wait() != 0:
                raise RuntimeError(stderr.decode(errors="replace").strip())

            move_encoded_video(encoded_output_path, output_path)

            return {
                "duration": frame_times[-1] if frame_times else 0,
                "frameCount": len(frame_times),
                "capped": capped,
                "contentMode": content_mode,
                "outputPath": str(output_path),
                "saveWarning": "",
            }
        except Exception as e:
            if ffmpeg_proc.poll() is None:
                if ffmpeg_proc.stdin and not ffmpeg_proc.stdin.closed:
                    try:
                        ffmpeg_proc.stdin.close()
                    except OSError:
                        pass
                ffmpeg_proc.kill()
            raise e
        finally:
            if ffmpeg_proc.stderr:
                ffmpeg_proc.stderr.close()


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python playwright_render.py <input.json> <output.mp4>", file=sys.stderr)
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        result = render_payload(payload, output_path)
        print(json.dumps(result), file=sys.stderr)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
