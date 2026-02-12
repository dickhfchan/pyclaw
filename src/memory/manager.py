from __future__ import annotations

import hashlib
import sqlite3
import struct
import time
import uuid
from pathlib import Path
from typing import Any

from src.memory.chunker import chunk_markdown
from src.memory.embeddings import EmbeddingProvider
from src.memory.schema import ensure_schema
from src.memory.search import SearchResult, search_hybrid


class MemoryManager:
    """Orchestrates memory indexing, syncing, and searching.

    Scans Markdown files in the memory directory, chunks them,
    generates embeddings, and stores everything in SQLite for
    hybrid vector + keyword search.
    """

    def __init__(
        self,
        memory_dir: str | Path,
        db_path: str | Path,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        chunk_tokens: int = 2000,
        chunk_overlap: int = 200,
        search_top_k: int = 5,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
    ) -> None:
        self.memory_dir = Path(memory_dir)
        self.db_path = Path(db_path)
        self.chunk_tokens = chunk_tokens
        self.chunk_overlap = chunk_overlap
        self.search_top_k = search_top_k
        self.vector_weight = vector_weight
        self.text_weight = text_weight

        self._conn = ensure_schema(self.db_path)
        self._embedder = EmbeddingProvider(
            model_name=embedding_model,
            db=self._conn,
        )
        self._watcher: Any = None

    def sync(self) -> dict[str, int]:
        """Scan memory directory and sync changes to the database.

        Returns a dict with counts: added, updated, deleted, unchanged.
        """
        stats = {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0}

        # List all .md files in the memory directory
        disk_files = self._list_md_files()
        disk_paths = {str(p) for p in disk_files}

        # Get known files from DB
        db_rows = self._conn.execute("SELECT path, hash FROM files").fetchall()
        db_files = {row[0]: row[1] for row in db_rows}

        # Detect deleted files
        for db_path in db_files:
            if db_path not in disk_paths:
                self._remove_file(db_path)
                stats["deleted"] += 1

        # Detect new and changed files
        for file_path in disk_files:
            rel_path = str(file_path)
            content = file_path.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            if rel_path not in db_files:
                self._index_file(file_path, rel_path, content, content_hash)
                stats["added"] += 1
            elif db_files[rel_path] != content_hash:
                self._remove_file(rel_path)
                self._index_file(file_path, rel_path, content, content_hash)
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1

        self._conn.commit()
        return stats

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        """Search memory using hybrid vector + keyword search."""
        k = top_k or self.search_top_k
        query_embedding = self._embedder.embed(query)
        return search_hybrid(
            self._conn,
            query_text=query,
            query_embedding=query_embedding,
            top_k=k,
            vector_weight=self.vector_weight,
            text_weight=self.text_weight,
        )

    def get_context(self, query: str, top_k: int | None = None) -> str:
        """Search memory and return formatted context for the agent prompt."""
        results = self.search(query, top_k)
        if not results:
            return ""

        parts = ["## Relevant Memory\n"]
        for r in results:
            parts.append(f"**{r.path}** (lines {r.start_line}-{r.end_line}):")
            parts.append(r.snippet)
            parts.append("")

        return "\n".join(parts)

    def get_file_content(self, filename: str) -> str | None:
        """Read a specific memory file's content (e.g., SOUL.md)."""
        file_path = self.memory_dir / filename
        if file_path.exists():
            return file_path.read_text(encoding="utf-8")
        return None

    def close(self) -> None:
        """Close the database connection and stop any file watchers."""
        self.stop_watching()
        self._conn.close()

    def start_watching(self, debounce_seconds: float = 5.0) -> None:
        """Watch the memory directory for changes and auto-sync."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            return

        manager = self

        class _Handler(FileSystemEventHandler):
            def __init__(self) -> None:
                self._last_sync = 0.0
                self._debounce = debounce_seconds

            def on_any_event(self, event: Any) -> None:
                if not event.src_path.endswith(".md"):
                    return
                now = time.time()
                if now - self._last_sync < self._debounce:
                    return
                self._last_sync = now
                manager.sync()

        observer = Observer()
        observer.schedule(_Handler(), str(self.memory_dir), recursive=True)
        observer.daemon = True
        observer.start()
        self._watcher = observer

    def stop_watching(self) -> None:
        """Stop the file watcher if running."""
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    def _list_md_files(self) -> list[Path]:
        """List all .md files in the memory directory."""
        if not self.memory_dir.exists():
            return []
        files = list(self.memory_dir.rglob("*.md"))
        return sorted(files)

    def _index_file(
        self, abs_path: Path, rel_path: str, content: str, content_hash: str
    ) -> None:
        """Index a single file: chunk, embed, and store."""
        stat = abs_path.stat()
        self._conn.execute(
            "INSERT OR REPLACE INTO files (path, hash, mtime, size) VALUES (?, ?, ?, ?)",
            (rel_path, content_hash, stat.st_mtime, stat.st_size),
        )

        chunks = chunk_markdown(content, self.chunk_tokens, self.chunk_overlap)
        now = int(time.time())

        texts = [c.text for c in chunks]
        embeddings = self._embedder.embed_batch(texts) if texts else []

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = str(uuid.uuid4())
            emb_blob = struct.pack(f"{len(embedding)}f", *embedding)

            self._conn.execute(
                """INSERT INTO chunks (id, path, start_line, end_line, hash, model, text, embedding, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (chunk_id, rel_path, chunk.start_line, chunk.end_line,
                 chunk.hash, self._embedder.model_name, chunk.text, emb_blob, now),
            )

            # Insert into FTS index
            try:
                self._conn.execute(
                    "INSERT INTO chunks_fts (id, path, start_line, end_line, text) VALUES (?, ?, ?, ?, ?)",
                    (chunk_id, rel_path, chunk.start_line, chunk.end_line, chunk.text),
                )
            except sqlite3.OperationalError:
                pass

            # Insert into vector index
            try:
                self._conn.execute(
                    "INSERT INTO chunks_vec (id, embedding) VALUES (?, ?)",
                    (chunk_id, emb_blob),
                )
            except sqlite3.OperationalError:
                pass

    def _remove_file(self, rel_path: str) -> None:
        """Remove a file and its chunks from the database."""
        # Get chunk IDs before deleting
        chunk_ids = [
            row[0]
            for row in self._conn.execute(
                "SELECT id FROM chunks WHERE path = ?", (rel_path,)
            ).fetchall()
        ]

        # Delete from FTS
        for cid in chunk_ids:
            try:
                self._conn.execute(
                    "DELETE FROM chunks_fts WHERE id = ?", (cid,)
                )
            except sqlite3.OperationalError:
                pass

        # Delete from vector index
        for cid in chunk_ids:
            try:
                self._conn.execute(
                    "DELETE FROM chunks_vec WHERE id = ?", (cid,)
                )
            except sqlite3.OperationalError:
                pass

        self._conn.execute("DELETE FROM chunks WHERE path = ?", (rel_path,))
        self._conn.execute("DELETE FROM files WHERE path = ?", (rel_path,))


def log_session(
    daily_dir: str | Path,
    timestamp: str,
    query_summary: str,
    response_summary: str,
    decisions: list[str] | None = None,
) -> Path:
    """Append a session entry to the daily log file.

    Creates the daily directory and file if they don't exist.
    Returns the path to the daily log file.
    """
    daily_dir = Path(daily_dir)
    daily_dir.mkdir(parents=True, exist_ok=True)

    # Use the date from the timestamp or current date
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        dt = datetime.now()

    filename = dt.strftime("%Y-%m-%d") + ".md"
    file_path = daily_dir / filename

    entry_parts = [
        f"\n## {timestamp}\n",
        f"**Query:** {query_summary}\n",
        f"**Response:** {response_summary}\n",
    ]
    if decisions:
        entry_parts.append("**Decisions:**\n")
        for d in decisions:
            entry_parts.append(f"- {d}\n")

    entry_parts.append("---\n")

    with open(file_path, "a", encoding="utf-8") as f:
        f.writelines(entry_parts)

    return file_path
