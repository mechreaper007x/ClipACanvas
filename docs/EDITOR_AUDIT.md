# Clip.A.Canvas — Milestone 0 Architecture Audit

Date: 2026-11-12
Branch: `main`
Baseline: `main` at `b8addc5`; the speech/audio work described in the Phase 3 addendum is uncommitted at the time of writing.

## Addendum — local model lifecycle (2026-11-16)

Verified in the working tree on 2026-11-16.

- Local model workers (StyleTTS2, Kokoro, Piper, ZONOS3-Mini and EmbeddingGemma) now load on the first request and unload after `CLIPACANVAS_MODEL_IDLE_SECONDS` of inactivity (default 120 s). A daemon watchdog takes each worker lock non-blockingly, so it never interrupts an in-flight synthesis or embedding; the next request starts the worker again. STT is excluded (about 51 MB, and dictation should stay instant).
- The Voice panel no longer warms a provider when it is selected or when the panel opens, and the `/api/tts/warm` endpoint was removed. Opening the panel lists availability without loading a model; the first Generate pays the load.
- Measured on this machine: StyleTTS2 peaks at 2,433 MB, is freed completely after idle, and a cold synthesis (model load + one line) takes 41 s; warm lines stay around 3 s. EmbeddingGemma loads in 0.4 s / 875 MB and reloads in the same time after idle. With no model loaded the app is back to the WebView2 + backend + STT baseline (about 1 GB).
- No dtype or quantization change was made: StyleTTS2 stays float32, so its audio is bit-identical. `CLIPACANVAS_MODEL_IDLE_SECONDS=0` disables unloading.
- Test: `tests/_check_model_lifecycle.py` loads the embedding worker, waits for the idle unload, and confirms the next request reloads it.

## Addendum — EmbeddingGemma 2 moves to LiteRT (2026-11-16)

Verified in the working tree on 2026-11-16.

### What changed

- The visual index now runs `litert-community/embeddinggemma-2-740m-litert-lm`: a single 485 MB `.litertlm` bundle with QAT mixed precision (int4 transformer/embeddings, int8 vision) executed by LiteRT-LM's `EmbeddingEngine`, replacing the 1.49 GB PyTorch/sentence-transformers checkpoint. On this machine the runtime uses the CPU (XNNPACK) backend; `CLIPACANVAS_EMBEDDING_DEVICE=gpu` switches to the WebGPU backend, and `cpu`/`auto` stay on CPU.
- `embedding_litert_worker.py` keeps the old JSON-lines contract (`text`, `images`, `tags`) and the model's original prompt map (`Retrieval-query` = `task: search result | query: `, `Classification` = `task: classification | query: `, `Document` = `title: none | text: `), so `serve.py`, the retrieval endpoint and the agent tool are unchanged. Label vectors are cached per worker session; images are embedded one at a time through `Content.ImageFile`.
- Runtime resolution moved to `runtimes/litert` (`runtime.json` names the interpreter and asset folder) with the same `CLIPACANVAS_EMBEDDING_PYTHON`, `CLIPACANVAS_EMBEDDING_ASSETS` and `CLIPACANVAS_EMBEDDING_DEVICE` overrides; `CLIPACANVAS_EMBEDDING_MODEL` can point directly at a `.litertlm` file. Analysis version is 6, so every existing manifest reindexes on next load; the sidecar records `runtime: "litert"`.
- Measured against the original on the same still life and labels: load 0.38 s vs 18.7 s, RSS 0.32 GB after load / 0.88 GB after image work vs 2.72 / 3.34 GB (the app worker had grown to 4.26 GB working / 5.9 GB committed under indexing), image embedding 2.4 s vs 6.2 s, text embedding ~125 ms per call. Image vector cosine PyTorch↔LiteRT is 0.932–0.979; text vectors average 0.994 (min 0.988). Object ranking was identical (all ten still-life objects in the top ten of twenty labels, same 0.01+ margin over the best false label); text→image retrieval was 10/10 for both.
- Color words and color+object phrases remain unreliable in multi-object frames in **both** runtimes (absent magenta/cyan/pink outrank real colors; only 2/10 true attribute pairs rank first), so no color filters or attribute claims were added. Tag labels stay short nouns; long phrases such as `a potted succulent plant` lower scores.

### Limitations

- CPU indexing is still ~2.4 s per sampled frame; long footage remains capped at 24 frames. The LiteRT worker still loads on first use and stays resident for the session — the load-on-demand/unload lifecycle and consent prompts are a separate follow-up.
- The bundle is int4 QAT, so vectors differ from the old fp32 index; a reindex is mandatory, and tag thresholds/margins were kept (the measured scores stayed in the same band).

## Addendum — local footage retrieval (Video Moments Finder pattern, 2026-11-15)

Verified in the working tree on 2026-11-15.

### What is implemented

- **Frame index:** every image and video now gets a retrieval index on import. Videos are sampled at ~1 fps, with the interval widened so one asset never exceeds 24 frames (`VISUAL_FRAME_FPS`, `VISUAL_FRAME_LIMIT`); each sampled frame is stored as a 640 px JPEG with its source timestamp and a 768-d normalized embedding. Images keep one vector. The sidecar `analysis/embeddings-<asset>.json` now carries the media filename, frame timestamps, thumbnail URLs and vectors; the manifest frames include time, thumbnail and tags. Analysis version 5 rebuilds old manifests.
- **Local search:** `POST /api/media/search` embeds the query text with the model's `Retrieval-query` prompt, cosine-ranks every indexed frame in the project, drops scores below 0.2, collapses neighbouring frames within 1.5 s and returns distinct moments with asset URL, source timestamp, score and thumbnail. No media or text leaves the machine.
- **UI:** the PROJECT panel has a SEARCH FOOTAGE field. Results show a frame thumbnail, asset name, source timecode and match percentage; clicking a result seeks the timeline clip that covers that moment or previews the asset at that source time. An empty query restores the bin.
- **Agent tool:** `search_footage(query, limit)` returns asset ids, names, source timestamps, scores and thumbnails, so the chat model can choose B-roll or answer content questions from a few lines instead of receiving video frames. The tool list and UI labels are updated.
- **Purpose boundary:** this uses EmbeddingGemma only as a retrieval/similarity model. No captions, scene descriptions, object coordinates or hosted media analysis are generated. Tags and the local summary remain a by-product of the same embedding pass.

### Limitations

- Retrieval resolution is the sampling interval (1 s on short clips, wider on long clips, 24 frames maximum), so a very short event between samples can be missed; timestamps come from the sampling grid.
- CPU indexing costs roughly seconds per frame on this machine; long footage is capped at 24 frames to keep import usable.
- Search needs the EmbeddingGemma runtime and an existing index; assets are indexed automatically on import and stale manifests rebuild on load.

