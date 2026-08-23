"""ChromaDB-backed semantic log store. See README.md "Phase 5 — 2.
Semantic Search" — supports queries like "show database timeout errors"
or "similar incidents from last month" over embedded log chunks.
"""

from __future__ import annotations

import hashlib

from embeddings.embedder import Embedder, get_embedder

COLLECTION_NAME = "observability-logs"


class ChromaLogStore:
    def __init__(self, persist_dir: str = "./chroma_db", embedder: Embedder | None = None):
        self.persist_dir = persist_dir
        self.embedder = embedder or get_embedder("minilm")
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb

            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(COLLECTION_NAME)
        return self._collection

    def add_logs(self, texts: list[str], metadatas: list[dict]) -> int:
        """Embed and upsert a batch of log lines/chunks. `metadatas[i]`
        should match `texts[i]` — see ingestion.loader.LogRecord.metadata().
        Returns the number of records written.
        """
        if len(texts) != len(metadatas):
            raise ValueError("texts and metadatas must be the same length")
        if not texts:
            return 0

        collection = self._get_collection()
        embeddings = self.embedder.embed(texts)
        ids = [_stable_id(text, meta) for text, meta in zip(texts, metadatas)]

        collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        return len(texts)

    def semantic_search(self, query: str, n_results: int = 10, where: dict | None = None) -> list[dict]:
        """Find the `n_results` log lines/chunks most semantically similar
        to `query`, optionally filtered by metadata (e.g. {"namespace": "prod"})."""
        collection = self._get_collection()
        query_embedding = self.embedder.embed_one(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
        )

        hits = []
        for doc, meta, distance in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            hits.append({"text": doc, "metadata": meta, "distance": distance})
        return hits


def _stable_id(text: str, meta: dict) -> str:
    """Deterministic ID so re-ingesting the same log line is an upsert,
    not a duplicate."""
    key = f"{meta.get('namespace')}|{meta.get('pod')}|{meta.get('timestamp')}|{text}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
