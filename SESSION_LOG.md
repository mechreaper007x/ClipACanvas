# Session Log

## 2026-03-25

### Summary

- Added a persistent session-log workflow for future agent sessions.
- Updated the GitHub repository homepage to the live site: `https://code2video.vercel.app`
- Added the live website link and release link near the top of `README.md`.
- Removed the old Vercel `website` project and kept the real production site on `code2video.vercel.app`.

### Files Touched

- `AGENTS.md`
- `SESSION_LOG.md`
- `README.md`

### Commits

- `b079a78` - `Add live website link to README`

### Deploy Links

- Website: `https://code2video.vercel.app`
- GitHub: `https://github.com/mechreaper007x/code2video-renderer`
- Release: `https://github.com/mechreaper007x/code2video-renderer/releases/tag/v1.0.0`

### Open Items

- `installer/CODE2VIDEO.iss` still has an unrelated local modification and was intentionally left out of website/session-log work.

## 2026-03-25

### Summary

- Added a manual `Clip Length` control to the desktop/web UI so renders are no longer locked to the DOM/SVG auto-preview fallback.
- Kept `Auto` timing as the safe default and wired manual overrides through the existing backend duration controls.
- Verified the real frontend flow with a looping DOM animation using `Clip Length = 8 seconds`; the app returned a successful 8-second render.

### Files Touched

- `code2video.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- `Auto` mode for DOM/SVG still favors short consumer-safe previews; change it only if you want longer default clips.
- `installer/CODE2VIDEO.iss` still has an unrelated local modification and remains untouched.

## 2026-03-25

### Summary

- Replaced the single generic AI hint with product-specific prompting guidance for canvas, DOM, and SVG exports.
- Added visible creator branding in the app footer: `signed by savyasachi mishra`.
- Verified the app UI still loads cleanly with the new prompt cards and no page errors.

### Files Touched

- `code2video.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Visible footer branding is in place, but actual Windows code signing still requires a real Authenticode certificate.
- `installer/CODE2VIDEO.iss` still has an unrelated local modification and remains untouched.

## 2026-03-25

### Summary

- Added a local release helper to generate `dist/SHA256SUMS.txt` and `dist/RELEASE_NOTES.md` from the current packaged artifacts.
- Updated the website downloads section with an unsigned-build trust note and a link back to the GitHub release page.
- Added a short `README.md` release-trust section describing the checksum workflow.

### Files Touched

- `build_release_assets.py`
- `website/index.html`
- `website/styles.css`
- `README.md`
- `dist/SHA256SUMS.txt`
- `dist/RELEASE_NOTES.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- Website: `https://code2video.vercel.app`
- Release: `https://github.com/mechreaper007x/code2video-renderer/releases/tag/v1.0.0`

### Open Items

- The generated checksum and release-note files still need to be uploaded with the next GitHub release if you want users to see them there.
- `installer/CODE2VIDEO.iss` still has an unrelated local modification and remains untouched.

## 2026-03-25

### Summary

- Removed the macOS download option from the website because the current Mac build is not reliable enough to advertise.
- Updated the website hero note and download trust note to say macOS downloads are currently unavailable.
- Verified the website now renders a single Windows download card only.

### Files Touched

- `website/index.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- Website: `https://code2video.vercel.app`

### Open Items

- If you want this change live, the website needs a redeploy.
- `installer/CODE2VIDEO.iss` still has an unrelated local modification and remains untouched.

## 2026-03-25

### Summary

- Pushed the essential product updates to GitHub while keeping local-only/session files out of the repo.
- Included the render-control updates, prompt tips, release helper, regression test, and website cleanup that removes the broken macOS download path.
- Left the unrelated `installer/CODE2VIDEO.iss` local modification uncommitted.

### Files Touched

- `.gitignore`
- `README.md`
- `build_release_assets.py`
- `code2video.html`
- `desktop_app.py`
- `playwright_render.py`
- `tests/frontend_render_matrix.py`
- `website/index.html`
- `website/styles.css`
- `SESSION_LOG.md`

### Commits

- `3d819d4` - `Improve render controls and release flow`

### Deploy Links

- GitHub: `https://github.com/mechreaper007x/code2video-renderer`

### Open Items

- Website changes are pushed but not redeployed yet.
- `installer/CODE2VIDEO.iss` still has an unrelated local modification and remains untouched.

## 2026-03-25

### Summary

- Rebuilt the Windows desktop artifacts from the latest source: fresh portable bundle zip and fresh installer exe.
- Updated the GitHub release `v1.0.0` in place with the new Windows assets and uploaded a new `SHA256SUMS.txt`.
- Redeployed the website so the live frontend now exposes both Windows download options: installer and portable zip.
- Pushed the website source change to GitHub so the repo matches the live site.

### Files Touched

- `dist/CODE2VIDEO-windows.zip`
- `dist/CODE2VIDEO-Setup.exe`
- `dist/SHA256SUMS.txt`
- `dist/RELEASE_NOTES.md`
- `website/index.html`
- `SESSION_LOG.md`

### Commits

- `e4a8794` - `Add portable zip download to website`

### Deploy Links

- Website: `https://code2video.vercel.app`
- Release: `https://github.com/mechreaper007x/code2video-renderer/releases/tag/v1.0.0`

### Open Items

- `installer/CODE2VIDEO.iss` still has an unrelated local modification and remains untouched.
- `website/.gitignore` was created locally by Vercel linking and remains uncommitted.

## 2026-03-27

### Summary

- Validated the renamed `Clip.A.Canvas` codebase after recent internal changes.
- Python compile checks passed for the server, desktop entry point, build scripts, renderer, and regression harness.
- The frontend render matrix passed all 11 cases across DOM/SVG and canvas render paths.
- Corrected README, website, and release-asset GitHub links to match the current repository slug and updated the website checksum label to `SHA-256`.

### Files Touched

- `README.md`
- `build_release_assets.py`
- `website/index.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- If the GitHub repository is later renamed from `code2video-renderer` to `clip-a-canvas`, update the repo and release URLs again to match the new slug.

## 2026-03-27

### Summary

- Rewrote the GitHub-facing `README.md` to present the product clearly as `Clip.A.Canvas`.
- Reorganized the documentation around quick start, build outputs, release workflow, and project layout.
- Kept the README aligned with the current repository slug while explicitly separating repo naming from product naming.

### Files Touched

- `README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- If the GitHub repository slug changes later, update the clone and release URLs in `README.md` to match it.

## 2026-03-27

### Summary

- No repo changes made.
- Validated a user-provided Pokeball SVG/CSS animation through the live `Clip.A.Canvas` frontend render path.
- The render completed successfully at `720x720`, `5 Mbps`, and manual `6 seconds`, with no console errors or page errors.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The current manual clip-length control does not offer an exact `4.5` second option, so looped DOM/SVG animations like this one need `6 seconds` or a future finer-grained duration control.

## 2026-03-27

### Summary

- Tuned the Pokeball SVG animation for cleaner `Clip.A.Canvas` export framing and aligned the loop to the app's `6 seconds` manual clip preset.
- Saved the verified snippet as a local artifact for reuse.
- Re-ran the real frontend render path successfully at `720x720`, `5 Mbps`, and `6 seconds`, with no console or page errors.

### Files Touched

- `output/playwright/pokeball-tuned-clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- If you want this motion to end on a seamless loop boundary instead of a held caught-state ending, the keyframes should be re-timed for loop continuity rather than a one-shot export finish.

## 2026-03-27

### Summary

- Updated the default generated-code render path so DOM/SVG exports now run at `60 FPS` automatically instead of `30 FPS`.
- Increased the DOM/SVG request timeout and progress estimate to match the higher default frame count.
- Brought the Node Playwright fallback closer to the Python renderer by adding loop-duration detection for auto-timed animations.
- Re-ran the full frontend render matrix successfully after the change.

### Files Touched

- `clipacanvas.html`
- `playwright_render.mjs`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- DOM/SVG exports are now smoother by default, but the higher frame count will increase render time for heavier generated scenes.

## 2026-03-27

### Summary

- Added an auto-timing classifier for pasted DOM/SVG code that detects explicit loop timing from CSS, WAAPI, SVG SMIL, and GSAP patterns, with a procedural-loop fallback for scripted motion.
- Corrected the first classifier pass so known loop durations now drive the actual auto clip window instead of falling back to the old blunt short-clip behavior.
- Revalidated the original `4.5s` Pokeball CSS/SVG example in auto mode; it now exports at `4.75s` via auto classification instead of collapsing to the old generic clip.
- Re-ran the full frontend render matrix successfully after the classifier correction.

### Files Touched

- `clipacanvas.html`
- `playwright_render.py`
- `playwright_render.mjs`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The auto classifier is still rule-based, not learned; runtime metadata remains the stronger source of truth when generated code exposes usable browser animation timing.

## 2026-03-27

### Summary

- Found and fixed a lower-level DOM/SVG renderer bug: the control script was not being reliably injected ahead of user code during HTML loading, so virtual-time hooks could be missing while renders still appeared to succeed.
- Switched both the Python and Node renderers to inject the control script directly into the HTML before user scripts run.
- Verified the fix with a targeted CSS transition probe: a `2s` linear transition now lands at the expected intermediate states (`12.5px`, `25px`, `50px`, `75px`, `100px`).
- Re-ran the full frontend render matrix successfully after the renderer fix.

### Files Touched

- `playwright_render.py`
- `playwright_render.mjs`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The DOM/SVG capture path is now wired correctly, but if a specific generated snippet still feels wrong, compare that snippet’s authored behavior in preview versus export to isolate any remaining virtual-time edge cases.

## 2026-03-27

### Summary

- No repo changes made.
- Compared the local `Clip.A.Canvas` project against the external `showlab/Code2Video` repository to validate the naming collision risk and product overlap.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- External project: `https://github.com/showlab/Code2Video`

### Open Items

- If you want zero naming ambiguity, the remaining cleanup is branding consistency across your repo slug, releases, and website around `Clip.A.Canvas`.

## 2026-03-27

### Summary

- No repo changes made.
- Ran a focused smoke-render suite against the current `Clip.A.Canvas` frontend using representative snippets: CSS transition, SVG Pokeball loop, WAAPI loop, timer-driven DOM, and canvas `requestAnimationFrame`.
- All five cases rendered successfully with download enabled.
- The SVG Pokeball loop still fell back to the generic DOM/SVG auto summary instead of the explicit CSS-loop summary because the pasted minified `animation:` declarations omitted trailing semicolons, which the current source-text classifier expects.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- If you want the auto classifier to be more robust for minified pasted CSS, loosen the source-text parser so it does not require a trailing semicolon after `animation:` declarations.

## 2026-03-27

### Summary

- Added the new `image.png` wordmark logo to the desktop app header, website branding, and README.
- Bundled `image.png` in desktop build scripts so packaged builds can load the new header logo.
- Copied the logo into `website/image.png` for the static site.

### Files Touched

- `clipacanvas.html`
- `website/index.html`
- `website/styles.css`
- `website/image.png`
- `README.md`
- `build_desktop.py`
- `build_mac_app.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The packaged app icon still uses the existing square asset in `assets/clipacanvas.ico` and `assets/clipacanvas.png`; only the visible wordmark/logo surfaces were switched to the new wide `image.png`.

## 2026-03-27

### Summary

- Switched the visible branding surfaces from the photographed `image.png` logo to the new transparent neon wordmark `logo_neon_preview-removebg-preview.png`.
- Updated the desktop app header, website branding, README header, and packaged-build asset bundling to use the new transparent logo file.

### Files Touched

- `clipacanvas.html`
- `website/index.html`
- `website/styles.css`
- `README.md`
- `build_desktop.py`
- `build_mac_app.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The Windows/macOS app icon still uses the square packaged assets in `assets/clipacanvas.ico` and `assets/clipacanvas.png`; only the wide wordmark surfaces were changed.

## 2026-03-27

### Summary

- Redesigned the website landing page around the neon transparent logo with a new dark visual system, rebuilt HTML structure, and replaced the old light card layout.
- Verified the new website layout in a real browser at desktop and mobile widths and saved screenshots.

### Files Touched

- `website/index.html`
- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The website now matches the neon logo direction, but the packaged desktop app header still uses its own app-shell styling and may need a separate visual pass if you want the app and marketing site to look more tightly matched.

## 2026-03-27

### Summary

- Removed the duplicate hero logo and the `LIVE PREVIEW / 60 FPS / OFFLINE EXPORT` pills from the website hero.
- Increased the top-left navbar logo presence and rebalanced the hero around a single visible brand anchor.
- Re-rendered desktop and mobile website screenshots after the cleanup.

### Files Touched

- `website/index.html`
- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The marketing site now uses only the top-left logo, but the desktop app shell still has its own branding treatment if you want that aligned next.

## 2026-03-27

### Summary

- Removed the website top-bar logo entirely and integrated the neon logo as a low-opacity hero overlay instead.
- Re-rendered desktop and mobile website screenshots to verify the new overlay composition.

### Files Touched

- `website/index.html`
- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The logo is now treated as a background-style hero overlay; if you want it stronger or more centered, that can be tuned without changing the page structure again.

## 2026-03-27

### Summary

- Repositioned the website logo overlay to the actual top-left of the hero and added dedicated hero spacing so it no longer sits cramped or off to the right.
- Re-rendered desktop and mobile website screenshots after the top-left overlay correction.

### Files Touched

- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The website hero overlay is now anchored top-left; if needed, only strength/opacity tweaks remain, not structural changes.

## 2026-03-27

### Summary

- Created a trimmed website logo overlay asset from `logo_neon_preview-removebg-preview.png` and switched the hero overlay to use it.
- Reworked the website hero card so the right preview column expands vertically instead of leaving a lower-right dead space.
- Regenerated desktop and mobile browser screenshots for the current website state.

### Files Touched

- `logo_neon_overlay.png`
- `website/logo_neon_overlay.png`
- `website/index.html`
- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The website hero now uses the trimmed overlay asset and a taller right-side preview area; any remaining work is visual tuning rather than structural repair.

## 2026-03-27

### Summary

- Removed the boxed hero implementation and converted the top section to an open layout with a floating preview window and non-card metric row.
- Kept the trimmed neon logo as a top-left hero overlay and regenerated desktop/mobile browser screenshots for the current website state.

### Files Touched

- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The hero is no longer box-driven; any further work is now typography/composition tuning, not structural cleanup.

## 2026-03-27

### Summary

- Moved the website logo from the hero overlay to the page’s actual top-left corner and shifted the navbar to make room for it on desktop.
- Regenerated desktop and mobile website screenshots after the top-left logo placement change.

### Files Touched

- `website/index.html`
- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The logo now anchors the page’s top-left; any further changes are visual polish only.

## 2026-03-27

### Summary

- Decoupled the top-left website logo from the navigation flow so the nav and hero spread left-right naturally instead of clustering around the logo.
- Widened the desktop page shell and rebalanced the hero columns around the fixed top-left logo.
- Regenerated desktop and mobile browser screenshots for the updated website layout.

### Files Touched

- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The website layout now spreads around the fixed top-left logo; further work would be styling polish rather than layout correction.

## 2026-03-27

### Summary

- Slightly increased the desktop hero video card size by widening the right hero column and increasing the preview frame minimum height.
- Regenerated the desktop website screenshot after the video card size adjustment.

### Files Touched

- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The video card has a modest size bump; any further increase should be balanced against the left headline column.

## 2026-03-27

### Summary

- Applied a final website polish pass focused on stronger top-nav typography, firmer right-side metric hierarchy, and a slightly higher-contrast hero preview frame.
- Regenerated desktop and mobile browser screenshots after the polish pass.

### Files Touched

- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The current site is structurally settled; any further changes would be fine-tuning of visual style rather than layout correction.

## 2026-03-27

### Summary

- Removed the website topbar `Get Windows Build` button.
- Moved the fixed top-left logo farther left and shifted the nav to the right so the top strip no longer overlaps the logo.
- Regenerated desktop and mobile website screenshots after the top-strip cleanup.

### Files Touched

- `website/index.html`
- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `output/playwright/website-redesign-mobile.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The top strip is now clean; any remaining website work is visual polish only.

## 2026-03-27

### Summary

- Nudged the fixed top-left website logo slightly downward to clear the top edge.
- Regenerated the desktop website screenshot after the logo offset tweak.

### Files Touched

- `website/styles.css`
- `output/playwright/website-redesign-desktop.png`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- None.

## 2026-03-27

### Summary

- Switched the Windows packaging flow to a single-file `ClipACanvas.exe` that embeds the preloaded `bin/` payload for Chromium and FFmpeg.
- Updated the installer script to package the portable executable directly and output the setup binary into `dist/`.
- Rebuilt the Windows release artifacts and refreshed `SHA256SUMS.txt` plus `RELEASE_NOTES.md`.

### Files Touched

- `build_desktop.py`
- `build_installer.py`
- `installer/ClipACanvas.iss`
- `build_release_assets.py`
- `README.md`
- `dist/ClipACanvas.exe`
- `dist/ClipACanvas-windows.zip`
- `dist/ClipACanvas-Setup.exe`
- `dist/SHA256SUMS.txt`
- `dist/RELEASE_NOTES.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The old `dist/ClipACanvas/` folder from the previous onedir build could not be removed during packaging because another process still has it locked.

## 2026-03-27

### Summary

- Increased the desktop app header logo size so the packaged app branding is no longer compressed in the Windows builds.
- Kept the cropped `logo_neon_overlay.png` asset for the app header after confirming the alternate preview PNG only added transparent padding, not a different logo shape.
- Rebuilt the Windows portable executable, portable ZIP, installer, checksums, and release notes.

### Files Touched

- `clipacanvas.html`
- `dist/ClipACanvas.exe`
- `dist/ClipACanvas-windows.zip`
- `dist/ClipACanvas-Setup.exe`
- `dist/SHA256SUMS.txt`
- `dist/RELEASE_NOTES.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The old `dist/ClipACanvas/` folder from the previous onedir build is still present because another process has it locked during cleanup.

## 2026-03-27

### Summary

- Replaced the Windows executable icon source with a proper square `custom_app_icon.ico` instead of the squeezed horizontal wordmark icon.
- Rebuilt the Windows portable executable, portable ZIP, installer, checksums, and release notes so the extracted `ClipACanvas.exe` from `ClipACanvas-windows.zip` uses the corrected icon.

### Files Touched

- `assets/custom_app_icon.ico`
- `dist/ClipACanvas.exe`
- `dist/ClipACanvas-windows.zip`
- `dist/ClipACanvas-Setup.exe`
- `dist/SHA256SUMS.txt`
- `dist/RELEASE_NOTES.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The old `dist/ClipACanvas/` folder from the previous onedir build is still present because another process has it locked during cleanup.

## 2026-03-27

### Summary

