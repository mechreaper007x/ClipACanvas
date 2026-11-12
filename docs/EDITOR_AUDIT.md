# Clip.A.Canvas — Milestone 0 Architecture Audit

Date: 2026-11-12
Branch: `main`
Baseline: `main` at `b8addc5`; the speech/audio work described in the Phase 3 addendum is uncommitted at the time of writing.

## Addendum — Phase 4 (semantic asset intelligence)

Verified in the working tree on 2026-11-12, after `5fb33dd`.

### What is implemented

- **Local shot detection (offline):** FFmpeg's scene score (threshold 0.3, 320px analysis scale) scans the first 180 seconds of a video; the manifest (`analyzer.version` 2) stores up to 24 shot boundaries as `shots[]` with `start`, `end` and, for the first 12, a keyframe URL. Keyframes are 640px JPEGs extracted into the app-data analysis cache and served read-only at `GET /api/media/frames/<filename>/<n>.jpg`. Images and audio have no shots. Old manifests (v1) rebuild on first use, and project assets refresh automatically because the frontend requires analyzer version 2.
- **Provider registry:** `GET /api/media/semantic/providers` lists Gemini with live availability (API key present), the verified model (`gemini-2.5-flash`), vision/transcript capabilities, the inline upload cap and a plain-language terms string.
- **Consent-gated analysis:** `POST /api/media/semantic` rejects any request without `consent: true` (403). It sends at most 6 local keyframe JPEGs (an image is downscaled to one still), plus audio only if transcription was requested: audio assets must be mp3/wav/flac and under 19 MB; video audio is extracted locally to mono 24 kHz mp3 and capped at 5 minutes. The request uses the Gemini Interactions API (`/v1beta/interactions`) with a JSON `response_format.schema`; results are sanitized and merged into the manifest, preserving the user block. Provider failures return explicit 403/400/404/502 errors — there is no silent fallback or automatic upload.
- **Inspector:** the CONTENT block shows the shot strip with timestamps and previews, AI tags, description and transcript, and the analyzed provider/model/frame count. ANALYZE CONTENT opens a consent panel that states exactly what is uploaded, requires an explicit checkbox and hides until a provider is available. A USER NOTE editor saves a human-confirmed description separately from AI fields; notes survive re-analysis and reload.
- **Agent access:** `get_asset_analysis` returns the shot list and semantic fields; `search_assets` matches AI tags, subjects and transcript text in addition to names and human notes. The system prompt requires the agent to say "not analyzed" instead of inventing content, and no agent tool can start an upload.

### Limitations

- Shot detection covers only the first 180 seconds and keeps at most 24 boundaries / 12 previews. FFmpeg's scene metric can miss cuts between flat colors (verified: solid red→green→blue clips) while detecting textured footage reliably.
- Hosted analysis was contract-tested against the documented Interactions API with a stubbed transport; no live Gemini call was made during verification because no hosted key was configured. The exact request body, response parsing, consent gate and error mapping are covered by tests.
- Gemini is the only semantic provider. Transcript timestamps are model estimates (no word-level alignment), video transcription covers the first 5 minutes, and transcripts are read-only.
- Shots and semantic data persist with the project in localStorage; there is still no project file format.

## Addendum — Phase 3 (speech generation and audio mix)

Verified in the working tree on 2026-11-12.

### What is implemented