## Addendum — local content analysis and 0-based model counters (2026-11-15)

Verified in the working tree on 2026-11-15.

### What is implemented

- **Media content is analyzed locally only.** ANALYZE CONTENT no longer opens a consent panel or uploads frames. It calls `POST /api/media/analyze` with `refresh: true`, which bypasses the cache and recomputes the manifest: FFmpeg technical probe, scene shots/keyframes, EmbeddingGemma 2 zero-shot tags per keyframe, a frame-difference motion profile, and a local summary sentence built from those measurements (`"5.5 s video, 1 shot, slow motion, 2160×3840 portrait, silent. Local visual index: …"`). The inspector shows `LOCAL · EMBEDDINGGEMMA 2 · N TAGS · M FRAMES`, the summary, stills, tags and motion with the device and `NO UPLOAD`; audio assets are labelled `LOCAL INDEX · IMAGES AND VIDEO`. Analysis version 4 rebuilds old manifests, and a refresh preserves the USER NOTE block.
- **The hosted media-semantic path was removed.** `GET /api/media/semantic/providers`, `POST /api/media/semantic`, the Gemini Interactions upload code and the consent UI are deleted; no hosted provider is called for media content. Legacy `semantic` fields in old project files are ignored by the inspector and replaced the next time the manifest is rebuilt. The agent still reads the local index (`visual.tags`, `visual.description`, shots, motion) through `get_asset_analysis` and `search_assets`.
- **Model counters read used/limit from zero.** The composer model menu now shows `0/5 rpm · 0/20 day` for an unused model (previously the remaining headroom, which read as if 5 of 5 were used), with tooltips stating `X of Y requests/min used · Z left` and the limit source. The usage footer's minute/day token and request rows follow the same convention. Limit enforcement is unchanged.

### Limitations

- EmbeddingGemma is a vision embedding model, not a caption generator: it produces scored tags from the app's label vocabulary, frame vectors and motion, so the local summary is assembled from measurements rather than free-form prose. A richer description still requires the USER NOTE or the agent.
- Audio assets have no local content index (visual indexing covers images and videos); the CONTENT block shows the local-only label and keeps the user note.
- Verification used the real CPU runtime (`tests/_check_embeddings.py`) and `tests/_check_asset_semantics.py`, which fails if any `_llm_http_post` call happens during indexing or ANALYZE CONTENT.

## Addendum — Phase 6 (typed lanes, frame stepping, project files)

Verified in the working tree on 2026-11-12, after `6de97dd`.

### What is implemented

- **Media-clip attachment:** the media inspector now exposes the same OVERLAY LINK controls as the code inspector, so image/video clips can be attached and detached through the UI, not only the agent tools. The shared controls respect the existing rules (no audio parents, no attached overlays as parents, automatic track placement).
- **Frame stepping:** the playhead is quantized to the project frame rate (the export `frameRate`, default 60). Arrow keys step exactly one frame; Shift+Arrow steps one second; Home/End jump to bounds. Monitor timecode already rendered `HH:MM:SS:FF` and now uses the same frame-rate helper. Stepping 60 frames at 60 fps lands exactly on 1.000 s without drift.
- **Typed audio lanes:** A1 VOICEOVER, A2 MUSIC and A3 SFX render as dedicated 32 px rows below the V tracks; audio clips no longer appear on video rows or consume V-track layout. Audio can be dragged between lanes, reassigned from the clip inspector, dropped from the bin or files onto a lane (audio only), and keeps its wave/trim/resize/rename behavior. Deleting audio does not ripple video and video edits do not shift audio lanes; the compact row height keeps all seven rows visible without scrolling at 916 px height.
- **Project file:** `SAVE PROJECT` / `OPEN PROJECT` in the project panel write and read a `.ccproj.json` file (`format: "clipacanvas-project"`, version 1) containing clips, transitions, audio tracks/mix, layers, playhead and the asset records (including shots/semantic analysis). The browser uses a blob download and file picker; the desktop shell uses native save/open dialogs through new `save_project_file` / `open_project_file` bridge methods. Opening validates the format/version, asks before replacing the current timeline, then re-runs analysis for assets whose cached manifests are missing or stale.
- Tests cover frame stepping at 60/30 fps, lane rendering/drags/drops, non-audio rejection on audio lanes, save/open round trips (including the hidden file input) and that deleting audio leaves video timing untouched.

### Limitations

- Storage is still float seconds, not integer ticks: the playhead is frame-quantized, but clip in/out edits remain on the 0.1 s grid, and 29.97/59.94 drop-frame timecode is not implemented.
- A project file references media files by their content-addressed `/media` URL; media is not embedded, so a project moved to another installation needs those files reimported/linked.
- Native desktop save/open dialogs cannot be automated in tests; the WebView2 suite verifies the bridge exists and that the serialization/apply path restores clips and lanes, while the browser suite covers the full download/file-picker round trip.

## Addendum — Phase 5 (overlay attachment UI)

Verified in the working tree on 2026-11-12, after `2d14579`.

### What is implemented

- The code-clip inspector has an OVERLAY LINK block: it lists eligible parent clips (non-audio, not already attached) with track and start time, attaches the selected clip as an overlay through `projectOps.attachOverlay`, and shows the current state (`NOT ATTACHED`, `ATTACHED`, or `PARENT OF n`).
- Attached clips show the parent under ATTACHED TO plus a DETACH action; detaching uses `projectOps.detachOverlay`. Attach/detach keep the editor, timeline, bin and stage in sync, and attachment persists across reloads.
- The UI enforces the same rules as the agent tools: an attached overlay cannot be used as a parent (it is excluded from the select), audio clips are excluded, and attaching moves the overlay to a free track above its parent when needed.
- No new model behavior was added — the UI drives the existing `parentClipId` operations.

### Limitations

- The attachment controls live in the code-clip inspector only; media clips can be attached through agent tools but do not expose the same buttons yet.
- One parent per overlay, no drag-to-link gesture, and overlays still use explicit offsets rather than anchored transforms tracked to objects.

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

