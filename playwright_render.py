#!/usr/bin/env python3

import base64
import hashlib
import html
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

HARD_MAX_DURATION_SECONDS = 60.0

_CODEC_ENCODERS = {
    "h264": "libx264",
    "h265": "libx265",
    "hevc": "libx265",
    "vp9": "libvpx-vp9",
    "vp8": "libvpx",
    "av1": "libaom-av1",
    "prores": "prores_ks",
    "gif": "gif",
}

# Hardware encoders are only used when GPU boost asks for them and the local
# ffmpeg + driver can actually run the encoder.
_HW_ENCODERS = {
    "h264": ("h264_nvenc", "h264_qsv", "h264_amf"),
    "h265": ("hevc_nvenc", "hevc_qsv", "hevc_amf"),
    "hevc": ("hevc_nvenc", "hevc_qsv", "hevc_amf"),
}
_HW_ENCODER_PROBES: dict = {}


def _encoder_usable(ffmpeg_exe: str, encoder: str) -> bool:
    key = (ffmpeg_exe, encoder)
    cached = _HW_ENCODER_PROBES.get(key)
    if cached is not None:
        return cached
    usable = False
    try:
        probe = subprocess.run(
            [
                ffmpeg_exe, "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=64x64:r=1",
                "-frames:v", "1", "-c:v", encoder, "-f", "null", "-",
            ],
            capture_output=True,
            timeout=20,
        )
        usable = probe.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        usable = False
    _HW_ENCODER_PROBES[key] = usable
    return usable