- **Provider registry:** `GET /api/tts/providers` reports three providers with live availability. `sapi` is the local Windows `System.Speech` engine (offline, no download, voices enumerated from the OS and cached five minutes). `gemini` uses the Gemini TTS Interactions API; `mistral` uses the Voxtral `/v1/audio/speech` endpoint. Each entry carries supported formats, capability flags (`speed`, `style`, `emotion`, `voiceCloning`, `streaming`) and a plain-language terms string shown in the UI. Hosted providers are marked unavailable with a reason until their key exists in the backend key store.
- **Synthesis endpoint:** `POST /api/tts/generate` validates text (1–4000 chars), provider availability, model, voice, format, speed (0.5–2 where supported) and style. SAPI runs a PowerShell `System.Speech` script offline with the requested rate. Gemini sends the script plus optional `speech_metadata` style and reads base64 `output_audio`. Mistral sends `model`/`input`/`voice_id`/`response_format`/`stream` and reads `audio_data`. Keys stay in the existing backend key store; the frontend never receives them.
- **Caching:** SHA-256 over the canonical request (version, provider, model, voice, format, speed, style, text) keyed under `%APPDATA%/ClipACanvas/tts`. A repeat request returns the existing media file without calling the provider. Audio is stored as a normal content-hashed `/media` asset, probed with the bundled FFmpeg for duration/sample rate/channels, and recorded with provider, voice and terms provenance.
- **Voiceover Studio:** right-pane `VOICE` tab with script (selection pre-fills), character count, provider/model/voice/format/speed/style/target controls, an explicit hosted-provider consent line, generate action, status, audio preview, and insertion at the playhead on the chosen lane (`A1` default, `A2`/`A3` optional) or into the bin.
- **Audio mix:** `A1 VOICEOVER` / `A2 MUSIC` / `A3 SFX` are persisted in `timelineState.audioTracks` with `mute`, `solo` and `volume` (0–2). Audio clips carry `audioTrack`. The inspector exposes lane assignment and per-lane mix rows; the timeline shows lane tags on audio clips. Export and hosted renders carry `audioTrack` plus gain, the renderer applies FFmpeg `volume=` and honors mute/solo (any solo lane suppresses non-solo lanes; muted or zero-gain clips are skipped).
- Generated and imported speech use the existing `/media`, bin, timeline, composite preview and export paths; no parallel pipeline was added.

### Limitations

- Hosted providers were implemented against the official documentation (Gemini Interactions API; Mistral `audio/speech` reference) but no live hosted call was made during verification because no hosted key was configured. Failures surface explicit provider errors (502) instead of silently falling back to another provider.
- Mistral Voxtral is exposed with preset voices only; cloning needs a reference-audio upload and is not exposed. Speed/style controls hide for providers that do not support them.
- SAPI voice quality depends on installed Windows voices; UI speed maps onto the engine's rate scale.
- Audio lanes are logical (`clip.audioTrack` + mix); clips still sit visually on the V1–V4 rows with `A1`–`A3` tags, and there are no typed audio lanes or lane heights yet.
- Voiceover Studio generates whole scripts or the selected text; there is no per-paragraph regeneration, scrubbing preview, or TTS agent tool yet.

## Addendum — Phase 2 (transition engine)

Verified in the working tree on 2026-11-12.

### What is implemented

- **Project model:** `timelineState.transitions` (max 40) persisted inside `clipacanvas.timeline.v1`. Each record: `id`, `fromClipId`, `toClipId`, `type`, `duration`, `alignment` (`center|start|end`), `params` (`direction`, `color`, `intensity`), `code` (custom only), `version`. Transitions are saved on a cut, survive reload, and are pruned when their clips disappear, stop touching, or the window overlaps another transition on the same track.
- **Deterministic contract:** one engine (`ccTransitionRuntime` in `clipacanvas.html`) is embedded verbatim in the Program Monitor composite and in the Playwright sequence document. It receives normalized progress plus clip timing and returns declarative surface styles; there are no timers, wall-clock reads, or randomness (glitch jitter uses a `sin` hash of progress). The incoming surface is forced above the outgoing one, so same-track cuts composite correctly.
- **Preset library (13):** dissolve, fade-black, fade-white, dip-color, wipe, push, slide, zoom-in, zoom-out, zoom-blur, glitch, rgb-split, blur-dissolve. Direction, dip color and intensity are configurable; each preset is exercised by tests.
- **Custom transitions:** `type: "custom"` plus code declaring `function renderTransition(ctx)` returning `{outgoing, incoming, overlay}` CSS styles (`opacity`, `transform`, `filter`, `clipPath`, `backgroundColor`, `mixBlendMode`). Code is length-limited, deny-listed (`fetch`, DOM/window access, loops, `eval`, etc.), and only compiled inside the sandboxed preview page or the Playwright page — never in the app window. Invalid code is rejected at add/update time; a runtime failure falls back to a dissolve inside the isolated page.
- **Boundary handling:** transitions require two clips touching on one track and no longer than either clip. Video clips are checked for real footage handles: outgoing needs `d/2` (center), `d` (start) or 0 (end) past its out point; incoming needs the matching pre-roll before its in point. Violations return explicit errors instead of corrupting timing.
- **UI:** `TRANSITION` toolbar action + a dialog (type, duration, alignment, direction, color, intensity, custom code, remove). Cut badges open the dialog; preview jumps to the transition midpoint and uses the Program Monitor. Preview playback posts time into the composite page so the blend animates without reloading layers.
- **Agent tools:** `add_transition`, `update_transition`, `remove_transition` through `projectOps`; `timelineSummaryForChat` and `get_clip_context` include transitions. The system prompt documents the presets and the custom contract.

