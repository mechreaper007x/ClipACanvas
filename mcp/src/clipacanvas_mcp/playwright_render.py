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
from pathlib import Path

from playwright.sync_api import sync_playwright


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


def render_payload(payload: dict, output_path: str | Path, ffmpeg_exe: str | None = None) -> dict:
    ffmpeg_exe = ffmpeg_exe or os.environ.get("FFMPEG_EXE")
    if not ffmpeg_exe:
        raise RuntimeError("FFMPEG_EXE environment variable is required.")

    output_path = Path(output_path)
    code = payload["code"]
    width = int(payload["width"])
    height = int(payload["height"])
    bitrate = payload.get("bitrate", "5M")
    content_mode = payload.get("contentMode", "auto")
    frame_rate = int(payload.get("frameRate", 60))
    max_duration = float(payload.get("maxDuration", 12))
    min_duration = float(payload.get("minDuration", 0.35))
    settle_window = float(payload.get("settleWindow", 0.45))

    # Memory Optimization: Start FFmpeg with a pipe
    ffmpeg_cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-r", str(frame_rate),
        "-i", "-", # read from stdin
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "faster",
        "-b:v", bitrate,
        "-maxrate", bitrate,
        "-bufsize", bitrate,
        str(output_path),
    ]

    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

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
                meta = page.evaluate("() => (window.__clipacanvasCaptureMeta ? window.__clipacanvasCaptureMeta() : { activeAnimations: 0, suggestedDurationMs: 0 })")
                suggested_duration = max(min_duration, float(meta.get("suggestedDurationMs", 0) or 0) / 1000.0)
                if content_mode != "canvas" and suggested_duration <= min_duration:
                    suggested_duration = max(min_duration, min(max_duration, 6.0))
                elif suggested_duration > min_duration:
                    suggested_duration = min(max_duration, suggested_duration + 0.25)
                target_duration = min(max_duration, max(min_duration, suggested_duration))
                frame_total = int(math.ceil(target_duration * frame_rate)) + 2

                for index in range(frame_total):
                  t = round(index / frame_rate, 4)
                  page.evaluate("s => { if (window.__clipacanvasSetTime) window.__clipacanvasSetTime(s); }", t)
                  
                  content = page.screenshot(type="png")
                  signature = hash_frame(content)
                  
                  if not last_signature or signature != last_signature:
                      last_signature = signature
                      last_change_time = t

                  # Write directly to FFmpeg pipe
                  ffmpeg_proc.stdin.write(content)
                  frame_times.append(t)

                  meta = page.evaluate("() => (window.__clipacanvasCaptureMeta ? window.__clipacanvasCaptureMeta() : { activeAnimations: 0, suggestedDurationMs: 0 })")
                  idle_for = t - last_change_time
                  if t >= min_duration and idle_for >= settle_window and meta["activeAnimations"] == 0:
                      capped = False
                      break
            finally:
                browser.close()
                gc.collect() # Immediate cleanup

        # Close FFmpeg pipe to finish encoding
        ffmpeg_proc.stdin.close()
        stdout, stderr = ffmpeg_proc.communicate()
        if ffmpeg_proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip())

        return {
            "duration": frame_times[-1] if frame_times else 0,
            "frameCount": len(frame_times),
            "capped": capped,
            "contentMode": content_mode,
        }
    except Exception as e:
        if ffmpeg_proc.poll() is None:
            ffmpeg_proc.kill()
        raise e


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
