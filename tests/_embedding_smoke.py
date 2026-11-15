"""Calibrate EmbeddingGemma 2: load time, text alignment, zero-shot tag scores."""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
PYTHON = Path(r"C:\Users\Savyasachi Mishra\AppData\Roaming\ClipACanvas\runtimes\litert\python\Scripts\python.exe")
ASSETS = Path(r"C:\Users\Savyasachi Mishra\AppData\Roaming\ClipACanvas\runtimes\litert\assets")
FOOTBALL = ROOT / "output" / "uitest" / "embed" / "football.jpg"
SCENE = ROOT / "output" / "uitest" / "embed" / "scene.jpg"

started = time.time()
proc = subprocess.Popen(
    [str(PYTHON), str(ROOT / "embedding_litert_worker.py"), "--model", str(ASSETS / "embeddinggemma-2-740m.litertlm"), "--device", sys.argv[1] if len(sys.argv) > 1 else "cpu"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, encoding="utf-8", errors="replace", bufsize=1,
)
print("ready:", proc.stdout.readline().strip(), f"after {time.time() - started:.1f}s", flush=True)


def request(payload):
    started = time.time()
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    reply = json.loads(proc.stdout.readline())
    print(f"{payload.get('kind')} in {time.time() - started:.2f}s", flush=True)
    return reply


texts = request({"kind": "text", "prompt": "SearchQuery", "texts": [
    "a boy playing football on a grass field",
    "a car driving on a highway at night",
]})
images = request({"kind": "images", "paths": [str(FOOTBALL), str(SCENE)]})
import math

def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))

for name, vector in zip(("football.jpg", "scene.jpg"), images["vectors"]):
    print(name, "football-text:", round(cosine(vector, texts["vectors"][0]), 3),
          "car-text:", round(cosine(vector, texts["vectors"][1]), 3))

tags = request({"kind": "tags", "paths": [str(FOOTBALL), str(SCENE)],
                "labels": json.loads(subprocess.run(
                    [sys.executable, "-c", "import sys,json; sys.path.insert(0, r'C:\\Users\\Savyasachi Mishra\\Desktop\\clipacanvas'); import serve; print(json.dumps(serve.VISUAL_LABELS))"],
                    capture_output=True, text=True).stdout),
                "topk": 8})
for path, result in zip(("football.jpg", "scene.jpg"), tags["results"]):
    print(path, [(tag["label"], tag["score"]) for tag in result["tags"]], flush=True)
print("dim:", tags.get("dim"))
proc.stdin.close()
proc.wait(timeout=30)
print("stderr tail:", (proc.stderr.read() or "")[-400:])
