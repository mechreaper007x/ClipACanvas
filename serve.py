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
import queue
import uuid
import asyncio
import atexit
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
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
                "fps": {"type": "string", "description": "Frame rate: 24, 25, 30, 48, 50, 60, 90, 120, 144 or 240."},
                "duration": {"type": "number", "description": "Clip length in seconds, 0.5 or longer."},
                "format": {"type": "string", "enum": ["mp4", "webm", "mov", "gif"]},
                "bitrate": {"type": "string", "enum": ["1M", "2M", "5M", "10M", "20M"]},
            },
        },
    },
    {
        "name": "insert_animation_code",
        "description": "Write or replace the SELECTED code scene with a complete self-contained HTML document; the live preview refreshes immediately. When the scene already contains embedded media (an <img>/<video class=\"cc-scene-media\"> added with put_media_in_scene), the app keeps those elements automatically: if your HTML omits them they are inserted at the top of the body behind your content, so you can write the title or effect without copying the media tag. Include them yourself when you need precise placement. Compose titles, captions, effects or animation inside the same document; never create a separate overlay layer or scene for content that belongs to this scene. To intentionally remove the embedded media, pass removeMedia:true. Use this for the current scene only, never for additional scenes.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Complete single-file HTML document, no markdown fences."},
                "duration": {"type": "number", "description": "Optional scene length in seconds, 0.5 or longer, matching the animation; omit to keep the box length."},
                "removeMedia": {"type": "boolean", "description": "Set true only when the user explicitly asks to remove the scene's embedded images or videos; otherwise the new code must keep every existing cc-scene-media element."},
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
                "duration": {"type": "number", "description": "Scene length in seconds, 0.5 or longer. Match the animation length."},
                "layer": {"type": "string", "enum": ["same", "above"], "description": "same appends after the last scene on the selected scene's track; above creates an upper track only for a separate overlay scene above an imported video/image clip or when the user explicitly asks for an independent overlay scene. For content on a code scene (titles, captions, effects around its embedded media), rewrite that scene in place with insert_animation_code instead of adding a layer."},
                "start": {"type": "number", "description": "Optional exact start time in seconds; omit to append automatically."},
                "transition": {
                    "type": "object",
                    "description": "Optional transition on the cut this scene creates with the previous touching scene on the same track. Include it by default when the scene continues a sequence; the cut is resolved automatically.",
                    "properties": {
                        "type": {"type": "string", "description": "Preset id or \"custom\"."},
                        "duration": {"type": "number", "description": "Length in seconds, 0.1 to 3."},
                        "alignment": {"type": "string", "enum": ["center", "start", "end"]},
                        "direction": {"type": "string", "enum": ["left", "right", "up", "down"]},
                        "color": {"type": "string"},
                        "intensity": {"type": "number"},
                        "code": {"type": "string", "description": "Custom renderTransition(ctx) source when type is custom."},
                    },
                    "required": ["type"],
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "put_media_in_scene",
        "description": "Put a project bin image or video INSIDE a code scene's own HTML (for example Scene 01 or Scene 02). Use this when the user asks to add a clip into a scene; it does not create a new timeline layer. An empty scene adopts the media as its full-frame content; in a scene that already has content the media is added as a positioned element (use x/y to place it). Pass sceneId from get_app_state, or omit it to use the selected scene. For an imported video clip (which has no HTML of its own) use create_overlay with parentClipId instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "assetId": {"type": "string", "description": "Project bin asset id from search_assets or get_app_state."},
                "sceneId": {"type": "string", "description": "Target code scene clip id; defaults to the selected scene."},
                "x": {"type": "number", "description": "Optional horizontal center in percent, 4-96, for a positioned element in a non-empty scene."},
                "y": {"type": "number", "description": "Optional vertical center in percent, 4-96, for a positioned element in a non-empty scene."},
            },
            "required": ["assetId"],
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
        "name": "search_footage",
        "description": "Find the best matching moments in the project's footage by meaning using the local EmbeddingGemma 2 frame index. No image or video is uploaded. Returns the asset id, asset name, timestamp in the source file, similarity score and a thumbnail for each match. Use this to find B-roll for narration or to answer what footage shows before placing media; never ask to upload a video.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What the shot should show, e.g. 'wing above clouds at sunset'."},
                "limit": {"type": "integer", "description": "Maximum moments to return, 1-20. Defaults to 8."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_asset_analysis",
        "description": "Read one asset's cached analysis manifest: technical metadata, the locally detected shot list (with keyframe URLs), the local visual index (EmbeddingGemma 2 zero-shot tags with scores, per-indexed-frame tags and thumbnails, motion score and label — images and videos), semantic status, AI description and user notes. The visual index is computed on this machine without consent; use its tags and motion to describe the footage honestly and to write overlays that fit it. For content questions use search_footage. Semantic analysis only exists after the user ran it with explicit consent; when it is 'not_analyzed', never invent visual or audio content that is not in the manifest.",
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
        "description": "Create an independent HTML overlay clip above existing footage on the timeline. The page must have a fully transparent background so the footage below stays visible. Optionally attach it to a parent clip. The overlay stays separately selectable and editable; this is not motion tracking. Use this to put a bin asset inside an imported VIDEO clip (picture-in-picture) by writing a transparent overlay containing a <video>/<img> whose src is the asset url from search_assets, matching the parent clip's start and duration and passing parentClipId. For a code scene, do NOT use an overlay: put the media element inside that scene's HTML instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Complete single-file HTML document with a transparent page background, no markdown fences."},
                "name": {"type": "string", "description": "Short overlay name, up to 24 characters."},
                "duration": {"type": "number", "description": "Overlay length in seconds, 0.5 or longer. Defaults to the parent clip length."},
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
                "duration": {"type": "number", "description": "New length in seconds, 0.5 or longer."},
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
        "description": "Add or update a saved visual transition on an existing cut where two clips touch on the same track. Presets: dissolve, fade-black, fade-white, dip-color, wipe, push, slide, zoom-in, zoom-out, zoom-blur, glitch, rgb-split, blur-dissolve. Defaults to the touching cut of the selected clip. Set all:true to apply the same transition at every touching cut in one call. For a custom transition use type \"custom\" and provide code declaring function renderTransition(ctx) that returns {outgoing, incoming, overlay} style objects for ctx.progress 0→1 (opacity, transform, filter, clipPath, backgroundColor, mixBlendMode). Custom code is validated and runs only inside the isolated preview/export page. Clips without extra source footage still work: the transition holds the outgoing last frame and the incoming first frame.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Preset id or \"custom\"."},
                "all": {"type": "boolean", "description": "Apply or update this transition at every touching cut across all video tracks. Use it once after building a multi-scene sequence."},
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
        "description": "Change a saved transition's type, duration, alignment, parameters or custom code. Defaults to the transition on the selected clip's cut when transitionId is omitted.",
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
        "name": "generate_voiceover",
        "description": "Generate narration with the speech provider and place the audio on a timeline lane: A1 voiceover (default), A2 music, A3 sound effects. Installed local neural voices (StyleTTS2, Kokoro, Piper, ZONOS3-Mini) need no key and are preferred; ZONOS3-Mini adds 27 narrators and 43 languages; Windows Speech is the offline fallback; hosted providers require configured keys. The audio also lands in the media bin. Set captions true to add timed subtitle overlays for the same text. Returns the clip, duration, lane and caption count.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Narration script, up to 4000 characters."},
                "provider": {"type": "string", "enum": ["styletts2", "kokoro", "piper", "zonos", "sapi", "gemini", "mistral"], "description": "Optional speech provider; defaults to the best installed local neural voice. If the requested gender is unavailable on it, the app moves to a provider that has one."},
                "voice": {"type": "string", "description": "Optional voice id or voice name from the Available speech voices system message (for example am_michael, Madhur, libritts-4077, Savannah, Microsoft David Desktop). The provider is inferred when it is unambiguous."},
                "gender": {"type": "string", "enum": ["male", "female", "neutral"], "description": "Preferred narrator gender. Use it when the script or the user calls for a male or female voice instead of naming a specific voice."},
                "model": {"type": "string", "description": "Optional speech model id."},
                "speed": {"type": "number", "description": "Speaking rate 0.5 to 2 for providers that support it."},
                "style": {"type": "string", "description": "Speaking style for providers that support it."},
                "lane": {"type": "string", "enum": ["A1", "A2", "A3"], "description": "Audio lane; defaults to A1 voiceover."},
                "start": {"type": "number", "description": "Timeline start in seconds; defaults to the playhead."},
                "name": {"type": "string", "description": "Clip name shown on the timeline."},
                "captions": {"type": "boolean", "description": "Also create timed caption overlays for this narration."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "add_captions",
        "description": "Add timed subtitle overlay clips on a free track above the scenes. Each cue is a transparent, safe-margin caption clip, so captions render in both the monitor and the export. Pass an audio clipId to match an existing voiceover's span, or start plus duration.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Caption text; sentences become cues."},
                "start": {"type": "number", "description": "Start in seconds; defaults to the clip or the playhead."},
                "duration": {"type": "number", "description": "Span in seconds; defaults to the clip's duration."},
                "clipId": {"type": "string", "description": "Optional audio clip whose timing the captions follow."},
                "maxChars": {"type": "number", "description": "Characters per cue, 40 to 160 (default 90)."},
                "name": {"type": "string", "description": "Name prefix for the caption clips."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "place_media",
        "description": "Place an existing bin asset on the timeline. Images and videos go on a video track (V1 to V4 via track 0 to 3); audio goes on an audio lane A1, A2 or A3. Identify the asset by assetId or a search query that matches exactly one asset. Media comes from the bin only; import files first.",
        "parameters": {
            "type": "object",
            "properties": {
                "assetId": {"type": "string", "description": "Bin asset id from get_app_state or search_assets."},
                "query": {"type": "string", "description": "Name or description search when assetId is unknown."},
                "track": {"type": "number", "description": "Video track index 0 to 3; ignored for audio."},
                "lane": {"type": "string", "enum": ["A1", "A2", "A3"], "description": "Audio lane for audio assets; defaults to A2."},
                "at": {"type": "number", "description": "Start in seconds; defaults to the playhead."},
            },
        },
    },
    {
        "name": "verify_timeline",
        "description": "Check the timeline for structural problems before rendering: empty scene code, clips shorter than 0.5s, same-track overlaps, audio clips outside A1-A3, missing media assets and transitions that point at deleted clips. Returns passed plus a problem list.",
        "parameters": {
            "type": "object",
            "properties": {},
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


def _retry_delay_seconds(detail: str, headers=None) -> int:
    if headers is not None:
        value = headers.get('Retry-After') or headers.get('retry-after')
        if value:
            try:
                return max(1, int(float(value)))
            except (TypeError, ValueError):
                pass
    patterns = (
        r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"',
        r'"retry_after"\s*:\s*"?(\d+(?:\.\d+)?)',
        r'retry\s+after\s+(\d+(?:\.\d+)?)',
    )
    for pattern in patterns:
        match = re.search(pattern, detail or '', re.IGNORECASE)
        if not match:
            continue
        try:
            return max(1, int(float(match.group(1)) + 0.5))
        except ValueError:
            continue
    return 0


def _rate_limit_message(provider: str, model: str, retry_seconds: int, tried_fallback: bool) -> str:
    label = str(model or '').replace('models/', '')
    if tried_fallback:
        head = f'{provider.capitalize()} is out of free-tier quota for every model it tried (429).'
        tail = ', or switch to another provider.'
    else:
        head = f'{provider.capitalize()} is out of free-tier quota for {label} (429).'
        tail = ', pick another model, or switch providers.'
    body = ' Free-tier keys allow only a small number of requests per model per minute/day, and tool calls use extra requests.'
    if retry_seconds:
        body += f' Retry in about {_human_duration(retry_seconds)}'
    else:
        body += ' Retry in about a minute'
    return head + body + tail


_MODEL_COOLDOWNS: dict = {}


def _model_cooldowns_path() -> Path:
    return _keys_dir() / "llm-quota.json"


def _load_model_cooldowns() -> None:
    try:
        raw = json.loads(_model_cooldowns_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(raw, dict):
        return
    now = time.time()
    for key, until in raw.items():
        if not isinstance(key, str) or not isinstance(until, (int, float)):
            continue
        provider, _, model = key.partition(":")
        if provider not in ("gemini", "mistral") or not model or until <= now:
            continue
        _MODEL_COOLDOWNS[(provider, model)] = float(until)


def _save_model_cooldowns() -> None:
    try:
        now = time.time()
        raw = {
            f"{provider}:{model}": int(until)
            for (provider, model), until in _MODEL_COOLDOWNS.items()
            if until > now
        }
        path = _model_cooldowns_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw), encoding="utf-8")
    except OSError:
        pass


def _set_model_cooldown(provider: str, model: str, seconds: int) -> None:
    if seconds > 0:
        _MODEL_COOLDOWNS[(provider, model)] = time.time() + seconds
        _save_model_cooldowns()


def _model_cooldown_remaining(provider: str, model: str) -> int:
    until = _MODEL_COOLDOWNS.get((provider, model), 0)
    return max(0, int(until - time.time()))


_LLM_USAGE_LOCK = threading.Lock()


class _LLMQuotaError(RuntimeError):
    """The selected model has no free-tier capacity left in the active window."""


def _llm_usage_path() -> Path:
    return _keys_dir() / "llm-usage.json"


def _usage_today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _load_llm_usage() -> dict:
    try:
        raw = json.loads(_llm_usage_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_llm_usage(data: dict) -> None:
    try:
        path = _llm_usage_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _usage_model_bucket(provider_bucket: dict, model: str) -> dict:
    models = provider_bucket.setdefault("models", {})
    return models.setdefault(model or "unknown", {
        "calls": 0, "ok": 0, "promptTokens": 0, "completionTokens": 0, "limit": 0
    })


def _record_llm_usage(provider: str, model: str, purpose: str, usage=None, status: int = 200,
                      limit: int = 0, quota=None, rate=None, estimated: int = 0) -> None:
    usage = usage if isinstance(usage, dict) else {}
    quota = quota if isinstance(quota, dict) else {}
    rate = rate if isinstance(rate, dict) else {}
    prompt = max(0, int(usage.get("prompt") or 0))
    completion = max(0, int(usage.get("completion") or 0))
    service_tier = str(usage.get("serviceTier") or usage.get("service_tier") or "")
    ok = 200 <= int(status) < 300
    purpose = (str(purpose or "chat").strip()[:24] or "chat")
    if ok:
        _record_minute_event(provider, model, prompt + completion)
    if rate:
        _record_rate_limits(provider, model, rate)
    with _LLM_USAGE_LOCK:
        data = _load_llm_usage()
        day = _usage_today()
        provider_bucket = data.setdefault(day, {}).setdefault(provider, {
            "calls": 0, "ok": 0, "promptTokens": 0, "completionTokens": 0,
            "purposes": {}, "models": {}
        })
        provider_bucket["calls"] = int(provider_bucket.get("calls") or 0) + 1
        if ok:
            provider_bucket["ok"] = int(provider_bucket.get("ok") or 0) + 1
        provider_bucket["promptTokens"] = int(provider_bucket.get("promptTokens") or 0) + prompt
        provider_bucket["completionTokens"] = int(provider_bucket.get("completionTokens") or 0) + completion
        purposes = provider_bucket.setdefault("purposes", {})
        purposes[purpose] = int(purposes.get(purpose) or 0) + 1
        provider_bucket["lastModel"] = str(model or "")
        provider_bucket["lastAt"] = int(time.time())
        provider_bucket["lastStatus"] = int(status)
        provider_bucket["lastPromptTokens"] = prompt
        provider_bucket["lastCompletionTokens"] = completion
        provider_bucket["lastEstimatedTokens"] = int(estimated or 0)
        if service_tier:
            provider_bucket["serviceTier"] = service_tier
        if rate:
            provider_bucket["rateLimit"] = dict(rate)
        model_bucket = _usage_model_bucket(provider_bucket, str(model or ""))
        model_bucket["calls"] = int(model_bucket.get("calls") or 0) + 1
        if ok:
            model_bucket["ok"] = int(model_bucket.get("ok") or 0) + 1
        model_bucket["promptTokens"] = int(model_bucket.get("promptTokens") or 0) + prompt
        model_bucket["completionTokens"] = int(model_bucket.get("completionTokens") or 0) + completion
        model_bucket["lastPromptTokens"] = prompt
        model_bucket["lastCompletionTokens"] = completion
        model_bucket["lastAt"] = int(time.time())
        model_bucket["lastStatus"] = int(status)
        model_bucket["lastEstimatedTokens"] = int(estimated or 0)
        if service_tier:
            model_bucket["serviceTier"] = service_tier
        if rate:
            model_bucket["rateLimit"] = dict(rate)
        quota_limit = int(quota.get("limit") or limit or 0)
        if quota_limit > 0:
            model_bucket["limit"] = max(int(model_bucket.get("limit") or 0), quota_limit)
            if quota.get("window"):
                model_bucket["limitWindow"] = str(quota.get("window"))[:8]
            if quota.get("quotaId"):
                model_bucket["limitId"] = str(quota.get("quotaId"))[:120]
            if quota.get("type"):
                model_bucket["limitType"] = str(quota.get("type"))[:12]
        for old in sorted(data)[:-14]:
            data.pop(old, None)
        _save_llm_usage(data)


def _llm_usage_today() -> dict:
    with _LLM_USAGE_LOCK:
        return _load_llm_usage().get(_usage_today(), {})


def _quota_details_from_error(detail: str) -> dict:
    """Gemini 429 bodies carry QuotaFailure violations and RetryInfo."""
    try:
        payload = json.loads(detail or "{}")
    except json.JSONDecodeError:
        return {}
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return {}
    retry_seconds = _retry_delay_seconds(detail)
    found = []
    for item in error.get("details") or []:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("@type") or "")
        if not kind.endswith("QuotaFailure"):
            continue
        for violation in item.get("violations") or []:
            if not isinstance(violation, dict):
                continue
            quota_id = str(violation.get("quotaId") or "")
            quota_metric = str(violation.get("quotaMetric") or "")
            try:
                limit = int(float(violation.get("quotaValue") or 0))
            except (TypeError, ValueError):
                limit = 0
            lowered = (quota_id + " " + quota_metric).lower()
            if "perday" in lowered:
                window = "day"
            elif "perminute" in lowered:
                window = "minute"
            elif "persecond" in lowered:
                window = "second"
            else:
                window = ""
            found.append({
                "limit": limit,
                "quotaId": quota_id,
                "quotaMetric": quota_metric,
                "window": window,
                "type": "tokens" if "token" in lowered else "requests",
                "retrySeconds": retry_seconds,
            })
    if not found:
        return {"retrySeconds": retry_seconds} if retry_seconds else {}
    for candidate in found:
        if candidate.get("window") == "day":
            return candidate
    return found[0]


def _gemini_quota_limit(detail: str) -> int:
    return int(_quota_details_from_error(detail).get("limit") or 0)


_MODEL_RATE_STATE: dict = {}
_MODEL_CATALOG: dict = {}
_MODEL_CATALOG_TTL = 300


def _rate_limits_from_headers(headers) -> dict:
    out = {}
    if headers is None:
        return out
    try:
        items = list(headers.items())
    except AttributeError:
        return out
    for key, value in items:
        lowered = str(key).lower()
        if not lowered.startswith("x-ratelimit-"):
            continue
        try:
            out[lowered] = int(float(value))
        except (TypeError, ValueError):
            out[lowered] = str(value)
    if out:
        out["updatedAt"] = int(time.time())
    return out


def _record_rate_limits(provider: str, model: str, rate: dict) -> dict:
    if not isinstance(rate, dict) or not rate:
        return {}
    previous = _MODEL_RATE_STATE.get((provider, model), {})
    merged = dict(previous)
    for key, value in rate.items():
        # A 429 body often reports limit 0; keep the last real limit.
        if key == "x-ratelimit-limit-req-minute" and value == 0 and int(previous.get(key) or 0) > 0:
            continue
        merged[key] = value
    _MODEL_RATE_STATE[(provider, model)] = merged
    return merged


def _model_rate_state(provider: str, model: str) -> dict:
    return dict(_MODEL_RATE_STATE.get((provider, model), {}))


def _rate_remaining(provider: str, model: str) -> int:
    state = _MODEL_RATE_STATE.get((provider, model), {})
    updated = int(state.get("updatedAt") or 0)
    if not updated or time.time() - updated > 70:
        return -1
    try:
        return int(state.get("x-ratelimit-remaining-req-minute") or 0)
    except (TypeError, ValueError):
        return -1


def _estimate_prompt_tokens(messages, tools: bool = False) -> int:
    try:
        raw = json.dumps(messages, ensure_ascii=False)
    except (TypeError, ValueError):
        raw = str(messages)
    return max(1, int(len(raw) / 3.2)) + (2000 if tools else 0)


def _model_input_limit(models, name: str) -> int:
    for model in models or []:
        if str(model.get('name') or '') == name:
            try:
                return int(model.get('inputTokenLimit') or 0)
            except (TypeError, ValueError):
                return 0
    return 0


# AI Studio > Rate limits (free tier, standard service tier), observed on the
# user's key on 2026-11-15. Gemini exposes these only in the AI Studio UI:
# models.list has context/output limits, success responses carry no quota
# headers, and a 429 only reports the single exhausted metric. Values are
# overridden per model/timeframe by any 429 QuotaFailure the API returns.
FREE_TIER_LIMITS_VERIFIED = "2026-11-15"
_FREE_TIER_LIMITS = {
    "gemini-2.5-flash": {"rpm": 5, "tpm": 250000, "rpd": 20},
    "gemini-2.5-flash-lite": {"rpm": 10, "tpm": 250000, "rpd": 20},
    "gemini-3-flash-preview": {"rpm": 5, "tpm": 250000, "rpd": 20},
    "gemini-3.1-flash-lite": {"rpm": 15, "tpm": 250000, "rpd": 500},
    "gemini-3.1-flash-lite-preview": {"rpm": 15, "tpm": 250000, "rpd": 500},
    "gemini-3.5-flash-lite": {"rpm": 15, "tpm": 250000, "rpd": 500},
    "gemini-3.6-flash": {"rpm": 5, "tpm": 250000, "rpd": 20},
    "gemini-3.8-flash": {"rpm": 5, "tpm": 250000, "rpd": 20},
    "gemini-4-hydrogen": {"rpm": 5, "tpm": 250000, "rpd": 20},
    "gemini-4-argon": {"rpm": 0, "tpm": 0, "rpd": 0},
    "gemini-4-carbon": {"rpm": 0, "tpm": 0, "rpd": 0},
    "gemini-2.5-pro": {"rpm": 0, "tpm": 0, "rpd": 0},
    "gemini-3.1-pro-preview": {"rpm": 0, "tpm": 0, "rpd": 0},
    "gemini-pro-latest": {"rpm": 0, "tpm": 0, "rpd": 0},
    "gemma-4-26b-it": {"rpm": 30, "tpm": 16000, "rpd": 14400},
    "gemma-4-26b-a4b-it": {"rpm": 30, "tpm": 16000, "rpd": 14400},
    "gemma-4-31b-it": {"rpm": 30, "tpm": 16000, "rpd": 14400},
    "gemini-robotics-er-2-preview": {"rpm": 5, "tpm": 250000, "rpd": 20},
}

_MODEL_MINUTE_EVENTS: dict = {}
_MINUTE_WINDOW = 60


def _normalize_model_name(name: str) -> str:
    return str(name or '').strip().split('/')[-1].lower()


def _model_tier(provider: str, model: str) -> str:
    name = _normalize_model_name(model)
    if provider == 'gemini':
        if 'flash-lite' in name or name.startswith('gemma'):
            return 'lite'
        if 'pro' in name and 'flash' not in name:
            return 'pro'
        if 'flash' in name:
            return 'flash'
        return 'other'
    if 'large' in name:
        return 'pro'
    if 'small' in name or 'ministral' in name:
        return 'lite'
    if 'medium' in name or 'codestral' in name or 'code' in name:
        return 'flash'
    return 'other'


def _free_tier_limits(provider: str, model: str):
    if provider != 'gemini':
        return None
    entry = _FREE_TIER_LIMITS.get(_normalize_model_name(model))
    return dict(entry) if entry else None


def _record_minute_event(provider: str, model: str, tokens) -> None:
    key = (provider, _normalize_model_name(model))
    now = time.time()
    events = [item for item in _MODEL_MINUTE_EVENTS.get(key, []) if now - item[0] < _MINUTE_WINDOW]
    events.append((now, max(0, int(tokens or 0))))
    _MODEL_MINUTE_EVENTS[key] = events


def _minute_usage(provider: str, model: str):
    key = (provider, _normalize_model_name(model))
    now = time.time()
    events = [item for item in _MODEL_MINUTE_EVENTS.get(key, []) if now - item[0] < _MINUTE_WINDOW]
    _MODEL_MINUTE_EVENTS[key] = events
    return len(events), sum(item[1] for item in events)


def _minute_wait_seconds(provider: str, model: str) -> int:
    key = (provider, _normalize_model_name(model))
    events = _MODEL_MINUTE_EVENTS.get(key, [])
    if not events:
        return 0
    oldest = min(item[0] for item in events)
    return max(1, int(oldest + _MINUTE_WINDOW - time.time()))


def _model_headroom(provider: str, model: str, bucket=None):
    """Remaining free-tier RPM/TPM/RPD for a model, or None when unknown."""
    bucket = bucket if isinstance(bucket, dict) else {}
    limits = None
    source = ''
    if provider == 'gemini':
        table = _free_tier_limits(provider, model)
        if table:
            limits = dict(table)
            source = 'free-table'
    rate = _model_rate_state(provider, model) or bucket.get('rateLimit') or {}
    if provider == 'mistral' and rate:
        # Headers describe a one-minute window; stale values mean "unknown",
        # not "still exhausted".
        if time.time() - int(rate.get('updatedAt') or 0) > 70:
            rate = {}
        else:
            limits = {
                'rpm': int(rate.get('x-ratelimit-limit-req-minute') or 0) or None,
                'tpm': int(rate.get('x-ratelimit-limit-tokens-minute') or 0) or None,
                'rpd': None,
            }
            source = 'headers'
    quota_limit = int(bucket.get('limit') or 0)
    if quota_limit > 0:
        window = str(bucket.get('limitWindow') or 'day')
        quota_type = str(bucket.get('limitType') or 'requests')
        if not limits:
            limits = {'rpm': None, 'tpm': None, 'rpd': None}
        if window == 'day':
            if quota_type == 'tokens':
                limits['tpd'] = quota_limit
            else:
                limits['rpd'] = quota_limit
            if source == 'free-table':
                source = 'free-table+429'
            elif source == 'headers':
                source = 'headers+429'
            else:
                source = '429'
        elif window == 'minute':
            if quota_type == 'tokens':
                limits['tpm'] = quota_limit
            else:
                limits['rpm'] = quota_limit
            if source == 'headers':
                source = 'headers+429'
            else:
                source = '429'
    if not limits:
        return None
    remaining = {}
    if provider == 'gemini':
        minute_calls, minute_tokens = _minute_usage(provider, model)
        if limits.get('rpm') is not None:
            remaining['rpm'] = max(0, limits['rpm'] - minute_calls)
        if limits.get('tpm') is not None:
            remaining['tpm'] = max(0, limits['tpm'] - minute_tokens)
        if limits.get('rpd') is not None:
            remaining['rpd'] = max(0, limits['rpd'] - int(bucket.get('ok') or 0))
    else:
        try:
            if 'x-ratelimit-remaining-req-minute' in rate:
                remaining['rpm'] = max(0, int(rate.get('x-ratelimit-remaining-req-minute') or 0))
            if 'x-ratelimit-remaining-tokens-minute' in rate:
                remaining['tpm'] = max(0, int(rate.get('x-ratelimit-remaining-tokens-minute') or 0))
        except (TypeError, ValueError):
            pass
    return {
        'limits': limits,
        'remaining': remaining,
        'source': source,
        'verifiedAt': FREE_TIER_LIMITS_VERIFIED if source.startswith('free') else '',
    }


def _headroom_blocked(provider: str, model: str, bucket=None) -> bool:
    info = _model_headroom(provider, model, bucket)
    if not info:
        return False
    remaining = info.get('remaining') or {}
    limits = info.get('limits') or {}
    for key in ('rpd', 'rpm', 'tpm'):
        if limits.get(key) is not None and remaining.get(key) == 0:
            return True
    return False


def _model_fits_tokens(provider: str, model: str, bucket, estimated: int) -> bool:
    info = _model_headroom(provider, model, bucket)
    if not info:
        return True
    estimated = max(0, int(estimated or 0))
    tpm = info.get('limits', {}).get('tpm')
    if tpm and estimated > int(tpm):
        return False
    remaining_tpm = (info.get('remaining') or {}).get('tpm')
    if remaining_tpm is not None and estimated > int(remaining_tpm):
        return False
    return True


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
PROJECT_MAX_BYTES = 64 * 1024 * 1024


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


def _project_name_taken(entries: list[dict], name: str, exclude_id: str = "") -> bool:
    target = name.strip().upper()
    return any(
        _project_entry_id(entry) != exclude_id
        and str(entry.get("name") or "").strip().upper() == target
        for entry in entries
    )


def _unique_project_display(display: str, entries: list[dict], exclude_id: str = "") -> str:
    base = display.strip()[:60] or "PROJECT"
    taken = {
        str(entry.get("name") or "").strip().upper()
        for entry in entries
        if _project_entry_id(entry) != exclude_id
    }
    if base.upper() not in taken:
        return base
    counter = 2
    while f"{base} {counter}".upper() in taken:
        counter += 1
    return f"{base} {counter}"


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


ANALYSIS_VERSION = 6
SEMANTIC_SHOT_SCAN_SECONDS = 180
SEMANTIC_SHOT_LIMIT = 24
SEMANTIC_KEYFRAME_LIMIT = 12
VISUAL_MODEL = "google/embeddinggemma-2"
VISUAL_RUNTIME = "litert"
VISUAL_DEVICE_DEFAULT = "auto"
VISUAL_FRAME_FPS = 1.0
VISUAL_FRAME_LIMIT = 24
VISUAL_SEARCH_LIMIT = 12
VISUAL_SEARCH_MIN_SCORE = 0.2
VISUAL_TAGS_PER_FRAME = 4
VISUAL_TAG_LIMIT = 6
VISUAL_TAG_THRESHOLD = 0.55
VISUAL_TAG_MARGIN = 0.045
VISUAL_MODEL_FILE = "embeddinggemma-2-740m.litertlm"
VISUAL_LABELS = [
    "person", "people", "crowd", "woman", "man", "child", "hands", "face", "interview",
    "car", "truck", "bus", "motorcycle", "bicycle", "train", "airplane", "boat",
    "road", "street", "city", "building", "house", "bridge", "tunnel", "stairs",
    "sky", "clouds", "sun", "sunset", "sunrise", "night", "lights", "neon",
    "ocean", "sea", "beach", "waves", "river", "lake", "waterfall", "rain", "snow", "fog",
    "mountain", "forest", "tree", "grass", "field", "flowers", "garden", "desert",
    "animal", "dog", "cat", "bird", "horse", "cow", "fish",
    "food", "coffee", "table", "chair", "kitchen", "office", "room", "window", "door",
    "computer", "phone", "screen", "text", "logo", "chart", "map", "money",
    "factory", "construction", "machine", "robot", "fire", "smoke", "explosion",
    "music", "concert", "stage", "microphone", "dance", "sport", "football", "cricket",
    "shopping", "travel", "aerial view", "close-up", "hand-drawn", "animation", "cartoon",
]
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
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
    ("Zephyr", "female"), ("Puck", "male"), ("Charon", "male"), ("Kore", "female"),
    ("Fenrir", "male"), ("Leda", "female"), ("Orus", "male"), ("Aoede", "female"),
    ("Callirrhoe", "female"), ("Autonoe", "female"), ("Enceladus", "male"), ("Iapetus", "male"),
    ("Umbriel", "male"), ("Algieba", "male"), ("Despina", "female"), ("Erinome", "female"),
    ("Algenib", "male"), ("Rasalgethi", "male"), ("Laomedeia", "female"), ("Achernar", "female"),
    ("Alnilam", "male"), ("Schedar", "male"), ("Gacrux", "female"), ("Pulcherrima", "female"),
    ("Achird", "male"), ("Zubenelgenubi", "male"), ("Vindemiatrix", "female"), ("Sadachbia", "male"),
    ("Sadaltager", "male"), ("Sulafat", "female"),
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
    ("gb_jane_neutral", "Jane", "en-GB", "female"),
    ("gb_oliver_neutral", "Oliver", "en-GB", "male"),
    ("en_paul_neutral", "Paul", "en-US", "male"),
    ("en_paul_sad", "Paul (sad)", "en-US", "male"),
    ("fr_marie_neutral", "Marie", "fr-FR", "female"),
]
_SAPI_VOICE_CACHE = {"at": 0.0, "voices": [], "error": ""}
_SAPI_VOICE_LOCK = threading.Lock()

