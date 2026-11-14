"""Persistent ZONOS3-Mini speech worker.

Run by the optional Zonos runtime interpreter, never by the app's bundled
Python. The protocol is JSON lines on stdin/stdout; model chatter is redirected
to stderr so the parent only sees protocol messages.
"""

import argparse
import contextlib
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    assets = Path(args.assets)
    device = "cuda" if args.device == "cuda" else "cpu"

    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from transformers import AutoModel

        dtype = torch.float32
        if device == "cuda":
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        model = AutoModel.from_pretrained(str(assets), trust_remote_code=True, dtype=dtype)
        model = model.to(device)
        model.eval()
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
            voice = str(request.get("voice") or "").strip()
            if not voice:
                raise ValueError("Voice is required.")
            language = str(request.get("language") or "en_us").strip() or "en_us"
            seed = int(request.get("seed", 0))
            out = Path(str(request.get("out") or ""))
            out.parent.mkdir(parents=True, exist_ok=True)
            with contextlib.redirect_stdout(sys.stderr):
                result = model.generate(text, voice=voice, language=language, seed=seed)
            import soundfile as sf
            sf.write(str(out), result.waveform.numpy(), result.sampling_rate, subtype="PCM_16")
            info = sf.info(str(out))
            print(json.dumps({
                "ok": True,
                "duration": round(float(info.duration), 3),
                "sampleRate": int(info.samplerate),
            }), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)[:500]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
