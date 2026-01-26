"""
Search endpoints.
"""

import asyncio
import logging
import os
import time
from typing import List, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from typesense.exceptions import TypesenseClientError

from ..models import (
    APIStats,
    FeedbackRequest,
    FeedbackResponse,
    Language,
    SearchResponse,
    SearchResult,
    SearchStats,
)
from ..services.wiki_client import WikiClient
from ..state import AppState

logger = logging.getLogger(__name__)
router = APIRouter()

CSE_CONFIGURED = os.getenv("GOOGLE_CSE_API_KEY") and os.getenv("GOOGLE_CSE_API_KEY") != "your_google_api_key_here"
RERANKING_ENABLED = os.getenv("RERANKING_ENABLED", "false").lower() == "true"

def _truncate(text: str, max_chars: int = 256) -> str:
    return text[:max_chars]

async def _embed_results(embedding_provider, results: List[SearchResult]):
    """Asynchronously embeds a list of search results in place."""
    texts_to_embed = [_truncate(f"{r.title or ''} {r.excerpt or ''}") for r in results if not r.vectors]
    if not texts_to_embed:
        return

    embeddings = await asyncio.to_thread(embedding_provider.encode, texts_to_embed)
    
    text_idx = 0
    for result in results:
        if not result.vectors:
            result.vectors = embeddings[text_idx]
            text_idx += 1