### Limitations

- Custom transitions return CSS effects on the composited surfaces; they cannot rasterize the outgoing/incoming frames into per-pixel shaders without a new capture path (html2canvas-class or canvas readback), which was intentionally not added.
- The Program Monitor composites live layers during playback, so child compositions are not seeked to an exact local time mid-transition; the blend math is identical to the export, which seeks every frame deterministically.
- No transition keyboard shortcut and no drag-to-resize on the badge yet.
- MCP/TUI renderer copies do not forward transitions; only the desktop `/render` path does.

## Addendum — Phase 0 (AI-native directive: compositing, transitions, asset intelligence, TTS, zoom)

Verified against the working tree on 2026-11-12, after `bb4772c`.

### Feature-by-feature state

**Video compositing and overlays**
- Implemented: layered tracks (V1–V4), independent image/video/code clips, per-clip media wrappers, drag/insert/drop overlay policy, Program Monitor composite, deterministic iframe layering in the export (z-index by track).
- Implemented this phase: `parentClipId` in the project model with sanitize/resolve on load, `projectOps.attachOverlay`/`detachOverlay`/`getClipContext`, predictable overlay shifts when a parent moves or its in-point is trimmed, detach on parent delete, and agent tools `create_overlay`/`update_overlay`/`delete_overlay`/`attach_overlay`/`detach_overlay`/`get_clip_context`.
- Not implemented: object tracking (explicitly out of scope and not claimed), UI buttons for attachment (operations are available to the agent/API), overlay transforms/keyframes.
- Dependencies/risks: same-track overlap rules apply; an overlay must sit on a higher track than its parent; chain attachment is rejected; split leaves attached children with the left half.

**Transitions**
- Implemented at Phase 0 time: nothing beyond hard cuts; each clip's iframe started independently.
- Implemented in Phase 2: transition records on cuts, deterministic preview/export engine, 13-preset library, custom `renderTransition(ctx)` code, video handle checks, timeline badges/dialog, agent tools. See the Phase 2 addendum.
- Remaining: custom transitions cannot rasterize per-pixel source frames; MCP/TUI paths do not forward transitions.

**Asset intelligence**
- Implemented this phase: `/api/media/analyze` probes stored media with the bundled FFmpeg (duration, resolution, fps, codecs, sample rate, channels, streams, bytes), writes a cached manifest keyed by content hash under `%APPDATA%/ClipACanvas/analysis`, and returns an explicit `semantic.status: "not_analyzed"` record with empty subjects/tags/shots/transcript. The inspector shows the technical block; the asset record persists the manifest; agent tools `search_assets`, `get_asset_analysis`, `update_asset_description` expose concise summaries and human-confirmed notes separately from AI fields.
- Not implemented: visual/semantic analysis, shot segmentation, keyframe extraction, transcription, provider selection/consent, user-facing description editor.
- Dependencies/risks: no media bytes leave the machine in this phase; FFmpeg's input probe is used because FFprobe is not bundled; image fps is suppressed because FFmpeg reports a nominal 25 fps for stills.