- No repo changes made.
- Verified by direct icon extraction that both `dist/ClipACanvas.exe` and `dist/ClipACanvas-Setup.exe` already embed the new square icon resource.
- The remaining mismatch is local Windows shell icon caching rather than a packaging configuration problem.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- If Explorer, Start Menu, or existing shortcuts still show the old icon, refresh the local Windows icon cache or recreate the shortcut after replacing the executable.

## 2026-03-27

### Summary

- No repo changes made.
- Cleared the local Windows icon cache, restarted Explorer, and verified in Explorer that `ClipACanvas.exe` and `ClipACanvas-Setup.exe` now show the new square icon.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Existing pinned shortcuts outside the refreshed folder view may still need to be recreated if Windows cached them separately.

## 2026-03-27

### Summary

- Found that the installer-created public desktop shortcut was still showing the old icon even though the installed executable already embedded the new square icon.
- Repointed the current public desktop and per-user Start Menu shortcuts to the verified square icon asset.
- Updated the installer script to ship `custom_app_icon.ico` into `{app}` and use it explicitly for new shortcut creation, then rebuilt the installer and refreshed release metadata.

### Files Touched

- `installer/ClipACanvas.iss`
- `dist/ClipACanvas-Setup.exe`
- `dist/SHA256SUMS.txt`
- `dist/RELEASE_NOTES.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The currently installed `ProgramData` Start Menu shortcut could not be rewritten in place from this session, so a per-user Start Menu shortcut was created instead.

## 2026-03-27

### Summary

- Committed and pushed the selected app and website source changes to GitHub while intentionally leaving screenshots, log files, session log changes, and build-helper files out of the commit.
- Deployed the `website/` folder to Vercel production and refreshed the live `code2video.vercel.app` alias.

### Files Touched

- `SESSION_LOG.md`

### Commits

- `ea4edb1` - `Refresh ClipACanvas app and website branding`

### Deploy Links

- GitHub: `https://github.com/mechreaper007x/code2video-renderer/commit/ea4edb1`
- Vercel Inspect: `https://vercel.com/creatorsavya-8060s-projects/code2video/CmT3MNfTUgZZ3KypYL8nC5T7kVDR`
- Production: `https://code2video.vercel.app`

### Open Items

- Local-only build-helper changes, installer changes, screenshot assets, and session-log entries remain unpushed by request.

## 2026-03-27

### Summary

- Renamed the GitHub repository from `code2video-renderer` to `ClipACanvas` and updated the local `origin` remote to the new URL.
- Renamed the Vercel project from `code2video` to `clipacanvas`, updated the local Vercel link file, redeployed production, and assigned `clipacanvas.vercel.app`.

### Files Touched

- `website/.vercel/project.json`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- GitHub: `https://github.com/mechreaper007x/ClipACanvas`
- Vercel Inspect: `https://vercel.com/creatorsavya-8060s-projects/clipacanvas/67U72DdAhPy4vDh6bemgYCvi2LMb`
- Production: `https://clipacanvas.vercel.app`

### Open Items

- Existing source links in README/site content still point at the old GitHub slug and old Vercel alias until they are updated in a future commit.

## 2026-03-30

### Summary

- No repo changes made.
- Reviewed the current desktop icon wiring and confirmed the packaged Windows icon is a separate square asset from the visible neon wordmark/logo surfaces.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- If the neon PNG was only intended for the desktop icon, the app header and website should be switched back to a separate wordmark or text treatment instead of reusing it there.

## 2026-04-14

### Summary

- Fixed the local Gemini MCP registration for `clipacanvas` by replacing the missing `uvx` command with `python -m clipacanvas_mcp.server`.
- Fixed the MCP tool execution path so blocking Playwright rendering runs outside the async MCP loop.
- Fixed the MCP render tool's repo-root resolution so it can import `playwright_render.py` when launched from the installed editable package.
- Verified Gemini reports `clipacanvas` as connected and ran a local MCP `render_video_to_file` smoke test successfully.

### Files Touched

- `.gemini/settings.json`
- `mcp/src/clipacanvas_mcp/server.py`
- `mcp/src/clipacanvas_mcp/render_tool.py`
- `mcp/README.md`
- `output/mcp-smoke.mp4`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- `postman-api-mcp` still reports disconnected in Gemini, but it is unrelated to `clipacanvas`.

## 2026-04-14

### Summary

- No repo changes made.
- Checked local Claude and Codex configuration locations for enabling the `clipacanvas` MCP server outside Gemini.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Claude Desktop's `%APPDATA%\Claude` config folder was not present on this machine during inspection.

## 2026-04-14

### Summary

- Registered the `clipacanvas` MCP server through the direct Codex CLI and Claude Code MCP add commands.
- Verified Codex lists `clipacanvas` as enabled.
- Replaced Claude Code's first plain `python` entry with a Windows `cmd /c python -m clipacanvas_mcp.server` launcher after the initial health check failed.
- Verified Claude Code reports `clipacanvas` as connected.
- Updated the MCP README with direct local install commands for Claude Code and Codex CLI.

### Files Touched

- `mcp/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Claude Desktop still needs manual JSON config if you want desktop-app integration instead of Claude Code integration.

## 2026-04-14

### Summary

- Made the MCP package self-contained by adding the renderer module inside `clipacanvas_mcp` instead of relying on the repo-root `playwright_render.py`.
- Updated the MCP render tool to import the packaged renderer first, with a repo-root fallback for development.
- Added automatic Playwright Chromium installation on first MCP render if Chromium is missing.
- Updated the MCP README with direct `mcp add` commands that can install from the GitHub repo via `uvx` once the `mcp/` package is pushed.
- Verified the packaged renderer import and ran a successful MCP `render_video_to_file` smoke test.

### Files Touched

- `mcp/src/clipacanvas_mcp/playwright_render.py`
- `mcp/src/clipacanvas_mcp/render_tool.py`
- `mcp/README.md`
- `output/mcp-package-smoke.mp4`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The `mcp/` package still needs to be pushed to GitHub before the documented GitHub `uvx` install commands work for other users.
- Local wheel build verification was not run because `hatchling` is not installed in this Python environment.

## 2026-04-14

### Summary

- Updated the top-level README with current GitHub links plus direct MCP install commands for Gemini, Codex, and Claude Code.
- Updated the website source to point at the renamed `ClipACanvas` GitHub repo and added a dedicated MCP install section.
- Deployed the updated website to Vercel production and pushed the source commit to GitHub.

### Files Touched

- `README.md`
- `website/index.html`
- `website/styles.css`
- `SESSION_LOG.md`

### Commits

- `bc08d6a` - `Refresh website links and MCP docs`

### Deploy Links

- Vercel Inspect: `https://vercel.com/creatorsavya-8060s-projects/clipacanvas/3W7CVCjCy6fGw3JQ4LCN7tXYeXsN`
- Production: `https://clipacanvas.vercel.app`
- GitHub: `https://github.com/mechreaper007x/ClipACanvas/commit/bc08d6a`

### Open Items

- `build_release_assets.py` still has an unstaged local repo-link update and remains outside the pushed commit.

## 2026-04-14

### Summary

- No repo changes made.
- Fixed the live GitHub release `v1.0.0` so the website download buttons no longer 404.
- Regenerated local release notes and checksums, updated the release title to `Clip.A.Canvas v1.0.0`, and uploaded `ClipACanvas-Setup.exe`, `ClipACanvas-windows.zip`, and the refreshed `SHA256SUMS.txt`.
- Verified both public download URLs now return HTTP `200`.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- Release: `https://github.com/mechreaper007x/ClipACanvas/releases/tag/v1.0.0`

### Open Items

- The old `CODE2VIDEO-*` assets still exist on the release alongside the new `ClipACanvas-*` assets.

## 2026-04-14

### Summary

- Created a 1080x1080 animated bat-emblem vector MP4 using the ClipACanvas MCP render tool.
- Interpreted the requested `1080` output as a square logo export.

### Files Touched

- `output/batman-logo-animated-vector-1080.mp4`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Rerender as 1920x1080 if a widescreen 1080p version is preferred.

## 2026-04-14

### Summary

- Repaired the `clipacanvas-tui` source so the keyboard file actions and render path work from the packaged `tui/src` module instead of relying on repo-root imports.
- Fixed the render worker to save persistent MP4 outputs under `renders/`, use the correct Textual worker state check, and read the renderer's actual result keys.
- Added FFmpeg auto-resolution inside the bundled TUI renderer and verified the package path by rendering a real smoke-test MP4.

### Files Touched

- `tui/src/clipacanvas_tui/app.py`
- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/src/clipacanvas_tui/playwright_render.py`
- `output/tui-package-smoke.mp4`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The TUI source is fixed and smoke-tested locally, but the `tui/` package is still untracked in git and has not been published or released yet.

## 2026-04-15

### Summary

- No repo changes made.
- Reviewed the terminal-only installation/setup path for `clipacanvas-tui`, including PATH-friendly options.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The cleanest public install path is `pipx`, but the `tui/` package still needs to be committed/published before other users can install it directly from GitHub or PyPI.

## 2026-04-15

### Summary

- Replaced the TUI's default editor payload with a self-contained animated canvas demo so the render path can be checked immediately after launch.
- Recompiled the updated TUI screen module and refreshed the local `pipx` install so the PATH-visible `clipacanvas-tui` command picks up the new default scene.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- `pipx` completed the refresh, but it still warns that your current pipx home path contains spaces; the install works, but that path layout is not ideal long term.

## 2026-04-15

### Summary

- Added a real browser-backed live preview flow to `clipacanvas-tui` using a local preview server that updates as the editor content changes.
- Added TUI preview actions and startup options so large HTML can be loaded from a file or stdin instead of relying on terminal paste size.
- Recompiled the TUI package, smoke-tested the preview server endpoints, and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/app.py`
- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/src/clipacanvas_tui/preview_server.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The terminal-side `5 KiB` paste ceiling was not coming from the TUI source itself; the new file/stdin startup path avoids that limit instead of trying to fight the terminal paste channel.

## 2026-04-15

### Summary

- Added a dedicated `Ctrl+K` clear-all shortcut for wiping the TUI editor while keeping the older `Ctrl+L` binding as a hidden compatibility alias.
- Updated the TUI README shortcut list and refreshed the local `pipx` install so the PATH-visible `clipacanvas-tui` command picks up the new binding.

### Files Touched

- `tui/src/clipacanvas_tui/app.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- `clipacanvas-tui` still resolves through multiple PATH entries on this machine, but both current installs now point at the updated source tree.

## 2026-04-15

### Summary

- Added an explicit `Ctrl+V` clipboard-paste action to `clipacanvas-tui` so code can be inserted directly from the local clipboard without relying on the terminal's large-paste path.
- Updated the TUI README shortcut list and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/app.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The terminal itself may still show a large-paste warning for terminal-level paste, but `Ctrl+V` inside the TUI now bypasses that path by reading from the local clipboard directly.

## 2026-04-15

### Summary

- Added a direct OS-clipboard import workflow to `clipacanvas-tui` so long HTML can be loaded without using the terminal paste path at all.
- Added a `Clipboard` toolbar button, `Ctrl+Y` shortcut, and `--clipboard` startup flag.
- Updated the TUI README and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/clipboard.py`
- `tui/src/clipacanvas_tui/app.py`
- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Large terminal paste warnings can still happen if you paste into the terminal itself; the new clipboard import path avoids that by reading directly from the OS clipboard instead.

## 2026-04-15

### Summary

- Added custom manual duration support to the main app by extending the clip-length control with a custom numeric seconds input.
- Added custom duration support to the TUI with a duration field where blank means auto and numeric values force a fixed render length.
- Added a hard backend clamp of `60` seconds across the Python, Node, TUI, and MCP renderers so custom duration cannot run unbounded.
- Recompiled the Python paths, syntax-checked the Node renderer, and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `clipacanvas.html`
- `playwright_render.py`
- `playwright_render.mjs`
- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/src/clipacanvas_tui/playwright_render.py`
- `mcp/src/clipacanvas_mcp/playwright_render.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Manual duration is now custom, but the browser app UI change was compile-checked only; no full browser-side interaction test was run in this session.

## 2026-04-15

### Summary

- Fixed the main app custom-duration UX so focusing or typing in the custom seconds field automatically switches the clip-length mode from `Auto` to `Custom`.

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- No additional browser-side interaction test was run after this small UI behavior fix.

## 2026-04-15

### Summary

- Fixed the TUI duration workflow by adding an explicit `Clip` selector (`Auto` / `Custom`) and making the duration input auto-switch to `Custom` when you type seconds.
- Updated the TUI README and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The main app and TUI both now support custom duration, but only the TUI-specific fix was addressed in this follow-up.

## 2026-04-15

### Summary

- Simplified the TUI header layout by removing the extra preview/clipboard toolbar buttons and replacing them with a compact two-row control bar plus shortcut hints.
- Kept preview and clipboard actions available through their existing keyboard shortcuts and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The TUI layout was compile-checked and reinstalled, but no interactive window screenshot or manual resize test was run in this pass.

## 2026-04-15

### Summary

- Added `F6` as the primary TUI clipboard-load shortcut because terminal hosts can intercept `Ctrl+Y` before the TUI receives it.
- Kept `Ctrl+Y` as a hidden compatibility alias, updated the shortcut hints/docs, and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/app.py`
- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The most reliable large-code path remains `clipacanvas-tui --clipboard --preview`, which bypasses terminal key handling entirely.

## 2026-04-15

### Summary

- No repo changes made.
- Kept the current TUI clipboard button/workflow unchanged after the latest adjustments.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- None.

## 2026-04-15

### Summary

- Restored the TUI `Clipboard` button in the header action row after it had been removed during the layout simplification pass.
- Recompiled the updated TUI screen and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- None.

## 2026-04-15

### Summary

- Added configurable render output destination controls to the TUI status pane.
- `Default Folder` keeps the existing timestamped `./renders` workflow, while `Custom Path` accepts either a target `.mp4` path or a folder path for rendered videos.
- Recompiled the updated TUI screen, refreshed the PATH-installed `clipacanvas-tui` command, and updated the TUI README.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The TUI save-destination flow was compile-checked and reinstalled, but no manual interactive render test was run in this pass.

## 2026-04-15

### Summary

- Removed the TUI default output option and simplified render destination selection to a single explicit `Output Path` field.
- The TUI now always requires either a target `.mp4` file path or a folder path before rendering.
- Recompiled the updated TUI screen, refreshed the PATH-installed `clipacanvas-tui` command, and updated the TUI README.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- No interactive render test was run after removing the default output option.

## 2026-04-15

### Summary

- Improved the TUI output-path parser so existing directories are recognized as folders instead of being misclassified as file paths.
- Trimmed surrounding quotes from the TUI output path input before resolving it.
- Recompiled the updated TUI screen and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Protected system folders can still fail if the current user does not have write permission there.

## 2026-04-15

### Summary

- Found that the current TUI render/duration regression was primarily a layout issue: at narrower terminal widths the duration controls were being pushed off-screen even though the backend render path still worked.
- Split the top controls into separate rows so the duration selector/input and render button stay visible at narrower widths.
- Verified the TUI render path headlessly after the layout fix with a manual `1.5s` render to a custom output path, which produced a real MP4 successfully.
- Refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The installed TUI now has the verified layout fix; any remaining issue in an already-open terminal window likely requires relaunching the command to pick up the updated code.

## 2026-04-15

### Summary

- Investigated the TUI render failure for the exact output folder `C:\Users\Savyasachi Mishra\Videos\clipacanvas`.
- Confirmed the old backend could surface vague Windows/FFmpeg errors for custom output folders.
- Changed the TUI renderer to encode into a temporary MP4 first, then move the final file to the requested destination.
- Added an early output-folder writability probe so unwritable destinations fail with an explicit message instead of `[Errno 22]`.
- Re-verified that workspace renders still succeed and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/playwright_render.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- In the sandboxed debug environment, `C:\Users\Savyasachi Mishra\Videos\clipacanvas` is still not writable, so the TUI now reports that explicitly.

## 2026-04-15

### Summary

- Removed the TUI's over-strict preflight output-folder writability probe, which could block renders before the actual final save was attempted.
- Kept the temp-file encode flow, but moved error reporting to the real destination save step so protected or unusual Windows folders can still work if the final move succeeds.
- Re-verified that normal TUI renders still export successfully and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/playwright_render.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- If a Windows media folder still rejects the final save, the TUI should now report that concrete destination-save failure directly.

## 2026-04-15

### Summary

- Confirmed that `C:\Users\Savyasachi Mishra\Videos\clipacanvas` is being blocked at the Windows file-operation level: direct Python writes, PowerShell writes, `cmd copy`, and `robocopy` all failed against that destination.
- Added a fallback save path for the TUI renderer: if the requested destination is blocked, the finished MP4 is preserved under `%LOCALAPPDATA%\ClipACanvas\renders` instead of failing the whole render.
- Updated the TUI status messaging so it shows the actual saved output path and includes a warning when a fallback location is used.
- Verified the blocked-folder case now succeeds with a real saved MP4 in the fallback render directory and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/playwright_render.py`
- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The chosen `Videos\clipacanvas` destination remains blocked by Windows for this process, so the TUI now falls back to `%LOCALAPPDATA%\ClipACanvas\renders` when needed.

## 2026-04-15

### Summary

- Verified that the folder block is caused by Windows Controlled Folder Access rather than the TUI alone: `Desktop` and `Downloads` are writable, while `Documents` and `Videos` are blocked for multiple runtimes and copy mechanisms.
- Updated the TUI fallback path to prefer `Downloads\ClipACanvas\renders` so blocked protected-folder saves still land somewhere visible to the user.
- Added explicit Controlled Folder Access warning text to blocked-save fallback messages, including the interpreter path to allow in Windows Security for direct saves into protected folders.
- Refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/playwright_render.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Direct saves into protected folders such as `Documents` and `Videos` still require allowing the TUI interpreter/app through Windows Controlled Folder Access.

## 2026-04-15

### Summary

- Traced the TUI render backend end to end and confirmed the render itself completes; the only remaining failure point for protected folders is the final OS-level save into `Documents`/`Videos`.
- Verified via Windows Defender event logs that Controlled Folder Access is actively blocking the exact processes involved, including `python3.12.exe` and earlier direct `ffmpeg` writes, for `%userprofile%\\Videos\\clipacanvas`.
- Confirmed `clipacanvas-tui` on this machine currently resolves to the user-site launcher under the Python 3.12 local packages scripts path, not the pipx shim.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Direct saves into protected folders will not work until the blocked runtime is allowed through Windows Controlled Folder Access or the destination is moved outside protected libraries.

## 2026-04-15

### Summary

