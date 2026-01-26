"""
Knowledge Panel endpoints.
Provides Wikipedia/Vikidia article data for knowledge panels in the frontend.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class KnowledgePanelResponse(BaseModel):
    """Response model for knowledge panel data."""
    title: str
    extract: str
    thumbnail: Optional[str] = None
    url: str
    source: str


@router.get(
    "/knowledge-panel",
    response_model=KnowledgePanelResponse,
    status_code=status.HTTP_200_OK,
    summary="Get knowledge panel data",
)
async def get_knowledge_panel(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    lang: str = Query(default="fr", description="Language code (fr, en, etc.)"),
) -> KnowledgePanelResponse:
    """
    Get knowledge panel data for a query.

    This endpoint searches for relevant articles and returns formatted data
    for display in a knowledge panel (title, extract, thumbnail, URL).

    Uses WikiClient with CloudFlare bypass to avoid CORS and 403 errors.
    """
    state = request.app.state
    wiki_clients = state.wiki_clients

    if not wiki_clients:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No wiki sources configured"
        )

    # Find the appropriate wiki client for the language
    wiki_client = None
    for client in wiki_clients:
        # Simple heuristic: check if site_name contains the language
        if lang in client.site_name.lower():
            wiki_client = client
            break

    # Fallback to first client if no language match
    if not wiki_client:
        wiki_client = wiki_clients[0]

    try:
        # Search for the article
        search_results = await wiki_client.search(query=q, lang=lang, limit=3)

        if not search_results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No knowledge panel found for this query"
            )

        # Use the first (most relevant) result
        best_result = search_results[0]

        # Get the full page data (extract + thumbnail)
        page_data = await wiki_client.get_page_data(
            page_title=best_result.title,
            include_extract=True,
            include_thumbnail=True
        )

        if not page_data or 'extract' not in page_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not retrieve page data"
            )

        # Build response
        return KnowledgePanelResponse(
            title=best_result.title,
            extract=page_data.get('extract', ''),
            thumbnail=page_data.get('thumbnail'),
            url=str(best_result.url),  # Convert HttpUrl to string
            source=wiki_client.site_name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching knowledge panel: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge panel data"
        )