- **Provider registry:** `GET /api/tts/providers` reports six providers with live availability and lists the local neural engines first, so the app defaults to one of them whenever it is installed. `styletts2` (LibriTTS), `kokoro` (82M, five voices including Hindi) and `piper` (CPU voices including Hindi) each run through a separate runtime interpreter and a persistent worker process; they report available only when their runtime imports cleanly and their assets exist, and the import probes run in parallel. Probe answers are persisted for 10 minutes (`tts-probes.json`) so a relaunch lists engines instantly, and the Voice panel hydrates from a cached registry with an explicit `CHECKING ENGINES…` state instead of an empty form. `sapi` is the local Windows `System.Speech` fallback. `gemini` uses the Gemini TTS Interactions API; `mistral` uses the Voxtral `/v1/audio/speech` endpoint. Each entry carries supported formats, capability flags (`speed`, `style`, `emotion`, `voiceCloning`, `streaming`) and a plain-language terms string shown in the UI. Hosted providers are marked unavailable with a reason until their key exists in the backend key store.
- **Synthesis endpoint:** `POST /api/tts/generate` validates text (1–4000 chars), provider availability, model, voice, format, speed (0.5–2 where supported) and style. SAPI runs a PowerShell `System.Speech` script offline with the requested rate. StyleTTS2, Kokoro and Piper send the script to their local worker over JSON lines and read the returned WAV; audio never leaves the machine. Gemini sends the script plus optional `speech_metadata` style and reads base64 `output_audio`. Mistral sends `model`/`input`/`voice_id`/`response_format`/`stream` and reads `audio_data`. Keys stay in the existing backend key store; the frontend never receives them.
- **Caching:** SHA-256 over the canonical request (version, provider, model, voice, format, speed, style, text) keyed under `%APPDATA%/ClipACanvas/tts`. A repeat request returns the existing media file without calling the provider. Audio is stored as a normal content-hashed `/media` asset, probed with the bundled FFmpeg for duration/sample rate/channels, and recorded with provider, voice and terms provenance.
- **Voiceover Studio:** right-pane `VOICE` tab with script (selection pre-fills), character count, provider/model/voice/format/speed/style/target controls, an explicit hosted-provider consent line, generate action, status, audio preview, and insertion at the playhead on the chosen lane (`A1` default, `A2`/`A3` optional) or into the bin.
- **Audio mix:** `A1 VOICEOVER` / `A2 MUSIC` / `A3 SFX` are persisted in `timelineState.audioTracks` with `mute`, `solo` and `volume` (0–2). Audio clips carry `audioTrack`. The inspector exposes lane assignment and per-lane mix rows; the timeline shows lane tags on audio clips. Export and hosted renders carry `audioTrack` plus gain, the renderer applies FFmpeg `volume=` and honors mute/solo (any solo lane suppresses non-solo lanes; muted or zero-gain clips are skipped).
- Generated and imported speech use the existing `/media`, bin, timeline, composite preview and export paths; no parallel pipeline was added.

### Limitations

- Hosted providers were implemented against the official documentation (Gemini Interactions API; Mistral `audio/speech` reference) but no live hosted call was made during verification because no hosted key was configured. Failures surface explicit provider errors (502) instead of silently falling back to another provider.
- Mistral Voxtral is exposed with preset voices only; cloning needs a reference-audio upload and is not exposed. Speed/style controls hide for providers that do not support them.
- StyleTTS2 uses the default LJSpeech reference voice; the runtime supports voice cloning through a reference WAV, but the app does not expose a reference-voice picker yet. Its first generation loads the model (about 30 s on the test machine), then lines synthesize in about a second. The packaged build does not bundle torch; it needs the separate StyleTTS2 runtime folder.
- Kokoro and Piper ship five voices (Kokoro) and two voices (Piper, English and Hindi) on this machine; adding more voices means adding models to their runtime folders. Kokoro's first line loads the pipeline (about 15 s cold on the test machine), then warm lines take a fraction of a second; Piper is CPU-only and warm lines are around 0.15 s.
- SAPI voice quality depends on installed Windows voices; UI speed maps onto the engine's rate scale.
- Audio lanes are logical (`clip.audioTrack` + mix); clips still sit visually on the V1–V4 rows with `A1`–`A3` tags, and there are no typed audio lanes or lane heights yet.
- Voiceover Studio generates whole scripts or the selected text; there is no per-paragraph regeneration or scrubbing preview.

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
| 2 | Transition library + generated transitions + overlay UI | Done (13 presets, custom code, inspector attach/detach) |
| 2 | Voiceover Studio + local/hosted TTS | Done (StyleTTS2, Kokoro, Piper, ZONOS3-Mini, SAPI, Gemini, Mistral; A1–A3 mix) |
| 3 | Semantic/visual/audio asset analysis | Done (local shots + keyframes; consent-gated Gemini vision/transcript) |
| 4 | Full workflow validation + project persistence of all new objects | Done in localStorage + `.ccproj.json`; hosted-provider live checks pending |

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
- Chat sessions are scoped per project: the SQLite `sessions` table carries `project_id`, legacy chats are bound to the last open project on migration, opening a project loads only its sessions (and a new project starts with a new chat), and every save replaces just that project's rows. The CHATS popover is project-labelled.
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

## Addendum — Phase 7 (hosted provider live verification)

Verified on 2026-11-12 against the real stored keys (keys were loaded by the backend only and never printed or committed).

### Results

- **Gemini TTS:** live request returned a 4.88 s / 24 kHz mono WAV through `/api/tts/generate`; the Voiceover Studio generated and played it. The live Interactions response carries audio in `steps[].content[]` (`type: "audio"`), not `output_audio`; the parser now accepts both shapes and is unit-tested.
- **Gemini content analysis:** live vision analysis on a synthetic three-shot test video returned an accurate description, tags and confidence 0.95 from `gemini-2.5-flash` with 3 uploaded keyframes. Live transcription of synthetic TTS audio returned the exact sentence with a 0.0 s start. Only generated test media was uploaded.
- **Mistral TTS:** the key is valid (models list reachable) but the speech endpoint rejects the legacy `voice_447` catalog for speech v1. `voxtral-mini-tts-latest` with the documented speech-v1 voices works live; five voices were verified (`gb_jane_neutral`, `gb_oliver_neutral`, `en_paul_neutral`, `en_paul_sad`, `fr_marie_neutral`) in both mp3 and wav. The Studio generated a 2.56 s WAV through the live provider. `voxtral-mini-tts-3-0` returns the account's 429 rate limit, so `latest` is the default and 3.0 remains selectable.
- The provider registry now lists the speech-v1 voice catalog and both Mistral models; the voice catalog is no longer the deprecated `voice_*` list.

### Limitations

- The Mistral 3.0 rate limit is account-side; the app surfaces the provider error instead of hiding or retrying indefinitely.
- Hosted calls still require the user's keys in the backend store; no key material is exposed to the frontend or logs.

## Addendum — Premiere-style keyboard shortcuts (2026-11-14)

