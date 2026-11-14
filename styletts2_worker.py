"""Persistent StyleTTS2 speech worker.

Run by the optional StyleTTS2 runtime interpreter, never by the app's bundled
Python. The protocol is JSON lines on stdin/stdout; model chatter is redirected
to stderr so the parent only sees protocol messages.
"""

import argparse
import contextlib
import json
import sys
from pathlib import Path


def configure_checkpoint_loading(assets: Path) -> None:
    import torch

    # The official StyleTTS2 util files are training checkpoints (optimizer
    # state included), which torch's restricted loader cannot deserialize.
    original_load = torch.load
    roots = (str(assets), str(Path.home() / ".cache" / "cached_path"))

    def scoped_load(*args, **kwargs):
        path = str(args[0]) if args else str(kwargs.get("f", ""))
        if path.startswith(roots):
            kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    torch.load = scoped_load


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", required=True)
    args = parser.parse_args()

    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    assets = Path(args.assets)
    configure_checkpoint_loading(assets)

    with contextlib.redirect_stdout(sys.stderr):
        import styletts2.tts as sts
        from cached_path import cached_path
        from styletts2 import tts

        sts.ASR_CONFIG_URL = str(assets / "asr-config.yml")
        sts.ASR_CHECKPOINT_URL = str(assets / "epoch_00080.pth")
        sts.F0_CHECKPOINT_URL = str(assets / "bst.t7")
        sts.BERT_CONFIG_URL = str(assets / "plbert-config.yml")
        sts.BERT_CHECKPOINT_URL = str(assets / "step_1000000.t7")

        engine = tts.StyleTTS2()
        style = engine.compute_style(cached_path(sts.DEFAULT_TARGET_VOICE_URL))
        styles = {"": style}
        device = engine.device
    print(json.dumps({"event": "ready", "device": device}), flush=True)

    def style_for(reference: str):
        if not reference:
            return styles[""]
        path = Path(reference)
        if not path.exists():
            raise ValueError(f"Voice reference is missing: {path.name}")
        key = str(path.resolve())
        if key not in styles:
            with contextlib.redirect_stdout(sys.stderr):
                styles[key] = engine.compute_style(key)
        return styles[key]

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
            out = Path(str(request.get("out") or ""))
            out.parent.mkdir(parents=True, exist_ok=True)
            ref_style = style_for(str(request.get("ref") or "").strip())
            with contextlib.redirect_stdout(sys.stderr):
                engine.inference(text, output_wav_file=str(out), ref_s=ref_style)
            import soundfile as sf
            audio, rate = sf.read(str(out), dtype="float32", always_2d=True)
            sf.write(str(out), audio, rate, subtype="PCM_16")
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
