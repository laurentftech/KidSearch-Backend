"""
Pytest configuration and fixtures for KidSearch tests
"""

import os
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Set test environment
os.environ["TESTING"] = "true"
os.environ["TYPESENSE_URL"] = "http://localhost:8108"
os.environ["TYPESENSE_API_KEY"] = "test_key"
os.environ["INDEX_NAME"] = "test_index"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_typesense_client():
    """Mock Typesense client for testing"""
    client = MagicMock()
    client.collections = MagicMock()
    client.operations = MagicMock()
    return client


@pytest.fixture
def async_mock_typesense_client():
    """Mock Typesense client for async testing"""
    from kidsearch.api.services.typesense_client import TypesenseClient

    client = AsyncMock(spec=TypesenseClient)
    client.connect = AsyncMock()
    client.search = AsyncMock(
        return_value={"hits": [], "found": 0, "search_time_ms": 10}
    )
    client.index_documents = AsyncMock()
    client.get_stats = AsyncMock(
        return_value={"num_documents": 0, "name": "test_index"}
    )
    return client


@pytest.fixture
def api_client():
    """FastAPI test client"""
    from kidsearch.api.server import app

    return TestClient(app)


@pytest.fixture
def sample_search_result():
    """Sample search result for testing"""
    from kidsearch.api.models import SearchResult, SearchSource

    return SearchResult(
        id="test-1",
        title="Test Document",
        url="https://example.com/test",
        excerpt="This is a test document",
        content="Full test content",
        site="Example",
        images=[],
        lang="fr",
        timestamp=1234567890,
        source=SearchSource.TYPESENSE,
        score=0.95,
    )


@pytest.fixture
def sample_search_results(sample_search_result):
    """Multiple sample search results"""
    from kidsearch.api.models import SearchResult, SearchSource

    results = [sample_search_result]

    for i in range(2, 6):
        results.append(
            SearchResult(
                id=f"test-{i}",
                title=f"Test Document {i}",
                url=f"https://example.com/test{i}",
                excerpt=f"This is test document {i}",
                site="Example",
                images=[],
                lang="fr",
                source=SearchSource.TYPESENSE,
                score=0.95 - (i * 0.1),
            )
        )

    return results


@pytest.fixture
def temp_db_path(tmp_path):
    """Temporary database path for testing"""
    return str(tmp_path / "test_stats.db")


@pytest.fixture
def mock_safety_filter():
    """Mock safety filter"""
    from kidsearch.api.services.safety import SafetyFilter

    filter_mock = MagicMock(spec=SafetyFilter)
    filter_mock.is_query_safe.return_value = True
    filter_mock.filter_results.return_value = []
    return filter_mock
