"""
Wikipedia page lookup service.

Finds Wikipedia pages for games using Wikidata IDs as the primary method,
with fallback to OpenSearch API. This is separate from genre scraping.
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
import threading

import requests
from django.conf import settings

from games import config
from games.services.wiki_genre_service import WikiGenreService

logger = logging.getLogger(__name__)


@dataclass
class PageLookupResult:
    """Result of Wikipedia page lookup for a single game."""

    game_name: str
    page_title: Optional[str] = None
    lookup_source: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def success(self) -> bool:
        """Returns True if page was found."""
        return self.page_title is not None

    @property
    def wikipedia_url(self) -> Optional[str]:
        """Construct Wikipedia URL from page title."""
        if not self.page_title:
            return None
        return f"https://en.wikipedia.org/wiki/{self.page_title.replace(' ', '_')}"


class WikiPageLookupService:
    """
    Service for finding Wikipedia pages for video games.

    Uses a two-tier approach:
    1. Primary: Wikidata API (fast, reliable when wikidata_id exists)
    2. Fallback: OpenSearch API (slower, more comprehensive)

    Supports optional authentication for 10x faster rate limits.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        delay: Optional[float] = None,
        user_agent: str = config.WIKI_USER_AGENT,
        progress_callback: Optional[Callable[[str, Dict], None]] = None,
    ):
        """
        Initialize the Wikipedia page lookup service.

        Args:
            access_token: Optional Wikimedia Bot Password for authenticated requests
            delay: Override delay between requests (default: based on auth status)
            user_agent: User-Agent header for Wikimedia API compliance
            progress_callback: Optional callback for progress updates
        """
        self.access_token = access_token or settings.WIKIDATA_ACCESS_TOKEN
        self.user_agent = user_agent
        self.progress_callback = progress_callback

        # Set rate limit delay based on authentication
        if delay is not None:
            self.delay = delay
        elif self.access_token:
            self.delay = config.WIKIDATA_AUTHENTICATED_DELAY
            logger.info(
                "Using authenticated Wikidata requests (%.2fs delay)", self.delay
            )
        else:
            self.delay = config.WIKIDATA_UNAUTHENTICATED_DELAY
            logger.info(
                "Using unauthenticated Wikidata requests (%.2fs delay)", self.delay
            )

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        # Rate limiting state (thread-safe)
        self.last_request_time: float = 0.0
        self.rate_limit_lock = threading.Lock()

        # Create WikiGenreService for fallback OpenSearch
        # Use same delay for consistency
        self.wiki_genre_service = WikiGenreService(
            delay=config.WIKI_REQUEST_DELAY,  # Use Wikipedia delay for OpenSearch
            user_agent=self.user_agent,
        )

    def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting between requests (thread-safe)."""
        with self.rate_limit_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                sleep_time = self.delay - elapsed
                time.sleep(sleep_time)
            self.last_request_time = time.time()

    def _make_request(
        self, url: str, params: Optional[Dict] = None, use_auth: bool = False
    ) -> Optional[requests.Response]:
        """
        Make rate-limited request with error handling and retry logic.

        Args:
            url: URL to fetch
            params: Optional query parameters
            use_auth: Whether to add authentication headers

        Returns:
            Response object, or None on error
        """
        max_retries = 3
        retry_delay = 1.0  # Start with 1 second

        for attempt in range(max_retries):
            self._wait_for_rate_limit()

            headers = {}
            if use_auth and self.access_token:
                # Wikimedia Bot Password format: username@botname:password
                # Use HTTP Basic Auth
                auth = (
                    tuple(self.access_token.split(":", 1))
                    if ":" in self.access_token
                    else None
                )
                if not auth:
                    logger.warning(
                        "Invalid token format, falling back to unauthenticated"
                    )
            else:
                auth = None

            try:
                response = self.session.get(
                    url, params=params, headers=headers, auth=auth, timeout=30
                )
                response.raise_for_status()
                return response
            except (
                requests.ConnectionError,
                requests.Timeout,
                requests.exceptions.ChunkedEncodingError,
            ) as e:
                # Transient errors - retry with backoff
                if attempt < max_retries - 1:
                    logger.warning(
                        "Connection error on attempt %d/%d: %s. Retrying in %.1fs...",
                        attempt + 1,
                        max_retries,
                        e,
                        retry_delay,
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("Request failed after %d attempts: %s", max_retries, e)
                    return None
            except requests.RequestException as e:
                # Non-transient errors - don't retry
                logger.warning("Request failed (non-retryable): %s", e)
                return None

        return None

    def _lookup_via_wikidata(self, wikidata_id: str) -> Optional[str]:
        """
        Look up English Wikipedia page title via Wikidata API.

        Args:
            wikidata_id: Wikidata ID (e.g., "Q12345")

        Returns:
            Wikipedia page title, or None if not found
        """
        if not wikidata_id:
            return None

        params = {
            "action": "wbgetentities",
            "format": "json",
            "props": "sitelinks",
            "ids": wikidata_id,
            "sitefilter": "enwiki",
        }

        response = self._make_request(
            config.WIKIDATA_API_URL, params=params, use_auth=True
        )
        if not response:
            return None

        try:
            data = response.json()
            # Extract enwiki sitelink
            entities = data.get("entities", {})
            entity = entities.get(wikidata_id, {})
            sitelinks = entity.get("sitelinks", {})
            enwiki = sitelinks.get("enwiki", {})
            page_title = enwiki.get("title")

            if page_title:
                logger.debug(
                    "Found Wikipedia page via Wikidata: %s -> %s",
                    wikidata_id,
                    page_title,
                )
                return page_title
            else:
                logger.debug("No enwiki sitelink for %s", wikidata_id)
                return None

        except (ValueError, KeyError) as e:
            logger.warning(
                "Failed to parse Wikidata response for %s: %s", wikidata_id, e
            )
            return None

    def _lookup_via_opensearch(
        self, game_name: str, year: Optional[int] = None
    ) -> Optional[tuple[str, str]]:
        """
        Look up Wikipedia page via OpenSearch API (fallback method).

        Uses WikiGenreService's comprehensive search logic.

        Args:
            game_name: Name of the video game
            year: Optional year of release for disambiguation

        Returns:
            Tuple of (page_title, source) or None if not found
            source is one of: opensearch_year, opensearch_basic, opensearch_fallback
        """
        # Use WikiGenreService's search method
        url = self.wiki_genre_service._search_wikipedia(game_name, year)

        if url:
            # Extract page title from URL
            # URL format: https://en.wikipedia.org/wiki/Page_Title
            if "/wiki/" in url:
                page_title = url.split("/wiki/")[1]
                # Decode URL encoding and replace underscores with spaces
                import urllib.parse

                page_title = urllib.parse.unquote(page_title).replace("_", " ")

                # Determine source based on search success
                # This is approximate - WikiGenreService doesn't expose
                # which variant succeeded
                if year:
                    source = config.WIKI_LOOKUP_SOURCE_OPENSEARCH_YEAR
                else:
                    source = config.WIKI_LOOKUP_SOURCE_OPENSEARCH_BASIC

                logger.debug(
                    "Found Wikipedia page via OpenSearch: %s -> %s",
                    game_name,
                    page_title,
                )
                return (page_title, source)

        return None

    def lookup_page(
        self,
        game_name: str,
        wikidata_id: Optional[str] = None,
        year: Optional[int] = None,
    ) -> PageLookupResult:
        """
        Look up Wikipedia page for a game.

        Tries multiple strategies in order:
        1. Wikidata API (if wikidata_id provided)
        2. OpenSearch with year
        3. OpenSearch without year

        Args:
            game_name: Name of the video game
            wikidata_id: Optional Wikidata ID
            year: Optional year of release

        Returns:
            PageLookupResult with page title and source
        """
        # Try Wikidata first
        if wikidata_id:
            page_title = self._lookup_via_wikidata(wikidata_id)
            if page_title:
                return PageLookupResult(
                    game_name=game_name,
                    page_title=page_title,
                    lookup_source=config.WIKI_LOOKUP_SOURCE_WIKIDATA,
                )

        # Try OpenSearch with year
        if year:
            result = self._lookup_via_opensearch(game_name, year)
            if result:
                page_title, source = result
                return PageLookupResult(
                    game_name=game_name,
                    page_title=page_title,
                    lookup_source=source,
                )

        # Try OpenSearch without year
        result = self._lookup_via_opensearch(game_name, year=None)
        if result:
            page_title, source = result
            return PageLookupResult(
                game_name=game_name,
                page_title=page_title,
                lookup_source=config.WIKI_LOOKUP_SOURCE_OPENSEARCH_FALLBACK,
            )

        # All methods failed
        return PageLookupResult(
            game_name=game_name,
            error_message="Page not found on Wikipedia",
        )

    def process_games(
        self, games: List[tuple]
    ) -> tuple[List[PageLookupResult], int, int]:
        """
        Process multiple games and return results.

        Args:
            games: List of (name, wikidata_id, year) tuples

        Returns:
            Tuple of (results list, success count, failure count)
        """
        results = []
        success_count = 0
        failure_count = 0
        total = len(games)

        self._notify_progress("start", {"total": total})

        for idx, (game_name, wikidata_id, year) in enumerate(games, start=1):
            result = self.lookup_page(game_name, wikidata_id, year)
            results.append(result)

            if result.success:
                success_count += 1
                self._notify_progress(
                    "progress",
                    {
                        "current": idx,
                        "total": total,
                        "game_name": game_name,
                        "page_title": result.page_title,
                        "lookup_source": result.lookup_source,
                    },
                )
            else:
                failure_count += 1
                self._notify_progress(
                    "error",
                    {
                        "current": idx,
                        "total": total,
                        "game_name": game_name,
                        "message": result.error_message,
                    },
                )

        self._notify_progress(
            "complete",
            {
                "total": total,
                "success": success_count,
                "failures": failure_count,
            },
        )

        return (results, success_count, failure_count)

    def _notify_progress(self, event_type: str, data: Dict) -> None:
        """Call progress callback if provided."""
        if self.progress_callback:
            self.progress_callback(event_type, data)
