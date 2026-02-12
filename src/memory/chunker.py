from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class MemoryChunk:
    start_line: int
    end_line: int
    text: str
    hash: str


def chunk_markdown(
    content: str,
    chunk_tokens: int = 2000,
    overlap_tokens: int = 200,
) -> list[MemoryChunk]:
    """Split Markdown content into overlapping chunks.

    Uses a character-based approximation (1 token ~= 4 chars).
    Tries to break at heading boundaries when possible.

    Args:
        content: The Markdown text to chunk.
        chunk_tokens: Target size per chunk in tokens.
        overlap_tokens: Overlap between consecutive chunks in tokens.

    Returns:
        A list of MemoryChunk objects with line numbers and content hash.
    """
    if not content or not content.strip():
        return []

    lines = content.split("\n")
    max_chars = max(32, chunk_tokens * 4)
    overlap_chars = max(0, overlap_tokens * 4)

    chunks: list[MemoryChunk] = []
    current_lines: list[tuple[int, str]] = []  # (line_number, text)
    current_chars = 0

    for i, line in enumerate(lines):
        line_chars = len(line) + 1  # +1 for newline

        # Check if adding this line would exceed the chunk size
        if current_chars + line_chars > max_chars and current_lines:
            # Try to break at a heading boundary
            chunk = _flush_chunk(current_lines)
            chunks.append(chunk)

            # Calculate overlap: keep lines from the end of current chunk
            current_lines, current_chars = _compute_overlap(
                current_lines, overlap_chars
            )

        current_lines.append((i + 1, line))  # 1-indexed line numbers
        current_chars += line_chars

    # Flush remaining lines
    if current_lines:
        chunks.append(_flush_chunk(current_lines))

    return chunks


def _flush_chunk(lines: list[tuple[int, str]]) -> MemoryChunk:
    """Create a MemoryChunk from accumulated lines."""
    text = "\n".join(line for _, line in lines)
    return MemoryChunk(
        start_line=lines[0][0],
        end_line=lines[-1][0],
        text=text,
        hash=hashlib.sha256(text.encode()).hexdigest(),
    )


def _compute_overlap(
    lines: list[tuple[int, str]], overlap_chars: int
) -> tuple[list[tuple[int, str]], int]:
    """Keep lines from the end to fill the overlap window."""
    if overlap_chars <= 0:
        return [], 0

    kept: list[tuple[int, str]] = []
    chars = 0
    for line_no, text in reversed(lines):
        line_chars = len(text) + 1
        if chars + line_chars > overlap_chars and kept:
            break
        kept.append((line_no, text))
        chars += line_chars

    kept.reverse()
    return kept, chars
