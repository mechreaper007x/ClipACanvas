#!/usr/bin/env python3
"""
Clip.A.Canvas Backend Assistant
- Serves the frontend
- Handles Playwright + FFmpeg video rendering
- Auto-opens the tool in your browser
"""

import os
import re
import time
import json
import base64
import ctypes
import hashlib
import shutil
import sqlite3
import webbrowser
import subprocess
import sys
import tempfile
import threading
import platform
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get("CLIPACANVAS_CORS_ORIGIN", "*").split(",") if origin.strip()]

CODEC_OUTPUT_FORMATS = {
    'h264': ('mp4', 'video/mp4'),
    'h265': ('mp4', 'video/mp4'),
    'hevc': ('mp4', 'video/mp4'),
    'vp9': ('webm', 'video/webm'),
    'vp8': ('webm', 'video/webm'),
    'av1': ('webm', 'video/webm'),
    'prores': ('mov', 'video/quicktime'),
    'gif': ('gif', 'image/gif'),
}

_RENDER_FRAME_ROOT = Path(tempfile.gettempdir()) / 'clipacanvas_render_frames'
_RENDER_ID_RE = re.compile(r'^[A-Za-z0-9_-]{6,64}$')
_RENDER_FRAME_RE = re.compile(r'^frame_(\d{1,7})\.jpg$')


def _render_frames_dir(render_id: str) -> Path:
    return _RENDER_FRAME_ROOT / render_id


def _prune_render_frames(max_age_seconds: int = 3600) -> None:
    try:
        root = _RENDER_FRAME_ROOT
        if not root.is_dir():
            return
        cutoff = time.time() - max_age_seconds
        for child in root.iterdir():
            try:
                if child.is_dir() and child.stat().st_mtime < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
            except OSError:
                continue
    except OSError:
        pass


def _codec_output(codec: str) -> tuple:
    codec = str(codec or 'h264').lower().strip()
    return CODEC_OUTPUT_FORMATS.get(codec, CODEC_OUTPUT_FORMATS['h264'])


def _model_sort_key(model: dict) -> tuple:
    name = model["name"].lower()
    if "gemma" in name:
        return (2, 0, 0)
    if "pro" in name and "flash" not in name:
        tier = 3
    elif "flash-lite" in name:
        tier = 1
    elif "flash" in name:
        tier = 2
    else:
        tier = 0
    version_parts = [int(part) for part in re.findall(r"\d+", name)][:2]
    version = (version_parts[0] if version_parts else 0, version_parts[1] if len(version_parts) > 1 else 0)
    return (tier, version[0], version[1])


def _mistral_model_sort_key(model: dict) -> tuple:
    name = model["name"].lower()
    if "large" in name:
        tier = 3
    elif "medium" in name or "codestral" in name:
        tier = 2
    elif "small" in name or "ministral" in name:
        tier = 1
    else:
        tier = 0
    version_parts = [int(part) for part in re.findall(r"\d+", name)][:2]
    version = (version_parts[0] if version_parts else 0, version_parts[1] if len(version_parts) > 1 else 0)
    return (tier, version[0], version[1])


# Tools the assistant can call. The app runs each call in the UI and drives the
# follow-up turns; Gemini and Mistral both map from this single declaration list.
LLM_TOOL_DECLARATIONS = [
    {
        "name": "get_app_state",
        "description": "Read the selected scene code, the full timeline, export settings and latest render result.",
    },
    {
        "name": "set_export_settings",
        "description": "Change export settings in the app. Only call this when the user explicitly asked for that exact setting in their latest message; the app ignores unrequested changes and never lets the model override the user's choices.",
        "parameters": {
            "type": "object",
            "properties": {
                "resolution": {"type": "string", "description": "Exact pixel size as WxH, e.g. 1920x1080 or 1080x1920. Keep the user's current resolution tier and aspect ratio; never downgrade it."},
                "fps": {"type": "string", "description": "Frame rate: 24, 25, 30, 48, 50, 60 or 120."},
                "duration": {"type": "number", "description": "Clip length in seconds, 0.5 to 60."},
                "format": {"type": "string", "enum": ["mp4", "webm", "mov", "gif"]},
                "bitrate": {"type": "string", "enum": ["1M", "2M", "5M", "10M", "20M"]},
            },
        },
    },
    {
        "name": "insert_animation_code",
        "description": "Fill or replace the SELECTED scene (the editor) with a complete self-contained HTML animation; the live preview refreshes immediately. Use this for the current scene only, never for additional scenes.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Complete single-file HTML document, no markdown fences."},
                "duration": {"type": "number", "description": "Optional scene length in seconds, 0.5 to 60, matching the animation; omit to keep the box length."},
            },
            "required": ["code"],
        },
    },
    {
        "name": "add_scene",
        "description": "Create an additional scene as a new logic box on the timeline, with its own complete HTML animation. Use this for every extra scene in a sequence instead of merging scenes into one document; the app appends the box, selects it and previews it. The whole timeline renders as one video.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Complete single-file HTML document for this scene, no markdown fences."},
                "name": {"type": "string", "description": "Short scene name, up to 24 characters, e.g. INTRO or TITLE."},
                "duration": {"type": "number", "description": "Scene length in seconds, 0.5 to 60. Match the animation length."},
                "layer": {"type": "string", "enum": ["same", "above"], "description": "same appends after the last scene on the selected scene's track; above creates an upper track for overlays, titles or captions that need a transparent page background."},
                "start": {"type": "number", "description": "Optional exact start time in seconds; omit to append automatically."},
            },
            "required": ["code"],
        },
    },
    {
        "name": "search_assets",
        "description": "Search the project bin and return concise asset summaries with cached technical metadata. Use this before composing around imported media; omit query to list all assets.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name, tag or description fragment. Empty returns every asset."},
            },
        },
    },
    {
        "name": "get_asset_analysis",
        "description": "Read one asset's cached analysis manifest: technical metadata, the locally detected shot list (with keyframe URLs), semantic status, AI description and user notes. Semantic analysis only exists after the user ran it with explicit consent; when it is 'not_analyzed', never invent visual or audio content that is not in the manifest.",
        "parameters": {
            "type": "object",
            "properties": {
                "assetId": {"type": "string", "description": "Project asset id from search_assets or get_app_state."},
            },
            "required": ["assetId"],
        },
    },
    {
        "name": "update_asset_description",
        "description": "Save a human-confirmed description or note on a project asset. It is stored separately from AI analysis and must not be overwritten by generated text.",
        "parameters": {
            "type": "object",
            "properties": {
                "assetId": {"type": "string", "description": "Project asset id."},
                "description": {"type": "string", "description": "Short human-confirmed description of the asset's content or intended use."},
                "notes": {"type": "string", "description": "Optional extra production notes."},
            },
            "required": ["assetId", "description"],
        },
    },
    {
        "name": "create_overlay",
        "description": "Create an independent HTML overlay clip above existing footage on the timeline. The page must have a fully transparent background so the footage below stays visible. Optionally attach it to a parent clip. The overlay stays separately selectable and editable; this is not motion tracking.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Complete single-file HTML document with a transparent page background, no markdown fences."},
                "name": {"type": "string", "description": "Short overlay name, up to 24 characters."},
                "duration": {"type": "number", "description": "Overlay length in seconds, 0.5 to 60. Defaults to the parent clip length."},
                "start": {"type": "number", "description": "Start time in seconds. Defaults to the parent clip start."},
                "track": {"type": "integer", "description": "Optional V-track index 0-3. Defaults to one track above the parent."},
                "parentClipId": {"type": "string", "description": "Optional clip id this overlay belongs to."},
            },
            "required": ["code"],
        },
    },
    {
        "name": "update_overlay",
        "description": "Change an existing code overlay's code, name or duration. Imported media and code scenes are not overlays and must be edited with their own tools.",
        "parameters": {
            "type": "object",
            "properties": {
                "clipId": {"type": "string", "description": "Overlay clip id."},
                "code": {"type": "string", "description": "New complete HTML document, no markdown fences."},
                "name": {"type": "string", "description": "New short name, up to 24 characters."},
                "duration": {"type": "number", "description": "New length in seconds, 0.5 to 60."},
            },
            "required": ["clipId"],
        },
    },
    {
        "name": "attach_overlay",
        "description": "Attach an existing overlay clip to a parent video/image/code clip so it follows the parent's timing. It stays independently editable.",
        "parameters": {
            "type": "object",
            "properties": {
                "clipId": {"type": "string", "description": "Overlay clip id."},
                "parentClipId": {"type": "string", "description": "Parent clip id."},
            },
            "required": ["clipId", "parentClipId"],
        },
    },
    {
        "name": "detach_overlay",
        "description": "Detach an overlay from its parent. The overlay keeps its current position.",
        "parameters": {
            "type": "object",
            "properties": {
                "clipId": {"type": "string", "description": "Overlay clip id."},
            },
            "required": ["clipId"],
        },
    },
    {
        "name": "delete_overlay",
        "description": "Delete an overlay clip. Its source footage and parent clip are not modified.",
        "parameters": {
            "type": "object",
            "properties": {
                "clipId": {"type": "string", "description": "Overlay clip id."},
            },
            "required": ["clipId"],
        },
    },
    {
        "name": "get_clip_context",
        "description": "Read one clip's timing, track, parent/children relationships and asset analysis summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "clipId": {"type": "string", "description": "Timeline clip id."},
            },
            "required": ["clipId"],
        },
    },
    {
        "name": "add_transition",
        "description": "Add a saved visual transition on an existing cut where two clips touch on the same track. Presets: dissolve, fade-black, fade-white, dip-color, wipe, push, slide, zoom-in, zoom-out, zoom-blur, glitch, rgb-split, blur-dissolve. Defaults to the touching cut of the selected clip. For a custom transition use type \"custom\" and provide code declaring function renderTransition(ctx) that returns {outgoing, incoming, overlay} style objects for ctx.progress 0→1 (opacity, transform, filter, clipPath, backgroundColor, mixBlendMode). Custom code is validated and runs only inside the isolated preview/export page. Video clips must have enough footage handles for the requested alignment.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Preset id or \"custom\"."},
                "fromClipId": {"type": "string", "description": "Optional outgoing clip id; defaults to the selected clip's touching cut."},
                "toClipId": {"type": "string", "description": "Optional incoming clip id."},
                "duration": {"type": "number", "description": "Length in seconds, 0.1 to 3."},
                "alignment": {"type": "string", "enum": ["center", "start", "end"], "description": "Where the transition sits relative to the cut."},
                "direction": {"type": "string", "enum": ["left", "right", "up", "down"], "description": "Motion/reveal direction for wipe, push and slide."},
                "color": {"type": "string", "description": "Dip color for dip-color, e.g. #0a0f0d."},
                "intensity": {"type": "number", "description": "Effect strength 0 to 1 for zoom, glitch, rgb-split and blur presets."},
                "code": {"type": "string", "description": "Custom transition source when type is custom."},
            },
            "required": ["type"],
        },
    },
    {
        "name": "update_transition",
        "description": "Change a saved transition's type, duration, alignment, parameters or custom code. Defaults to the transition on the selected clip's cut when transitionId is omitted. The same handle validation applies.",
        "parameters": {
            "type": "object",
            "properties": {
                "transitionId": {"type": "string", "description": "Transition id from get_app_state; optional."},
                "type": {"type": "string", "description": "New preset id or \"custom\"."},
                "duration": {"type": "number", "description": "New length in seconds, 0.1 to 3."},
                "alignment": {"type": "string", "enum": ["center", "start", "end"]},
                "direction": {"type": "string", "enum": ["left", "right", "up", "down"]},
                "color": {"type": "string"},
                "intensity": {"type": "number"},
                "code": {"type": "string", "description": "New custom code when type is custom."},
            },
        },
    },
    {
        "name": "remove_transition",
        "description": "Remove a transition from a cut. Neither clip nor its footage is modified. Defaults to the transition on the selected clip's cut.",
        "parameters": {
            "type": "object",
            "properties": {
                "transitionId": {"type": "string", "description": "Transition id; optional."},
            },
        },
    },
    {
        "name": "render_video",
        "description": "Render the whole timeline (every scene, in order and by layer) to one video file with the current export settings. Can take from a few seconds to a few minutes.",
    },
]


def _gemini_schema_types(schema):
    if isinstance(schema, dict):
        converted = {}
        for key, value in schema.items():
            # Only the JSON-schema "type" keyword holds a scalar type name.
            # A parameter may itself be named "type", whose value is a dict
            # schema and must be converted normally, not stringified.
            if key == "type" and isinstance(value, str):
                converted[key] = value.upper()
            else:
                converted[key] = _gemini_schema_types(value)
        return converted
    if isinstance(schema, list):
        return [_gemini_schema_types(item) for item in schema]
    return schema


def _gemini_tool_declarations() -> list:
    declarations = []
    for tool in LLM_TOOL_DECLARATIONS:
        declaration = {"name": tool["name"], "description": tool["description"]}
        if tool.get("parameters"):
            declaration["parameters"] = _gemini_schema_types(tool["parameters"])
        declarations.append(declaration)
    return declarations


def _mistral_tool_declarations() -> list:
    declarations = []
    for tool in LLM_TOOL_DECLARATIONS:
        declarations.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters") or {"type": "object", "properties": {}},
            },
        })
    return declarations


def _tool_result_value(text: str):
    try:
        parsed = json.loads(text) if text else None
    except (json.JSONDecodeError, TypeError):
        return text
    return parsed if parsed is not None else text


def _retry_delay_seconds(detail: str) -> int:
    match = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', detail or '')
    if not match:
        return 0
    try:
        return max(1, int(float(match.group(1)) + 0.5))
    except ValueError:
        return 0


def _rate_limit_message(provider: str, model: str, retry_seconds: int, tried_fallback: bool) -> str:
    label = str(model or '').replace('models/', '')
    if tried_fallback:
        head = f'{provider.capitalize()} is out of free-tier quota for every model it tried (429).'
    else:
        head = f'{provider.capitalize()} is out of free-tier quota for {label} (429).'
    body = ' Free-tier keys allow only a small number of requests per model per day, and tool calls use extra requests.'
    if retry_seconds:
        body += f' Retry in about {_human_duration(retry_seconds)}'
    else:
        body += ' Retry in about a minute'
    return head + body + ', or switch to another model.'


_MODEL_COOLDOWNS: dict = {}


def _set_model_cooldown(provider: str, model: str, seconds: int) -> None:
    if seconds > 0:
        _MODEL_COOLDOWNS[(provider, model)] = time.time() + seconds


def _model_cooldown_remaining(provider: str, model: str) -> int:
    until = _MODEL_COOLDOWNS.get((provider, model), 0)
    return max(0, int(until - time.time()))


def _human_duration(seconds: int) -> str:
    if seconds < 90:
        return f'{seconds}s'
    if seconds < 3600:
        return f'{max(1, round(seconds / 60))} min'
    return f'{seconds / 3600:.1f} h'


def app_dir_candidates() -> list[Path]:
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS))

        executable_path = Path(sys.executable).resolve()
        contents_dir = executable_path.parent.parent
        candidates.extend([
            contents_dir / "Resources",
            contents_dir / "Frameworks",
            executable_path.parent,
        ])

    candidates.append(Path(__file__).resolve().parent)
    return candidates