**Text-to-speech**
- Implemented: nothing. No provider abstraction or audio-track semantics exist yet.
- Required next: `TTSProvider` interface and capability registry, local provider detection on the target hardware, at least one verified local and one verified hosted provider using official documentation, cache keyed by text/model/voice/language/speed, Voiceover Studio, A1/A2/A3 track semantics.
- Risks: model weights/licences and memory limits on a 16 GB / GTX 1650 laptop; API endpoints must be verified, never invented; keys must stay behind the existing backend key store.

**Timeline zoom and precision**
- Implemented before this phase: zoom 1–8×, wheel zoom anchored at the pointer, playhead-anchored zoom buttons, horizontal scroll, fit, 5-mark ruler.
- Implemented this phase: percent control with the required 100/125/150/200/250/300/400/600/800 presets, a 100–800 slider (step 5), direct numeric entry, playhead-anchored zoom, and control sync with wheel/buttons/FIT. Tested at 1664×916 and 1280×720 without document overflow.
- Not implemented: frame/tick timebase, frame stepping; edits remain float-seconds rounded at 0.01–0.1 s boundaries. Not claimed as frame-accurate.

### Implementation plan and status

| Phase | Item | Status |
|-------|------|--------|
| 1 | Technical asset metadata + cached manifest | Done |
| 1 | Structured asset access for the agent | Done (`search_assets`, `get_asset_analysis`, `update_asset_description`) |
| 1 | Explicit overlay relationships | Done (model, ops, inspector, agent tools) |
| 1 | Transition data structures and execution contract | Done (see Phase 2 addendum) |
| 1 | TTS provider abstraction | Deferred (no provider verified yet) |
| 1 | Improved zoom configuration | Done (presets, slider, numeric entry, anchoring) |
| 2 | Transition library + generated transitions + overlay UI | Transitions + custom transitions done; overlay attachment UI still deferred |
| 2 | Voiceover Studio + local/hosted TTS | Not started |
| 3 | Semantic/visual/audio asset analysis | Done (local shots + keyframes; consent-gated Gemini vision/transcript) |
| 4 | Full workflow validation + project persistence of all new objects | Partial: overlays, analysis and transitions persist; TTS absent |

### Dependencies and licensing notes

No new runtime dependencies were added. Asset probing reuses the bundled FFmpeg; analysis caching uses JSON files under the existing app data directory. TTS model weights, if added, will require explicit licence review before bundling.

### Limitations of this phase

- WebView2 coverage added for the new zoom controls, analysis inspector, overlay attachment and the transition dialog/preview/export (`_check_webview_transitions.py`).
- The project timeline remains localStorage-only; analysis and `parentClipId` persist with it, but there is no project file/export yet.
- No performance regression was measured for the extra analysis call; probing is local and runs once per content hash.

## 1. What is already implemented

### Frontend shell (clipacanvas.html, 12.6k lines)
- Compact top bar with project name (localStorage `clipacanvas.projectName`), SAVED/EDITING state, DOWNLOAD, EXPORT, layout reset, settings, history (`:3851-3900`, `:10983-11010`).
- Left panel `PROJECT | CODE`: project bin + scene list in PROJECT; Monaco in CODE (`:3861`, `:11671-11868`).
- Centre Program Monitor with aspect-correct stage, transport play/pause, timecode, FPS label, FIT, fullscreen (`:3900-3948`).
- Right panel `INSPECTOR | CLIPPPA | RECIPE` (`:3960-4140`).
- Full-width timeline in the bottom dock: ruler, playhead, V1–V4 rows, zoom, horizontal scroll, toolbar (`:4100-4330`, `:9959-10069`).
- Splitters and persisted panel sizes via `/api/prefs` (`serve.py:606-620`).

### Project bin and media
- Import images/video/audio through `/api/media` (content-hashed names, 200 MB cap) (`serve.py:1751-1806`).
- Bin cards with real 16:9 art, kind badge, duration, select/inspect, + insert at playhead, double-click insert.
- Pointer-based bin→timeline drag with ghost, lane highlight, marker time, overlay policy and rejection of full tracks (`clipacanvas.html:10760-10810`, `:11185-11340`); verified in real WebView2 (`tests/_check_webview_dragdrop.py`).
- Bin→stage drag embeds media inside the selected scene (`embedAssetInScene`; `tests/_check_scene_embed.py`).
- Audio waveforms come from real `decodeAudioData` peaks, cached per asset (`:11774-11827`).

