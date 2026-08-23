"""Embedding wrapper around sentence-transformers. Supports the three
models listed in the README ("Phase 5 — 2. Semantic Search").
"""

from __future__ import annotations

import functools

SUPPORTED_MODELS = {
    "bge-small": "BAAI/bge-small-en-v1.5",
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
    "e5-large": "intfloat/e5-large-v2",
}


class Embedder:
    def __init__(self, model: str = "minilm"):
        if model not in SUPPORTED_MODELS:
            raise ValueError(f"Unknown model '{model}'. Choose from: {list(SUPPORTED_MODELS)}")
        self.model_name = SUPPORTED_MODELS[model]
        self._model = None  # lazy-loaded — importing sentence_transformers is expensive

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns one vector per input text."""
        if not texts:
            return []
        model = self._load()
        return model.encode(texts, normalize_embeddings=True).tolist()

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


@functools.lru_cache(maxsize=len(SUPPORTED_MODELS))
def get_embedder(model: str = "minilm") -> Embedder:
    """Cached factory so repeated calls reuse one loaded model."""
    return Embedder(model)