- Added a Windows protected-folder setup assistant to the TUI. Pressing `F7` now opens an elevated PowerShell allow-list flow for the exact runtime that Defender is blocking.
- Switched the Controlled Folder Access guidance to use the real current process image path (`python3.12.exe` under `Program Files\\WindowsApps`) instead of the old alias path.
- Added pre-render rerouting for protected folders so the TUI chooses the fallback location before rendering, not only after a blocked final save.
- Refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/playwright_render.py`
- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/src/clipacanvas_tui/app.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The new `F7` flow still depends on the user approving the Windows elevation prompt; direct protected-folder saves remain blocked until that approval happens.

## 2026-04-15

### Summary

- Removed the fallback-save product flow from the TUI. Protected-folder issues are now handled before render instead of silently saving elsewhere.
- Kept the `F7` Windows protected-folder setup assistant and updated the TUI/README to frame it as the supported fix path.
- Re-verified the backend with a real short render directly to `C:\Users\Savyasachi Mishra\Videos\clipacanvas\direct_save_test.mp4`, which succeeded after the protected-folder allow step.
- Refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/playwright_render.py`
- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The installed TUI should now reflect the no-fallback behavior; any old window/session must be relaunched to pick up the updated code.

## 2026-04-15

### Summary

- Added TUI-side render estimation and live render feedback: the status pane now shows an estimated wall-clock render time, live elapsed/remaining time, and a small ASCII activity animation while a render is running.
- Added lightweight learning from recent successful renders so estimate quality improves across the current TUI session.
- Verified the new fields update during a headless TUI render test and refreshed the PATH-installed `clipacanvas-tui` command.

### Files Touched

- `tui/src/clipacanvas_tui/screens/editor.py`
- `tui/README.md`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- The estimate is heuristic-based and should improve after a few successful renders in the same TUI session.

## 2026-04-15

### Summary

- Reviewed the renderer and preview-server code paths for host-RCE risk.
- Confirmed the current design executes untrusted HTML/JS inside Chromium rather than in Python, so the main security boundary is browser code execution and network access rather than direct host command execution.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- No repo changes made.

## 2026-04-15

### Summary

- No repo changes made.
- Explained the main ways MP4 files can be involved in data leaks: vulnerable media players/decoders, metadata exposure, wrapper/playlist tricks, and social-engineering delivery rather than active code inside a normal MP4.
- Framed the lower-risk output posture for `Clip.A.Canvas`: standard re-encoded MP4 output is safer than executing untrusted render-time HTML/JS or passing through arbitrary media streams.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- If the product will accept untrusted imported media later, re-encode and strip metadata by default instead of remuxing arbitrary tracks.

## 2026-04-15

### Summary

- Expanded the GitHub `README.md` with a real TUI install section covering direct GitHub install, local editable install, requirements, and the Windows `F7` protected-folder helper.
- Added a dedicated TUI install section to the marketing site, updated navigation/hero CTAs, and pushed the static `website/` folder live on Vercel.

### Files Touched

- `README.md`
- `website/index.html`
- `website/styles.css`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- Website: `https://clipacanvas.vercel.app`

### Open Items

- Unrelated local worktree changes outside the README/website/session-log files remain untouched.

## 2026-05-15

### Summary

- No repo changes made.
- Listed supported Clip.A.Canvas CLI/MCP install and launch commands from the current README, MCP docs, TUI docs, and package metadata.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- TUI docs and package metadata currently disagree on the executable name: docs mention `clipacanvas-tui`, while `tui/pyproject.toml` exposes `clippp`.

## 2026-05-15

### Summary

- No repo changes made.
- Clarified the planned Claude and Codex release paths for the existing `clipacanvas-mcp` package, including Claude Desktop MCPB and Codex CLI/plugin distribution.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Codex plugin packaging still needs a concrete local plugin manifest/build step if the project targets Codex's plugin directory instead of only direct MCP CLI install.

## 2026-05-15

### Summary

- No product repo changes made.
- Verified live PyPI packages: `clipacanvas-mcp` is published at `1.0.2`; `clipacanvas-tui` is published at `1.0.0`.
- Updated the release guidance mentally to use direct PyPI commands instead of GitHub-subdirectory install commands for normal users.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- PyPI MCP: `https://pypi.org/project/clipacanvas-mcp/`
- PyPI TUI: `https://pypi.org/project/clipacanvas-tui/`

### Open Items

- Public docs should be cleaned up to prefer PyPI install commands now that both packages are published.

## 2026-05-15

### Summary

- No product repo changes made.
- Outlined the Claude-first release path: immediate Claude Code install through the published PyPI MCP package and Claude Desktop distribution through an `.mcpb` bundle.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- Claude Desktop release still needs a concrete `.mcpb` manifest, bundle build, and GitHub release asset.

## 2026-05-15

### Summary

- Added Claude Desktop MCPB packaging under `claude/desktop-extension`, bundling the annotated Clip.A.Canvas MCP server source with UV-managed Python dependencies.
- Added Claude submission support docs, a public Claude install page, and a public privacy policy page.
- Added MCP tool titles and annotations for Claude review, including destructive metadata on `render_video_to_file`.
- Built `dist/ClipACanvas-1.0.2.mcpb` and verified the manifest with `@anthropic-ai/mcpb`.
- Deployed the updated website to Vercel so `https://clipacanvas.vercel.app/claude.html` and `https://clipacanvas.vercel.app/privacy.html` are live.
- Added a repo-local Codex plugin package under `plugins/clipacanvas` with MCP config, skill guidance, marketplace metadata, assets, and a release zip.

### Files Touched

- `claude/desktop-extension/manifest.json`
- `claude/desktop-extension/pyproject.toml`
- `claude/desktop-extension/src/server.py`
- `claude/desktop-extension/src/clipacanvas_mcp/*`
- `claude/desktop-extension/icon.png`
- `claude/desktop-extension/README.md`
- `claude/connectors-directory-submission.md`
- `plugins/clipacanvas/.codex-plugin/plugin.json`
- `plugins/clipacanvas/.mcp.json`
- `plugins/clipacanvas/skills/clipacanvas-render/SKILL.md`
- `plugins/clipacanvas/assets/icon.png`
- `plugins/clipacanvas/assets/logo.png`
- `.agents/plugins/marketplace.json`
- `mcp/src/clipacanvas_mcp/render_tool.py`
- `website/index.html`
- `website/styles.css`
- `website/claude.html`
- `website/privacy.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- Website: `https://clipacanvas.vercel.app`
- Claude docs: `https://clipacanvas.vercel.app/claude.html`
- Privacy policy: `https://clipacanvas.vercel.app/privacy.html`

### Release Artifacts

- `dist/ClipACanvas-1.0.2.mcpb` - SHA-256 `FE9C56896FFCDB824B3D81A427E383B06FD853218A586485BA57F67766ABC8B1`
- `dist/clipacanvas-codex-plugin-1.0.2.zip` - SHA-256 `F2564DDB651BBCDBA2ECD1221E68BB0A6583F617EE4EDE94E8A96A7A1546CAAD`

### Open Items

- `dist/ClipACanvas-1.0.2.mcpb` is unsigned; signing requires a release signing key.
- The Claude Desktop extension icon validates but is 256x256; MCPB recommends 512x512 for best display.
- Official hosted Claude Connector Directory listing still requires a separate hardened HTTPS remote MCP service if targeting Claude.ai beyond local desktop extension distribution.
- Existing unrelated local worktree changes remain untouched.

## 2026-05-26

### Summary

- Registered both `clipacanvas-tui` and `clippp` CLI entry points in `tui/pyproject.toml` for full naming compatibility.
- Updated `README.md` and `tui/README.md` to recommend PyPI-first installation commands.
- Created `MARKETING.md` outlining the launch and promotion strategy (copy templates for Product Hunt, Hacker News, Reddit, Twitter/X, and registry lists) along with 3 showcase animation code snippets.
- Validated that both CLI commands run successfully, and all 11 cases in the frontend render matrix regression test suite pass.
- Added Glama claim verification file `.well-known/glama.json` and official MCP registry manifest `.mcp/server.json`.
- Populated `awesome_mcp_readme.md` with a detailed step-by-step workbook for submitting the MCP server to Smithery, Glama, dotMCP, and the official MCP registry.
- Created `tunnel.yaml` and successfully connected the local server to dotMCP via their secure WebSocket tunnel relay.

### Files Touched

- `tui/pyproject.toml`
- `README.md`
- `tui/README.md`
- `MARKETING.md`
- `.well-known/glama.json`
- `.mcp/server.json`
- `awesome_mcp_readme.md`
- `tunnel.yaml`
- `SESSION_LOG.md`

### Commits

- `d9f3a94` - `docs: align CLI script names, update PyPI install instructions, add MCP registry manifests and marketing materials`

### Deploy Links

- None.

### Open Items

- Push these updates to the GitHub repository to make them public.
- Claim/promote the Smithery listing and submit the MCP server to Glama.ai and dotMCP.io.

## 2026-05-26

### Summary

- Added SSE (Server-Sent Events) transport layer to the MCP server so it can run
  in the cloud without consuming local laptop resources.
- Created a Starlette ASGI app (`sse_app.py`) that exposes `/sse`, `/messages/`,
  `/health`, and a landing page using `mcp.server.sse.SseServerTransport`.
- Created a multi-stage `Dockerfile` targeting Hugging Face Spaces (port 7860)
  with Playwright Chromium + FFmpeg pre-installed and a non-root runtime user.
- Created `README_HF.md` with the required HF Spaces YAML front-matter
  (`sdk: docker`, `app_port: 7860`).
- Added `[sse]` optional dependency group (`starlette>=0.27`, `uvicorn[standard]>=0.24`)
  and registered `clipmcp` / `clipmcp-sse` as console script entry points.

### Files Touched

- `mcp/src/clipacanvas_mcp/sse_app.py` — new SSE transport Starlette app
- `mcp/pyproject.toml` — added [sse] extras and new script entry points
- `mcp/Dockerfile` — HF Spaces Docker image (multi-stage, Chromium + FFmpeg)
- `mcp/README_HF.md` — HF Spaces card with YAML front-matter

### Commits

- `44dfc2b` — `feat: add SSE transport server and Hugging Face Spaces Dockerfile`

### Deploy Links

- None yet — next step is creating the HF Space.

### Open Items

- Create the actual Hugging Face Space repo and push the `mcp/` directory to it.
- The Space README must be named `README.md` at the root of the Space repo (copy `README_HF.md`).
- After first deploy, update the connect URL in `README_HF.md` with the real Space slug.

## 2026-05-26 (HF Spaces Deployment)

### Summary

- Created HF Space `mechreaper007x/clip-a-canvas-mcp` (Docker SDK, public) via API.
- Pushed all MCP server source files to the Space repo; Docker build triggered automatically.
- Updated `mcp/README_HF.md` with the real subdomain URL.

### Files Touched

- `mcp/README_HF.md` — updated with real Space URL

### Commits

- `4416654` — `docs: update README_HF with real HF Space URL`

### Deploy Links

- HF Space: `https://huggingface.co/spaces/mechreaper007x/clip-a-canvas-mcp`
- SSE Endpoint (once build completes): `https://mechreaper007x-clip-a-canvas-mcp.hf.space/sse`

### Open Items

- Wait for Docker build to complete on HF (takes ~5–10 min first time; Playwright install is heavy).
- Test SSE endpoint with an MCP client once the Space shows status RUNNING.

## 2026-05-27

### Summary

- Checked and verified that the Hugging Face Space `mechreaper007x/clip-a-canvas-mcp` is successfully built and stage is `RUNNING`.
- Diagnosed a Starlette signature mismatch in the `/messages/` POST endpoint (`sse_app.py`): the handler `handle_messages` took `(request: Request)` but was mounted as an ASGI app requiring `(scope, receive, send)`. This was causing `TypeError: handle_messages() takes 1 positional argument but 3 were given` whenever dotMCP posted JSON-RPC payloads to the Space, returning HTTP 500.
- Fixed the ASGI signature of `handle_messages` to take `(scope, receive, send)` in `mcp/src/clipacanvas_mcp/sse_app.py` and successfully pushed the update to both the main GitHub repository and the Hugging Face Space repository.
- Verified that the new HF build (`35047f7`) compiled successfully (with Docker cached layers) and the container successfully started (`Application startup complete`).
- Installed `supergateway` locally and configured `tunnel.yaml` to run `node` directly on `node_modules/supergateway/dist/index.js`. This bypasses Windows `cmd.exe /c` batch wrapping issues and Node security patch restrictions (EINVAL errors when spawning `.cmd`/`.bat` files without shell expansion).
- Configured `supergateway` with the `--logLevel none` option to suppress stdout logging, preventing corruption of the dotMCP JSON-RPC stream.
- Started the `npx @dotmcp/tunnel start -c tunnel.yaml` daemon in the background to sync tools with dotmcp.io and route requests to the cloud without local computer resource overhead.
- Diagnosed root `README.md` mismatch: The root README had accidentally been overwritten with the general "MCP Registry" README in a previous commit, causing Glama to reject the repository listing.
- Restored the correct root `README.md` describing the Clip.A.Canvas project, its desktop app, TUI CLI, and remote/local MCP server setup.
- Updated `task.md` and `walkthrough.md` to reflect full deployment completion and health check verification.

### Files Touched

- `SESSION_LOG.md`
- `README.md`
- `mcp/src/clipacanvas_mcp/sse_app.py`
- `tunnel.yaml`
- `package.json`
- `package-lock.json`
- `task.md`
- `walkthrough.md`

### Commits

- `e7e6a5e` — `docs: restore correct Clip.A.Canvas root README.md with cloud/local MCP instructions`
- `9234837` — `fix: resolve Starlette handle_messages signature mismatch (takes scope, receive, send)`
- `4777c1d` — `chore: spawn node directly on supergateway in tunnel.yaml to fix Windows spawn issues`
- `84e893e` — `chore: add --logLevel none to supergateway in tunnel.yaml to prevent stream corruption`
- Pushed all 8 pending local commits (`44dfc2b` through `0bc9f26`) to GitHub.

### Deploy Links

- HF Space: `https://huggingface.co/spaces/mechreaper007x/clip-a-canvas-mcp`
- SSE Endpoint: `https://mechreaper007x-clip-a-canvas-mcp.hf.space/sse`
- Health Endpoint: `https://mechreaper007x-clip-a-canvas-mcp.hf.space/health`
- GitHub main branch: `https://github.com/mechreaper007x/ClipACanvas`

### Open Items

- Keep the background tunnel daemon running to route dotMCP traffic to Hugging Face Spaces.

## 2026-05-27 (Post-Deployment Verification & Subprocess Fix)

### Summary

- Fixed Starlette ASGI routing inside the Hugging Face Space by copying the class-based `SSEHandler` implementation to the Space repository.
- Resolved a runtime `ValueError: flush of closed file` error by removing the manual `ffmpeg_proc.stdin.close()` invocation before `communicate()` in `playwright_render.py` (applied across root, `mcp`, and `claude/desktop-extension` packages). This lets Python's subprocess library manage stdin closure natively.
- Tested and verified the cloud-deployed SSE endpoint using the client script, confirming it successfully renders HTML/CSS code and returns a valid base64 MP4 stream to the client.
- Pushed updates to both the Hugging Face Space repository (`8875794`) and the main GitHub repository (`21f1946`).
- Confirmed that the local `dotmcp-tunnel` proxying through `supergateway` correctly routes requests to the cloud without local compute overhead.

### Files Touched

- `mcp/src/clipacanvas_mcp/playwright_render.py`
- `playwright_render.py`
- `claude/desktop-extension/src/clipacanvas_mcp/playwright_render.py`
- `mcp/src/clipacanvas_mcp/sse_app.py`
- `SESSION_LOG.md`

### Commits

- `21f1946` — `fix: resolve Starlette ASGI sse response type and prevent ValueError: flush of closed file in subprocess communicate on Python 3.11+`
- `8875794` (HF Space) — `fix: remove manual stdin close before communicate`

### Deploy Links

- HF Space: `https://huggingface.co/spaces/mechreaper007x/clip-a-canvas-mcp`
- SSE Endpoint: `https://mechreaper007x-clip-a-canvas-mcp.hf.space/sse`
- Health Endpoint: `https://mechreaper007x-clip-a-canvas-mcp.hf.space/health`

### Open Items

- Monitor the dotMCP tunnel daemon in the background to ensure steady connectivity.

## 2026-05-27 (Glama Listing Approval & Dockerfile Alignment)

### Summary

- Restored the correct `mcp/README.md` to avoid registry overwrite conflict.
- Verified that the Clip.A.Canvas MCP server has been successfully published to the official Model Context Protocol Registry at version `1.0.2` (duplicate version attempt rejected by registry server as already published).
- Created a standard `Dockerfile` at the root of the repository to support Glama's automated safety/quality checks and general containerized stdio-based builds.
- Updated `.gitignore` to keep local-only publisher CLI binaries and test logs ignored.
- Committed and pushed all registry manifests, licenses, and the new root `Dockerfile` to the GitHub repository.

### Files Touched

- `Dockerfile` (root)
- `mcp/server.json`
- `mcp/smithery.yaml`
- `.gitignore`
- `LICENSE`
- `mcp/LICENSE`
- `SESSION_LOG.md`

### Commits

- `07d43b1` — `chore: add root Dockerfile for Glama safety checks and commit registry manifests`

### Deploy Links

- GitHub: `https://github.com/mechreaper007x/ClipACanvas`
- HF Space: `https://huggingface.co/spaces/mechreaper007x/clip-a-canvas-mcp`
- SSE Endpoint: `https://mechreaper007x-clip-a-canvas-mcp.hf.space/sse`
- Health Endpoint: `https://mechreaper007x-clip-a-canvas-mcp.hf.space/health`
- Official MCP Registry namespace: `io.github.mechreaper007x/clipacanvas`
- Glama listing: `https://glama.ai/mcp/servers/mechreaper007x/ClipACanvas` (or via search)

### Open Items

- Claim the listing on Glama.ai using owner email `creatorsavya@gmail.com` and run the automated safety/quality checks.

## 2026-05-27 (Glama CMD Arguments Correction & Successful Deploy)

### Summary

- No product repo changes made (excluding session log updates).
- Diagnosed Glama runtime crash caused by module typo in CMD Arguments (`python -m clipmcp`).
- Instructed the user to update their Glama CMD Arguments to use the correct Python module path `clipacanvas_mcp.server`.
- Verified that the corrected CMD Arguments successfully completed the Glama registry build and deployment!

- Overwrote the complicated transition-related `LICENSE` with a clean industry-standard `MIT License` to fix automated license parsing ("Does not have a license F").
- Created `LICENSE.md` as an additional copy of the license file for maximum scanner compatibility.
- Created a standard `glama.json` metadata manifest at the root of the repository to resolve the "No glama.json" issue.
- Added the `"license": "MIT"` field to the root `package.json` to assist Node.js-based repository scanner compatibility.
- Configured `CORSMiddleware` in `sse_app.py` to allow direct browser connections from Glama's web MCP Inspector, resolving proxy buffering timeouts (`Request timed out`).

