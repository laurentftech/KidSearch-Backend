"""
Tests for search results merger service
"""
import pytest
from kidsearch.api.services.merger import SearchMerger
from kidsearch.api.models import SearchResult, SearchSource


@pytest.mark.unit
class TestSearchMerger:
    """Test cases for SearchMerger"""

    def test_merger_initialization(self):
        """Test merger initialization with default weights"""
        merger = SearchMerger()
        assert merger.typesense_weight == 0.7
        assert merger.cse_weight == 0.3

    def test_merger_custom_weights(self):
        """Test merger initialization with custom weights"""
        merger = SearchMerger(typesense_weight=0.6, cse_weight=0.4)
        assert merger.typesense_weight == 0.6
        assert merger.cse_weight == 0.4

    def test_merge_empty_results(self):
        """Test merging with empty results"""
        merger = SearchMerger()
        merged = merger.merge(typesense_results=[], cse_results=[], limit=10)
        assert merged == []

    def test_merge_typesense_only(self):
        """Test merging with only Typesense results"""
        merger = SearchMerger()

        ts_results = [
            SearchResult(
                id="ts-1",
                title="Typesense Result",
                url="https://example.com/ts1",
                excerpt="Typesense result",
                source=SearchSource.TYPESENSE,
                score=0.9
            )
        ]

        merged = merger.merge(typesense_results=ts_results, cse_results=[], limit=10)

        assert len(merged) == 1
        assert merged[0].id == "ts-1"
        # Score should be weighted
        assert merged[0].score == pytest.approx(0.9 * 0.7)

    def test_merge_deduplication(self):
        """Test deduplication of results with same URL"""
        merger = SearchMerger()

        ts_results = [
            SearchResult(
                id="ts-1",
                title="Typesense Result",
                url="https://example.com/page",
                excerpt="From Typesense",
                source=SearchSource.TYPESENSE,
                score=0.9
            )
        ]

        cse_results = [
            SearchResult(
                id="cse-1",
                title="CSE Result",
                url="https://example.com/page",  # Same URL
                excerpt="From CSE",
                source=SearchSource.GOOGLE_CSE,
                score=0.8
            )
        ]

        merged = merger.merge(typesense_results=ts_results, cse_results=cse_results, limit=10)

        # Should only have one result (Typesense has priority)
        assert len(merged) == 1
        assert merged[0].id == "ts-1"
        assert merged[0].excerpt == "From Typesense"

    def test_merge_url_normalization(self):
        """Test URL normalization (www, trailing slash, etc.)"""
        merger = SearchMerger()

        ts_results = [
            SearchResult(
                id="ts-1",
                title="Typesense Result",
                url="https://www.example.com/page/",
                excerpt="From Typesense",
                source=SearchSource.TYPESENSE,
                score=0.9
            )
        ]

        cse_results = [
            SearchResult(
                id="cse-1",
                title="CSE Result",
                url="https://example.com/page",  # Same URL without www and trailing slash
                excerpt="From CSE",
                source=SearchSource.GOOGLE_CSE,
                score=0.8
            )
        ]

        merged = merger.merge(typesense_results=ts_results, cse_results=cse_results, limit=10)

        # Should be deduplicated
        assert len(merged) == 1
        assert merged[0].id == "ts-1"

    def test_merge_sorting_by_score(self):
        """Test that results are sorted by weighted score"""
        merger = SearchMerger()

        ts_results = [
            SearchResult(
                id="ts-1",
                title="TS Result 1",
                url="https://example.com/ts1",
                excerpt="Low score",
                source=SearchSource.TYPESENSE,
                score=0.5  # After weighting: 0.35
            ),
            SearchResult(
                id="ts-2",
                title="TS Result 2",
                url="https://example.com/ts2",
                excerpt="High score",
                source=SearchSource.TYPESENSE,
                score=0.9  # After weighting: 0.63
            )
        ]

        cse_results = [
            SearchResult(
                id="cse-1",
                title="CSE Result",
                url="https://example.com/cse1",
                excerpt="Medium score",
                source=SearchSource.GOOGLE_CSE,
                score=1.0  # After weighting: 0.30
            )
        ]

        merged = merger.merge(typesense_results=ts_results, cse_results=cse_results, limit=10)

        # Should be sorted: ts-2 (0.63), ts-1 (0.35), cse-1 (0.30)
        assert len(merged) == 3
        assert merged[0].id == "ts-2"
        assert merged[1].id == "ts-1"
        assert merged[2].id == "cse-1"

    def test_merge_limit_respected(self):
        """Test that merge respects the limit parameter"""
        merger = SearchMerger()

        ts_results = [
            SearchResult(
                id=f"ts-{i}",
                title=f"Result {i}",
                url=f"https://example.com/ts{i}",
                excerpt="Excerpt",
                source=SearchSource.TYPESENSE,
                score=0.9 - (i * 0.1)
            ) for i in range(10)
        ]

        merged = merger.merge(typesense_results=ts_results, cse_results=[], limit=5)

        assert len(merged) == 5

    def test_normalize_url_preserves_query_params(self):
        """Test that URL normalization preserves query parameters"""
        merger = SearchMerger()

        url1 = "https://example.com/page?id=123&sort=date"
        url2 = "https://www.example.com/page/?id=123&sort=date"

        normalized1 = merger._normalize_url(url1)
        normalized2 = merger._normalize_url(url2)

        # Should be equal after normalization
        assert normalized1 == normalized2
        # Should preserve query params
        assert "id=123" in normalized1
        assert "sort=date" in normalized1
