"""ZONOS3-Mini provider: catalog, CPU synthesis, 44.1 kHz output, Hindi voice."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-zonos-")

import serve
from serve import _media_dir, synthesize_speech

ZONOS_PY = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python" / "Python311" / "python.exe"
ZONOS_ASSETS = Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "zonos" / "assets"
os.environ["CLIPACANVAS_ZONOS_PYTHON"] = str(ZONOS_PY)
os.environ["CLIPACANVAS_ZONOS_ASSETS"] = str(ZONOS_ASSETS)

registry = serve.tts_provider_registry()
zonos = next(provider for provider in registry["providers"] if provider["id"] == "zonos")
voices = {voice["id"]: voice for voice in zonos["voices"]}
print("zonos:", zonos["available"], "|", zonos["reason"])
print("voices:", len(zonos["voices"]), [voice["id"] for voice in zonos["voices"]])
assert zonos["available"], zonos["reason"]
assert len(zonos["voices"]) == 27, voices
assert len([voice for voice in zonos["voices"] if voice["gender"] == "male"]) >= 12
assert len([voice for voice in zonos["voices"] if voice["gender"] == "female"]) >= 12
assert voices["Savannah"]["gender"] == "female"
assert voices["Arjun"]["language"] == "hi-IN"

english = synthesize_speech({"provider": "zonos", "voice": "Savannah",
                             "text": "The sea keeps its own time."})
hindi = synthesize_speech({"provider": "zonos", "voice": "Arjun",
                           "text": "नदियाँ पहाड़ों से बहती हैं।"})
print("english:", {key: english.get(key) for key in ("ok", "duration", "format", "url")})
print("hindi:", {key: hindi.get(key) for key in ("ok", "duration", "format", "url")})
assert english["ok"], english
assert hindi["ok"], hindi
assert english["url"] != hindi["url"]
assert english["format"] == "wav", english
assert 0.3 < float(english["duration"]), english
assert 0.3 < float(hindi["duration"]), hindi

probe = subprocess.run(
    [str(ZONOS_PY), "-c", """
import json, sys
import soundfile as sf
info = sf.info(sys.argv[1])
print(json.dumps({"rate": info.samplerate, "duration": round(info.duration, 3), "channels": info.channels}))
""", str(_media_dir() / english["filename"])],
    capture_output=True, text=True, timeout=120,
)
assert probe.returncode == 0, probe.stderr[-800:]
print("probe:", probe.stdout.strip())
assert '"rate": 44100' in probe.stdout, probe.stdout

male = synthesize_speech({"provider": "zonos", "voice": "Wyatt", "text": "The sea keeps its own time."})
assert male["ok"], male
pitch = subprocess.run(
    [str(ROOT / ".venvs" / "sts2" / "Scripts" / "python.exe"), "-c", """
import json, sys
import librosa, numpy as np
result = {}
for path in sys.argv[1:]:
    audio, rate = librosa.load(path, sr=22050)
    f0, _, _ = librosa.pyin(audio, fmin=50, fmax=500, sr=rate, frame_length=1024)
    voiced = f0[~np.isnan(f0)]
    result[path] = float(np.median(voiced))
print(json.dumps(result))
""", str(_media_dir() / english["filename"]), str(_media_dir() / male["filename"])],
    capture_output=True, text=True, timeout=180,
)
assert pitch.returncode == 0, pitch.stderr[-800:]
values = list(json.loads(pitch.stdout.strip().splitlines()[-1]).values())
print("median f0 Savannah/Wyatt:", [round(value, 1) for value in values])
assert values[0] - values[1] > 25, values
print("PASS zonos")