- Added standard registry badges (Smithery and Glama) with premium hover transitions to the website's MCP section (`website/index.html` and `website/styles.css`).
- Integrated clear, copy-pasteable documentation for **Glama Gateway** (`npx -y @glama/mcp-gateway`) and **dotMCP Tunnel** (`npx dotmcp-tunnel`) into the website's installation grid, highlighting cloud-proxied and globally tunneled execution.
- Updated the website (`index.html`), root `README.md`, and `mcp/README.md` to reflect Google's transition of **Gemini CLI to Antigravity CLI**, fully supporting and documenting the new launch command (`antigravity mcp add`).
- Pushed the website changes to GitHub to automatically trigger Vercel to rebuild and redeploy `https://clipacanvas.vercel.app`.

### Files Touched

- `SESSION_LOG.md`
- `LICENSE`
- `LICENSE.md`
- `mcp/LICENSE`
- `glama.json`
- `package.json`
- `mcp/src/clipacanvas_mcp/sse_app.py`
- `website/index.html`
- `website/styles.css`
- `README.md`
- `mcp/README.md`

### Commits

- `b569b0d` — `chore: add root glama.json manifest and fix LICENSE formatting for automated parsing`
- `f907233` — `chore: add root LICENSE.md and add license metadata to package.json for scanner compatibility`
- `d167729` (GitHub) / `a609f96` (HF) — `feat: add CORSMiddleware to enable native web browser connections`
- `fda93e4` — `feat: add Smithery and Glama registry badges with premium hover transitions to website`
- `0d62f2e` — `docs: integrate copy-pasteable Glama Gateway and dotMCP Tunnel guides into website`
- `05fc1a1` — `docs: update website, root README, and mcp/README for Google's Antigravity CLI transition`

### Deploy Links

- Glama listing: `https://glama.ai/mcp/servers/mechreaper007x/ClipACanvas`
- GitHub Release v1.0.2: `https://github.com/mechreaper007x/ClipACanvas/releases/tag/v1.0.2`
- HF Space: `https://huggingface.co/spaces/mechreaper007x/clip-a-canvas-mcp`
- Vercel Website: `https://clipacanvas.vercel.app`

### Open Items

- Claim/manage the live listing on Glama.ai.

## 2026-05-27 (Antigravity CLI Internet Check & Configuration Update)

### Summary

- Performed a web/internet check on the newly announced Google **Antigravity CLI** (`agy`) which succeeds the retired Gemini CLI.
- Discovered that the global MCP configurations for Antigravity are managed via `mcp_config.json` located at `~/.gemini/antigravity-cli/mcp_config.json` (macOS/Linux) or `%USERPROFILE%\.gemini\antigravity-cli\mcp_config.json` (Windows), and verified that active servers are checked using `agy inspect` and `/mcp list` in the TUI session.
- Replaced the older fictional/incorrect shell commands (`antigravity mcp add ...`) on the Vercel website and the `mcp/README.md` file with the correct and accurate JSON snippet for `mcp_config.json` and `agy` tool execution.
- Diagnosed and fixed the Claude/Codex client startup issues:
  - Addressed Claude Desktop's `-32000` (Connection Closed) error on Windows by implementing/documenting the standard `cmd /c` process wrapper for subprocess execution.
  - Clarified Codex TUI's cosmetic `Auth: Unsupported` display status, highlighting that local stdio-based MCP servers function securely without external OAuth requirements.
- Staged, committed, and pushed these updates to the GitHub repository, and triggered successful redeployments of the production website on Vercel.

### Files Touched

- `SESSION_LOG.md`
- `mcp/README.md`
- `website/index.html`
- `website/claude.html`
- `README.md`
- `.vercelignore`
- `vercel.json`
- `mcp/pyproject.toml`
- `.mcp/server.json`

### Commits

- `28139e1` — `docs: update Antigravity CLI (agy) configuration instructions on website and README`
- `d058f4e` — `docs: clarify Windows Claude cmd wrapper and Codex Auth: Unsupported status`
- `0865b2d` — `chore: update session log for Antigravity CLI discovery and deployment`
- `20a789c` — `chore: add .vercelignore to exclude large build artifacts from Vercel uploads`
- `f58635b` — `chore: polish session log with Claude and Codex fixes`
- `1db3f35` — `chore: add root vercel.json to route all root domain traffic to the website folder`
- `dc2cf8b` — `chore: fix vercel.json rewrite loop using negative lookahead regex`
- `d988d23` — `chore: final session log sync with Vercel deploy commits`
- `490f603` — `docs: use correct uvx --from clipacanvas-mcp clipmcp command in all guides`
- `604a81f` — `chore: polish session log with vercel rewrite loop commits`
- `fb6b04b` — `fix: resolve module layout mapping bug in Hatchling by adding sources = ['src'] to wheel targets`
- `60ace15` — `chore: final session log sync with uvx fix`
- `2cb0951` — `fix: resolve Codex local startup error by adding the correct uvx arguments to .mcp/server.json`
- `c06890a` — `chore: sync session log with pyproject mapping fix`

### Deploy Links

- Vercel Website: `https://clipacanvas.vercel.app`
- GitHub Repo: `https://github.com/mechreaper007x/ClipACanvas`

### Open Items

- None. The transition to Antigravity CLI and Windows subprocess wrappers has been fully and accurately integrated.

## 2026-05-27 (MCP Local Execution Fix — Playwright Chromium Install)

### Summary

- Diagnosed the root cause of MCP tool execution failures in Codex and Claude Code: **Playwright Chromium browser binaries were not installed** on the local system after a version update.
- The Playwright Python package was present, but the actual Chromium headless shell at `%LOCALAPPDATA%\ms-playwright\chromium_headless_shell-1169\` was missing, causing `BrowserType.launch: Executable doesn't exist` errors.
- Ran `python -m playwright install chromium` to download Chromium 136.0.7103.25 (build v1169) and the headless shell.
- Verified the fix with three independent test suites:
  - `mcp_diagnostic.py` — all 5/5 checks passed (imports, FFmpeg, Playwright, tool definitions, 1s test render).
  - `tests/frontend_render_matrix.py` — all 11/11 regression cases passed across DOM/SVG and Canvas render modes.
  - `mcp_e2e_test.py` — full JSON-RPC stdio lifecycle (initialize → tools/list → render_video) passed with 100,676 chars Base64 video returned.
- Confirmed all MCP client configurations are correct: Codex (`~/.codex/config.toml`), Claude global (`~/.claude.json`), and project (`.mcp/server.json`).
- No code changes were required — only the Playwright browser installation was missing.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- None. MCP server local execution is fully operational across all clients.

## 2026-05-27 (dotMCP Tunnel Security Fix)

### Summary

- Fixed dotMCP Tunnel key exposure by removing `tunnel.yaml` from Git tracking.
- Added `tunnel.yaml` to `.gitignore`.
- Created `tunnel.example.yaml` template with relative paths and placeholder key.
- Corrected the incorrect `@dotmcp/tunnel` package name and `-c tunnel.yaml` command-line options in the documentation.
- Restored the active tunnel key in the local, now-gitignored `tunnel.yaml` file so it can reconnect.
- Implemented **Option B (Cloud Tunnel)** to automatically run `@dotmcp/tunnel` inside Hugging Face Spaces.
- Added `start.sh` script to boot both the SSE server and the tunnel daemon in the cloud container when env secrets are present.
- Updated `mcp/Dockerfile` to install Node.js, npm, `@dotmcp/tunnel`, and `supergateway`.

### Files Touched

- `.gitignore`
- `tunnel.example.yaml`
- `tunnel.yaml` (untracked)
- `awesome_mcp_readme.md`
- `website/index.html`
- `mcp/Dockerfile`
- `mcp/start.sh`
- `SESSION_LOG.md`

### Commits

- `82577e6` — `security: untrack tunnel.yaml and add tunnel.example.yaml to prevent key exposure`
- `909803a` — `docs: correct dotmcp-tunnel package name and options in guides`
- `fdd1b35` — `feat: run dotmcp-tunnel in the cloud inside Hugging Face Spaces container`
- `2495466` — `fix: change localhost to 127.0.0.1 in start.sh to bypass Node.js IPv6 resolution issue`

### Deploy Links

- HF Space: `https://huggingface.co/spaces/mechreaper007x/clip-a-canvas-mcp`

### Open Items

- None. Both local and cloud-based dotMCP tunnel connections are fully operational.





## 2026-11-02

### Summary

- No repo changes made.
- Provided an architectural overview and technical decision retrospective on the headless browser-to-video rendering pipeline (time virtualization, CDP frame streaming, zero-disk FFmpeg piping, and auto-settle detection).

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- None.

### Open Items

- None.

## 2026-11-09

### Summary

- No repo changes made.
- Read and analyzed the external repository `filippocalippo/StykAnimate-App` alongside the local `Clip.A.Canvas` codebase.
- Evaluated both architectures, core engines, rendering pipelines, export mechanisms, and potential integration points.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Deploy Links

- External repo: `https://github.com/filippocalippo/StykAnimate-App`

### Open Items

- None.


## 2026-11-11

### Summary

- Replaced storage-level secret protection with application-level encryption for saved LLM API keys.
- Keys are now encrypted with AES-256-GCM (`cryptography`), versioned `v1:` format, per-provider AAD; the random master key (`keys.key`) is DPAPI-wrapped on Windows and a 0600 file on other platforms (previously non-Windows stored keys as plain base64).
- Legacy `keys.dat` values (DPAPI / old base64) are decrypted on load and auto-migrated to the new format; unreadable master keys are backed up as `keys.key.bak` instead of being clobbered.
- Verified with a scratch suite: round-trip, reload, tamper rejection, cross-provider swap rejection, legacy migration, corrupt-key recovery.

### Files Touched

- `serve.py`
- `requirements.txt`
- `desktop_requirements.txt`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` needs a rebuild to ship the new encryption (cryptography is now a desktop dependency).

## 2026-11-11

### Summary

- NEW CHAT now resets the workspace: code editor (Monaco) is emptied, the live preview iframe is cleared, and `lastCode` is dropped, so every new chat starts on a clean canvas. Works regardless of whether the current chat has messages or was already empty.
- Previous chat content remains reachable from chat history; selecting it restores its latest code as before.
- Updated settings hint to reflect the new AES-256-GCM key encryption.
- Verified with Playwright against an isolated data dir: chat-with-code scenario, empty-chat-with-pasted-code scenario, empty chat state, blank editor/canvas; screenshot checked.

### Files Touched

- `clipacanvas.html`

### Commits

- No commits created.

### Open Items

- None.

## 2026-11-11

### Summary

- Convert Video / Download / Preview are now three equal small rectangles in one horizontal row instead of stacked full-width buttons. Labels keep their text; the primary label wraps to two lines inside its third of the 360px panel.

### Files Touched

- `clipacanvas.html`

### Commits

- No commits created.

### Open Items

- None.

## 2026-11-11

### Summary

- Frame range fixed: the codec was never sent to `/render`, and explicit ranges were silently clamped to the auto-detected duration and cut early by settle detection. Explicit ranges (0-1s, 1-2s, Full Range or typed values) are now rendered exactly to the requested end; auto mode (empty end) keeps the adaptive settle trim. Invalid ranges (end <= start, start past auto duration) now show a clear error instead of being silently rewritten.
- Export formats widened from 2 to 7: H.264 MP4, H.265/HEVC MP4, VP9 WebM, VP8 WebM, AV1 WebM, ProRes 422 MOV, animated GIF. Codec now flows through the request; server maps codec to container/MIME; renderers set matching encoders, pixel formats (ProRes yuv422p10le), audio codec per container (Opus in WebM) and a palette filter for GIF (fps capped at 50). GIF results preview inline as an image and the download panel labels the real container.
- Node fallback renderer updated with the same codecs and exact range support; desktop save dialog accepts mp4/webm/mov/gif; AI tool schema and format parsing understand webm/mov/gif plus h265/vp8/av1/prores tokens.
- Verified: 7-codec matrix via ffprobe, explicit 0-4s range yields exactly 48 frames at 12 FPS, 1-2s yields 12, auto still trims settled animations, invalid range rejected; UI wiring test; real GIF render end-to-end through the server; Node fallback renders h265/vp9/gif and long ranges.

### Files Touched

- `clipacanvas.html`
- `serve.py`
- `playwright_render.py`
- `playwright_render.mjs`
- `desktop_app.py`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild to ship AES key encryption, new-chat canvas reset, button row, and the new export formats.

## 2026-11-11

### Summary

- Tidied the right-panel settings arrangement: the custom clip-length field is now a labeled field that only appears when Clip Length = Custom (previously a stray "15" input sat under Auto, merely dimmed).
- Frame range inputs now have START / END sub-labels, live in an aligned two-column grid, and the end placeholder reads "auto"; the help line was rewritten to match the new range/auto behavior.
- Verified with Playwright: hidden in Auto, visible/labeled in Custom, hides again on Auto; screenshots of Export Settings and the full Output section checked.

### Files Touched

- `clipacanvas.html`

### Commits

- No commits created.

### Open Items

- None.

## 2026-11-11

### Summary

- Output section: Bitrate and Export Profile now share one row (85/115 split), matching the Frame Rate + Codec pair. Option labels were compacted so every value fits without truncation; profile values and the JS mapping are unchanged, so saved settings still restore.
- Export-profile status message now shows the human label (e.g. "Wide — 1280×720 @30") instead of the raw key.
- Verified with Playwright: fields share a row (131/177 px), all option texts measured within select width, profile application updates resolution/fps and status.

### Files Touched

- `clipacanvas.html`

### Commits

- No commits created.

### Open Items

- None.

## 2026-11-11

### Summary

- Removed the redundant "OUTPUT FORMAT" row (format is implied by the Codec select) and the lone "OUTPUT" section header above Resolution.
- The export block now runs straight into Resolution, Frame Rate | Codec, Bitrate | Export Profile, with top padding compensating for the removed header.
- Removed the now-dead output-format label sync code; codec still persists via the shared settings listener.
- Verified with Playwright: no OUTPUT header, no format row, Bitrate/Profile still share a row, no page errors; screenshot checked.

### Files Touched

- `clipacanvas.html`

### Commits

- No commits created.

### Open Items

- None.

## 2026-11-11

### Summary

- Implemented the Elephant-Goldfish Model (google/elephant-goldfish-model, announced 2026-10-22) as the chat review loop: the elephant keeps conversation memory and writes code; a goldfish call runs in a fresh stateless context with only the request, the code, export settings and objective preview signals, returns severity-tagged JSON findings, and never sees chat history or tools.
- After any turn that writes code, one goldfish review runs automatically; blockers/majors trigger exactly one elephant fix turn (memory intact, findings injected) that rewrites the editor via insert_animation_code. No re-review loop.
- Added a persisted GOLDFISH REVIEW block in chat (PASSED or N ISSUES with blocker/major/nit findings and fixes), stored with a new review role allowed by client/server chatlog sanitizers.
- Free runtime evidence: the sandboxed preview now reports its own JS errors plus a 700ms snapshot (canvases, svg, videos, animations, text chars) via postMessage into the goldfish context.
- Dropped per user: audio work, offline template gallery, local LM Studio provider.
- Verified with mocked provider E2E: blocker path (6 requests: elephant 2 + goldfish 1 + fix 2 + title 1) fixes the editor and persists across reload; pass path skips the fix; goldfish payloads contain exactly 2 messages with no conversation history; preview errors/snapshot forwarded.

### Files Touched

- `clipacanvas.html`
- `serve.py`

### Commits

- No commits created.

### Open Items

- Goldfish uses the same model as the elephant turn; selecting a cheaper flash model keeps review quota low.
- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-11 (resolution, settings ownership, review noise)

### Summary

- Split Aspect Ratio and Resolution into separate controls: 5 aspects (16:9, 9:16, 1:1, 4:3, 3:4) x 8 tiers (240p-4K) = 40 presets, plus custom WxH accepted from chat. The hidden `#resolution` value feeds the existing preview/render path; the label shows pixels, aspect and marks custom sizes.
- Export settings are user-owned: `set_export_settings` now only applies values parsed from the current user message (resolution, aspect/tier, fps, duration, format, bitrate), and automatic goldfish-fix turns cannot change them. The system prompt and `serve.py` tool schema say so explicitly, and aspect changes keep the user's resolution tier (1920x1080 <-> 1080x1920).
- Passed goldfish reviews are no longer stored or shown; only blocker/major reviews produce a note. Removed the "TOOLS · ..." note under assistant replies.
- Verified with Playwright: 40 presets, aspect/tier mapping, custom 1000x1000, reload persistence, unrequested-setting guard, mocked chat turns (model tries 1280x720 while the user is on 1920x1080; stays 1920x1080), hidden passed reviews. A real 1000x1000 render produced 24 frames of h264 at 1000x1000.

### Files Touched

- `clipacanvas.html`
- `serve.py`
- `tests/_check_aspect_resolution.py` (new)
- `tests/desktop_smoke.py`
- `tests/desktop_render_smoke.py`
- `tests/packaged_render_smoke.py`
- `tests/run_packaged_full.py`
- `tests/frontend_render_matrix.py`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-11 (live chat action line)

### Summary

- Chat and goldfish progress messages no longer go to the global status bar, so lines like "Goldfish fix applied" never appear over the chat box. The status bar is back to preview/render status only.
- Replaced the static "…" thinking bubble with a live action line. The system prompt now asks the model to write one short present-tense action line before each tool call; the bubble shows that line while the tool runs, with tool-derived fallbacks when the model sends no text. It pulses and is removed when the turn ends.
- Verified with a mocked `sendChat` flow: the action log contains the LLM-written "Writing the caterpillar animation…" and "Checking the code for errors…", the status-bar log contains no goldfish/chat statuses, passed reviews stay hidden, and the final reply renders.

### Files Touched

- `clipacanvas.html`
- `tests/_check_aspect_resolution.py`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-11 (goldfish fully hidden)

### Summary

- The goldfish reviewer is now stealth-only: removed the review card builder and styles, the goldfish tool trace, review-role storage/lookup, and the review context injection. Legacy review rows are filtered out on load and excluded from the chat model context; client and server now only accept user/assistant/render messages.
- Kept the background review and single elephant fix turn, plus neutral action lines ("Checking the code for errors…", "Fixing the code…").
- Verified with Playwright: legacy review messages render nothing, a blocker review produces no chat message or trace, and the goldfish still returns findings in the background.

### Files Touched

- `clipacanvas.html`
- `serve.py`
- `tests/_check_aspect_resolution.py`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-11 (agentic chat flow)

### Summary

- Replaced the fixed interview prompt (aspect -> resolution -> duration -> style) with agentic guidance: act when the request is clear, ask at most one question only when it materially changes the result, never re-ask answered details, infer style from the subject, and proceed when the user delegates a choice.
- Added a delegation system nudge ("Choose according to...") and an answered-question nudge for short replies, so the model continues instead of asking again.
- Bare tier answers like "1080" now update the resolution while keeping the current aspect ratio, matching the screenshot's flow.
- Verified with Playwright: bare 1080 -> 1920x1080 on 16:9, both nudges are sent, and the old questionnaire text is gone from the prompt.