### Timeline model and editing
- `timelineState {clips, activeId, layers, assets, playhead, selectedAssetId, draggingId}` persisted to `localStorage['clipacanvas.timeline.v1']` with sanitize/clamp on load (`:8974-9314`).
- Clips: code, image, video, audio; per-clip `code`, `duration`, `start`, `track`, `explicitDuration`, `assetId`, `mediaUrl`, `sourceIn`, `fit`.
- Add scene (`createSceneClip`), duplicate/blank add (`addLogicClip`), move between tracks with clash rejection, trim left/right with media `sourceIn` handling, split (`splitAtPlayhead`/`splitClipRecord`), ripple delete, rename, snapping (`snapTimelineEdge`), 40-clip/4-layer caps (`:10118-10670`, `:11403-11538`).
- Timeline zoom/scroll view model `timelineView {zoom,start}` with time↔pixel mapping (`:10640-10712`).
- Clip visuals: type classes, image thumbnails, real audio waveform, names/durations.

### Preview and playback
- Composite Program Monitor: `buildCompositePreview`/`renderCompositePreview` build a layered iframe document for clips at the playhead (`:9328-9374`), cached by `playbackClipKey` and refreshed only at clip/bucket boundaries (`:9424-9435`, `:10854-10900`).
- rAF playback clock advances the playhead; Space relay from sandboxed frames; timecode `HH:MM:SS:FF`; arrows step ±0.1 s / ±1 s (`:10875-11040`, `:11666-11669`).
- Deterministic renderer: `build_sequence_document()` overlays one iframe per clip with `z-index=track+1`, mocks `Date`/`performance.now`, queues timers, pauses WAAPI and seeks via `__clipacanvasSetTime` (`playwright_render.py:85-458`).

### Export
- Frontend builds `/render` payload (resolution, fps, codec, bitrate, frame range, clips, audio) and POSTs synchronously; Python streams PNG/JPEG frames over a pipe to FFmpeg, muxes audio with `atrim/asetpts/adelay/amix`, probes NVENC/QSV/AMF (`serve.py:951-1040`, `playwright_render.py:599-731`).
- GPU boost path renders via CDP JPEG; thumbnails are polled separately for progress; export verified by pixel probes in several suites.

### AI and integrations
- Chat with provider/model selection, tool calls (`get_app_state`, `set_export_settings`, `insert_animation_code`, `add_scene`, `render_video`), settings gating, code verification turn, chat SQLite with migration (`clipacanvas.html:6780-6850`, `:8288-8450`; `serve.py:642-829`).
- MCP STDIO/SSE servers expose `render_video` / `render_video_to_file` through an in-process renderer; TUI exists under `tui/`.
- Desktop shell uses pywebview with a loopback random-port server, native save/open dialogs, bundled browser/FFmpeg resolution (`desktop_app.py:170-243`).

### Tests
- 20+ Playwright/Python suites including workspace layout, timeline CRUD, media timing, overlays, scene embeds, audio mix, chat scenes, render matrices, packaged exe smoke, and the WebView2 drag test. See `tests/` and the section below.

## 2. Partially implemented

