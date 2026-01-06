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
    hltb_id: Optional[str] = None  # HowLongToBeat ID from Wikidata P2816
    steam_app_id: Optional[str] = None  # Steam AppID from Wikidata P1733
    wikiquote_page_title: Optional[str] = (
        None  # Wikiquote page from enwikiquote sitelink
    )

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

    def _fetch_wikidata_label(self, qid: str) -> Optional[str]:
        """
        Fetch the English label for a Wikidata entity.

        Args:
            qid: Wikidata Q-ID (e.g., "Q208850")

        Returns:
            English label string, or None if not found
        """
        params = {
            "action": "wbgetentities",
            "format": "json",
            "props": "labels",
            "ids": qid,
            "languages": "en",
        }

        response = self._make_request(
            config.WIKIDATA_API_URL, params=params, use_auth=True
        )
        if not response:
            return None

        try:
            data = response.json()
            entities = data.get("entities", {})
            entity = entities.get(qid, {})
            labels = entity.get("labels", {})
            en_label = labels.get("en", {})
            return en_label.get("value")
        except (ValueError, KeyError) as e:
            logger.warning("Failed to parse Wikidata label for %s: %s", qid, e)
            return None

    def _get_wikidata_id_from_page(self, page_title: str) -> Optional[str]:
        """
        Look up the Wikidata Q-ID for a Wikipedia page title.

        Args:
            page_title: Wikipedia page title (e.g., "The Jackbox Party Pack")

        Returns:
            Wikidata Q-ID (e.g., "Q31638338"), or None if not found
        """
        if not page_title:
            return None

        # Convert spaces to underscores for the API
        normalized_title = page_title.replace(" ", "_")

        params = {
            "action": "wbgetentities",
            "format": "json",
            "sites": "enwiki",
            "titles": normalized_title,
            "props": "info",  # Minimal props, we just need the Q-ID
        }

        response = self._make_request(
            config.WIKIDATA_API_URL, params=params, use_auth=True
        )
        if not response:
            return None

        try:
            data = response.json()
            entities = data.get("entities", {})
            # The response uses the Q-ID as key, or "-1" if not found
            for qid, entity in entities.items():
                if qid.startswith("Q"):
                    logger.debug(
                        "Found Wikidata ID for page '%s': %s", page_title, qid
                    )
                    return qid
            return None
        except (ValueError, KeyError) as e:
            logger.warning(
                "Failed to get Wikidata ID for page '%s': %s", page_title, e
            )
            return None

    def _lookup_via_wikidata(self, wikidata_id: str) -> Optional[
        tuple[
            str,
            Optional[str],
            Optional[str],
            Optional[str],
        ]
    ]:
        """
        Look up Wikipedia/Wikiquote page titles and metadata via Wikidata API.

        Args:
            wikidata_id: Wikidata ID (e.g., "Q12345")

        Returns:
            Tuple of (page_title, hltb_id, steam_app_id, wikiquote_title),
            or None if not found.
            page_title may be None if no enwiki sitelink exists.
        """
        if not wikidata_id:
            return None

        params = {
            "action": "wbgetentities",
            "format": "json",
            "props": "sitelinks|claims",
            "ids": wikidata_id,
            "sitefilter": "enwiki|enwikiquote",
        }

        response = self._make_request(
            config.WIKIDATA_API_URL, params=params, use_auth=True
        )
        if not response:
            return None

        try:
            data = response.json()
            # Extract entity data
            entities = data.get("entities", {})
            entity = entities.get(wikidata_id, {})

            # Extract enwiki sitelink
            sitelinks = entity.get("sitelinks", {})
            enwiki = sitelinks.get("enwiki", {})
            page_title = enwiki.get("title")

            # Extract enwikiquote sitelink
            enwikiquote = sitelinks.get("enwikiquote", {})
            wikiquote_title = enwikiquote.get("title")

            claims = entity.get("claims", {})

            # Extract HLTB ID from P2816 claim (HowLongToBeat ID property)
            # Filter out deprecated claims and prefer "preferred" rank over "normal"
            hltb_id = None
            p2816 = claims.get("P2816", [])
            if p2816:
                # Filter out deprecated claims and sort by rank preference
                valid_claims = []
                for claim in p2816:
                    rank = claim.get("rank", "normal")
                    if rank != "deprecated":
                        valid_claims.append((claim, rank))

                if valid_claims:
                    # Sort by rank preference (preferred first, then normal)
                    valid_claims.sort(key=lambda x: 0 if x[1] == "preferred" else 1)
                    best_claim = valid_claims[0][0]
                    mainsnak = best_claim.get("mainsnak", {})
                    datavalue = mainsnak.get("datavalue", {})
                    hltb_id = datavalue.get("value")
                    if hltb_id:
                        logger.debug(
                            "Found HLTB ID via Wikidata P2816: %s -> %s",
                            wikidata_id,
                            hltb_id,
                        )

            # Extract Steam AppID from P1733 claim
            # Filter out deprecated claims and prefer "preferred" rank over "normal"
            steam_app_id = None
            p1733 = claims.get("P1733", [])
            if p1733:
                # Filter out deprecated claims and sort by rank preference
                valid_claims = []
                for claim in p1733:
                    rank = claim.get("rank", "normal")
                    if rank != "deprecated":
                        valid_claims.append((claim, rank))

                if valid_claims:
                    # Sort by rank preference (preferred first, then normal)
                    valid_claims.sort(key=lambda x: 0 if x[1] == "preferred" else 1)
                    best_claim = valid_claims[0][0]
                    mainsnak = best_claim.get("mainsnak", {})
                    datavalue = mainsnak.get("datavalue", {})
                    steam_app_id = datavalue.get("value")
                    if steam_app_id:
                        logger.debug(
                            "Found Steam AppID via Wikidata P1733: %s -> %s",
                            wikidata_id,
                            steam_app_id,
                        )

            if page_title:
                logger.debug(
                    "Found Wikipedia page via Wikidata: %s -> %s",
                    wikidata_id,
                    page_title,
                )
            else:
                logger.debug("No enwiki sitelink for %s", wikidata_id)

            # Return metadata even without enwiki sitelink
            # (page_title may be None, but we still want HLTB ID, etc.)
            return (
                page_title,
                hltb_id,
                steam_app_id,
                wikiquote_title,
            )

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

    def _merge_wikidata_metadata(
        self,
        primary: Optional[Dict],
        secondary: Optional[Dict],
    ) -> Dict:
        """
        Merge metadata from two Wikidata sources.

        Primary values take precedence when both have the same field.

        Args:
            primary: Metadata from primary Wikidata ID (stored on game)
            secondary: Metadata from secondary Wikidata ID (from Wikipedia page)

        Returns:
            Merged metadata dict
        """
        if not primary and not secondary:
            return {}
        if not primary:
            return secondary or {}
        if not secondary:
            return primary

        merged = {}
        all_keys = set(primary.keys()) | set(secondary.keys())

        for key in all_keys:
            primary_val = primary.get(key)
            secondary_val = secondary.get(key)
            # Primary takes precedence
            merged[key] = primary_val if primary_val else secondary_val

        return merged

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

        When using OpenSearch, also looks up the page's Wikidata ID to get
        additional metadata, then merges with the stored wikidata_id's metadata.

        Args:
            game_name: Name of the video game
            wikidata_id: Optional Wikidata ID (stored on game)
            year: Optional year of release

        Returns:
            PageLookupResult with page title and source
        """
        # Get metadata from stored wikidata_id (if any)
        stored_metadata = None
        stored_page_title = None
        if wikidata_id:
            wikidata_result = self._lookup_via_wikidata(wikidata_id)
            if wikidata_result:
                (
                    stored_page_title,
                    hltb_id,
                    steam_app_id,
                    wikiquote_title,
                ) = wikidata_result

                stored_metadata = {
                    "hltb_id": hltb_id,
                    "steam_app_id": steam_app_id,
                    "wikiquote_page_title": wikiquote_title,
                }

                # If stored Wikidata has enwiki sitelink, use it directly
                if stored_page_title:
                    return PageLookupResult(
                        game_name=game_name,
                        page_title=stored_page_title,
                        lookup_source=config.WIKI_LOOKUP_SOURCE_WIKIDATA,
                        **{k: v for k, v in stored_metadata.items() if v},
                    )

        # Try OpenSearch to find the Wikipedia page
        opensearch_result = None
        if year:
            opensearch_result = self._lookup_via_opensearch(game_name, year)

        if not opensearch_result:
            opensearch_result = self._lookup_via_opensearch(game_name, year=None)

        if opensearch_result:
            page_title, source = opensearch_result
            if not year:
                source = config.WIKI_LOOKUP_SOURCE_OPENSEARCH_FALLBACK

            # Look up the page's Wikidata ID to get additional metadata
            page_wikidata_id = self._get_wikidata_id_from_page(page_title)
            page_metadata = None

            if page_wikidata_id and page_wikidata_id != wikidata_id:
                # Different Wikidata ID - get its metadata too
                page_result = self._lookup_via_wikidata(page_wikidata_id)
                if page_result:
                    (
                        _,  # page_title already known
                        hltb_id,
                        steam_app_id,
                        wikiquote_title,
                    ) = page_result
                    page_metadata = {
                        "hltb_id": hltb_id,
                        "steam_app_id": steam_app_id,
                        "wikiquote_page_title": wikiquote_title,
                    }
                    logger.info(
                        "Merging metadata from two Wikidata IDs for %s: %s (stored) + %s (page)",
                        game_name,
                        wikidata_id,
                        page_wikidata_id,
                    )

            # Merge metadata from both sources (stored takes precedence)
            merged_metadata = self._merge_wikidata_metadata(
                stored_metadata, page_metadata
            )

            return PageLookupResult(
                game_name=game_name,
                page_title=page_title,
                lookup_source=source,
                **{k: v for k, v in merged_metadata.items() if v},
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
