"""Integration test for the memory pipeline.

Creates temp Markdown files -> syncs -> searches -> verifies results.
"""
from __future__ import annotations

from pathlib import Path

import pytest

try:
    import fastembed
    HAS_FASTEMBED = True
except ImportError:
    HAS_FASTEMBED = False

pytestmark = pytest.mark.skipif(not HAS_FASTEMBED, reason="fastembed not installed")

from src.memory.manager import MemoryManager


@pytest.fixture
def memory_env(tmp_path: Path):
    """Set up a temporary memory directory with sample files."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()

    (memory_dir / "SOUL.md").write_text(
        "# Soul\n\nI am a helpful, patient assistant who values clarity."
    )
    (memory_dir / "USER.md").write_text(
        "# User\n\nName: Alice\nPrefers: short answers, dark mode, Python over JavaScript."
    )
    (memory_dir / "MEMORY.md").write_text(
        "# Memory\n\n## 2025-01-15\nDecided to use PostgreSQL for the project database.\n\n"
        "## 2025-01-20\nAlice mentioned she dislikes verbose error messages."
    )

    db_path = tmp_path / "data" / "memory.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return memory_dir, db_path


def test_sync_indexes_all_files(memory_env):
    memory_dir, db_path = memory_env
    mm = MemoryManager(memory_dir=memory_dir, db_path=db_path)
    stats = mm.sync()

    assert stats["added"] == 3
    assert stats["updated"] == 0
    assert stats["deleted"] == 0
    mm.close()


def test_search_finds_relevant_content(memory_env):
    memory_dir, db_path = memory_env
    mm = MemoryManager(memory_dir=memory_dir, db_path=db_path)
    mm.sync()

    results = mm.search("PostgreSQL database")
    assert len(results) > 0
    texts = " ".join(r.snippet for r in results)
    assert "PostgreSQL" in texts
    mm.close()


def test_search_finds_user_preferences(memory_env):
    memory_dir, db_path = memory_env
    mm = MemoryManager(memory_dir=memory_dir, db_path=db_path)
    mm.sync()

    # Search for exact terms present in USER.md
    results = mm.search("Alice short answers dark mode")
    assert len(results) > 0
    texts = " ".join(r.snippet for r in results)
    assert "Alice" in texts
    mm.close()


def test_get_context_returns_formatted(memory_env):
    memory_dir, db_path = memory_env
    mm = MemoryManager(memory_dir=memory_dir, db_path=db_path)
    mm.sync()

    context = mm.get_context("PostgreSQL database project")
    assert "Relevant Memory" in context
    assert "PostgreSQL" in context
    mm.close()


def test_update_file_reindexes(memory_env):
    memory_dir, db_path = memory_env
    mm = MemoryManager(memory_dir=memory_dir, db_path=db_path)
    mm.sync()

    # Modify a file
    (memory_dir / "MEMORY.md").write_text(
        "# Memory\n\n## 2025-01-15\nSwitched from PostgreSQL to SQLite for simplicity.\n"
    )

    stats = mm.sync()
    assert stats["updated"] == 1

    results = mm.search("SQLite")
    texts = " ".join(r.snippet for r in results)
    assert "SQLite" in texts
    mm.close()


def test_delete_file_removes_from_index(memory_env):
    memory_dir, db_path = memory_env
    mm = MemoryManager(memory_dir=memory_dir, db_path=db_path)
    mm.sync()

    # Delete a file
    (memory_dir / "MEMORY.md").unlink()

    stats = mm.sync()
    assert stats["deleted"] == 1
    mm.close()
