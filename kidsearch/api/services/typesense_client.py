"""
Typesense client with async support and embedding integration
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

import typesense
from typesense.exceptions import TypesenseClientError

from kidsearch.embeddings import (
    EmbeddingProvider,
    NoEmbeddingProvider,
    create_embedding_provider,
)


class TypesenseClient:
    """Async Typesense client with embedding support"""

    def __init__(self, url: str, api_key: str, collection_name: str):
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.client: Optional[typesense.Client] = None
        self.embedding_provider: EmbeddingProvider = NoEmbeddingProvider()
        self.use_vector_search = False

        # Initialize embedding provider
        embedding_provider_name = os.getenv("EMBEDDING_PROVIDER", "none").lower()
        if embedding_provider_name == "gemini":
            self.embedding_provider = create_embedding_provider()
            self.use_vector_search = True
        elif embedding_provider_name in ["huggingface", "sentence_transformer"]:
            self.embedding_provider = create_embedding_provider()
            self.use_vector_search = True

    async def connect(self):
        """Initialize Typesense client and create collection if needed"""
        # Parse URL to get host and port
        url_parts = self.url.replace("http://", "").replace("https://", "").split(":")
        host = url_parts[0]
        port = int(url_parts[1]) if len(url_parts) > 1 else 8108

        self.client = typesense.Client(
            {
                "nodes": [{"host": host, "port": str(port), "protocol": "http"}],
                "api_key": self.api_key,
                "connection_timeout_seconds": 30,
            }
        )

        # Test connection
        try:
            await asyncio.to_thread(self.client.collections.retrieve)
        except Exception as e:
            raise TypesenseClientError(f"Failed to connect to Typesense: {e}")

        # Create collection if it doesn't exist
        await self._ensure_collection()

    async def _ensure_collection(self):
        """Create collection with schema if it doesn't exist"""
        try:
            await asyncio.to_thread(
                self.client.collections[self.collection_name].retrieve
            )
            return  # Collection exists
        except Exception:
            pass  # Collection doesn't exist, create it

        # Define schema
        schema = {
            "name": self.collection_name,
            "enable_nested_fields": True,
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "site", "type": "string", "facet": True},
                {"name": "url", "type": "string"},
                {"name": "title", "type": "string"},
                {"name": "excerpt", "type": "string"},
                {"name": "content", "type": "string"},
                {"name": "images", "type": "object[]"},
                {"name": "lang", "type": "string", "facet": True},
                {"name": "timestamp", "type": "int64"},
                {"name": "indexed_at", "type": "string"},
                {"name": "last_crawled_at", "type": "string"},
                {"name": "content_hash", "type": "string"},
            ],
        }

        # Add vector field if embeddings enabled
        if self.use_vector_search and self.embedding_provider:
            embedding_dim = self.embedding_provider.get_embedding_dim()
            if embedding_dim > 0:
                schema["fields"].extend(
                    [
                        {
                            "name": "embedding_vec",
                            "type": "float[]",
                            "num_dim": embedding_dim,
                        },
                        {
                            "name": "embedding_provider",
                            "type": "string",
                            "optional": True,
                        },
                        {"name": "embedding_model", "type": "string", "optional": True},
                        {
                            "name": "embedding_dimensions",
                            "type": "int32",
                            "optional": True,
                        },
                        {
                            "name": "has_embedding",
                            "type": "bool",
                            "optional": True,
                            "facet": True,
                        },
                    ]
                )

        # Create collection
        try:
            await asyncio.to_thread(self.client.collections.create, schema)
        except Exception as e:
            # Collection might have been created by another worker
            if "already exists" in str(e):
                return
            raise

    async def index_documents(self, documents: List[Dict[str, Any]]):
        """Batch index documents"""
        if not documents:
            return

        # Convert documents to Typesense format
        # Remove _vectors field if present (Meilisearch format)
        for doc in documents:
            if "_vectors" in doc:
                vec = doc.pop("_vectors")
                if isinstance(vec, dict) and "default" in vec:
                    doc["embedding_vec"] = vec["default"]
                elif isinstance(vec, list):
                    doc["embedding_vec"] = vec

        # Batch import
        await asyncio.to_thread(
            self.client.collections[self.collection_name].documents.import_,
            documents,
            {"action": "upsert"},
        )

    async def search(
        self,
        query: str,
        filter_by: Optional[str] = None,
        limit: int = 20,
        use_vector: bool = True,
        query_vector: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Search documents with optional vector search"""

        search_params = {
            "q": query,
            "query_by": "title,excerpt,content",
            "limit": limit,
            "include_fields": "id,title,url,excerpt,site,images,lang,timestamp,indexed_at",
        }

        if filter_by:
            search_params["filter_by"] = filter_by

        # Vector search if enabled
        if use_vector and self.use_vector_search and query_vector:
            # Convert query_vector to comma-separated string
            vector_str = ",".join(map(str, query_vector))
            search_params["vector_query"] = f"embedding_vec:([{vector_str}], k:{limit})"

        # Execute search
        results = await asyncio.to_thread(
            self.client.collections[self.collection_name].documents.search,
            search_params,
        )

        return results

    async def delete_document(self, doc_id: str):
        """Delete a document by ID"""
        await asyncio.to_thread(
            self.client.collections[self.collection_name].documents[doc_id].delete
        )

    async def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            collection = await asyncio.to_thread(
                self.client.collections[self.collection_name].retrieve
            )
            return {
                "num_documents": collection.get("num_documents", 0),
                "name": collection.get("name", ""),
            }
        except Exception:
            return {"num_documents": 0, "name": self.collection_name}

    async def close(self):
        """Cleanup (Typesense client doesn't need explicit close)"""
        pass
