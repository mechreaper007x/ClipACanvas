"""Persistent LiteRT EmbeddingGemma 2 worker.

Run by the optional LiteRT runtime interpreter, never by the app's bundled
Python. JSON lines on stdin/stdout; runtime chatter goes to stderr.
"""

import argparse
import json
import sys
from pathlib import Path

PROMPTS = {
    "BitextMining": "task: search result | query: ",
    "Classification": "task: classification | query: ",
    "Clustering": "task: clustering | query: ",
    "CodeRetrieval": "task: code retrieval | query: ",
    "Document": "title: none | text: ",
    "FactChecking": "task: fact checking | query: ",
    "InstructionRetrieval": "task: code retrieval | query: ",
    "MultilabelClassification": "task: classification | query: ",
    "PairClassification": "task: sentence similarity | query: ",
    "QuestionAnswering": "task: question answering | query: ",
    "Reranking": "task: search result | query: ",
    "Retrieval": "task: search result | query: ",
    "Retrieval-document": "title: none | text: ",
    "Retrieval-query": "task: search result | query: ",
    "STS": "task: sentence similarity | query: ",
    "SearchQuery": "task: search result | query: ",
    "SentenceSimilarity": "task: sentence similarity | query: ",
    "Summarization": "task: sentence similarity | query: ",
    "document": "title: none | text: ",
    "query": "task: search result | query: ",
}

MODEL_FILE = "embeddinggemma-2-740m.litertlm"


def resolve_model(value: str) -> Path:
    path = Path(value)
    if path.is_file() and path.suffix == ".litertlm":
        return path
    if path.is_dir():
        preferred = path / MODEL_FILE
        if preferred.exists():
            return preferred
        matches = sorted(path.glob("*.litertlm"))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"No .litertlm model found at {value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--model")
    source.add_argument("--assets")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from litert_lm import Backend, Content, EmbeddingEngine, EmbeddingOptions

    model_path = resolve_model(args.model or args.assets)
    requested = str(args.device or "cpu").strip().lower()
    if requested in ("gpu", "cuda"):
        backend, device = Backend.GPU(), "gpu"
    elif requested == "npu":
        backend, device = Backend.NPU(), "npu"
    else:
        backend, device = Backend.CPU(), "cpu"

    def build(target_backend):
        return EmbeddingEngine(str(model_path), backend=target_backend, vision_backend=target_backend)

    try:
        engine = build(backend)
    except Exception:
        if device == "cpu":
            raise
        engine, device = build(Backend.CPU()), "cpu"
    options = EmbeddingOptions(normalize=True)
    label_vectors: dict[str, list[float]] = {}
    print(json.dumps({"event": "ready", "device": device}), flush=True)

    def embed_text(text: str, prompt: str | None) -> list[float]:
        prefix = PROMPTS.get(prompt or "", "")
        return engine.compute_embedding(prefix + text, options).embedding

    def embed_image(path: str) -> list[float]:
        return engine.compute_embedding(Content.ImageFile(path), options).embedding

    def label_vector(label: str) -> list[float]:
        if label not in label_vectors:
            label_vectors[label] = embed_text(f"a photo of {label}", "Classification")
        return label_vectors[label]

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
                prompt = request.get("prompt") or None
                vectors = [embed_text(str(text), prompt) for text in request.get("texts") or []]
                print(json.dumps({"ok": True, "vectors": vectors}), flush=True)
            elif kind == "images":
                vectors = [embed_image(str(path)) for path in request.get("paths") or []]
                print(json.dumps({"ok": True, "vectors": vectors}), flush=True)
            elif kind == "tags":
                paths = [str(path) for path in request.get("paths") or []]
                labels = [str(label) for label in request.get("labels") or []]
                topk = max(1, min(20, int(request.get("topk") or 5)))
                if not paths or not labels:
                    raise ValueError("paths and labels are required")
                matrix = [label_vector(label) for label in labels]
                results = []
                for path in paths:
                    vector = embed_image(path)
                    scores = [sum(a * b for a, b in zip(vector, label)) for label in matrix]
                    order = sorted(range(len(scores)), key=lambda index: -scores[index])[:topk]
                    results.append({
                        "tags": [{"label": labels[index], "score": round(scores[index], 4)}
                                 for index in order],
                        "vector": vector,
                    })
                print(json.dumps({"ok": True, "results": results, "dim": len(matrix[0])}), flush=True)
            else:
                raise ValueError(f"Unknown request kind: {kind}")
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)[:500]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
