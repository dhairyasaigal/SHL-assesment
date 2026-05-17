import json
import os
import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

CATALOG_PATH = Path("data/catalog.json")
INDEX_PATH = Path("data/faiss.index")
META_PATH = Path("data/faiss_meta.pkl")

_model: SentenceTransformer | None = None
_index: faiss.Index | None = None
_catalog: list[dict] = []


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _build_text(item: dict) -> str:
    """
    Build a rich searchable string from catalog item fields.
    Uses 'link' (not 'url') and 'keys' (not 'test_type') per actual JSON schema.
    """
    parts = [
        item.get("name", ""),
        item.get("description", "")[:300],
        " ".join(item.get("job_levels", [])),
        " ".join(item.get("keys", [])),
        " ".join(item.get("languages", [])),
        item.get("duration", ""),
    ]
    return " | ".join(p for p in parts if p.strip())


def load_index():
    """Load FAISS index and catalog into memory. Called once at startup."""
    global _index, _catalog

    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"catalog.json not found at {CATALOG_PATH}. "
            "Save your catalog JSON there before starting."
        )

    with open(CATALOG_PATH, encoding="utf-8") as f:
        raw_catalog = json.load(f)

    # Normalize: ensure 'link' field exists (catalog uses 'link', not 'url')
    for item in raw_catalog:
        if "link" not in item and "url" in item:
            item["link"] = item["url"]

    if INDEX_PATH.exists() and META_PATH.exists():
        _index = faiss.read_index(str(INDEX_PATH))
        with open(META_PATH, "rb") as f:
            _catalog = pickle.load(f)
        print(f"Loaded FAISS index with {_index.ntotal} vectors and {len(_catalog)} catalog items.")
    else:
        print("No pre-built index found. Building now...")
        _build_and_save_index(raw_catalog)


def _build_and_save_index(catalog: list[dict]):
    global _index, _catalog
    model = _get_model()

    texts = [_build_text(item) for item in catalog]
    print(f"Encoding {len(texts)} catalog items...")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    embeddings = embeddings.astype("float32")

    dim = embeddings.shape[1]
    _index = faiss.IndexFlatIP(dim)
    _index.add(embeddings)
    _catalog = catalog

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(_index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump(catalog, f)

    print(f"Built and saved index with {_index.ntotal} vectors.")


def retrieve(query: str, k: int = 7) -> list[dict]:
    """Return top-k catalog items for a given query string."""
    global _index, _catalog

    if _index is None or not _catalog:
        load_index()

    model = _get_model()
    qvec = model.encode([query], normalize_embeddings=True).astype("float32")
    k = min(k, len(_catalog))
    scores, idxs = _index.search(qvec, k)

    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if 0 <= idx < len(_catalog):
            item = dict(_catalog[idx])
            item["_score"] = float(score)
            results.append(item)
    return results


def get_all_catalog_links() -> set[str]:
    """Return all valid catalog links for URL validation."""
    global _catalog
    if not _catalog:
        load_index()
    return {item["link"] for item in _catalog if "link" in item}