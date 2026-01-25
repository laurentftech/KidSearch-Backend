"""
Tests for Pydantic models
"""
import pytest
from pydantic import ValidationError
from kidsearch.api.models import (
    SearchRequest,
    SearchResult,
    SearchSource,
    SearchStats,
    SearchResponse,
    Language
)


@pytest.mark.unit
class TestSearchRequest:
    """Test SearchRequest model"""

    def test_valid_search_request(self):
        """Test creating a valid search request"""
        request = SearchRequest(
            q="dinosaures",
            lang=Language.FR,
            limit=20,
            use_cse=True,
            use_reranking=True
        )

        assert request.q == "dinosaures"
        assert request.lang == Language.FR
        assert request.limit == 20
        assert request.use_cse is True
        assert request.use_reranking is True

    def test_search_request_defaults(self):
        """Test default values in search request"""
        request = SearchRequest(q="test")

        assert request.lang == Language.FR
        assert request.limit == 20
        assert request.use_cse is True
        assert request.use_reranking is True

    def test_search_request_empty_query_fails(self):
        """Test that empty query raises validation error"""
        with pytest.raises(ValidationError):
            SearchRequest(q="")

    def test_search_request_limit_validation(self):
        """Test limit must be within bounds"""
        # Too low
        with pytest.raises(ValidationError):
            SearchRequest(q="test", limit=0)

        # Too high
        with pytest.raises(ValidationError):
            SearchRequest(q="test", limit=101)

        # Valid limits
        SearchRequest(q="test", limit=1)
        SearchRequest(q="test", limit=100)


@pytest.mark.unit
class TestSearchResult:
    """Test SearchResult model"""

    def test_valid_search_result(self):
        """Test creating a valid search result"""
        result = SearchResult(
            id="test-1",
            title="Test Title",
            url="https://example.com/test",
            excerpt="Test excerpt",
            source=SearchSource.TYPESENSE,
            score=0.95
        )

        assert result.id == "test-1"
        assert result.title == "Test Title"
        assert str(result.url) == "https://example.com/test"
        assert result.source == SearchSource.TYPESENSE
        assert result.score == 0.95

    def test_search_result_with_optional_fields(self):
        """Test search result with optional fields"""
        result = SearchResult(
            id="test-1",
            title="Test",
            url="https://example.com",
            excerpt="Excerpt",
            content="Full content here",
            site="Example Site",
            lang="fr",
            source=SearchSource.TYPESENSE,
            score=0.9
        )

        assert result.content == "Full content here"
        assert result.site == "Example Site"
        assert result.lang == "fr"

    def test_search_result_score_validation(self):
        """Test score must be between 0 and 1"""
        # Valid scores
        SearchResult(
            id="test",
            title="Test",
            url="https://example.com",
            excerpt="Test",
            source=SearchSource.TYPESENSE,
            score=0.0
        )

        SearchResult(
            id="test",
            title="Test",
            url="https://example.com",
            excerpt="Test",
            source=SearchSource.TYPESENSE,
            score=1.0
        )

        # Invalid scores
        with pytest.raises(ValidationError):
            SearchResult(
                id="test",
                title="Test",
                url="https://example.com",
                excerpt="Test",
                source=SearchSource.TYPESENSE,
                score=-0.1
            )

        with pytest.raises(ValidationError):
            SearchResult(
                id="test",
                title="Test",
                url="https://example.com",
                excerpt="Test",
                source=SearchSource.TYPESENSE,
                score=1.1
            )


@pytest.mark.unit
class TestSearchStats:
    """Test SearchStats model"""

    def test_valid_search_stats(self):
        """Test creating valid search stats"""
        stats = SearchStats(
            total_results=20,
            typesense_results=15,
            cse_results=5,
            processing_time_ms=250.5,
            typesense_time_ms=100.0,
            cse_time_ms=120.0,
            reranking_applied=True,
            cache_hit=False
        )

        assert stats.total_results == 20
        assert stats.typesense_results == 15
        assert stats.cse_results == 5
        assert stats.processing_time_ms == 250.5
        assert stats.reranking_applied is True

    def test_search_stats_defaults(self):
        """Test default values in search stats"""
        stats = SearchStats(
            total_results=10,
            processing_time_ms=100.0
        )

        assert stats.typesense_results == 0
        assert stats.cse_results == 0
        assert stats.reranking_applied is False
        assert stats.cache_hit is False


@pytest.mark.unit
class TestSearchResponse:
    """Test SearchResponse model"""

    def test_valid_search_response(self, sample_search_result):
        """Test creating a valid search response"""
        stats = SearchStats(
            total_results=1,
            typesense_results=1,
            processing_time_ms=100.0
        )

        response = SearchResponse(
            query="test query",
            results=[sample_search_result],
            stats=stats
        )

        assert response.query == "test query"
        assert len(response.results) == 1
        assert response.stats.total_results == 1
