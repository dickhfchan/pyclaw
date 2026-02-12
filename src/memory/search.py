from __future__ import annotations

import sqlite3
import struct
from dataclasses import dataclass


@dataclass
class SearchResult:
    id: str
    path: str
    start_line: int
    end_line: int
    snippet: str
    score: float


def search_vector(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[SearchResult]:
    """Search chunks by vector cosine similarity using sqlite-vec."""
    try:
        blob = struct.pack(f"{len(query_embedding)}f", *query_embedding)
        rows = conn.execute(
            """
            SELECT v.id, v.distance, c.path, c.start_line, c.end_line, c.text
            FROM chunks_vec v
            JOIN chunks c ON v.id = c.id
            WHERE v.embedding MATCH ?
            ORDER BY v.distance
            LIMIT ?
            """,
            (blob, top_k),
        ).fetchall()

        results = []
        for row in rows:
            # sqlite-vec returns distance (lower = more similar)
            # Convert to a 0-1 score where higher = better
            distance = float(row[1])
            score = 1.0 / (1.0 + distance)
            results.append(SearchResult(
                id=row[0],
                path=row[2],
                start_line=row[3],
                end_line=row[4],
                snippet=row[5][:700] if row[5] else "",
                score=score,
            ))
        return results
    except sqlite3.OperationalError:
        # sqlite-vec not available
        return []


def search_keyword(
    conn: sqlite3.Connection,
    query_text: str,
    top_k: int = 5,
) -> list[SearchResult]:
    """Search chunks by BM25 keyword matching using FTS5."""
    fts_query = _build_fts_query(query_text)
    if not fts_query:
        return []

    try:
        rows = conn.execute(
            """
            SELECT f.id, f.path, f.start_line, f.end_line, f.text, rank
            FROM chunks_fts f
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, top_k),
        ).fetchall()

        results = []
        for row in rows:
            # FTS5 rank is negative (more negative = better match)
            rank = float(row[5])
            score = _bm25_rank_to_score(rank)
            results.append(SearchResult(
                id=row[0],
                path=row[1],
                start_line=row[2],
                end_line=row[3],
                snippet=row[4][:700] if row[4] else "",
                score=score,
            ))
        return results
    except sqlite3.OperationalError:
        # FTS5 not available
        return []


def search_hybrid(
    conn: sqlite3.Connection,
    query_text: str,
    query_embedding: list[float],
    top_k: int = 5,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
) -> list[SearchResult]:
    """Hybrid search combining vector similarity and BM25 keyword matching.

    Results are merged using weighted scoring and deduplicated by chunk ID.
    """
    vector_results = search_vector(conn, query_embedding, top_k=top_k * 2)
    keyword_results = search_keyword(conn, query_text, top_k=top_k * 2)

    return merge_hybrid_results(
        vector_results=vector_results,
        keyword_results=keyword_results,
        vector_weight=vector_weight,
        text_weight=text_weight,
        top_k=top_k,
    )


def merge_hybrid_results(
    vector_results: list[SearchResult],
    keyword_results: list[SearchResult],
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    top_k: int = 5,
) -> list[SearchResult]:
    """Merge vector and keyword results with weighted scoring."""
    by_id: dict[str, dict] = {}

    for r in vector_results:
        by_id[r.id] = {
            "id": r.id,
            "path": r.path,
            "start_line": r.start_line,
            "end_line": r.end_line,
            "snippet": r.snippet,
            "vector_score": r.score,
            "text_score": 0.0,
        }

    for r in keyword_results:
        if r.id in by_id:
            by_id[r.id]["text_score"] = r.score
            if r.snippet:
                by_id[r.id]["snippet"] = r.snippet
        else:
            by_id[r.id] = {
                "id": r.id,
                "path": r.path,
                "start_line": r.start_line,
                "end_line": r.end_line,
                "snippet": r.snippet,
                "vector_score": 0.0,
                "text_score": r.score,
            }

    merged = []
    for entry in by_id.values():
        score = vector_weight * entry["vector_score"] + text_weight * entry["text_score"]
        merged.append(SearchResult(
            id=entry["id"],
            path=entry["path"],
            start_line=entry["start_line"],
            end_line=entry["end_line"],
            snippet=entry["snippet"],
            score=score,
        ))

    merged.sort(key=lambda r: r.score, reverse=True)
    return merged[:top_k]


def _build_fts_query(raw: str) -> str | None:
    """Convert a natural language query to an FTS5 query string."""
    import re

    tokens = re.findall(r"[A-Za-z0-9_]+", raw)
    if not tokens:
        return None
    quoted = [f'"{t}"' for t in tokens]
    return " AND ".join(quoted)


def _bm25_rank_to_score(rank: float) -> float:
    """Convert FTS5 rank (negative, lower = better) to a 0-1 score."""
    normalized = max(0.0, -rank) if rank < 0 else 0.0
    return 1.0 / (1.0 + 1.0 / (normalized + 0.001))
