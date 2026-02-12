from __future__ import annotations

import sqlite3
from pathlib import Path


def ensure_schema(db_path: str | Path) -> sqlite3.Connection:
    """Create/open the memory SQLite database and ensure all tables exist.

    Creates: files, chunks, chunks_fts (FTS5), embedding_cache tables.
    Loads sqlite-vec extension and creates the vector virtual table.
    Enables WAL mode for concurrent reads.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            hash TEXT NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            hash TEXT NOT NULL,
            model TEXT NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB,
            updated_at INTEGER NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS embedding_cache (
            hash TEXT NOT NULL,
            model TEXT NOT NULL,
            embedding BLOB NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (hash, model)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_embedding_cache_updated_at ON embedding_cache(updated_at)"
    )

    # FTS5 for keyword search
    _ensure_fts(conn)

    # sqlite-vec for vector search
    _ensure_vec(conn)

    conn.commit()
    return conn


def _ensure_fts(conn: sqlite3.Connection) -> None:
    """Create FTS5 virtual table if not present."""
    # Check if the table already exists
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
    ).fetchone()
    if row:
        return
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                text,
                id UNINDEXED,
                path UNINDEXED,
                start_line UNINDEXED,
                end_line UNINDEXED
            )
        """)
    except sqlite3.OperationalError:
        # FTS5 may not be available in all SQLite builds
        pass


def _ensure_vec(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension and create vector table if available."""
    try:
        import sqlite_vec  # type: ignore[import-untyped]

        sqlite_vec.load(conn)
        # Check if vec table already exists
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
        ).fetchone()
        if not row:
            conn.execute(
                "CREATE VIRTUAL TABLE chunks_vec USING vec0(id TEXT PRIMARY KEY, embedding float[384])"
            )
    except (ImportError, sqlite3.OperationalError):
        # sqlite-vec not installed or not available
        pass