# Optional local neural engines installed beside the app. The packaged build
# never bundles torch; the backend drives separate runtime interpreters through
# persistent worker processes.
STYLETTS2_MODEL = {"id": "libritts", "label": "StyleTTS2 LibriTTS"}
# StyleTTS2 clones a narrator from a short reference clip. The bundled LibriTTS
# references add three female and four male voices; `default` keeps the
# original LJSpeech target.
STYLETTS2_VOICES = [
    {"id": "default", "label": "LJSpeech · female", "language": "en-US", "gender": "female"},
    {"id": "libritts-1221", "label": "LibriTTS 1221 · female", "language": "en-US", "gender": "female"},
    {"id": "libritts-3", "label": "LibriTTS 3 · female", "language": "en-US", "gender": "female"},
    {"id": "libritts-4", "label": "LibriTTS 4 · female", "language": "en-US", "gender": "female"},
    {"id": "libritts-4077", "label": "LibriTTS 4077 · male", "language": "en-US", "gender": "male"},
    {"id": "libritts-5", "label": "LibriTTS 5 · male", "language": "en-US", "gender": "male"},
    {"id": "libritts-5639", "label": "LibriTTS 5639 · male", "language": "en-US", "gender": "male"},
    {"id": "libritts-908", "label": "LibriTTS 908 · male", "language": "en-US", "gender": "male"},
]
STYLETTS2_VOICE_REFS = {
    "libritts-1221": "1221-135767-0014.wav",
    "libritts-3": "3.wav",
    "libritts-4": "4.wav",
    "libritts-4077": "4077-13754-0000.wav",
    "libritts-5": "5.wav",
    "libritts-5639": "5639-40744-0020.wav",
    "libritts-908": "908-157963-0027.wav",
}
STYLETTS2_ASSET_FILES = ("epoch_00080.pth", "bst.t7", "step_1000000.t7", "asr-config.yml", "plbert-config.yml")
KOKORO_MODEL = {"id": "kokoro-82m", "label": "Kokoro 82M"}
# Curated Kokoro-82M English and Hindi voices. Voice packs download on first
# use from the model repository, so the list is wider than the warm cache.
KOKORO_VOICES = [
    {"id": "af_heart", "label": "Heart · female", "language": "en-US", "gender": "female"},
    {"id": "af_bella", "label": "Bella · female", "language": "en-US", "gender": "female"},
    {"id": "af_sarah", "label": "Sarah · female", "language": "en-US", "gender": "female"},
    {"id": "af_nicole", "label": "Nicole · female", "language": "en-US", "gender": "female"},
    {"id": "af_nova", "label": "Nova · female", "language": "en-US", "gender": "female"},
    {"id": "af_sky", "label": "Sky · female", "language": "en-US", "gender": "female"},
    {"id": "am_michael", "label": "Michael · male", "language": "en-US", "gender": "male"},
    {"id": "am_adam", "label": "Adam · male", "language": "en-US", "gender": "male"},
    {"id": "am_eric", "label": "Eric · male", "language": "en-US", "gender": "male"},
    {"id": "am_fenrir", "label": "Fenrir · male", "language": "en-US", "gender": "male"},
    {"id": "am_liam", "label": "Liam · male", "language": "en-US", "gender": "male"},
    {"id": "am_onyx", "label": "Onyx · male", "language": "en-US", "gender": "male"},
    {"id": "am_puck", "label": "Puck · male", "language": "en-US", "gender": "male"},
    {"id": "bf_emma", "label": "Emma · female", "language": "en-GB", "gender": "female"},
    {"id": "bf_isabella", "label": "Isabella · female", "language": "en-GB", "gender": "female"},
    {"id": "bm_daniel", "label": "Daniel · male", "language": "en-GB", "gender": "male"},
    {"id": "bm_george", "label": "George · male", "language": "en-GB", "gender": "male"},
    {"id": "hf_alpha", "label": "Alpha · female", "language": "hi-IN", "gender": "female"},
    {"id": "hm_omega", "label": "Omega · male", "language": "hi-IN", "gender": "male"},
]
PIPER_MODEL = {"id": "medium", "label": "Piper medium"}
# Only voices whose .onnx file is installed are listed by the registry.
PIPER_VOICES = [
    ("en_US-lessac-medium", "Lessac · female", "en-US", "female"),
    ("en_US-ryan-medium", "Ryan · male", "en-US", "male"),
    ("en_US-joe-medium", "Joe · male", "en-US", "male"),
    ("en_US-kusal-medium", "Kusal · male", "en-US", "male"),
    ("en_GB-alan-medium", "Alan · male", "en-GB", "male"),
    ("hi_IN-pratham-medium", "Pratham · male", "hi-IN", "male"),
]
ZONOS_MODEL = {"id": "zonos3-mini", "label": "ZONOS3-Mini"}
# Zyphra ZONOS3-Mini release voices (Apache 2.0): 27 professional narrators
# across English, French, German, Hindi, Italian, Korean, Mandarin,
# Portuguese, Spanish and Telugu.
ZONOS_VOICES = [
    {"id": "Savannah", "label": "Savannah · female", "language": "en-US", "gender": "female"},
    {"id": "Wyatt", "label": "Wyatt · male", "language": "en-US", "gender": "male"},
    {"id": "Imogen", "label": "Imogen · female", "language": "en-GB", "gender": "female"},
    {"id": "Rupert", "label": "Rupert · male", "language": "en-GB", "gender": "male"},
    {"id": "Cillian", "label": "Cillian · male", "language": "en-GB", "gender": "male"},
    {"id": "Jett", "label": "Jett · male", "language": "en-US", "gender": "male"},
    {"id": "Morgana", "label": "Morgana · female", "language": "en-US", "gender": "female"},
    {"id": "Sakura", "label": "Sakura · female", "language": "en-US", "gender": "female"},
    {"id": "Thaddeus", "label": "Thaddeus · male", "language": "en-US", "gender": "male"},
    {"id": "Willow", "label": "Willow · female", "language": "en-US", "gender": "female"},
    {"id": "Gaspard", "label": "Gaspard · male", "language": "fr-FR", "gender": "male"},
    {"id": "Liesel", "label": "Liesel · female", "language": "de-DE", "gender": "female"},
    {"id": "Wolfgang", "label": "Wolfgang · male", "language": "de-DE", "gender": "male"},
    {"id": "Ananya", "label": "Ananya · female", "language": "hi-IN", "gender": "female"},
    {"id": "Arjun", "label": "Arjun · male", "language": "hi-IN", "gender": "male"},
    {"id": "Ginevra", "label": "Ginevra · female", "language": "it-IT", "gender": "female"},
    {"id": "Lorenzo", "label": "Lorenzo · male", "language": "it-IT", "gender": "male"},
    {"id": "Seoyeon", "label": "Seoyeon · female", "language": "ko-KR", "gender": "female"},
    {"id": "Minjun", "label": "Minjun · male", "language": "ko-KR", "gender": "male"},
    {"id": "Meilin", "label": "Meilin · female", "language": "zh-CN", "gender": "female"},
    {"id": "Haoran", "label": "Haoran · male", "language": "zh-CN", "gender": "male"},
    {"id": "Leonor", "label": "Leonor · female", "language": "pt-BR", "gender": "female"},
    {"id": "Thiago", "label": "Thiago · male", "language": "pt-BR", "gender": "male"},
    {"id": "Ximena", "label": "Ximena · female", "language": "es-ES", "gender": "female"},
    {"id": "Rodrigo", "label": "Rodrigo · male", "language": "es-ES", "gender": "male"},
    {"id": "Sravya", "label": "Sravya · female", "language": "te-IN", "gender": "female"},
    {"id": "Chaitanya", "label": "Chaitanya · male", "language": "te-IN", "gender": "male"},
]
ZONOS_VOICE_LANGUAGES = {
    "Savannah": "en_us", "Wyatt": "en_us", "Imogen": "en_gb", "Rupert": "en_gb",
    "Cillian": "en_gb", "Jett": "en_us", "Morgana": "en_us", "Sakura": "en_us",
    "Thaddeus": "en_us", "Willow": "en_us", "Gaspard": "fr_fr", "Liesel": "de",
    "Wolfgang": "de", "Ananya": "hi", "Arjun": "hi", "Ginevra": "it", "Lorenzo": "it",
    "Seoyeon": "ko", "Minjun": "ko", "Meilin": "cmn", "Haoran": "cmn",
    "Leonor": "pt_br", "Thiago": "pt_br", "Ximena": "es", "Rodrigo": "es",
    "Sravya": "te", "Chaitanya": "te",
}
ZONOS_ASSET_FILES = ("config.json", "model.safetensors", "voices.safetensors", "modeling_zonos3.py")
LOCAL_RUNTIME_ALIASES = {"styletts2": ("sts2",)}
LOCAL_PROBE_TTL = 600
LOCAL_WORKER_TIMEOUT = 180
_LOCAL_PROBES: dict = {}
_LOCAL_PROBE_LOCK = threading.Lock()
_PROBE_CACHE_LOCK = threading.Lock()
_PROBE_CACHE_FILE = "tts-probes.json"


