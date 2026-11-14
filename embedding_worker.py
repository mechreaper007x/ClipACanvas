"""Persistent EmbeddingGemma 2 worker for local visual analysis.

Run by the optional embedding runtime interpreter, never by the app's bundled
Python. JSON lines on stdin/stdout; model chatter goes to stderr.
"""

import argparse
import contextlib
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from sentence_transformers import SentenceTransformer

        device = args.device
        if device not in ("cpu", "cuda"):
            free_card = False
            if torch.cuda.is_available():
                try:
                    free_card = torch.cuda.get_device_properties(0).total_memory >= 8 * 1024**3
                except Exception:
                    free_card = False
            device = "cuda" if free_card else "cpu"
        dtype = torch.float32
        if device == "cuda":
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
        model = SentenceTransformer(
            args.assets,
            device=device,
            model_kwargs={"torch_dtype": dtype},
            config_kwargs={"audio_config": None},
        )
        label_vectors = {}
    print(json.dumps({"event": "ready", "device": device}), flush=True)

    def embed_texts(texts, prompt_name):
        kwargs = {"normalize_embeddings": True, "convert_to_numpy": True}
        if prompt_name:
            kwargs["prompt_name"] = prompt_name
        with contextlib.redirect_stdout(sys.stderr):
            return model.encode(texts, **kwargs)

    def embed_images(paths):
        with contextlib.redirect_stdout(sys.stderr):
            return model.encode(paths, normalize_embeddings=True, convert_to_numpy=True)

    def label_matrix(labels):
        missing = [label for label in labels if label not in label_vectors]
        if missing:
            vectors = embed_texts([f"a photo of {label}" for label in missing], "Classification")
            for label, vector in zip(missing, vectors):
                label_vectors[label] = vector
        import numpy as np
        return np.stack([label_vectors[label] for label in labels])

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
            kind = str(request.get("kind") or "")
            if kind == "text":
                vectors = embed_texts([str(text) for text in request.get("texts") or []],
                                      request.get("prompt") or None)
                print(json.dumps({"ok": True, "vectors": vectors.tolist()}), flush=True)
            elif kind == "tags":
                import numpy as np
                paths = [str(path) for path in request.get("paths") or []]
                labels = [str(label) for label in request.get("labels") or []]
                topk = max(1, min(20, int(request.get("topk") or 5)))
                if not paths or not labels:
                    raise ValueError("paths and labels are required")
                images = embed_images(paths)
                matrix = label_matrix(labels)
                scores = images @ matrix.T
                results = []
                for row, vector in zip(scores, images):
                    order = np.argsort(-row)[:topk]
                    results.append({
                        "tags": [{"label": labels[int(i)], "score": round(float(row[int(i)]), 4)}
                                 for i in order],
                        "vector": [round(float(value), 6) for value in vector],
                    })
                print(json.dumps({"ok": True, "results": results, "dim": int(images.shape[1])}), flush=True)
            elif kind == "images":
                paths = [str(path) for path in request.get("paths") or []]
                vectors = embed_images(paths)
                print(json.dumps({"ok": True, "vectors": vectors.tolist()}), flush=True)
            else:
                raise ValueError(f"Unknown request kind: {kind}")
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)[:500]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
