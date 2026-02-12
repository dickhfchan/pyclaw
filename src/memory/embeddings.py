from __future__ import annotations

import hashlib
import sqlite3
import time
from typing import Any


class EmbeddingProvider:
    """Wraps fastembed for local embedding generation with caching."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        db: sqlite3.Connection | None = None,
    ) -> None:
        self.model_name = model_name
        self._db = db
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding  # type: ignore[import-untyped]

            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text."""
        cached = self._cache_get(text)
        if cached is not None:
            return cached

        model = self._get_model()
        embeddings = list(model.embed([text]))
        result = list(embeddings[0])

        self._cache_put(text, result)
        return result

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        results: list[list[float] | None] = [None] * len(texts)
        to_compute: list[tuple[int, str]] = []

        # Check cache first
        for i, text in enumerate(texts):
            cached = self._cache_get(text)
            if cached is not None:
                results[i] = cached
            else:
                to_compute.append((i, text))

        if to_compute:
            model = self._get_model()
            compute_texts = [t for _, t in to_compute]
            embeddings = list(model.embed(compute_texts))
            for (idx, text), emb in zip(to_compute, embeddings):
                vec = list(emb)
                results[idx] = vec
                self._cache_put(text, vec)

        return [r for r in results if r is not None]

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def _cache_get(self, text: str) -> list[float] | None:
        if self._db is None:
            return None
        h = self._hash(text)
        row = self._db.execute(
            "SELECT embedding FROM embedding_cache WHERE hash = ? AND model = ?",
            (h, self.model_name),
        ).fetchone()
        if row is None:
            return None
        import struct

        blob = row[0] if isinstance(row, tuple) else row["embedding"]
        n = len(blob) // 4
        return list(struct.unpack(f"{n}f", blob))

    def _cache_put(self, text: str, embedding: list[float]) -> None:
        if self._db is None:
            return
        import struct

        h = self._hash(text)
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        self._db.execute(
            """INSERT OR REPLACE INTO embedding_cache (hash, model, embedding, updated_at)
               VALUES (?, ?, ?, ?)""",
            (h, self.model_name, blob, int(time.time())),
        )
        self._db.commit()
