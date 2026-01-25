"""
Tests for search endpoints and score normalization.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request
from kidsearch.api.models import SearchResult, SearchSource, Language
from kidsearch.api.routes.search import search, submit_feedback


class TestScoreNormalization:
    """Tests for Typesense score normalization logic."""

    @pytest.mark.asyncio
    async def test_score_normalization_normal_range(self):
        """Test score normalization with normal score range."""
        from kidsearch.api.routes.search import router

        # Mock Typesense response with normal scores
        mock_typesense_response = {
            'hits': [
                {
                    'document': {
                        'id': '1',
                        'title': 'First Result',
                        'url': 'https://example.com/1',
                        'excerpt': 'First excerpt',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': 1000}
                },
                {
                    'document': {
                        'id': '2',
                        'title': 'Second Result',
                        'url': 'https://example.com/2',
                        'excerpt': 'Second excerpt',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': 500}
                },
                {
                    'document': {
                        'id': '3',
                        'title': 'Third Result',
                        'url': 'https://example.com/3',
                        'excerpt': 'Third excerpt',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': 100}
                }
            ]
        }

        # Create mock request
        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        # Mock Typesense client
        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(return_value=mock_typesense_response)
        mock_ts_client.use_vector_search = False

        # Mock other services
        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: kwargs.get('typesense_results', [])
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        # Call search endpoint
        response = await search(
            request=mock_request,
            q="test query",
            lang=Language.FR,
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        # Verify normalized scores are between 0 and 1
        assert len(response.results) == 3
        assert all(0.0 <= r.score <= 1.0 for r in response.results)

        # Verify relative ordering is preserved (highest score = 1.0, lowest = 0.0)
        assert response.results[0].score == 1.0  # 1000 -> max
        assert response.results[1].score == pytest.approx(0.444, abs=0.01)  # 500 -> middle
        assert response.results[2].score == 0.0  # 100 -> min

    @pytest.mark.asyncio
    async def test_score_normalization_huge_integers(self):
        """Test score normalization with Typesense's huge 64-bit integer scores."""
        from kidsearch.api.routes.search import router

        # Mock Typesense response with huge integer scores (real Typesense behavior)
        mock_typesense_response = {
            'hits': [
                {
                    'document': {
                        'id': '1',
                        'title': 'Result 1',
                        'url': 'https://example.com/1',
                        'excerpt': 'Excerpt 1',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': 578730123365187698}
                },
                {
                    'document': {
                        'id': '2',
                        'title': 'Result 2',
                        'url': 'https://example.com/2',
                        'excerpt': 'Excerpt 2',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': 578730123365187600}
                }
            ]
        }

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(return_value=mock_typesense_response)
        mock_ts_client.use_vector_search = False

        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: kwargs.get('typesense_results', [])
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        response = await search(
            request=mock_request,
            q="test query",
            lang=Language.FR,
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        # Verify scores are normalized to 0-1 range
        assert len(response.results) == 2
        assert all(0.0 <= r.score <= 1.0 for r in response.results)

        # First result should have score 1.0 (highest)
        assert response.results[0].score == 1.0
        # Second result should have score 0.0 (lowest)
        assert response.results[1].score == 0.0

    @pytest.mark.asyncio
    async def test_score_normalization_all_identical_scores(self):
        """Test score normalization when all scores are identical."""
        from kidsearch.api.routes.search import router

        # Mock Typesense response with identical scores
        mock_typesense_response = {
            'hits': [
                {
                    'document': {
                        'id': str(i),
                        'title': f'Result {i}',
                        'url': f'https://example.com/{i}',
                        'excerpt': f'Excerpt {i}',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': 1000}
                }
                for i in range(1, 4)
            ]
        }

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(return_value=mock_typesense_response)
        mock_ts_client.use_vector_search = False

        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: kwargs.get('typesense_results', [])
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        response = await search(
            request=mock_request,
            q="test query",
            lang=Language.FR,
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        # When all scores are identical, they should all be normalized to 1.0
        assert len(response.results) == 3
        assert all(r.score == 1.0 for r in response.results)

    @pytest.mark.asyncio
    async def test_score_normalization_single_result(self):
        """Test score normalization with single result."""
        from kidsearch.api.routes.search import router

        # Mock Typesense response with single result
        mock_typesense_response = {
            'hits': [
                {
                    'document': {
                        'id': '1',
                        'title': 'Only Result',
                        'url': 'https://example.com/1',
                        'excerpt': 'Only excerpt',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': 12345}
                }
            ]
        }

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(return_value=mock_typesense_response)
        mock_ts_client.use_vector_search = False

        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: kwargs.get('typesense_results', [])
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        response = await search(
            request=mock_request,
            q="test query",
            lang=Language.FR,
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        # Single result should have score 1.0
        assert len(response.results) == 1
        assert response.results[0].score == 1.0

    @pytest.mark.asyncio
    async def test_score_normalization_empty_results(self):
        """Test score normalization with empty results."""
        from kidsearch.api.routes.search import router

        # Mock Typesense response with no results
        mock_typesense_response = {
            'hits': []
        }

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(return_value=mock_typesense_response)
        mock_ts_client.use_vector_search = False

        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: kwargs.get('typesense_results', [])
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        response = await search(
            request=mock_request,
            q="test query",
            lang=Language.FR,
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        # Empty results should return empty list
        assert len(response.results) == 0

    @pytest.mark.asyncio
    async def test_score_normalization_string_scores(self):
        """Test score normalization when scores are returned as strings."""
        from kidsearch.api.routes.search import router

        # Mock Typesense response with string scores
        mock_typesense_response = {
            'hits': [
                {
                    'document': {
                        'id': '1',
                        'title': 'Result 1',
                        'url': 'https://example.com/1',
                        'excerpt': 'Excerpt 1',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': "578730123365187698"}  # String score
                },
                {
                    'document': {
                        'id': '2',
                        'title': 'Result 2',
                        'url': 'https://example.com/2',
                        'excerpt': 'Excerpt 2',
                        'site': 'Example'
                    },
                    'text_match_info': {'score': "578730123365187600"}  # String score
                }
            ]
        }

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(return_value=mock_typesense_response)
        mock_ts_client.use_vector_search = False

        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: kwargs.get('typesense_results', [])
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        response = await search(
            request=mock_request,
            q="test query",
            lang=Language.FR,
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        # String scores should be converted and normalized properly
        assert len(response.results) == 2
        assert all(0.0 <= r.score <= 1.0 for r in response.results)
        assert response.results[0].score == 1.0
        assert response.results[1].score == 0.0


class TestLanguageFiltering:
    """Tests for language filtering in search."""

    @pytest.mark.asyncio
    async def test_language_filter_french(self):
        """Test search with French language filter."""
        from kidsearch.api.routes.search import router

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(return_value={'hits': []})
        mock_ts_client.use_vector_search = False

        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: []
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        await search(
            request=mock_request,
            q="test query",
            lang=Language.FR,
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        # Verify Typesense was called with French filter
        mock_ts_client.search.assert_called_once()
        call_kwargs = mock_ts_client.search.call_args[1]
        assert call_kwargs['filter_by'] == 'lang:=fr'

    @pytest.mark.asyncio
    async def test_language_filter_all(self):
        """Test search with 'all' language filter (no filtering)."""
        from kidsearch.api.routes.search import router

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(return_value={'hits': []})
        mock_ts_client.use_vector_search = False

        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: []
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        # Create custom Language enum value for "all"
        class AllLanguage:
            value = "all"

        await search(
            request=mock_request,
            q="test query",
            lang=AllLanguage(),
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        # Verify Typesense was called without language filter
        mock_ts_client.search.assert_called_once()
        call_kwargs = mock_ts_client.search.call_args[1]
        assert call_kwargs['filter_by'] is None


class TestSearchErrorHandling:
    """Tests for search error handling."""

    @pytest.mark.asyncio
    async def test_search_typesense_unavailable(self):
        """Test search when Typesense is unavailable."""
        from fastapi import HTTPException

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()
        mock_state.typesense_client = None

        mock_request.app.state = mock_state

        # Should raise HTTPException with 503 status
        with pytest.raises(HTTPException) as exc_info:
            await search(
                request=mock_request,
                q="test query",
                lang=Language.FR,
                limit=20,
                use_cse=False,
                use_hybrid=False,
                use_reranking=False
            )

        assert exc_info.value.status_code == 503
        assert "Typesense is not available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_search_typesense_error_returns_empty(self):
        """Test search when Typesense raises an error."""
        from kidsearch.api.routes.search import router
        from typesense.exceptions import TypesenseClientError

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()

        mock_ts_client = AsyncMock()
        mock_ts_client.search = AsyncMock(side_effect=TypesenseClientError("Connection error"))
        mock_ts_client.use_vector_search = False

        mock_state.typesense_client = mock_ts_client
        mock_state.cse_client = None
        mock_state.wiki_clients = []
        mock_state.safety_filter = MagicMock()
        mock_state.safety_filter.filter_results = lambda x: x
        mock_state.merger = MagicMock()
        mock_state.merger.merge = lambda **kwargs: []
        mock_state.reranker = None
        mock_state.embedding_provider = None
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        # Should not raise, but return empty results
        response = await search(
            request=mock_request,
            q="test query",
            lang=Language.FR,
            limit=20,
            use_cse=False,
            use_hybrid=False,
            use_reranking=False
        )

        assert len(response.results) == 0
        assert response.stats.total_results == 0


class TestFeedbackEndpoint:
    """Tests for feedback endpoint."""

    @pytest.mark.asyncio
    async def test_submit_feedback_success(self):
        """Test successful feedback submission."""
        from kidsearch.api.models import FeedbackRequest

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()
        mock_stats_db = MagicMock()
        mock_stats_db.log_feedback = MagicMock()

        mock_state.stats_db = mock_stats_db
        mock_request.app.state = mock_state

        feedback = FeedbackRequest(
            query="test query",
            result_id="result-1",
            result_url="https://example.com/result",
            reason="helpful"
        )

        response = await submit_feedback(
            request=mock_request,
            feedback=feedback
        )

        assert response.success is True
        mock_stats_db.log_feedback.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_feedback_no_stats_db(self):
        """Test feedback submission when stats DB is not available."""
        from kidsearch.api.models import FeedbackRequest

        mock_request = MagicMock(spec=Request)
        mock_state = MagicMock()
        mock_state.stats_db = None

        mock_request.app.state = mock_state

        feedback = FeedbackRequest(
            query="test query",
            result_id="result-1",
            result_url="https://example.com/result",
            reason="helpful"
        )

        # Should still return success even without DB
        response = await submit_feedback(
            request=mock_request,
            feedback=feedback
        )

        assert response.success is True
