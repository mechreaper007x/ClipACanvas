"""Local model lifecycle: load on demand, unload after idle, restart."""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-lifecycle-")
os.environ["CLIPACANVAS_EMBEDDING_PYTHON"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "litert" / "python" / "Scripts" / "python.exe")
os.environ["CLIPACANVAS_EMBEDDING_ASSETS"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "litert" / "assets")
os.environ["CLIPACANVAS_EMBEDDING_DEVICE"] = "cpu"
os.environ["CLIPACANVAS_MODEL_IDLE_SECONDS"] = "2"

import serve

request = {"kind": "text", "texts": ["idle lifecycle probe"], "prompt": "Retrieval-query"}
first = serve._embedding_request(request)
assert first.get("ok") and serve._EMBEDDING_WORKER.alive(), first
print("loaded on demand")

deadline = time.time() + 20
while time.time() < deadline and serve._EMBEDDING_WORKER.alive():
    time.sleep(0.5)
assert not serve._EMBEDDING_WORKER.alive(), "idle worker did not unload"
print("unloaded after idle")

second = serve._embedding_request(request)
assert second.get("ok") and serve._EMBEDDING_WORKER.alive(), second
print("reloaded on next request")
serve._EMBEDDING_WORKER.stop()
print("MODEL LIFECYCLE CHECK: OK")
