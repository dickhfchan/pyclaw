from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

from src.memory.manager import MemoryManager, log_session


def _make_manager(tmp_path: Path, **kwargs) -> MemoryManager:
    """Create a MemoryManager with a mock embedder to avoid fastembed dependency."""
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    db_path = tmp_path / "data" / "memory.db"

    manager = MemoryManager(
        memory_dir=mem_dir,
        db_path=db_path,
        **kwargs,
    )
    # Mock the embedder to avoid needing fastembed installed
    mock_embedder = MagicMock()
    mock_embedder.model_name = "test-model"
    mock_embedder.embed.return_value = [0.1] * 384
    mock_embedder.embed_batch.side_effect = lambda texts: [[0.1] * 384 for _ in texts]
    manager._embedder = mock_embedder
    return manager


class TestMemoryManagerSync:
    def test_sync_empty_directory(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        stats = manager.sync()
        assert stats["added"] == 0
        assert stats["unchanged"] == 0
        manager.close()

    def test_sync_adds_new_file(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        (tmp_path / "memory" / "test.md").write_text("# Test\n\nHello world.")
        stats = manager.sync()
        assert stats["added"] == 1
        # Verify chunks were created
        rows = manager._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        assert rows[0] > 0
        manager.close()

    def test_sync_detects_change(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        test_file = tmp_path / "memory" / "test.md"
        test_file.write_text("# V1\n\nOriginal.")
        manager.sync()

        test_file.write_text("# V2\n\nUpdated content.")
        stats = manager.sync()
        assert stats["updated"] == 1
        manager.close()

    def test_sync_detects_delete(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        test_file = tmp_path / "memory" / "test.md"
        test_file.write_text("# Test\n\nContent.")
        manager.sync()

        test_file.unlink()
        stats = manager.sync()
        assert stats["deleted"] == 1
        # Verify chunks were removed
        rows = manager._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        assert rows[0] == 0
        manager.close()

    def test_sync_unchanged_skips(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        (tmp_path / "memory" / "test.md").write_text("# Test\n\nContent.")
        manager.sync()

        stats = manager.sync()
        assert stats["unchanged"] == 1
        assert stats["added"] == 0
        manager.close()

    def test_sync_multiple_files(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        (tmp_path / "memory" / "a.md").write_text("# A\n\nFile A.")
        (tmp_path / "memory" / "b.md").write_text("# B\n\nFile B.")
        stats = manager.sync()
        assert stats["added"] == 2
        manager.close()

    def test_sync_subdirectory(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        daily_dir = tmp_path / "memory" / "daily"
        daily_dir.mkdir()
        (daily_dir / "2026-01-01.md").write_text("# Jan 1\n\nLog entry.")
        stats = manager.sync()
        assert stats["added"] == 1
        manager.close()


class TestMemoryManagerGetContext:
    def test_get_context_empty(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        context = manager.get_context("anything")
        assert context == ""
        manager.close()

    def test_get_file_content(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        (tmp_path / "memory" / "SOUL.md").write_text("# Soul\n\nI am helpful.")
        content = manager.get_file_content("SOUL.md")
        assert content is not None
        assert "helpful" in content
        manager.close()

    def test_get_file_content_missing(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        content = manager.get_file_content("NONEXISTENT.md")
        assert content is None
        manager.close()


class TestLogSession:
    def test_creates_daily_file(self, tmp_path: Path) -> None:
        daily_dir = tmp_path / "daily"
        path = log_session(
            daily_dir,
            timestamp="2026-02-12T10:00:00",
            query_summary="What's on my calendar?",
            response_summary="You have 3 meetings today.",
        )
        assert path.exists()
        content = path.read_text()
        assert "calendar" in content
        assert "3 meetings" in content

    def test_appends_to_existing(self, tmp_path: Path) -> None:
        daily_dir = tmp_path / "daily"
        log_session(daily_dir, "2026-02-12T10:00:00", "Q1", "A1")
        log_session(daily_dir, "2026-02-12T11:00:00", "Q2", "A2")
        path = daily_dir / "2026-02-12.md"
        content = path.read_text()
        assert "Q1" in content
        assert "Q2" in content

    def test_includes_decisions(self, tmp_path: Path) -> None:
        daily_dir = tmp_path / "daily"
        log_session(
            daily_dir,
            "2026-02-12T10:00:00",
            "Should I use React?",
            "Yes, for this project.",
            decisions=["Use React for frontend", "Keep backend in Python"],
        )
        content = (daily_dir / "2026-02-12.md").read_text()
        assert "Use React" in content
        assert "Python" in content
