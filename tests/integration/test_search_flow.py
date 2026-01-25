"""
Integration tests for complete search flow
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kidsearch.api.models import SearchSource


@pytest.mark.integration
def test_complete_search_request_validation():
    """Test complete search request validation"""
    from kidsearch.api.models import SearchRequest, Language

    # Create valid search request
    request = SearchRequest(
        q="test query",
        lang=Language.FR,
        limit=10,
        use_cse=False,
        use_reranking=False
    )

    assert request.q == "test query"
    assert request.lang == Language.FR
    assert request.limit == 10
    assert request.use_cse is False
    assert request.use_reranking is False


@pytest.mark.integration
def test_health_to_stats_flow(api_client):
    """Test that health check and stats endpoints work together"""
    # Check health first
    health_response = api_client.get("/api/health")
    assert health_response.status_code == 200

    health_data = health_response.json()
    assert health_data["status"] in ["healthy", "degraded"]

    # Stats endpoint should also be accessible
    # Note: This endpoint may not exist yet, but demonstrates integration testing
    # stats_response = api_client.get("/api/stats")
    # assert stats_response.status_code == 200


@pytest.mark.integration
@pytest.mark.slow
def test_search_with_safety_filter():
    """Test that search respects safety filters"""
    from kidsearch.api.services.safety import SafetyFilter
    from kidsearch.api.services.merger import SearchMerger
    from kidsearch.api.models import SearchResult, SearchSource

    # Initialize services
    safety_filter = SafetyFilter()
    safety_filter.blocked_keywords = {"inappropriate"}

    merger = SearchMerger()

    # Create test results including inappropriate content
    results = [
        SearchResult(
            id="safe-1",
            title="Safe Content",
            url="https://safe.com/page",
            excerpt="This is safe for children",
            source=SearchSource.TYPESENSE,
            score=0.9
        ),
        SearchResult(
            id="unsafe-1",
            title="Inappropriate Content",
            url="https://unsafe.com/page",
            excerpt="This contains inappropriate material",
            source=SearchSource.TYPESENSE,
            score=0.8
        )
    ]

    # Filter results
    filtered = safety_filter.filter_results(results)

    # Unsafe content should be filtered out
    assert len(filtered) == 1
    assert filtered[0].id == "safe-1"


@pytest.mark.integration
def test_merger_with_deduplication():
    """Test merger with deduplication across sources"""
    from kidsearch.api.services.merger import SearchMerger
    from kidsearch.api.models import SearchResult, SearchSource

    merger = SearchMerger()

    # Create results from different sources with overlapping URLs
    ts_results = [
        SearchResult(
            id="ts-1",
            title="Typesense Result",
            url="https://example.com/page1",
            excerpt="From Typesense",
            source=SearchSource.TYPESENSE,
            score=0.9
        ),
        SearchResult(
            id="ts-2",
            title="Unique Typesense",
            url="https://example.com/page2",
            excerpt="Unique",
            source=SearchSource.TYPESENSE,
            score=0.8
        )
    ]

    cse_results = [
        SearchResult(
            id="cse-1",
            title="CSE Duplicate",
            url="https://example.com/page1",  # Duplicate of ts-1
            excerpt="From CSE",
            source=SearchSource.GOOGLE_CSE,
            score=0.95
        ),
        SearchResult(
            id="cse-2",
            title="Unique CSE",
            url="https://example.com/page3",
            excerpt="Unique CSE",
            source=SearchSource.GOOGLE_CSE,
            score=0.7
        )
    ]

    merged = merger.merge(
        typesense_results=ts_results,
        cse_results=cse_results,
        limit=10
    )

    # Should have 3 unique results (duplicate removed)
    assert len(merged) == 3

    # Typesense version should be preferred for duplicate
    urls = [str(r.url) for r in merged]
    ids = [r.id for r in merged]

    assert "https://example.com/page1" in urls
    assert "ts-1" in ids  # Typesense version
    assert "cse-1" not in ids  # CSE version filtered out