@router.get(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Unified search",
)
async def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    lang: Language = Query(default=Language.FR, description="Search language"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    use_cse: bool = Query(default=True, description="Include Google CSE results"),
    use_hybrid: bool = Query(default=True, description="Use hybrid vector search"),
    use_reranking: bool = Query(default=True, description="Apply semantic reranking"),
) -> SearchResponse:
    state: AppState = request.app.state
    start_time = time.time()
    logger.info(f"Search request: q='{q}', lang={lang.value}, use_cse={use_cse}, use_reranking={use_reranking}")

    typesense_client = state.typesense_client
    cse_client = state.cse_client
    wiki_clients = state.wiki_clients
    safety_filter = state.safety_filter
    merger = state.merger
    reranker = state.reranker
    embedding_provider = state.embedding_provider

    if not typesense_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Typesense is not available.")

    async def search_typesense() -> Tuple[List[SearchResult], float]:
        s = time.time()
        try:
            # Generate query embedding if hybrid search is enabled
            query_vector = None
            if use_hybrid and typesense_client.use_vector_search and embedding_provider:
                query_embeddings = await asyncio.to_thread(embedding_provider.encode, [q])
                query_vector = query_embeddings[0] if query_embeddings else None

            # Build filter for language
            filter_by = None
            if lang and lang.value != "all":
                filter_by = f"lang:={lang.value}"

            # Search Typesense
            results_dict = await typesense_client.search(
                query=q,
                filter_by=filter_by,
                limit=limit,
                use_vector=use_hybrid,
                query_vector=query_vector
            )

            # Transform Typesense results to SearchResult format
            from ..models import ImageResult, SearchSource

            # First pass: collect all hits and scores
            hits_list = results_dict.get('hits', [])

            # Get raw scores and find max for normalization
            raw_scores = []
            for hit in hits_list:
                raw_score = hit.get('text_match_info', {}).get('score', 0)
                if isinstance(raw_score, str):
                    try:
                        raw_score = float(raw_score)
                    except ValueError:
                        raw_score = 0.0
                raw_scores.append(raw_score)

            # Normalize scores to 0-1 range using min-max normalization
            max_score = max(raw_scores) if raw_scores else 1.0
            min_score = min(raw_scores) if raw_scores else 0.0
            score_range = max_score - min_score

            search_results = []
            for idx, hit in enumerate(hits_list):
                doc = hit['document']
                # Normalize score to 0-1 range
                if score_range > 0:
                    normalized_score = (raw_scores[idx] - min_score) / score_range
                else:
                    # All scores are the same (single result or identical scores)
                    normalized_score = 1.0 if raw_scores else 0.0

                # Ensure score is in valid range
                normalized_score = max(0.0, min(1.0, normalized_score))

                search_results.append(SearchResult(
                    id=doc['id'],
                    title=doc['title'],
                    url=doc['url'],
                    excerpt=doc['excerpt'],
                    site=doc.get('site'),
                    images=[ImageResult(**img) if isinstance(img, dict) else img for img in doc.get('images', [])],
                    lang=doc.get('lang'),
                    timestamp=doc.get('timestamp'),
                    indexed_at=doc.get('indexed_at'),
                    source=SearchSource.TYPESENSE,
                    score=normalized_score,
                    vectors=doc.get('embedding_vec') if (RERANKING_ENABLED and use_reranking) else None
                ))

            return search_results, (time.time() - s) * 1000
        except TypesenseClientError as e:
            logger.error(f"Typesense API error: {e}")
            return [], (time.time() - s) * 1000
        except Exception as e:
            logger.error(f"Typesense search failed: {e}")
            return [], (time.time() - s) * 1000

    async def search_cse() -> Tuple[List[SearchResult], bool, float]:
        if not (use_cse and CSE_CONFIGURED and cse_client):
            return [], False, 0.0
        s = time.time()
        try:
            res, hit = await cse_client.search(query=q, lang=lang.value, num_results=min(limit, 10))
            if embedding_provider and use_reranking and RERANKING_ENABLED:
                await _embed_results(embedding_provider, res)
            return res, hit, (time.time() - s) * 1000
        except Exception as e:
            logger.error(f"CSE search failed: {e}", exc_info=True)
            return [], False, (time.time() - s) * 1000

    async def search_wiki() -> Tuple[List[SearchResult], float]:
        """Search all configured wiki instances in parallel."""
        if not wiki_clients:
            return [], 0.0

        s = time.time()

        # Search all wikis in parallel
        async def search_single_wiki(client: WikiClient) -> List[SearchResult]:
            try:
                return await client.search(query=q, lang=lang.value, limit=5)
            except Exception as e:
                logger.error(f"Error searching wiki {client.site_name}: {e}")
                return []

        # Execute all wiki searches concurrently
        wiki_results_list = await asyncio.gather(*[search_single_wiki(client) for client in wiki_clients])

        # Flatten and combine results from all wikis
        all_wiki_results = []
        for results in wiki_results_list:
            all_wiki_results.extend(results)

        # Embed results if provider is available
        if embedding_provider and all_wiki_results and use_reranking and RERANKING_ENABLED:
            await _embed_results(embedding_provider, all_wiki_results)

        return all_wiki_results, (time.time() - s) * 1000

    query_embedding_task = asyncio.to_thread(embedding_provider.encode, [q]) if RERANKING_ENABLED and embedding_provider and use_reranking else None

    (ts_res, ts_time), (cse_res, cache_hit, cse_time), (wiki_res, wiki_time), query_emb_list = await asyncio.gather(
        search_typesense(), search_cse(), search_wiki(), query_embedding_task or asyncio.sleep(0, result=[None])
    )

    query_embedding = np.array(query_emb_list[0]) if query_emb_list and query_emb_list[0] else None

    ts_res = safety_filter.filter_results(ts_res)
    cse_res = safety_filter.filter_results(cse_res)
    wiki_res = safety_filter.filter_results(wiki_res)

    logger.info(f"Results after safety filter: Typesense={len(ts_res)}, CSE={len(cse_res)}, Wiki={len(wiki_res)}")

    # Deduplicate wiki results by ID to avoid duplicates from multiple wikis
    seen_ids = set()
    deduped_wiki_res = []
    for r in wiki_res:
        if r.id not in seen_ids:
            deduped_wiki_res.append(r)
            seen_ids.add(r.id)

    logger.info(f"Wiki results after deduplication: {len(deduped_wiki_res)}")

    # Changed from limit * 2 to limit for performance on weak CPUs
    merged_results = deduped_wiki_res + merger.merge(typesense_results=ts_res, cse_results=cse_res, limit=limit)
    logger.info(f"Results after merge: {len(merged_results)}")

    reranking_applied, reranking_time_ms = False, None
    if use_reranking and RERANKING_ENABLED and reranker and query_embedding is not None:
        rerank_start = time.time()
        merged_results = reranker.rerank(query=q, results=merged_results, top_k=limit, query_embedding=query_embedding)
        reranking_time_ms = (time.time() - rerank_start) * 1000
        reranking_applied = True
        logger.info(f"Reranking applied in {reranking_time_ms:.2f}ms, results after rerank: {len(merged_results)}")
    else:
        logger.info(f"Reranking skipped (enabled={use_reranking}, configured={RERANKING_ENABLED}, reranker={reranker is not None}, embedding={query_embedding is not None})")

    final_results = merged_results[:limit]
    logger.info(f"Final results count: {len(final_results)}")

    # Remove embeddings from results before sending to client (waste of bandwidth)
    for result in final_results:
        result.vectors = None

    total_time_ms = (time.time() - start_time) * 1000

    logger.info(f"Search completed in {total_time_ms:.2f}ms - Breakdown: Typesense={ts_time:.1f}ms, CSE={cse_time:.1f}ms, Wiki={wiki_time:.1f}ms, Rerank={reranking_time_ms:.1f}ms" if reranking_time_ms else f"Search completed in {total_time_ms:.2f}ms - Breakdown: Typesense={ts_time:.1f}ms, CSE={cse_time:.1f}ms, Wiki={wiki_time:.1f}ms")

    stats = SearchStats(
        total_results=len(final_results),
        typesense_results=len(ts_res),
        cse_results=len(cse_res),
        wiki_results=len(wiki_res),
        processing_time_ms=total_time_ms,
        typesense_time_ms=ts_time,
        cse_time_ms=cse_time,
        wiki_time_ms=wiki_time,
        reranking_time_ms=reranking_time_ms,
        reranking_applied=reranking_applied,
        cache_hit=cache_hit,
    )

    if state.stats_db:
        state.stats_db.log_search(q, lang.value, limit, use_cse, use_hybrid, use_reranking, stats.model_dump())

    return SearchResponse(query=q, results=final_results, stats=stats)

