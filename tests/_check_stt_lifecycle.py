"""Dictation model lifecycle: load on demand, survive a long request, unload after idle."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORK = Path(tempfile.mkdtemp(prefix="cc-stt-lifecycle-"))
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-stt-lifecycle-keys-")
os.environ["CLIPACANVAS_STT_ASSETS"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "stt" / "assets")
os.environ["CLIPACANVAS_MODEL_IDLE_SECONDS"] = "2"

import serve  # noqa: E402

TEXT = "Create a cinematic title with warm golden light and a slow camera push."
wav = WORK / "lifecycle.wav"
script = (
    "Add-Type -AssemblyName System.Speech; "
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$s.SetOutputToWaveFile('%s'); $s.Speak('%s'); $s.Dispose()" % (wav, TEXT)
)
subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True)

serve._ensure_stt_worker()
assert serve._STT_WORKER.alive(), "worker did not start"
print("worker started")

started = time.time()
result = serve._stt_request(
    {"op": "transcribe", "audio": str(wav), "language": "en"}, timeout=300)
elapsed = time.time() - started
print("transcribed in %.1fs:" % elapsed, result.get("text"))
assert result.get("ok") and "cinematic" in (result.get("text") or "").lower(), result
assert serve._STT_WORKER.alive(), "worker unloaded during a request"

deadline = time.time() + 25
while time.time() < deadline and serve._STT_WORKER.alive():
    time.sleep(0.5)
assert not serve._STT_WORKER.alive(), "idle dictation model did not unload"
print("unloaded after idle")

serve._ensure_stt_worker()
assert serve._STT_WORKER.alive(), "worker did not reload"
print("reloaded on next use")
serve._STT_WORKER.stop()
print("STT LIFECYCLE CHECK: OK")
