"""
Client for searching a MediaWiki instance (Vikidia, Wikipedia).
"""

import logging
from typing import List
import aiohttp
import ssl
import certifi
import os

from ..models import SearchResult

# Import curl_cffi for Cloudflare bypass
try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False

# Import cloudscraper for advanced Cloudflare bypass
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

logger = logging.getLogger(__name__)

# User-Agent for HTTP requests
USER_AGENT = os.getenv('USER_AGENT', 'KidSearch-Crawler/2.0 (+https://github.com/laurentftech/MeilisearchCrawler)')


class WikiClient:
    """A client to search a MediaWiki site like Vikidia."""

    def __init__(self, api_url: str, site_url: str, site_name: str, lang: str = None):
        self.api_url = api_url
        self.site_url = site_url
        self.site_name = site_name
        self.user_agent = USER_AGENT
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

        # Auto-detect language from API URL if not provided
        if lang is None:
            if 'en.wikipedia' in api_url or 'en.vikidia' in api_url:
                self.lang = 'en'
            elif 'fr.wikipedia' in api_url or 'fr.vikidia' in api_url:
                self.lang = 'fr'
            elif 'es.wikipedia' in api_url:
                self.lang = 'es'
            elif 'de.wikipedia' in api_url:
                self.lang = 'de'
            else:
                # Default to English for unknown
                self.lang = 'en'
        else:
            self.lang = lang

    def _use_cloudflare_bypass(self) -> bool:
        """Determines if cloudscraper should be used to bypass Cloudflare."""
        return CLOUDSCRAPER_AVAILABLE and 'vikidia' in self.site_name.lower()

    async def _fetch_with_curl_cffi(self, params: dict) -> dict:
        """Makes a request using curl_cffi to bypass Cloudflare."""
        async with CurlAsyncSession() as session:
            try:
                # Build Accept-Language based on wiki language
                accept_lang_map = {
                    'fr': 'fr-FR,fr;q=0.9,en;q=0.8',
                    'en': 'en-US,en;q=0.9',
                    'es': 'es-ES,es;q=0.9,en;q=0.8',
                    'de': 'de-DE,de;q=0.9,en;q=0.8'
                }
                accept_language = accept_lang_map.get(self.lang, 'en-US,en;q=0.9')

                headers = {
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Accept-Language': accept_language,
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': self.site_url,
                    'DNT': '1',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin'
                }
                response = await session.get(
                    self.api_url,
                    params=params,
                    headers=headers,
                    impersonate="chrome120",
                    timeout=10
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"HTTP error while searching wiki with curl_cffi: {e}")
                return {}

    async def _fetch_with_aiohttp(self, params: dict) -> dict:
        """Makes a request using aiohttp with a proper User-Agent."""
        # Build Accept-Language header based on wiki language
        accept_lang_map = {
            'fr': 'fr-FR,fr;q=0.9,en;q=0.8',
            'en': 'en-US,en;q=0.9',
            'es': 'es-ES,es;q=0.9,en;q=0.8',
            'de': 'de-DE,de;q=0.9,en;q=0.8'
        }
        accept_language = accept_lang_map.get(self.lang, 'en-US,en;q=0.9')

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': accept_language,
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': self.site_url,
            'DNT': '1',
            'Connection': 'keep-alive'
        }
        async with aiohttp.ClientSession(headers=headers, connector=aiohttp.TCPConnector(ssl=self.ssl_context)) as session:
            try:
                async with session.get(self.api_url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    response.raise_for_status()
                    return await response.json()
            except Exception as e:
                logger.error(f"HTTP error while searching wiki with aiohttp: {e}")
                return {}

    async def _fetch_with_cloudscraper(self, params: dict) -> dict:
        """Makes a request using cloudscraper to bypass Cloudflare challenges."""
        import asyncio
        from functools import partial
        import certifi

        try:
            # cloudscraper is sync, so we run it in executor
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )

            # Run synchronous request in thread pool with SSL cert verification
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(scraper.get, self.api_url, params=params, timeout=15, verify=certifi.where())
            )

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"HTTP error while searching wiki with cloudscraper: {e}")
            return {}

    async def search(self, query: str, lang: str, limit: int = 5) -> List[SearchResult]:
        """
        Searches the wiki for a given query.

        Args:
            query: The search query.
            lang: The language of the search (used for result model).
            limit: The maximum number of results to return.

        Returns:
            A list of SearchResult objects.
        """
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srprop": "snippet|titlesnippet",
            "origin": "*"  # Required for CORS
        }

        use_cf_bypass = self._use_cloudflare_bypass()
        if use_cf_bypass:
            # Try cloudscraper first (best Cloudflare bypass)
            logger.debug(f"Using cloudscraper to search wiki: {self.site_name}")
            data = await self._fetch_with_cloudscraper(params)

            # Fallback to curl_cffi if cloudscraper failed
            if not data or 'query' not in data:
                logger.info(f"cloudscraper failed for {self.site_name}, trying curl_cffi")
                if CURL_CFFI_AVAILABLE:
                    data = await self._fetch_with_curl_cffi(params)

            # Final fallback to aiohttp
            if not data or 'query' not in data:
                logger.info(f"All CF bypass methods failed for {self.site_name}, falling back to aiohttp")
                data = await self._fetch_with_aiohttp(params)
        else:
            logger.debug(f"Using aiohttp to search wiki: {self.site_name}")
            data = await self._fetch_with_aiohttp(params)

        if not data or 'query' not in data or 'search' not in data['query']:
            return []

        results = []
        for item in data['query']['search']:
            page_id = item.get("pageid")
            title = item.get("title")
            snippet_html = item.get("snippet", "")

            if not all([page_id, title]):
                continue

            # Construct URL from page ID
            url = f"{self.site_url}?curid={page_id}"

            results.append(
                SearchResult(
                    id=f"wiki_{page_id}",
                    url=url,
                    title=title,
                    excerpt=snippet_html,  # Keep HTML for display
                    source="wiki",
                    site=self.site_name,
                    lang=lang,
                    score=1.0,  # Default score for wiki results
                )
            )

        return results