- Ctrl/Cmd+A outside text fields selects every timeline clip and never highlights page text; Ctrl+Shift+A clears the selection. Ctrl+A in inputs, textareas and Monaco keeps native select-all.
- Multi-clip selection: Shift+click adds, Ctrl+click toggles; selected clips render with a go-colored ring. The active clip still drives the editor and inspector.
- Premiere-style keys: Space play/pause; J/K/L shuttle with rate doubling; Left/Right frame step; Shift+Left/Right five frames; Up/Down previous/next edit point; Home/End; Ctrl+K add edit (split at playhead); Delete/Backspace lift (gap stays); Shift+Delete ripple delete; S snapping toggle; = / - zoom; \ fit; Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y undo/redo.
- Ctrl+Shift+K now focuses Clipppa chat (Ctrl+K was freed for Add Edit).
- A `?` button in the timeline header and Ctrl+Alt+K open the shortcut sheet; `?` no longer opens while typing in an input.
- Batch ripple delete processes removals right-to-left so multi-clip gaps close exactly once; a multi delete is one undo step.
- Project files now persist `timeline.activeId`, so restoring an autosave reopens the clip that was being edited.
- Tests: `tests/_check_shortcuts_selection.py` (selection, text-selection guard, lift/ripple, batch delete, split, snapping, edit points, frame steps, zoom, JKL, shortcut sheet, header fit at 1664/1440/1280).

## Addendum — Voice catalog and automatic transitions (2026-11-14)

- The speech registry now labels every voice with a gender. Kokoro exposes 19 curated English and Hindi voices (10 male, including Michael, Adam, Eric, Fenrir, Liam, Onyx, Puck, Daniel, George, Omega), Gemini's 30 prebuilt voices carry the documented Google Cloud genders, Mistral voices are labelled male/female, and Windows SAPI labels include the installer's gender.
- The chat assistant now receives a live "Available speech voices" system message with ids and genders. `generate_voiceover` accepts `gender` in addition to `voice`; the resolver matches ids, display names and labels, and moves to a provider that has the requested gender (StyleTTS2 is female-only, so a male request lands on Kokoro, Piper, SAPI or a hosted male voice). The frontend provider cache key was bumped to v2.
- AI scene creation is auto-scored: `add_scene` installs a 0.4s dissolve on the new touching cut unless a `transition` object (preset or custom `renderTransition` code) is supplied; `transition:false` keeps a hard cut. `add_transition` accepts `all:true` to apply or update one effect at every touching cut without stacking duplicates. The system prompt now makes transitions the default finish for every cut and gives the model both paths to write custom code itself.
- Fixed a selection regression where pressing a transition badge re-rendered the timeline during pointerdown and swallowed the badge click; badges now bypass the empty-lane scrub.
- Tests: `tests/_check_voice_genders_transitions.py` (gender routing by gender/name/id, provider fallback, 19-voice panel, auto dissolve, custom scene transition, hard cut, all-cuts dedupe, verify); `_check_tts.py`, `_check_agent_voice.py`, `_check_voice_provider_cache.py`, `_check_transitions.py`, `desktop_smoke.py`, `_check_packaged_agent_plan.py` and `_check_packaged_shortcuts.py` pass.

## Addendum — Microsoft Edge neural voices (2026-11-14)

- A seventh provider, `edge` ("Microsoft Edge Neural (online)"), adds the free Microsoft read-aloud catalog: 322 neural voices across 142 locales with male and female options for most languages and no account or key. English, Hindi and the other priority locales are sorted first; each voice carries its locale and gender.
- The catalog is fetched once from Microsoft's voice-list endpoint, cached in `tts-probes`-style disk JSON (`edge-voices.json`, 24h TTL) and kept in memory. A curated 49-voice fallback keeps the provider usable on a first start without internet; the registry never blocks on a refresh it cannot serve.
- Synthesis uses `edge_tts` 7.3.1 (7.2.x receives a 403 from the DRM-protected endpoint) with an explicit aiohttp `ThreadedResolver`, because aiodns cannot reach DNS servers on this machine. Output is 24 kHz mp3 and flows through the same media probe, cache and A1–A3 lanes as every other provider.
- `generate_voiceover` accepts `provider: "edge"`; the chat voice catalog lists 80 Edge ids (all priority locales) plus a note that ids follow `locale-NameNeural`. The resolver matches Edge ids or names (e.g. "Ryan", "Madhur") and keeps local engines ahead of online voices for plain gender requests.
- Defensive fix: an unavailable provider with no key now fails with its reason instead of falling through to the Mistral branch; the frontend provider cache key moved to v3.
- Packaging: `edge_tts` and `aiohttp` are collected by `build_desktop.py`, `ClipACanvas.spec` and `ClipACanvasDebug.spec`; requirements list `edge-tts>=7.3.1`.
- Tests: `_check_tts.py` generates a live Edge mp3 through `/api/tts/generate`; `_check_voice_genders_transitions.py` checks 322 voices, gender counts, Hindi coverage, name/id/gender routing and 322 panel options; `_check_voice_provider_cache.py` expects 7 providers.

## Addendum — StyleTTS2 narrator voices; Edge provider removed (2026-11-14)

- StyleTTS2 now exposes eight narrators: the original LJSpeech target (`default`) plus seven LibriTTS reference voices (three female, four male). The 3 s, 16 kHz references are bundled in `styletts2-voices/` (LibriTTS, CC BY 4.0, from the official StyleTTS2 demo page).
- The worker computes each voice's style embedding lazily from its reference and caches it in memory for the session; later lines stay at roughly the previous speed. The registry lists a voice only when its reference file exists.
- Male requests now route to a StyleTTS2 LibriTTS male voice first because StyleTTS2 heads the local provider order; Kokoro/SAPI still cover names or engines that StyleTTS2 lacks. Measured on identical text: LJSpeech ~205 Hz, LibriTTS 4077 ~112 Hz.
- The Microsoft Edge provider added earlier today was removed on request: catalog, synthesis, registry entry, tool enum, frontend prompt/catalog, packaging flags, requirements and tests are gone. The frontend provider cache key moved to v4.
- Packaging bundles `styletts2-voices/` in `build_desktop.py`, `ClipACanvas.spec` and `ClipACanvasDebug.spec`.
- Tests: `tests/_check_styletts2_voices.py` (new; catalog, synthesis, pitch separation), `_check_voice_genders_transitions.py` (8 voices, male routing by gender/name/id, panel), `_check_tts.py`, `_check_voice_provider_cache.py` (6 providers, v4) and `_check_packaged_agent_plan.py` updated.



## Addendum — ZONOS3-Mini local narrator engine (2026-11-14)