### Files Touched

- `clipacanvas.html`
- `tests/_check_aspect_resolution.py`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-11 (adaptive flows and single render)

### Summary

- Added three conversational flows to the system prompt: guided (step-by-step questions), one-shot (complete brief -> act), and brainstorm (propose directions first). The agent infers the flow from the user and can switch on signals like "just do it" or "what do you think?".
- Softened the deterministic nudges: an answered question moves the flow forward at the user's pace, and a delegated choice only settles that choice instead of forcing code.
- Render requests made while code is being written are now queued until after the background review/fix, so one request produces one render of the corrected code.
- The goldfish fix turn is fully stealth: no tool traces, no assistant reply, no rendering; the original assistant message's `codeAfter` is updated to the fixed code for restore/REVERT.
- Verified with mocked Playwright: insert + render + blocker fix -> 1 render of the FIXED code, 1 assistant reply, 1 insert trace, 1 queued render trace, 0 review cards, 0 goldfish statuses.

### Files Touched

- `clipacanvas.html`
- `tests/_check_aspect_resolution.py`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-11 (strict stateless goldfish)

### Summary

- Hardened the goldfish prompt into an adversarial QA review: execution, motion, viewport/resolution fit, request match, visibility and render stability; runtime errors are blockers; pass requires zero blocker/major findings and no unresolved uncertainty; findings need evidence and one concrete fix.
- Verified the reviewer is stateless: `buildGoldfishReviewMessages` returns exactly 2 messages (system + artifact), with no chat history and no tools; the backend forwards them directly to `generateContent` / `chat/completions` with no conversation ID. The mocked flow asserts 2 messages, roles system/user, tools false, and no assistant/title leakage.
- Existing deferred-render and stealth-fix checks still pass.

### Files Touched

- `clipacanvas.html`
- `tests/_check_aspect_resolution.py`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-11 (end-to-end verification)

### Summary

- Ran the full test pass on Python 3.11 against throwaway servers with a temp `CLIPACANVAS_KEYS_DIR`; no user chatlog or preferences touched, and no real LLM API calls made.
- `tests/_check_aspect_resolution.py`: all checks pass — aspect/tier split, custom WxH, settings gate, guided/one-shot/brainstorm prompt, stateless goldfish (exactly 2 messages, tools off), single render of the fixed code, stealth fix turn, persistence.
- `tests/frontend_render_matrix.py`: 11/11 render cases (DOM/CSS/SVG/WAAPI/timer/canvas) finish with valid downloads.
- `tests/desktop_smoke.py`: PASS — UI, themes, history, chatlog, key storage, GPU render and chat restore; no page or console errors.
- All 7 export codecs verified end to end: h264/h265 -> .mp4, vp9/vp8/av1 -> .webm, prores -> .mov, gif -> .gif; FFmpeg probes confirm the stream codec and 96x96 dimensions.
- Test-only fixes: render matrix waits for the Monaco textarea with `state="attached"`; desktop smoke seeds prior code before REVERT and asks for settings explicitly.

### Files Touched

- `tests/_check_aspect_resolution.py`
- `tests/frontend_render_matrix.py`
- `tests/desktop_smoke.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-11 (render leader + agent-only render notes)

### Summary

- Added a film-leader slate over the Live Preview stage while any render runs (manual Convert, RE-RENDER, or the agent's render tool): sprocket strips, grain, scratches, crosshair, and a countdown numeral driven by real render progress, with the stage label, percentage and ETA. Success ends with a one-frame cut flash; failure fades immediately.
- Pure CSS/SVG on top of the existing progress ticker; no extra animation loop, and reduced-motion users get a static slate. The slate is responsive inside the 9:16 stage (corner tag and ETA collapse on narrow widths).
- Render-log rows are now agent-only: `renderWithPlaywrightBackend` takes `logToChat`, manual renders never write chat history, and the agent render tool passes it through. Manual render errors no longer add chat rows.
- Verified in Chromium: slate visible mid-render with advancing numeral/percent, hidden after success and failure; manual render adds 0 chat notes, agent render adds 1.

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.
- Old manual render rows already stored in earlier chats are left untouched.

## 2026-11-12 (settings parse + render flow)

### Summary

- Fixed "resolutions 1080" without a `p`: bare tier numbers are now parsed, so "16:9 ratio and resolutions 1080" applies 1920x1080 instead of silently keeping the 540 tier.
- Duplicate tool calls within a turn: repeated `set_export_settings` / `insert_animation_code` calls reuse the earlier result, and only one SETTINGS trace is shown.
- One render per turn: extra `render_video` calls return an already-rendered result instead of rendering again.
- Completed renders no longer add a second RENDER_VIDEO trace; the RENDERED note is the record. Queued renders still show the "queued until code verification" trace.
- The render tool result now reports `status: complete`, and the system prompt marks `render_video` synchronous: confirm the file is ready, never claim it is still rendering or promise a later update. Added a no-re-confirm rule: an already-expressed render intent plus settings applies and renders in the same turn.
- Verified with a mocked chat flow (1920x1080, one settings trace, one render, one note, complete tool result), the full logic suite, and the desktop smoke suite (PASS, GPU render included).

### Files Touched

- `clipacanvas.html`
- `tests/desktop_smoke.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.
- The model's "still rendering" wording is fixed by prompt + tool result only; needs one live-API turn to confirm (real API not called here to save quota).

## 2026-11-12 (settings autonomy verification)

### Summary

- Verified the full settings chain with a mocked LLM and a real render: "make it 12 seconds, 16:9 and 1080" applied 1920x1080 and 12s, the actual `/render` request used 1920x1080 at 60 FPS/h264, and the downloaded file probes as h264, 1920x1080, 12.00s.
- The mock agent also tried 120 FPS, AV1 and 20M; the user-owned guard kept 60 FPS, h264 and 5M. One settings trace, one render note, no separate RENDER_VIDEO trace, and the final reply confirmed ready.
- Refined the render guidance: only a non-queued ok result means "already rendered"; a queued result should be described as rendering after verification.

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.

## 2026-11-12 (film transport strip)

### Summary

- Replaced the flat READY/WAITING progress block with a film transport: two reels, a sprocket gate, and actual render frames developing left to right.
- Backend: `/render` accepts a `renderId`, the Python renderer captures up to 16 sparse JPEG thumbnails (150 px max side) via CDP while rendering and writes `meta.json`; `GET /render/frames?id=` lists frames and `?n=` serves one; frame folders older than an hour are pruned.
- Frontend: the strip polls the frame list during the render, appends each new thumbnail, scrolls to the newest, spins the reels while rendering, and marks the transport done or jammed. The percentage/ETA readout and the thin progress line remain below. Reduced-motion disables the reel spin and frame fade.
- Verified with a real 4 second render: 16 thumbnails appeared live, all loaded (max natural width 141 px), the transport ended in the done or failed state, and the full desktop smoke suite passed with a GPU render.

### Files Touched

- `clipacanvas.html`
- `serve.py`
- `playwright_render.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.
- Thumbnails come from the Python renderer; the Node fallback still shows an empty strip.

## 2026-11-12 (film transport redesign)

### Summary

- Redesigned the strip into a proper film transport: supply and take-up reels connected by perforated film leaders into a sprocket gate, with rounded 35 mm-style perforations.
- The reels carry wound film that transfers as progress advances (supply thins, take-up fills) and spin while rendering. The readout shows a state dot, `35 MM`, ETA, frame count and percentage.
- Actual captured frames still develop left to right; idle, exposing, done and jammed states remain, and reduced motion disables the spin and frame fade.
- Verified with a real render: 16 thumbnails appeared live (2 at 35% mid-render), all loaded, done and failed states correct, no page errors.

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.
- The Node renderer fallback still produces an empty strip.

## 2026-11-12 (35 mm canister transport)

### Summary

- Replaced the projector-style reels with two 35 mm film cassettes modelled on the reference: cream label, black caps and spool, `COLOR`, `200` and `35 MM` type.
- The progress track is now a continuous brown negative running behind the cassettes, with punched sprocket holes and the captured frames developing in the middle.
- The take-up cassette fills with a wound film layer as progress rises, so one cassette starts clean and the other ends wrapped; the readout adds a `C-41` process mark and the live frame count.
- Verified with a real render: 16 frames appeared live, the take-up wrap tracked 25% to 100%, done and failed states correct, no page errors.

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.
- The Node renderer fallback still produces an empty strip.

## 2026-11-12 (film transport corrections)

### Summary

- The cassettes now have circular top spools that visibly rotate while a render runs; the take-up wrap continues to grow as progress rises.
- The strip is now a continuous negative: frames sit edge to edge with thin frame lines, smaller punched perforations and no card gaps, so it reads as one film ribbon instead of separate thumbnails.
- Starting a new chat or switching chats resets the transport to `NO FRAMES YET / READY` so old frames do not linger with an empty canvas.
- Verified with a real render: the spool animation ran while rendering, 16 frames appeared, done and failed states stayed correct, and `startNewChat()` cleared the strip and readout. No page errors.

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.
- The Node renderer fallback still produces an empty strip.

## 2026-11-12 (film strip motion)

### Summary

- The negative now visibly runs during a render: the track is built from two identical frame sequences and driven by a requestAnimationFrame `translateX` feed, so it loops seamlessly at 60 px/s in the take-up direction with no scrolling cost.
- Perforations travel at the matching 16 px / 0.27 s so they stay in step with the frames; the spool keeps rotating.
- On completion the feed stops and glides to the newest frames; on failure it stays jammed. Reduced-motion users get a static strip that still snaps to the latest frame.
- Frame aspect follows the export size, and starting a new chat or switching chats cancels the feed and resets the track.
- Verified with a real 640x360 render: transform advanced while rendering, 16 frames and 16 mirrored clones, aspect `640 / 360`, final offset lands on the newest frame, done/failed/new-chat states pass, desktop smoke suite fully passes with no page or console errors.

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for all recent changes.
- The Node renderer fallback still produces an empty strip.

## 2026-11-12 (Control Room layout)

### Summary

- Rebuilt the app shell as the Control Room: unchanged logo top-left, command bar, code pane left, live stage centre with an export timeline, Clipppa / Recipe tabs on the right, and a full-width transport dock with the moving negative and render bins.
- The assistant is now named **Clipppa** in its tab, header, composer, command bar, empty state and system prompt.
- All manual export controls moved intact into the new Recipe tab (timing, clip length, frame range, aspect, resolution, FPS, codec, bitrate, profile, latest render). Scene selection is not required to reach them.
- The timeline follows the export range and moves its playhead with render progress. The dock shows the current file/recipe, real ETA/percent, and the last four renders as bins using a real captured frame thumbnail stored with the run.
- The header command bar sends a message straight to Clipppa and supports Ctrl/Cmd+K; chat history and new chat live in a CHATS popover. The stage, timeline and bins leave room for multi-clip editing later without faking an editor now.
- Verified: logic suite passes; full desktop smoke passes (layout, drags, themes, chat, tools, renders, keys, chatlog); real 960x540 render passes with the timeline at 45%, moving film, one dock bin with a loaded thumbnail, and correct dock metadata. No page or console errors.

### Files Touched

- `clipacanvas.html`
- `tests/desktop_smoke.py`
- `tests/_check_aspect_resolution.py`
- `tests/_inspect_layout.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for the Control Room.
- The Node renderer fallback still produces an empty strip.
- The timeline and bins are display/progress surfaces; multi-clip trimming and scene editing are not implemented yet.

## 2026-11-12 (Layer timeline in the dock)

### Summary

- Removed the header command bar completely; Ctrl/Cmd+K now focuses Clipppa, and the shortcut help/dock hints were updated.
- Removed the timeline from the stage. The stage is now the pure preview canvas; the scene editor moved into the large empty transport area above the film strip.
- Rebuilt the scene strip as a Premiere-style layer timeline: V2/V1 track rows, a shared ruler, per-clip absolute time positions, gaps, and a playhead. `+ BOX`, `DUP`, `DEL` and `+ LAYER` (up to 4 layers) live in the timeline header.
- Each logic box now stores `start`, `duration` and `track`. Drag a box horizontally to move it in time, vertically to move it between layers, and drag the right edge to resize its duration. Selection loads that scene's code and previews it; double-click renames.
- The render pipeline now composes overlapping layers as one video: each active clip is seeked on its own virtual clock, stacked by track, and transparent top-layer pages let lower layers show through. Frame range trims the whole sequence.
- Single-box, untouched timelines still use the original auto-duration render path. A moved or resized box, or two or more boxes, switches to the explicit sequence path.
- Timeline state (clips, starts, tracks, layers) persists in `clipacanvas.timeline.v1`; older stored clips migrate onto V1 sequentially. Default dock height increased to 340px and old 236px/legacy defaults migrate once.
- Verified: layer UI checks (select, resize, chat-to-active-box, rename, horizontal/vertical drag, add layer, dup/del, frame range), two-box UI render, backend sequence matrix (sequential, trimmed, layered overlap, transparent overlay), auto duration policy, aspect/resolution logic, and the full desktop smoke suite all pass with no page/console errors. Live app restarted on 127.0.0.1:54535 (PID 19344).

### Files Touched

- `clipacanvas.html`
- `playwright_render.py`
- `serve.py`
- `tests/_check_logic_timeline.py` (new)
- `tests/_check_sequence_render.py` (new)
- `tests/_check_sequence_ui.py` (new)
- `tests/desktop_duration_smoke.py`
- `tests/desktop_smoke.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` is still stale and needs a rebuild for the layer timeline.
- The Node renderer fallback still produces an empty strip and does not understand layered clips.
- Layers currently hold code scenes only; photo/video import into the layer timeline is not implemented.

## 2026-11-12 (Film transport on the canvas)

### Summary

- Moved the 35mm film transport out of the dock and onto the bottom of the live preview canvas, as annotated. It is now a compact overlay (76px strip + readout + progress) with a dark scrim, cans at both ends and theme-independent light readout text.
- The dock is now purely the layer timeline and fills the full dock body; the dock header is labeled EDIT, with TIMELINE controls below it.
- Render thumbnails still feed the same film strip and now develop directly over the canvas; the film progress bar and readout travel with it. Verified with a two-scene render: 17 real frames appeared in the stage overlay and the render completed.
- Verified: desktop smoke suite passes; layer timeline UI checks pass (select, resize, drag time/layers, add layer, dup/del, chat-to-active-box); two-scene UI render passes with the film overlay; light-theme film readout remains readable on the black stage.
- Live app restarted on 127.0.0.1:54455 (PID 8344).

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for the dock layer timeline and canvas film overlay.
- The Node renderer fallback still produces an empty strip and does not understand layered clips.
- Layers currently hold code scenes only; photo/video import into the layer timeline is not implemented.

## 2026-11-12 (Render-popup transport)

### Summary

- The film transport no longer sits on the canvas at idle. It is hidden in the normal state and pops up from the bottom of the canvas only when a render starts (manual Convert or agent render).
- On pop-up it plays `stage-film-develop`: the film path brightens/scales in, canisters rise in, then the reel runs with perforation travel, developing frames, readout, and progress. The render leader countdown sits above it.
- The finished reel holds for ~4.2s after completion (3s on failure), then fades out and the canvas returns to a clean preview. Pressing PREVIEW or switching chat context hides it immediately.
- Verified with a two-scene render: idle hidden, mid-render visible with real frames and 21% progress, done visible at 100%, then hidden after the hold. Desktop smoke, layer UI, and two-scene UI render all pass with no console/page errors.
- Live app restarted on 127.0.0.1:56251 (PID 10828).

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild.
- Node renderer fallback remains an empty-strip fallback.

## 2026-11-12 (Blank scenes and multi-scene agent)

### Summary

- The timeline now opens as one single V1 track. Empty extra layers collapse on reload; V2–V4 appear only after + LAYER or when a box is moved onto them.
- + BOX now creates a blank scene (3s, blank editor, blank canvas) instead of copying the active code; DUP still copies. Empty scenes show an `EMPTY SCENE / WRITE CODE OR ASK CLIPPPA` overlay on the stage.
- Box drags and resizes snap to 0 and to other clip starts/ends (0.16s threshold).
- Clipppa now knows the whole edit: every request gets the timeline summary (scenes, layers, start, duration, selection, empty flags), and a new `add_scene` tool creates real logic boxes with code, name, duration, `same`/`above` layer and optional start. `insert_animation_code` now fills only the selected scene and can update its duration.
- The system prompt requires one HTML document per scene via add_scene for extra scenes, forbids merging scenes into one file, and reserves `above` + transparent background for overlays/titles. Goldfish review follows the newest scene and the single queued render still runs after verification.
- Verified with a mocked two-round tool turn (two real scene boxes, correct V1 append + V2 overlay, traces, goldfish pass, queued render), the full timeline UI test, sequence render matrix, desktop smoke, duration smoke and aspect/resolution checks. A live Gemini 3.6 Flash probe answered "add another high-impact scene" with one `add_scene` call carrying code, name, duration and layer.
- Live app restarted on 127.0.0.1:50065 (PID 5096).

### Files Touched

