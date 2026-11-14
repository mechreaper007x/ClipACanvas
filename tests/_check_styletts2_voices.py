"""StyleTTS2 multi-voice catalog: reference voices synthesize distinct narrators."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-sts2-voices-")

import serve
from serve import _media_dir, synthesize_speech

STS_PY = ROOT / ".venvs" / "sts2" / "Scripts" / "python.exe"
TEXT = "A river remembers every stone it passes, and every mile is a different story."

registry = serve.tts_provider_registry()
styletts2 = next(provider for provider in registry["providers"] if provider["id"] == "styletts2")
voices = {voice["id"]: voice for voice in styletts2["voices"]}
print("styletts2 voices:", [(voice["id"], voice["gender"]) for voice in styletts2["voices"]])
assert styletts2["available"], styletts2["reason"]
assert len(voices) >= 8, voices
assert voices["default"]["gender"] == "female"
assert voices["libritts-4077"]["gender"] == "male"
assert len([voice for voice in styletts2["voices"] if voice["gender"] == "male"]) >= 4

female = synthesize_speech({"provider": "styletts2", "voice": "default", "text": TEXT})
male = synthesize_speech({"provider": "styletts2", "voice": "libritts-4077", "text": TEXT})
print("female:", {key: female.get(key) for key in ("provider", "voice", "duration", "url")})
print("male:", {key: male.get(key) for key in ("provider", "voice", "duration", "url")})
assert female["ok"] and male["ok"], (female, male)
assert female["voice"] == "default" and male["voice"] == "libritts-4077"
assert female["url"] != male["url"]
assert 0.5 < float(female["duration"]) and 0.5 < float(male["duration"])

probe = subprocess.run(
    [str(STS_PY), "-c", """
import json, sys
import librosa, numpy as np
result = {}
for path in sys.argv[1:]:
    audio, rate = librosa.load(path, sr=16000)
    f0, _, _ = librosa.pyin(audio, fmin=50, fmax=500, sr=rate, frame_length=1024)
    voiced = f0[~np.isnan(f0)]
    result[path] = float(np.median(voiced))
print(json.dumps(result))
""", str(_media_dir() / female["filename"]), str(_media_dir() / male["filename"])],
    capture_output=True, text=True, timeout=180,
)
assert probe.returncode == 0, probe.stderr[-800:]
pitch = list(json.loads(probe.stdout.strip().splitlines()[-1]).values())
print("median f0 female/male:", [round(value, 1) for value in pitch])
assert pitch[0] - pitch[1] > 30, pitch
print("PASS styletts2 voices")