def _read_probe_cache_file() -> dict:
    try:
        data = json.loads((_keys_dir() / _PROBE_CACHE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_probe_cache_entry(key: str, entry: dict) -> None:
    with _PROBE_CACHE_LOCK:
        data = _read_probe_cache_file()
        data[key] = entry
        cutoff = time.time() - LOCAL_PROBE_TTL * 6
        data = {
            name: value for name, value in data.items()
            if isinstance(value, dict) and float(value.get("at") or 0) >= cutoff
        }
        try:
            _write_text_atomic(_keys_dir() / _PROBE_CACHE_FILE, json.dumps(data))
        except OSError:
            pass


class _LocalTtsWorker:
    """A persistent JSON-lines worker in an optional runtime interpreter."""

    def __init__(self, name: str):
        self.name = name
        self.lock = threading.RLock()
        self.proc = None
        self.queue = None
        self.device = ""
        self.boots = 0
        self.last_stderr = ""
        self.last_used = 0.0

    def alive(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        self.queue = None
        self.device = ""
        if not proc:
            return
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proc.kill()
            except OSError:
                pass

    def start(self, python: str, script: Path, args: list[str], timeout: int = 300) -> None:
        self.stop()
        self.last_stderr = ""
        print(f"  [{self.name}] starting worker with {python}")
        proc = subprocess.Popen(
            [python, str(script), *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            cwd=str(script.parent),
        )
        messages: queue.Queue = queue.Queue()

        def drain_stderr():
            tail = []
            for line in proc.stderr or []:
                line = line.rstrip()
                if line:
                    tail = (tail + [line])[-12:]
                    self.last_stderr = " | ".join(tail)[-1000:]

        def pump():
            try:
                for line in proc.stdout or []:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(message, dict):
                        messages.put(message)
            finally:
                messages.put({"event": "closed"})

        threading.Thread(target=drain_stderr, name=f"{self.name}-stderr", daemon=True).start()
        threading.Thread(target=pump, name=f"{self.name}-pump", daemon=True).start()
        self.proc, self.queue = proc, messages
        try:
            ready = messages.get(timeout=timeout)
        except queue.Empty:
            self.stop()
            raise RuntimeError(f"{self.name} runtime did not become ready in time.")
        if ready.get("event") != "ready":
            detail = self.last_stderr or ready.get("error") or "no ready signal"
            self.stop()
            raise RuntimeError(f"{self.name} runtime failed to load: {detail[-300:]}")
        self.device = str(ready.get("device") or "")
        self.boots += 1
        self.last_used = time.time()
        _ensure_model_idle_watchdog()
        print(f"  [{self.name}] worker ready ({self.device or 'unknown device'})")

    def request(self, payload: dict, timeout: int = LOCAL_WORKER_TIMEOUT) -> dict:
        if not self.alive():
            raise OSError(f"{self.name} worker is not running")
        self.last_used = time.time()
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        response = self.queue.get(timeout=timeout)
        self.last_used = time.time()
        return response


_STYLETTS2_WORKER = _LocalTtsWorker("StyleTTS2")
_KOKORO_WORKER = _LocalTtsWorker("Kokoro")
_PIPER_WORKER = _LocalTtsWorker("Piper")
_ZONOS_WORKER = _LocalTtsWorker("ZONOS3-Mini")
_EMBEDDING_WORKER = _LocalTtsWorker("EmbeddingGemma")


def _model_idle_seconds() -> float:
    try:
        return float(os.environ.get("CLIPACANVAS_MODEL_IDLE_SECONDS", "120"))
    except ValueError:
        return 120.0


MODEL_IDLE_SECONDS = _model_idle_seconds()
_IDLE_MANAGED_WORKERS = (
    _STYLETTS2_WORKER, _KOKORO_WORKER, _PIPER_WORKER, _ZONOS_WORKER, _EMBEDDING_WORKER,
)
_IDLE_WATCH_STARTED = False
_IDLE_WATCH_LOCK = threading.Lock()


def _model_idle_watchdog() -> None:
    if MODEL_IDLE_SECONDS <= 0:
        return
    while True:
        time.sleep(5.0)
        now = time.time()
        for worker in _IDLE_MANAGED_WORKERS:
            if not worker.alive() or now - worker.last_used < MODEL_IDLE_SECONDS:
                continue
            if not worker.lock.acquire(blocking=False):
                continue
            try:
                if worker.alive() and now - worker.last_used >= MODEL_IDLE_SECONDS:
                    print(f"  [{worker.name}] unloading idle model")
                    worker.stop()
            finally:
                worker.lock.release()


def _ensure_model_idle_watchdog() -> None:
    global _IDLE_WATCH_STARTED
    with _IDLE_WATCH_LOCK:
        if _IDLE_WATCH_STARTED:
            return
        _IDLE_WATCH_STARTED = True
    threading.Thread(target=_model_idle_watchdog, name="model-idle-watch", daemon=True).start()


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
                name = parts[0].replace("Microsoft ", "").replace(" Desktop", "").strip() or parts[0]
                gender = (parts[2] if len(parts) > 2 else "").strip().lower()
                voices.append({
                    "id": parts[0],
                    "label": f"{name} · {gender}" if gender else name,
                    "language": parts[1] or "unknown",
                    "gender": gender,
                })
            if not voices:
                error = "No installed Windows speech voices were found."
        except (OSError, subprocess.TimeoutExpired) as exc:
            error = f"Windows speech engine unavailable: {exc}"
    with _SAPI_VOICE_LOCK:
        _SAPI_VOICE_CACHE.update({"at": time.time(), "voices": voices, "error": error})
    return voices, error


def _probe_local_engines(jobs: dict) -> dict:
    """Run local runtime import probes in parallel; jobs maps name to (python, code) or None."""
    results = {name: (False, "", "") for name in jobs}
    pending = {name: job for name, job in jobs.items() if job}
    if not pending:
        return results
    with ThreadPoolExecutor(max_workers=len(pending)) as pool:
        futures = {
            name: pool.submit(_local_probe, name, python, code)
            for name, (python, code) in pending.items()
        }
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as exc:
                results[name] = (False, f"{name} runtime check failed: {exc}", "")
    return results


def tts_provider_registry() -> dict:
    keys = _load_saved_keys()
    sapi_voices, sapi_error = _sapi_voice_list()

    sts_python, sts_assets, sts_voices, sts_error = _styletts2_locate()
    kk_python, kk_error = _kokoro_locate()
    pp_python, pp_voices, pp_error = _piper_locate()
    zo_python, zo_assets, zo_error = _zonos_locate()
    probes = _probe_local_engines({
        "StyleTTS2": (sts_python, "import torch, styletts2, soundfile; print('device=' + ('cuda' if torch.cuda.is_available() else 'cpu'))") if not sts_error else None,
        "Kokoro": (kk_python, "import torch, kokoro, soundfile; print('device=' + ('cuda' if torch.cuda.is_available() else 'cpu'))") if not kk_error else None,
        "Piper": (pp_python, "import piper, soundfile; print('device=cpu')") if not pp_error else None,
        "ZONOS3-Mini": (zo_python, "import torch, transformers, soundfile; print('device=' + ('cuda' if torch.cuda.is_available() else 'cpu'))") if not zo_error else None,
    })
    sts_ok, sts_reason, sts_device = probes["StyleTTS2"]
    kk_ok, kk_reason, kk_device = probes["Kokoro"]
    pp_ok, pp_reason, _ = probes["Piper"]
    zo_ok, zo_reason, _ = probes["ZONOS3-Mini"]
    sts_note = "Local neural voice; no key, no upload. A voice is computed from its reference on first use, then about a second per line."
    if sts_ok and sts_device:
        sts_note = f"Local neural voice on {sts_device.upper()}; no key, no upload. A voice is computed from its reference on first use, then about a second per line."
    kk_note = "Fast local neural voice; no key, no upload. Warm lines synthesize in a fraction of a second."
    if kk_ok and kk_device:
        kk_note = f"Fast local neural voice on {kk_device.upper()}; no key, no upload. Warm lines synthesize in a fraction of a second."
    zo_note = "43 languages and 27 narrators at 44.1 kHz; no key, no upload. Runs on CPU by default, so long scripts take longer than the lightweight engines."
    sts_voice_entries = [
        dict(voice) for voice in STYLETTS2_VOICES
        if voice["id"] == "default"
        or (sts_voices and (Path(sts_voices) / STYLETTS2_VOICE_REFS[voice["id"]]).exists())
    ]
    piper_voice_entries = [
        {"id": voice_id, "label": label, "language": language, "gender": gender}
        for voice_id, label, language, gender in PIPER_VOICES
        if pp_voices and (Path(pp_voices) / f"{voice_id}.onnx").exists()
    ]
    pp_available = bool(pp_ok and piper_voice_entries)

    providers = [
        {
            "id": "styletts2",
            "label": "StyleTTS2 (local neural)",
            "kind": "local",
            "available": bool(sts_ok),
            "reason": "" if sts_ok else (sts_error or sts_reason or "StyleTTS2 runtime is not installed."),
            "requiresKey": "",
            "models": [STYLETTS2_MODEL],
            "voices": sts_voice_entries,
            "languages": ["en-US"],
            "formats": ["wav"],
            "supports": {"speed": False, "style": False, "emotion": False, "voiceCloning": False, "streaming": False},
            "notes": sts_note,
            "terms": "Runs locally. Script text never leaves the machine.",
        },
        {
            "id": "kokoro",
            "label": "Kokoro (local neural)",
            "kind": "local",
            "available": bool(kk_ok),
            "reason": "" if kk_ok else (kk_error or kk_reason or "Kokoro runtime is not installed."),
            "requiresKey": "",
            "models": [KOKORO_MODEL],
            "voices": KOKORO_VOICES,
            "languages": sorted({voice["language"] for voice in KOKORO_VOICES}),
            "formats": ["wav"],
            "supports": {"speed": True, "style": False, "emotion": False, "voiceCloning": False, "streaming": False},
            "notes": kk_note,
            "terms": "Runs locally. Script text never leaves the machine.",
        },
        {
            "id": "piper",
            "label": "Piper (local neural)",
            "kind": "local",
            "available": pp_available,
            "reason": "" if pp_available else (pp_error or pp_reason or "Piper runtime is not installed."),
            "requiresKey": "",
            "models": [PIPER_MODEL],
            "voices": piper_voice_entries,
            "languages": sorted({voice["language"] for voice in piper_voice_entries}),
            "formats": ["wav"],
            "supports": {"speed": True, "style": False, "emotion": False, "voiceCloning": False, "streaming": False},
            "notes": "Lightweight CPU neural voice; no key, no GPU needed. Good on laptops and while the GPU renders.",
            "terms": "Runs locally. Script text never leaves the machine.",
        },
        {
            "id": "zonos",
            "label": "ZONOS3-Mini (local neural)",
            "kind": "local",
            "available": bool(zo_ok and zo_assets),
            "reason": "" if zo_ok and zo_assets else (zo_error or zo_reason or "ZONOS3-Mini runtime is not installed."),
            "requiresKey": "",
            "models": [ZONOS_MODEL],
            "voices": ZONOS_VOICES,
            "languages": sorted({voice["language"] for voice in ZONOS_VOICES}),
            "formats": ["wav"],
            "supports": {"speed": False, "style": False, "emotion": False, "voiceCloning": False, "streaming": False},
            "notes": zo_note,
            "terms": "Runs locally. Script text never leaves the machine.",
        },
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
            "voices": [{"id": voice, "label": f"{voice} · {gender}", "language": "auto", "gender": gender} for voice, gender in GEMINI_TTS_VOICES],
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
            "voices": [{"id": voice_id, "label": f"{label} · {gender}", "language": language, "gender": gender} for voice_id, label, language, gender in MISTRAL_TTS_VOICES],
            "languages": sorted({language for _, _, language, _ in MISTRAL_TTS_VOICES}),
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


def _local_runtime_dir(name: str) -> Path:
    return _keys_dir() / "runtimes" / name


def _local_runtime_config(name: str) -> dict:
    try:
        data = json.loads((_local_runtime_dir(name) / "runtime.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _local_worker_path(script_name: str) -> Path | None:
    for base in (APP_DIR, Path(sys.executable).resolve().parent, Path.cwd()):
        candidate = base / script_name
        if candidate.exists():
            return candidate
    return None


def _local_python(name: str, env_var: str, config: dict) -> str:
    runtime_dir = _local_runtime_dir(name)
    candidates = [
        os.environ.get(env_var, ""),
        str(config.get("python") or ""),
        str(runtime_dir / "python.exe"),
        str(runtime_dir / "Scripts" / "python.exe"),
        str(runtime_dir / "venv" / "Scripts" / "python.exe"),
    ]
    if not getattr(sys, "frozen", False):
        candidates.append(sys.executable)
    local_appdata = os.environ.get("LOCALAPPDATA") or ""
    if local_appdata:
        candidates.append(str(Path(local_appdata) / "Programs" / "Python" / "Python311" / "python.exe"))
    venv_names = (name, *LOCAL_RUNTIME_ALIASES.get(name, ()))
    venv_candidates = []
    for base in (APP_DIR, Path.cwd(), Path(sys.executable).resolve().parent, Path(sys.executable).resolve().parent.parent):
        for venv_name in venv_names:
            venv_candidates.append(str(base / ".venvs" / venv_name / "Scripts" / "python.exe"))
    # A dedicated engine venv is a stronger signal than the current interpreter.
    candidates = venv_candidates + candidates
    return next((item for item in candidates if item and Path(item).exists()), "")


def _local_probe(name: str, python: str, code: str) -> tuple[bool, str, str]:
    key = f"{name}|{python}"
    with _LOCAL_PROBE_LOCK:
        entry = _LOCAL_PROBES.get(key)
        if entry and time.time() - entry["at"] < LOCAL_PROBE_TTL:
            return entry["ok"], entry["reason"], entry["device"]
    # The import probe costs seconds on a cold start (torch import), so reuse
    # the last answer across launches and recheck after the TTL.
    with _PROBE_CACHE_LOCK:
        cached = _read_probe_cache_file().get(key)
    if isinstance(cached, dict) and time.time() - float(cached.get("at") or 0) < LOCAL_PROBE_TTL:
        entry = {
            "at": float(cached.get("at") or 0),
            "ok": bool(cached.get("ok")),
            "reason": str(cached.get("reason") or ""),
            "device": str(cached.get("device") or ""),
        }
        with _LOCAL_PROBE_LOCK:
            _LOCAL_PROBES[key] = entry
        return entry["ok"], entry["reason"], entry["device"]
    ok, reason, device = False, "", ""
    try:
        proc = subprocess.run(
            [python, "-c", code], capture_output=True, text=True, errors="replace", timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), cwd=str(APP_DIR),
        )
        match = re.search(r"device=(cuda|cpu)", proc.stdout or "")
        if proc.returncode == 0 and match:
            ok, device = True, match.group(1)
        else:
            lines = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip().splitlines()
            reason = f"{name} runtime failed to start: {lines[-1][:200] if lines else 'unknown error'}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        reason = f"{name} runtime failed to start: {exc}"
    entry = {"at": time.time(), "ok": ok, "reason": reason, "device": device}
    with _LOCAL_PROBE_LOCK:
        _LOCAL_PROBES[key] = entry
    _write_probe_cache_entry(key, entry)
    return ok, reason, device


def _styletts2_locate() -> tuple[str, str, str, str]:
    """Resolve the optional StyleTTS2 runtime: (python, assets root, voices root, error)."""
    config = _local_runtime_config("styletts2")
    python = _local_python("styletts2", "CLIPACANVAS_STYLETTS2_PYTHON", config)
    runtime_dir = _local_runtime_dir("styletts2")
    asset_roots = [
        os.environ.get("CLIPACANVAS_STYLETTS2_ASSETS", ""),
        str(config.get("assets") or ""),
        str(runtime_dir / "assets"),
        str(APP_DIR / "output" / "uitest" / "tts" / "sts2" / "assets"),
    ]
    assets = next(
        (root for root in asset_roots
         if root and all((Path(root) / name).exists() for name in STYLETTS2_ASSET_FILES)),
        "",
    )
    reference_names = set(STYLETTS2_VOICE_REFS.values())
    voice_roots = [
        os.environ.get("CLIPACANVAS_STYLETTS2_VOICES", ""),
        str(runtime_dir / "voices"),
        str(APP_DIR / "styletts2-voices"),
    ]
    voices = next(
        (root for root in voice_roots
         if root and any((Path(root) / name).exists() for name in reference_names)),
        "",
    )
    if not python:
        return "", "", voices, "StyleTTS2 runtime is not installed."
    if not assets:
        return python, "", voices, "StyleTTS2 model assets are missing from the runtime folder."
    if not _local_worker_path("styletts2_worker.py"):
        return python, assets, voices, "The StyleTTS2 worker is missing from this build."
    return python, assets, voices, ""


def _kokoro_locate() -> tuple[str, str]:
    """Resolve the optional Kokoro runtime: (python, error)."""
    config = _local_runtime_config("kokoro")
    python = _local_python("kokoro", "CLIPACANVAS_KOKORO_PYTHON", config)
    if not python:
        return "", "Kokoro runtime is not installed."
    if not _local_worker_path("kokoro_worker.py"):
        return python, "The Kokoro worker is missing from this build."
    return python, ""


def _piper_locate() -> tuple[str, str, str]:
    """Resolve the optional Piper runtime: (python, voices root, error)."""
    config = _local_runtime_config("piper")
    python = _local_python("piper", "CLIPACANVAS_PIPER_PYTHON", config)
    voices_roots = [
        os.environ.get("CLIPACANVAS_PIPER_VOICES", ""),
        str(config.get("voices") or ""),
        str(_local_runtime_dir("piper") / "voices"),
        str(APP_DIR / "output" / "uitest" / "tts" / "piper"),
    ]
    voices = next(
        (root for root in voices_roots
         if root and any((Path(root) / f"{voice_id}.onnx").exists() for voice_id, _, _, _ in PIPER_VOICES)),
        "",
    )
    if not python:
        return "", "", "Piper runtime is not installed."
    if not voices:
        return python, "", "Piper voice models are missing."
    if not _local_worker_path("piper_worker.py"):
        return python, voices, "The Piper worker is missing from this build."
    return python, voices, ""


def _zonos_locate() -> tuple[str, str, str]:
    """Resolve the optional ZONOS3-Mini runtime: (python, assets root, error)."""
    config = _local_runtime_config("zonos")
    python = _local_python("zonos", "CLIPACANVAS_ZONOS_PYTHON", config)
    runtime_dir = _local_runtime_dir("zonos")
    asset_roots = [
        os.environ.get("CLIPACANVAS_ZONOS_ASSETS", ""),
        str(config.get("assets") or ""),
        str(runtime_dir / "assets"),
    ]
    assets = next(
        (root for root in asset_roots
         if root and all((Path(root) / name).exists() for name in ZONOS_ASSET_FILES)),
        "",
    )
    if not python:
        return "", "", "ZONOS3-Mini runtime is not installed."
    if not assets:
        return python, "", "ZONOS3-Mini model assets are missing from the runtime folder."
    if not _local_worker_path("zonos_worker.py"):
        return python, assets, "The ZONOS3-Mini worker is missing from this build."
    return python, assets, ""


def _local_generate(worker: _LocalTtsWorker, python: str, script_name: str,
                    script_args: list, payload: dict, label: str,
                    timeout: int = LOCAL_WORKER_TIMEOUT) -> bytes:
    script = _local_worker_path(script_name)
    if not script:
        raise RuntimeError(f"The {label} worker is missing from this build.")
    with worker.lock:
        for attempt in (0, 1):
            if not worker.alive():
                worker.start(python, script, script_args)
            output = _tts_dir() / f"{worker.name.lower()}-{uuid.uuid4().hex}.wav"
            try:
                message = worker.request({**payload, "out": str(output)}, timeout=timeout)
            except queue.Empty:
                worker.stop()
                if attempt == 0:
                    continue
                raise RuntimeError(f"{label} timed out generating speech.")
            except OSError as exc:
                worker.stop()
                if attempt == 0:
                    continue
                raise RuntimeError(f"{label} runtime stopped unexpectedly: {exc}") from exc
            if message.get("event") == "closed":
                worker.stop()
                if attempt == 0:
                    continue
                raise RuntimeError(f"{label} runtime exited while generating speech.")
            if not message.get("ok"):
                output.unlink(missing_ok=True)
                raise RuntimeError(f"{label} failed: {message.get('error') or 'unknown error'}")
            try:
                data = output.read_bytes()
            finally:
                output.unlink(missing_ok=True)
            if len(data) < 64:
                raise RuntimeError(f"{label} returned empty audio.")
            return data
    raise RuntimeError(f"{label} failed.")


def _styletts2_synthesize(text: str, voice: str) -> bytes:
    python, assets, voices, error = _styletts2_locate()
    if error:
        raise RuntimeError(error)
    reference = ""
    ref_name = STYLETTS2_VOICE_REFS.get(voice)
    if ref_name and voices:
        candidate = Path(voices) / ref_name
        if candidate.exists():
            reference = str(candidate)
    if voice != "default" and not reference:
        raise RuntimeError("The selected StyleTTS2 voice reference is missing.")
    return _local_generate(
        _STYLETTS2_WORKER, python, "styletts2_worker.py",
        ["--assets", assets], {"text": text, "voice": voice or "default", "ref": reference}, "StyleTTS2",
    )


def _kokoro_synthesize(text: str, voice: str, speed: float) -> bytes:
    python, error = _kokoro_locate()
    if error:
        raise RuntimeError(error)
    return _local_generate(
        _KOKORO_WORKER, python, "kokoro_worker.py",
        [], {"text": text, "voice": voice or "af_heart", "speed": speed}, "Kokoro",
    )


def _piper_synthesize(text: str, voice: str, speed: float) -> bytes:
    python, voices, error = _piper_locate()
    if error:
        raise RuntimeError(error)
    return _local_generate(
        _PIPER_WORKER, python, "piper_worker.py",
        ["--voices", voices], {"text": text, "voice": voice, "speed": speed}, "Piper",
    )


def _zonos_synthesize(text: str, voice: str) -> bytes:
    python, assets, error = _zonos_locate()
    if error:
        raise RuntimeError(error)
    device = os.environ.get("CLIPACANVAS_ZONOS_DEVICE", "cpu").strip().lower()
    if device not in ("cpu", "cuda"):
        device = "cpu"
    return _local_generate(
        _ZONOS_WORKER, python, "zonos_worker.py",
        ["--assets", assets, "--device", device],
        {"text": text, "voice": voice, "language": ZONOS_VOICE_LANGUAGES.get(voice, "en_us")},
        "ZONOS3-Mini", timeout=900,
    )


def _local_engine(provider_id: str) -> dict | None:
    if provider_id == "styletts2":
        python, assets, voices, error = _styletts2_locate()
        return {
            "name": "StyleTTS2", "worker": _STYLETTS2_WORKER, "python": python,
            "script": "styletts2_worker.py", "args": ["--assets", assets] if assets else [], "error": error,
            "probe": "import torch, styletts2, soundfile; print('device=' + ('cuda' if torch.cuda.is_available() else 'cpu'))",
        }
    if provider_id == "kokoro":
        python, error = _kokoro_locate()
        return {
            "name": "Kokoro", "worker": _KOKORO_WORKER, "python": python,
            "script": "kokoro_worker.py", "args": [], "error": error,
            "probe": "import torch, kokoro, soundfile; print('device=' + ('cuda' if torch.cuda.is_available() else 'cpu'))",
        }
    if provider_id == "piper":
        python, voices, error = _piper_locate()
        return {
            "name": "Piper", "worker": _PIPER_WORKER, "python": python,
            "script": "piper_worker.py", "args": ["--voices", voices] if voices else [], "error": error,
            "probe": "import piper, soundfile; print('device=cpu')",
        }
    if provider_id == "zonos":
        python, assets, error = _zonos_locate()
        device = os.environ.get("CLIPACANVAS_ZONOS_DEVICE", "cpu").strip().lower()
        if device not in ("cpu", "cuda"):
            device = "cpu"
        return {
            "name": "ZONOS3-Mini", "worker": _ZONOS_WORKER, "python": python,
            "script": "zonos_worker.py", "args": ["--assets", assets, "--device", device] if assets else [], "error": error,
            "probe": "import torch, transformers, soundfile; print('device=' + ('cuda' if torch.cuda.is_available() else 'cpu'))",
        }
    return None


def _stop_local_workers() -> None:
    for worker in (_STYLETTS2_WORKER, _KOKORO_WORKER, _PIPER_WORKER, _ZONOS_WORKER, _EMBEDDING_WORKER, _STT_WORKER):
        worker.stop()


atexit.register(_stop_local_workers)


# ── Local dictation (speech-to-text) ──────────────────────────────

STT_MAX_RECORD_SECONDS = 120
STT_MAX_AUDIO_BYTES = 40 * 1024 * 1024

_STT_WORKER = _LocalTtsWorker("SpeechToText")
_IDLE_MANAGED_WORKERS = (*_IDLE_MANAGED_WORKERS, _STT_WORKER)
_STT_LOCK = threading.RLock()
_STT_BOOT_LOCK = threading.Lock()
_STT_STATE_LOCK = threading.Lock()
_STT_STATE = {
    "phase": "idle",
    "modelState": "idle",
    "modelError": "",
    "progress": {"stage": "", "pct": 0, "detail": ""},
    "error": "",
    "startedAt": 0.0,
    "lastText": "",
    "input": "",
    "device": "",
    "peak": 0.0,
}


def _stt_dir() -> Path:
    directory = _keys_dir() / "stt"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _stt_model_id() -> str:
    model = (os.environ.get("CLIPACANVAS_STT_MODEL") or "").strip()
    return model or "faster-whisper-small.en"


def _stt_locate() -> tuple[str, str, str]:
    config = _local_runtime_config("stt")
    python = _local_python("stt", "CLIPACANVAS_STT_PYTHON", config)
    assets = (
        (os.environ.get("CLIPACANVAS_STT_ASSETS") or "").strip()
        or str(config.get("assets") or "").strip()
        or str(_local_runtime_dir("stt") / "assets")
    )
    if not python:
        return "", assets, (
            "The local dictation runtime was not found. Install Python 3.11 with "
            "faster-whisper, sounddevice and soundfile, or set CLIPACANVAS_STT_PYTHON."
        )
    return python, assets, ""


def _stt_model_ready() -> bool:
    try:
        data = json.loads((Path(_stt_locate()[1]) / "model-ready.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return str(data.get("model") or "") == _stt_model_id()


def _stt_update(**fields) -> None:
    with _STT_STATE_LOCK:
        _STT_STATE.update(fields)


def _stt_snapshot() -> dict:
    with _STT_STATE_LOCK:
        state = dict(_STT_STATE)
        state["progress"] = dict(_STT_STATE.get("progress") or {})
    phase = str(state.get("phase") or "idle")
    recording = phase == "recording"
    elapsed = 0.0
    if recording and state.get("startedAt"):
        elapsed = round(max(0.0, time.time() - float(state["startedAt"])), 1)
    return {**state, "phase": phase, "recording": recording, "elapsed": elapsed}


def _stt_request(payload: dict, timeout: float = 180.0) -> dict:
    """Send a request and consume progress events until the final answer."""
    worker = _STT_WORKER
    if not worker.alive() or worker.proc is None or worker.queue is None:
        raise OSError("The dictation engine is not running.")
    # Hold the worker lock for real work so the idle watchdog cannot unload the
    # model mid-recording or mid-transcription. Status probes stay lock-free.
    locked = str(payload.get("op") or "") != "status"
    if locked:
        worker.lock.acquire()
    try:
        worker.last_used = time.time()
        worker.proc.stdin.write(json.dumps(payload) + "\n")
        worker.proc.stdin.flush()
        deadline = time.time() + timeout
        while True:
            remaining = max(0.5, deadline - time.time())
            message = worker.queue.get(timeout=remaining)
            if not isinstance(message, dict):
                continue
            event = message.get("event")
            if event == "closed":
                return {"ok": False, "closed": True, "error": "The dictation engine stopped unexpectedly."}
            if event == "progress":
                _stt_update(progress={
                    "stage": str(message.get("stage") or ""),
                    "pct": int(message.get("pct") or 0),
                    "detail": str(message.get("detail") or ""),
                })
                continue
            if event == "model":
                state = str(message.get("state") or "")
                if state == "ready":
                    _stt_update(modelState="ready", modelError="")
                elif state == "error":
                    _stt_update(modelState="error", modelError=str(message.get("error") or "Speech model failed to load."))
                continue
            return message
    finally:
        if locked:
            worker.lock.release()


def _ensure_stt_worker() -> None:
    python, assets, error = _stt_locate()
    if error:
        raise RuntimeError(error)
    with _STT_BOOT_LOCK:
        if _STT_WORKER.alive():
            return
        script = _local_worker_path("stt_worker.py")
        if not script:
            raise RuntimeError("The dictation worker is missing from this build.")
        device = (os.environ.get("CLIPACANVAS_STT_DEVICE") or "auto").strip().lower()
        if device not in ("cpu", "cuda"):
            device = "auto"
        Path(assets).mkdir(parents=True, exist_ok=True)
        _STT_WORKER.start(
            python, script,
            ["--assets", assets, "--model", _stt_model_id(), "--device", device],
            timeout=300,
        )
        _stt_update(device=_STT_WORKER.device)


def _stt_live_status() -> dict:
    state = _stt_snapshot()
    python, _assets, reason = _stt_locate()
    state.update({
        "available": bool(python),
        "reason": reason,
        "engine": "faster-whisper small.en (local, English)",
        "model": _stt_model_id(),
        "maxSeconds": STT_MAX_RECORD_SECONDS,
        "languages": ["en"],
    })
    worker = _STT_WORKER
    if worker.alive() and state["phase"] in ("preparing", "recording", "transcribing"):
        worker.last_used = time.time()
    if worker.alive() and state["phase"] != "transcribing" and _STT_LOCK.acquire(blocking=False):
        try:
            message = _stt_request({"op": "status"}, timeout=2.0)
            if message.get("ok"):
                state["modelState"] = str(message.get("modelState") or state["modelState"])
                state["modelError"] = str(message.get("modelError") or "")
                if isinstance(message.get("progress"), dict):
                    state["progress"] = dict(message["progress"])
                state["input"] = str(message.get("input") or state.get("input") or "")
                state["device"] = str(message.get("device") or state.get("device") or "")
                if message.get("recording"):
                    state["phase"] = "recording"
                    state["recording"] = True
                    state["elapsed"] = float(message.get("elapsed") or 0.0)
                    state["peak"] = float(message.get("peak") or 0.0)
        except (queue.Empty, OSError):
            pass
        finally:
            _STT_LOCK.release()
    state["modelReady"] = _stt_model_ready() or state.get("modelState") == "ready"
    return state



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
    if provider["kind"] == "local" and not provider["available"]:
        raise RuntimeError(provider["reason"] or "Local speech is unavailable.")
    if not provider["available"]:
        if provider.get("requiresKey"):
            raise PermissionError(provider["reason"] or f"{provider['label']} is not configured.")
        raise RuntimeError(provider["reason"] or f"{provider['label']} is unavailable.")

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
    elif provider_id == "styletts2":
        audio_bytes = _styletts2_synthesize(text, voice)
    elif provider_id == "kokoro":
        audio_bytes = _kokoro_synthesize(text, voice, speed)
    elif provider_id == "piper":
        audio_bytes = _piper_synthesize(text, voice, speed)
    elif provider_id == "zonos":
        audio_bytes = _zonos_synthesize(text, voice)
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
        proc = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=120,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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


def _embedding_model_path(roots: list[str]) -> str:
    for root in roots:
        if not root:
            continue
        candidate = Path(root)
        if candidate.is_file() and candidate.suffix == ".litertlm":
            return str(candidate)
        if candidate.is_dir():
            preferred = candidate / VISUAL_MODEL_FILE
            if preferred.exists():
                return str(preferred)
            matches = sorted(candidate.glob("*.litertlm"))
            if matches:
                return str(matches[0])
    return ""


def _embedding_locate() -> tuple[str, str, str]:
    """Resolve the LiteRT EmbeddingGemma 2 runtime: (python, model file, error)."""
    config = _local_runtime_config(VISUAL_RUNTIME)
    python = _local_python(VISUAL_RUNTIME, "CLIPACANVAS_EMBEDDING_PYTHON", config)
    runtime_dir = _local_runtime_dir(VISUAL_RUNTIME)
    model = _embedding_model_path([
        os.environ.get("CLIPACANVAS_EMBEDDING_MODEL", ""),
        os.environ.get("CLIPACANVAS_EMBEDDING_ASSETS", ""),
        str(config.get("assets") or ""),
        str(runtime_dir / "assets"),
    ])
    if not python:
        return "", "", "EmbeddingGemma LiteRT runtime is not installed."
    if not model:
        return python, "", "EmbeddingGemma LiteRT model is missing from the runtime folder."
    if not _local_worker_path("embedding_litert_worker.py"):
        return python, model, "The EmbeddingGemma worker is missing from this build."
    return python, model, ""


def _embedding_device() -> str:
    device = os.environ.get("CLIPACANVAS_EMBEDDING_DEVICE", VISUAL_DEVICE_DEFAULT).strip().lower()
    return device if device in ("cpu", "cuda", "gpu", "auto") else VISUAL_DEVICE_DEFAULT


def _embedding_request(payload: dict, timeout: int = 600) -> dict:
    python, model, error = _embedding_locate()
    if error:
        raise RuntimeError(error)
    script = _local_worker_path("embedding_litert_worker.py")
    if not script:
        raise RuntimeError("The EmbeddingGemma worker is missing from this build.")
    args = ["--model", model, "--device", _embedding_device()]
    with _EMBEDDING_WORKER.lock:
        for attempt in (0, 1):
            if not _EMBEDDING_WORKER.alive():
                _EMBEDDING_WORKER.start(python, script, args, timeout=420)
            try:
                message = _EMBEDDING_WORKER.request(payload, timeout=timeout)
            except queue.Empty:
                _EMBEDDING_WORKER.stop()
                if attempt == 0:
                    continue
                raise RuntimeError("EmbeddingGemma timed out.")
            except OSError as exc:
                _EMBEDDING_WORKER.stop()
                if attempt == 0:
                    continue
                raise RuntimeError(f"EmbeddingGemma runtime stopped unexpectedly: {exc}") from exc
            if message.get("event") == "closed":
                _EMBEDDING_WORKER.stop()
                if attempt == 0:
                    continue
                raise RuntimeError("EmbeddingGemma runtime exited while indexing.")
            if not message.get("ok"):
                raise RuntimeError(f"EmbeddingGemma failed: {message.get('error') or 'unknown error'}")
            return message
    raise RuntimeError("EmbeddingGemma failed.")


def _visual_frames(path: Path, filename: str, kind: str, technical: dict) -> list[tuple[float, Path]]:
    """Frames for the retrieval index: one still for images, ~1 fps samples for video."""
    frame_dir = _analysis_frame_dir(filename)
    if kind == "image":
        target = frame_dir / "image.jpg"
        if not target.exists():
            try:
                subprocess.run(
                    [FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
                     "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(target)],
                    capture_output=True, text=True, errors="replace", timeout=30,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
        return [(0.0, target)] if target.exists() and target.stat().st_size > 128 else []
    duration = float(technical.get("duration") or 0)
    if duration <= 0:
        return []
    interval = max(1.0 / VISUAL_FRAME_FPS, duration / VISUAL_FRAME_LIMIT)
    for stale in frame_dir.glob("index-*.jpg"):
        try:
            stale.unlink()
        except OSError:
            pass
    limit_time = min(duration, interval * VISUAL_FRAME_LIMIT)
    try:
        subprocess.run(
            [FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error",
             "-t", f"{limit_time:.3f}", "-i", str(path),
             "-vf", f"fps={1.0 / interval:.6f},scale=640:-2",
             "-q:v", "4", str(frame_dir / "index-%02d.jpg")],
            capture_output=True, text=True, errors="replace", timeout=240,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        pass
    entries: list[tuple[float, Path]] = []
    for index, target in enumerate(sorted(frame_dir.glob("index-*.jpg"))):
        if not target.exists() or target.stat().st_size < 128:
            continue
        entries.append((round(index * interval, 3), target))
        if len(entries) >= VISUAL_FRAME_LIMIT:
            break
    return entries


def _motion_profile(path: Path, duration: float | None) -> dict:
    """Frame-difference motion score from grayscale samples, CPU only."""
    if not duration or duration <= 0.25:
        return {"score": 0.0, "peak": 0.0, "label": "still", "profile": []}
    fps = 4
    width, height = 128, 72
    limit = min(float(duration), 120.0)
    try:
        proc = subprocess.run(
            [FFMPEG_EXE, "-v", "error", "-t", f"{limit:.3f}", "-i", str(path),
             "-vf", f"scale={width}:{height},format=gray", "-r", str(fps),
             "-f", "rawvideo", "-"],
            capture_output=True, timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"score": 0.0, "label": "unknown", "profile": []}
    frame_size = width * height
    data = proc.stdout or b""
    frames = [data[i:i + frame_size] for i in range(0, len(data) - frame_size + 1, frame_size)]
    if len(frames) < 2:
        return {"score": 0.0, "peak": 0.0, "label": "still", "profile": []}
    buckets: dict[int, list[float]] = {}
    diffs: list[float] = []
    for index in range(1, len(frames)):
        diff = sum(abs(a - b) for a, b in zip(frames[index], frames[index - 1])) / (frame_size * 255.0)
        diffs.append(diff)
        buckets.setdefault(int(index / fps), []).append(diff)
    profile = [[second, round(sum(values) / len(values), 4)] for second, values in sorted(buckets.items())]
    score = round(sum(diffs) / len(diffs), 4)
    diffs.sort()
    peak = round(diffs[int((len(diffs) - 1) * 0.95)], 4)
    if score < 0.002:
        label = "static"
    elif score < 0.010:
        label = "slow"
    elif score < 0.025:
        label = "moderate"
    else:
        label = "fast"
    return {"score": score, "peak": peak, "label": label, "profile": profile[:60]}


def _visual_content_summary(kind: str, technical: dict, shots: list[dict],
                            tags: list[dict], motion: dict) -> str:
    """Plain-language summary built only from local measurements."""
    labels = [str(tag.get("label") or "") for tag in tags if tag.get("label")]
    bits: list[str] = []
    if kind == "image":
        bits.append("Still image")
    else:
        duration = float(technical.get("duration") or 0)
        bits.append(f"{duration:.1f} s video" if duration > 0 else "Video")
        shot_count = len(shots) or 1
        bits.append(f"{shot_count} shot" + ("" if shot_count == 1 else "s"))
        motion_label = str(motion.get("label") or "")
        if motion_label and motion_label not in ("still", "unknown"):
            bits.append(f"{motion_label} motion")
    width = technical.get("width")
    height = technical.get("height")
    if width and height:
        shape = "portrait" if height > width else ("landscape" if width > height else "square")
        bits.append(f"{width}×{height} {shape}")
    bits.append("with audio" if technical.get("audioCodec") else "silent")
    summary = ", ".join(bits) + "."
    if labels:
        return summary + " Local visual index: " + ", ".join(labels) + "."
    return summary + " No visual labels passed the confidence floor."


def _visual_analyze_media(path: Path, filename: str, technical: dict, shots: list[dict]) -> dict:
    """Local EmbeddingGemma pass: zero-shot content tags, keyframe vectors, motion."""
    kind = _media_kind_for(filename)
    if kind not in ("image", "video"):
        return {"status": "skipped", "reason": "Visual indexing covers images and videos."}
    python, assets, error = _embedding_locate()
    if error:
        return {"status": "unavailable", "provider": VISUAL_MODEL, "reason": error}
    frames = _visual_frames(path, filename, kind, technical)
    if not frames:
        return {"status": "unavailable", "provider": VISUAL_MODEL,
                "reason": "No frames could be extracted for the retrieval index."}
    payload = {
        "kind": "tags",
        "paths": [str(target) for _, target in frames],
        "labels": VISUAL_LABELS,
        "topk": VISUAL_TAGS_PER_FRAME,
    }
    try:
        message = _embedding_request(payload)
    except Exception as exc:
        return {"status": "error", "provider": VISUAL_MODEL, "reason": str(exc)[:300]}
    results = message.get("results") or []
    if len(results) != len(frames):
        return {"status": "error", "provider": VISUAL_MODEL,
                "reason": "EmbeddingGemma returned an unexpected frame count."}
    aggregate: dict[str, float] = {}
    frame_records = []
    vectors = []
    for index, ((moment, _), result) in enumerate(zip(frames, results), start=1):
        ranked = result.get("tags") or []
        top_score = float(ranked[0].get("score") or 0) if ranked else 0.0
        floor = max(VISUAL_TAG_THRESHOLD, top_score - VISUAL_TAG_MARGIN)
        tags = [
            {"label": str(tag.get("label")), "score": round(float(tag.get("score") or 0), 3)}
            for tag in ranked[:VISUAL_TAGS_PER_FRAME]
            if float(tag.get("score") or 0) >= floor
        ]
        thumb = f"/api/media/frames/{filename}/index-{index:02d}.jpg"
        frame_records.append({"time": round(moment, 3), "thumb": thumb, "tags": tags})
        for tag in tags:
            aggregate[tag["label"]] = max(aggregate.get(tag["label"], 0.0), tag["score"])
        vector = result.get("vector") or []
        if vector:
            vectors.append({"time": round(moment, 3), "thumb": thumb, "vector": vector})
    ordered = sorted(aggregate.items(), key=lambda item: -item[1])[:VISUAL_TAG_LIMIT]
    motion = _motion_profile(path, technical.get("duration")) if kind == "video" else {
        "score": 0.0, "peak": 0.0, "label": "still", "profile": []}
    if vectors:
        try:
            (_analysis_dir() / f"embeddings-{Path(filename).stem}.json").write_text(
                json.dumps({
                    "model": VISUAL_MODEL,
                    "runtime": VISUAL_RUNTIME,
                    "dim": message.get("dim"),
                    "filename": filename,
                    "frames": vectors,
                    "indexedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }),
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"  [SERVER] embedding sidecar write failed: {exc}")
    ordered_tags = [{"label": label, "score": round(score, 3)} for label, score in ordered]
    return {
        "status": "indexed",
        "provider": "embeddinggemma-2",
        "model": VISUAL_MODEL,
        "runtime": VISUAL_RUNTIME,
        "device": _embedding_device(),
        "description": _visual_content_summary(kind, technical, shots, ordered_tags, motion),
        "tags": ordered_tags,
        "frames": frame_records,
        "motion": motion,
        "indexedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def analyze_media_file(filename: str, refresh: bool = False) -> dict:
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
    if (not refresh
            and isinstance(cached, dict)
            and cached.get("analyzer", {}).get("version") == ANALYSIS_VERSION
            and cached.get("asset", {}).get("bytes") == path.stat().st_size):
        return cached
    technical = _probe_media_technical(path)
    content_hash = filename[len("media-"):].split(".")[0]
    shots = _detect_media_shots(path, filename, technical)
    manifest = {
        "asset": {
            "contentHash": content_hash,
            "filename": filename,
            "url": f"/media/{filename}",
            "bytes": technical["bytes"],
        },
        "technical": technical,
        "shots": shots,
        "visual": _visual_analyze_media(path, filename, technical, shots),
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
            "engine": "ffmpeg-input-probe+scene-detect+embeddinggemma2",
            "analyzedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }
    if isinstance(cached, dict) and isinstance(cached.get("user"), dict):
        manifest["user"] = cached["user"]
    try:
        _write_analysis_manifest(filename, manifest)
    except OSError as exc:
        print(f"  [SERVER] analysis cache write failed: {exc}")
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
            project_id TEXT NOT NULL DEFAULT '',
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
    session_columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    if "project_id" not in session_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN project_id TEXT NOT NULL DEFAULT ''")
        # Chat history used to be global; attach it to the project that was
        # last open so existing work keeps its conversations.
        session = _read_session()
        legacy_project = str((session or {}).get('projectId') or '')
        if legacy_project:
            conn.execute("UPDATE sessions SET project_id = ? WHERE project_id = ''", (legacy_project,))
        conn.commit()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id)")
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
    legacy_project = str((_read_session() or {}).get('projectId') or '')
    for session in sessions:
        if not isinstance(session, dict):
            continue
        messages = _clean_chat_messages(session.get("messages"))
        if not messages:
            continue
        session_id = str(session.get("id") or f"chat-{int(time.time() * 1000)}")
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, project_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, legacy_project, str(session.get("title") or "Previous chat")[:120],
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


def _load_chatlog(project_id=None) -> list:
    try:
        conn = _chatlog_connect()
    except sqlite3.Error:
        return []
    try:
        sessions = []
        query = "SELECT id, title, created_at, updated_at FROM sessions"
        params = ()
        if project_id is not None:
            query += " WHERE project_id = ?"
            params = (str(project_id),)
        for row in conn.execute(query + " ORDER BY updated_at, created_at", params):
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


def _save_chatlog(sessions: list, project_id=None) -> None:
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
        scope = None if project_id is None else str(project_id)
        if not prepared:
            # A save that carries no messages would replace the store with
            # nothing; the client only legitimately clears chats through the
            # per-session DELETE endpoint.
            if scope is None:
                existing = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            else:
                existing = conn.execute(
                    "SELECT COUNT(*) FROM sessions WHERE project_id = ?", (scope,)
                ).fetchone()[0]
            if existing:
                print("  [SERVER] refused empty chatlog save; keeping stored chats")
                return
        with conn:
            if scope is None:
                conn.execute("DELETE FROM sessions")
            else:
                conn.execute("DELETE FROM sessions WHERE project_id = ?", (scope,))
            for session, session_id, messages in prepared:
                conn.execute(
                    "INSERT INTO sessions (id, project_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, scope or '', str(session.get("title") or "")[:120],
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
            if self.path == '/api/llm/usage':
                return self._handle_llm_usage()
            if urllib.parse.urlparse(self.path).path == '/api/llm/chatlog':
                return self._handle_chatlog_get(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            if self.path == '/api/prefs':
                return self._handle_prefs_get()
            if self.path == '/api/tts/providers':
                return self._handle_tts_providers()
            if self.path == '/api/stt/status':
                return self._handle_stt_status()
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
            elif self.path == '/api/media/search':
                self._handle_media_search()
            elif self.path == '/api/tts/generate':
                self._handle_tts_generate()
            elif self.path == '/api/stt/status':
                self._handle_stt_status()
            elif self.path == '/api/stt/prepare':
                self._handle_stt_prepare()
            elif self.path == '/api/stt/warm':
                self._handle_stt_warm()
            elif self.path == '/api/stt/start':
                self._handle_stt_start()
            elif self.path == '/api/stt/stop':
                self._handle_stt_stop()
            elif self.path == '/api/stt/cancel':
                self._handle_stt_cancel()
            elif urllib.parse.urlparse(self.path).path == '/api/stt/transcribe':
                self._handle_stt_transcribe()
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
                        timeout=600,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
        # A manual model pick may still switch to a sibling of the SAME provider
        # when that model is out of quota; never to another provider.
        fallback_on_quota = bool(payload.get('fallbackOnQuota', False))
        purpose = str(payload.get('purpose') or 'chat').strip().lower()[:24] or 'chat'

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
            catalog = self._catalog_models(provider, api_key)
        except Exception:
            catalog = []
        estimated_tokens = _estimate_prompt_tokens(messages, use_tools)
        input_limit = _model_input_limit(catalog, requested_model)
        if input_limit and estimated_tokens > max(1024, input_limit - 16384):
            self._send_json({
                'ok': False,
                'error': f'This request needs about {estimated_tokens} tokens, above the {input_limit}-token context of {requested_model}. Pick a model with a larger context or shorten the scene code.',
                'estimatedPromptTokens': estimated_tokens,
                'inputTokenLimit': input_limit,
            }, 400)
            return

        try:
            text = ''
            tool_calls = []
            used_model = None
            current = requested_model
            tried = []
            attempt = 0
            model_retries = 0
            last_error = None
            quota_search = False
            quota_retry = False
            # Skip a model that recently hit its quota or has no free-tier
            # headroom left instead of spending a request on a guaranteed 429.
            usage_models = ((_llm_usage_today().get(provider) or {}).get('models') or {})
            if allow_fallback or fallback_on_quota:
                bucket = usage_models.get(current) or {}
                if (
                    _model_cooldown_remaining(provider, current) > 0
                    or _headroom_blocked(provider, current, bucket)
                    or not _model_fits_tokens(provider, current, bucket, estimated_tokens)
                ):
                    sibling = self._capacity_sibling(provider, api_key, current, [], use_tools, estimated_tokens)
                    if sibling:
                        print(f"  [SERVER] {current} has no capacity left, switching to {sibling}")
                        current = sibling
                        if fallback_on_quota:
                            quota_search = True
            while attempt < 4:
                bucket = usage_models.get(current) or {}
                fits_request = _model_fits_tokens(provider, current, bucket, estimated_tokens)
                if (allow_fallback or fallback_on_quota) and (
                    not fits_request
                    or _headroom_blocked(provider, current, bucket)
                    or _model_cooldown_remaining(provider, current) > 0
                ):
                    sibling = self._capacity_sibling(provider, api_key, current, tried, use_tools, estimated_tokens)
                    if sibling:
                        print(f"  [SERVER] {current} has no free-tier headroom, switching to sibling {sibling}")
                        current = sibling
                        if fallback_on_quota:
                            quota_search = True
                        if current not in tried:
                            tried.append(current)
                    else:
                        info = _model_headroom(provider, current, bucket) or {}
                        limits = info.get('limits') or {}
                        remaining = info.get('remaining') or {}
                        if not fits_request:
                            raise _LLMQuotaError(
                                f'This request needs about {estimated_tokens} tokens, above the '
                                f'{limits.get("tpm")} tokens/minute limit of {_normalize_model_name(current)}. '
                                'Pick a larger model or shorten the scene code.'
                            )
                        if limits.get('rpd') == 0 or remaining.get('rpd') == 0:
                            raise _LLMQuotaError(
                                f'{_normalize_model_name(current)} has no free-tier requests left today '
                                f'(RPD {limits.get("rpd") or 0}). Pick another model or wait for the daily reset.'
                            )
                        wait = _minute_wait_seconds(provider, current)
                        if wait > 0:
                            print(f"  [SERVER] waiting {wait}s for {current} per-minute window")
                            time.sleep(wait)
                tried.append(current)
                quota_retry = quota_search
                try:
                    if provider == 'mistral':
                        result = self._mistral_chat(api_key, messages, current, use_tools)
                    else:
                        result = self._gemini_chat(api_key, messages, current, use_tools)
                    text = str(result.get('text') or '').strip()
                    tool_calls = result.get('toolCalls') or []
                    rate = result.get('rateLimit') or _model_rate_state(provider, current)
                    _record_llm_usage(provider, current, purpose, result.get('usage'), 200,
                                      quota=None, rate=rate, estimated=estimated_tokens)
                    if text or tool_calls:
                        used_model = current
                        break
                    raise RuntimeError('Provider returned reasoning only with no text.')
                except urllib.error.HTTPError as exc:
                    detail = ''
                    try:
                        detail = exc.read().decode('utf-8', errors='replace')[:8000]
                    except Exception:
                        pass
                    rate = _record_rate_limits(provider, current, _rate_limits_from_headers(getattr(exc, 'headers', None)))
                    quota = _quota_details_from_error(detail) if provider == 'gemini' else {}
                    if provider == 'mistral' and exc.code == 429:
                        merged = rate or _model_rate_state(provider, current)
                        limit_req = int(merged.get('x-ratelimit-limit-req-minute') or 0)
                        if limit_req > 0:
                            quota = {'limit': limit_req, 'window': 'minute', 'type': 'requests'}
                    _record_llm_usage(provider, current, purpose, None, exc.code, 0, quota, rate, estimated_tokens)
                    # Some models on the list (e.g. gemma) reject tool schemas;
                    # retry the same model as plain text before any fallback.
                    if use_tools and exc.code == 400 and ('tool' in detail.lower() or 'function' in detail.lower()):
                        print(f"  [SERVER] {current} rejected tools, retrying without them")
                        use_tools = False
                        tools_dropped = True
                        continue
                    detail = detail[:600]
                    exc._clip_detail = detail
                    last_error = exc
                    if exc.code == 429:
                        # Free-tier quota is per model, so remember when this one
                        # frees up and let AUTO (or a manual pick with quota
                        # fallback) try a sibling model of the same provider.
                        delay = _retry_delay_seconds(detail, getattr(exc, 'headers', None)) or 60
                        _set_model_cooldown(provider, current, delay)
                        if fallback_on_quota:
                            quota_search = True
                        quota_retry = fallback_on_quota
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
                if not allow_fallback and not quota_retry:
                    break
                candidates = catalog
                if not candidates:
                    try:
                        candidates = self._catalog_models(provider, api_key)
                    except Exception:
                        break
                names = [str(cand.get('name', '')) for cand in candidates]
                models_by_name = {str(cand.get('name', '')): cand for cand in candidates}
                start = names.index(current) + 1 if current in names else 0
                ordered = names[start:] + names[:start]
                next_model = None
                for name in ordered:
                    if name in tried or _model_cooldown_remaining(provider, name) > 0:
                        continue
                    if use_tools and not models_by_name.get(name, {}).get('supportsTools', True):
                        continue
                    if _headroom_blocked(provider, name, usage_models.get(name) or {}):
                        continue
                    if not _model_fits_tokens(provider, name, usage_models.get(name) or {}, estimated_tokens):
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
                retry_seconds = _retry_delay_seconds(detail, getattr(exc, 'headers', None)) or _model_cooldown_remaining(provider, last_model)
                print(f"  [SERVER] {provider}/{last_model} quota exhausted for {_human_duration(retry_seconds) if retry_seconds else 'a while'}")
                last_bucket = (((_llm_usage_today().get(provider) or {}).get('models') or {}).get(last_model) or {})
                if last_bucket.get('limit'):
                    quota = {
                        'limit': int(last_bucket.get('limit') or 0),
                        'window': str(last_bucket.get('limitWindow') or 'day'),
                        'type': str(last_bucket.get('limitType') or 'requests'),
                        'quotaId': str(last_bucket.get('limitId') or ''),
                    }
                else:
                    quota = _quota_details_from_error(detail) if provider == 'gemini' else {}
                self._send_json({
                    'ok': False,
                    'error': _rate_limit_message(provider, last_model, retry_seconds, len(tried) > 1),
                    'detail': detail,
                    'retryAfterSeconds': retry_seconds,
                    'rateLimit': _model_rate_state(provider, last_model),
                    'quotaLimit': quota,
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
        except _LLMQuotaError as exc:
            print(f"  [SERVER] LLM quota block ({provider}): {exc}")
            self._send_json({'ok': False, 'error': str(exc)}, 429)
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

        used = used_model or requested_model
        used_bucket = (((_llm_usage_today().get(provider) or {}).get('models') or {}).get(used) or {})
        used_quota = {}
        if used_bucket.get('limit'):
            used_quota = {
                'limit': int(used_bucket.get('limit') or 0),
                'window': str(used_bucket.get('limitWindow') or 'day'),
                'type': str(used_bucket.get('limitType') or 'requests'),
                'quotaId': str(used_bucket.get('limitId') or ''),
            }
        self._send_json({
            'ok': True,
            'provider': provider,
            'model': used,
            'fallbackFrom': requested_model if used != requested_model else '',
            'text': text,
            'toolCalls': tool_calls,
            'tools': use_tools,
            'toolsDisabled': bool(tools_requested and tools_dropped),
            'rateLimit': _model_rate_state(provider, used),
            'quotaLimit': used_quota,
            'estimatedPromptTokens': estimated_tokens,
            'inputTokenLimit': _model_input_limit(catalog, used),
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

        usage_models = ((_llm_usage_today().get(provider) or {}).get('models') or {})
        for model in models:
            model_name = str(model.get('name', ''))
            model['cooldownSeconds'] = _model_cooldown_remaining(provider, model_name)
            model['callsToday'] = int(((usage_models or {}).get(model_name) or {}).get('calls') or 0)
            bucket = (usage_models or {}).get(model_name) or {}
            model['okToday'] = int(bucket.get('ok') or 0)
            state = _model_rate_state(provider, model_name)
            if state:
                model['rateLimit'] = state
            info = _model_headroom(provider, model_name, bucket)
            if info:
                model['limits'] = info['limits']
                model['headroom'] = info['remaining']
                model['limitsSource'] = info['source']
                if info.get('verifiedAt'):
                    model['limitsVerifiedAt'] = info['verifiedAt']
            if bucket.get('serviceTier'):
                model['serviceTier'] = bucket['serviceTier']
            output_cap = 16384
            try:
                if model.get('outputTokenLimit'):
                    output_cap = min(output_cap, int(model['outputTokenLimit']))
            except (TypeError, ValueError):
                pass
            model['maxOutputTokens'] = output_cap
            limit = int(bucket.get('limit') or 0)
            if limit > 0:
                window = str(bucket.get('limitWindow') or 'day')
                model['quotaLimit'] = {
                    'limit': limit,
                    'window': window,
                    'type': str(bucket.get('limitType') or 'requests'),
                    'quotaId': str(bucket.get('limitId') or ''),
                    'remaining': max(0, limit - model['okToday']) if window == 'day' else None,
                }
        self._send_json({'ok': True, 'models': models})

    def _handle_llm_usage(self):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        with _LLM_USAGE_LOCK:
            providers = _load_llm_usage().get(_usage_today(), {})
        if not isinstance(providers, dict):
            providers = {}
        for (cooldown_provider, cooldown_model), until in list(_MODEL_COOLDOWNS.items()):
            remaining = max(0, int(until - time.time()))
            if remaining <= 0:
                continue
            provider_bucket = providers.setdefault(cooldown_provider, {
                'calls': 0, 'ok': 0, 'promptTokens': 0, 'completionTokens': 0,
                'purposes': {}, 'models': {}
            })
            model_bucket = _usage_model_bucket(provider_bucket, cooldown_model)
            model_bucket['cooldownSeconds'] = remaining
        for provider_name, provider_bucket in providers.items():
            models = provider_bucket.get('models') if isinstance(provider_bucket, dict) else None
            for model_name, model_bucket in (models or {}).items():
                limit = int(model_bucket.get('limit') or 0)
                ok_today = int(model_bucket.get('ok') or 0)
                window = str(model_bucket.get('limitWindow') or 'day')
                model_bucket['remaining'] = max(0, limit - ok_today) if limit > 0 and window == 'day' else None
                live = _model_rate_state(provider_name, model_name)
                if live:
                    model_bucket['rateLimit'] = live
                info = _model_headroom(provider_name, model_name, model_bucket)
                if info:
                    model_bucket['limits'] = info['limits']
                    model_bucket['headroom'] = info['remaining']
                    model_bucket['limitsSource'] = info['source']
                    if info.get('verifiedAt'):
                        model_bucket['limitsVerifiedAt'] = info['verifiedAt']
        self._send_json({'ok': True, 'today': _usage_today(), 'usage': providers})

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

    def _handle_chatlog_get(self, query):
        if not self._same_origin_request():
            self.send_error(403, "Origin not allowed")
            return
        scope = query.get('projectId', [None])[0]
        if scope is not None:
            scope = str(scope)[:80]
        self._send_json({'ok': True, 'sessions': _load_chatlog(scope)})

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
        scope = None
        if 'projectId' in payload:
            scope = str(payload.get('projectId') or '')[:80]
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
        _save_chatlog(cleaned_sessions, scope)
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
    def _llm_http_post_raw(url, body, headers, timeout=180):
        request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
            return payload, response.headers

    @staticmethod
    def _llm_http_post(url, body, headers, timeout=180):
        payload, _headers = ClipACanvasHandler._llm_http_post_raw(url, body, headers, timeout=timeout)
        return payload

    @staticmethod
    def _llm_http_get(url, headers, timeout=30):
        request = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))

    def _catalog_models(self, provider, api_key):
        cached = _MODEL_CATALOG.get(provider)
        if cached and time.time() - cached.get('at', 0) < _MODEL_CATALOG_TTL:
            return list(cached.get('models') or [])
        models = self._mistral_models(api_key) if provider == 'mistral' else self._gemini_models(api_key)
        _MODEL_CATALOG[provider] = {'at': time.time(), 'models': models}
        return models

    def _capacity_sibling(self, provider, api_key, current, tried, use_tools, need_tokens=0):
        try:
            models = self._catalog_models(provider, api_key)
        except Exception:
            return None
        usage_models = ((_llm_usage_today().get(provider) or {}).get('models') or {})
        candidates = []
        for model in models:
            name = str(model.get('name') or '')
            if not name or name == current or name in tried:
                continue
            if use_tools and not model.get('supportsTools', True):
                continue
            if _model_cooldown_remaining(provider, name) > 0:
                continue
            bucket = usage_models.get(name) or {}
            if _headroom_blocked(provider, name, bucket):
                continue
            if need_tokens:
                if not _model_fits_tokens(provider, name, bucket, need_tokens):
                    continue
                context_limit = int(model.get('inputTokenLimit') or 0)
                if context_limit and need_tokens + 16384 > context_limit:
                    continue
            calls = int(bucket.get('calls') or 0)
            candidates.append((calls, name))
        current_tier = _model_tier(provider, current)
        same_tier = [item for item in candidates if _model_tier(provider, item[1]) == current_tier]
        if same_tier:
            candidates = same_tier
        elif current_tier == 'pro':
            flash = [item for item in candidates if _model_tier(provider, item[1]) == 'flash']
            if flash:
                candidates = flash
        candidates.sort()
        return candidates[0][1] if candidates else None

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
                'supportsTools': True,
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

        body = {'contents': contents, 'generationConfig': {'maxOutputTokens': 16384}}
        if system_parts:
            body['systemInstruction'] = {'parts': [{'text': '\n\n'.join(system_parts)}]}
        if tools:
            body['tools'] = [{'functionDeclarations': _gemini_tool_declarations()}]

        model_name = str(model).strip()
        if model_name.startswith('models/'):
            model_name = model_name[len('models/'):]

        url = f'https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model_name)}:generateContent?key={urllib.parse.quote(api_key)}'
        data, response_headers = self._llm_http_post_raw(url, body, {'Content-Type': 'application/json'}, timeout=150)
        rate = _record_rate_limits('gemini', model, _rate_limits_from_headers(response_headers))
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
        meta = data.get('usageMetadata') if isinstance(data.get('usageMetadata'), dict) else {}
        usage = {
            'prompt': int(meta.get('promptTokenCount') or 0),
            'completion': int(meta.get('candidatesTokenCount') or 0) + int(meta.get('thoughtsTokenCount') or 0),
            'total': int(meta.get('totalTokenCount') or 0),
            'serviceTier': str(meta.get('serviceTier') or response_headers.get('X-Gemini-Service-Tier') or ''),
        }
        return {'text': ''.join(texts).strip(), 'toolCalls': tool_calls, 'usage': usage, 'rateLimit': rate}

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

        body = {'model': model, 'messages': converted, 'max_tokens': 16384}
        if tools:
            body['tools'] = _mistral_tool_declarations()
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        data, response_headers = self._llm_http_post_raw('https://api.mistral.ai/v1/chat/completions', body, headers, timeout=150)
        rate = _record_rate_limits('mistral', model, _rate_limits_from_headers(response_headers))
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
        meta = data.get('usage') if isinstance(data.get('usage'), dict) else {}
        usage = {
            'prompt': int(meta.get('prompt_tokens') or 0),
            'completion': int(meta.get('completion_tokens') or 0),
            'total': int(meta.get('total_tokens') or 0),
            'serviceTier': str(meta.get('service_tier') or ''),
        }
        return {'text': text, 'toolCalls': tool_calls, 'usage': usage, 'rateLimit': rate}

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
            capabilities = entry.get('capabilities') if isinstance(entry.get('capabilities'), dict) else {}
            models.append({
                'name': model_id,
                'displayName': model_id,
                'description': str(entry.get('description') or ''),
                'inputTokenLimit': entry.get('max_context_length'),
                'outputTokenLimit': None,
                'supportsTools': bool(capabilities.get('function_calling')),
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
            # A content save must never duplicate another project's name; keep
            # the stored name and let the rename endpoint report collisions.
            if _project_name_taken(entries, display, exclude_id=project_id):
                display = str(entry.get('name') or display)
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
        if body.get('dedupe'):
            display = _unique_project_display(display, entries)
        elif _project_name_taken(entries, display):
            return self._send_json(
                {'ok': False, 'error': f'A project named "{display}" already exists. Choose another name.'},
                409,
            )
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
        if _project_name_taken(entries, name, exclude_id=project_id):
            return self._send_json(
                {'ok': False, 'error': f'A project named "{name}" already exists. Choose another name.'},
                409,
            )
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
        autosave = _read_json_path(_project_autosave_path(project_id))
        if isinstance(autosave, dict) and _validate_project_doc(autosave):
            autosave = None
        # Opening must land on the newest state. The library copy is only
        # written on save/return Home while the per-project autosave follows
        # every edit, so a stale library copy must never shadow it.
        saved_at = str((doc or {}).get('savedAt') or '')
        autosave_at = str((autosave or {}).get('savedAt') or '')
        recovered = isinstance(autosave, dict) and (
            doc is None
            or (bool(autosave_at) and (not saved_at or autosave_at > saved_at))
        )
        if recovered:
            doc = autosave
        if doc is None:
            return self._send_json({'ok': False, 'error': 'Project file could not be read.'}, 500)
        self._send_json({'ok': True, 'project': doc, 'entry': _project_entry_meta(entry), 'recovered': recovered})

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
        refresh = (payload or {}).get('refresh') is True
        filename = Path(urllib.parse.unquote(url[len('/media/'):])).name
        try:
            manifest = analyze_media_file(filename, refresh=refresh)
        except FileNotFoundError:
            return self._send_json({'ok': False, 'error': 'Media file not found.'}, 404)
        except ValueError:
            return self._send_json({'ok': False, 'error': 'Unknown media file.'}, 400)
        except Exception as exc:
            print(f"  [SERVER] analysis error: {exc}")
            return self._send_json({'ok': False, 'error': 'Media analysis failed.'}, 500)
        self._send_json({'ok': True, 'manifest': manifest})

    def _handle_media_search(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > 65536:
            return self._send_json({'ok': False, 'error': 'Invalid search request.'}, 400)
        try:
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return self._send_json({'ok': False, 'error': 'Invalid JSON.'}, 400)
        query = str((payload or {}).get('query') or '').strip()
        if not query or len(query) > 300:
            return self._send_json({'ok': False, 'error': 'Write a query between 1 and 300 characters.'}, 400)
        try:
            limit = int((payload or {}).get('limit') or VISUAL_SEARCH_LIMIT)
        except (TypeError, ValueError):
            limit = VISUAL_SEARCH_LIMIT
        limit = max(1, min(24, limit))
        try:
            message = _embedding_request({'kind': 'text', 'texts': [query], 'prompt': 'Retrieval-query'})
        except Exception as exc:
            print(f"  [SERVER] footage search failed: {exc}")
            return self._send_json({
                'ok': False,
                'error': f'Local search is unavailable: {str(exc)[:200]}'
            }, 502)
        vectors = message.get('vectors') or []
        query_vector = vectors[0] if vectors and isinstance(vectors[0], list) else []
        if not query_vector:
            return self._send_json({'ok': False, 'error': 'Local search returned no vector.'}, 500)
        results = []
        for sidecar in _analysis_dir().glob('embeddings-*.json'):
            try:
                data = json.loads(sidecar.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            filename = str(data.get('filename') or '')
            if not MEDIA_NAME_RE.match(filename):
                continue
            for frame in data.get('frames') or []:
                if not isinstance(frame, dict):
                    continue
                vector = frame.get('vector') or []
                if not isinstance(vector, list) or len(vector) != len(query_vector):
                    continue
                try:
                    score = sum(float(a) * float(b) for a, b in zip(query_vector, vector))
                except (TypeError, ValueError):
                    continue
                if score < VISUAL_SEARCH_MIN_SCORE:
                    continue
                thumb = str(frame.get('thumb') or '')
                if not thumb.startswith('/api/media/frames/'):
                    thumb = ''
                results.append({
                    'filename': filename,
                    'url': f'/media/{filename}',
                    'time': round(float(frame.get('time') or 0), 3),
                    'score': round(score, 4),
                    'thumb': thumb,
                })
        results.sort(key=lambda item: -item['score'])
        # Collapse neighbouring frames from the same moment so a result list is
        # distinct moments, not the same second repeated.
        picked = []
        for item in results:
            if any(prev['filename'] == item['filename']
                   and abs(prev['time'] - item['time']) < 1.5
                   for prev in picked):
                continue
            picked.append(item)
            if len(picked) >= limit:
                break
        results = picked
        self._send_json({
            'ok': True,
            'query': query,
            'model': VISUAL_MODEL,
            'count': len(results),
            'results': results,
        })

    def _handle_analysis_frame(self, raw_name):
        name = urllib.parse.unquote(raw_name)
        match = re.match(r"^([^/]+)/(?:(shot|index)-(\d{1,3})|(\d{1,2}))\.jpg$", name)
        if not match or not MEDIA_NAME_RE.match(match.group(1)):
            return self._safe_text_error('Frame not found.', 404)
        frame_dir = _analysis_dir() / f"frames-{Path(match.group(1)).stem}"
        if match.group(2):
            frame_path = frame_dir / f"{match.group(2)}-{int(match.group(3)):02d}.jpg"
        else:
            frame_path = frame_dir / f"shot-{int(match.group(4)):02d}.jpg"
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

    def _handle_stt_status(self):
        try:
            self._send_json({'ok': True, **_stt_live_status()})
        except Exception as exc:
            print(f"  [SERVER] STT status error: {exc}")
            self._send_json({'ok': False, 'error': 'Could not read dictation status.'}, 500)

    def _handle_stt_prepare(self):
        self._discard_request_body()
        try:
            with _STT_LOCK:
                _ensure_stt_worker()
                response = _stt_request({"op": "prepare"}, timeout=120)
            self._send_json({
                'ok': True,
                'state': str(response.get('state') or 'loading'),
                'model': _stt_model_id(),
                'modelReady': _stt_model_ready() or response.get('state') == 'ready',
            })
        except queue.Empty:
            _STT_WORKER.stop()
            self._send_json({'ok': False, 'error': 'The dictation engine did not respond.'}, 504)
        except (RuntimeError, OSError) as exc:
            self._send_json({'ok': False, 'error': str(exc)}, 502)

    def _handle_stt_warm(self):
        self._discard_request_body()
        _, _assets, error = _stt_locate()
        if error:
            return self._send_json({'ok': False, 'error': error}, 502)

        def boot():
            try:
                with _STT_LOCK:
                    _ensure_stt_worker()
            except (RuntimeError, OSError) as exc:
                print(f"  [SpeechToText] warm-up failed: {exc}")

        if not _STT_WORKER.alive():
            threading.Thread(target=boot, name="speech-to-text-warm", daemon=True).start()
        self._send_json({'ok': True, 'warming': not _STT_WORKER.alive()})

    def _handle_stt_start(self):
        self._discard_request_body()
        try:
            with _STT_LOCK:
                _stt_update(phase="preparing", error="",
                            progress={"stage": "boot", "pct": 0, "detail": "Starting dictation engine"})
                _ensure_stt_worker()
                # Open the microphone before touching the model: PortAudio's
                # stream open blocks while CUDA model loading runs.
                response = _stt_request({"op": "record_start"}, timeout=60)
                if not response.get("ok"):
                    message = str(response.get("error") or "The microphone is unavailable.")
                    _stt_update(phase="idle", error=message)
                    return self._send_json({'ok': False, 'error': message}, 502)
                started = time.time()
                input_name = str(response.get("input") or "")
                _stt_update(phase="recording", startedAt=started, error="", peak=0.0, input=input_name)

            def prime_model():
                time.sleep(0.5)
                with _STT_LOCK:
                    if not _STT_WORKER.alive():
                        return
                    try:
                        _stt_request({"op": "prepare"}, timeout=60)
                    except (queue.Empty, OSError):
                        pass

            threading.Thread(target=prime_model, name="speech-to-text-prime", daemon=True).start()
            self._send_json({
                'ok': True,
                'recording': True,
                'startedAt': started,
                'input': input_name,
                'maxSeconds': STT_MAX_RECORD_SECONDS,
            })
        except queue.Empty:
            _STT_WORKER.stop()
            _stt_update(phase="idle", error="The dictation engine did not respond.")
            self._send_json({'ok': False, 'error': 'The dictation engine did not respond.'}, 504)
        except (RuntimeError, OSError) as exc:
            _stt_update(phase="idle", error=str(exc))
            self._send_json({'ok': False, 'error': str(exc)}, 502)

    def _handle_stt_stop(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        payload = {}
        if 0 < length <= 20000:
            try:
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        output = _stt_dir() / f"dictation-{uuid.uuid4().hex}.wav"
        try:
            with _STT_LOCK:
                if not _STT_WORKER.alive():
                    _stt_update(phase="idle")
                    return self._send_json({'ok': False, 'error': 'Dictation is not recording.'}, 409)
                _stt_update(phase="transcribing", error="",
                            progress={"stage": "transcribe", "pct": 0, "detail": "Transcribing"})
                capture = _stt_request({"op": "record_stop", "out": str(output)}, timeout=60)
                if not capture.get("ok"):
                    message = str(capture.get("error") or "Could not stop the recording.")
                    _stt_update(phase="idle", error=message)
                    return self._send_json({'ok': False, 'error': message}, 502)
                duration = float(capture.get("duration") or 0)
                if duration < 0.35:
                    _stt_update(phase="idle", progress={"stage": "ready", "pct": 100, "detail": "Ready"})
                    return self._send_json({'ok': False, 'error': 'That recording was too short to transcribe.'}, 400)
                result = _stt_request(
                    {"op": "transcribe", "audio": str(output), "language": "en"},
                    timeout=1800,
                )
                if not result.get("ok"):
                    message = str(result.get('error') or 'Transcription failed.')
                    _stt_update(phase="idle", error=message)
                    return self._send_json({'ok': False, 'error': message}, 502)
                text = ' '.join(str(result.get('text') or '').split())
                _stt_update(phase="idle", progress={"stage": "ready", "pct": 100, "detail": "Ready"})
                if not text or result.get('silent'):
                    return self._send_json({
                        'ok': True, 'text': '', 'silent': True,
                        'duration': round(float(result.get('duration') or duration), 2),
                    })
                _stt_update(lastText=text)
                self._send_json({
                    'ok': True,
                    'text': text,
                    'duration': round(float(result.get('duration') or duration), 2),
                    'confidence': result.get('confidence'),
                    'language': 'en',
                    'model': _stt_model_id(),
                    'device': _stt_snapshot().get('device') or '',
                })
        except queue.Empty:
            _STT_WORKER.stop()
            _stt_update(phase="idle", error="Transcription timed out.")
            self._send_json({'ok': False, 'error': 'Transcription timed out. Try a shorter sentence.'}, 504)
        except (RuntimeError, OSError) as exc:
            _stt_update(phase="idle", error=str(exc))
            self._send_json({'ok': False, 'error': str(exc)}, 502)
        finally:
            output.unlink(missing_ok=True)

    def _handle_stt_cancel(self):
        self._discard_request_body()
        with _STT_LOCK:
            if _STT_WORKER.alive():
                try:
                    _stt_request({"op": "record_cancel"}, timeout=10)
                except (queue.Empty, OSError):
                    pass
            _stt_update(phase="idle", error="",
                        progress={"stage": "", "pct": 0, "detail": ""})
        self._send_json({'ok': True})

    def _handle_stt_transcribe(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > STT_MAX_AUDIO_BYTES:
            return self._send_json({'ok': False, 'error': 'Send an audio file up to 40 MB.'}, 400)
        raw = self.rfile.read(length)
        if len(raw) < 64:
            return self._send_json({'ok': False, 'error': 'The audio payload is empty.'}, 400)
        output = _stt_dir() / f"upload-{uuid.uuid4().hex}.wav"
        output.write_bytes(raw)
        try:
            with _STT_LOCK:
                _stt_update(phase="transcribing", error="",
                            progress={"stage": "transcribe", "pct": 0, "detail": "Transcribing"})
                _ensure_stt_worker()
                result = _stt_request(
                    {"op": "transcribe", "audio": str(output), "language": "en"},
                    timeout=1800,
                )
                _stt_update(phase="idle", progress={"stage": "ready", "pct": 100, "detail": "Ready"})
                if not result.get("ok"):
                    raise RuntimeError(str(result.get('error') or 'Transcription failed.'))
                text = ' '.join(str(result.get('text') or '').split())
                self._send_json({
                    'ok': True,
                    'text': text,
                    'silent': bool(result.get('silent')),
                    'duration': float(result.get('duration') or 0),
                    'confidence': result.get('confidence'),
                    'language': 'en',
                    'model': _stt_model_id(),
                })
        except queue.Empty:
            _STT_WORKER.stop()
            _stt_update(phase="idle", error="Transcription timed out.")
            self._send_json({'ok': False, 'error': 'Transcription timed out.'}, 504)
        except (RuntimeError, OSError, ValueError) as exc:
            _stt_update(phase="idle", error=str(exc))
            self._send_json({'ok': False, 'error': str(exc)}, 400)
        finally:
            output.unlink(missing_ok=True)


    def _discard_request_body(self, limit=20000):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            length = 0
        if 0 < length <= limit:
            try:
                self.rfile.read(length)
            except OSError:
                pass

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
    _load_model_cooldowns()
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
