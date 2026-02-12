from __future__ import annotations

from src.memory.search import SearchResult, merge_hybrid_results, _build_fts_query, _bm25_rank_to_score


class TestBuildFtsQuery:
    def test_simple_query(self) -> None:
        result = _build_fts_query("hello world")
        assert result == '"hello" AND "world"'

    def test_empty_query(self) -> None:
        assert _build_fts_query("") is None
        assert _build_fts_query("   ") is None

    def test_special_chars_stripped(self) -> None:
        result = _build_fts_query("hello! world? foo-bar")
        assert result == '"hello" AND "world" AND "foo" AND "bar"'

    def test_single_token(self) -> None:
        result = _build_fts_query("python")
        assert result == '"python"'


class TestBm25RankToScore:
    def test_negative_rank(self) -> None:
        score = _bm25_rank_to_score(-5.0)
        assert 0 < score < 1

    def test_zero_rank(self) -> None:
        score = _bm25_rank_to_score(0.0)
        assert score >= 0

    def test_more_negative_is_higher_score(self) -> None:
        score_a = _bm25_rank_to_score(-10.0)
        score_b = _bm25_rank_to_score(-1.0)
        assert score_a > score_b


class TestMergeHybridResults:
    def _make_result(self, id: str, score: float) -> SearchResult:
        return SearchResult(
            id=id, path="test.md", start_line=1, end_line=10,
            snippet="text", score=score,
        )

    def test_merge_disjoint(self) -> None:
        vec = [self._make_result("a", 0.9)]
        kw = [self._make_result("b", 0.8)]
        merged = merge_hybrid_results(vec, kw, vector_weight=0.7, text_weight=0.3, top_k=10)
        assert len(merged) == 2
        ids = {r.id for r in merged}
        assert ids == {"a", "b"}

    def test_merge_overlapping(self) -> None:
        vec = [self._make_result("a", 0.9)]
        kw = [self._make_result("a", 0.8)]
        merged = merge_hybrid_results(vec, kw, vector_weight=0.7, text_weight=0.3, top_k=10)
        assert len(merged) == 1
        # Score should be weighted combination
        expected = 0.7 * 0.9 + 0.3 * 0.8
        assert abs(merged[0].score - expected) < 0.001

    def test_top_k_limits_results(self) -> None:
        vec = [self._make_result(f"v{i}", 0.5) for i in range(10)]
        kw = [self._make_result(f"k{i}", 0.5) for i in range(10)]
        merged = merge_hybrid_results(vec, kw, top_k=5)
        assert len(merged) == 5

    def test_sorted_by_score_descending(self) -> None:
        vec = [self._make_result("low", 0.1), self._make_result("high", 0.9)]
        merged = merge_hybrid_results(vec, [], vector_weight=1.0, text_weight=0.0, top_k=10)
        assert merged[0].id == "high"
        assert merged[1].id == "low"

    def test_empty_inputs(self) -> None:
        merged = merge_hybrid_results([], [], top_k=5)
        assert merged == []