- An eighth provider, `zonos` ("ZONOS3-Mini (local neural)"), adds Zyphra's 2026 Apache-2.0 TTS model: 27 named narrators (10 English plus French, German, Hindi, Italian, Korean, Mandarin, Portuguese, Spanish and Telugu) across 43 languages at 44.1 kHz. It runs through `transformers` remote code (`trust_remote_code=True`) in a persistent worker, so script text never leaves the machine.
- Runtime: `runtimes/zonos/assets` holds the HF checkpoint (`config.json`, `model.safetensors`, `voices.safetensors`, `modeling_zonos3.py` and tokenizer files); `runtimes/zonos/runtime.json` names the interpreter and assets folder. On this machine the engine-interpreter search resolves to Python 3.11 with torch 2.11 and transformers 5.9. `CLIPACANVAS_ZONOS_PYTHON`, `CLIPACANVAS_ZONOS_ASSETS` and `CLIPACANVAS_ZONOS_DEVICE` override the same values.
- Device: CPU `float32` is the default (cold load about 27 s, about 8 s per short line, roughly 4x real time). `CLIPACANVAS_ZONOS_DEVICE=cuda` switches the worker to `float16` on this 4 GB GTX 1650 (cold load about 17 s, about 5 s per line); GPU is opt-in so renders keep the card.
- Text normalization: `zyphra-textnorm` is optional and not installed here, so numbers, dates and units pass through unnormalized (the worker prints a one-time notice to stderr). English, Hindi and the other release voices synthesize correctly without it.
- Voice routing: the catalog gives every narrator a gender; the resolver matches Zonos names (`Savannah`, `Arjun`) or ids, and the chat prompt points non-English scripts at the matching Zonos narrator. The local provider order is StyleTTS2 → Kokoro → Piper → Zonos, and the frontend provider cache key moved to v5.
- Synthesis uses a 900 s request timeout for this engine (other local workers keep 180 s) because long CPU lines are slower than real time; `generate_voiceover` accepts `provider: "zonos"`.
- Packaging: `zonos_worker.py` is bundled by `build_desktop.py`, `ClipACanvas.spec` and `ClipACanvasDebug.spec`. Model assets stay outside the exe in the runtime folder.
- Tests: `tests/_check_zonos.py` (new; 27-voice catalog, Savannah English and Arjun Hindi synthesis, 44.1 kHz probe, pitch separation Savannah 200.6 Hz vs Wyatt 94.9 Hz), `_check_voice_genders_transitions.py` (27 panel options, Zonos name/Hindi routing), `_check_voice_provider_cache.py` (v5, 7+ providers) and `_check_packaged_agent_plan.py` (Zonos take in the packaged exe) updated.

## Addendum — Local visual index and media-aware overlays (2026-11-14)

- A local EmbeddingGemma 2 tier (`google/embeddinggemma-2`, Apache 2.0, text+image encoders only) now indexes imported media. `analyze_media_file` embeds up to three shot keyframes, runs zero-shot object/scene tagging against a 96-label vocabulary (top 4 tags per keyframe with a score floor and top-relative margin), stores 768-d frame vectors in `analysis/embeddings-<asset>.json`, and records a frame-difference motion score/peak/label for videos. Everything runs on this machine; unlike the Gemini vision tier there is no upload and no consent step.
- Runtime: `runtimes/embedgemma2/assets` holds the 1.49 GB checkpoint and `runtime.json` names the interpreter (Python 3.11, sentence-transformers 6.3, transformers 5.23). `CLIPACANVAS_EMBEDDING_PYTHON`, `CLIPACANVAS_EMBEDDING_ASSETS` and `CLIPACANVAS_EMBEDDING_DEVICE` override them. The device default is `auto`: CUDA only on cards with at least 8 GB, so this 4 GB GTX 1650 stays on CPU and leaves VRAM for renders (CPU ≈ 6 s per keyframe; CUDA measured ≈ 5× faster).
- Analysis version is 3. `analysis.visual` (status, provider, tags, per-frame tags, motion) is sanitized into project files; the media inspector shows the local tags, motion label and a `LOCAL VISUAL INDEX · EMBEDDINGGEMMA2` status; `search_assets` matches visual tags; and the agent's asset summary now carries `visualTags`, `motion` and shot count. The system prompt tells the agent to read asset analysis before creating overlays on media and to cite tags honestly.
- Zero-shot labels are hints, not detections: scores sit in a narrow 0.55–0.68 band, so each frame keeps only the top four within 0.045 of its best label; expect common near-neighbours (football/sport/field) and treat tags as evidence, not ground truth.
- Live verification with the real Gemini key: the agent created a lower-third overlay with `create_overlay` and `parentClipId` on an imported football still, with its visual tags (`football, sport, sun, field`) in the chat context; asked for a custom transition, it wrote its own `renderTransition(ctx)` wipe and saved it via `add_transition` (0.5 s). At the cut the Program Monitor composite showed both layers at opacity 0.5 with `clip-path: inset(0 50% 0 0)`, and removing the transition returned the preview to single-clip mode.
- Packaging: `embedding_worker.py` is bundled by `build_desktop.py`, `ClipACanvas.spec` and `ClipACanvasDebug.spec`; model assets stay in the runtime folder.
- Tests: `tests/_check_embeddings.py` (image tags, video keyframes, motion vs a still video, 768-d sidecar), `tests/_check_visual_ui.py` (inspector tags/status), `tests/_check_agent_live_media.py` (live model overlay + model-written transition), `_check_voice_genders_transitions.py` regression, and `_check_packaged_agent_plan.py` now indexes a still through `/api/media/analyze` inside the exe.

## Addendum — Scenes and timeline are no longer capped (2026-11-15)

- The editor no longer enforces a 40-scene cap or a 60-second timeline. `TIMELINE_MAX_SECONDS` and `HARD_MAX_DURATION_SECONDS` now sit at 24 hours (an arithmetic ceiling, not a product limit), the three 40-clip checks are gone (new scene, duplicate, project op), and the transition list lost its 40-entry cap so a long edit can still finish every cut.
- The deterministic renderer had its own copies of the same limits: `build_sequence_document` clamped clip starts to 60 s, `render_payload` took only the first 40 clips and 40 transitions, and `HARD_MAX_DURATION_SECONDS` capped render ranges. All removed/raised, so a 3-minute sequence renders exactly like a 30-second one.
- Project payload cap raised from 8 MB to 64 MB so the durable project store can hold long timelines with rich scene code; the frame-range inputs and duration fields now accept up to 24 h, and the ruler/timecode formats grow an hours field (`1:32.00`, `1:02:03.50`).
- Timeline persistence now schedules the durable project save even when the localStorage mirror throws (quota), so large projects keep autosaving.
- Verified against the real 31-clip, 1:00.00 project: a new scene appends at 1:00 and the timeline grows to 1:04 (screenshot `output/playwright/timeline-past-60.png`). New test `tests/_check_unlimited_scenes.py` creates 45 scenes (3:04, 46 clips after duplicate), adds 44 transitions, saves/reloads through the backend, and renders a 61–61.5 s window to a blue 0.5 s mp4; timeline, project, chat-scene, transition, zoom, history and preview regressions pass.