def resolve_app_dir() -> Path:
    for candidate in app_dir_candidates():
        if (candidate / "clipacanvas.html").exists():
            return candidate
    return app_dir_candidates()[0]


APP_DIR = resolve_app_dir()
IS_WINDOWS = platform.system() == "Windows"
FFMPEG_NAME = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"


def resolve_ffmpeg_exe() -> str:
    env_ffmpeg = os.environ.get("FFMPEG_EXE")
    if env_ffmpeg:
        return env_ffmpeg

    for candidate_dir in app_dir_candidates():
        bundled_ffmpeg = candidate_dir / "bin" / FFMPEG_NAME
        if bundled_ffmpeg.exists():
            return str(bundled_ffmpeg)

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        print("ERROR: imageio-ffmpeg is required.")
        print("Please run: pip install imageio-ffmpeg")
        raise SystemExit(1)


FFMPEG_EXE = resolve_ffmpeg_exe()


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.c_void_p)]


if IS_WINDOWS:
    _CRYPT_PROTECT = ctypes.windll.crypt32.CryptProtectData
    _CRYPT_PROTECT.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_wchar_p,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _CRYPT_PROTECT.restype = ctypes.c_int

    _CRYPT_UNPROTECT = ctypes.windll.crypt32.CryptUnprotectData
    _CRYPT_UNPROTECT.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _CRYPT_UNPROTECT.restype = ctypes.c_int

    _LOCAL_FREE = ctypes.windll.kernel32.LocalFree
    _LOCAL_FREE.argtypes = [ctypes.c_void_p]
    _LOCAL_FREE.restype = ctypes.c_void_p


def _dpapi_protect(data: bytes) -> bytes:
    if not IS_WINDOWS:
        return data
    input_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.c_void_p))
    output_blob = _DATA_BLOB()
    if not _CRYPT_PROTECT(ctypes.byref(input_blob), None, None, None, None, 0x01, ctypes.byref(output_blob)):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        _LOCAL_FREE(output_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    if not IS_WINDOWS:
        return data
    input_blob = _DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.c_void_p))
    output_blob = _DATA_BLOB()
    if not _CRYPT_UNPROTECT(ctypes.byref(input_blob), None, None, None, None, 0x01, ctypes.byref(output_blob)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        _LOCAL_FREE(output_blob.pbData)


def _keys_dir() -> Path:
    override = os.environ.get("CLIPACANVAS_KEYS_DIR")
    if override:
        return Path(override)
    return Path(os.environ.get("APPDATA") or os.path.expanduser("~")) / "ClipACanvas"


MEDIA_MAX_BYTES = 200 * 1024 * 1024
MEDIA_NAME_RE = re.compile(r"^media-[a-f0-9]{20}\.[a-z0-9]{2,5}$")
MEDIA_TYPES = {
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".webp": ("image", "image/webp"),
    ".gif": ("image", "image/gif"),
    ".avif": ("image", "image/avif"),
    ".bmp": ("image", "image/bmp"),
    ".mp4": ("video", "video/mp4"),
    ".m4v": ("video", "video/mp4"),
    ".mov": ("video", "video/quicktime"),
    ".webm": ("video", "video/webm"),
    ".ogv": ("video", "video/ogg"),
    ".ogg": ("video", "video/ogg"),
    ".mp3": ("audio", "audio/mpeg"),
    ".wav": ("audio", "audio/wav"),
    ".m4a": ("audio", "audio/mp4"),
    ".aac": ("audio", "audio/aac"),
    ".flac": ("audio", "audio/flac"),
    ".oga": ("audio", "audio/ogg"),
    ".opus": ("audio", "audio/opus"),
}


def _media_dir() -> Path:
    directory = _keys_dir() / "media"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


PROJECT_FORMAT = "clipacanvas-project"
PROJECT_VERSION = 1
PROJECT_AUTOSAVE_NAME = "autosave.ccproj.json"
PROJECT_SESSION_NAME = "session.json"
PROJECT_AUTOSAVE_SUFFIX = ".autosave.ccproj.json"
PROJECT_FILE_RE = re.compile(r"^(?!autosave)[a-z0-9][a-z0-9-]{0,63}\.ccproj\.json$")
PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
PROJECT_MAX_BYTES = 8 * 1024 * 1024


def _projects_dir() -> Path:
    directory = _keys_dir() / "projects"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


AGENT_PLAN_MAX_BYTES = 256 * 1024
AGENT_PLAN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,80}$")