- **Track presentation:** clips are type-distinguishable, but tracks are still generic V1–V4; no typed video/audio tracks, lock/hide/mute/solo/rename/height, or track-level audio busses.
- **Timing:** float seconds rounded to tenths/milliseconds; renderer converts to ms. No integer frame/tick base, no 29.97 handling.
- **Selection/properties:** clip inspector covers start/end/duration/track and media `sourceIn`/fit plus split/open-code; no wrapper transforms, opacity, keyframes, or transitions.
- **Playback:** play/pause + timecode work and the composite refreshes at boundaries, but no frame stepping, no authoritative project clock for embedded media/audio, no A/V sync guarantees, no stop-at-end policy beyond the clock.
- **Persistence:** prefs/keys/chat/media are server-backed; the timeline/project itself is browser localStorage only. No project file save/load/export, no schema version, no migration.
- **AI integration:** tools mutate the timeline through direct functions; there is no shared operation layer yet and MCP cannot edit timelines.
- **Audio:** mixing works with gain-free `amix`; no fades/volume envelopes. Timeline audio is now bounded to the captured render window, so a short audio clip no longer truncates the export (`playwright_render.py`, mux `-t`). The legacy single-`audioPath` auto mode still relies on `-shortest`.
- **Performance:** preview and timeline avoid per-frame document rebuilds, but each pointermove during clip move/trim rebuilds all timeline rows via `innerHTML`; bin thumbnails re-create DOM on every repaint; waveforms are not persisted.

## 3. Missing

- Structured project-operation layer (Milestone 1 gap, addressed below).
- Undo/redo, render cancellation/job status, server-side project persistence, versioned schema/migrations.
- Stable track IDs, integer timebase, keyframes, transitions, wrapper transforms, audio fades.
- Structured agent operations over the same project model; MCP timeline/media rendering.
- Project validation (missing media, overlapping same-track clips, invalid ranges).
- Performance benchmarks (RAM/CPU/latency/export throughput/memory growth).

## 4. Functions to preserve

`build_sequence_document` and the deterministic seek machinery; `buildTimelineRenderPlan`; `/render` contract; FFmpeg pipe + encoder probing; content-addressed media and Range serving; AES-GCM/DPAPI key store; `renderCompositePreview`/`previewAtPlayhead` boundary caching; `createSceneClip`, `insertAssetClip`, `placeAssetClipAt`, `splitClipRecord`, `deleteLogicClip`, `snapTimelineEdge`, `overlayTrackFor`, `renderLogicBoxes`; chat tool gating and verification; prefs sanitization.

## 5. Functions that need refactoring (proposed, not done now)

- Duplicate renderers across `playwright_render.py`, `mcp/.../playwright_render.py`, `tui/.../playwright_render.py` and `playwright_render.mjs` — consolidate in a later milestone.
- `serve.py` is a 1926-line module mixing HTTP, rendering, chat, keys and prefs — split by domain later.
- Timeline drag/trim logic mutates clips inline; extract pure timing operations so UI, ops layer and tests share one implementation.
- `renderLogicBoxes` full `innerHTML` rebuild during pointer drags — update only the dragged box in a later performance pass.

## 6. Project model evolution (recommendation)

Do **not** replace `timelineState` now. Introduce, in Milestone 2:
- A versioned envelope `{version, meta, tracks[], clips[], assets[]}` with stable `trackId`/`clipId`.
- Integer frame ticks internally (`tick = round(seconds * fps)`), converting to seconds only at the `/render` boundary.
- An adapter that reads `clipacanvas.timeline.v1` and writes a `v2` key only after a successful migration; v1 remains readable.
- Track objects carrying `kind`, `name`, `muted`, `hidden`, `locked`, `height`.
- Keyframes/transitions as optional per-clip arrays, empty until Milestone 3.
The current flat clip records already carry everything the renderer needs, so the adapter can translate v2 → current payload without touching Playwright/FFmpeg.

## 7. Professional without extra resource cost

- Keep one live composite iframe; no per-clip Chromium instances in preview.
- Reuse the existing boundary-keyed preview refresh; add frame-step seeking on top of it rather than continuous re-rendering.
- Cache bin thumbnails and waveform peaks (persist peaks) instead of redrawing assets.
- Avoid whole-timeline DOM rebuilds for single-clip drags.
- Keep the single render Chromium + FFmpeg pipe; improve cancellation and progress rather than adding parallelism.
- Add measurable benchmarks before/after any optimization.

## 8. Safest implementation order

