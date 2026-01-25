"""
Tests for Typesense client service
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kidsearch.api.services.typesense_client import TypesenseClient


@pytest.mark.unit
@pytest.mark.asyncio
class TestTypesenseClient:
    """Test cases for TypesenseClient"""

    async def test_client_initialization(self):
        """Test Typesense client initialization"""
        client = TypesenseClient(
            url="http://localhost:8108",
            api_key="test_key",
            collection_name="test_collection"
        )

        assert client.url == "http://localhost:8108"
        assert client.api_key == "test_key"
        assert client.collection_name == "test_collection"
        assert client.client is None  # Not connected yet

    @patch("kidsearch.api.services.typesense_client.typesense.Client")
    async def test_connect(self, mock_client_class):
        """Test connecting to Typesense"""
        mock_client = MagicMock()
        mock_client.collections.retrieve = MagicMock()
        mock_client_class.return_value = mock_client

        client = TypesenseClient(
            url="http://localhost:8108",
            api_key="test_key",
            collection_name="test_collection"
        )

        await client.connect()

        assert client.client is not None
        mock_client_class.assert_called_once()

    @patch("kidsearch.api.services.typesense_client.typesense.Client")
    async def test_index_documents(self, mock_client_class):
        """Test indexing documents"""
        mock_collection = MagicMock()
        mock_collection.documents.import_ = MagicMock()

        mock_client = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_client_class.return_value = mock_client

        client = TypesenseClient(
            url="http://localhost:8108",
            api_key="test_key",
            collection_name="test_collection"
        )
        client.client = mock_client

        documents = [
            {"id": "1", "title": "Test Doc 1", "content": "Content 1"},
            {"id": "2", "title": "Test Doc 2", "content": "Content 2"}
        ]

        await client.index_documents(documents)

        mock_collection.documents.import_.assert_called_once_with(
            documents,
            {'action': 'upsert'}
        )

    @patch("kidsearch.api.services.typesense_client.typesense.Client")
    async def test_search(self, mock_client_class):
        """Test searching documents"""
        mock_collection = MagicMock()
        mock_collection.documents.search = MagicMock(return_value={
            "hits": [
                {
                    "document": {
                        "id": "1",
                        "title": "Test Result",
                        "url": "https://example.com",
                        "excerpt": "Test excerpt"
                    },
                    "text_match": 100
                }
            ],
            "found": 1,
            "search_time_ms": 5
        })

        mock_client = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_client_class.return_value = mock_client

        client = TypesenseClient(
            url="http://localhost:8108",
            api_key="test_key",
            collection_name="test_collection"
        )
        client.client = mock_client

        results = await client.search(query="test query", limit=10)

        assert "hits" in results
        assert results["found"] == 1
        mock_collection.documents.search.assert_called_once()

    @patch("kidsearch.api.services.typesense_client.typesense.Client")
    async def test_get_stats(self, mock_client_class):
        """Test getting collection statistics"""
        mock_collection = MagicMock()
        mock_retrieve = MagicMock(return_value={
            "name": "test_collection",
            "num_documents": 100
        })

        mock_client = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_client.collections.__getitem__.return_value.retrieve = mock_retrieve
        mock_client_class.return_value = mock_client

        client = TypesenseClient(
            url="http://localhost:8108",
            api_key="test_key",
            collection_name="test_collection"
        )
        client.client = mock_client

        stats = await client.get_stats()

        assert stats["num_documents"] == 100
        assert stats["name"] == "test_collection"

    @patch("kidsearch.api.services.typesense_client.typesense.Client")
    async def test_delete_document(self, mock_client_class):
        """Test deleting a document"""
        mock_document = MagicMock()
        mock_document.delete = MagicMock()

        mock_collection = MagicMock()
        mock_collection.documents.__getitem__.return_value = mock_document

        mock_client = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_client_class.return_value = mock_client

        client = TypesenseClient(
            url="http://localhost:8108",
            api_key="test_key",
            collection_name="test_collection"
        )
        client.client = mock_client

        await client.delete_document("doc-123")

        mock_collection.documents.__getitem__.assert_called_with("doc-123")

    @patch("kidsearch.api.services.typesense_client.typesense.Client")
    async def test_search_with_vector(self, mock_client_class):
        """Test vector search functionality"""
        mock_collection = MagicMock()
        mock_collection.documents.search = MagicMock(return_value={
            "hits": [],
            "found": 0
        })

        mock_client = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_client_class.return_value = mock_client

        client = TypesenseClient(
            url="http://localhost:8108",
            api_key="test_key",
            collection_name="test_collection"
        )
        client.client = mock_client
        client.use_vector_search = True

        query_vector = [0.1, 0.2, 0.3, 0.4]
        await client.search(
            query="test",
            use_vector=True,
            query_vector=query_vector,
            limit=10
        )

        # Verify vector_query parameter was added
        call_args = mock_collection.documents.search.call_args[0][0]
        assert "vector_query" in call_args
