"""Lightweight tests only — they don't load the real sentence-transformers
model or spin up ChromaDB (both are slow/heavy), just the logic around them."""

import pytest

from embeddings.embedder import Embedder
from vector_store.chroma_store import ChromaLogStore, _stable_id


def test_embedder_rejects_unknown_model():
    with pytest.raises(ValueError):
        Embedder(model="not-a-real-model")


def test_embed_empty_list_short_circuits_without_loading_model():
    embedder = Embedder(model="minilm")
    assert embedder.embed([]) == []
    assert embedder._model is None  # never triggered the lazy load


def test_stable_id_is_deterministic_and_distinguishes_pods():
    meta_a = {"namespace": "prod", "pod": "payment-1", "timestamp": "2026-01-01T00:00:00"}
    meta_b = {"namespace": "prod", "pod": "payment-2", "timestamp": "2026-01-01T00:00:00"}

    assert _stable_id("same text", meta_a) == _stable_id("same text", meta_a)
    assert _stable_id("same text", meta_a) != _stable_id("same text", meta_b)


def test_add_logs_rejects_mismatched_lengths():
    store = ChromaLogStore(persist_dir="/tmp/unused")
    with pytest.raises(ValueError):
        store.add_logs(["one", "two"], [{"namespace": "prod"}])


def test_add_logs_empty_is_a_noop_without_touching_chromadb():
    store = ChromaLogStore(persist_dir="/tmp/unused")
    assert store.add_logs([], []) == 0
    assert store._collection is None  # never triggered client/collection creation