def resolve_video_encoder(codec: str, ffmpeg_exe: str, gpu_boost: bool) -> str:
    cpu_encoder = _CODEC_ENCODERS.get(codec, "libx264")
    if not gpu_boost:
        return cpu_encoder
    for encoder in _HW_ENCODERS.get(codec, ()):
        if _encoder_usable(ffmpeg_exe, encoder):
            return encoder
    return cpu_encoder


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

  window.__clipacanvasMediaSeek = function(seconds) {
    const target = Math.max(0, Number(seconds) || 0);
    const videos = Array.from(document.querySelectorAll('video'));
    if (!videos.length) return Promise.resolve();
    return Promise.all(videos.map(video => new Promise(resolve => {
      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        video.removeEventListener('seeked', finish);
        video.removeEventListener('error', finish);
        resolve();
      };
      try { video.pause(); } catch (_) {}
      if (video.error || video.readyState < 1) { finish(); return; }
      const duration = Number(video.duration);
      const sourceIn = Math.max(0, Number(video.dataset.sourceIn) || 0);
      const absoluteTarget = sourceIn + target;
      let seekTo = absoluteTarget;
      if (Number.isFinite(duration) && duration > 0) {
        seekTo = video.hasAttribute('data-source-in')
          ? Math.min(absoluteTarget, Math.max(0, duration - 0.001))
          : Math.min(Math.max(0, target % duration), Math.max(0, duration - 0.001));
      }
      if (Math.abs(video.currentTime - seekTo) < 0.02 && video.readyState >= 2) { finish(); return; }
      video.addEventListener('seeked', finish, { once: true });
      video.addEventListener('error', finish, { once: true });
      try { video.currentTime = seekTo; } catch (_) { finish(); }
    })));
  };

  window.__clipacanvasAwaitMedia = function() {
    return window.__clipacanvasMediaReady || Promise.resolve();
  };

  window.__clipacanvasSetTime = function(seconds) {
    const targetMs = Math.max(0, (Number(seconds) || 0) * 1000);
    __runDueTimers(targetMs);
    __state.timeMs = targetMs;
    __syncAnimations(targetMs);
    try {
      document.documentElement.style.setProperty('--cc-time', String(targetMs / 1000) + 's');
      window.dispatchEvent(new CustomEvent('cc-seek', { detail: { time: targetMs / 1000 } }));
    } catch (_) {}
    __flushAnimationFrame(targetMs);
    window.__clipacanvasMediaReady = window.__clipacanvasMediaSeek(targetMs / 1000);
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


def build_sequence_document(clips: list[dict], transitions: list[dict] | None = None, engine_source: str = "") -> str:
    """Compose layered logic-box clips into one page whose virtual clock spans the sequence.

    Transitions are evaluated by the shared frontend engine (embedded verbatim),
    so the Program Monitor and the export blend from the same progress math.
    """
    frames = []
    cursor_ms = 0
    for clip in clips:
        duration_ms = max(1, int(round(float(clip["duration"]) * 1000)))
        raw_start = clip.get("start")
        if raw_start is None:
            start_ms = cursor_ms
        else:
            start_ms = int(round(max(0.0, float(raw_start)) * 1000))
        start_ms = min(max(0, 60000 - duration_ms), max(0, start_ms))
        try:
            track = max(0, min(7, int(clip.get("track") or 0)))
        except (TypeError, ValueError):
            track = 0
        frames.append({
            "id": str(clip.get("id") or ""),
            "start": start_ms,
            "duration": duration_ms,
            "track": track,
            "html": inject_control_script(str(clip["code"])),
        })
        cursor_ms = max(cursor_ms, start_ms + duration_ms)
    frames.sort(key=lambda frame: (frame["track"], frame["start"]))
    total_ms = max((frame["start"] + frame["duration"] for frame in frames), default=0)

    frame_tags = "\n".join(
        '<iframe class="cc-clip" data-clip-id="{clip_id}" data-start="{start}" data-duration="{duration}" data-track="{track}" '
        'style="z-index:{zindex}" srcdoc="{html}"></iframe>'.format(
            clip_id=html.escape(frame["id"], quote=True),
            start=frame["start"],
            duration=frame["duration"],
            track=frame["track"],
            zindex=(frame["track"] + 1) * 100,
            html=html.escape(frame["html"], quote=True),
        )
        for frame in frames
    )
    transition_json = json.dumps(transitions or [], ensure_ascii=False).replace("<", "\\u003c")
    safe_engine = engine_source.replace("</script", "<\\/script") if engine_source else ""
    engine_tag = f"<script>{safe_engine}</script>" if safe_engine else ""

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; background: #000; overflow: hidden; }}
  .cc-clip {{ position: absolute; inset: 0; width: 100%; height: 100%; border: 0; display: block; visibility: hidden; transform-origin: center center; }}
</style>
</head>
<body>
{frame_tags}
{engine_tag}
<script>
(function () {{
  var frames = Array.prototype.slice.call(document.querySelectorAll('.cc-clip'));
  var layers = frames.map(function (frame) {{
    return {{
      el: frame,
      clipId: frame.getAttribute('data-clip-id') || '',
      start: (Number(frame.dataset.start) || 0) / 1000,
      duration: (Number(frame.dataset.duration) || 0) / 1000,
      track: Number(frame.dataset.track) || 0
    }};
  }});
  var transitions = {transition_json};
  var totalMs = {total_ms};
  var runtime = window.CCTransitions || null;
  var lastActive = [];

  function fallbackActiveAt(ms) {{
    var seconds = ms / 1000;
    var active = [];
    for (var index = 0; index < layers.length; index++) {{
      var layer = layers[index];
      if (seconds >= layer.start && seconds < layer.start + layer.duration) {{
        active.push({{ index: index, clipId: layer.clipId, local: seconds - layer.start }});
      }}
    }}
    return {{ active: active, transitions: [] }};
  }}

  window.__clipacanvasSetTime = async function (seconds) {{
    var ms = Math.max(0, (Number(seconds) || 0) * 1000);
    var result;
    if (runtime && runtime.applyAt) {{
      result = runtime.applyAt(document.body, ms / 1000, layers, transitions);
    }} else {{
      result = fallbackActiveAt(ms);
      for (var index = 0; index < layers.length; index++) {{
        layers[index].el.style.visibility = ms / 1000 >= layers[index].start && ms / 1000 < layers[index].start + layers[index].duration ? 'visible' : 'hidden';
      }}
    }}
    lastActive = result.active || [];
    var waits = [];
    for (var cursor = 0; cursor < lastActive.length; cursor++) {{
      var entry = lastActive[cursor];
      var childFrame = frames[entry.index];
      if (!childFrame) continue;
      try {{
        var child = childFrame.contentWindow;
        if (child && child.__clipacanvasSetTime) {{
          child.__clipacanvasSetTime(entry.local);
        }}
        if (child && child.__clipacanvasAwaitMedia) {{
          waits.push(child.__clipacanvasAwaitMedia());
        }}
      }} catch (error) {{}}
    }}
    if (waits.length) {{
      try {{ await Promise.all(waits); }} catch (error) {{}}
    }}
    return ms;
  }};

  window.__clipacanvasCaptureMeta = function () {{
    var activeAnimations = 0;
    for (var cursor = 0; cursor < lastActive.length; cursor++) {{
      try {{
        var activeFrame = frames[lastActive[cursor].index];
        if (!activeFrame) continue;
        var child = activeFrame.contentWindow;
        if (child && child.__clipacanvasCaptureMeta) {{
          var meta = child.__clipacanvasCaptureMeta();
          activeAnimations += Math.max(0, Number(meta.activeAnimations) || 0);
        }}
      }} catch (error) {{}}
    }}
    return {{ activeAnimations: activeAnimations, suggestedDurationMs: totalMs }};
  }};

  window.__ccReady = async function () {{
    for (var index = 0; index < frames.length; index++) {{
      var frame = frames[index];
      try {{
        var doc = frame.contentDocument;
        if (doc && doc.readyState !== 'complete') {{
          await new Promise(function (resolve) {{
            frame.addEventListener('load', resolve, {{ once: true }});
          }});
        }}
        var child = frame.contentWindow;
        if (!child) continue;
        try {{ if (child.document.fonts && child.document.fonts.ready) await child.document.fonts.ready; }} catch (error) {{}}
        try {{
          await Promise.all(Array.from(child.document.images || []).map(function (img) {{
            if (img.complete && img.naturalWidth) return Promise.resolve();
            return new Promise(function (resolve) {{
              img.onload = resolve;
              img.onerror = resolve;
            }});
          }}));
        }} catch (error) {{}}
        try {{
          var videos = Array.from(child.document.querySelectorAll('video') || []);
          await Promise.all(videos.map(function (video) {{
            if (video.readyState >= 2) return Promise.resolve();
            return new Promise(function (resolve) {{
              var settled = false;
              var finish = function () {{
                if (settled) return;
                settled = true;
                video.removeEventListener('loadeddata', finish);
                video.removeEventListener('error', finish);
                resolve();
              }};
              video.addEventListener('loadeddata', finish, {{ once: true }});
              video.addEventListener('error', finish, {{ once: true }});
            }});
          }}));
        }} catch (error) {{}}
        try {{ if (typeof child.__ccReady === 'function') await child.__ccReady(); }} catch (error) {{}}
        try {{ if (typeof child.__clipacanvasReady === 'function') await child.__clipacanvasReady(); }} catch (error) {{}}
      }} catch (error) {{}}
    }}
    await window.__clipacanvasSetTime(0);
  }};

  window.__clipacanvasSequence = {{ totalMs: totalMs, count: frames.length }};
}})();
</script>
</body>
</html>"""


def _handle_route(route) -> None:
    url = route.request.url
    if not url.startswith("http") or (
        "127.0.0.1" in url or "localhost" in url or "10.0.2.2" in url
    ):
        route.continue_()
        return
    # Allow external resources (CDN libraries, fonts, APIs) but fail fast
    # when offline so renders don't hang waiting on unreachable hosts.
    try:
        response = route.fetch(timeout=8000)
        route.fulfill(response=response)
    except Exception:
        route.abort()


def render_payload(payload: dict, output_path: str | Path, ffmpeg_exe: str | None = None) -> dict:
    ffmpeg_exe = ffmpeg_exe or os.environ.get("FFMPEG_EXE")
    if not ffmpeg_exe:
        raise RuntimeError("FFMPEG_EXE environment variable is required.")

    output_path = Path(output_path)
    frame_dir_value = str(payload.get("frameDir") or "").strip()
    frame_dir_path = Path(frame_dir_value) if frame_dir_value else None
    if frame_dir_path is not None:
        try:
            frame_dir_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            frame_dir_path = None
    raw_clips = payload.get("clips")
    clips: list[dict] = []
    clip_cursor = 0.0
    if isinstance(raw_clips, list):
        for raw_clip in raw_clips[:40]:
            if not isinstance(raw_clip, dict):
                continue
            clip_code = str(raw_clip.get("code") or "")
            if not clip_code.strip():
                continue
            try:
                clip_duration = min(
                    HARD_MAX_DURATION_SECONDS,
                    max(0.2, float(raw_clip.get("duration") or 0)),
                )
            except (TypeError, ValueError):
                clip_duration = 0.2
            try:
                clip_start = max(0.0, float(raw_clip.get("start")))
            except (TypeError, ValueError):
                clip_start = clip_cursor
            clip_start = min(max(0.0, HARD_MAX_DURATION_SECONDS - clip_duration), clip_start)
            try:
                clip_track = max(0, min(7, int(raw_clip.get("track") or 0)))
            except (TypeError, ValueError):
                clip_track = 0
            clips.append({
                "id": str(raw_clip.get("id") or ""),
                "code": clip_code,
                "duration": clip_duration,
                "start": clip_start,
                "track": clip_track,
            })
            clip_cursor = max(clip_cursor, clip_start + clip_duration)
    sequence_mode = bool(clips)
    sequence_duration = min(
        HARD_MAX_DURATION_SECONDS,
        max((clip["start"] + clip["duration"] for clip in clips), default=0.0),
    )
    code = payload.get("code") or (
        "\n\n".join(clip["code"] for clip in clips) if clips else ""
    )
    if not str(code).strip():
        raise ValueError("Render payload has no animation code.")
    width = int(payload["width"])
    height = int(payload["height"])
    bitrate = payload.get("bitrate", "5M")
    content_mode = "dom" if sequence_mode else payload.get("contentMode", "auto")
    frame_rate = int(payload.get("frameRate", 60))
    max_duration = min(
        HARD_MAX_DURATION_SECONDS,
        max(0.35, float(payload.get("maxDuration", 12))),
    )
    min_duration = min(max_duration, max(0.0, float(payload.get("minDuration", 0.35))))
    settle_window = float(payload.get("settleWindow", 0.45))
    codec = str(payload.get("codec", "h264")).lower().strip()
    if codec not in _CODEC_ENCODERS:
        codec = "h264"
    audio_path = str(payload.get("audioPath") or payload.get("audio_path") or "").strip()
    # GIF delay resolution is 10ms, so cap the capture rate instead of letting
    # ffmpeg round (or reject) high frame rates.
    if codec == "gif" and frame_rate > 50:
        frame_rate = 50
    render_start_seconds = max(0.0, float(payload.get("renderStart", payload.get("render_start", 0)) or 0))
    render_start_seconds = min(render_start_seconds, HARD_MAX_DURATION_SECONDS)
    raw_end = payload.get("renderEnd", payload.get("render_end"))
    render_end_explicit = raw_end is not None and str(raw_end).strip() != ""
    render_end_seconds = None
    if render_end_explicit:
        render_end_seconds = min(
            max(0.0, float(raw_end)),
            HARD_MAX_DURATION_SECONDS,
        )
    if sequence_mode:
        render_start_seconds = min(render_start_seconds, max(0.0, sequence_duration - 0.05))
        render_end_seconds = min(render_end_seconds or sequence_duration, sequence_duration)
        render_end_explicit = True
    if render_end_explicit and render_end_seconds <= render_start_seconds:
        raise ValueError("Render end must be greater than render start.")
    if audio_path:
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise RuntimeError(f"Audio file not found: {audio_path}")
        audio_path = str(audio_file.resolve())
    else:
        audio_path = ""
    audio_clips: list[dict] = []
    raw_audio_clips = payload.get("audioClips")
    if isinstance(raw_audio_clips, list) and codec != "gif":
        for raw_clip in raw_audio_clips[:16]:
            if not isinstance(raw_clip, dict):
                continue
            clip_path = str(raw_clip.get("path") or "").strip()
            if not clip_path or not Path(clip_path).is_file():
                continue
            try:
                audio_clips.append({
                    "path": clip_path,
                    "start": max(0.0, float(raw_clip.get("start") or 0)),
                    "sourceIn": max(0.0, float(raw_clip.get("sourceIn") or 0)),
                    "duration": max(0.05, float(raw_clip.get("duration") or 0)),
                })
            except (TypeError, ValueError):
                continue

    transition_clips = {clip["id"] for clip in clips if clip["id"]}
    transitions: list[dict] = []
    transition_engine = ""
    raw_transitions = payload.get("transitions")
    if isinstance(raw_transitions, list) and sequence_mode:
        for raw_transition in raw_transitions[:40]:
            if not isinstance(raw_transition, dict):
                continue
            from_id = str(raw_transition.get("fromClipId") or "")
            to_id = str(raw_transition.get("toClipId") or "")
            if not from_id or not to_id or from_id == to_id:
                continue
            if from_id not in transition_clips or to_id not in transition_clips:
                continue
            try:
                transition_duration = min(3.0, max(0.1, float(raw_transition.get("duration") or 0.6)))
            except (TypeError, ValueError):
                transition_duration = 0.6
            try:
                transition_cut = max(0.0, float(raw_transition.get("cut") or 0))
            except (TypeError, ValueError):
                transition_cut = 0.0
            try:
                transition_track = max(0, min(7, int(raw_transition.get("track") or 0)))
            except (TypeError, ValueError):
                transition_track = 0
            params = raw_transition.get("params")
            transitions.append({
                "id": str(raw_transition.get("id") or f"tr-{len(transitions)}")[:40],
                "fromClipId": from_id,
                "toClipId": to_id,
                "type": str(raw_transition.get("type") or "dissolve")[:32],
                "duration": transition_duration,
                "alignment": raw_transition.get("alignment") if raw_transition.get("alignment") in ("center", "start", "end") else "center",
                "cut": transition_cut,
                "track": transition_track,
                "params": params if isinstance(params, dict) else {},
                "code": str(raw_transition.get("code") or "")[:8000],
            })
        if transitions:
            engine = str(payload.get("transitionEngine") or "")
            if 0 < len(engine) <= 80000 and "CCTransitions" in engine:
                transition_engine = engine

    gpu_boost = bool(payload.get("gpuBoost") or payload.get("gpu_boost"))
    video_codec = resolve_video_encoder(codec, ffmpeg_exe, gpu_boost)    # GPU boost also captures frames as high-quality JPEG: PNG encoding is the
    # biggest CPU cost in the capture loop, JPEG cuts render time noticeably.
    frame_image_format = "jpeg" if gpu_boost else "png"
    # Memory Optimization: Start FFmpeg with a pipe
    ffmpeg_cmd = [ffmpeg_exe, "-y"]

    if audio_path:
        ffmpeg_cmd += ["-i", audio_path]
    for audio_clip in audio_clips:
        ffmpeg_cmd += ["-i", audio_clip["path"]]
    video_input_index = (1 if audio_path else 0) + len(audio_clips)

    ffmpeg_cmd += [
        "-f", "image2pipe",
        "-vcodec", "mjpeg" if frame_image_format == "jpeg" else "png",
        "-r", str(frame_rate),
        "-i", "-",  # read from stdin
    ]
    ffmpeg_cmd += ["-c:v", video_codec]
    if codec == "gif":
        # GIF ships an 8-bit palette; build it per render for clean gradients.
        ffmpeg_cmd += [
            "-vf", "split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5",
            "-loop", "0",
        ]
    else:
        ffmpeg_cmd += ["-pix_fmt", "yuv422p10le" if codec == "prores" else "yuv420p"]

    if video_codec == "libx264":
        ffmpeg_cmd += ["-preset", "faster", "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    elif video_codec == "libx265":
        ffmpeg_cmd += ["-preset", "medium", "-tag:v", "hvc1", "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    elif video_codec.endswith("_nvenc"):
        ffmpeg_cmd += ["-preset", "p4", "-tune", "hq", "-rc", "vbr", "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
        if codec in ("h265", "hevc"):
            ffmpeg_cmd += ["-tag:v", "hvc1"]
    elif video_codec.endswith("_amf"):
        ffmpeg_cmd += ["-quality", "balanced", "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    elif video_codec.endswith("_qsv"):
        ffmpeg_cmd += ["-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    elif video_codec == "libvpx-vp9":
        ffmpeg_cmd += ["-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    elif video_codec == "libvpx":
        ffmpeg_cmd += ["-deadline", "good", "-cpu-used", "2", "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    elif video_codec == "libaom-av1":
        ffmpeg_cmd += ["-cpu-used", "8", "-row-mt", "1", "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]
    elif video_codec == "prores_ks":
        ffmpeg_cmd += ["-profile:v", "3", "-vendor", "apl0"]
    elif video_codec == "gif":
        pass
    else:
        ffmpeg_cmd += ["-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bitrate]

    if audio_path and codec != "gif" and not audio_clips:
        audio_codec = "libopus" if codec in ("vp9", "vp8", "av1") else "aac"
        ffmpeg_cmd += ["-c:a", audio_codec]
        if render_end_seconds is not None:
            ffmpeg_cmd += ["-t", f"{max(0.1, render_end_seconds - render_start_seconds):.3f}"]
        else:
            ffmpeg_cmd += ["-shortest"]
    elif audio_clips and codec != "gif":
        # Timeline audio is mixed under the captured frames on its own clock:
        # trim the source in/out, then delay each clip to its sequence start.
        filter_parts: list[str] = []
        mix_labels: list[str] = []
        if audio_path:
            filter_parts.append("[0:a]anull[a0]")
            mix_labels.append("[a0]")
        audio_input_index = 1 if audio_path else 0
        for clip_index, audio_clip in enumerate(audio_clips):
            relative_start = audio_clip["start"] - render_start_seconds
            source_in = audio_clip["sourceIn"]
            clip_duration = audio_clip["duration"]
            if relative_start < 0:
                source_in += -relative_start
                clip_duration += relative_start
                relative_start = 0.0
            if clip_duration <= 0.05:
                continue
            label = f"a{len(mix_labels)}"
            delay_ms = int(round(relative_start * 1000))
            filter_parts.append(
                f"[{audio_input_index + clip_index}:a]"
                f"atrim=start={source_in:.3f}:duration={clip_duration:.3f},"
                f"asetpts=PTS-STARTPTS,"
                f"adelay=delays={delay_ms}:all=1[{label}]"
            )
            mix_labels.append(f"[{label}]")
        if not mix_labels:
            filter_parts = []
        if len(mix_labels) == 1:
            filter_parts.append(f"{mix_labels[0]}anull[mixa]")
        elif len(mix_labels) > 1:
            filter_parts.append(
                "".join(mix_labels)
                + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0[mixa]"
            )
        if filter_parts:
            ffmpeg_cmd += [
                "-filter_complex", ";".join(filter_parts),
                "-map", f"{video_input_index}:v",
                "-map", "[mixa]",
            ]
            audio_codec = "libopus" if codec in ("vp9", "vp8", "av1") else "aac"
            ffmpeg_cmd += ["-c:a", audio_codec]
            # Bound the mux to the captured window so a short audio clip cannot
            # truncate the video, and silence after the last clip is kept.
            if render_end_seconds is not None:
                mux_duration = max(0.1, render_end_seconds - render_start_seconds)
                ffmpeg_cmd += ["-t", f"{mux_duration:.3f}"]
            else:
                ffmpeg_cmd += ["-shortest"]
    ffmpeg_cmd += [str(output_path)]

    ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    frame_times: list[float] = []
    last_signature = ""
    last_change_time = 0.0
    capped = True

    try:
        with sync_playwright() as playwright:
            # Memory Optimization: Add flags to Chromium
            chromium_args = [
                "--disable-dev-shm-usage",
                "--hide-scrollbars",
                "--mute-audio",
                "--js-flags=--max-old-space-size=256", # Limit V8 heap
            ]
            if gpu_boost:
                chromium_args += [
                    "--ignore-gpu-blocklist",
                    "--enable-gpu-rasterization",
                    "--enable-zero-copy",
                ]
            else:
                chromium_args.append("--disable-gpu")
            browser = playwright.chromium.launch(headless=True, args=chromium_args)
            try:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    screen={"width": width, "height": height},
                    device_scale_factor=1,
                    color_scheme="dark",
                )
                page = context.new_page()
                page.route(
                    "**/*",
                    lambda route: _handle_route(route),
                )
                document_html = build_sequence_document(clips, transitions, transition_engine) if sequence_mode else inject_control_script(code)
                page.set_content(document_html, wait_until="load")
                page.evaluate(
                    """async () => {
                        try {
                            if (document.fonts && document.fonts.ready) {
                                await document.fonts.ready;
                            }
                        } catch (_) {}
                        try {
                            await Promise.all(Array.from(document.images || []).map((img) => {
                                if (img.complete && img.naturalWidth) return Promise.resolve();
                                return new Promise((resolve) => {
                                    img.onload = resolve;
                                    img.onerror = resolve;
                                });
                            }));
                        } catch (_) {}
                        if (typeof window.__ccReady === 'function') {
                            try { await window.__ccReady(); } catch (_) {}
                        } else if (typeof window.__clipacanvasReady === 'function') {
                            try { await window.__clipacanvasReady(); } catch (_) {}
                        }
                    }"""
                )
                meta = page.evaluate("() => (window.__clipacanvasCaptureMeta ? window.__clipacanvasCaptureMeta() : { activeAnimations: 0, suggestedDurationMs: 0 })")
                suggested_duration = max(min_duration, float(meta.get("suggestedDurationMs", 0) or 0) / 1000.0)
                if content_mode != "canvas" and suggested_duration <= min_duration:
                    suggested_duration = max(min_duration, min(max_duration, 6.0))
                elif suggested_duration > min_duration:
                    suggested_duration = min(max_duration, suggested_duration + 0.25)
                target_duration = min(max_duration, max(min_duration, suggested_duration))
                if render_end_explicit:
                    end_time = render_end_seconds
                    capture_duration = max(target_duration, end_time, render_start_seconds)
                else:
                    end_time = target_duration
                    if render_start_seconds >= end_time:
                        raise ValueError(
                            f"Render start ({render_start_seconds:.2f}s) is beyond the auto duration ({end_time:.2f}s)."
                        )
                    capture_duration = target_duration
                frame_total = int(math.ceil(capture_duration * frame_rate)) + 2

                start_frame = max(0, min(frame_total - 1, int(render_start_seconds * frame_rate)))
                end_frame = min(
                    frame_total,
                    max(start_frame + 1, int(math.ceil(end_time * frame_rate))),
                )

                cdp = context.new_cdp_session(page) if frame_image_format == "jpeg" else None

                frame_span = max(1, end_frame - start_frame)
                thumb_every = max(1, int(math.ceil(frame_span / 16)))
                thumb_saved: set[int] = set()
                thumb_scale = min(0.22, 150.0 / max(width, height, 1))
                thumb_cdp = None
                if frame_dir_path is not None:
                    try:
                        thumb_cdp = cdp or context.new_cdp_session(page)
                    except Exception:
                        thumb_cdp = None
                    try:
                        meta_tmp = frame_dir_path / "meta.json.tmp"
                        meta_tmp.write_text(json.dumps({
                            "width": width,
                            "height": height,
                            "frameRate": frame_rate,
                            "totalFrames": frame_span,
                        }), encoding="utf-8")
                        os.replace(meta_tmp, frame_dir_path / "meta.json")
                    except OSError:
                        pass

                def save_thumbnail(frame_index):
                    if thumb_cdp is None or frame_index in thumb_saved:
                        return
                    try:
                        shot = thumb_cdp.send("Page.captureScreenshot", {
                            "format": "jpeg",
                            "quality": 72,
                            "optimizeForSpeed": True,
                            "fromSurface": True,
                            "clip": {
                                "x": 0,
                                "y": 0,
                                "width": width,
                                "height": height,
                                "scale": thumb_scale,
                            },
                        })
                        raw = base64.b64decode(shot["data"])
                        target = frame_dir_path / f"frame_{frame_index:05d}.jpg"
                        temp_target = frame_dir_path / f"frame_{frame_index:05d}.tmp"
                        temp_target.write_bytes(raw)
                        os.replace(temp_target, target)
                        thumb_saved.add(frame_index)
                    except Exception:
                        pass

                for index in range(start_frame, end_frame):
                  t = round(index / frame_rate, 4)
                  page.evaluate(
                      """async (s) => {
                          if (window.__clipacanvasSetTime) await window.__clipacanvasSetTime(s);
                          if (window.__clipacanvasAwaitMedia) await window.__clipacanvasAwaitMedia();
                      }""",
                      t,
                  )

                  if cdp is not None:
                      shot = cdp.send("Page.captureScreenshot", {
                          "format": "jpeg",
                          "quality": 92,
                          "optimizeForSpeed": True,
                          "fromSurface": True,
                      })
                      content = base64.b64decode(shot["data"])
                  else:
                      content = page.screenshot(type="png")
                  signature = hash_frame(content)
                  
                  if not last_signature or signature != last_signature:
                      last_signature = signature
                      last_change_time = t

                  # Write directly to FFmpeg pipe
                  ffmpeg_proc.stdin.write(content)
                  frame_times.append(t)
                  if (index - start_frame) % thumb_every == 0:
                      save_thumbnail(index)

                  idle_for = t - last_change_time
                  # Only auto mode may stop early when the animation settles;
                  # explicit frame ranges are rendered to the requested end.
                  if not render_end_explicit and t >= min_duration and idle_for >= settle_window:
                      meta = page.evaluate("() => (window.__clipacanvasCaptureMeta ? window.__clipacanvasCaptureMeta() : { activeAnimations: 0, suggestedDurationMs: 0 })")
                      if meta["activeAnimations"] == 0:
                          save_thumbnail(index)
                          capped = False
                          break
                if frame_times:
                    save_thumbnail(start_frame + len(frame_times) - 1)
            finally:
                browser.close()
                gc.collect() # Immediate cleanup

        # Close FFmpeg pipe to finish encoding and read outputs
        stdout, stderr = ffmpeg_proc.communicate()
        if ffmpeg_proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip())

        # Write reproducibility manifest sidecar
        try:
            import json as _json
            options_key = {
                "width": width,
                "height": height,
                "bitrate": bitrate,
                "codec": codec,
                "frameRate": frame_rate,
                "max_duration": max_duration,
                "min_duration": min_duration,
                "settle_window": settle_window,
                "audio_path": audio_path,
                "gpu_boost": gpu_boost,
                "encoder": video_codec,
            }
            content_hash = hashlib.sha256((code + _json.dumps(options_key, sort_keys=True)).encode("utf-8")).hexdigest()
            manifest_path = output_path.with_suffix(".json")
            manifest = {
                "engine": "clipacanvas-desktop",
                "version": "1.0.0",
                "contentHash": content_hash,
                "codec": codec,
                "width": width,
                "height": height,
                "frameRate": frame_rate,
                "duration": frame_times[-1] if frame_times else 0,
                "frameCount": len(frame_times),
                "capped": capped,
                "contentMode": content_mode,
                "encoder": video_codec,
                "gpuBoost": gpu_boost,
                "audioPath": audio_path or None,
                "renderStart": render_start_seconds,
                "renderEnd": render_end_seconds if render_end_seconds is not None else target_duration,
                "output": str(output_path.resolve()),
            }
            manifest_path.write_text(_json.dumps(manifest, indent=2), encoding="utf-8")
        except Exception:
            pass

        return {
            "duration": frame_times[-1] if frame_times else 0,
            "frameCount": len(frame_times),
            "capped": capped,
            "contentMode": content_mode,
            "codec": codec,
            "encoder": video_codec,
            "gpuBoost": gpu_boost,
            "contentHash": content_hash if "content_hash" in locals() else None,
            "renderStart": render_start_seconds,
            "renderEnd": render_end_seconds if render_end_seconds is not None else target_duration,
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
