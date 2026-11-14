"""Persistent Piper speech worker (JSON lines on stdin/stdout)."""

import argparse
import contextlib
import json
import re
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voices", required=True)
    args = parser.parse_args()

    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    voices_dir = Path(args.voices)

    with contextlib.redirect_stdout(sys.stderr):
        import numpy as np
        import soundfile as sf
        from piper import PiperVoice
        from piper.config import SynthesisConfig

    print(json.dumps({"event": "ready", "device": "cpu"}), flush=True)
    cache = {}

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            print(json.dumps({"ok": False, "error": "Invalid worker request."}), flush=True)
            continue
        try:
            text = str(request.get("text") or "").strip()
            if not text:
                raise ValueError("Empty script.")
            voice_id = str(request.get("voice") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9._-]+", voice_id):
                raise ValueError("Invalid voice id.")
            model_path = voices_dir / f"{voice_id}.onnx"
            if not model_path.exists():
                raise ValueError(f"Voice model {voice_id} is not installed.")
            speed = min(2.0, max(0.5, float(request.get("speed") or 1.0)))
            out = Path(str(request.get("out") or ""))
            out.parent.mkdir(parents=True, exist_ok=True)
            with contextlib.redirect_stdout(sys.stderr):
                if voice_id not in cache:
                    cache[voice_id] = PiperVoice.load(str(model_path))
                chunks = list(cache[voice_id].synthesize(text, syn_config=SynthesisConfig(length_scale=1.0 / speed)))
            if not chunks:
                raise RuntimeError("No audio produced.")
            audio = np.concatenate([chunk.audio_float_array for chunk in chunks]).astype("float32")
            sample_rate = int(chunks[0].sample_rate)
            sf.write(str(out), audio, sample_rate, subtype="PCM_16")
            print(json.dumps({
                "ok": True,
                "duration": round(float(len(audio) / sample_rate), 3),
                "sampleRate": sample_rate,
            }), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)[:500]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
