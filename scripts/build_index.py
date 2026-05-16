"""
Pre-build the FAISS index from data/catalog.json.
Usage: python scripts/build_index.py
"""

import json
import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

CATALOG_PATH = Path("data/catalog.json")
INDEX_PATH   = Path("data/faiss.index")
META_PATH    = Path("data/faiss_meta.pkl")
MODEL_NAME   = "all-MiniLM-L6-v2"


def build_text(item: dict) -> str:
    """Match the same text construction used in retriever.py."""
    parts = [
        item.get("name", ""),
        item.get("description", "")[:300],
        " ".join(item.get("job_levels", [])),
        " ".join(item.get("keys", [])),
        " ".join(item.get("languages", [])),
        item.get("duration", ""),
    ]
    return " | ".join(p for p in parts if p.strip())


def main():
    assert CATALOG_PATH.exists(), f"{CATALOG_PATH} not found. Save catalog JSON there first."

    with open(CATALOG_PATH, encoding="utf-8") as f:
        catalog = json.load(f)

    # Normalize link field
    for item in catalog:
        if "link" not in item and "url" in item:
            item["link"] = item["url"]

    print(f"Loaded {len(catalog)} items from {CATALOG_PATH}")
    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    texts = [build_text(item) for item in catalog]
    print("Encoding embeddings...")
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=64,
    )
    embeddings = embeddings.astype("float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump(catalog, f)

    print(f"\nSaved index ({index.ntotal} vectors) → {INDEX_PATH}")
    print(f"Saved metadata ({len(catalog)} items) → {META_PATH}")

    # Sanity checks
    checks = [
        "senior leadership selection CXO",
        "mid-level Java developer stakeholder",
        "entry level cashier customer service",
        "data scientist machine learning Python",
    ]
    for query in checks:
        qvec = model.encode([query], normalize_embeddings=True).astype("float32")
        scores, idxs = index.search(qvec, 3)
        print(f"\nQuery: '{query}'")
        for score, idx in zip(scores[0], idxs[0]):
            item = catalog[idx]
            print(f"  [{score:.3f}] {item['name']} | keys: {item.get('keys', [])}")


if __name__ == "__main__":
    main()