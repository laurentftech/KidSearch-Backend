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

logger = logging.getLogger(__name__)

# User-Agent for HTTP requests
USER_AGENT = os.getenv(
    "USER_AGENT",
    "KidSearch-Crawler/2.0 (+https://github.com/laurentftech/KidSearch-Backend)",
)


class WikiClient:
    """A client to search a MediaWiki site like Vikidia."""

    def __init__(self, api_url: str, site_url: str, site_name: str, lang: str = None):
        self.api_url = api_url
        self.site_url = site_url
        self.site_name = site_name
        self.user_agent = USER_AGENT
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self._session: aiohttp.ClientSession | None = None
        self._curl_session: CurlAsyncSession | None = None

        # Auto-detect language from API URL if not provided
        if lang is None:
            if "en.wikipedia" in api_url or "en.vikidia" in api_url:
                self.lang = "en"
            elif "fr.wikipedia" in api_url or "fr.vikidia" in api_url:
                self.lang = "fr"
            elif "es.wikipedia" in api_url:
                self.lang = "es"
            elif "de.wikipedia" in api_url:
                self.lang = "de"
            else:
                # Default to English for unknown
                self.lang = "en"
        else:
            self.lang = lang

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=20),
                raise_for_status=False,
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    def _use_cloudflare_bypass(self) -> bool:
        """Determines if curl_cffi should be used to bypass Cloudflare."""
        return CURL_CFFI_AVAILABLE and "vikidia" in self.site_name.lower()

    async def _fetch_with_curl_cffi(self, params: dict) -> dict:
        """Makes a request using curl_cffi to bypass Cloudflare efficiently."""
        if not CURL_CFFI_AVAILABLE:
            return {}

        # Crée la session une seule fois
        if self._curl_session is None:
            self._curl_session = CurlAsyncSession(
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                }
            )

        try:
            accept_lang_map = {
                "fr": "fr-FR,fr;q=0.9,en;q=0.8",
                "en": "en-US,en;q=0.9",
                "es": "es-ES,es;q=0.9,en;q=0.8",
                "de": "de-DE,de;q=0.9,en;q=0.8",
            }
            accept_language = accept_lang_map.get(self.lang, "en-US,en;q=0.9")

            headers = {
                "Accept-Language": accept_language,
                "Referer": self.site_url,
                "DNT": "1",
            }

            resp = await self._curl_session.get(
                self.api_url,
                params=params,
                headers=headers,
                impersonate="chrome120",
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            logger.warning(f"curl_cffi request failed for {self.site_name}: {e}")
            return {}

    async def _fetch_with_aiohttp(self, params: dict) -> dict:
        """Makes a request using a persistent aiohttp session with a proper User-Agent."""
        session = await self._get_session()

        # Build Accept-Language header based on wiki language
        accept_lang_map = {
            "fr": "fr-FR,fr;q=0.9,en;q=0.8",
            "en": "en-US,en;q=0.9",
            "es": "es-ES,es;q=0.9,en;q=0.8",
            "de": "de-DE,de;q=0.9,en;q=0.8",
        }
        accept_language = accept_lang_map.get(self.lang, "en-US,en;q=0.9")

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": accept_language,
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": self.site_url,
            "DNT": "1",
            "Connection": "keep-alive",
        }

        try:
            async with session.get(
                self.api_url, params=params, headers=headers
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"HTTP error while searching wiki with aiohttp: {e}")
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
            "origin": "*",  # Required for CORS
        }

        use_cf_bypass = self._use_cloudflare_bypass()
        if use_cf_bypass:
            # Use curl_cffi for Cloudflare bypass (Vikidia)
            logger.debug(f"Using curl_cffi to bypass Cloudflare for {self.site_name}")
            data = await self._fetch_with_curl_cffi(params)

            # Fallback to aiohttp if curl_cffi failed
            if not data or "query" not in data:
                logger.info(
                    f"curl_cffi failed for {self.site_name}, falling back to aiohttp"
                )
                data = await self._fetch_with_aiohttp(params)
        else:
            logger.debug(f"Using aiohttp to search wiki: {self.site_name}")
            data = await self._fetch_with_aiohttp(params)

        if not data or "query" not in data or "search" not in data["query"]:
            return []

        results = []
        for item in data["query"]["search"]:
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

    async def get_page_data(
        self,
        page_title: str,
        include_extract: bool = True,
        include_thumbnail: bool = True,
        extract_sentences: int = 3,
        thumbnail_size: int = 300,
    ) -> dict:
        """
        Get detailed page data for a specific title.

        Args:
            page_title: The title of the page.
            include_extract: Whether to include the text extract.
            include_thumbnail: Whether to include the thumbnail image.
            extract_sentences: Number of sentences to include in extract.
            thumbnail_size: Thumbnail width in pixels.

        Returns:
            Dictionary with 'extract' and/or 'thumbnail' keys.
        """
        props = []
        if include_extract:
            props.append("extracts")
        if include_thumbnail:
            props.append("pageimages")

        params = {
            "action": "query",
            "format": "json",
            "prop": "|".join(props),
            "titles": page_title,
            "origin": "*",
        }

        if include_extract:
            params.update(
                {
                    "exintro": "1",  # Only intro section
                    "explaintext": "1",  # Plain text, no HTML
                    "exsentences": str(extract_sentences),
                }
            )

        if include_thumbnail:
            params.update({"piprop": "thumbnail", "pithumbsize": str(thumbnail_size)})

        # Use same bypass logic as search
        use_cf_bypass = self._use_cloudflare_bypass()
        if use_cf_bypass:
            # Use curl_cffi for Cloudflare bypass
            data = await self._fetch_with_curl_cffi(params)
            # Fallback to aiohttp
            if not data or "query" not in data:
                data = await self._fetch_with_aiohttp(params)
        else:
            data = await self._fetch_with_aiohttp(params)

        if not data or "query" not in data or "pages" not in data["query"]:
            return {}

        # Get first (and only) page from results
        pages = data["query"]["pages"]
        page = next(iter(pages.values()))

        result = {}
        if include_extract and "extract" in page:
            result["extract"] = page["extract"]
        if include_thumbnail and "thumbnail" in page:
            result["thumbnail"] = page["thumbnail"].get("source")

        return result

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        if self._curl_session:
            await self._curl_session.close()
        logger.info(f"Closed WikiClient session for {self.site_name}")
