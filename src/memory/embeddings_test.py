from __future__ import annotations

import sqlite3
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.memory.embeddings import EmbeddingProvider
from src.memory.schema import ensure_schema


def _mock_embedding_provider(db: sqlite3.Connection | None = None) -> EmbeddingProvider:
    """Create an EmbeddingProvider with a mocked fastembed model."""
    provider = EmbeddingProvider(model_name="test-model", db=db)
    mock_model = MagicMock()
    # fastembed returns a generator of numpy arrays
    mock_model.embed.side_effect = lambda texts: [
        [0.1 * (i + 1)] * 384 for i, _ in enumerate(texts)
    ]
    provider._model = mock_model
    return provider


class TestEmbeddingProvider:
    def test_embed_returns_correct_dimension(self) -> None:
        provider = _mock_embedding_provider()
        result = provider.embed("hello world")
        assert len(result) == 384

    def test_embed_batch(self) -> None:
        provider = _mock_embedding_provider()
        results = provider.embed_batch(["hello", "world"])
        assert len(results) == 2
        assert len(results[0]) == 384
        assert len(results[1]) == 384

    def test_cache_stores_and_retrieves(self, tmp_path: Path) -> None:
        conn = ensure_schema(tmp_path / "test.db")
        provider = _mock_embedding_provider(db=conn)

        # First call should compute
        result1 = provider.embed("hello world")
        assert provider._model.embed.call_count == 1

        # Second call should hit cache
        result2 = provider.embed("hello world")
        # embed is not called again because cache returns it
        assert provider._model.embed.call_count == 1
        assert len(result1) == len(result2)
        # Allow for float32 precision loss from struct pack/unpack
        for a, b in zip(result1, result2):
            assert abs(a - b) < 1e-6
        conn.close()

    def test_cache_miss_for_different_text(self, tmp_path: Path) -> None:
        conn = ensure_schema(tmp_path / "test.db")
        provider = _mock_embedding_provider(db=conn)

        provider.embed("hello")
        provider.embed("world")
        assert provider._model.embed.call_count == 2
        conn.close()

    def test_batch_uses_cache(self, tmp_path: Path) -> None:
        conn = ensure_schema(tmp_path / "test.db")
        provider = _mock_embedding_provider(db=conn)

        # Pre-cache one item
        provider.embed("hello")
        assert provider._model.embed.call_count == 1

        # Batch with one cached and one new
        results = provider.embed_batch(["hello", "world"])
        assert len(results) == 2
        # Only "world" should have triggered a new embed call
        assert provider._model.embed.call_count == 2
        conn.close()

    def test_no_cache_without_db(self) -> None:
        provider = _mock_embedding_provider(db=None)
        result1 = provider.embed("hello")
        result2 = provider.embed("hello")
        # Without cache, embed is called twice
        assert provider._model.embed.call_count == 2