## Addendum — Timeline working span and zoom-out (2026-11-15)

- A 100% timeline view no longer shrinks to the content length. The view keeps a 30-second working baseline (`TIMELINE_MIN_VIEW_SECONDS`) or the full sequence if it is longer, so a single 3-second scene renders as a small box (about 10% of the lane) instead of stretching across the entire ruler. An empty timeline shows 0–30 s.
- Zoom now runs from 1% to 800%. Below 100% the view expands beyond the sequence (a 6 s edit at 50% shows 60 s; at 1% a 30 s baseline spans 50 minutes), above 100% it zooms into clips; 100% / FIT always returns to the baseline view. Anchoring and Ctrl+wheel use the view time, so the point under the pointer stays put even beyond the content end.
- The zoom percent field was widened to 58 px, centered, with native number spinners removed, so `100`/`800` are no longer clipped.
- Updated `tests/_check_timeline_zoom.py` covers the 3 s solo scene (≈10% width, 30 s ruler), empty view, presets 1–800, zoom-out to 50%, clamping at 1/800 (3000 s span), playhead anchoring on a 120 s sequence, wheel zoom, button/FIT sync and no document overflow at 1280.

## Addendum — Media playback, console windows, project recovery (2026-11-15)

- Media playback no longer recreates the media iframe every 0.5 s. `playbackClipKey()` dropped the `mediaBucket` term, so during playback a video/iframe stays mounted and plays natively for the whole clip instead of being reloaded and re-seeked twice per second — the source of the stuttering monitor.
- Every FFmpeg/ffprobe child process in `serve.py` (technical probe, shot detection, keyframe extraction, motion profile, semantic frames, audio extraction) and in `playwright_render.py` (encoder probe, capture/encode pipe) now passes `CREATE_NO_WINDOW`. Importing or analyzing media in the windowed exe no longer flashes terminal windows.
- A backup of the original 31-clip `UNTITLED PROJECT 5` (saved 2026-11-15 01:10) was restored as a separate library project `RESTORED PROJECT 5`; the project store had re-created project id `untitled-project-5` at 17:42 with a new empty timeline, so the original content was preserved from `projects-backup-20261115-0110`.

## Addendum — Local English dictation (2026-11-15, model replaced 2026-11-16)

- The chat composer has a mic control with a static `EN` badge; dictation is English-only. Click the mic to record, click again to transcribe; Esc (or the ✕ on the status strip) cancels, and recordings stop automatically at 120 s. The transcript is inserted into the prompt at the caret end so it can be edited before sending; the strip shows the live timer, mic level ring and model download/load percent.
- Speech-to-text runs fully local. `stt_worker.py` records with `sounddevice` (16 kHz mono, device-default rate resampled in numpy) and transcribes with `faster-whisper small.en` (CTranslate2 int8 on the CPU, VAD filter, beam 5, timestamped decoding). It returns fluent English with punctuation and capitalisation. Nothing is uploaded and the audio file is deleted after transcription.
- Model choice (85-sample LibriSpeech/JFK benchmark, 2026-11-16): small.en clean corpus WER 5.45% / noisy 6.42% / all 5.81%, RTF 2.51, load 2.36 s, peak RSS 712 MB, 464 MB on disk. The previous Vosk small EN model measured 13.74% / 18.87% / 15.62%, RTF 4.68, 272 MB RSS. faster-whisper base.en and distil-small.en were rejected (less accurate) and the Hindi Vosk model is retired.
- Runtime: `%APPDATA%/ClipACanvas/runtimes/stt/assets/models/faster-whisper-small.en` holds `config.json`, `tokenizer.json`, `vocabulary.txt` and `model.bin`. On first prepare the worker downloads any missing file from `huggingface.co/Systran/faster-whisper-small.en` and reports percent through the status endpoint; later runs load from disk. Overrides: `CLIPACANVAS_STT_PYTHON`, `CLIPACANVAS_STT_ASSETS`, `CLIPACANVAS_STT_MODEL_DIR`, `CLIPACANVAS_STT_INPUT`.
- Backend endpoints: `GET /api/stt/status` (model state, progress, input name, recording elapsed/peak), `POST /api/stt/warm|prepare|start|stop|cancel`, and `POST /api/stt/transcribe` (raw WAV body, used by tests; the legacy `lang` parameter is ignored and every response is English). The model is managed by the shared idle watchdog: it unloads after 120 s without dictation and reloads on the next mic click; active recording/transcription holds the worker lock so it cannot be unloaded mid-request.
- Guards: near-silence (loudest 100 ms window RMS < 0.02) is rejected as `silent`, so noise does not insert text. The mic opens first and the model is primed in the background, so the model load overlaps with the user speaking.
- Tests: `tests/_check_dictation.py` (real small.en, SAPI English WER ≤ 10%, punctuation/case, auto/legacy-hi parameters, silence guard, mic smoke), `tests/_check_dictation_ui.py` (mic state machine, static EN badge, insertion, cancel, no page errors) and `tests/_check_packaged_dictation.py` (worker bundled inside the exe, packaged English WER check).
- Packaging: `stt_worker.py` is bundled by `build_desktop.py`, `ClipACanvas.spec` and `ClipACanvasDebug.spec`; model assets stay in the runtime folder.
- Packaging: `stt_worker.py` is bundled by `build_desktop.py`, `ClipACanvas.spec` and `ClipACanvasDebug.spec`; model assets stay in the runtime folder.

## Addendum — Media nesting, full-length transitions and deep zoom (2026-11-15)

