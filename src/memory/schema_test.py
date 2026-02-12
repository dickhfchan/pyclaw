from __future__ import annotations

from pathlib import Path

from src.memory.schema import ensure_schema


class TestEnsureSchema:
    def test_creates_database_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn = ensure_schema(db_path)
        assert db_path.exists()
        conn.close()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nested" / "dir" / "test.db"
        conn = ensure_schema(db_path)
        assert db_path.exists()
        conn.close()

    def test_creates_files_table(self, tmp_path: Path) -> None:
        conn = ensure_schema(tmp_path / "test.db")
        conn.execute(
            "INSERT INTO files (path, hash, mtime, size) VALUES (?, ?, ?, ?)",
            ("test.md", "abc123", 1000.0, 42),
        )
        row = conn.execute("SELECT * FROM files WHERE path = 'test.md'").fetchone()
        assert row["hash"] == "abc123"
        conn.close()

    def test_creates_chunks_table(self, tmp_path: Path) -> None:
        conn = ensure_schema(tmp_path / "test.db")
        conn.execute(
            """INSERT INTO chunks (id, path, start_line, end_line, hash, model, text, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("c1", "test.md", 1, 10, "hash1", "bge-small", "hello world", 1000),
        )
        row = conn.execute("SELECT * FROM chunks WHERE id = 'c1'").fetchone()
        assert row["text"] == "hello world"
        conn.close()

    def test_creates_embedding_cache_table(self, tmp_path: Path) -> None:
        conn = ensure_schema(tmp_path / "test.db")
        conn.execute(
            """INSERT INTO embedding_cache (hash, model, embedding, updated_at)
               VALUES (?, ?, ?, ?)""",
            ("h1", "bge-small", b"\x00" * 16, 1000),
        )
        row = conn.execute(
            "SELECT * FROM embedding_cache WHERE hash = 'h1'"
        ).fetchone()
        assert row["model"] == "bge-small"
        conn.close()

    def test_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        conn1 = ensure_schema(db_path)
        conn1.execute(
            "INSERT INTO files (path, hash, mtime, size) VALUES (?, ?, ?, ?)",
            ("test.md", "abc", 1.0, 1),
        )
        conn1.commit()
        conn1.close()

        # Second call should not error or lose data
        conn2 = ensure_schema(db_path)
        row = conn2.execute("SELECT * FROM files WHERE path = 'test.md'").fetchone()
        assert row is not None
        conn2.close()

    def test_wal_mode(self, tmp_path: Path) -> None:
        conn = ensure_schema(tmp_path / "test.db")
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_fts_table_created(self, tmp_path: Path) -> None:
        conn = ensure_schema(tmp_path / "test.db")
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
        ).fetchone()
        assert row is not None
        conn.close()
