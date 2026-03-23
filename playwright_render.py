#!/usr/bin/env python3

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
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

  window.__code2videoSetTime = function(seconds) {
    const targetMs = Math.max(0, (Number(seconds) || 0) * 1000);
    __runDueTimers(targetMs);
    __state.timeMs = targetMs;
    __syncAnimations(targetMs);
    __flushAnimationFrame(targetMs);
    return targetMs;
  };

  window.__code2videoCaptureMeta = function() {
    const animations = document.getAnimations ? document.getAnimations({ subtree: true }) : [];
    let activeAnimations = 0;
    let hasInfiniteAnimation = false;

    animations.forEach(anim => {
      try {
        const timing = anim.effect && typeof anim.effect.getComputedTiming === 'function'
          ? anim.effect.getComputedTiming()
          : null;
        if (!timing) return;

        if (Number.isFinite(timing.endTime)) {
          if (__state.timeMs < timing.endTime) activeAnimations++;
        } else {
          activeAnimations++;
          hasInfiniteAnimation = true;
        }
      } catch (_) {}
    });

    return {
      activeAnimations,
      hasInfiniteAnimation
    };
  };
})();
"""


def hash_frame(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def run_ffmpeg(ffmpeg_exe: str, args: list[str]) -> None:
    result = subprocess.run(
        [ffmpeg_exe, *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffmpeg exited with code {result.returncode}")


def capture_frames(page, frame_rate: int, max_duration: float, min_duration: float, settle_window: float, temp_dir: str):
    frame_total = int(math.ceil(max_duration * frame_rate)) + 2
    frame_times: list[float] = []
    last_signature = ""
    last_change_time = 0.0

    for index in range(frame_total):
      t = round(index / frame_rate, 4)
      page.evaluate(
          """seconds => {
              if (typeof window.__code2videoSetTime === 'function') {
                  window.__code2videoSetTime(seconds);
              }
          }""",
          t,
      )
      content = page.screenshot(type="png")
      signature = hash_frame(content)
      if not last_signature or signature != last_signature:
          last_signature = signature
          last_change_time = t

      frame_path = Path(temp_dir) / f"frame{index:05d}.png"
      frame_path.write_bytes(content)
      frame_times.append(t)

      meta = page.evaluate(
          """() => (
              typeof window.__code2videoCaptureMeta === 'function'
                  ? window.__code2videoCaptureMeta()
                  : { activeAnimations: 0, hasInfiniteAnimation: false }
          )"""
      )
      idle_for = t - last_change_time
      settled = t >= min_duration and idle_for >= settle_window and meta["activeAnimations"] == 0
      if settled:
          return frame_times, False

    return frame_times, True


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python playwright_render.py <input.json> <output.mp4>", file=sys.stderr)
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    ffmpeg_exe = os.environ.get("FFMPEG_EXE")
    if not ffmpeg_exe:
        print("FFMPEG_EXE environment variable is required.", file=sys.stderr)
        return 1

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    code = payload["code"]
    width = int(payload["width"])
    height = int(payload["height"])
    bitrate = payload.get("bitrate", "5M")
    frame_rate = int(payload.get("frameRate", 60))
    max_duration = float(payload.get("maxDuration", 12))
    min_duration = float(payload.get("minDuration", 0.35))
    settle_window = float(payload.get("settleWindow", 0.45))

    temp_dir = tempfile.mkdtemp(prefix="code2video-playwright-")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--hide-scrollbars", "--mute-audio"],
            )
            try:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    screen={"width": width, "height": height},
                    device_scale_factor=1,
                    color_scheme="dark",
                )
                page = context.new_page()
                page.add_init_script(CONTROL_SCRIPT)
                page.set_content(code, wait_until="load")
                page.evaluate(
                    """async () => {
                        try {
                            if (document.fonts && document.fonts.ready) {
                                await document.fonts.ready;
                            }
                        } catch (_) {}
                    }"""
                )

                frame_times, capped = capture_frames(
                    page,
                    frame_rate=frame_rate,
                    max_duration=max_duration,
                    min_duration=min_duration,
                    settle_window=settle_window,
                    temp_dir=temp_dir,
                )
            finally:
                browser.close()

        run_ffmpeg(
            ffmpeg_exe,
            [
                "-y",
                "-framerate", str(frame_rate),
                "-i", str(Path(temp_dir) / "frame%05d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "fast",
                "-b:v", bitrate,
                "-maxrate", bitrate,
                "-bufsize", bitrate,
                str(output_path),
            ],
        )
        print(
            json.dumps(
                {
                    "duration": frame_times[-1] if frame_times else 0,
                    "frameCount": len(frame_times),
                    "capped": capped,
                }
            ),
            file=sys.stderr,
        )
        return 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