- A bin image/video dropped directly on a code scene's logic box is now embedded inside that scene's HTML (`resolveTimelineDrop` returns `embedClip`, `embedAssetInScene(asset, position, targetClip)`); it no longer creates a new timeline layer. The same drop works for OS files on a scene box, and the scene box gets a green `drop-embed` ring while hovering. Dragging the media on the preview still moves it inside the scene. The bin ＋ button and double-click also embed when a code scene is selected and the playhead is inside it (`addAssetSmart`); double-click is tracked by click count because selecting an asset re-renders the tile. The media inspector keeps a deliberate layer path: `INSERT AT PLAYHEAD` adds a separate clip, while `INSERT INTO <SCENE>` embeds.
- An empty code scene adopts the added image/video as its full-frame content: the scene is written as a complete HTML document with a black page and a 100%×100% media element (`object-fit: contain`, `data-cc-fill="1"`). In a scene that already has content the media is a positioned element (drop point, or 72% centered). Full-frame fill media is excluded from the preview drag tools. Existing projects that saved a lone 72% `cc-scene-media` fragment are upgraded on load by `upgradeLegacySceneMedia`; rich scene code is untouched.
- The agent has a matching `put_media_in_scene` tool: pass `assetId` plus `sceneId` (or select the scene and omit it). It injects the media element into the scene's HTML and returns the scene summary; it rejects imported video clips with a message to use `create_overlay` + `parentClipId` instead. `create_overlay` descriptions now say overlays are only for imported video clips, not code scenes.
- The media inspector's embed button is explicit about the target: `INSERT INTO <SCENE>` for code scenes and `ADD PIP OVER <CLIP>` for imported video clips, which creates the attached overlay.
- Transitions no longer require spare footage handles. The shared transition runtime freezes the outgoing last frame and incoming first frame during the window, so `add_transition`/`update_transition` succeed on clips that use their full source and export exactly what the Program Monitor shows.
- Timeline zoom minimum is 1%: a 30 s baseline spans 50 minutes at the lowest setting; presets are 1/2/5/10/25/50/75/100/125/150/200/250/300/400/600/800 and numeric entry clamps to 1–800.
- Tests: `_check_scene_embed.py` now covers drop-to-embed and the `put_media_in_scene` tool path, `_check_media_pip.py` covers attached PIP overlays on imported video, `_check_transitions.py` covers a no-handle full-length transition and its exported dissolve, and `_check_timeline_zoom.py` covers the 1% clamp.

## Addendum — Playback resume for videos embedded in scenes (2026-11-15)

- The preview clock's live branch (`__clipacanvasMediaSeek(seconds, false)`) now resumes every `<video>` that the paused branch stopped: a paused element seeks to the virtual time and calls `play()`, and a playing element is re-seeked when it drifts more than 0.5 s from the clock. Previously the live branch returned immediately, so pause → resume left scene videos frozen on their last frame while the scene animation kept running.
- Both branches share the same `seekTime` math: videos with `data-source-in` seek to `sourceIn + t` clamped to the source length, other videos wrap on `t % duration` like the deterministic renderer. Live playback still has no A/V lock guarantees, but the video now follows the timeline and recovers from scrubs.
- Tests: `_check_media_pause_resume.py` covers a timeline media clip and a video inside a code scene (play, pause twice, resume, video time advances); `_check_packaged_scene_pause_resume.py` repeats the scene case inside the WebView2 exe with a 6 s clip and checks that video time tracks the playhead.

## Addendum — The agent composes inside a scene with media (2026-11-15)

- When the selected code scene already contains embedded media (`<img>`/`<video class="cc-scene-media">`), the chat system prompt now tells the model to rewrite that same scene with `insert_animation_code`, keeping the media elements unchanged and building titles, captions, effects and animation around them; `add_scene layer:"above"` and `create_overlay` are scoped to imported video/image clips or an explicitly requested independent overlay scene.
- Each API request gains a system message that lists the selected scene's embedded media (`kind`, `src`, full-frame flag) and states that content for that scene belongs inside the same document, with a hint to put new layers after a full-frame video with a higher `z-index`. `chatToolAppState().selectedClip` also returns `embeddedMedia`, so the model sees it even when the scene code is truncated to the 8000-character context limit.
- `insert_animation_code` keeps existing scene media automatically: if the model's new HTML omits a `cc-scene-media` element, the app injects the original tag at the top of the body (behind the new content), keeps clip/layer counts unchanged and reports `preservedMedia` in the result. The model can still include the tag itself for precise placement; `removeMedia:true` is the explicit opt-out. This replaced an initial rejection guard, which surfaced long red tool errors whenever the model rewrote a scene without copying the video tag.
- Tests: `_check_scene_embed.py` covers the per-turn cue, an omitted-media rewrite that keeps the media behind a new title (`preservedMedia` 1), an in-scene title that includes the media itself, and explicit removal; `_check_packaged_scene_embed.py` repeats the automatic preservation in the WebView2 exe; `_check_chat_scenes.py` asserts the tool description and `removeMedia` property.

- The Goldfish reviewer prompt now treats app-served `/media/` assets referenced by `cc-scene-media` as local project media, not a network dependency, and describes a scene-media video as clock-driven rather than the artifact's motion source. Without this, a valid in-scene edit could be "fixed" by removing the video the user asked to keep.

## Addendum — Quota-aware model routing (2026-11-15)

- A manually selected model now survives a 429: the server retries sibling models of the same provider (`fallbackOnQuota`), never another provider. The response reports the actual `model` and `fallbackFrom`; the assistant header already shows the model that answered.
- Per-model 429 cooldowns persist in `<keys dir>/llm-quota.json`, parse `Retry-After`, `retryDelay` and `retry_after` with a 60 s floor, and survive restarts. AUTO and manual picks skip cooled models; `/api/llm/models` returns `cooldownSeconds`, and the model selector and composer menu label them (`quota ~5m`).
- Rate-limit copy distinguishes one exhausted model from every model tried, and points to another model or provider instead of repeating the same dead end.
- Tests: `tests/_check_llm_quota_fallback.py` fakes a Mistral 429 and verifies same-provider fallback, no fallback when quota fallback is disabled, persisted cooldowns and the model-list annotation; `_check_chat_scenes.py` checks the quota label in the picker and composer.
- Once quota fallback starts, the server keeps searching through sibling models even if one is unavailable for another reason (for example a plan 403), so a manual pick reaches the first sibling that actually answers instead of stopping on the next error.

## Addendum — Local LLM usage ledger and call breakdown (2026-11-15)

- Every provider request made by the chat harness is now counted in `<keys dir>/llm-usage.json` with the day, provider, model, purpose (`chat`, `review`, `title`, `plan`, `plan-step`, `fix`), HTTP status, prompt/completion tokens and — when the provider reveals it — the quota limit. History is pruned to 14 days. Recording happens in `_handle_llm_chat` per HTTP attempt (success and HTTP error), so fallback retries, sibling searches, 429s and tools-rejected retries all appear.
- Gemini `usageMetadata` (including thoughts tokens) and Mistral `usage` are normalized to prompt/completion/total. Gemini 429 bodies are parsed for `quotaValue` before display truncation, so the model row can show `~N left of M` after a quota error; Mistral does not report a limit, so only counted calls and the cooldown are shown.
- `GET /api/llm/usage` returns today's provider buckets with purposes and per-model calls/tokens/limit/remaining/cooldownSeconds. The composer model menu reads it on open and after each turn: each model row shows `N calls` (or `N used · ~M left`), cooled models get a burn-colored dot, and a `Today` footer lists per-provider calls, tokens and the purpose split, with a note that providers do not expose remaining quota.
- Why calls disappear faster than expected: a plain chat turn is one provider request plus a model-generated title request on the first turn; a code turn adds a Goldfish review request and, when it finds blockers, a stealth fix turn (tool round + summary). Planned briefs add a planner request plus per-step tool/summary rounds, and quota fallback retries add one request per model tried.
- Tests: `tests/_check_llm_usage.py` fakes Gemini success and a 429 with `quotaValue`, asserts ledger totals/purposes/limits/cooldowns, then drives the real UI: the menu renders the usage footer, model-row counts and cooled dot, and a chat turn records `chat` plus `title` purposes.