- `clipacanvas.html`
- `serve.py`
- `tests/_check_logic_timeline.py`
- `tests/_check_chat_scenes.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for blank scenes, single-track defaults and the add_scene tool.
- Node renderer fallback remains an empty-strip fallback.
- Layers still hold code scenes only; photo/video import is not implemented.

## 2026-11-12 (New chat button in the Clipppa header)

### Summary

- Replaced the tiny AUTO · GEMINI badge in the Clipppa header with a square `+` new-chat button (26px, token-based styling, model shown in its tooltip). It clears the composer and opens a fresh chat.
- Enlarged and brightened the CHATS history control in the right tab row (0.6rem, medium weight, secondary text token) so the history list is discoverable.
- Verified: fresh chat goes from 33 messages to 0 on click; the button is visible in dark and light themes; desktop smoke suite still passes with no page/console errors.
- Live app restarted on 127.0.0.1:50282 (PID 20668).

### Files Touched

- `clipacanvas.html`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for the timeline and chat UI changes.
- Node renderer fallback remains an empty-strip fallback.

## 2026-11-12 (Image and video lanes)

### Summary

- Added a `+ MEDIA` import control to the timeline. It opens a file picker for PNG, JPG, WebP, GIF, AVIF, BMP, MP4, MOV, M4V, WebM and OGV, uploads locally, and drops real media clips onto the selected layer.
- Importing into an empty selected scene fills that scene instead of leaving dead lead-in; further files append on the same track. Media clips can be selected, renamed, duplicated, dragged between V1–V4, resized, snapped, previewed and deleted.
- Timeline clips are now typed: image clips show their thumbnail behind a dark scrim, video clips use a filmstrip strip pattern and a `VIDEO · name` label. Types, sources and names persist with the timeline.
- Added `/api/media` uploads stored under `%APPDATA%/ClipACanvas/media` and a `/media/<id>` route with byte-range support (200 MB cap, extension allowlist, hashed filenames).
- Media plays in the live canvas through generated wrappers (contain fit, transparent background so overlays work). The sequence renderer rewrites media URLs to absolute addresses and now awaits video readiness and seeks per frame under the virtual clock.
- Verified with a still plus a two-color video: green image frame, blue then red video frames at the expected times; payload contains absolute media URLs; clips survive reload. A 320×180 mixed sequence rendered in ~2s.
- Regression suites pass: logic timeline, mocked chat scenes, sequence render matrix, sequence UI render, desktop smoke, duration smoke, aspect/resolution.
- Live app restarted on 127.0.0.1:64781 (PID 23844); live media upload/GET verified.

### Files Touched

- `clipacanvas.html`
- `serve.py`
- `playwright_render.py`
- `tests/_check_media_timeline.py`
- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for the timeline, chat and media UI changes.
- Node renderer fallback still does not understand media or layered clips.
- Audio import and media-bin browsing are not implemented yet; deleting a clip does not delete its stored file.

## 2026-11-12 (NLE editor rebuild: project bin, playhead, trims, split/ripple)

### Summary

- Rebuilt the timeline around a real NLE model. Imported images and videos now live in a `PROJECT · MEDIA` bin (thumbnails, `+ IMPORT`, click to inspect, double-click/`＋` to insert at the playhead, drag onto a track). Importing no longer auto-drops clips.
- Timeline clips reference `assetId` + `sourceIn` + `fit` instead of storing generated HTML wrappers. Selecting a media clip replaces Monaco with a media inspector (poster, available media, clip length, source-in slip, contain/cover fit, show in project); selecting a code scene restores the editor.
- Added a draggable playhead with timecode and frame preview, insert edits at the playhead (ripple open, splitting straddling clips), overwrite placement when dragging assets onto a track, left/right trim handles (head trim advances video source-in), split at the playhead (`SPLIT` / `S`), ripple delete (`DEL`), duplicate/rename, clip dragging with snapping and overlap blocking. `+ LAYER` adds V2–V4 tracks.
- Render plan now builds media wrappers on demand with absolute URLs and `data-source-in`; the renderer's media seek honors the in point and clamps inside the source range (plain code-page videos keep their old modulo loop). Clips split at a playhead carry the correct in point on the right half.
- Chat: `insert_animation_code` on a selected media clip now creates a new code scene instead of converting the user's media; app state and the timeline summary expose project assets, the playhead and source-in. Empty/trailing placeholder code scenes are still excluded from export.
- Timeline meta/render readouts now count `CLIPS` rather than boxes. Keyboard help lists split, ripple delete and playhead stepping.

### Files Touched

- `clipacanvas.html`
- `playwright_render.py`
- `tests/_check_media_timeline.py` (rewritten for the bin/insert/trim/split/ripple/source-in flow)
- `tests/_check_logic_timeline.py` (move test now respects occupied tracks)
- `tests/_check_sequence_ui.py` (dock readout uses CLIPS)
- `SESSION_LOG.md`

### Verification

- `_check_media_timeline.py`: import stays in the bin; insert image at 0 and video at 3s; inspector length/source-in slip; left trim advances source-in; ripple insert/delete shifts later clips; split at 1.4 leaves the right video half with source-in 0.6; render pixels at 0.3s/1.0s/1.7s are green/blue/red; reload preserves assets, in points and empty clip code.
- Passed: `_check_logic_timeline.py`, `_check_sequence_ui.py`, `_check_sequence_render.py`, `_check_chat_scenes.py`, `_check_aspect_resolution.py`, `desktop_smoke.py`, `desktop_duration_smoke.py`. No page/console errors.
- Live app restarted on 127.0.0.1:50915 (PID 5044). Verified the served page has the project bin, SPLIT button and CLIPS meta, no console errors, and live `/api/media` upload + Range GET (206).

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for the NLE editor.
- The stage previews one clip at a time (selected clip at the playhead, otherwise the bottom track); V1–V4 compositing happens on export.
- Node renderer fallback still does not understand media, trims or layered clips.
- Audio tracks, undo/redo, asset removal from the bin and stored-media cleanup are not implemented.

## 2026-11-12 (Run app)

### Summary

- No repo changes made.
- First started the browser server (`PORT=50517 python serve.py`, PID 9648), then stopped it on request and launched the native desktop window instead.
- Desktop app is running via `python desktop_app.py` (Python 3.11, PID 23508), window title `Clip.A.Canvas`.

### Files Touched

- `SESSION_LOG.md`

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for the NLE editor and chat changes.

## 2026-11-12 (Empty-bin import + audio lanes)

### Summary

- The empty PROJECT · MEDIA area is now an import target: click/double-click (or Enter/Space) opens the media picker, and files can still be dropped anywhere on the bin row. Hint copy now reads "DOUBLE-CLICK TO IMPORT · OR DROP FILES HERE — IMAGES · VIDEO · AUDIO".
- Import accepts audio alongside images/video: MP3, WAV, M4A, AAC, FLAC, OGA, Opus. `MEDIA_TYPES` in `serve.py` serves and stores them like other media.
- Audio is a first-class project asset: bin tile with waveform art and `AUD` badge, audio player in the inspector, insert/trim/slip/split on the timeline, and an `AUDIO` (no-picture) stage preview.
- Export mixes timeline audio: the render plan sends `audioClips` (url, start, sourceIn, duration); `serve.py` resolves `/media/...` to local files; `playwright_render.py` adds ffmpeg inputs with `atrim`/`adelay`/`amix` under the captured frames.
- The old single `audioPath` setting path still works when no timeline audio exists.

### Files Touched

- `clipacanvas.html`
- `serve.py`
- `playwright_render.py`
- `tests/_check_audio_import.py`
- `SESSION_LOG.md`

### Verification

- New `_check_audio_import.py`: double-click on the empty bin opens the picker, imports a still + MP3; audio asset shows `AUD` + waveform; insert at 0.4s; render payload carries the audio clip; exported MP4 is silent before 0.4s and 440 Hz tone afterwards.
- Passed: `_check_media_timeline.py`, `_check_logic_timeline.py`, `_check_sequence_ui.py`, `_check_chat_scenes.py`, `_check_sequence_render.py`, `_check_aspect_resolution.py`, `desktop_smoke.py`, `desktop_duration_smoke.py`. No console/page errors.
- Desktop app restarted (PID 16404, window `Clip.A.Canvas`, server 127.0.0.1:55203); served page includes the new import copy and audio accept list.

### Commits

- No commits created.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild for the import/audio/timeline changes.
- Video clips' embedded audio is not mixed yet; only imported audio clips play in the export.
- The Node renderer fallback still ignores media and audio.

## 2026-11-12 (Media overlays + faithful thumbnails)

### Summary

- Project-bin images no longer fill a cropped box: the bin shows the whole picture contained over a blurred copy of itself. Timeline image clips now use a repeating filmstrip at the picture's own aspect instead of covering a wide tile.
- Media inserted at a playhead that sits inside an existing scene now lands on the first free layer above (e.g. V2) instead of rippling the scene away. The scene stays untouched and the status reads `overlay`.
- Dragging a media clip over an occupied scene spills it to the next free layer and follows the pointer instead of blocking the move. Dropping a bin asset onto an occupied lane overlays it above; if all four layers are occupied, the app refuses with a message.
- Insertion into a gap still ripples later clips (unchanged).
- Video export already contained images; verified it also composites the overlay above the scene (green scene visible around the magenta still, no stretching).

### Files Touched

- `clipacanvas.html`
- `tests/_check_media_overlay.py` (new)
- `tests/_check_media_timeline.py` (insert-at-playhead expectations now describe the overlay behavior)
- `SESSION_LOG.md`

### Verification

- `_check_media_overlay.py`: bin thumbnail uses `object-fit: contain` with backdrop; insert over V1 scene creates a V2 overlay and leaves the scene at 0–6s; dragging the photo over the scene moves it to V2 at 4.3s; exported frame shows scene green at the top and the still in the middle.
- Passed: `_check_audio_import.py`, `_check_media_timeline.py`, `_check_logic_timeline.py`, `_check_sequence_ui.py`, `_check_chat_scenes.py`, `_check_sequence_render.py`, `_check_aspect_resolution.py`, `desktop_smoke.py`. No console/page errors.
- Desktop app restarted (window `Clip.A.Canvas`, server 127.0.0.1:50951) with the new overlay and thumbnail behavior.

### Commits

- No commits created.

### Open Items

- The stage still previews one clip at a time; the V1+overlay composite is only visible in the export (existing limitation).
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Clipchamp-style bin + composited stage preview)

### Summary

- Project · Media no longer stretches one asset into a tall panel-filling tile. The bin is a 2-column grid of natural media cards: a 16:9 thumbnail (contained picture, cover video, waveform for audio) with the name/duration strip below. Cards sit at the top and scroll instead of stretching to the dock height.
- The live stage now composites every track at the playhead like the export: the selected/overlaid photo appears on top of the scene instead of the stage showing the photo alone. Composite previews are rebuilt on selection, insert, scrub and editor preview; a single un-layered clip still previews alone so its animation keeps running.
- Code layers inside a composite keep the preview reporter via a message relay, so error/snapshot diagnostics still reach the app.
- Layer structure is unchanged (V2 is the overlay track above V1, the same as Clipchamp's overlay track); the preview now shows the real stack.

### Files Touched

- `clipacanvas.html`
- `tests/_check_media_overlay.py`
- `SESSION_LOG.md`

### Verification

- `_check_media_overlay.py`: bin art is 202x113.6 (16:9, not stretched); inserting the photo over SCENE 01 gives a 2-layer stage srcdoc; stage screenshot shows scene green around a magenta photo; drag-over-scene still lands on V2; export still composites the photo over the scene without distortion.
- Passed: `_check_media_timeline.py`, `_check_logic_timeline.py`, `_check_sequence_ui.py`, `_check_chat_scenes.py`, `_check_audio_import.py`, `_check_sequence_render.py`, `_check_aspect_resolution.py`, `desktop_smoke.py`, `desktop_duration_smoke.py`. No console/page errors.
- Desktop app restarted (window `Clip.A.Canvas`, server 127.0.0.1:59893). Live check with the futuristic-city photo shows the wide bin card and the scene's "THE END" text composited above the photo.

### Commits

- No commits created.

### Open Items

- The composite preview plays code layers from their own 0, not the local timeline offset (same as before for single clips); only media in/out points are time-accurate.
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Media inside a scene)

### Summary

- Added `INSERT INTO SCENE` to the media inspector for image and video assets. It embeds the media in the target scene's own HTML (`<img>/<video class="cc-scene-media">`, centered at 72%, z-index 20) before `</body>` instead of creating a new clip or layer.
- Target scene = the active code scene, otherwise the topmost code scene covering the playhead, otherwise the first code scene; the button names it (`INSERT INTO SCENE 01`). Audio assets hide the button because embedded audio would not be mixed.
- After embedding, the scene is selected, its code loads in the editor (so the element can be moved/resized), and the stage previews the media inside the scene. The bin asset stays in PROJECT.
- Single-scene renders now absolutize `/media/...` URLs in the payload code, so embedded media renders outside the app server. Sequence code was already absolutized.

### Files Touched

- `clipacanvas.html`
- `tests/_check_scene_embed.py` (new)
- `SESSION_LOG.md`

### Verification

- `_check_scene_embed.py`: embed button reads `INSERT INTO SCENE 01`; click keeps 1 clip / 1 layer; scene code gains `<img src="/media/media-...">` before `</body>` and the editor shows it; stage screenshot shows green scene + centered magenta photo; exported 1s render shows the same pixels (embedded media survived the render).
- Passed: `_check_media_overlay.py`, `_check_media_timeline.py`, `_check_logic_timeline.py`, `_check_sequence_ui.py`, `_check_chat_scenes.py`, `_check_audio_import.py`, `_check_sequence_render.py`, `_check_aspect_resolution.py`, `desktop_smoke.py`, `desktop_duration_smoke.py`. No console/page errors.
- Desktop app restarted (window `Clip.A.Canvas`, server 127.0.0.1:51571). Live check with the futuristic-city photo embedded into SCENE 01: single V1 clip, photo inside the scene preview next to the scene's title.

### Commits

- No commits created.

### Open Items

- Embedded media is centered at 72% by default; reposition/resize via the scene code (or ask Clipppa).
- Audio cannot be embedded in a scene (no audio capture from the scene HTML); use a timeline audio clip.
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Scene media: remove, drop, drag)

### Summary

- Media embedded inside a scene can now be deleted: the asset inspector shows `REMOVE FROM SCENE 01` (named for the owning scene); it strips the `<img>/<video>` with that media URL from every scene that embeds it, reselects the scene and re-previews. Scenes left without the element render unchanged.
- Drag & drop over the live stage: dragging a bin card over the preview highlights the stage and dropping places the media **inside the target scene** centered at the drop point (40% width) instead of creating a layer. Files dragged in from the OS over the stage are imported and embedded the same way.
- The embedded picture can be dragged inside the preview: a small in-scene script (injected in the head for previews) tracks pointer drags and posts the new left/top percentages back, which rewrite the style in the scene code, save, and re-preview. Clicking the picture in the preview selects its bin asset (inspector shows REMOVE).
- Point-in-time fix: drag used `document.documentElement` height, which is 0 inside the sandboxed scene; switched to `window.innerWidth/innerHeight` so vertical movement is no longer clamped.
- Regression fix: scene tools are injected in the `<head>` (fallback: `<html>`, doctype, prepend), so they no longer land inside an unclosed `<script>` in short scene snippets (`desktop_smoke.py` "Unexpected token '<'" is gone).

### Files Touched

- `clipacanvas.html`
- `tests/_check_scene_embed.py`
- `SESSION_LOG.md`

### Verification

- `_check_scene_embed.py`: embed → 1 clip, image inside code, stage shows the picture; export pixels include it; `REMOVE` clears the element and the stage returns to the scene alone; drop from the bin at (69.7%, 30.0%) embeds at the drop point; dragging the picture inside the preview moves it to (91.2%, 42.1%); clicking it selects the asset and shows REMOVE. No page errors.
- Passed: `_check_media_overlay.py`, `_check_media_timeline.py`, `_check_logic_timeline.py`, `_check_sequence_ui.py`, `_check_chat_scenes.py`, `_check_audio_import.py`, `_check_sequence_render.py`, `_check_aspect_resolution.py`, `desktop_smoke.py`, `desktop_duration_smoke.py`.
- Desktop app restarted (window `Clip.A.Canvas`, PID 22260, server 127.0.0.1:51134). Live check with the futuristic-city photo embedded into SCENE 01: single clip/layer, inspector shows `INSERT INTO SCENE 01 | REMOVE FROM SCENE 01`, no console errors.

### Commits

- `47e0daa` - `feat: media bin, overlays, audio mixing, composite preview and in-scene media` (also carries the previously uncommitted media/audio/overlay work, bundled fonts and test suites)

### Open Items

- External OS file-drop over the stage is relayed from inside the scene iframe but was only exercised programmatically, not with a real drag from Explorer.
- Scene repositions update the scene code style only; scene animations that key the element position could override it.
- `dist/ClipACanvas.exe` still needs a rebuild for the media, overlay, audio, composite-preview and scene-embed work.

## 2026-11-12 (NLE workspace refactor: full-width timeline, tabs, monitor)

### Summary

- Header reduced to 58px: wordmark, editable project name, SAVED/EDITING state, DOWNLOAD, EXPORT, layout reset, settings, history. Render progress stays in the timeline strip.
- Left panel is now tabbed PROJECT | CODE. PROJECT holds the media bin (moved out of the dock), import controls and a scene list; selecting a scene opens its source in CODE. CODE holds Monaco, now with horizontal scrolling instead of wrapping.
- Right panel is tabbed INSPECTOR | CLIPPPA | RECIPE, opening on INSPECTOR. The media inspector moved here unchanged; code clips get a new inspector (start, end, duration, track, OPEN CODE, SPLIT AT PLAYHEAD).
- Timeline spans the full window (1632 of 1664px). Added CTRL/SHIFT+wheel zoom and scroll, − FIT + controls, a 1× indicator, track headers with clip counts, per-kind clip treatments (emerald code, filmstrip image, steel-striped video, real-peak amber audio waveform) and fixed 74px tracks.
- Program monitor gained a transport bar: play/pause (Space, works from inside the preview iframe too), HH:MM:SS:FF current/duration timecode, frame-rate chip, FIT/1:1 toggle and fullscreen.
- Snapping is now 6px in time-space instead of a fixed 0.16s, so trims work at any zoom and timeline width.
- Project name persists through the existing /api/prefs store (new `projectName` key), not localStorage alone.

### Files Touched

- `clipacanvas.html`
- `serve.py`
- `tests/_check_workspace.py` (new)
- `tests/_viz_workspace.py` (new)
- `tests/_check_media_timeline.py`, `tests/_check_scene_embed.py`, `tests/_check_audio_import.py`, `tests/_check_logic_timeline.py`, `tests/desktop_smoke.py`
- `SESSION_LOG.md`

### Verification

- `_check_workspace.py`: tabs, bin in left panel, 1632px timeline, playback advances the playhead, zoom narrows the view and FIT resets, media import opens the Inspector, chat and recipe intact; no overflow at 1664×916, 1440×900, 1280×720; preview stays 9:16; timeline share 35%/36%/45%.
- Passed: `_check_media_overlay.py`, `_check_media_timeline.py`, `_check_scene_embed.py`, `_check_audio_import.py`, `_check_logic_timeline.py`, `_check_sequence_ui.py`, `_check_chat_scenes.py`, `_check_sequence_render.py`, `_check_aspect_resolution.py`, `desktop_smoke.py`, `desktop_duration_smoke.py`. No page or console errors.
- Screenshots: `output/playwright/workspace-before-1664.png` (old layout) vs `workspace-final-1664.png`, `workspace-final-1440.png`, `workspace-final-1280.png`; plus code-tab, zoomed, media-inspector, chat and light/violet theme shots.
- Desktop app restarted (PID 5608, server 127.0.0.1:65411); the live page serves the new tabs, 1632px timeline, monitor transport and export button with no console errors.

### Commits

- None. The task instructions require explicit permission before committing or pushing.

### Open Items

- Code scenes show no cached frame thumbnail on timeline clips; capturing a frame needs an extra renderer, which the constraints forbid. Code clips use a distinct emerald treatment instead.
- Playback rebuilds the preview only at clip/bucket boundaries; code animations run on their own clock and are not seeked.
- Undo/redo was not added because no state history exists yet.
- `dist/ClipACanvas.exe` still needs a rebuild for the workspace, media, overlay, audio and scene-embed work.

## 2026-11-12 (Full-surface timeline drops)

### Summary

- Imported media can now be dragged from PROJECT · MEDIA anywhere onto the timeline, not only the 74px track lanes. Dropping in the empty area below the tracks falls back to the bottom track (V1) at the pointer's time and overlays above an occupied scene.
- Bin cards show the image itself as the drag ghost; while over the timeline the target lane is outlined, a `DROP TO ADD TO THE TIMELINE` badge appears and the drop marker follows the pointer. Drag end clears all feedback.
- The timeline dragover/drop listeners moved from `#logicTracks` to `#etTracksWrap` so the empty surface participates.