def _agent_plans_dir() -> Path:
    directory = _keys_dir() / "agent-plans"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write_text_atomic(path: Path, text: str) -> None:
    temp = path.with_name(f".{path.name}.{os.urandom(4).hex()}.tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validate_project_doc(doc) -> str:
    if not isinstance(doc, dict):
        return "Project payload must be a JSON object."
    if doc.get("format") != PROJECT_FORMAT:
        return "Not a Clip.A.Canvas project payload."
    try:
        version = int(doc.get("version") or 0)
    except (TypeError, ValueError):
        return "Invalid project version."
    if version < 1 or version > PROJECT_VERSION:
        return "Unsupported project version."
    timeline = doc.get("timeline")
    if not isinstance(timeline, dict) or not isinstance(timeline.get("clips"), list):
        return "Project payload has no timeline."
    if len(timeline["clips"]) > 400:
        return "Project has too many clips."
    return ""


def _read_project_index() -> list[dict]:
    path = _projects_dir() / "index.json"
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [entry for entry in parsed if isinstance(entry, dict) and isinstance(entry.get("file"), str)]


def _write_project_index(entries: list[dict]) -> None:
    _write_text_atomic(_projects_dir() / "index.json", json.dumps(entries, indent=2))


def _project_autosave_path(project_id: str) -> Path:
    return _projects_dir() / f"{project_id}{PROJECT_AUTOSAVE_SUFFIX}"


def _read_json_path(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _project_saved_at(path: Path) -> str:
    doc = _read_json_path(path)
    if isinstance(doc, dict) and isinstance(doc.get("savedAt"), str):
        return doc["savedAt"]
    try:
        stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except OSError:
        return ""


def _project_entry_id(entry: dict) -> str:
    value = str(entry.get("id") or "")
    if PROJECT_ID_RE.match(value):
        return value
    match = re.match(r"^([a-z0-9][a-z0-9-]{0,63})\.ccproj\.json$", str(entry.get("file") or ""))
    return match.group(1) if match else ""


def _find_project_entry(entries: list[dict], project_id: str):
    return next((entry for entry in entries if _project_entry_id(entry) == project_id), None)


def _project_entry_meta(entry: dict) -> dict:
    project_id = _project_entry_id(entry)
    file_name = str(entry.get("file") or "")
    file_path = _projects_dir() / file_name
    doc = _read_json_path(file_path) if PROJECT_FILE_RE.match(file_name) else None
    readable = isinstance(doc, dict)
    saved_at = ""
    if readable:
        saved_at = doc.get("savedAt") if isinstance(doc.get("savedAt"), str) else _project_saved_at(file_path)
    autosave_saved_at = _project_saved_at(_project_autosave_path(project_id)) if project_id else ""
    recoverable = bool(autosave_saved_at) and (not saved_at or autosave_saved_at > saved_at)
    return {
        "id": project_id,
        "name": str(entry.get("name") or "PROJECT"),
        "file": file_name,
        "savedAt": saved_at or str(entry.get("savedAt") or ""),
        "createdAt": str(entry.get("createdAt") or ""),
        "autosaveSavedAt": autosave_saved_at,
        "recoverable": recoverable,
        "missing": not readable,
    }


def _unique_project_stem(display: str, entries: list[dict]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", display.lower()).strip("-")[:48] or "project"
    used = {str(entry.get("file") or "") for entry in entries}
    stem = slug
    counter = 2
    while f"{stem}.ccproj.json" in used:
        stem = f"{slug}-{counter}"
        counter += 1
    return stem


def _session_path() -> Path:
    return _projects_dir() / PROJECT_SESSION_NAME


def _read_session():
    session = _read_json_path(_session_path())
    return session if isinstance(session, dict) else None


def _write_session(project_id: str, name: str, saved_at: str) -> None:
    _write_text_atomic(_session_path(), json.dumps({
        "projectId": project_id,
        "name": name,
        "savedAt": saved_at,
    }, ensure_ascii=False))


ANALYSIS_VERSION = 2
SEMANTIC_DEFAULT_MODEL = "gemini-2.5-flash"
SEMANTIC_MAX_FRAMES = 6
SEMANTIC_MAX_INLINE_BYTES = 19 * 1024 * 1024
SEMANTIC_MAX_TRANSCRIPT_SECONDS = 300
SEMANTIC_SHOT_SCAN_SECONDS = 180
SEMANTIC_SHOT_LIMIT = 24
SEMANTIC_KEYFRAME_LIMIT = 12
SEMANTIC_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "subjects": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "suggestedUses": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "transcript": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    "required": ["description", "tags"],
}
_ANALYSIS_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_ANALYSIS_VIDEO_RE = re.compile(r"Stream #\d+:\d+[^:]*: Video: ([A-Za-z0-9_\-]+)")
_ANALYSIS_RESOLUTION_RE = re.compile(r"(?<![\d.])(\d{2,5})x(\d{2,5})(?![\d.])")
_ANALYSIS_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")
_ANALYSIS_AUDIO_RE = re.compile(r"Stream #\d+:\d+[^:]*: Audio: ([A-Za-z0-9_\-]+)")
_ANALYSIS_HZ_RE = re.compile(r"(\d+)\s*Hz")
_ANALYSIS_CHANNELS_RE = re.compile(r",\s*(mono|stereo|quad|5\.1|7\.1)\b")


def _analysis_dir() -> Path:
    directory = _keys_dir() / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _probe_media_technical(path: Path) -> dict:
    """Read technical metadata from FFmpeg's input probe (no frame decode)."""
    proc = subprocess.run(
        [FFMPEG_EXE, "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, errors="replace", timeout=30,
    )
    output = proc.stderr or ""
    technical: dict = {
        "duration": None,
        "width": None,
        "height": None,
        "fps": None,
        "videoCodec": None,
        "audioCodec": None,
        "sampleRate": None,
        "channels": None,
        "streams": len(re.findall(r"Stream #\d+:\d+", output)),
        "bytes": path.stat().st_size,
    }
    duration = _ANALYSIS_DURATION_RE.search(output)
    if duration:
        hours, minutes, seconds = duration.groups()
        technical["duration"] = round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 3)
    video = _ANALYSIS_VIDEO_RE.search(output)
    if video:
        technical["videoCodec"] = video.group(1).lower()
        video_line = next((line for line in output.splitlines() if video.group(0) in line), "")
        resolution = _ANALYSIS_RESOLUTION_RE.search(video_line)
        if resolution:
            technical["width"] = int(resolution.group(1))
            technical["height"] = int(resolution.group(2))
        fps = _ANALYSIS_FPS_RE.search(video_line)
        if fps:
            technical["fps"] = round(float(fps.group(1)), 3)
    audio = _ANALYSIS_AUDIO_RE.search(output)
    if audio:
        technical["audioCodec"] = audio.group(1).lower()
        audio_line = next((line for line in output.splitlines() if audio.group(0) in line), "")
        hz = _ANALYSIS_HZ_RE.search(audio_line)
        if hz:
            technical["sampleRate"] = int(hz.group(1))
        channels = _ANALYSIS_CHANNELS_RE.search(audio_line)
        if channels:
            technical["channels"] = {"mono": 1, "stereo": 2, "quad": 4, "5.1": 6, "7.1": 8}.get(channels.group(1))
    if technical["duration"] is None and technical["videoCodec"]:
        # Stills have no duration; FFmpeg reports a nominal 25 fps for them.
        technical["fps"] = None
    return technical


TTS_MAX_TEXT = 4000
TTS_CACHE_VERSION = 1
# Verified against the official docs on 2026-11-12:
# Gemini TTS: ai.google.dev / aistudio.google.com speech-generation docs.
# Mistral Voxtral TTS: docs.mistral.ai audio/speech API reference and voices page.
GEMINI_TTS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_TTS_MODELS = [
    {"id": "gemini-3.8-flash-tts", "label": "Gemini 3.8 Flash TTS"},
    {"id": "gemini-3.8-flash-lite-tts", "label": "Gemini 3.8 Flash-Lite TTS"},
]
GEMINI_TTS_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]
MISTRAL_TTS_URL = "https://api.mistral.ai/v1/audio/speech"
MISTRAL_TTS_MODELS = [
    {"id": "voxtral-mini-tts-latest", "label": "Voxtral Mini TTS (speech v1)"},
    {"id": "voxtral-mini-tts-3-0", "label": "Voxtral Mini TTS 3.0"},
]
MISTRAL_TTS_MODEL = MISTRAL_TTS_MODELS[0]["id"]
# Speech v1 preset voice ids verified live on 2026-11-12. The legacy voice_*
# catalog from the deprecated TTS docs is rejected by this endpoint.
MISTRAL_TTS_VOICES = [
    ("gb_jane_neutral", "English (UK)"),
    ("gb_oliver_neutral", "English (UK)"),
    ("en_paul_neutral", "English (US)"),
    ("en_paul_sad", "English (US)"),
    ("fr_marie_neutral", "French"),
]
_SAPI_VOICE_CACHE = {"at": 0.0, "voices": [], "error": ""}
_SAPI_VOICE_LOCK = threading.Lock()


def _tts_dir() -> Path:
    directory = _keys_dir() / "tts"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _sapi_voice_list() -> tuple[list[dict], str]:
    """Installed Windows SAPI voices, cached for five minutes.

    This is the local provider: it uses the OS speech engine, requires no
    network and no model download, and reports only voices actually installed.
    """
    with _SAPI_VOICE_LOCK:
        if time.time() - _SAPI_VOICE_CACHE["at"] < 300:
            return _SAPI_VOICE_CACHE["voices"], _SAPI_VOICE_CACHE["error"]
    voices: list[dict] = []
    error = ""
    powershell = shutil.which("powershell.exe") if IS_WINDOWS else None
    if not powershell:
        error = "Windows SAPI is not available on this platform."
    else:
        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.GetInstalledVoices() | ForEach-Object { $i = $_.VoiceInfo; "
            "Write-Output ($i.Name + '|' + $i.Culture.Name + '|' + $i.Gender) }"
        )
        try:
            proc = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, errors="replace", timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in (proc.stdout or "").splitlines():
                parts = line.strip().split("|")
                if len(parts) < 2 or not parts[0]:
                    continue
                voices.append({
                    "id": parts[0],
                    "label": parts[0].replace("Microsoft ", "").replace(" Desktop", ""),
                    "language": parts[1] or "unknown",
                    "gender": parts[2] if len(parts) > 2 else "",
                })
            if not voices:
                error = "No installed Windows speech voices were found."
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = f"Windows speech engine unavailable: {exc}"
    with _SAPI_VOICE_LOCK:
        _SAPI_VOICE_CACHE.update({"at": time.time(), "voices": voices, "error": error})
    return voices, error


def tts_provider_registry() -> dict:
    keys = _load_saved_keys()
    sapi_voices, sapi_error = _sapi_voice_list()
    providers = [
        {
            "id": "sapi",
            "label": "Windows Speech (local)",
            "kind": "local",
            "available": bool(sapi_voices),
            "reason": sapi_error if not sapi_voices else "",
            "requiresKey": "",
            "models": [{"id": "system", "label": "Installed SAPI voice"}],
            "voices": sapi_voices,
            "languages": sorted({voice["language"] for voice in sapi_voices}),
            "formats": ["wav"],
            "supports": {"speed": True, "style": False, "emotion": False, "voiceCloning": False, "streaming": False},
            "notes": "Offline OS speech; no network, no model download. Voice quality depends on installed Windows voices.",
            "terms": "Runs locally. Script text never leaves the machine.",
        },
        {
            "id": "gemini",
            "label": "Google Gemini TTS",
            "kind": "remote",
            "available": bool(keys.get("gemini")),
            "reason": "" if keys.get("gemini") else "Add a Gemini API key in Settings.",
            "requiresKey": "gemini",
            "models": GEMINI_TTS_MODELS,
            "voices": [{"id": voice, "label": voice, "language": "auto"} for voice in GEMINI_TTS_VOICES],
            "languages": ["auto"],
            "formats": ["wav"],
            "supports": {"speed": False, "style": True, "emotion": False, "voiceCloning": False, "streaming": False},
            "notes": "Language is detected from the script. Style is sent as Gemini speech metadata.",
            "terms": "Sends the script to Google generativelanguage.googleapis.com. The key stays in the backend.",
        },
        {
            "id": "mistral",
            "label": "Mistral Voxtral TTS",
            "kind": "remote",
            "available": bool(keys.get("mistral")),
            "reason": "" if keys.get("mistral") else "Add a Mistral API key in Settings.",
            "requiresKey": "mistral",
            "models": MISTRAL_TTS_MODELS,
            "voices": [{"id": voice, "label": f"{voice} · {language}", "language": language} for voice, language in MISTRAL_TTS_VOICES],
            "languages": sorted({language for _, language in MISTRAL_TTS_VOICES}),
            "formats": ["wav", "mp3"],
            "supports": {"speed": False, "style": False, "emotion": False, "voiceCloning": False, "streaming": False},
            "notes": "Speech v1 preset voices verified live; styles are baked into the voice name. Cloning needs a reference upload and is not exposed yet.",
            "terms": "Sends the script to api.mistral.ai. The key stays in the backend.",
        },
    ]
    return {"providers": providers}


def _tts_provider(provider_id: str) -> dict:
    for provider in tts_provider_registry()["providers"]:
        if provider["id"] == provider_id:
            return provider
    raise ValueError("Unknown speech provider.")


def _sapi_synthesize(text: str, voice: str, rate: int, output: Path) -> None:
    powershell = shutil.which("powershell.exe")
    if not powershell:
        raise RuntimeError("Windows SAPI is not available.")
    safe_output = str(output).replace("'", "''")
    safe_voice = str(voice).replace("'", "''")
    script_path = output.with_suffix(".ps1")
    text_path = output.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8-sig")
    script_path.write_text(
        "Add-Type -AssemblyName System.Speech\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        f"$s.SelectVoice('{safe_voice}')\n"
        f"$s.Rate = {int(rate)}\n"
        f"$s.SetOutputToWaveFile('{safe_output}')\n"
        f"$s.Speak([IO.File]::ReadAllText('{str(text_path).replace(chr(39), chr(39) * 2)}'))\n"
        "$s.Dispose()\n",
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            capture_output=True, text=True, errors="replace", timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0 or not output.exists() or output.stat().st_size < 64:
            detail = (proc.stderr or proc.stdout or "").strip()[:400]
            raise RuntimeError(f"Windows speech failed: {detail or 'no audio produced'}")
    finally:
        script_path.unlink(missing_ok=True)
        text_path.unlink(missing_ok=True)


def _gemini_tts_synthesize(text: str, model: str, voice: str, style: str) -> bytes:
    key = _load_saved_keys().get("gemini", "")
    if not key:
        raise PermissionError("Gemini API key is not configured. Add it in Settings.")
    text_entry: dict = {"type": "text", "text": text}
    if style:
        text_entry["annotations"] = [{"type": "speech_metadata", "style": style}]
    body = {
        "model": model,
        "input": [{"type": "user_input", "content": [text_entry]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    request = urllib.request.Request(
        GEMINI_TTS_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"Gemini TTS rejected the request ({exc.code}): {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Gemini TTS: {exc.reason}") from exc
    return _gemini_tts_audio_bytes(data)


def _gemini_tts_audio_bytes(data) -> bytes:
    """Read WAV audio from an Interactions response (current and legacy shapes)."""
    output = None
    for step in data.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for item in step.get("content") or []:
            if (isinstance(item, dict) and item.get("type") == "audio"
                    and isinstance(item.get("data"), str) and item.get("data")):
                output = item
                break
        if output:
            break
    if output is None:
        legacy = data.get("output_audio") if isinstance(data, dict) else None
        if isinstance(legacy, dict) and isinstance(legacy.get("data"), str):
            output = legacy
    if not isinstance(output, dict) or not output.get("data"):
        raise RuntimeError("Gemini TTS returned no audio data.")
    mime = str(output.get("mime_type") or "").lower()
    if mime and "wav" not in mime:
        raise RuntimeError(f"Gemini TTS returned unsupported audio type: {mime}")
    try:
        return base64.b64decode(output["data"])
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Gemini TTS returned invalid audio data.") from exc


def _mistral_tts_synthesize(text: str, model: str, voice: str, audio_format: str) -> bytes:
    key = _load_saved_keys().get("mistral", "")
    if not key:
        raise PermissionError("Mistral API key is not configured. Add it in Settings.")
    body = {
        "model": model or MISTRAL_TTS_MODEL,
        "input": text,
        "voice_id": voice,
        "response_format": audio_format,
        "stream": False,
    }
    request = urllib.request.Request(
        MISTRAL_TTS_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"Mistral TTS rejected the request ({exc.code}): {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Mistral TTS: {exc.reason}") from exc
    encoded = data.get("audio_data") if isinstance(data, dict) else None
    if not encoded:
        raise RuntimeError("Mistral TTS returned no audio data.")
    try:
        return base64.b64decode(encoded)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Mistral TTS returned invalid audio data.") from exc


def synthesize_speech(payload: dict) -> dict:
    """Generate speech with the selected provider and return a normal media asset."""
    provider_id = str(payload.get("provider") or "").strip().lower()
    provider = _tts_provider(provider_id)
    text = str(payload.get("text") or "").strip()
    if not text:
        raise ValueError("Script text is required.")
    if len(text) > TTS_MAX_TEXT:
        raise ValueError(f"Scripts are limited to {TTS_MAX_TEXT} characters.")
    voice = str(payload.get("voice") or "").strip()
    if not any(item["id"] == voice for item in provider["voices"]):
        raise ValueError("Choose a voice offered by this provider.")
    model = str(payload.get("model") or "").strip() or provider["models"][0]["id"]
    if not any(item["id"] == model for item in provider["models"]):
        raise ValueError("Choose a model offered by this provider.")
    audio_format = str(payload.get("format") or "wav").lower().strip()
    if audio_format not in provider["formats"]:
        audio_format = "wav"
    try:
        speed = min(2.0, max(0.5, float(payload.get("speed", 1) or 1)))
    except (TypeError, ValueError):
        speed = 1.0
    style = str(payload.get("style") or "").strip()[:200]
    if not provider["supports"].get("style"):
        style = ""
    emotion = str(payload.get("emotion") or "").strip()[:100]
    if not provider["supports"].get("emotion"):
        emotion = ""
    if provider_id == "sapi" and not provider["available"]:
        raise RuntimeError(provider["reason"] or "Local speech is unavailable.")
    if provider.get("requiresKey") and not provider["available"]:
        raise PermissionError(provider["reason"] or f"{provider['label']} is not configured.")

    cache_request = {
        "version": TTS_CACHE_VERSION,
        "provider": provider_id,
        "model": model,
        "voice": voice,
        "text": text,
        "speed": round(speed, 2),
        "style": style,
        "emotion": emotion,
        "format": audio_format,
    }
    cache_key = hashlib.sha256(json.dumps(cache_request, sort_keys=True).encode("utf-8")).hexdigest()
    cache_path = _tts_dir() / f"{cache_key}.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            media_file = _media_dir() / str(cached.get("filename") or "")
            if media_file.exists() and media_file.stat().st_size > 64:
                return {**cached, "ok": True, "cached": True, "cacheKey": cache_key}
        except (OSError, ValueError):
            pass

    suffix = ".wav" if audio_format == "wav" else ".mp3"
    if provider_id == "sapi":
        with tempfile.TemporaryDirectory() as tmp_name:
            output = Path(tmp_name) / "speech.wav"
            rate = int(round((speed - 1.0) * 10))
            _sapi_synthesize(text, voice, max(-10, min(10, rate)), output)
            audio_bytes = output.read_bytes()
    elif provider_id == "gemini":
        audio_bytes = _gemini_tts_synthesize(text, model, voice, style)
    else:
        audio_bytes = _mistral_tts_synthesize(text, model, voice, audio_format)
    if len(audio_bytes) < 64:
        raise RuntimeError("The speech provider returned an empty audio file.")

    content_hash = hashlib.sha256(audio_bytes).hexdigest()[:20]
    filename = f"media-{content_hash}{suffix}"
    media_path = _media_dir() / filename
    if not media_path.exists():
        tmp_media = media_path.with_suffix(media_path.suffix + ".tmp")
        tmp_media.write_bytes(audio_bytes)
        os.replace(tmp_media, media_path)
    technical = _probe_media_technical(media_path)
    record = {
        "version": TTS_CACHE_VERSION,
        "provider": provider_id,
        "providerLabel": provider["label"],
        "model": model,
        "voice": voice,
        "voiceLabel": next((item["label"] for item in provider["voices"] if item["id"] == voice), voice),
        "speed": round(speed, 2),
        "style": style,
        "emotion": emotion,
        "format": audio_format,
        "chars": len(text),
        "textPreview": text[:120],
        "filename": filename,
        "url": f"/media/{filename}",
        "duration": technical.get("duration"),
        "sampleRate": technical.get("sampleRate"),
        "channels": technical.get("channels"),
        "bytes": len(audio_bytes),
        "local": provider["kind"] == "local",
        "createdAt": time.time(),
    }
    tmp_cache = cache_path.with_suffix(".json.tmp")
    tmp_cache.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_cache, cache_path)
    return {**record, "ok": True, "cached": False, "cacheKey": cache_key}


def _media_kind_for(filename: str) -> str:
    media_type = MEDIA_TYPES.get(Path(filename).suffix.lower())
    return media_type[0] if media_type else "file"


def _analysis_frame_dir(filename: str) -> Path:
    directory = _analysis_dir() / f"frames-{Path(filename).stem}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _detect_media_shots(path: Path, filename: str, technical: dict) -> list[dict]:
    """Offline shot boundaries via FFmpeg's scene score, with keyframe stills."""
    if _media_kind_for(filename) != "video":
        return []
    duration = technical.get("duration")
    scan_end = min(float(duration), SEMANTIC_SHOT_SCAN_SECONDS) if duration else None
    args = [FFMPEG_EXE, "-hide_banner", "-nostats"]
    if scan_end:
        args += ["-t", f"{scan_end:.3f}"]
    args += [
        "-i", str(path), "-an",
        "-vf", "scale=320:-2,select='gt(scene,0.3)',showinfo",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"  [SERVER] shot detection failed: {exc}")
        return []
    starts: list[float] = []
    for line in (proc.stderr or "").splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match = re.search(r"pts_time:\s*([0-9.]+)", line)
        if not match:
            continue
        moment = float(match.group(1))
        if moment <= 0.05 or (scan_end and moment >= scan_end - 0.1):
            continue
        if starts and moment - starts[-1] < 0.4:
            continue
        starts.append(moment)
        if len(starts) >= SEMANTIC_SHOT_LIMIT - 1:
            break
    boundaries = [0.0] + starts
    shots = []
    for index, start in enumerate(boundaries):
        end = boundaries[index + 1] if index + 1 < len(boundaries) else scan_end
        shots.append({
            "start": round(start, 3),
            "end": round(end, 3) if end is not None else None,
            "keyframe": None,
        })
    frame_dir = _analysis_frame_dir(filename)
    for index, shot in enumerate(shots[:SEMANTIC_KEYFRAME_LIMIT]):
        target = frame_dir / f"shot-{index:02d}.jpg"
        moment = shot["start"] + 0.15
        if shot["end"] is not None:
            moment = min(moment, max(shot["start"], shot["end"] - 0.05))
        if not target.exists():
            try:
                extract = subprocess.run(
                    [FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error",
                     "-ss", f"{moment:.3f}", "-i", str(path), "-frames:v", "1",
                     "-vf", "scale=640:-2", "-q:v", "4", str(target)],
                    capture_output=True, text=True, errors="replace", timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired):
                extract = None
            if (extract is None or extract.returncode != 0
                    or not target.exists() or target.stat().st_size < 128):
                target.unlink(missing_ok=True)
                continue
        shot["keyframe"] = f"/api/media/frames/{filename}/{index}.jpg"
    return shots


def _write_analysis_manifest(filename: str, manifest: dict) -> None:
    cache_path = _analysis_dir() / f"{filename}.json"
    temp_path = cache_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(temp_path, cache_path)


def analyze_media_file(filename: str) -> dict:
    """Return a cached technical analysis manifest for a stored media file."""
    if not MEDIA_NAME_RE.match(filename or ""):
        raise ValueError("Unknown media file.")
    path = _media_dir() / filename
    if not path.exists():
        raise FileNotFoundError("Media file not found.")
    cache_path = _analysis_dir() / f"{filename}.json"
    cached = None
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
    if (isinstance(cached, dict)
            and cached.get("analyzer", {}).get("version") == ANALYSIS_VERSION
            and cached.get("asset", {}).get("bytes") == path.stat().st_size):
        return cached
    technical = _probe_media_technical(path)
    content_hash = filename[len("media-"):].split(".")[0]
    manifest = {
        "asset": {
            "contentHash": content_hash,
            "filename": filename,
            "url": f"/media/{filename}",
            "bytes": technical["bytes"],
        },
        "technical": technical,
        "shots": _detect_media_shots(path, filename, technical),
        "semantic": {
            "status": "not_analyzed",
            "provider": None,
            "description": "",
            "subjects": [],
            "tags": [],
            "shots": [],
            "transcript": [],
            "suggestedUses": [],
            "confidence": 0,
        },
        "user": {"description": "", "notes": "", "updatedAt": None},
        "analyzer": {
            "version": ANALYSIS_VERSION,
            "engine": "ffmpeg-input-probe+scene-detect",
            "analyzedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }
    try:
        _write_analysis_manifest(filename, manifest)
    except OSError as exc:
        print(f"  [SERVER] analysis cache write failed: {exc}")
    return manifest


def semantic_provider_registry() -> dict:
    keys = _load_saved_keys()
    return {"providers": [{
        "id": "gemini",
        "label": "Google Gemini",
        "kind": "remote",
        "available": bool(keys.get("gemini")),
        "reason": "" if keys.get("gemini") else "Add a Gemini API key in Settings.",
        "models": [{"id": SEMANTIC_DEFAULT_MODEL, "label": "Gemini 2.5 Flash"}],
        "capabilities": {"vision": True, "transcript": True, "shotDetection": "local"},
        "maxInlineBytes": SEMANTIC_MAX_INLINE_BYTES,
        "terms": (
            "Uploads still frames of this asset (and its audio when transcription is enabled) "
            "to Google generativelanguage.googleapis.com. Keys stay in the backend; the original "
            "file never leaves this machine."
        ),
    }]}


def _semantic_frame_bytes(path: Path, filename: str, manifest: dict, kind: str) -> list[bytes]:
    frame_dir = _analysis_frame_dir(filename)
    frames: list[bytes] = []
    if kind == "image":
        target = frame_dir / "image.jpg"
        if not target.exists():
            subprocess.run(
                [FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
                 "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(target)],
                capture_output=True, text=True, errors="replace", timeout=30,
            )
        if target.exists() and target.stat().st_size > 128:
            frames.append(target.read_bytes())
        return frames
    for shot in manifest.get("shots") or []:
        match = re.search(r"/(\d+)\.jpg$", str(shot.get("keyframe") or ""))
        if not match:
            continue
        target = frame_dir / f"shot-{int(match.group(1)):02d}.jpg"
        if target.exists() and target.stat().st_size > 128:
            frames.append(target.read_bytes())
        if len(frames) >= SEMANTIC_MAX_FRAMES:
            break
    if not frames and kind == "video":
        target = frame_dir / "shot-00.jpg"
        if target.exists() and target.stat().st_size > 128:
            frames.append(target.read_bytes())
    return frames


def _semantic_audio_bytes(path: Path, kind: str, technical: dict) -> tuple[dict | None, str]:
    if kind == "audio":
        mime = {".mp3": "audio/mp3", ".wav": "audio/wav", ".flac": "audio/flac"}.get(path.suffix.lower())
        if not mime:
            raise ValueError("Transcription supports mp3, wav and flac audio files.")
        if path.stat().st_size > SEMANTIC_MAX_INLINE_BYTES:
            raise ValueError("This audio file is larger than the 20 MB inline limit; trim it first.")
        return {"bytes": path.read_bytes(), "mime": mime}, ""
    if kind != "video":
        return None, ""
    if not technical.get("audioCodec"):
        return None, "No audio track in this video."
    with tempfile.TemporaryDirectory() as tmp_name:
        output = Path(tmp_name) / "speech.mp3"
        try:
            proc = subprocess.run(
                [FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
                 "-vn", "-t", str(SEMANTIC_MAX_TRANSCRIPT_SECONDS), "-ac", "1", "-ar", "24000",
                 "-b:a", "48k", "-f", "mp3", str(output)],
                capture_output=True, text=True, errors="replace", timeout=180,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None, "Audio could not be extracted from this video."
        if proc.returncode != 0 or not output.exists() or output.stat().st_size < 256:
            return None, "Audio could not be extracted from this video."
        note = ""
        if float(technical.get("duration") or 0) > SEMANTIC_MAX_TRANSCRIPT_SECONDS:
            note = "Transcribed the first 5 minutes of audio."
        return {"bytes": output.read_bytes(), "mime": "audio/mp3"}, note


def _semantic_prompt(kind: str, frame_count: int, has_audio: bool, audio_note: str) -> str:
    parts = ["Analyze this media for a video editor's asset library and return JSON matching the schema."]
    if frame_count:
        parts.append(f"{frame_count} still frame(s) are attached in chronological order.")
    if has_audio:
        parts.append(
            "The audio track is attached; transcribe speech verbatim in the transcript array, "
            "using start seconds when you can estimate them (otherwise omit the start)."
        )
    if audio_note:
        parts.append(audio_note)
    parts.append(
        "Describe only what is visible or audible; do not invent brands, names or events. "
        "Use lowercase 1-3 word tags. confidence is a number from 0 to 1."
    )
    return " ".join(parts)


def _parse_semantic_result(data: dict) -> dict:
    texts: list[str] = []
    for step in data.get("steps") or []:
        if not isinstance(step, dict) or step.get("type") not in (None, "model_output"):
            continue
        for item in step.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                texts.append(item["text"])
    text = "\n".join(texts).strip()
    if not text and isinstance(data.get("output_text"), str):
        text = data["output_text"].strip()
    if not text:
        raise RuntimeError("Gemini returned no analysis text.")
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        raw = json.loads(text)
    except ValueError as exc:
        raise RuntimeError("Gemini returned content analysis that was not valid JSON.") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Gemini returned an unexpected content analysis shape.")

    def clean_text(value, limit: int) -> str:
        return str(value or "").strip()[:limit]

    def clean_list(value, limit: int, item_limit: int = 120) -> list[str]:
        return [
            item.strip()[:item_limit]
            for item in (value if isinstance(value, list) else [])
            if isinstance(item, str) and item.strip()
        ][:limit]

    transcript = []
    for segment in raw.get("transcript") or []:
        if isinstance(segment, str) and segment.strip():
            transcript.append({"start": None, "text": segment.strip()[:500]})
            continue
        if not isinstance(segment, dict):
            continue
        segment_text = clean_text(segment.get("text"), 500)
        if not segment_text:
            continue
        start = segment.get("start")
        try:
            start = round(float(start), 2) if start is not None and float(start) >= 0 else None
        except (TypeError, ValueError):
            start = None
        transcript.append({"start": start, "text": segment_text})
        if len(transcript) >= 200:
            break
    confidence = raw.get("confidence")
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "description": clean_text(raw.get("description"), 2000),
        "subjects": clean_list(raw.get("subjects"), 12),
        "tags": clean_list(raw.get("tags"), 24),
        "suggestedUses": clean_list(raw.get("suggestedUses"), 12),
        "transcript": transcript,
        "confidence": confidence,
    }


def semantic_media_file(filename: str, *, transcribe: bool) -> dict:
    """Run consent-gated hosted content analysis and merge it into the manifest."""
    if not MEDIA_NAME_RE.match(filename or ""):
        raise ValueError("Unknown media file.")
    path = _media_dir() / filename
    if not path.exists():
        raise FileNotFoundError("Media file not found.")
    api_key = _load_saved_keys().get("gemini", "")
    if not api_key:
        raise PermissionError("Add a Gemini API key in Settings to run content analysis.")
    manifest = analyze_media_file(filename)
    kind = _media_kind_for(filename)
    if kind == "audio" and not transcribe:
        raise ValueError("Audio assets are analyzed through transcription; enable it for this request.")
    frames = _semantic_frame_bytes(path, filename, manifest, kind)
    if not frames and kind != "audio":
        raise RuntimeError("No frames could be extracted from this asset.")
    audio_payload = None
    audio_note = ""
    if transcribe:
        audio_payload, audio_note = _semantic_audio_bytes(path, kind, manifest.get("technical") or {})
    content: list[dict] = [{
        "type": "text",
        "text": _semantic_prompt(kind, len(frames), bool(audio_payload), audio_note),
    }]
    for frame in frames:
        content.append({
            "type": "image",
            "data": base64.b64encode(frame).decode("ascii"),
            "mime_type": "image/jpeg",
        })
    if audio_payload:
        content.append({
            "type": "audio",
            "data": base64.b64encode(audio_payload["bytes"]).decode("ascii"),
            "mime_type": audio_payload["mime"],
        })
    body = {
        "model": SEMANTIC_DEFAULT_MODEL,
        "input": [{"type": "user_input", "content": content}],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": SEMANTIC_SCHEMA,
        },
    }
    try:
        data = ClipACanvasHandler._llm_http_post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            body,
            {"Content-Type": "application/json", "x-goog-api-key": api_key},
            timeout=90,
        )
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        raise RuntimeError(f"Gemini rejected the content analysis ({exc.code}): {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Gemini: {exc.reason}") from exc
    result = _parse_semantic_result(data)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["semantic"] = {
        "status": "analyzed",
        "provider": "gemini",
        "providerLabel": "Google Gemini",
        "model": SEMANTIC_DEFAULT_MODEL,
        "description": result["description"],
        "subjects": result["subjects"],
        "tags": result["tags"],
        "shots": [],
        "transcript": result["transcript"],
        "suggestedUses": result["suggestedUses"],
        "confidence": result["confidence"],
        "framesSent": len(frames),
        "audioSent": bool(audio_payload),
        "audioNote": audio_note,
        "consentAt": now,
        "analyzedAt": now,
        "terms": (
            "Frames%s uploaded to Google Gemini with explicit user consent."
            % (" and audio" if audio_payload else "")
        ),
    }
    try:
        _write_analysis_manifest(filename, manifest)
    except OSError as exc:
        raise RuntimeError(f"Analysis finished but could not be saved: {exc}") from exc
    return manifest



def _resolve_timeline_audio(raw_clips) -> list[dict]:
    """Map /media/... audio clips from the render payload to local file paths."""
    if not isinstance(raw_clips, list):
        return []
    directory = _media_dir()
    resolved: list[dict] = []
    for raw in raw_clips[:16]:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "")
        if not url.startswith("/media/"):
            continue
        name = Path(urllib.parse.unquote(url[len("/media/"):])).name
        if not MEDIA_NAME_RE.match(name):
            continue
        kind = MEDIA_TYPES.get(Path(name).suffix.lower(), ("", ""))[0]
        if kind != "audio":
            continue
        path = directory / name
        if not path.is_file():
            continue
        try:
            start = max(0.0, float(raw.get("start") or 0))
            source_in = max(0.0, float(raw.get("sourceIn") or 0))
            duration = max(0.05, float(raw.get("duration") or 0))
            volume = min(2.0, max(0.0, float(raw.get("volume", 1) if raw.get("volume") is not None else 1)))
        except (TypeError, ValueError):
            continue
        resolved.append({
            "path": str(path),
            "start": start,
            "sourceIn": source_in,
            "duration": duration,
            "volume": volume,
        })
    return resolved


_KEYS_VERSION = "v1"
_MASTER_KEY_FILE = "keys.key"
_MASTER_KEY_BYTES = 32
_AEAD_AAD_PREFIX = b"clipacanvas.keys.v1"
_MASTER_KEY_LOCK = threading.Lock()
_MASTER_KEY_CACHE = None


def _wrap_master_key(key: bytes) -> bytes:
    return _dpapi_protect(key) if IS_WINDOWS else key


def _unwrap_master_key(data: bytes) -> bytes:
    return _dpapi_unprotect(data) if IS_WINDOWS else data


def _load_master_key() -> bytes:
    global _MASTER_KEY_CACHE
    with _MASTER_KEY_LOCK:
        if _MASTER_KEY_CACHE is not None:
            return _MASTER_KEY_CACHE
        keys_dir = _keys_dir()
        keys_dir.mkdir(parents=True, exist_ok=True)
        key_file = keys_dir / _MASTER_KEY_FILE
        try:
            wrapped = key_file.read_bytes()
        except OSError:
            wrapped = b""
        if wrapped:
            try:
                key = _unwrap_master_key(wrapped)
                if len(key) == _MASTER_KEY_BYTES:
                    _MASTER_KEY_CACHE = key
                    return key
            except Exception:
                pass
            # Unreadable key (copied from another user/machine): keep it aside, do not silently clobber.
            try:
                os.replace(key_file, key_file.with_name(key_file.name + ".bak"))
            except OSError:
                pass
        key = os.urandom(_MASTER_KEY_BYTES)
        tmp_file = keys_dir / (_MASTER_KEY_FILE + ".tmp")
        tmp_file.write_bytes(_wrap_master_key(key))
        if not IS_WINDOWS:
            os.chmod(tmp_file, 0o600)
        os.replace(tmp_file, key_file)
        _MASTER_KEY_CACHE = key
        return key


def _aead_aad(provider: str) -> bytes:
    return _AEAD_AAD_PREFIX + b":" + provider.encode("utf-8")


def _encrypt_secret(provider: str, value: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_load_master_key()).encrypt(nonce, value.encode("utf-8"), _aead_aad(provider))
    return _KEYS_VERSION + ":" + base64.b64encode(nonce + ciphertext).decode("ascii")


def _decrypt_secret(provider: str, encoded: str) -> str:
    if encoded.startswith(_KEYS_VERSION + ":"):
        blob = base64.b64decode(encoded[len(_KEYS_VERSION) + 1:], validate=True)
        nonce, ciphertext = blob[:12], blob[12:]
        return AESGCM(_load_master_key()).decrypt(nonce, ciphertext, _aead_aad(provider)).decode("utf-8")
    # Legacy format: DPAPI-wrapped on Windows, plain base64 on other platforms.
    return _dpapi_unprotect(base64.b64decode(encoded)).decode("utf-8")


def _load_saved_keys() -> dict:
    keys = {"gemini": "", "mistral": ""}
    keys_file = _keys_dir() / "keys.dat"
    try:
        raw = json.loads(keys_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return keys
    if not isinstance(raw, dict):
        return keys
    legacy_found = False
    failed = False
    for provider in keys:
        encoded = raw.get(provider)
        if not isinstance(encoded, str) or not encoded:
            continue
        try:
            keys[provider] = _decrypt_secret(provider, encoded)
            if keys[provider] and not encoded.startswith(_KEYS_VERSION + ":"):
                legacy_found = True
        except Exception:
            keys[provider] = ""
            failed = True
    if legacy_found and not failed:
        try:
            _save_keys_to_disk(keys)
        except OSError:
            pass
    return keys


def _save_keys_to_disk(keys: dict) -> None:
    keys_dir = _keys_dir()
    keys_dir.mkdir(parents=True, exist_ok=True)
    raw = {}
    for provider in ("gemini", "mistral"):
        value = str(keys.get(provider, "") or "").strip()
        raw[provider] = _encrypt_secret(provider, value) if value else ""
    tmp_file = keys_dir / "keys.dat.tmp"
    tmp_file.write_text(json.dumps(raw), encoding="utf-8")
    if not IS_WINDOWS:
        os.chmod(tmp_file, 0o600)
    os.replace(tmp_file, keys_dir / "keys.dat")


_DEFAULT_PREFS = {
    "theme": "dark",
    "projectName": "UNTITLED PROJECT",
    "panels": {"colLeft": 300, "colRight": 344, "rowChat": 324},
    "fonts": {"family": "ibm-plex-mono", "sizePct": 100},
    "codeColors": {"text": "", "keyword": "", "string": "", "number": "", "comment": ""},
    "performance": {"gpuBoost": False},
}

_FONT_FAMILIES = ("ibm-plex-mono", "jetbrains-mono", "fira-code", "cascadia-code", "consolas", "courier-new")

# Older builds offered accent names that are no longer offered; map them onto
# the closest current theme so existing prefs files keep working.
_THEME_MIGRATION = {
    "lime": "dark", "daylight": "light", "arctic": "light",
}

_THEME_KEYS = ("dark", "light", "violet", "ember", "ocean", "rose", "mint", "gold")


def _sanitize_prefs(raw: dict) -> dict:
    prefs = json.loads(json.dumps(_DEFAULT_PREFS))
    if not isinstance(raw, dict):
        return prefs
    theme = raw.get("theme")
    if isinstance(theme, str):
        theme = _THEME_MIGRATION.get(theme, theme)
        if theme in _THEME_KEYS:
            prefs["theme"] = theme
    if isinstance(raw.get("panels"), dict):
        for key, limits in (("colLeft", (150, 480)), ("colRight", (260, 620)), ("rowChat", (110, 900))):
            value = raw["panels"].get(key)
            if isinstance(value, (int, float)):
                prefs["panels"][key] = int(min(max(value, limits[0]), limits[1]))
    project_name = raw.get("projectName")
    if isinstance(project_name, str):
        cleaned_name = project_name.strip()[:40]
        if cleaned_name:
            prefs["projectName"] = cleaned_name
    if isinstance(raw.get("fonts"), dict):
        if raw["fonts"].get("family") in _FONT_FAMILIES:
            prefs["fonts"]["family"] = raw["fonts"]["family"]
        size = raw["fonts"].get("sizePct")
        if isinstance(size, (int, float)):
            prefs["fonts"]["sizePct"] = int(min(max(size, 85), 130))
    if isinstance(raw.get("codeColors"), dict):
        for key in prefs["codeColors"]:
            value = raw["codeColors"].get(key)
            if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                prefs["codeColors"][key] = value.lower()
    if isinstance(raw.get("performance"), dict):
        boost = raw["performance"].get("gpuBoost")
        if isinstance(boost, bool):
            prefs["performance"]["gpuBoost"] = boost
    return prefs


def _load_prefs() -> dict:
    prefs_file = _keys_dir() / "prefs.json"
    try:
        raw = json.loads(prefs_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = None
    return _sanitize_prefs(raw if isinstance(raw, dict) else None)


def _save_prefs_to_disk(prefs: dict) -> None:
    prefs_dir = _keys_dir()
    prefs_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = prefs_dir / "prefs.json.tmp"
    tmp_file.write_text(json.dumps(prefs), encoding="utf-8")
    os.replace(tmp_file, prefs_dir / "prefs.json")


def _clean_chat_messages(messages) -> list:
    cleaned = []
    if not isinstance(messages, list):
        return cleaned
    for entry in messages:
        if isinstance(entry, dict) and entry.get('role') in ('user', 'assistant', 'render') and isinstance(entry.get('content'), str):
            item = {'role': entry['role'], 'content': entry['content']}
            if isinstance(entry.get('modelMeta'), dict):
                item['modelMeta'] = entry['modelMeta']
            if isinstance(entry.get('note'), str):
                item['note'] = entry['note']
            if isinstance(entry.get('codeBefore'), str) and entry['codeBefore']:
                item['codeBefore'] = entry['codeBefore']
            if isinstance(entry.get('codeAfter'), str) and entry['codeAfter']:
                item['codeAfter'] = entry['codeAfter']
            cleaned.append(item)
    return cleaned


def _chatlog_db_path() -> Path:
    return _keys_dir() / "chatlog.db"


def _chatlog_connect() -> sqlite3.Connection:
    db_path = _chatlog_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model_meta TEXT,
            note TEXT,
            code_before TEXT,
            created_at INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    if "code_before" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN code_before TEXT")
    if "code_after" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN code_after TEXT")
    _migrate_chatlog_json(conn)
    return conn


def _migrate_chatlog_json(conn: sqlite3.Connection) -> None:
    json_file = _keys_dir() / "chatlog.json"
    if not json_file.exists():
        return
    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    if count:
        return
    try:
        raw = json.loads(json_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(raw, list):
        sessions = [{"id": "legacy", "title": "Previous chat", "messages": raw}]
    elif isinstance(raw, dict):
        sessions = raw.get("sessions") or []
    else:
        return
    if not isinstance(sessions, list):
        return
    inserted = 0
    for session in sessions:
        if not isinstance(session, dict):
            continue
        messages = _clean_chat_messages(session.get("messages"))
        if not messages:
            continue
        session_id = str(session.get("id") or f"chat-{int(time.time() * 1000)}")
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, str(session.get("title") or "Previous chat")[:120],
             int(session.get("createdAt") or 0), int(session.get("updatedAt") or 0)),
        )
        conn.executemany(
            "INSERT INTO messages (session_id, role, content, model_meta, note, code_before, code_after) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (session_id, m["role"], m["content"],
                 json.dumps(m["modelMeta"]) if m.get("modelMeta") else None,
                 m.get("note") if isinstance(m.get("note"), str) else None,
                 m.get("codeBefore") if isinstance(m.get("codeBefore"), str) else None,
                 m.get("codeAfter") if isinstance(m.get("codeAfter"), str) else None)
                for m in messages
            ],
        )
        inserted += 1
    if inserted:
        conn.commit()
    try:
        os.replace(json_file, json_file.with_suffix(".json.bak"))
    except OSError:
        pass


def _load_chatlog() -> list:
    try:
        conn = _chatlog_connect()
    except sqlite3.Error:
        return []
    try:
        sessions = []
        for row in conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at, created_at"
        ):
            session = {
                "id": row[0],
                "title": row[1],
                "createdAt": row[2],
                "updatedAt": row[3],
                "messages": [],
            }
            for msg_row in conn.execute(
                "SELECT role, content, model_meta, note, code_before, code_after FROM messages WHERE session_id = ? ORDER BY id",
                (row[0],),
            ):
                item = {"role": msg_row[0], "content": msg_row[1]}
                if msg_row[2]:
                    try:
                        parsed = json.loads(msg_row[2])
                        if isinstance(parsed, dict):
                            item["modelMeta"] = parsed
                    except json.JSONDecodeError:
                        pass
                if msg_row[3]:
                    item["note"] = msg_row[3]
                if msg_row[4]:
                    item["codeBefore"] = msg_row[4]
                if msg_row[5]:
                    item["codeAfter"] = msg_row[5]
                session["messages"].append(item)
            sessions.append(session)
        return sessions
    finally:
        conn.close()


def _save_chatlog(sessions: list) -> None:
    try:
        conn = _chatlog_connect()
    except sqlite3.Error:
        return
    try:
        prepared = []
        for session in sessions:
            if not isinstance(session, dict):
                continue
            session_id = str(session.get("id") or "")
            messages = _clean_chat_messages(session.get("messages"))
            if not session_id or not messages:
                continue
            prepared.append((session, session_id, messages))
        if not prepared:
            # A save that carries no messages would replace the store with
            # nothing; the client only legitimately clears chats through the
            # per-session DELETE endpoint.
            existing = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            if existing:
                print("  [SERVER] refused empty chatlog save; keeping stored chats")
                return
        with conn:
            conn.execute("DELETE FROM sessions")
            for session, session_id, messages in prepared:
                conn.execute(
                    "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (session_id, str(session.get("title") or "")[:120],
                     int(session.get("createdAt") or 0), int(session.get("updatedAt") or 0)),
                )
                conn.executemany(
                    "INSERT INTO messages (session_id, role, content, model_meta, note, code_before, code_after) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (session_id, m["role"], m["content"],
                         json.dumps(m["modelMeta"]) if m.get("modelMeta") else None,
                         m.get("note") if isinstance(m.get("note"), str) else None,
                         m.get("codeBefore") if isinstance(m.get("codeBefore"), str) else None,
                         m.get("codeAfter") if isinstance(m.get("codeAfter"), str) else None)
                        for m in messages
                    ],
                )
    finally:
        conn.close()