## Addendum — Real per-model limits, context caps and quota-aware routing (2026-11-15)

- Live API facts established with the user's keys: Gemini `models.list` exposes only `inputTokenLimit` and `outputTokenLimit`; successful Gemini calls return `X-Gemini-Service-Tier: standard` and `usageMetadata.serviceTier` but **no** rate-limit or quota headers; a Gemini 429 carries `QuotaFailure.violations` (`quotaId`, `quotaMetric`, `quotaValue`) and `RetryInfo.retryDelay` (observed `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, value 20, retry 54372 s). Mistral `models.list` exposes `max_context_length` and `capabilities.function_calling`; successful Mistral calls return live `x-ratelimit-limit-req-minute`, `x-ratelimit-remaining-req-minute`, `x-ratelimit-limit-tokens-minute`, `x-ratelimit-remaining-tokens-minute` (observed 2 req/min and 40 000 tok/min on the free key).
- Gemini free-tier RPM/TPM/RPD are not available from the API. They are encoded from the user's AI Studio rate-limit page (free plan, verified 2026-11-15) in `serve.py` `_FREE_TIER_LIMITS`; the table covers the chat models the app lists (flash 5/250K/20, flash-lite 15/250K/500, 2.5-flash-lite 10/250K/20, Gemma 4 30/16K/14.4K, pro and 4-argon/carbon 0). A provider 429 always overrides the table for the exhausted metric. The composer menu labels the source and verification date.
- The server records rolling 60-second calls/tokens per model and per-purpose/day totals. `/api/llm/models` and `/api/llm/usage` return `limits`, `headroom`, `limitsSource`, `callsToday`, `okToday`, `rateLimit` and (for Mistral) `inputTokenLimit`/`supportsTools`. The model rows show `ctx`, `used/limit rpm` and `used/limit day`; the footer shows provider totals, purposes, live req/token per-minute headroom and the last call's token spend.
- Routing is quota-aware for both providers. Before a call the server switches to a sibling of the same model tier when the model has no RPM/RPD/TPM headroom or the request is larger than its TPM budget; if no sibling exists it waits for the minute window (or refuses a request that cannot fit). A model whose RPD is 0 is skipped (Gemini pro tier on the free key). Mistral models without `function_calling` are never auto-picked for tool turns. AUTO never picks Gemma for code and falls back from the pro tier to flash when every pro model has no quota.
- Context is enforced before spending a call: `_estimate_prompt_tokens` (chars/3.2 + tool-schema allow 2 000) is checked against the model's `inputTokenLimit`; requests above the context, or above the model's tokens/minute budget, return a clear 400/429 without reaching the provider. Output is capped at 16 384 tokens for Gemini (`maxOutputTokens`) and Mistral (`max_tokens`).
- The title request now runs after the review/render instead of beside the review, so a free-tier model is not hit by two same-second requests.
- Tests: `tests/_check_llm_usage.py` fakes Gemini quota failures and Mistral headers, checks the free-tier table/headroom/sibling choice (RPM-exhausted flash → flash-lite, pro 0 RPD blocked), the context guard, context/tool metadata from the real parsers, the per-minute sibling switch without a 429, and the menu labels; `_check_llm_quota_fallback.py`, `_check_chat_scenes.py` and `_check_scene_embed.py` still pass.

## Addendum — Scene-embedded footage reaches the agent; stable composite preview (2026-11-16)

- `sceneMediaDetails(code)` maps every `cc-scene-media` element in a scene's HTML to its project asset and returns the asset name, duration, resolution, full-frame flag, user/AI description, production notes, visual tags, motion label and per-second moments. It feeds the selected-media system message, `timelineSummaryForChat().scenes[].embeddedMedia`, `chatToolAppState().selectedClip.embeddedMedia` and `getClipContext().embeddedMedia`, so the model knows what footage under Scene 01/02 shows even when only the selected scene's code is in context (or the code is truncated at 8 000 characters).
- The prompt now states that a caption/subtitle clip is text only with a fully transparent background and never a copy of the scene video; that embedded media belongs only to its own scene; and that captions, overlays and transitions "for the clips" are timed per clip from the timeline. Action lines must name the object and operation ("Rewriting Scene 01 around the wheel video…"), not "Updating…".
- The Program Monitor keeps one stable composite page. It mounts every renderable clip when the edit has ≤12 clips; larger edits mount clips around the playhead plus transition participants. CCTransitions applies visibility inside the page, and the iframe is rebuilt only when the mounted set, transitions or a code hash change. Crossing an overlay/caption boundary no longer replaces `srcdoc` or blanks the monitor, and playback no longer alternates between single-scene and composite previews.
- Only active layers are seeked on each time update. A layer that becomes visible is seeked immediately; active media layers play during live playback and pause when hidden. Composite media layers now map local time to the whole clip (`sourceIn`), and `mediaWrapperHtml` listens for host seek messages, so scrubbing a media clip in a composite lands on the correct frame.
- The renderer waits for `loadeddata`/`canplay` before seeking an unbuffered video, then waits for `requestVideoFrameCallback` (with a real-time fallback) and a double rAF after layer changes. Media waits use captured real timers because the control script replaces `setTimeout` with the virtual clock; a virtual-time timeout would deadlock the frame loop. The Node fallback (`playwright_render.mjs`) gained the same video seek/await and paint wait.
- Tests: new `_check_composite_stability.py` (mount survives the cut, seeks both scenes, pixel probes red/blue/lit), `_check_video_render_frames.py` (scene-embedded three-colour video plus transparent overlay exports red/green/blue at the right times with no black frames), `_check_scene_media_context.py` (asset analysis reaches every chat context path and prompt rule). `_check_preview_seek.py`, `_check_preview_export_parity.py` and `_check_chat_scenes.py` now run against a temporary APPDATA so the user's projects cannot skew them.