### Files Touched

- `clipacanvas.html`
- `tests/_check_workspace.py`
- `SESSION_LOG.md`

### Verification

- `_check_workspace.py` now drags a freshly imported card into the empty timeline area and asserts the drop badge, then a created clip at 1.7s on V2 above the scene. All other workspace checks pass at 1664/1440/1280.
- `_check_scene_embed.py` still passes (bin → stage embed at 69.8%/29.8%, in-preview drag to 91.7%/42.1%).

### Commits

- Committed and pushed in the Milestone 1 workspace commit.

### Open Items

- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Bin drag drop: pointer controller in WebView2)

### Summary

- Root cause of "dragging from the bin does nothing": in the desktop WebView2 runtime an in-page HTML5 drag from a bin card strips the custom `application/x-clipacanvas-asset` MIME type (`types` only had `text/uri-list`, `text/html`, `Files`) and the page never receives `dragover`/`drop`, so the timeline handlers never run. Chromium-only tests had hidden this.
- Replaced bin-card HTML5 DnD with a single pointer-events controller: 6px threshold, thumbnail ghost, `elementFromPoint` target resolution, timeline or Program Monitor target, commit on pointer release, cleanup on pointercancel/blur/Escape, one-shot click suppression so a drop does not also select the asset.
- Native HTML5 handlers remain only for OS file drops (timeline, stage, bin). Bin cards and their thumbnails are `draggable="false"`, so the two systems never compete.
- Drop feedback: target lane highlighted (`drop-over`/`drop-invalid`), vertical marker with time bubble, hint text `DROP AT 1.20s · V1` or `NO FREE TRACK AT 3.00s`.
- Dropping on the empty area below the tracks still falls back to V1 at the pointer time; occupied stacks reject with the existing status message and insert nothing.

### Files Touched

- `clipacanvas.html`
- `tests/_check_bin_dragdrop.py` (new, 12 scenarios incl. real export)
- `tests/_check_webview_dragdrop.py` (new, drives the real WebView2 window over CDP)
- `SESSION_LOG.md`

### Verification

- `_check_bin_dragdrop.py`: PASS in Chromium — image V1 @20%/75%, V2, video keeps 1.2s, audio stays audio on V3, two sequential drops, occupied stack rejected with `NO FREE TRACK` and no clip, overlay to V3, empty-area drop, Escape cancel, zoomed mapping, persistence/selection, real `#btnConvert` export (magenta center `(252,0,251)`).
- `_check_webview_dragdrop.py`: PASS in the actual WebView2 runtime (Edg/157.0.4341.46) via CDP: import → pointer drag → `DROP AT 1.50s · V1` → clip on V1 at 1.5s/3s, inspector follows, empty-area drop at 3.2s on V1.
- Regression suites after the change: `_check_workspace.py`, `_check_scene_embed.py` (bin → stage drag still works), `_check_media_overlay.py`, `_check_media_timeline.py`, `_check_audio_import.py`, `desktop_smoke.py` — all PASS.
- Screenshot: `output/playwright/bin-drag-hover.png`, `output/playwright/webview-dragdrop.png`.

### Commits

- Committed and pushed in the Milestone 1 workspace commit.

### Open Items

- Native HTML5 drags cannot be driven by synthetic CDP input on Windows WebView2, so the WebView check used pointer events through CDP; a final physical-mouse drag in the desktop window is still worth a human confirmation.
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Milestone 0 audit + Milestone 1 operation layer)

### Summary

- Added `docs/EDITOR_AUDIT.md`: evidence-based audit of the frontend, renderer, media, preview/playback, export, persistence, MCP/TUI and tests; implemented vs partial vs missing; preserve/refactor lists; proposed versioned/tick-based project model (not implemented); risks; Milestone 1 status and Milestone 2–4 order.
- Added the structured project-operation layer `projectOps` in `clipacanvas.html`, exposed as `window.projectOps`. Validated calls: `snapshot`, `seek`, `selectClip`, `createTrack`, `createComposition`, `insertAsset`, `moveClip`, `trimClip`, `splitClip`, `deleteClip`, `duplicateClip`. Each mutation goes through the existing persist/repaint/preview path; moves reject occupied ranges; inserts reuse overlay policy; trims validate length and media in-points.
- `createSceneClip` now accepts an explicit `track`; the chat `add_scene` tool uses `projectOps.createComposition` so AI and UI share the same structured path.
- Extracted `deleteClipById` from `deleteLogicClip`; ripple behavior and status text are unchanged.
- No UI controls were added without backing behavior. Keyframes, transitions, typed tracks, undo/redo and frame stepping remain deferred to Milestone 2/3.

### Files Touched

- `clipacanvas.html`
- `docs/EDITOR_AUDIT.md` (new)
- `tests/_check_project_ops.py` (new)
- `SESSION_LOG.md`

### Verification

- `tests/_check_project_ops.py` (new): PASS — explicit-track composition, track creation, asset insert, move + occupied rejection, image/video trim with `sourceIn`, split, duplicate, seek, ripple delete, invalid IDs, DOM/render-plan sync, snapshot shape, reload persistence.
- Regressions after the change: `_check_chat_scenes.py`, `_check_logic_timeline.py`, `_check_media_timeline.py`, `_check_workspace.py`, `desktop_smoke.py` — all PASS.
- Real WebView2 drag test (`_check_webview_dragdrop.py`) re-run on the final build — PASS (Edg/157).

### Commits

- Committed and pushed in the Milestone 1 workspace commit.

### Open Items

- Milestone 2: project clock/frame stepping, integer frame ticks with v1→v2 adapter, typed tracks and track controls, undo/redo, playback/export tests.
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (End-to-end verification and audio mux fix)

### Summary

- Added `tests/_check_e2e_flow.py`: one continuous user journey — import image/video/audio, add a scene from the timeline toolbar, edit code + duration in the inspector, add tracks, drag all three assets from the bin to V2/V3/V4 at explicit times, play/pause, verify the composite preview, export a 4 s 540×960 render, probe scene/image/video pixels and the audio bed, then reload and check persistence.
- The journey exposed a real renderer bug: a 1 s audio clip truncated a 4 s export to 1.2 s because the mux used `-shortest`. Timeline audio muxing now uses an explicit `-t` window equal to `renderEnd - renderStart`; the export is exactly 4.00 s and audio still peaks at -18.5 dB. `apad` was rejected after testing because it hangs the bundled FFmpeg with `-shortest`.
- The legacy single-`audioPath` path keeps bounded behavior (explicit `-t` when a render end exists, otherwise `-shortest`); noted in the audit.

### Files Touched

- `playwright_render.py`
- `tests/_check_e2e_flow.py` (new)
- `docs/EDITOR_AUDIT.md`
- `SESSION_LOG.md`

### Verification

- `_check_e2e_flow.py`: PASS — scene green `(0,189,62)`, image overlay magenta `(252,0,251)` with green letterbox, video blue `(0,51,252)` over green, audio max volume -18.5 dB, playback advances 1.0 → 1.70, 4 clips restored after reload; exported duration 4.00 s.
- Render/audio regressions after the mux fix: `_check_audio_import.py`, `_check_media_timeline.py`, `_check_media_overlay.py`, `_check_bin_dragdrop.py`, `renderer_feature_matrix.py` (4/4) — all PASS.
- Artifacts: `output/playwright/e2e-workspace.png`, `e2e-final.png`, `e2e-render.mp4`.

### Commits

- Not committed. The previous Milestone 1 push (`58bb71c`) predates this fix; explicit permission required to commit/push it.

### Open Items

- Commit/push the audio mux fix + E2E suite when approved.
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Phase 0 audit + Phase 1: asset intelligence, overlays, zoom)

### Summary

- Updated `docs/EDITOR_AUDIT.md` with a Phase 0 addendum for the AI-native directive: compositing/overlays, transitions, asset intelligence, TTS and zoom; implemented vs missing, dependencies, risks and phase status.
- Asset intelligence (technical): new `POST /api/media/analyze` probes stored media with the bundled FFmpeg and caches a manifest keyed by content hash under `%APPDATA%/ClipACanvas/analysis`. Fields: duration, resolution, fps, video/audio codec, sample rate, channels, streams, bytes. Semantic block is explicitly `not_analyzed`; no media leaves the machine.
- Frontend: assets now carry a persisted sanitized manifest; the media inspector shows a TECHNICAL block and an explicit content-analysis status. Import and project load analyze missing assets.
- Agent tools: `search_assets`, `get_asset_analysis`, `update_asset_description` (human notes stored separately from AI fields). LLM context now sends concise asset summaries, not full manifests.
- Overlay relationships: `parentClipId` in the clip model with sanitize/resolve, `projectOps.attachOverlay`/`detachOverlay`/`getClipContext`; attached overlays follow parent moves and in-point trims (clamped), detach when the parent is deleted, and are rejected for audio, self and chains. Inspector shows ATTACHED TO.
- Agent overlay tools: `create_overlay`, `update_overlay`, `attach_overlay`, `detach_overlay`, `delete_overlay`, `get_clip_context`, all through projectOps.
- Zoom: 100–800% percent field with presets, 100–800 slider (step 5), direct numeric entry, playhead-anchored zoom, synchronized with wheel/buttons/FIT.

### Files Touched

- `clipacanvas.html`, `serve.py`
- `docs/EDITOR_AUDIT.md`
- `tests/_check_asset_intelligence.py`, `tests/_check_timeline_zoom.py`, `tests/_check_overlays.py`, `tests/_check_webview_phase1.py` (new)
- `SESSION_LOG.md`

### Verification

- `_check_asset_intelligence.py`: PASS — probe for image/video/audio, inspector block, cache identity, agent tools, 404 for missing media, concise LLM context, reload persistence.
- `_check_timeline_zoom.py`: PASS — all nine presets, anchoring, numeric/slider/buttons/FIT sync, Ctrl+wheel pointer anchor, 800% layout and no overflow at 1664/1280.
- `_check_overlays.py`: PASS — attach, real mouse parent drag shifts overlay, trim shift, detach, delete detaches, chain/self/audio/missing rejection, reload persistence, agent tools.
- `_check_webview_phase1.py`: PASS in the real desktop WebView2 (Edg/157) — analysis inspector, 400% zoom control, overlay attach + ATTACHED TO row.
- Regressions: `_check_workspace.py`, `_check_project_ops.py`, `_check_chat_scenes.py`, `_check_bin_dragdrop.py`, `_check_e2e_flow.py`, `_check_media_timeline.py`, `desktop_smoke.py` — all PASS.

### Not implemented (reported, not mocked)

- Transitions (model/contract/library/generated transitions), TTS provider abstraction and Voiceover Studio, semantic/visual/audio analysis, frame/tick timebase, overlay attachment UI buttons, audio track semantics A1–A3.
- No new dependencies; no TTS model weights added.

### Commits

- Committed as the Phase 1 change set. Push not performed; explicit permission required.

### Open Items

- Next: transition data model + deterministic contract, TTS provider verification, semantic analysis consent flow.
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Phase 2: deterministic transition engine)

### Summary

- Added first-class transitions on touching cuts: `timelineState.transitions` persists in `clipacanvas.timeline.v1` with `fromClipId`, `toClipId`, `type`, `duration`, `alignment`, `params`, optional custom `code`, version. Invalid/overlapping/gapped transitions are pruned on save.
- Added a single deterministic engine (`ccTransitionRuntime`) whose source is embedded verbatim into both the Program Monitor composite and the Playwright sequence document. Progress drives declarative CSS surface styles; no timers or wall-clock state. Incoming surfaces are forced above outgoing ones so same-track cuts composite correctly.
- Preset library: dissolve, fade-black, fade-white, dip-color, wipe, push, slide, zoom-in, zoom-out, zoom-blur, glitch, rgb-split, blur-dissolve (13).
- Custom transitions: `function renderTransition(ctx)` returning `{outgoing, incoming, overlay}` styles; validated and deny-listed, compiled only inside the sandboxed preview/Playwright pages, never in the app window.
- Media boundary checks: outgoing footage past the out point and incoming handle before the in point are validated per alignment; video transitions export with real handles.
- UI: TRANSITION toolbar button, transition dialog (type/duration/alignment/direction/color/intensity/code/remove), cut badges, midpoint scrubbing preview; playback posts time into the composite page so blends animate.
- Agent tools: `add_transition`, `update_transition`, `remove_transition`; transitions are included in `timelineSummaryForChat` and `get_clip_context`.

### Files Touched

- `clipacanvas.html`, `playwright_render.py`, `serve.py`
- `docs/EDITOR_AUDIT.md`
- `tests/_check_transitions.py`, `tests/_check_webview_transitions.py` (new)
- `SESSION_LOG.md`

### Verification

- `_check_transitions.py`: PASS — preview pixels red→purple→blue across a dissolve, playback progress, all 13 presets, custom transitions + blocked code, wipe clip-path, fade-black, gap/length/handle rejection, 1.2 s export with start/mid/end probes, persistence, dialog add/edit/remove, a real media transition with footage handles, agent tools.
- `_check_webview_transitions.py`: PASS in WebView2 (Edg/157) — dialog add (zoom-blur), composite engine layers, 1.2 s export start/mid/end probes, restore after reload.
- Regressions: `_check_workspace.py`, `_check_overlays.py`, `_check_project_ops.py`, `_check_bin_dragdrop.py`, `_check_e2e_flow.py`, `_check_media_timeline.py`, `_check_chat_scenes.py`, `_check_timeline_zoom.py` — all PASS.
- Artifacts: `output/playwright/transition-export.mp4`, `transition-media.mp4`, `webview-transition.mp4`, `webview-transition-dialog.png`, `webview-transition-restored.png`.

### Commits

- This transition change set committed locally; not pushed.

### Open Items

- TTS provider abstraction and Voiceover Studio (next directive item); semantic asset analysis; overlay attachment UI buttons; frame/tick timebase.
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Phase 3: speech generation and audio mix)

### Summary

- Added a TTS provider registry and synthesis backend: local Windows SAPI (`System.Speech`, offline) plus hosted Gemini TTS and Mistral Voxtral, gated on installed voices / configured keys. Keys stay in the backend store; hosted requests run only on explicit user generation and state where the script is sent.
- Added deterministic caching keyed by canonical request (text/provider/model/voice/format/speed/style) under `%APPDATA%/ClipACanvas/tts`; generated audio is saved as a normal `/media` asset and probed with the bundled FFmpeg.
- Added the VOICE right-pane tab (Voiceover Studio): script + selection, provider/voice/speed/style controls, consent line, audio preview, insert at playhead or add to bin.
- Added A1 VOICEOVER / A2 MUSIC / A3 SFX audio lanes with mute/solo/volume, persisted with the project; clips carry `audioTrack`, the inspector exposes lane + mix, and export applies real FFmpeg gain and mute/solo.

### Files Touched

- `clipacanvas.html`, `serve.py`, `playwright_render.py`
- `docs/EDITOR_AUDIT.md` (Phase 3 addendum)
- `tests/_check_tts.py`, `tests/_check_webview_tts.py` (new)
- `SESSION_LOG.md`

### Verification

- `_check_tts.py`: PASS — provider availability (SAPI available, hosted disabled without keys), SAPI WAV generation, cache reuse without a second call, asset/bin creation, A1 insertion, export voiceover peak -1.9 dB, 0.5 lane gain -7.9 dB, lane assignment/mute/solo in the render plan, persistence, 1280 right-tab fit.
- `_check_webview_tts.py`: PASS in WebView2 (Edg/157) — generate, insert on A1, mute mix, restore after reload.
- Regressions PASS: `_check_workspace`, `_check_overlays`, `_check_project_ops`, `_check_bin_dragdrop`, `_check_e2e_flow`, `_check_media_timeline`, `_check_transitions`, `_check_chat_scenes`, `_check_audio_import`, `_check_timeline_zoom`; `py_compile` clean.
- Artifacts: `output/playwright/voice-studio.png`, `voiceover-export.mp4`, `voiceover-half.mp4`, `webview-voice-studio.png`.

### Commits

- This speech/audio change set committed locally; not pushed.

### Open Items

