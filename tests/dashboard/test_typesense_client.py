"""
Tests for dashboard Typesense client helper functions.
"""
import pytest
from unittest.mock import MagicMock, patch
from dashboard.src.typesense_client import (
    get_typesense_client,
    check_collection_exists,
    get_collection_stats,
    get_collection,
    search_collection,
    get_documents,
    get_collection_schema
)


class TestGetTypesenseClient:
    """Tests for get_typesense_client function."""

    @patch('dashboard.src.typesense_client.TYPESENSE_URL', 'http://localhost:8108')
    @patch('dashboard.src.typesense_client.TYPESENSE_API_KEY', 'test_key')
    @patch('dashboard.src.typesense_client.typesense.Client')
    @patch('dashboard.src.typesense_client.st.cache_resource', lambda func: func)
    def test_get_typesense_client_success(self, mock_client_class):
        """Test successful client connection."""
        mock_client = MagicMock()
        # Mock the collections.retrieve() call instead of operations.perform()
        mock_client.collections.retrieve.return_value = []
        mock_client_class.return_value = mock_client

        client = get_typesense_client()

        assert client is not None
        mock_client_class.assert_called_once()
        # Verify that collections.retrieve() was called to test the connection
        mock_client.collections.retrieve.assert_called_once()


class TestCheckCollectionExists:
    """Tests for check_collection_exists function."""

    def test_collection_exists(self):
        """Test when collection exists."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.retrieve.return_value = {'name': 'test_collection'}

        result = check_collection_exists(mock_client, 'test_collection')

        assert result is True
        mock_client.collections.__getitem__.assert_called_once_with('test_collection')
        mock_collection.retrieve.assert_called_once()

    def test_collection_not_exists(self):
        """Test when collection does not exist."""
        from typesense.exceptions import TypesenseClientError

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.retrieve.side_effect = TypesenseClientError("Not found")

        result = check_collection_exists(mock_client, 'test_collection')

        assert result is False

    def test_collection_check_general_exception(self):
        """Test when collection check raises general exception."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.retrieve.side_effect = Exception("General error")

        result = check_collection_exists(mock_client, 'test_collection')

        assert result is False


class TestGetCollectionStats:
    """Tests for get_collection_stats function."""

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_collection_stats_success(self, mock_error):
        """Test successful stats retrieval."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.retrieve.return_value = {
            'name': 'test_collection',
            'num_documents': 100
        }

        stats = get_collection_stats(mock_client, 'test_collection')

        assert stats is not None
        assert stats['name'] == 'test_collection'
        assert stats['number_of_documents'] == 100
        mock_error.assert_not_called()

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_collection_stats_error(self, mock_error):
        """Test stats retrieval error."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.retrieve.side_effect = Exception("Error")

        stats = get_collection_stats(mock_client, 'test_collection')

        assert stats is None
        mock_error.assert_called_once()


class TestGetCollection:
    """Tests for get_collection function."""

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_collection_success(self, mock_error):
        """Test successful collection retrieval."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection

        collection = get_collection(mock_client, 'test_collection')

        assert collection is not None
        assert collection == mock_collection
        mock_error.assert_not_called()

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_collection_error(self, mock_error):
        """Test collection retrieval error."""
        mock_client = MagicMock()
        mock_client.collections.__getitem__.side_effect = Exception("Error")

        collection = get_collection(mock_client, 'test_collection')

        assert collection is None
        mock_error.assert_called_once()


class TestSearchCollection:
    """Tests for search_collection function."""

    @patch('dashboard.src.typesense_client.st.error')
    def test_search_collection_success(self, mock_error):
        """Test successful collection search."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_documents = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.documents = mock_documents

        expected_result = {'hits': [{'document': {'id': '1', 'title': 'Test'}}]}
        mock_documents.search.return_value = expected_result

        params = {'q': 'test', 'limit': 10}
        result = search_collection(mock_client, 'test_collection', **params)

        assert result == expected_result
        mock_documents.search.assert_called_once_with(params)
        mock_error.assert_not_called()

    @patch('dashboard.src.typesense_client.st.error')
    def test_search_collection_error(self, mock_error):
        """Test collection search error."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_documents = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.documents = mock_documents
        mock_documents.search.side_effect = Exception("Search error")

        result = search_collection(mock_client, 'test_collection', q='test')

        assert result is None
        mock_error.assert_called_once()


class TestGetDocuments:
    """Tests for get_documents function."""

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_documents_success(self, mock_error):
        """Test successful document retrieval."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_documents = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.documents = mock_documents

        expected_hits = [
            {'document': {'id': '1', 'title': 'Test 1'}},
            {'document': {'id': '2', 'title': 'Test 2'}}
        ]
        mock_documents.search.return_value = {'hits': expected_hits}

        result = get_documents(mock_client, 'test_collection', limit=10)

        assert len(result) == 2
        # get_documents returns the full hits array, not just documents
        assert result[0] == {'document': {'id': '1', 'title': 'Test 1'}}
        assert result[1] == {'document': {'id': '2', 'title': 'Test 2'}}
        mock_error.assert_not_called()

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_documents_with_default_limit(self, mock_error):
        """Test document retrieval with default limit."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_documents = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.documents = mock_documents

        mock_documents.search.return_value = {'hits': []}

        get_documents(mock_client, 'test_collection')

        # Verify default limit of 250 was used
        call_args = mock_documents.search.call_args[0][0]
        assert call_args['limit'] == 250
        assert call_args['q'] == '*'

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_documents_error(self, mock_error):
        """Test document retrieval error."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_documents = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.documents = mock_documents
        mock_documents.search.side_effect = Exception("Error")

        result = get_documents(mock_client, 'test_collection')

        assert result == []
        mock_error.assert_called_once()


class TestGetCollectionSchema:
    """Tests for get_collection_schema function."""

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_collection_schema_success(self, mock_error):
        """Test successful schema retrieval."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection

        expected_schema = {
            'name': 'test_collection',
            'fields': [
                {'name': 'id', 'type': 'string'},
                {'name': 'title', 'type': 'string'}
            ]
        }
        mock_collection.retrieve.return_value = expected_schema

        schema = get_collection_schema(mock_client, 'test_collection')

        assert schema == expected_schema
        mock_collection.retrieve.assert_called_once()
        mock_error.assert_not_called()

    @patch('dashboard.src.typesense_client.st.error')
    def test_get_collection_schema_error(self, mock_error):
        """Test schema retrieval error."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.collections.__getitem__.return_value = mock_collection
        mock_collection.retrieve.side_effect = Exception("Error")

        schema = get_collection_schema(mock_client, 'test_collection')

        assert schema is None
        mock_error.assert_called_once()