def _delete_chatlog_session(session_id: str) -> bool:
    try:
        conn = _chatlog_connect()
    except sqlite3.Error:
        return False
    try:
        with conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


class ClipACanvasServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class ClipACanvasHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def translate_path(self, path):
        monaco_prefix = '/monaco/min/vs/'
        if path.startswith(monaco_prefix):
            dev_dir = APP_DIR / "node_modules" / "monaco-editor" / "min" / "vs"
            candidate = dev_dir / path[len(monaco_prefix):]
            if dev_dir.exists() and candidate.exists():
                return str(candidate)
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        cors_origin = self._cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            if cors_origin != "*":
                self.send_header("Vary", "Origin")
        super().end_headers()

    def do_OPTIONS(self):
        if self._origin_forbidden():
            self.send_error(403, "Origin not allowed")
            return
        self.send_response(204)
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        try:
            if self.path == '/':
                self.send_response(301)
                self.send_header('Location', '/clipacanvas.html')
                self.end_headers()
                return
            if self.path == '/api/config.js':
                return self._send_runtime_config()
            if self.path == '/api/project':
                return self._handle_project_get()
            if self.path == '/api/agent/plan':
                return self._handle_agent_plan_get(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            if self.path == '/api/projects':
                return self._handle_projects_get()
            if self.path == '/api/llm/keys':
                return self._handle_llm_keys_get()
            if self.path == '/api/llm/chatlog':
                return self._handle_chatlog_get()
            if self.path == '/api/prefs':
                return self._handle_prefs_get()
            if self.path == '/api/tts/providers':
                return self._handle_tts_providers()
            if self.path == '/api/media/semantic/providers':
                return self._handle_semantic_providers()
            if self.path == '/health':
                return self._send_json({'ok': True})
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/api/projects/open':
                return self._handle_projects_open(urllib.parse.parse_qs(parsed.query))
            if parsed.path == '/api/projects/recover':
                return self._handle_projects_recover(urllib.parse.parse_qs(parsed.query))
            if parsed.path == '/api/projects/session':
                return self._handle_projects_session()
            if parsed.path == '/render/frames':
                return self._handle_render_frames(urllib.parse.parse_qs(parsed.query))
            if parsed.path.startswith('/api/media/frames/'):
                return self._handle_analysis_frame(parsed.path[len('/api/media/frames/'):])
            if parsed.path.startswith('/media/'):
                return self._handle_media_get(parsed.path[len('/media/'):])
            return super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            print(f"  [SERVER] GET error: {exc}")
            self._safe_text_error('Backend request failed.', 500)

    def do_HEAD(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path.startswith('/media/'):
                return self._handle_media_get(parsed.path[len('/media/'):], head_only=True)
            return super().do_HEAD()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self):
        try:
            if self._origin_forbidden():
                self.send_error(403, "Origin not allowed")
                return
            if self.path == '/render':
                self._handle_render()
            elif self.path == '/api/project':
                self._handle_project_autosave()
            elif self.path == '/api/agent/plan':
                self._handle_agent_plan_post()
            elif self.path == '/api/projects':
                self._handle_projects_post()
            elif self.path == '/api/projects/rename':
                self._handle_projects_rename()
            elif self.path == '/api/projects/duplicate':
                self._handle_projects_duplicate()
            elif self.path == '/api/projects/delete':
                self._handle_projects_delete()
            elif self.path == '/api/media':
                self._handle_media_upload()
            elif self.path == '/api/media/analyze':
                self._handle_media_analyze()
            elif self.path == '/api/media/semantic':
                self._handle_media_semantic()
            elif self.path == '/api/tts/generate':
                self._handle_tts_generate()
            elif self.path == '/api/llm/chat':
                self._handle_llm_chat()
            elif self.path == '/api/llm/models':
                self._handle_llm_models()
            elif self.path == '/api/llm/keys':
                self._handle_llm_keys_post()
            elif self.path == '/api/llm/chatlog':
                self._handle_chatlog_post()
            elif self.path == '/api/prefs':
                self._handle_prefs_post()
            else:
                self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            print(f"  [SERVER] POST error: {exc}")
            self._safe_text_error('Backend render failed.', 500)

    def do_DELETE(self):
        try:
            if self._origin_forbidden():
                self.send_error(403, "Origin not allowed")
                return
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/api/llm/chatlog':
                self._handle_chatlog_delete(urllib.parse.parse_qs(parsed.query))
            else:
                self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            print(f"  [SERVER] DELETE error: {exc}")
            self._safe_text_error('Backend delete failed.', 500)

    def _handle_render(self):
        content_length = int(self.headers['Content-Length'])
        payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
        payload['audioClips'] = _resolve_timeline_audio(payload.get('audioClips'))
        render_id = str(payload.get('renderId') or '').strip()
        if _RENDER_ID_RE.match(render_id):
            try:
                _prune_render_frames()
                frames_dir = _render_frames_dir(render_id)
                frames_dir.mkdir(parents=True, exist_ok=True)
                payload['frameDir'] = str(frames_dir)
            except OSError:
                payload.pop('frameDir', None)
        codec = str(payload.get('codec', 'h264')).lower().strip()
        if codec not in CODEC_OUTPUT_FORMATS:
            codec = 'h264'
        output_extension = CODEC_OUTPUT_FORMATS[codec][0]

        node_renderer = APP_DIR / 'playwright_render.mjs'

        if not node_renderer.exists():
            node_renderer = None

        if node_renderer is None:
            try:
                import playwright_render  # noqa: F401
            except Exception:
                self._send_text_error('No Playwright renderer script is available.', 500)
                return

        if node_renderer is None and 'playwright_render' not in sys.modules:
            self._send_text_error('No Playwright renderer script is available.', 500)
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            out_filepath = os.path.join(tmpdir, f'output.{output_extension}')

            env = os.environ.copy()
            env['FFMPEG_EXE'] = resolve_ffmpeg_exe()
            result = None
            render_errors = []

            try:
                import playwright_render
                result_payload = playwright_render.render_payload(payload, out_filepath, ffmpeg_exe=env['FFMPEG_EXE'])
                result = subprocess.CompletedProcess(args=['python', 'playwright_render'], returncode=0, stderr=json.dumps(result_payload))
            except Exception as exc:
                render_errors.append(str(exc).strip() or 'Python renderer failed.')

            fallback_commands = []
            if node_renderer is not None:
                input_path = os.path.join(tmpdir, 'render-input.json')
                with open(input_path, 'w', encoding='utf-8') as f:
                    json.dump(payload, f)
                fallback_commands.append(['node', str(node_renderer), input_path, out_filepath])

            for cmd in fallback_commands:
                if result and result.returncode == 0 and os.path.exists(out_filepath):
                    break
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=APP_DIR,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=600
                    )
                except FileNotFoundError:
                    render_errors.append(f'Missing runtime for command: {" ".join(cmd[:2])}')
                    continue
                except subprocess.TimeoutExpired:
                    self._send_text_error('Playwright render timed out.', 504)
                    return

                if result.stderr.strip():
                    print(result.stderr.strip())

                if result.returncode == 0 and os.path.exists(out_filepath):
                    break

                render_errors.append(result.stderr.strip() or f'Renderer failed for command: {" ".join(cmd[:2])}')

            if not result or result.returncode != 0 or not os.path.exists(out_filepath):
                message = '\n'.join(err for err in render_errors if err) or 'Playwright rendering failed.'
                self._send_text_error(message, 500)
                return

            render_meta = self._parse_render_result(result)
            self._send_file(out_filepath, codec, render_meta)

    def _handle_render_frames(self, query):
        render_id = str((query.get('id') or [''])[0]).strip()
        if not _RENDER_ID_RE.match(render_id):
            self._send_json({'ok': False, 'error': 'Invalid render id.'}, 400)
            return
        frame_dir = _render_frames_dir(render_id)
        frame_number = str((query.get('n') or [''])[0]).strip()
        if frame_number:
            if not frame_number.isdigit():
                self._send_text_error('Frame not found.', 404)
                return
            frame_path = frame_dir / f'frame_{int(frame_number):05d}.jpg'
            try:
                data = frame_path.read_bytes() if frame_path.is_file() else b''
            except OSError:
                data = b''
            if not data:
                self._send_text_error('Frame not found.', 404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        frames = []
        total = 0
        if frame_dir.is_dir():
            try:
                meta_path = frame_dir / 'meta.json'
                if meta_path.is_file():
                    meta = json.loads(meta_path.read_text(encoding='utf-8'))
                    total = int(meta.get('totalFrames') or 0)
            except (OSError, ValueError, TypeError):
                total = 0
            try:
                for entry in frame_dir.iterdir():
                    match = _RENDER_FRAME_RE.match(entry.name)
                    if not match:
                        continue
                    index = int(match.group(1))
                    frames.append({
                        'index': index,
                        'url': f"/render/frames?id={urllib.parse.quote(render_id)}&n={index}"
                    })
            except OSError:
                frames = []
        frames.sort(key=lambda item: item['index'])
        self._send_json({'ok': True, 'frames': frames, 'total': total})

    def _handle_llm_chat(self):
        content_length = int(self.headers.get('Content-Length', 0) or 0)
        if content_length <= 0:
            self._send_json({'ok': False, 'error': 'Empty request body.'}, 400)
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({'ok': False, 'error': 'Invalid JSON body.'}, 400)
            return

        provider = str(payload.get('provider', 'gemini')).strip().lower() or 'gemini'
        api_key = str(payload.get('apiKey', '')).strip()
        model = str(payload.get('model', '')).strip()
        messages = payload.get('messages')
        allow_fallback = bool(payload.get('allowFallback', False))

        if provider not in ('mistral', 'gemini'):
            self._send_json({'ok': False, 'error': 'Provider must be "mistral" or "gemini".'}, 400)
            return
        if not api_key:
            self._send_json({'ok': False, 'error': 'Missing API key.'}, 400)
            return
        if not isinstance(messages, list) or not messages:
            self._send_json({'ok': False, 'error': 'Messages must be a non-empty list.'}, 400)
            return

        default_model = 'mistral-small-latest' if provider == 'mistral' else 'gemini-2.5-flash'
        requested_model = model or default_model
        use_tools = bool(payload.get('tools', False))
        tools_requested = use_tools
        tools_dropped = False

        try:
            text = ''
            tool_calls = []
            used_model = None
            current = requested_model
            tried = []
            attempt = 0
            model_retries = 0
            last_error = None
            # Skip a model that recently hit its daily quota instead of spending
            # another request on a guaranteed 429.
            if allow_fallback and _model_cooldown_remaining(provider, current) > 0:
                try:
                    candidates = self._mistral_models(api_key) if provider == 'mistral' else self._gemini_models(api_key)
                    candidate_names = [str(cand.get('name', '')) for cand in candidates]
                except Exception:
                    candidate_names = []
                for name in candidate_names:
                    if _model_cooldown_remaining(provider, name) <= 0:
                        print(f"  [SERVER] {current} is rate-limited, switching to {name}")
                        current = name
                        break
            while attempt < 4:
                tried.append(current)
                try:
                    if provider == 'mistral':
                        result = self._mistral_chat(api_key, messages, current, use_tools)
                    else:
                        result = self._gemini_chat(api_key, messages, current, use_tools)
                    text = str(result.get('text') or '').strip()
                    tool_calls = result.get('toolCalls') or []
                    if text or tool_calls:
                        used_model = current
                        break
                    raise RuntimeError('Provider returned reasoning only with no text.')
                except urllib.error.HTTPError as exc:
                    detail = ''
                    try:
                        detail = exc.read().decode('utf-8', errors='replace')[:600]
                    except Exception:
                        pass
                    # Some models on the list (e.g. gemma) reject tool schemas;
                    # retry the same model as plain text before any fallback.
                    if use_tools and exc.code == 400 and ('tool' in detail.lower() or 'function' in detail.lower()):
                        print(f"  [SERVER] {current} rejected tools, retrying without them")
                        use_tools = False
                        tools_dropped = True
                        continue
                    exc._clip_detail = detail
                    last_error = exc
                    if exc.code == 429:
                        # Free-tier quota is per model, so remember when this one
                        # frees up and let AUTO try a sibling model.
                        _set_model_cooldown(provider, current, _retry_delay_seconds(detail))
                    if exc.code in (423, 500, 502, 503, 504) and model_retries < 2:
                        # Provider overload, gateway hiccup or a transient lock:
                        # retry the same model with a short backoff before fallback.
                        model_retries += 1
                        delay = min(8.0, 1.5 * (2 ** (model_retries - 1)))
                        print(f"  [SERVER] {provider}/{current} returned {exc.code}; retrying in {delay:.1f}s")
                        time.sleep(delay)
                        continue
                except Exception as exc:
                    last_error = exc
                    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)) and model_retries < 2:
                        model_retries += 1
                        delay = min(8.0, 1.5 * (2 ** (model_retries - 1)))
                        print(f"  [SERVER] {provider}/{current} network error ({type(exc).__name__}); retrying in {delay:.1f}s")
                        time.sleep(delay)
                        continue
                if not allow_fallback:
                    break
                try:
                    candidates = self._mistral_models(api_key) if provider == 'mistral' else self._gemini_models(api_key)
                    names = [str(cand.get('name', '')) for cand in candidates]
                except Exception:
                    break
                start = names.index(current) + 1 if current in names else 0
                ordered = names[start:] + names[:start]
                next_model = None
                for name in ordered:
                    if name in tried or _model_cooldown_remaining(provider, name) > 0:
                        continue
                    next_model = name
                    break
                if not next_model:
                    break
                print(f"  [SERVER] LLM fallback: {current} failed ({type(last_error).__name__}), retrying with {next_model}")
                current = next_model
                model_retries = 0
                attempt += 1
            if used_model is None:
                raise last_error or RuntimeError('LLM request failed.')
        except urllib.error.HTTPError as exc:
            detail = getattr(exc, '_clip_detail', '') or ''
            if not detail:
                try:
                    detail = exc.read().decode('utf-8', errors='replace')[:600]
                except Exception:
                    pass
            print(f"  [SERVER] LLM provider error ({provider}, {exc.code}): {detail}")
            if exc.code == 429:
                last_model = tried[-1] if tried else requested_model
                retry_seconds = _retry_delay_seconds(detail) or _model_cooldown_remaining(provider, last_model)
                print(f"  [SERVER] {provider}/{last_model} quota exhausted for {_human_duration(retry_seconds) if retry_seconds else 'a while'}")
                self._send_json({
                    'ok': False,
                    'error': _rate_limit_message(provider, last_model, retry_seconds, len(tried) > 1),
                    'detail': detail,
                    'retryAfterSeconds': retry_seconds,
                }, 429)
                return
            if exc.code == 423:
                message = f'{provider.capitalize()} locked this request (423). Try a different model.'
            elif exc.code in (500, 502, 503, 504):
                message = f'{provider.capitalize()} is temporarily unavailable ({exc.code}) after retries. Retry in a moment or switch models.'
            else:
                message = f'{provider.capitalize()} API error ({exc.code}).'
            self._send_json({'ok': False, 'error': message, 'detail': detail}, 502)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            print(f"  [SERVER] LLM network error ({provider}): {exc}")
            self._send_json({
                'ok': False,
                'error': f'Could not reach {provider.capitalize()} API after retries. Check the network or switch providers.',
            }, 502)
            return
        except Exception as exc:
            print(f"  [SERVER] LLM error ({provider}): {exc}")
            if 'reasoning only' in str(exc):
                self._send_json({'ok': False, 'error': 'The model returned no readable reply (internal reasoning only). Try again or pick another model.'}, 502)
            else:
                self._send_json({'ok': False, 'error': 'LLM request failed.'}, 502)
            return

        self._send_json({
            'ok': True,
            'provider': provider,
            'model': used_model or requested_model,
            'text': text,
            'toolCalls': tool_calls,
            'tools': use_tools,
            'toolsDisabled': bool(tools_requested and tools_dropped),
        })

    def _handle_llm_models(self):
        content_length = int(self.headers.get('Content-Length', 0) or 0)
        if content_length <= 0:
            self._send_json({'ok': False, 'error': 'Empty request body.'}, 400)
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({'ok': False, 'error': 'Invalid JSON body.'}, 400)
            return

        provider = str(payload.get('provider', 'gemini')).strip().lower() or 'gemini'
        api_key = str(payload.get('apiKey', '')).strip()
        if provider not in ('mistral', 'gemini'):
            self._send_json({'ok': False, 'error': 'Provider must be "mistral" or "gemini".'}, 400)
            return
        if not api_key:
            self._send_json({'ok': False, 'error': 'Missing API key.'}, 400)
            return

        try:
            models = self._mistral_models(api_key) if provider == 'mistral' else self._gemini_models(api_key)
        except urllib.error.HTTPError as exc:
            detail = ''
            try:
                detail = exc.read().decode('utf-8', errors='replace')[:600]
            except Exception:
                pass
            print(f"  [SERVER] LLM models error ({provider}, {exc.code}): {detail}")
            self._send_json({'ok': False, 'error': f'{provider.capitalize()} API error ({exc.code}).', 'detail': detail}, 502)
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            print(f"  [SERVER] LLM models network error ({provider}): {exc}")
            self._send_json({'ok': False, 'error': f'Could not reach {provider.capitalize()} API.'}, 502)
            return
        except Exception as exc:
            print(f"  [SERVER] LLM models error ({provider}): {exc}")
            self._send_json({'ok': False, 'error': 'Could not load models.'}, 502)
            return

        self._send_json({'ok': True, 'models': models})

    def _handle_llm_keys_get(self):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        self._send_json({'ok': True, 'keys': _load_saved_keys()})

    def _handle_llm_keys_post(self):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        content_length = int(self.headers.get('Content-Length', 0) or 0)
        if content_length <= 0:
            self._send_json({'ok': False, 'error': 'Empty request body.'}, 400)
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({'ok': False, 'error': 'Invalid JSON body.'}, 400)
            return
        keys = _load_saved_keys()
        for provider in keys:
            if provider in payload and isinstance(payload[provider], str):
                keys[provider] = payload[provider].strip()
        _save_keys_to_disk(keys)
        self._send_json({'ok': True, 'keys': keys})

    def _handle_chatlog_get(self):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        self._send_json({'ok': True, 'sessions': _load_chatlog()})

    def _handle_prefs_get(self):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        self._send_json({'ok': True, 'prefs': _load_prefs()})

    def _handle_prefs_post(self):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        content_length = int(self.headers.get('Content-Length', 0) or 0)
        if content_length <= 0:
            self._send_json({'ok': False, 'error': 'Empty request body.'}, 400)
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({'ok': False, 'error': 'Invalid JSON body.'}, 400)
            return
        merged = _load_prefs()
        if isinstance(payload.get('theme'), str):
            merged['theme'] = payload['theme']
        if isinstance(payload.get('projectName'), str):
            merged['projectName'] = payload['projectName']
        if isinstance(payload.get('panels'), dict):
            merged['panels'] = {**merged['panels'], **payload['panels']}
        if isinstance(payload.get('fonts'), dict):
            merged['fonts'] = {**merged['fonts'], **payload['fonts']}
        if isinstance(payload.get('codeColors'), dict):
            merged['codeColors'] = {**merged['codeColors'], **payload['codeColors']}
        if isinstance(payload.get('performance'), dict):
            merged['performance'] = {**merged['performance'], **payload['performance']}
        merged = _sanitize_prefs(merged)
        _save_prefs_to_disk(merged)
        self._send_json({'ok': True, 'prefs': merged})

    def _handle_chatlog_post(self):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        content_length = int(self.headers.get('Content-Length', 0) or 0)
        if content_length <= 0:
            self._send_json({'ok': False, 'error': 'Empty request body.'}, 400)
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({'ok': False, 'error': 'Invalid JSON body.'}, 400)
            return
        sessions = payload.get('sessions')
        if not isinstance(sessions, list):
            self._send_json({'ok': False, 'error': 'sessions must be a list.'}, 400)
            return
        cleaned_sessions = []
        for session in sessions:
            if not isinstance(session, dict):
                continue
            messages = _clean_chat_messages(session.get('messages'))
            if not messages:
                continue
            cleaned_sessions.append({
                'id': str(session.get('id') or ''),
                'title': str(session.get('title') or '')[:120],
                'createdAt': int(session.get('createdAt') or 0),
                'updatedAt': int(session.get('updatedAt') or 0),
                'messages': messages,
            })
        _save_chatlog(cleaned_sessions)
        self._send_json({'ok': True, 'sessions': cleaned_sessions})

    def _handle_chatlog_delete(self, query):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        session_id = (query.get("id") or [""])[0]
        if not session_id:
            self._send_json({'ok': False, 'error': 'Missing session id.'}, 400)
            return
        self._send_json({'ok': True, 'deleted': _delete_chatlog_session(session_id)})

    @staticmethod
    def _llm_http_post(url, body, headers, timeout=180):
        request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))

    @staticmethod
    def _llm_http_get(url, headers, timeout=30):
        request = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))

    def _gemini_models(self, api_key):
        url = f'https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(api_key)}'
        data = self._llm_http_get(url, {'Content-Type': 'application/json'})

        excluded_tokens = ('tts', 'image', 'nano-banana', 'transcribe', 'customtools', 'computer-use', 'robotics', 'omni')
        # Upstream hangs (no HTTP response, ~40s timeouts) — exclude so AUTO
        # routing and the fallback loop never start on a dead model.
        excluded_names = {
            'models/gemini-3.8-flash',
            'models/gemini-3.7-flash',
            'models/gemini-flash-latest',
        }
        models = []
        for entry in data.get('models', []):
            name = str(entry.get('name', ''))
            if not (name.startswith('models/gemini-') or name.startswith('models/gemma-')):
                continue
            lowered = name.lower()
            if lowered in excluded_names:
                continue
            if any(token in lowered for token in excluded_tokens):
                continue
            if 'generateContent' not in (entry.get('supportedGenerationMethods') or []):
                continue
            models.append({
                'name': name,
                'displayName': str(entry.get('displayName') or name),
                'description': str(entry.get('description') or ''),
                'inputTokenLimit': entry.get('inputTokenLimit'),
                'outputTokenLimit': entry.get('outputTokenLimit'),
            })
        models.sort(key=_model_sort_key, reverse=True)
        return models

    def _gemini_chat(self, api_key, messages, model, tools=False):
        system_parts = []
        contents = []
        pending_tool_parts = []

        def flush_tool_parts():
            if pending_tool_parts:
                contents.append({'role': 'user', 'parts': list(pending_tool_parts)})
                pending_tool_parts.clear()

        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get('role', 'user')).lower()
            text = str(message.get('content') or '').strip()
            if role == 'system':
                if text:
                    system_parts.append(text)
                continue
            if role == 'tool':
                pending_tool_parts.append({
                    'functionResponse': {
                        'name': str(message.get('name') or 'tool'),
                        'response': {'result': _tool_result_value(text)},
                    }
                })
                continue
            flush_tool_parts()
            if role == 'assistant':
                parts = []
                if text:
                    parts.append({'text': text})
                for call in message.get('toolCalls') or []:
                    if not isinstance(call, dict):
                        continue
                    raw = call.get('raw')
                    if isinstance(raw, dict) and isinstance(raw.get('functionCall'), dict):
                        # Echo the original part so Gemini 3 thought signatures survive.
                        parts.append(raw)
                    elif call.get('name'):
                        args = call.get('args')
                        parts.append({'functionCall': {'name': str(call['name']), 'args': args if isinstance(args, dict) else {}}})
                if parts:
                    contents.append({'role': 'model', 'parts': parts})
                continue
            if text:
                contents.append({'role': 'user', 'parts': [{'text': text}]})
        flush_tool_parts()
        if not contents:
            raise RuntimeError('No chat content for Gemini request.')

        body = {'contents': contents}
        if system_parts:
            body['systemInstruction'] = {'parts': [{'text': '\n\n'.join(system_parts)}]}
        if tools:
            body['tools'] = [{'functionDeclarations': _gemini_tool_declarations()}]

        model_name = str(model).strip()
        if model_name.startswith('models/'):
            model_name = model_name[len('models/'):]

        url = f'https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model_name)}:generateContent?key={urllib.parse.quote(api_key)}'
        data = self._llm_http_post(url, body, {'Content-Type': 'application/json'}, timeout=150)
        try:
            parts = data['candidates'][0]['content']['parts']
        except (KeyError, IndexError, TypeError):
            raise RuntimeError('Unexpected Gemini response shape.')
        texts = []
        tool_calls = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            function_call = part.get('functionCall')
            if isinstance(function_call, dict):
                args = function_call.get('args')
                tool_calls.append({
                    'id': '',
                    'name': str(function_call.get('name') or ''),
                    'args': args if isinstance(args, dict) else {},
                    'raw': part,
                })
                continue
            if part.get('thought'):
                continue
            text = part.get('text')
            if isinstance(text, str):
                texts.append(text)
        return {'text': ''.join(texts).strip(), 'toolCalls': tool_calls}

    def _mistral_chat(self, api_key, messages, model, tools=False):
        converted = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get('role', 'user')).lower()
            text = str(message.get('content') or '').strip()
            if role == 'tool':
                converted.append({
                    'role': 'tool',
                    'tool_call_id': str(message.get('toolCallId') or ''),
                    'name': str(message.get('name') or 'tool'),
                    'content': text,
                })
                continue
            if role == 'assistant':
                item = {'role': 'assistant', 'content': text}
                calls = []
                for call in message.get('toolCalls') or []:
                    if not isinstance(call, dict):
                        continue
                    raw = call.get('raw')
                    if isinstance(raw, dict) and raw.get('function'):
                        calls.append(raw)
                    elif call.get('name'):
                        calls.append({
                            'id': str(call.get('id') or ''),
                            'type': 'function',
                            'function': {
                                'name': str(call['name']),
                                'arguments': json.dumps(call.get('args') or {}),
                            },
                        })
                if calls:
                    item['tool_calls'] = calls
                if text or calls:
                    converted.append(item)
                continue
            if text:
                converted.append({'role': role if role in ('system', 'user') else 'user', 'content': text})

        body = {'model': model, 'messages': converted}
        if tools:
            body['tools'] = _mistral_tool_declarations()
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        data = self._llm_http_post('https://api.mistral.ai/v1/chat/completions', body, headers, timeout=150)
        try:
            message = data['choices'][0]['message']
        except (KeyError, IndexError, TypeError):
            raise RuntimeError('Unexpected Mistral response shape.')

        content = message.get('content')
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if str(part.get('type', '')).lower() != 'text':
                    continue
                piece = part.get('text')
                if isinstance(piece, str) and piece.strip():
                    parts.append(piece)
            text = '\n'.join(parts).strip()
        else:
            text = ''

        tool_calls = []
        for call in message.get('tool_calls') or []:
            if not isinstance(call, dict):
                continue
            function = call.get('function') or {}
            args = function.get('arguments')
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {'value': args}
            tool_calls.append({
                'id': str(call.get('id') or ''),
                'name': str(function.get('name') or ''),
                'args': args if isinstance(args, dict) else {},
                'raw': call,
            })
        return {'text': text, 'toolCalls': tool_calls}

    def _mistral_models(self, api_key):
        data = self._llm_http_get(
            'https://api.mistral.ai/v1/models',
            {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'},
        )
        excluded_tokens = ('embed', 'moderation', 'ocr', 'fim', 'vibe-cli', 'voxtral')
        allowed_prefixes = ('mistral-', 'ministral-', 'codestral-', 'magistral-')
        models = []
        for entry in data.get('data', []):
            model_id = str(entry.get('id', ''))
            lowered = model_id.lower()
            if not any(lowered.startswith(prefix) for prefix in allowed_prefixes):
                continue
            if any(token in lowered for token in excluded_tokens):
                continue
            models.append({
                'name': model_id,
                'displayName': model_id,
                'description': str(entry.get('description') or ''),
                'inputTokenLimit': None,
                'outputTokenLimit': None,
            })
        models.sort(key=_mistral_model_sort_key, reverse=True)
        return models

    @staticmethod
    def _parse_render_result(result):
        if not result or not getattr(result, 'stderr', None):
            return {}
        for line in reversed(str(result.stderr).splitlines()):
            line = line.strip()
            if not line.startswith('{') or not line.endswith('}'):
                continue
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    return payload
            except json.JSONDecodeError:
                continue
        return {}

    def _send_file(self, filepath, codec='h264', render_meta=None):
        ext, mime = _codec_output(codec)
        filename = f'clipacanvas_{time.strftime("%Y%m%d_%H%M%S")}.{ext}'
        render_meta = render_meta or {}

        with open(filepath, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Content-Disposition', f'inline; filename="{filename}"')
        self.send_header('X-Render-Filename', filename)
        self.send_header('X-Render-Duration', str(render_meta.get('duration', '')))
        self.send_header('X-Render-Frame-Count', str(render_meta.get('frameCount', '')))
        self.send_header('X-Render-Codec', str(render_meta.get('codec', codec)))
        self.send_header('X-Render-Encoder', str(render_meta.get('encoder', '')))
        self.send_header('X-Render-Content-Hash', str(render_meta.get('contentHash', '')))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return
        print(f"  [SERVER] OK Sent temporary render: {filename}")

    def _handle_media_get(self, raw_name, head_only=False):
        name = urllib.parse.unquote(raw_name)
        media_type = MEDIA_TYPES.get(Path(name).suffix.lower())
        if not MEDIA_NAME_RE.match(name) or not media_type:
            return self._safe_text_error('Media not found.', 404)
        path = _media_dir() / name
        try:
            size = path.stat().st_size
            file_handle = path.open('rb')
        except OSError:
            return self._safe_text_error('Media not found.', 404)
        try:
            if size <= 0:
                self.send_response(416)
                self.send_header('Content-Range', 'bytes */0')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            start = 0
            end = size - 1
            status = 200
            range_header = (self.headers.get('Range') or '').strip()
            match = re.match(r'bytes=(\d*)-(\d*)$', range_header)
            if match and (match.group(1) or match.group(2)):
                if match.group(1):
                    start = int(match.group(1))
                    end = int(match.group(2)) if match.group(2) else size - 1
                else:
                    start = max(0, size - int(match.group(2)))
                if start >= size or start > end:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                end = min(end, size - 1)
                status = 206
            length = end - start + 1
            self.send_response(status)
            self.send_header('Content-Type', media_type[1])
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(length))
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            if head_only:
                return
            file_handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = file_handle.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            file_handle.close()

    def _read_project_body(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._send_json({'ok': False, 'error': 'Empty project payload.'}, 400)
            return None
        if length > PROJECT_MAX_BYTES:
            self._send_json({'ok': False, 'error': 'Project payload is too large.'}, 413)
            return None
        return self.rfile.read(length)

    def _handle_project_autosave(self):
        raw = self._read_project_body()
        if raw is None:
            return
        try:
            doc = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid JSON.'}, 400)
        error = _validate_project_doc(doc)
        if error:
            return self._send_json({'ok': False, 'error': error}, 400)
        project_id = str(doc.get('projectId') or '').strip()
        if project_id:
            if not PROJECT_ID_RE.match(project_id):
                return self._send_json({'ok': False, 'error': 'Invalid project id.'}, 400)
            entry = _find_project_entry(_read_project_index(), project_id)
            if entry is None:
                return self._send_json({'ok': False, 'error': 'Project is not in the project library.'}, 409)
            try:
                _write_text_atomic(_project_autosave_path(project_id), json.dumps(doc, ensure_ascii=False))
                _write_session(project_id, str(entry.get('name') or ''), str(doc.get('savedAt') or ''))
            except OSError as exc:
                return self._send_json({'ok': False, 'error': f'Project autosave failed: {exc}'}, 500)
            return self._send_json({
                'ok': True,
                'projectId': project_id,
                'savedAt': str(doc.get('savedAt') or ''),
                'bytes': len(raw),
            })
        # Legacy single-slot autosave for surfaces that are not project-aware.
        try:
            _write_text_atomic(_projects_dir() / PROJECT_AUTOSAVE_NAME, json.dumps(doc, ensure_ascii=False))
        except OSError as exc:
            return self._send_json({'ok': False, 'error': f'Project autosave failed: {exc}'}, 500)
        self._send_json({'ok': True, 'savedAt': str(doc.get('savedAt') or ''), 'bytes': len(raw), 'legacy': True})

    def _handle_project_get(self):
        path = _projects_dir() / PROJECT_AUTOSAVE_NAME
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            doc = None
        self._send_json({'ok': True, 'project': doc})

    def _handle_projects_get(self):
        entries = _read_project_index()
        self._send_json({'ok': True, 'projects': [_project_entry_meta(entry) for entry in entries]})

    def _handle_projects_session(self):
        entries = _read_project_index()
        session = _read_session()
        payload = None
        if session:
            project_id = str(session.get('projectId') or '')
            valid_id = bool(PROJECT_ID_RE.match(project_id))
            entry = _find_project_entry(entries, project_id) if valid_id else None
            saved_at = _project_saved_at(_projects_dir() / str(entry.get('file'))) if entry else ''
            autosave_saved_at = _project_saved_at(_project_autosave_path(project_id)) if valid_id else ''
            recoverable = bool(autosave_saved_at) and (not saved_at or autosave_saved_at > saved_at)
            payload = {
                'projectId': project_id,
                'name': str((entry or {}).get('name') or session.get('name') or 'LAST SESSION'),
                'savedAt': autosave_saved_at or str(session.get('savedAt') or ''),
                'recoverable': recoverable,
                'missing': entry is None,
            }
        legacy = None
        legacy_doc = _read_json_path(_projects_dir() / PROJECT_AUTOSAVE_NAME)
        if isinstance(legacy_doc, dict) and legacy_doc.get('format') == PROJECT_FORMAT:
            legacy_saved = legacy_doc.get('savedAt') if isinstance(legacy_doc.get('savedAt'), str) else ''
            # Compare against recorded save times only; a corrupt file's mtime
            # must not hide a genuinely newer legacy autosave.
            newest = max((str(entry.get('savedAt') or _project_entry_meta(entry)['savedAt']) for entry in entries), default='')
            if legacy_saved and legacy_saved > newest:
                legacy = {
                    'legacy': True,
                    'name': str(legacy_doc.get('projectName') or 'LAST SESSION'),
                    'savedAt': legacy_saved,
                }
        self._send_json({'ok': True, 'session': payload, 'legacy': legacy})

    def _handle_projects_post(self):
        raw = self._read_project_body()
        if raw is None:
            return
        try:
            body = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid JSON.'}, 400)
        if not isinstance(body, dict):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid.'}, 400)
        doc = body.get('project')
        error = _validate_project_doc(doc)
        if error:
            return self._send_json({'ok': False, 'error': error}, 400)
        entries = _read_project_index()
        project_id = str(body.get('id') or '').strip()
        display = str(body.get('name') or doc.get('projectName') or 'project').strip()[:60] or 'project'
        if project_id:
            entry = _find_project_entry(entries, project_id)
            if entry is None:
                return self._send_json({'ok': False, 'error': 'Project not found.'}, 404)
            file_name = str(entry.get('file') or '')
            if not PROJECT_FILE_RE.match(file_name):
                return self._send_json({'ok': False, 'error': 'Project file name is invalid.'}, 400)
            doc = dict(doc)
            doc['projectId'] = project_id
            doc['projectName'] = display
            saved_at = str(doc.get('savedAt') or '') or _now_iso()
            doc['savedAt'] = saved_at
            try:
                _write_text_atomic(_projects_dir() / file_name, json.dumps(doc, ensure_ascii=False))
            except OSError as exc:
                return self._send_json({'ok': False, 'error': f'Project save failed: {exc}'}, 500)
            entry = dict(entry)
            entry['id'] = project_id
            entry['name'] = display.upper()
            entry['savedAt'] = saved_at
            entries = [item for item in entries if _project_entry_id(item) != project_id]
            entries.insert(0, entry)
            _write_project_index(entries[:50])
            session = _read_session()
            if session and session.get('projectId') == project_id:
                _write_session(project_id, entry['name'], saved_at)
            return self._send_json({'ok': True, 'project': _project_entry_meta(entry)})
        stem = _unique_project_stem(display, entries)
        filename = f'{stem}.ccproj.json'
        if not PROJECT_FILE_RE.match(filename):
            return self._send_json({'ok': False, 'error': 'Project name cannot be used as a file name.'}, 400)
        doc = dict(doc)
        doc['projectId'] = stem
        doc['projectName'] = display
        doc['savedAt'] = _now_iso()
        try:
            _write_text_atomic(_projects_dir() / filename, json.dumps(doc, ensure_ascii=False))
            entry = {
                'id': stem,
                'name': display.upper(),
                'file': filename,
                'savedAt': doc['savedAt'],
                'createdAt': doc['savedAt'],
            }
            entries.insert(0, entry)
            _write_project_index(entries[:50])
        except OSError as exc:
            return self._send_json({'ok': False, 'error': f'Project save failed: {exc}'}, 500)
        self._send_json({'ok': True, 'project': _project_entry_meta(entry)})

    def _handle_projects_rename(self):
        raw = self._read_project_body()
        if raw is None:
            return
        try:
            body = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid JSON.'}, 400)
        if not isinstance(body, dict):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid.'}, 400)
        project_id = str(body.get('id') or '').strip()
        name = str(body.get('name') or '').strip()[:60]
        if not name:
            return self._send_json({'ok': False, 'error': 'Project name is required.'}, 400)
        entries = _read_project_index()
        entry = _find_project_entry(entries, project_id)
        file_name = str((entry or {}).get('file') or '')
        if entry is None or not PROJECT_FILE_RE.match(file_name):
            return self._send_json({'ok': False, 'error': 'Project not found.'}, 404)
        file_path = _projects_dir() / file_name
        doc = _read_json_path(file_path)
        if not isinstance(doc, dict):
            return self._send_json({'ok': False, 'error': 'Project file could not be read.'}, 500)
        doc['projectName'] = name
        doc['projectId'] = project_id
        try:
            _write_text_atomic(file_path, json.dumps(doc, ensure_ascii=False))
        except OSError as exc:
            return self._send_json({'ok': False, 'error': f'Project rename failed: {exc}'}, 500)
        entry = dict(entry)
        entry['id'] = project_id
        entry['name'] = name.upper()
        entries = [item for item in entries if _project_entry_id(item) != project_id]
        entries.insert(0, entry)
        _write_project_index(entries[:50])
        autosave_path = _project_autosave_path(project_id)
        autosave_doc = _read_json_path(autosave_path)
        if isinstance(autosave_doc, dict):
            autosave_doc['projectName'] = name
            autosave_doc['projectId'] = project_id
            try:
                _write_text_atomic(autosave_path, json.dumps(autosave_doc, ensure_ascii=False))
            except OSError:
                pass
        session = _read_session()
        if session and session.get('projectId') == project_id:
            session['name'] = entry['name']
            _write_text_atomic(_session_path(), json.dumps(session, ensure_ascii=False))
        self._send_json({'ok': True, 'project': _project_entry_meta(entry)})

    def _handle_projects_duplicate(self):
        raw = self._read_project_body()
        if raw is None:
            return
        try:
            body = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid JSON.'}, 400)
        if not isinstance(body, dict):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid.'}, 400)
        project_id = str(body.get('id') or '').strip()
        entries = _read_project_index()
        entry = _find_project_entry(entries, project_id)
        file_name = str((entry or {}).get('file') or '')
        if entry is None or not PROJECT_FILE_RE.match(file_name):
            return self._send_json({'ok': False, 'error': 'Project not found.'}, 404)
        doc = _read_json_path(_projects_dir() / file_name)
        if not isinstance(doc, dict):
            return self._send_json({'ok': False, 'error': 'Project file could not be read.'}, 500)
        base_name = str(entry.get('name') or 'PROJECT')
        taken = {str(item.get('name') or '').upper() for item in entries}
        display = f'{base_name} COPY'
        counter = 2
        while display.upper() in taken:
            display = f'{base_name} COPY {counter}'
            counter += 1
        stem = _unique_project_stem(display, entries)
        doc = dict(doc)
        doc['projectName'] = display
        doc['projectId'] = stem
        doc['savedAt'] = _now_iso()
        try:
            _write_text_atomic(_projects_dir() / f'{stem}.ccproj.json', json.dumps(doc, ensure_ascii=False))
            copy_entry = {
                'id': stem,
                'name': display.upper(),
                'file': f'{stem}.ccproj.json',
                'savedAt': doc['savedAt'],
                'createdAt': doc['savedAt'],
            }
            entries.insert(0, copy_entry)
            _write_project_index(entries[:50])
        except OSError as exc:
            return self._send_json({'ok': False, 'error': f'Project duplicate failed: {exc}'}, 500)
        self._send_json({'ok': True, 'project': _project_entry_meta(copy_entry)})

    def _handle_projects_delete(self):
        raw = self._read_project_body()
        if raw is None:
            return
        try:
            body = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid JSON.'}, 400)
        if not isinstance(body, dict):
            return self._send_json({'ok': False, 'error': 'Project payload is not valid.'}, 400)
        project_id = str(body.get('id') or '').strip()
        entries = _read_project_index()
        entry = _find_project_entry(entries, project_id)
        if entry is None:
            return self._send_json({'ok': False, 'error': 'Project not found.'}, 404)
        file_name = str(entry.get('file') or '')
        if PROJECT_FILE_RE.match(file_name):
            try:
                (_projects_dir() / file_name).unlink(missing_ok=True)
            except OSError as exc:
                return self._send_json({'ok': False, 'error': f'Project file could not be removed: {exc}'}, 500)
        try:
            _project_autosave_path(project_id).unlink(missing_ok=True)
        except OSError:
            pass
        entries = [item for item in entries if _project_entry_id(item) != project_id]
        _write_project_index(entries[:50])
        session = _read_session()
        if session and session.get('projectId') == project_id:
            try:
                _session_path().unlink(missing_ok=True)
            except OSError:
                pass
        self._send_json({'ok': True, 'deleted': project_id})

    def _handle_projects_open(self, query):
        project_id = str((query.get('id') or [''])[0]).strip()
        entry = _find_project_entry(_read_project_index(), project_id)
        file_name = str((entry or {}).get('file') or '')
        if entry is None or not PROJECT_FILE_RE.match(file_name):
            return self._send_json({'ok': False, 'error': 'Project not found.'}, 404)
        doc = _read_json_path(_projects_dir() / file_name)
        if doc is None:
            return self._send_json({'ok': False, 'error': 'Project file could not be read.'}, 500)
        self._send_json({'ok': True, 'project': doc, 'entry': _project_entry_meta(entry)})

    def _handle_projects_recover(self, query):
        project_id = str((query.get('id') or [''])[0]).strip()
        if project_id == 'legacy':
            doc = _read_json_path(_projects_dir() / PROJECT_AUTOSAVE_NAME)
            if not isinstance(doc, dict) or _validate_project_doc(doc):
                return self._send_json({'ok': False, 'error': 'No recoverable session was found.'}, 404)
            return self._send_json({'ok': True, 'project': doc, 'entry': None, 'legacy': True})
        entry = _find_project_entry(_read_project_index(), project_id)
        if entry is None:
            return self._send_json({'ok': False, 'error': 'Project not found.'}, 404)
        doc = _read_json_path(_project_autosave_path(project_id))
        if not isinstance(doc, dict) or _validate_project_doc(doc):
            return self._send_json({'ok': False, 'error': 'No recoverable autosave was found for this project.'}, 404)
        self._send_json({'ok': True, 'project': doc, 'entry': _project_entry_meta(entry), 'legacy': False})

    def _handle_agent_plan_post(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return self._send_json({'ok': False, 'error': 'Empty plan payload.'}, 400)
        if length > AGENT_PLAN_MAX_BYTES:
            return self._send_json({'ok': False, 'error': 'Plan payload is too large.'}, 413)
        try:
            body = json.loads(self.rfile.read(length).decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return self._send_json({'ok': False, 'error': 'Plan payload is not valid JSON.'}, 400)
        if not isinstance(body, dict):
            return self._send_json({'ok': False, 'error': 'Plan payload is not valid.'}, 400)
        session_id = str(body.get('sessionId') or '').strip()
        markdown = body.get('markdown')
        if not AGENT_PLAN_ID_RE.match(session_id):
            return self._send_json({'ok': False, 'error': 'Invalid plan session id.'}, 400)
        if not isinstance(markdown, str) or not markdown.strip():
            return self._send_json({'ok': False, 'error': 'Plan markdown is required.'}, 400)
        if len(markdown.encode('utf-8')) > AGENT_PLAN_MAX_BYTES:
            return self._send_json({'ok': False, 'error': 'Plan markdown is too large.'}, 413)
        try:
            path = _agent_plans_dir() / f'{session_id}.md'
            _write_text_atomic(path, markdown)
        except OSError as exc:
            return self._send_json({'ok': False, 'error': f'Plan save failed: {exc}'}, 500)
        self._send_json({'ok': True, 'bytes': len(markdown.encode('utf-8'))})

    def _handle_agent_plan_get(self, query):
        session_id = str((query.get('id') or [''])[0]).strip()
        if not AGENT_PLAN_ID_RE.match(session_id):
            return self._send_json({'ok': False, 'error': 'Invalid plan session id.'}, 400)
        try:
            markdown = (_agent_plans_dir() / f'{session_id}.md').read_text(encoding='utf-8')
        except OSError:
            return self._send_json({'ok': True, 'markdown': None})
        self._send_json({'ok': True, 'markdown': markdown})

    def _handle_media_upload(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return self._send_json({'ok': False, 'error': 'Empty media upload.'}, 400)
        if length > MEDIA_MAX_BYTES:
            return self._send_json({
                'ok': False,
                'error': f'File is too large (max {MEDIA_MAX_BYTES // (1024 * 1024)} MB).'
            }, 413)
        raw_name = urllib.parse.unquote(self.headers.get('X-File-Name') or '')
        display_name = Path(raw_name).stem.strip()[:60] or 'MEDIA'
        suffix = Path(raw_name).suffix.lower()
        if suffix not in MEDIA_TYPES:
            return self._send_json({
                'ok': False,
                'error': 'Unsupported media type. Use images, MP4/MOV/WebM/OGV video, or MP3/WAV/M4A/AAC/FLAC/OGG/Opus audio.'
            }, 400)
        kind, content_type = MEDIA_TYPES[suffix]
        media_dir = _media_dir()
        temp_path = media_dir / ('.upload-' + os.urandom(8).hex() + '.tmp')
        digest = hashlib.sha1()
        received = 0
        try:
            with temp_path.open('wb') as handle:
                while received < length:
                    chunk = self.rfile.read(min(1024 * 1024, length - received))
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
            if received != length:
                raise ValueError('Incomplete media upload.')
            filename = f"media-{digest.hexdigest()[:20]}{suffix}"
            final_path = media_dir / filename
            if final_path.exists():
                temp_path.unlink(missing_ok=True)
            else:
                os.replace(temp_path, final_path)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            return self._send_json({'ok': False, 'error': 'Media upload failed.'}, 500)
        self._send_json({
            'ok': True,
            'url': f'/media/{filename}',
            'kind': kind,
            'name': display_name,
            'bytes': received,
            'mime': content_type,
        })

    def _handle_media_analyze(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 65536:
            return self._send_json({'ok': False, 'error': 'Invalid analysis request.'}, 400)
        try:
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return self._send_json({'ok': False, 'error': 'Invalid JSON.'}, 400)
        url = str((payload or {}).get('url') or '')
        if not url.startswith('/media/'):
            return self._send_json({'ok': False, 'error': 'Only project media can be analyzed.'}, 400)
        filename = Path(urllib.parse.unquote(url[len('/media/'):])).name
        try:
            manifest = analyze_media_file(filename)
        except FileNotFoundError:
            return self._send_json({'ok': False, 'error': 'Media file not found.'}, 404)
        except ValueError:
            return self._send_json({'ok': False, 'error': 'Unknown media file.'}, 400)
        except Exception as exc:
            print(f"  [SERVER] analysis error: {exc}")
            return self._send_json({'ok': False, 'error': 'Media analysis failed.'}, 500)
        self._send_json({'ok': True, 'manifest': manifest})

    def _handle_analysis_frame(self, raw_name):
        name = urllib.parse.unquote(raw_name)
        match = re.match(r"^([^/]+)/(\d{1,2})\.jpg$", name)
        if not match or not MEDIA_NAME_RE.match(match.group(1)):
            return self._safe_text_error('Frame not found.', 404)
        frame_dir = _analysis_dir() / f"frames-{Path(match.group(1)).stem}"
        frame_path = frame_dir / f"shot-{int(match.group(2)):02d}.jpg"
        try:
            data = frame_path.read_bytes()
        except OSError:
            return self._safe_text_error('Frame not found.', 404)
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'private, max-age=3600')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _handle_semantic_providers(self):
        try:
            self._send_json({'ok': True, **semantic_provider_registry()})
        except Exception as exc:
            print(f"  [SERVER] semantic provider error: {exc}")
            self._send_json({'ok': False, 'error': 'Could not list content-analysis providers.'}, 500)

    def _handle_media_semantic(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 65536:
            return self._send_json({'ok': False, 'error': 'Invalid analysis request.'}, 400)
        try:
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return self._send_json({'ok': False, 'error': 'Invalid JSON.'}, 400)
        if not isinstance(payload, dict) or payload.get('consent') is not True:
            return self._send_json({
                'ok': False,
                'error': 'Explicit consent is required before uploading media to a hosted provider.'
            }, 403)
        provider = str(payload.get('provider') or 'gemini').strip().lower()
        if provider != 'gemini':
            return self._send_json({
                'ok': False,
                'error': 'Only the Gemini content-analysis provider is available.'
            }, 400)
        url = str(payload.get('url') or '')
        if not url.startswith('/media/'):
            return self._send_json({'ok': False, 'error': 'Only project media can be analyzed.'}, 400)
        filename = Path(urllib.parse.unquote(url[len('/media/'):])).name
        transcribe = payload.get('transcribe') is True
        try:
            manifest = semantic_media_file(filename, transcribe=transcribe)
        except PermissionError as exc:
            return self._send_json({'ok': False, 'error': str(exc)}, 403)
        except FileNotFoundError:
            return self._send_json({'ok': False, 'error': 'Media file not found.'}, 404)
        except ValueError as exc:
            return self._send_json({'ok': False, 'error': str(exc)}, 400)
        except RuntimeError as exc:
            return self._send_json({'ok': False, 'error': str(exc)[:500]}, 502)
        except Exception as exc:
            print(f"  [SERVER] content analysis error: {exc}")
            return self._send_json({'ok': False, 'error': 'Content analysis failed.'}, 500)
        self._send_json({'ok': True, 'provider': provider, 'manifest': manifest})

    def _handle_tts_providers(self):
        try:
            self._send_json({'ok': True, **tts_provider_registry()})
        except Exception as exc:
            print(f"  [SERVER] TTS provider error: {exc}")
            self._send_json({'ok': False, 'error': 'Could not list speech providers.'}, 500)

    def _handle_tts_generate(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 200000:
            return self._send_json({'ok': False, 'error': 'Invalid speech request.'}, 400)
        try:
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return self._send_json({'ok': False, 'error': 'Invalid JSON.'}, 400)
        if not isinstance(payload, dict):
            return self._send_json({'ok': False, 'error': 'Invalid speech request.'}, 400)
        try:
            result = synthesize_speech(payload)
        except ValueError as exc:
            return self._send_json({'ok': False, 'error': str(exc)}, 400)
        except PermissionError as exc:
            return self._send_json({'ok': False, 'error': str(exc)}, 403)
        except RuntimeError as exc:
            return self._send_json({'ok': False, 'error': str(exc)}, 502)
        except Exception as exc:
            print(f"  [SERVER] TTS error: {exc}")
            return self._send_json({'ok': False, 'error': 'Speech generation failed.'}, 500)
        self._send_json(result)

    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_text_error(self, message, status=500):
        data = message.encode('utf-8', errors='replace')
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _safe_text_error(self, message, status=500):
        try:
            self._send_text_error(message, status)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_runtime_config(self):
        api_base = os.environ.get("CLIPACANVAS_API_BASE", "").rstrip("/")
        payload = f"window.CLIPACANVAS_API_BASE = {json.dumps(api_base)};\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _cors_origin(self):
        request_origin = self.headers.get("Origin")
        if "*" in ALLOWED_ORIGINS:
            return "*"
        if request_origin and request_origin in ALLOWED_ORIGINS:
            return request_origin
        return None

    def _origin_forbidden(self):
        request_origin = self.headers.get("Origin")
        return bool(request_origin and "*" not in ALLOWED_ORIGINS and request_origin not in ALLOWED_ORIGINS)

    def _same_origin_request(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        try:
            parsed = urllib.parse.urlparse(origin)
        except ValueError:
            return False
        origin_host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1") and origin_host in ("localhost", "127.0.0.1"):
            return True
        return origin_host == host

    def log_message(self, fmt, *args):
        if "200 -" in fmt % args: return 
        print(f"  {self.address_string()} -> {fmt % args}")


def build_server(host: str = "0.0.0.0", port: int = 8000) -> ClipACanvasServer:
    return ClipACanvasServer((host, port), ClipACanvasHandler)


def server_url(server: ClipACanvasServer, public_host: str | None = None) -> str:
    bound_host, bound_port = server.server_address[:2]
    host = public_host or bound_host
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    return f"http://{host}:{bound_port}"


def start_server(host: str = "127.0.0.1", port: int = 0) -> tuple[ClipACanvasServer, threading.Thread]:
    server = build_server(host=host, port=port)
    thread = threading.Thread(target=server.serve_forever, name="clipacanvas-server", daemon=True)
    thread.start()
    return server, thread


def stop_server(server: ClipACanvasServer) -> None:
    server.shutdown()
    server.server_close()


def main() -> int:
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = build_server(host=host, port=port)
    url = server_url(server)
    
    print(f"\n  Clip.A.Canvas ENGINE ACTIVE (Backend FFmpeg Mode)")
    print(f"  ----------------------------------------------")
    print(f"  URL -> {url}")
    print(f"  Renders are streamed to the browser and discarded after response.")
    
    if os.environ.get("CLIPACANVAS_NO_BROWSER") != "1":
        webbrowser.open(url)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
