"""Persistent Kokoro speech worker (JSON lines on stdin/stdout)."""

import contextlib
import json
import os
import sys
from pathlib import Path

# httpx rejects the NO_PROXY values some Windows shells set; the hub client
# fails before it can read the local model cache.
os.environ.pop("NO_PROXY", None)
os.environ.pop("no_proxy", None)


def main() -> int:
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with contextlib.redirect_stdout(sys.stderr):
        import numpy as np
        import soundfile as sf
        import torch
        from kokoro import KPipeline

        device = "cuda" if torch.cuda.is_available() else "cpu"
        pipelines = {"a": KPipeline(lang_code="a", device=device)}
    print(json.dumps({"event": "ready", "device": device}), flush=True)

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
            voice = str(request.get("voice") or "af_heart")
            speed = min(2.0, max(0.5, float(request.get("speed") or 1.0)))
            out = Path(str(request.get("out") or ""))
            out.parent.mkdir(parents=True, exist_ok=True)
            language = voice[0] if voice else "a"
            with contextlib.redirect_stdout(sys.stderr):
                if language not in pipelines:
                    pipelines[language] = KPipeline(lang_code=language, device=device)
                chunks = [audio for _, _, audio in pipelines[language](text, voice=voice, speed=speed)]
            if not chunks:
                raise RuntimeError("No audio produced.")
            audio = np.concatenate([
                chunk.detach().cpu().numpy() if hasattr(chunk, "detach") else np.asarray(chunk)
                for chunk in chunks
            ]).astype("float32")
            sf.write(str(out), audio, 24000, subtype="PCM_16")
            print(json.dumps({
                "ok": True,
                "duration": round(float(len(audio) / 24000), 3),
                "sampleRate": 24000,
            }), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)[:500]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
