"""
Meilisearch client service for KidSearch API.
Handles search queries against local indexed content.
"""

import logging
import hashlib
import os
import sys
from pathlib import Path
from typing import List, Optional

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.errors import MeilisearchApiError, MeilisearchCommunicationError, MeilisearchError
from meilisearch_python_sdk.models.search import SearchResults, Hybrid
import httpx

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from meilisearchcrawler.embeddings import create_embedding_provider, EmbeddingProvider, NoEmbeddingProvider
from ..models import SearchResult, SearchSource, ImageResult

logger = logging.getLogger(__name__)


class MeilisearchClient:
    """
    Client for searching a local Meilisearch index.
    Supports keyword and vector (semantic) search if embeddings are configured.
    """

    def __init__(self, url: str, api_key: str, index_name: str):
        """
        Initialize Meilisearch client.
        """
        self.url = url
        self.api_key = api_key
        self.index_name = index_name
        self.client: Optional[AsyncClient] = None
        self.index = None

        self.embedding_provider: EmbeddingProvider = NoEmbeddingProvider()
        self.use_vector_search = False
        self.is_rest_embedder = False

        embedding_provider_name = os.getenv("EMBEDDING_PROVIDER", "none").lower()

        if embedding_provider_name == "gemini":
            logger.info("✓ Vector search enabled with Gemini (REST embedder)")
            self.use_vector_search = True
            self.is_rest_embedder = True
        elif embedding_provider_name in ["huggingface", "sentence_transformer"]:
            # HuggingFace embeddings are handled by Meilisearch's userProvided embedder
            # We don't need to generate embeddings client-side
            logger.info("✓ Vector search enabled with HuggingFace (Meilisearch REST embedder)")
            self.use_vector_search = True
            self.is_rest_embedder = True
        else:
            logger.info("Vector search disabled (no embedding provider)")

    async def connect(self):
        """Connect to Meilisearch and initialize the index."""
        try:
            # Configure with timeout for complex searches (especially hybrid/vector search)
            # meilisearch-python-sdk accepts timeout parameter (in seconds)
            self.client = AsyncClient(self.url, self.api_key, timeout=30)
            self.index = self.client.index(self.index_name)
            await self.client.health()
            logger.info(f"Connected to Meilisearch at {self.url}, index: {self.index_name} (timeout: 30s)")
        except MeilisearchCommunicationError:
            logger.error(f"Failed to connect to Meilisearch at {self.url}. Service may be down.")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while connecting to Meilisearch: {e}")
            raise

    async def is_healthy(self) -> bool:
        """Check if Meilisearch is healthy."""
        if not self.client:
            return False
        try:
            health = await self.client.health()
            return health.status == "available"
        except Exception:
            return False

    async def search(
            self, query: str, lang: Optional[str] = None, limit: int = 20, use_hybrid: bool = True, retrieve_vectors: bool = True  # AJOUTÉ
    ) -> List[SearchResult]:
        """Search Meilisearch index using keyword or hybrid vector search."""
        if not self.index:
            logger.error("Meilisearch client not connected")
            return []

        try:
            from meilisearch_python_sdk.models.search import Hybrid

            # Only retrieve vectors if reranking is enabled (saves ~100KB+ bandwidth)
            attributes = ["id", "title", "url", "excerpt", "site", "images", "lang", "timestamp", "indexed_at"]
            if retrieve_vectors:
                attributes.append("_vectors")

            search_params = {
                "limit": limit,
                "attributes_to_retrieve": attributes,
                "attributes_to_search_on": ["title", "excerpt"],
                "show_ranking_score": True,
            }

            if lang:
                search_params["filter"] = f"lang = {lang}"

            # MODIFIÉ: Vérifier à la fois use_hybrid ET use_vector_search
            if use_hybrid and self.use_vector_search:
                search_params["hybrid"] = Hybrid(
                    semantic_ratio=0.5,
                    embedder="default"
                )

                if not self.is_rest_embedder:
                    try:
                        query_embeddings = self.embedding_provider.encode([query])
                        if query_embeddings and query_embeddings[0]:
                            search_params["vector"] = query_embeddings[0]
                            logger.debug(f"Added vector for query: '{query}'")
                    except Exception as e:
                        logger.warning(f"Failed to generate query embedding, falling back to keyword search: {e}")
                        search_params.pop("hybrid", None)

            results: SearchResults = await self.index.search(query, **search_params)

            search_results: List[SearchResult] = []
            for hit in results.hits:
                images = [
                    ImageResult(**img_data)
                    for img_data in hit.get("images", [])[:5]
                    if isinstance(img_data, dict)
                ]
                score = hit.get("_rankingScore", 0.5)

                result = SearchResult(
                    id=hit.get("id", self._generate_id(hit.get("url", ""))),
                    title=hit.get("title", ""),
                    url=hit.get("url", ""),
                    excerpt=hit.get("excerpt", ""),
                    content=None,
                    site=hit.get("site"),
                    images=images,
                    lang=hit.get("lang"),
                    timestamp=hit.get("timestamp"),
                    indexed_at=hit.get("indexed_at"),
                    vectors=hit.get("_vectors", None),
                    source=SearchSource.MEILISEARCH,
                    score=score,
                )
                search_results.append(result)

            logger.info(f"Meilisearch search for '{query}' (lang={lang}): {len(search_results)} results")
            return search_results

        except httpx.ReadTimeout:
            logger.error(f"Meilisearch search timeout for query '{query}' (exceeded 30s). Try reducing index size or optimizing search parameters.")
            return []
        except MeilisearchApiError as e:
            logger.error(f"Meilisearch API error for query '{query}': {e}")
            return []
        except MeilisearchError as e:
            logger.error(f"Meilisearch error for query '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during Meilisearch search for '{query}': {type(e).__name__}: {e}")
            return []

    def _generate_id(self, url: str) -> str:
        """Generate a consistent unique ID from a URL."""
        return hashlib.md5(url.encode()).hexdigest()

    async def get_index_stats(self) -> dict:
        """Get statistics for the index."""
        if not self.index:
            return {}
        try:
            stats = await self.index.get_stats()
            return {
                "numberOfDocuments": stats.number_of_documents,
                "isIndexing": stats.is_indexing,
                "fieldDistribution": stats.field_distribution,
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {}