1. **Milestone 1 (this session):** workspace, bin, drag, timeline space, track/clip presentation, inspector, monitor controls are already in the working tree; the remaining gap is the structured operation layer + tests.
2. **Milestone 2:** playback controller and authoritative clock, frame stepping, integer timebase v2 adapter, typed tracks and track controls, undo/redo, playback/export tests.
3. **Milestone 3:** wrapper transforms, opacity, keyframes, transitions, audio fades/volume, improved thumbnails/inspector — in both preview and export.
4. **Milestone 4:** agent operations over `projectOps`, project validation, Elephant–Goldfish review, full project assembly.

## 9. Milestone 1 plan and status

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | Project / Monitor / Inspector / Timeline layout | Done | `:3851-4330`; `_check_workspace.py` |
| 2 | Project bin in a dedicated panel | Done | `:3861`, `:11671-11868` |
| 3 | Reliable bin→timeline drag | Done | `:10760-10810`, `:11185-11340`; Chromium + WebView2 tests |
| 4 | More horizontal timeline space | Done | 35–45% of height at 1664/1440/1280; `_check_workspace.py` |
| 5 | Video/audio track presentation | Done for M1 (typed tracks deferred to M2) | clip classes, thumbnails, real waveforms |
| 6 | Clip selection and property inspection | Done for M1 (transforms deferred) | clip/media inspector |
| 7 | Program Monitor controls | Done for M1 (frame stepping deferred to M2) | transport/timecode/FIT/fullscreen |
| 8 | Coherent project-operation layer | **This session** | `projectOps` in `clipacanvas.html` |
| 9 | Preserve code editing and AI chat | Done | CODE tab, chat tabs, tool flow |
| 10 | Tests | Done; ops test added this session | `tests/_check_project_ops.py` |

The operation layer exposes the existing timeline actions as validated, structured calls (`createComposition`, `insertAsset`, `moveClip`, `trimClip`, `splitClip`, `deleteClip`, `duplicateClip`, `createTrack`, `seek`, `snapshot`) with one mutation/persist/preview path. It deliberately does not add keyframes, transitions or typed tracks, which belong to later milestones.

## 10. Risks / limitations observed in code

- Timeline/project data is localStorage-only; clearing site data or moving to the packaged exe can lose a project. No project export.
- No render cancellation: aborting the fetch leaves the render thread/Chromium/FFmpeg running; `ThreadingHTTPServer` allows concurrent renders, each with its own Chromium.
- Floating-point seconds are rounded at several boundaries (clip start/duration, `atrim`, `adelay`), so frame-accurate edits can drift.
- Timeline audio is now muxed with an explicit `-t` window; the legacy single-audio auto path still uses `-shortest` and can truncate a longer video to a shorter audio file.
- The standalone `python serve.py` binds `0.0.0.0:8000` by default and CORS defaults to `*`; the desktop app binds loopback. `/api/llm/keys` requires same-origin but returns saved keys to the app.
- Renderer loads arbitrary external URLs in unsandboxed iframes and has no explicit network timeout for page loads.
- MCP/TUI renderer copies lag the desktop renderer (no media/audio/overlay support).
- No performance tests or baselines exist.

## 11. Evidence index

Frontend: `clipacanvas.html` (state `:8974`, persistence `:9164-9314`, render plan `:9240-9374`, timeline `:9959-10810`, preview `:9424-9435`, playhead `:11012-11040`, drag/trim `:11403-11538`, chat tools `:8288-8450`, bin `:11671-11868`).
Backend: `serve.py` (`/render` `:951-1040`, media `:1751-1806`, chat `:642-829`, prefs `:606-620`), `playwright_render.py` (`build_sequence_document` `:301-458`, FFmpeg `:599-731`), `desktop_app.py:170-243`, `mcp/src/clipacanvas_mcp/render_tool.py:19-201`, `tui/src/clipacanvas_tui/`.
Tests: `tests/_check_workspace.py`, `_check_bin_dragdrop.py`, `_check_webview_dragdrop.py`, `_check_media_timeline.py`, `_check_audio_import.py`, `_check_scene_embed.py`, `_check_media_overlay.py`, `_check_logic_timeline.py`, `frontend_render_matrix.py`, `desktop_smoke.py`.
