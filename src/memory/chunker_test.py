from __future__ import annotations

from src.memory.chunker import chunk_markdown


class TestChunkMarkdown:
    def test_empty_content(self) -> None:
        assert chunk_markdown("") == []
        assert chunk_markdown("   ") == []

    def test_single_chunk_short_content(self) -> None:
        content = "# Hello\n\nSome text here."
        chunks = chunk_markdown(content)
        assert len(chunks) == 1
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 3
        assert "Hello" in chunks[0].text
        assert "Some text here." in chunks[0].text

    def test_multiple_chunks_long_content(self) -> None:
        # Create content that exceeds one chunk (~8000 chars)
        lines = [f"Line {i}: " + "x" * 80 for i in range(120)]
        content = "\n".join(lines)
        chunks = chunk_markdown(content, chunk_tokens=500)  # ~2000 chars per chunk
        assert len(chunks) > 1

    def test_line_numbers_are_one_indexed(self) -> None:
        content = "first\nsecond\nthird"
        chunks = chunk_markdown(content)
        assert chunks[0].start_line == 1

    def test_chunks_have_unique_hashes(self) -> None:
        lines = [f"Line {i}: " + "x" * 80 for i in range(120)]
        content = "\n".join(lines)
        chunks = chunk_markdown(content, chunk_tokens=500)
        hashes = [c.hash for c in chunks]
        assert len(hashes) == len(set(hashes))

    def test_overlap_between_chunks(self) -> None:
        lines = [f"Line {i}: " + "x" * 80 for i in range(120)]
        content = "\n".join(lines)
        chunks = chunk_markdown(content, chunk_tokens=500, overlap_tokens=100)
        if len(chunks) >= 2:
            # The end of chunk N should overlap with the start of chunk N+1
            assert chunks[1].start_line <= chunks[0].end_line

    def test_no_overlap_when_zero(self) -> None:
        lines = [f"Line {i}: " + "x" * 80 for i in range(120)]
        content = "\n".join(lines)
        chunks = chunk_markdown(content, chunk_tokens=500, overlap_tokens=0)
        if len(chunks) >= 2:
            assert chunks[1].start_line > chunks[0].end_line

    def test_hash_is_sha256(self) -> None:
        content = "# Test\n\nSome content."
        chunks = chunk_markdown(content)
        assert len(chunks[0].hash) == 64  # SHA-256 hex digest length

    def test_all_content_covered(self) -> None:
        lines = ["line " + str(i) for i in range(50)]
        content = "\n".join(lines)
        chunks = chunk_markdown(content, chunk_tokens=200)
        # Last chunk should cover the last line
        assert chunks[-1].end_line == 50
        # First chunk should start at line 1
        assert chunks[0].start_line == 1