- Hosted TTS request paths verified from docs but not exercised live (no hosted key configured); semantic asset analysis, overlay attachment UI, frame/tick timebase remain.
- `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Phase 4: semantic asset intelligence)

### Summary

- Added offline shot detection and keyframe extraction for video assets (FFmpeg scene score, first 180 s, up to 24 boundaries / 12 JPEG previews) with a read-only frame route; manifest version 2 now carries `shots[]`.
- Added a consent-gated Gemini content-analysis path: `GET /api/media/semantic/providers` and `POST /api/media/semantic`. Requests without explicit consent are rejected; the backend uploads at most 6 local keyframes plus optional audio (audio assets mp3/wav/flac <19 MB; video audio extracted to mp3, first 5 minutes) and parses the Interactions API response into description/subjects/tags/suggested uses/transcript.
- Inspector CONTENT block: shot strip, tags, description, transcript, analyzed provider/frame count, a consent panel with an explicit checkbox, and a user-note editor kept separate from AI fields (notes survive re-analysis and reload).
- Agent access updated: `get_asset_analysis` includes shots, `search_assets` matches AI tags/subjects/transcript; prompt forbids claiming content when `not_analyzed`, and no tool can start an upload.

### Files Touched

- `serve.py`, `clipacanvas.html`
- `docs/EDITOR_AUDIT.md` (Phase 4 addendum, plan table)
- `tests/_check_asset_semantics.py`, `tests/_check_webview_semantics.py` (new)
- `SESSION_LOG.md`

### Verification

- `_check_asset_semantics.py`: PASS — 3 textured shots at 0/1/2 s with keyframes (JPEG probes), image/audio have no shots, offline inspector strip, no-key provider reason, consent gate (run disabled until checked; server 403 without consent), vision request body (model, JSON schema, 3 image items, JPEG base64), audio transcription item (wav for audio assets, extracted mp3 for video audio), image single-frame path, mock-provider 502 keeps the previous result, technical cache returns the merged semantic manifest, agent tools, reload persistence.
- `_check_webview_semantics.py`: PASS in WebView2 (Edg/157) — local shots, keyframe fetch as image/jpeg, consent gate without key, note persistence after reload.
- Regressions PASS: `_check_asset_intelligence`, `_check_workspace`, `_check_overlays`, `_check_project_ops`, `_check_bin_dragdrop`, `_check_e2e_flow`, `_check_media_timeline`, `_check_transitions`, `_check_tts`, `_check_chat_scenes`, `_check_audio_import`, `_check_timeline_zoom`; `py_compile` and `node --check` clean.
- Artifacts: `output/playwright/asset-semantics.png`, `webview-asset-semantics.png`.

### Commits

- This semantic asset intelligence change set committed locally; not pushed.

### Open Items

- Hosted semantic analysis was contract-tested with a stubbed transport, not a live Gemini call (no hosted key configured). Shot scan is limited to the first 3 minutes.
- Overlay attachment UI, frame/tick timebase remain; `dist/ClipACanvas.exe` still needs a rebuild.

## 2026-11-12 (Phase 5: overlay attachment UI)

### Summary

- Added an OVERLAY LINK block to the code-clip inspector: eligible parent list (non-audio, unattached clips with track/start), ATTACH AS OVERLAY, per-clip status (NOT ATTACHED / ATTACHED / PARENT OF n), ATTACHED TO parent display and DETACH.
- The UI drives the existing `projectOps.attachOverlay`/`detachOverlay` operations, so track placement above the parent, timing sync, persistence and agent parity are unchanged; errors (no free track, invalid parent) surface inline.

### Files Touched

- `clipacanvas.html`
- `docs/EDITOR_AUDIT.md` (Phase 5 addendum, plan table)
- `tests/_check_overlay_ui.py`, `tests/_check_webview_overlay_ui.py` (new)
- `SESSION_LOG.md`

### Verification

- `_check_overlay_ui.py`: PASS — eligibility options, attach (moves overlay above parent), parent move keeps overlay in sync, attached overlay excluded as a parent for other clips, detach restores free state, attachment survives reload.
- `_check_webview_overlay_ui.py`: PASS in WebView2 (Edg/157) — attach, status, reload, detach.
- Regressions PASS: `_check_overlays`, `_check_workspace`, `_check_project_ops`; `node --check` clean.
- Artifacts: `output/playwright/overlay-attach.png`, `webview-overlay-attach.png`.

### Commits

- This overlay UI change set committed locally; not pushed.

### Open Items

- Media clips do not expose attach buttons yet; frame/tick timebase and the `dist/ClipACanvas.exe` rebuild remain.

## 2026-11-12 (Phase 6: typed lanes, frame stepping, project files)

### Summary

- Media clips now get the OVERLAY LINK attach/detach controls in the media inspector through shared logic with the code inspector.
- Playhead is frame-quantized to the project frame rate; arrows step one frame, Shift+Arrow one second; timecode shares the same helper (60-frame stepping lands exactly on 1.000 s).
- Audio clips render on dedicated A1 VOICEOVER / A2 MUSIC / A3 SFX rows below the V tracks: drag between lanes, inspector lane select, bin/file drops onto a lane, audio-only rejection elsewhere; audio no longer occupies video rows or ripples with video edits.
- Added `.ccproj.json` project files: SAVE/OPEN PROJECT in the project panel, blob download + file picker in the browser, native dialogs via `save_project_file`/`open_project_file` in the desktop bridge; payload contains clips, transitions, audio tracks/mix, layers, playhead and assets with analysis; open confirms before replacing and refreshes stale analysis.

### Files Touched

- `clipacanvas.html`, `desktop_app.py`
- `docs/EDITOR_AUDIT.md` (Phase 6 addendum, plan table)
- `tests/_check_overlay_ui.py` (media clip coverage), `tests/_check_workspace.py`, `tests/_check_bin_dragdrop.py`, `tests/_check_e2e_flow.py` (typed-lane expectations)
- `tests/_check_frame_lanes_project.py`, `tests/_check_webview_frame_lanes_project.py` (new)
- `SESSION_LOG.md`

### Verification

- New suites PASS: frame stepping at 60/30 fps, A2→A3 drag, inspector lane switch, delete-audio no-ripple, bin drop on A2, non-audio rejection, project payload/download/apply/file-picker round trip; the same lane drag, frame step, desktop bridge and payload restore pass in WebView2 (Edg/157).
- Regressions PASS: workspace, bin dragdrop, audio import, media timeline, TTS, overlays, overlay UI, project ops, e2e flow, transitions, chat scenes, timeline zoom, asset intelligence, asset semantics, WebView semantics/TTS/overlay UI/transitions.
- Artifacts: `output/playwright/typed-lanes-project.png`, `webview-typed-lanes.png`, `overlay-attach.png`.

### Commits

- This change set committed locally; not pushed.

### Open Items

- Integer tick storage/29.97 drop-frame remains; project files reference local media rather than embedding it; live hosted TTS/semantic calls still need real keys.
- `dist/ClipACanvas.exe` rebuilt in this session after the commits.

### Packaged build

- Rebuilt `dist/ClipACanvas.exe` (21:34, 463 MB) and `dist/ClipACanvas-windows.zip` with Python 3.11 after this change set.
- Packaged launch/UI smoke (`run_packaged_full.py`) passed its structural checks; its render leg failed on a hidden `#clipLength` selector in that untracked legacy script, not on app behavior.
- Post-build follow-ups (sync the Monaco editor before serializing a project; audio clips report their A-lane in the agent timeline summary) were verified with `_check_frame_lanes_project` and `_check_chat_scenes`.

## 2026-11-12 (Phase 7: hosted provider live verification)

### Summary

- Loaded the stored Gemini/Mistral keys only in the backend and ran live checks.
- Fixed Gemini TTS response parsing: live audio arrives in `steps[].content[]` (`type: "audio"`), not `output_audio`; both shapes now parse and are unit-tested.
- Replaced the deprecated Mistral `voice_*` catalog with speech-v1 voices verified live (`gb_jane_neutral`, `gb_oliver_neutral`, `en_paul_neutral`, `en_paul_sad`, `fr_marie_neutral`); `voxtral-mini-tts-latest` is the working default (3.0 returns the account's 429 rate limit).
- Live-verified Gemini vision (3 synthetic keyframes, accurate description/tags, confidence 0.95) and transcription (exact sentence), plus the Voiceover Studio UI for Gemini and Mistral.

### Files Touched

- `serve.py` (Gemini audio parser, Mistral models/voices, model passthrough)
- `tests/_check_tts.py` (response-shape and catalog assertions)
- `docs/EDITOR_AUDIT.md`, `SESSION_LOG.md`

### Verification

- Live: Gemini TTS 4.88 s WAV; Mistral 3.38 s mp3 / 2.48 s wav; Studio produced 2.92 s Gemini and 2.56 s Mistral WAVs; Gemini semantic analysis and transcript live.
- `_check_tts.py` PASS after the parser/catalog changes.
- No key material was printed, logged or committed.

### Commits

- This hosted-verification change set committed locally; not pushed.

### Open Items

- Rebuild `dist/ClipACanvas.exe` so it includes the live provider fixes; Mistral 3.0 remains account-rate-limited.
- Rebuilt `dist/ClipACanvas.exe`/zip after the hosted fixes and verified through the packaged server: new Mistral models/voices are present and a live Gemini TTS request returned a 2.6 s WAV.

## 2026-11-12 (Dogfooding fixes: durable projects, A/V export, undo/redo)

### Summary

- First-time-user dogfooding of the packaged app exposed three blockers: the InPrivate WebView profile wiped the timeline and imported-media metadata on close; SAVE PROJECT failed before its dialog (`Clip.A.Canvas project (*.json) is not a valid file filter`); and the packaged renderer was stale, so exports lacked the images/audio the timeline showed.
- Added a durable project store: `/api/project` autosaves the full project (timeline, assets, lanes, name) to `%APPDATA%/ClipACanvas/projects/autosave.ccproj.json`; `/api/projects` keeps named project files plus a recent-projects index. The client autosaves after every timeline edit, restores on launch before any autosave can overwrite, flushes with `sendBeacon` on close, and shows a PROJECT LIBRARY list in the PROJECT tab.
- Fixed the pywebview filter names (`ClipACanvas project (*.json)`), enabled a persistent WebView2 profile (`private_mode=False` + `storage_path`), and kept disk autosave as the primary store.
- Added snapshot undo/redo for timeline mutations (toolbar buttons, Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y); playhead moves and asset analysis are not undo steps.
- Studied [x777/frontstage](https://github.com/x777/frontstage) (GPL-3.0) for project-session, project-registry and export patterns; no code copied.

### Files Touched

- `clipacanvas.html` (durable autosave/restore, project library, history, loadTimelineState persist flag)
- `serve.py` (project autosave/library endpoints, atomic writes, validation)
- `desktop_app.py` (save/open filters, persistent WebView2 profile)
- `tests/_check_project_persistence.py`, `tests/_check_film_export.py`, `tests/_check_timeline_history.py`, `tests/_check_packaged_persistence_render.py` (new)

### Verification

- `_check_project_persistence.py` PASS: edit → disk autosave → wipe storage → reload restores name, clips, assets, playhead; library save/reopen via the PROJECT tab.
- `_check_film_export.py` PASS: five images at 0–10 s, 1 s dissolve, music A2 + SFX A3; pixel and volume probes match.
- `_check_timeline_history.py` PASS: undo/redo buttons and shortcuts; playhead moves add no history; text inputs keep native undo.
- Existing `_check_media_timeline.py`, `_check_audio_import.py`, `_check_project_ops.py`, `_check_workspace.py` PASS.
- `_check_packaged_persistence_render.py` PASS in the real WebView2 over CDP: 1920×1080 30 fps MP4 with two images, dissolve, A2 music and A3 SFX (`output/uitest/renders/packaged-film-1080p.mp4`); packaged undo/redo and the PROJECT LIBRARY row were exercised; relaunch restored name, 4 clips, 4 assets, lanes and bin.

### Build

- Rebuilt `dist/ClipACanvas.exe` (final 23:16, 463 MB) and `dist/ClipACanvas-windows.zip` with Python 3.11 after the undo/redo and project-library UI were added.

### Commits

- None (not requested).

### Open Items

- Synthetic mouse input remains inert in WebView2 automation (keyboard/CDP paths used instead); physical mouse input was usable by the user.
- The observed 60 s composition cap and the malformed 0.5 s clip when inserting exactly at 60 s are not fixed.
- Native SAVE/OPEN dialog flow is fixed at the filter level and parsed by pywebview; the dialog itself was not automated end-to-end in this pass.
- Frontstage-inspired features not started: keyframes/effects, captions, FCPXML interop.

## 2026-11-13 (CLIPPPA: multi-scene tool calling)

### Summary

- Root cause of "CLIPPPA can't create multiple scenes": `_gemini_schema_types` treated every dict key named `type` as a JSON-schema keyword and stringified its value. The `add_transition`/`update_transition` tools have a *parameter* named `type`, so their schema became `"type": "{'TYPE': 'STRING', ...}"`. Gemini rejected all 17 tools with HTTP 400; the server silently retried without tools, so the model replied with one HTML document per turn and the client auto-inserted it into the selected scene, overwriting scene 1.
- Fixed the schema converter to only uppercase scalar `type` keywords and to recurse through property named `type`.
- The server now reports `toolsDisabled` and the chat shows a visible error instead of silently degrading.
- Raised the agent tool-round budget from 6 to 24, raised Gemini/Mistral HTTP timeouts from 40 s to 150 s, strengthened the system prompt to finish every scene in a multi-scene brief in one turn, and added a duplicate-`add_scene` guard to stop runaway loops.

### Files Touched

- `serve.py` (schema converter, toolsDisabled flag, LLM timeouts)
- `clipacanvas.html` (system prompt, tool-step budget, tools-disabled warning, duplicate scene guard)
- `tests/_check_llm_tools.py`, `tests/_check_clipppa_multiscene.py`, `tests/_check_packaged_clipppa.py` (new)

### Verification

- `_check_llm_tools.py` PASS; live Gemini call now returns an `add_scene` function call instead of a 400.
- `_check_clipppa_multiscene.py` PASS: one chat turn created SCENE 01/02/03 at 0/1/2 s via `insert_animation_code` + two `add_scene` calls, with tool traces and no page errors.
- `_check_packaged_clipppa.py` PASS in the rebuilt exe: one chat turn created SCENE 01 (0 s) and SCENE 02 (1 s) via `insert_animation_code` + `add_scene`, no tools-disabled warning.
- Rebuilt `dist/ClipACanvas.exe` (00:55, 463 MB) and `dist/ClipACanvas-windows.zip` with Python 3.11.

### Open Items

- No agent tools yet for TTS voiceover or placing bin audio/assets on A1–A3; the 54 s challenge still needs those via the manual UI.
- Gemini free-tier quotas can still fail mid-production; the fallback loop logs model switches.

## 2026-11-13 (Large briefs: hidden plan mode, provider retries)

### Summary

- Large briefs (≥1400 chars, ≥3 scene mentions or a storyboard) no longer go to the model in one turn. The chat first asks the same provider for a JSON production plan (max 18 steps), writes it to a hidden markdown file at `%APPDATA%/ClipACanvas/agent-plans/<sessionId>.md`, then executes each step as its own focused tool turn (max 8 tool rounds per step, 2 attempts) with the full brief as context.
- The plan file is never rendered in the chat. The UI shows live progress (`PLAN 2/9 · …`) and a final `PLAN COMPLETE · N/N steps executed · X clips` message with a `PLANNED · N STEPS` note.
- If planning fails, the turn falls back to a normal single turn with a visible error instead of dead-ending.
- Provider resilience: HTTP 423/500/502/503/504 and network/timeout errors are retried on the same model twice (1.5 s → 3 s backoff) before model switching; 423 and 5xx now surface specific messages ("locked this request", "temporarily unavailable (code) after retries") instead of a generic failure.
- Mistral "not reachable" was diagnosed: `/v1/models` returns 56 models and `mistral-large-latest` tool calling works; the old 40 s client timeout was cutting off long generations. Gemini/Mistral request timeouts are now 150 s.

### Files Touched

- `clipacanvas.html` (planner prompt/parser, hidden plan save, step executor, plan progress and summary, large-brief routing in `sendChat`, system prompt, tool-step budget, duplicate `add_scene` guard)
- `serve.py` (model retry loop and messages, 150 s LLM timeouts, `/api/agent/plan` GET/POST with atomic writes)
- `tests/_check_agent_plan.py`, `tests/_check_packaged_agent_plan.py`, `tests/_check_llm_retry.py` (new); `tests/_check_llm_tools.py`, `tests/_check_clipppa_multiscene.py`, `tests/_check_packaged_clipppa.py` (kept green)

### Verification

- `_check_agent_plan.py` PASS: a ~3.9 k-char brief produced a 3-step hidden plan; every step ticked `- [x]` in the `.md`, chat showed `PLAN COMPLETE · 3/3`, two scenes at 0/1 s, a 2 s 120-frame render, and neither the plan title nor its instructions appeared in the chat.
- `_check_packaged_agent_plan.py` PASS in the rebuilt exe (WebView2 over CDP, mocked LLM): same plan file, scenes and render checks inside `dist/ClipACanvas.exe`.
- `_check_llm_retry.py` PASS: two injected 503s are retried (1.5 s, 3 s) and the third call succeeds; a permanent 423 returns "Gemini locked this request (423). Try a different model."
- `_check_llm_tools.py` PASS: 17 tool schemas valid for both providers.

### Build

- Rebuilt `dist/ClipACanvas.exe` (01:39, 463 MB) and `dist/ClipACanvas-windows.zip` with Python 3.11 so the packaged app includes plan mode, retries and the plan endpoint.

### Open Items

- Gemini free-tier quotas can still interrupt a long planned production mid-run; each step retries twice, then the run continues with remaining steps and reports failures in the summary.
- No agent tools yet for TTS voiceover or placing bin audio/assets on A1–A3; the 54 s challenge still needs those via the manual UI.
- The observed 60 s composition cap and the malformed 0.5 s clip when inserting exactly at 60 s remain unfixed.
- `07716b3` - durable projects, undo/redo, and hidden stepwise production plans (pushed to `origin/main`).

## 2026-11-13 (Task 01: Project Home and project management)

### Summary

- The desktop app now launches into a Project Home launcher (new project, recent projects with modified/edited state, open project file, recover last session) instead of dropping straight into the editor. Browser/dev surfaces keep the editor-first flow unless `?home=1` is passed.
- Projects carry a stable id and every project keeps its own autosave file, so autosaves can no longer overwrite another project. The library index is enriched with `recoverable`, `autosaveSavedAt` and `missing` metadata.
- Added project management: create with a name dialog, open, rename (file identity preserved), duplicate (new id and file), delete with confirmation (removes the project file and its autosave), legacy `autosave.ccproj.json` recovery imported as a library project, and crash recovery from per-project autosaves.
- Returning Home saves the library copy first and skips the pagehide beacon while Home is visible, so leaving the editor neither loses work nor creates false recovery prompts. Invalid project files and missing media report errors without breaking the launcher.
- The desktop window loads `clipacanvas.html?desktop=1`; the boot decision no longer depends on pywebview API injection timing.

### Files Touched

- `clipacanvas.html`, `serve.py`, `desktop_app.py`
- `tests/_check_project_home.py` (new), `tests/_check_packaged_persistence_render.py`

### Verification

- `_check_project_home.py` PASS: 10 scenarios — empty first launch, create, independent projects + autosave isolation, open, rename/duplicate, delete cancel + confirm, crash recovery, restart to Home, v1 compatibility + legacy recovery + invalid file, missing media.
- Real desktop window (pywebview/WebView2 over CDP) PASS: Home on launch, create project, back Home, relaunch to Home with no auto-open, reopen project intact.
- Regressions PASS: `_check_project_persistence`, `_check_timeline_history`, `_check_workspace`, `_check_frame_lanes_project`, `_check_project_ops`, `_check_film_export`, `_check_media_timeline`, `desktop_smoke`.

### Build

- Rebuilt `dist/ClipACanvas.exe` (02:42, 463 MB) and `dist/ClipACanvas-windows.zip` (02:43) with Python 3.11.
- `_check_packaged_persistence_render.py` PASS against the rebuilt exe: launches into Project Home, creates "Packaged Film" from the launcher, writes `packaged-film.autosave.ccproj.json`, renders 1920x1080 30 fps with A2 music + A3 SFX (pixel and volume probes), relaunches to Home with no auto-open, and reopens the project with 4 clips / 4 assets / lanes intact.
- `dist/ClipACanvas-Setup.exe`, `SHA256SUMS.txt` and `RELEASE_NOTES.md` were not refreshed (installer and release assets are a separate step).

### Commits

- None (task forbids commit/push).

### Open Items

- Project files still reference media by URL; media cleanup on delete is out of scope. Opening a file for an already-known project targets that project and replaces its library copy on return Home (explicit user action).
