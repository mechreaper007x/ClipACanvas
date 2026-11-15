"""Local EmbeddingGemma visual index: image tags, video keyframes, motion."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-embed-")
os.environ["CLIPACANVAS_EMBEDDING_PYTHON"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "litert" / "python" / "Scripts" / "python.exe")
os.environ["CLIPACANVAS_EMBEDDING_ASSETS"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "litert" / "assets")
os.environ["CLIPACANVAS_EMBEDDING_DEVICE"] = "cpu"

import serve

media_dir = Path(os.environ["CLIPACANVAS_KEYS_DIR"]) / "media"
media_dir.mkdir(parents=True)
ffmpeg = serve.resolve_ffmpeg_exe()

shutil.copy(ROOT / "output" / "uitest" / "embed" / "football.jpg", media_dir / "media-0123456789abcdef0123.jpg")
shutil.copy(ROOT / "output" / "boy-football-juggling.mp4", media_dir / "media-0123456789abcdef0124.mp4")
subprocess.run(
    [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1",
     "-i", str(ROOT / "output" / "uitest" / "media" / "scene1.png"),
     "-t", "3", "-r", "15", "-pix_fmt", "yuv420p", str(media_dir / "media-0123456789abcdef0125.mp4")],
    check=True,
)

IMAGE = "media-0123456789abcdef0123.jpg"
VIDEO = "media-0123456789abcdef0124.mp4"
STATIC = "media-0123456789abcdef0125.mp4"

image = serve.analyze_media_file(IMAGE)
video = serve.analyze_media_file(VIDEO)
still = serve.analyze_media_file(STATIC)
for name, manifest in ((IMAGE, image), (VIDEO, video), (STATIC, still)):
    visual = manifest["visual"]
    print(name, "| status:", visual.get("status"), "| reason:", visual.get("reason", ""))
    print("  tags:", visual.get("tags"))
    print("  frames:", [(frame["time"], [tag["label"] for tag in frame["tags"]]) for frame in visual.get("frames", [])])
    print("  motion:", (visual.get("motion") or {}).get("score"), (visual.get("motion") or {}).get("label"))
    assert visual["status"] == "indexed", visual
    assert visual["provider"] == "embeddinggemma-2"
    assert visual["tags"], visual
    assert len(visual["frames"]) <= serve.VISUAL_FRAME_LIMIT, visual["frames"]
    assert all(frame["thumb"].startswith("/api/media/frames/") for frame in visual["frames"]), visual["frames"]
    times = [frame["time"] for frame in visual["frames"]]
    assert times == sorted(times), times
    assert (media_dir.parent / "analysis" / f"embeddings-{Path(name).stem}.json").exists()

labels = [tag["label"] for tag in image["visual"]["tags"]]
print("image labels:", labels)
assert any(label in labels for label in
           ("football", "sport", "field", "grass", "person", "child", "sky")), labels
assert image["visual"]["motion"]["label"] == "still"
assert len(image["visual"]["frames"]) == 1, image["visual"]["frames"]
assert len(video["visual"]["frames"]) >= 2, video["visual"]["frames"]

video_motion = video["visual"]["motion"]
still_motion = still["visual"]["motion"]
print("video motion:", video_motion["score"], video_motion["label"],
      "| static motion:", still_motion["score"], still_motion["label"])
assert still_motion["label"] in ("static", "still"), still_motion
assert video_motion["score"] > still_motion["score"], (video_motion, still_motion)
assert any(label in [tag["label"] for tag in video["visual"]["tags"]]
           for label in ("football", "sport", "field", "grass", "person", "child", "sky")), video["visual"]["tags"]

vectors = json.loads((media_dir.parent / "analysis" / f"embeddings-{Path(IMAGE).stem}.json").read_text(encoding="utf-8"))
assert vectors["dim"] == 768 and len(vectors["frames"][0]["vector"]) == 768, vectors["dim"]
print("PASS embeddings")
