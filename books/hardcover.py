"""
Hardcover GraphQL API client for fetching book metadata.

Hardcover (hardcover.app) is a modern book tracking platform with a
comprehensive GraphQL API. Requires API token for authentication.

API Documentation: https://docs.hardcover.app/api/getting-started/
"""

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_REQUEST_TIMEOUT = 30.0
DEFAULT_RATE_LIMIT = 1.0  # 60 requests/minute = 1 per second
DEFAULT_CACHE_SIZE = 500


class HardcoverApi:
    """
    Client for interacting with the Hardcover GraphQL API.

    Handles authentication, rate limiting, caching, and data retrieval.
    Requires API token from https://hardcover.app/account/api
    """

    ENDPOINT = "https://api.hardcover.app/v1/graphql"

    def __init__(
        self,
        api_token: str,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        cache_size: int = DEFAULT_CACHE_SIZE,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """
        Initialize the Hardcover API client.

        Args:
            api_token: Hardcover API token from account settings
            rate_limit: Minimum seconds between requests (default: 1.0)
            cache_size: Maximum number of items to cache (default: 500)
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.api_token = api_token
        self.timeout = timeout
        self.min_request_interval = rate_limit
        self.cache_max_size = cache_size

        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        # LRU caches
        self.book_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.author_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.search_cache: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()

        # Thread safety
        self.rate_limit_lock = threading.Lock()
        self.cache_lock = threading.Lock()
        self.last_request_time = 0.0

    def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting by sleeping if necessary."""
        with self.rate_limit_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
            self.last_request_time = time.time()

    def _get_from_cache(self, cache: OrderedDict, key: str) -> Optional[Any]:
        """Get item from cache with LRU update."""
        with self.cache_lock:
            if key in cache:
                value = cache.pop(key)
                cache[key] = value
                return value
        return None

    def _set_in_cache(self, cache: OrderedDict, key: str, value: Any) -> None:
        """Set item in cache with LRU eviction."""
        with self.cache_lock:
            if key in cache:
                cache.pop(key)
            elif len(cache) >= self.cache_max_size:
                cache.popitem(last=False)
            cache[key] = value

    def _make_request(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        Make a GraphQL request with rate limiting and retry logic.

        Args:
            query: GraphQL query string
            variables: Optional query variables
            max_retries: Maximum number of retries on failure

        Returns:
            Response data dictionary if successful, None otherwise
        """
        retry_count = 0
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        while retry_count <= max_retries:
            self._wait_for_rate_limit()
            try:
                response = requests.post(
                    self.ENDPOINT,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout,
                )

                if response.status_code == 429:
                    if retry_count < max_retries:
                        wait_time = 2**retry_count
                        logger.warning(
                            "Rate limited by Hardcover. Retrying in %d seconds...",
                            wait_time,
                        )
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        logger.error("Rate limited. Max retries exceeded.")
                        return None

                if response.status_code != 200:
                    logger.warning(
                        "Hardcover API error: %d - %s",
                        response.status_code,
                        response.text[:200],
                    )
                    return None

                data = response.json()
                if "errors" in data:
                    logger.warning("GraphQL errors: %s", data["errors"])
                    return None

                return data.get("data")

            except requests.RequestException as exc:
                logger.warning("Request failed: %s", exc)
                if retry_count < max_retries:
                    retry_count += 1
                    time.sleep(1)
                    continue
                return None

        return None

    def search_books(
        self,
        query: str,
        limit: int = 10,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Search for books by title, author, or ISBN.

        Args:
            query: Search query string
            limit: Maximum number of results (default: 10)
            page: Page number (default: 1)

        Returns:
            List of book dictionaries with metadata
        """
        cache_key = f"search:{query}:{limit}:{page}"
        cached = self._get_from_cache(self.search_cache, cache_key)
        if cached is not None:
            return cached

        graphql_query = """
        query SearchBooks($query: String!, $perPage: Int!, $page: Int!) {
            search(
                query: $query,
                query_type: "Book",
                per_page: $perPage,
                page: $page
            ) {
                results
            }
        }
        """

        variables = {
            "query": query,
            "perPage": limit,
            "page": page,
        }

        data = self._make_request(graphql_query, variables)
        if data is None:
            return []

        try:
            # The results field contains JSON string or list
            results = data.get("search", {}).get("results", [])
            if isinstance(results, str):
                import json

                results = json.loads(results)

            self._set_in_cache(self.search_cache, cache_key, results)
            return results
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse search results: %s", exc)
            return []

    def get_book_by_id(self, book_id: int) -> Optional[Dict[str, Any]]:
        """
        Get book details by Hardcover book ID.

        Args:
            book_id: Hardcover book ID

        Returns:
            Book metadata dictionary or None if not found
        """
        cache_key = f"book:{book_id}"
        cached = self._get_from_cache(self.book_cache, cache_key)
        if cached is not None:
            return cached

        graphql_query = """
        query GetBook($id: Int!) {
            books(where: {id: {_eq: $id}}) {
                id
                title
                slug
                description
                release_date
                pages
                cached_contributors
                cached_tags
                cached_image
                editions {
                    isbn_13
                    isbn_10
                    pages
                    audio_seconds
                }
            }
        }
        """

        variables = {"id": book_id}
        data = self._make_request(graphql_query, variables)

        if data is None:
            return None

        try:
            books = data.get("books", [])
            if not books:
                return None

            book = books[0]
            self._set_in_cache(self.book_cache, cache_key, book)
            return book
        except (ValueError, KeyError) as exc:
            logger.warning("Failed to parse book response: %s", exc)
            return None

    def get_book_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Look up a book by ISBN.

        Args:
            isbn: ISBN-10 or ISBN-13

        Returns:
            Book metadata dictionary or None if not found
        """
        # Clean ISBN
        clean_isbn = isbn.replace("-", "").strip()

        cache_key = f"isbn:{clean_isbn}"
        cached = self._get_from_cache(self.book_cache, cache_key)
        if cached is not None:
            return cached

        # Search by ISBN
        results = self.search_books(clean_isbn, limit=1)
        if results:
            book = results[0]
            self._set_in_cache(self.book_cache, cache_key, book)
            return book

        return None

    def get_book_info(
        self, title: str, author: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for a book and return comprehensive metadata.

        Args:
            title: Book title
            author: Optional author name

        Returns:
            Dictionary with comprehensive book metadata:
                - title: Book title
                - authors: List of author names
                - year: Publication year
                - isbn: List of ISBNs
                - cover_url: URL to cover image
                - genres: List of genres/tags
                - description: Book description
                - pages: Page count
                - hardcover_id: Hardcover book ID
                - slug: URL-friendly identifier
        """
        query = title
        if author:
            query = f"{title} {author}"

        results = self.search_books(query, limit=5)

        if not results:
            return None

        # Find best match
        best_match = None
        title_lower = title.lower()

        for result in results:
            result_title = (result.get("title") or "").lower()
            if result_title == title_lower:
                best_match = result
                break
            if result_title.startswith(title_lower):
                if best_match is None:
                    best_match = result

        if best_match is None:
            best_match = results[0]

        # Extract and normalize data
        contributors = best_match.get("cached_contributors") or []
        authors = []
        for contrib in contributors:
            if isinstance(contrib, dict):
                name = contrib.get("name") or contrib.get("author", {}).get("name")
                if name:
                    authors.append(name)
            elif isinstance(contrib, str):
                authors.append(contrib)

        tags = best_match.get("cached_tags") or []
        genres = []
        for tag in tags:
            if isinstance(tag, dict):
                genres.append(tag.get("tag") or tag.get("name", ""))
            elif isinstance(tag, str):
                genres.append(tag)

        # Get ISBNs from editions if available
        isbns = []
        editions = best_match.get("editions") or []
        for edition in editions:
            if isinstance(edition, dict):
                if edition.get("isbn_13"):
                    isbns.append(edition["isbn_13"])
                if edition.get("isbn_10"):
                    isbns.append(edition["isbn_10"])

        # Parse release date
        year = None
        release_date = best_match.get("release_date")
        if release_date:
            try:
                year = int(str(release_date)[:4])
            except (ValueError, TypeError):
                pass

        return {
            "title": best_match.get("title"),
            "authors": authors,
            "year": year,
            "isbn": isbns,
            "cover_url": best_match.get("cached_image"),
            "genres": genres,
            "description": best_match.get("description"),
            "pages": best_match.get("pages"),
            "hardcover_id": best_match.get("id"),
            "slug": best_match.get("slug"),
        }


def get_api(
    api_token: Optional[str] = None,
    rate_limit: float = DEFAULT_RATE_LIMIT,
    cache_size: int = DEFAULT_CACHE_SIZE,
) -> Optional[HardcoverApi]:
    """
    Create and return a Hardcover API client instance.

    Args:
        api_token: Hardcover API token. If None, reads from settings.
        rate_limit: Minimum seconds between requests
        cache_size: Maximum number of items to cache

    Returns:
        Configured HardcoverApi client, or None if no token available
    """
    if api_token is None:
        api_token = getattr(settings, "HARDCOVER_API_TOKEN", None)

    if not api_token:
        logger.debug(
            "Hardcover API token not configured. "
            "Set HARDCOVER_API_TOKEN in settings or environment."
        )
        return None

    return HardcoverApi(
        api_token=api_token,
        rate_limit=rate_limit,
        cache_size=cache_size,
    )
