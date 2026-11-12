# Clip.A.Canvas — Milestone 0 Architecture Audit

Date: 2026-11-12
Branch: `main`
Baseline: working tree contains the uncommitted Milestone 1 workspace refactor (layout, bin drag, dock timeline) plus the pointer drag controller. No commits were made during this audit. All claims below were read from the working tree; tests were not run for this report.

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
