"""The agent must see what footage inside a scene actually shows."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="cc-scene-media-ctx-")

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

SCENE = """<!doctype html><html><head><style>
html,body{margin:0;background:#000;overflow:hidden}
</style></head><body>
<video class="cc-scene-media" src="/media/media-aaaa1111bbbb2222cccc.mp4" data-cc-fill="1" muted playsinline style="position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:20"></video>
<h1 id="title" style="position:fixed;top:20%;left:50%;transform:translateX(-50%);color:#fff;z-index:30">NIGHT</h1>
</body></html>"""

server, thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1480, "height": 960})
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1200)
        result = page.evaluate("""(code) => {
            timelineState.assets = [{
                id: 'asset-wheel',
                name: 'wheel-night.mp4',
                kind: 'video',
                url: '/media/media-aaaa1111bbbb2222cccc.mp4',
                duration: 6,
                analysis: {
                    technical: { width: 1920, height: 1080, fps: 30, duration: 6 },
                    visual: {
                        tags: [{ label: 'neon', score: 0.94 }, { label: 'stage', score: 0.88 }, { label: 'dance', score: 0.81 }],
                        motion: { label: 'camera pans right', score: 0.7 },
                        frames: [
                            { time: 0, tags: [{ label: 'crowd' }, { label: 'lights' }] },
                            { time: 1, tags: [{ label: 'wheel' }, { label: 'neon' }] }
                        ]
                    },
                    semantic: { status: 'done', description: 'A neon stage with dancers' },
                    user: { description: 'Wheel footage from the night shoot', notes: 'keep the logo bottom-right' }
                }
            }];
            timelineState.clips = [{
                id: 'scene-one', name: 'SCENE 01', code, duration: 6, start: 0, track: 0, type: 'code'
            }];
            timelineState.transitions = [];
            timelineState.layers = 4;
            timelineState.activeId = 'scene-one';
            timelineState.playhead = 1;
            const details = sceneMediaDetails(code);
            const app = chatToolAppState();
            const summary = timelineSummaryForChat();
            const context = projectOps.getClipContext('scene-one');
            const messages = buildChatApiMessages('Add voiceover captions over these scenes');
            const mediaMessage = messages.find(m => m.role === 'system' && m.content.startsWith('The media embedded in the selected scene')) || {};
            const selectionMessage = messages.find(m => m.role === 'system' && m.content.startsWith('Current selection:')) || {};
            return {
                details,
                appMedia: app.selectedClip.embeddedMedia,
                summaryMedia: summary.scenes[0].embeddedMedia,
                contextMedia: context.embeddedMedia,
                mediaMessage: mediaMessage.content || '',
                selectionMessage: selectionMessage.content || '',
                prompt: CHAT_SYSTEM_PROMPT
            };
        }""", SCENE)
        details = result["details"][0]
        print("details:", details)
        assert details["assetId"] == "asset-wheel", details
        assert details["name"] == "wheel-night.mp4", details
        assert details["fullFrame"] is True, details
        assert details["durationSeconds"] == 6, details
        assert details["resolution"] == "1920x1080", details
        assert details["description"] == "Wheel footage from the night shoot", details
        assert details["userNotes"] == "keep the logo bottom-right", details
        assert "neon" in details["visualTags"] and "stage" in details["visualTags"], details
        assert details["motion"] == "camera pans right", details
        assert len(details["moments"]) == 2 and details["moments"][1]["atSeconds"] == 1, details

        assert result["appMedia"][0]["visualTags"] == details["visualTags"], result["appMedia"]
        assert result["summaryMedia"][0]["show"] == "Wheel footage from the night shoot", result["summaryMedia"]
        assert result["summaryMedia"][0]["assetId"] == "asset-wheel", result["summaryMedia"]
        assert result["contextMedia"][0]["moments"][0]["atSeconds"] == 0, result["contextMedia"]

        media_message = result["mediaMessage"]
        for needle in ("wheel-night.mp4", "neon", "camera pans right", "Wheel footage from the night shoot", "full-frame background", "Never copy one scene's media"):
            assert needle in media_message, (needle, media_message)
        assert 'code scene "SCENE 01"' in result["selectionMessage"], result["selectionMessage"]
        assert "A caption or subtitle clip is text only" in result["prompt"]
        assert "Embedded media belongs to its own scene only" in result["prompt"]
        assert 'names the object and the operation' in result["prompt"]
        browser.close()
finally:
    stop_server(server)

print("PASS scene media context")
