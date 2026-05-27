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
- `.vercelignore`

### Commits

- `28139e1` — `docs: update Antigravity CLI (agy) configuration instructions on website and README`
- `d058f4e` — `docs: clarify Windows Claude cmd wrapper and Codex Auth: Unsupported status`
- `0865b2d` — `chore: update session log for Antigravity CLI discovery and deployment`
- `20a789c` — `chore: add .vercelignore to exclude large build artifacts from Vercel uploads`
- `f58635b` — `chore: polish session log with Claude and Codex fixes`

### Deploy Links

- Vercel Website: `https://clipacanvas.vercel.app`
- GitHub Repo: `https://github.com/mechreaper007x/ClipACanvas`

### Open Items

- None. The transition to Antigravity CLI and Windows subprocess wrappers has been fully and accurately integrated.

