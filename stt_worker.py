"""Persistent local English speech-to-text worker.

Records microphone audio with sounddevice and transcribes it with
faster-whisper small.en (CTranslate2 int8, CPU). JSON lines on stdin/stdout;
library chatter goes to stderr so the parent only sees protocol messages.
The model loads on demand, keeps punctuation and capitalisation, and never
touches the GPU, leaving VRAM for rendering and narration.
"""

import argparse
import contextlib
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

SAMPLE_RATE = 16000
MAX_RECORD_SECONDS = 120.0
MODEL_LABEL = "faster-whisper-small.en"
MODEL_DIR_NAME = "faster-whisper-small.en"
MODEL_BASE_URL = "https://huggingface.co/Systran/faster-whisper-small.en/resolve/main"

# Expected sizes only drive the progress bar; actual Content-Length wins.
MODEL_FILES = (
    ("config.json", 2657),
    ("tokenizer.json", 2128466),
    ("vocabulary.txt", 422309),
    ("model.bin", 483545366),
)
MODEL_TOTAL_BYTES = sum(size for _name, size in MODEL_FILES)

EMIT_LOCK = threading.Lock()


def emit(payload: dict) -> None:
    with EMIT_LOCK:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def note(message: str) -> None:
    try:
        sys.stderr.write(f"[stt] {message}\n")
        sys.stderr.flush()
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", required=True)
    parser.add_argument("--model", default=MODEL_LABEL)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    if os.environ.get("CLIPACANVAS_STT_DEBUG") == "1":
        import faulthandler
        faulthandler.enable()
        faulthandler.dump_traceback_later(20, repeat=True)

    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    assets = Path(args.assets)
    assets.mkdir(parents=True, exist_ok=True)
    models_root = assets / "models"
    marker_path = assets / "model-ready.json"

    with contextlib.redirect_stdout(sys.stderr):
        import numpy as np
        import sounddevice as sd
        import soundfile as sf
        from faster_whisper import WhisperModel

    override = (os.environ.get("CLIPACANVAS_STT_MODEL_DIR") or "").strip()
    model_dir = Path(override) if override else models_root / MODEL_DIR_NAME

    def model_ready(path: Path) -> bool:
        return all((path / name).is_file() for name, _size in MODEL_FILES)

    def input_device_name() -> str:
        wanted = os.environ.get("CLIPACANVAS_STT_INPUT", "").strip().lower()
        try:
            if wanted:
                for info in sd.query_devices():
                    name = str(info.get("name") or "")
                    if info.get("max_input_channels", 0) > 0 and wanted in name.lower():
                        return name
            return str(sd.query_devices(kind="input")["name"])
        except Exception:
            return ""

    state = {
        "model": None,
        "modelState": "idle",
        "modelError": "",
        "loadThread": None,
        "progress": {"stage": "", "pct": 0, "detail": ""},
        "lastText": "",
    }

    def set_progress(stage: str, pct: int, detail: str) -> None:
        state["progress"] = {"stage": stage, "pct": int(pct), "detail": detail}
        emit({"event": "progress", "stage": stage, "pct": int(pct), "detail": detail})

    def download_model() -> Path:
        if model_ready(model_dir):
            return model_dir
        model_dir.mkdir(parents=True, exist_ok=True)
        done = sum(
            (model_dir / name).stat().st_size
            for name, _size in MODEL_FILES
            if (model_dir / name).is_file()
        )
        for name, _size in MODEL_FILES:
            target = model_dir / name
            if target.is_file() and target.stat().st_size > 0:
                continue
            part = target.with_suffix(target.suffix + ".part")
            request = urllib.request.Request(
                f"{MODEL_BASE_URL}/{name}?download=true",
                headers={"User-Agent": "ClipACanvas/dictation"},
            )
            with urllib.request.urlopen(request, timeout=120) as response, open(part, "wb") as handle:
                total = int(response.headers.get("Content-Length") or 0)
                file_done = 0
                last_emit = 0.0
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    handle.write(chunk)
                    file_done += len(chunk)
                    now = time.time()
                    if now - last_emit >= 0.5:
                        last_emit = now
                        pct = int(95 * min(1.0, (done + file_done) / MODEL_TOTAL_BYTES))
                        set_progress(
                            "download", pct,
                            f"Downloading English speech model · "
                            f"{(done + file_done) // 1048576}/{MODEL_TOTAL_BYTES // 1048576} MB",
                        )
            if total and file_done < total:
                raise RuntimeError(f"The {name} download ended early.")
            os.replace(part, target)
            done += target.stat().st_size
        if not model_ready(model_dir):
            raise RuntimeError("The English speech model could not be installed.")
        return model_dir

    def load_model() -> None:
        try:
            note("loading faster-whisper small.en")
            state["modelState"] = "loading"
            set_progress("download", 0, "Preparing English speech model")
            path = download_model()
            set_progress("load", 96, "Loading English speech model")
            threads = max(1, min(8, os.cpu_count() or 4))
            state["model"] = WhisperModel(
                str(path),
                device="cpu",
                compute_type="int8",
                cpu_threads=threads,
                num_workers=1,
                local_files_only=True,
            )
            state["modelState"] = "ready"
            state["modelError"] = ""
            try:
                marker_path.write_text(json.dumps({
                    "model": MODEL_LABEL,
                    "engine": "faster-whisper",
                    "computeType": "int8",
                    "dir": str(path),
                    "at": time.time(),
                }), encoding="utf-8")
            except OSError:
                pass
            set_progress("ready", 100, "English speech model ready")
            emit({"event": "model", "state": "ready", "device": "cpu", "model": MODEL_LABEL})
        except Exception as exc:
            state["modelState"] = "error"
            state["modelError"] = str(exc)[:500]
            emit({"event": "model", "state": "error", "error": state["modelError"]})

    def ensure_loading() -> str:
        if state["model"] is not None:
            return "ready"
        if state["modelState"] == "loading" and state["loadThread"] and state["loadThread"].is_alive():
            return "loading"
        state["modelState"] = "loading"
        state["modelError"] = ""
        thread = threading.Thread(target=load_model, name="whisper-load", daemon=True)
        state["loadThread"] = thread
        thread.start()
        return "loading"

    def resample(audio, src_rate: int, dst_rate: int):
        if src_rate == dst_rate or len(audio) == 0:
            return audio
        out_len = int(round(len(audio) * dst_rate / float(src_rate)))
        if out_len <= 0:
            return audio[:0]
        src_x = np.arange(len(audio), dtype=np.float64)
        dst_x = np.linspace(0, len(audio) - 1, out_len)
        return np.interp(dst_x, src_x, audio).astype(np.float32)

    recorder = {
        "stream": None,
        "chunks": [],
        "rate": SAMPLE_RATE,
        "frames": 0,
        "peak": 0.0,
        "started": 0.0,
    }
    recorder_lock = threading.Lock()

    def record_callback(indata, frames, time_info, status) -> None:
        with recorder_lock:
            if recorder["stream"] is None:
                return
            if recorder["frames"] >= int(MAX_RECORD_SECONDS * recorder["rate"]):
                return
            mono = np.asarray(indata[:, 0], dtype=np.float32).copy()
            recorder["chunks"].append(mono)
            recorder["frames"] += len(mono)
            if len(mono):
                peak = float(np.max(np.abs(mono)))
                if peak > recorder["peak"]:
                    recorder["peak"] = peak

    def record_start() -> dict:
        with recorder_lock:
            if recorder["stream"] is not None:
                return {"ok": True, "recording": True, "rate": recorder["rate"]}
            recorder["chunks"] = []
            recorder["frames"] = 0
            recorder["peak"] = 0.0
            errors = []
            stream = None
            rate = SAMPLE_RATE
            for candidate in (16000, 48000, 44100):
                try:
                    stream = sd.InputStream(
                        samplerate=candidate, channels=1, dtype="float32",
                        callback=record_callback,
                    )
                    stream.start()
                    rate = candidate
                    break
                except Exception as exc:
                    errors.append(f"{candidate} Hz: {exc}")
                    stream = None
            if stream is None:
                return {"ok": False, "error": "Microphone unavailable. " + " | ".join(errors)[:300]}
            recorder["stream"] = stream
            recorder["rate"] = rate
            recorder["started"] = time.time()
        return {"ok": True, "recording": True, "rate": rate, "input": input_device_name()}

    def close_stream() -> dict:
        with recorder_lock:
            stream = recorder["stream"]
            recorder["stream"] = None
            chunks = recorder["chunks"]
            recorder["chunks"] = []
            rate = recorder["rate"]
            peak = recorder["peak"]
            started = recorder["started"]
        if stream is not None:
            try:
                stream.stop()
            finally:
                try:
                    stream.close()
                except Exception:
                    pass
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        duration = len(audio) / float(rate) if rate else 0.0
        return {"audio": audio, "rate": rate, "peak": peak, "duration": duration, "started": started}

    def record_stop(out_path: Path) -> dict:
        captured = close_stream()
        audio = resample(captured["audio"], captured["rate"], SAMPLE_RATE)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(out_path), audio, SAMPLE_RATE, subtype="PCM_16")
        return {
            "ok": True,
            "duration": round(len(audio) / float(SAMPLE_RATE), 3),
            "peak": round(float(captured["peak"]), 4),
        }

    def record_cancel() -> dict:
        captured = close_stream()
        return {"ok": True, "duration": round(captured["duration"], 3)}

    def transcribe(audio_path: Path, language: str) -> dict:
        if state["model"] is None:
            ensure_loading()
            thread = state["loadThread"]
            if thread is not None:
                thread.join()
        model = state["model"]
        if model is None:
            return {"ok": False, "error": state["modelError"] or "The English speech model failed to load."}
        with sf.SoundFile(str(audio_path)) as handle:
            audio = handle.read(dtype="float32", always_2d=True).mean(axis=1)
            rate = int(handle.samplerate or SAMPLE_RATE)
        audio = resample(np.asarray(audio, dtype=np.float32), rate, SAMPLE_RATE)
        duration = len(audio) / float(SAMPLE_RATE)
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0
        window = SAMPLE_RATE // 10
        loudest = 0.0
        if len(audio) >= window:
            frames = audio[: len(audio) - (len(audio) % window)].reshape(-1, window)
            loudest = float(np.sqrt(np.mean(np.square(frames), axis=1)).max())
        empty = {
            "ok": True, "text": "", "silent": True, "duration": round(duration, 3),
            "peak": round(peak, 4), "rms": round(rms, 4),
        }
        if duration < 0.3 or loudest < 0.02:
            return empty

        set_progress("transcribe", 0, "Transcribing")
        segments, _info = model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            condition_on_previous_text=False,
            without_timestamps=False,
            temperature=0.0,
        )
        parts = []
        logprobs = []
        no_speech = []
        for segment in segments:
            piece = " ".join(str(segment.text or "").split())
            if piece:
                parts.append(piece)
            if segment.avg_logprob is not None:
                logprobs.append(float(segment.avg_logprob))
            if segment.no_speech_prob is not None:
                no_speech.append(float(segment.no_speech_prob))
        text = " ".join(parts).strip()
        confidence = 0.0
        if logprobs:
            confidence = float(np.exp(sum(logprobs) / len(logprobs)))
        if not text:
            return {**empty, "language": "en", "confidence": round(confidence, 3)}
        state["lastText"] = text
        set_progress("ready", 100, "English speech model ready")
        return {
            "ok": True,
            "text": text,
            "language": "en",
            "confidence": round(min(1.0, max(0.0, confidence)), 3),
            "noSpeech": round(max(no_speech), 3) if no_speech else 0.0,
            "duration": round(duration, 3),
            "peak": round(peak, 4),
            "rms": round(rms, 4),
            "silent": False,
        }

    def status() -> dict:
        with recorder_lock:
            recording = recorder["stream"] is not None
            elapsed = round(time.time() - recorder["started"], 2) if recording else 0.0
            peak = round(float(recorder["peak"]), 4)
        return {
            "ok": True,
            "model": MODEL_LABEL,
            "modelState": state["modelState"],
            "modelError": state["modelError"],
            "modelLoaded": state["model"] is not None,
            "device": "cpu",
            "input": input_device_name(),
            "recording": recording,
            "elapsed": elapsed,
            "peak": peak,
            "progress": state["progress"],
        }

    cached = model_ready(model_dir)
    emit({
        "event": "ready",
        "device": "cpu",
        "input": input_device_name(),
        "model": MODEL_LABEL,
        "modelCached": cached,
    })

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            emit({"ok": False, "error": "Invalid worker request."})
            continue
        op = str(request.get("op") or "").strip()
        try:
            if op == "status":
                emit(status())
            elif op == "prepare":
                emit({"ok": True, "state": ensure_loading(), "model": MODEL_LABEL, "device": "cpu"})
            elif op == "record_start":
                emit(record_start())
            elif op == "record_stop":
                raw_out = str(request.get("out") or "").strip()
                if not raw_out:
                    raise ValueError("Output path is required.")
                emit(record_stop(Path(raw_out)))
            elif op == "record_cancel":
                emit(record_cancel())
            elif op == "transcribe":
                audio_path = Path(str(request.get("audio") or ""))
                if not audio_path.exists():
                    raise ValueError("Audio file is missing.")
                emit(transcribe(audio_path, str(request.get("language") or "en")))
            else:
                emit({"ok": False, "error": f"Unknown operation: {op}"})
        except Exception as exc:
            emit({"ok": False, "error": str(exc)[:500]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