@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_200_OK)
async def submit_feedback(request: Request, feedback: FeedbackRequest) -> FeedbackResponse:
    state: AppState = request.app.state
    if state.stats_db:
        state.stats_db.log_feedback(**feedback.model_dump())
    return FeedbackResponse(success=True, message="Feedback received.")

@router.get("/stats", status_code=status.HTTP_200_OK)
async def get_stats(request: Request) -> JSONResponse:
    state: AppState = request.app.state
    stats_db = state.stats_db
    cse_client = state.cse_client
    
    if not stats_db:
        api_stats = APIStats(
            total_searches=0, searches_last_hour=0, avg_response_time_ms=0.0,
            cache_hit_rate=0.0, top_queries=[], error_rate=0.0,
            cse_quota_used=0, cse_quota_limit=100
        )
    else:
        cse_quota = cse_client.get_quota_usage() if cse_client else {}
        api_stats = APIStats(
            total_searches=stats_db.get_total_searches(),
            searches_last_hour=stats_db.get_searches_last_hour(),
            avg_response_time_ms=stats_db.get_avg_search_time(),
            cache_hit_rate=stats_db.get_cache_hit_rate(),
            top_queries=stats_db.get_top_queries(limit=50),
            error_rate=stats_db.get_error_rate(),
            cse_quota_used=cse_quota.get("used", 0),
            cse_quota_limit=cse_quota.get("limit", 100),
        )
        
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}
    return JSONResponse(content=api_stats.model_dump(), headers=headers)

@router.post("/stats/reset", status_code=status.HTTP_200_OK)
async def reset_stats(request: Request):
    state: AppState = request.app.state
    if not state.stats_db or not state.stats_db.reset_stats():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reset API statistics.")
    logger.info("API statistics have been reset.")
    return {"message": "API statistics reset successfully."}
