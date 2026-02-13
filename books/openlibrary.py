"""
Open Library API client for fetching book metadata.

Open Library (openlibrary.org) is a free, open-source digital library with
comprehensive book metadata. No authentication required.

API Documentation: https://openlibrary.org/dev/docs/api/books
"""

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_RATE_LIMIT = 1.0  # 1 request per second (be respectful)
DEFAULT_CACHE_SIZE = 500


class OpenLibraryApi:
    """
    Client for interacting with the Open Library API.

    Handles rate limiting, caching, and data retrieval from Open Library endpoints.
    No authentication required.
    """

    BASE_URL = "https://openlibrary.org"
    COVERS_URL = "https://covers.openlibrary.org"

    def __init__(
        self,
        rate_limit: float = DEFAULT_RATE_LIMIT,
        cache_size: int = DEFAULT_CACHE_SIZE,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """
        Initialize the Open Library API client.

        Args:
            rate_limit: Minimum seconds between requests (default: 1.0)
            cache_size: Maximum number of items to cache (default: 500)
            timeout: Request timeout in seconds (default: 10.0)
        """
        self.timeout = timeout
        self.min_request_interval = rate_limit
        self.cache_max_size = cache_size

        # LRU caches
        self.work_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.edition_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
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
        self, url: str, max_retries: int = 3
    ) -> Optional[requests.Response]:
        """
        Make an API request with rate limiting and retry logic.

        Args:
            url: The API endpoint URL
            max_retries: Maximum number of retries on failure

        Returns:
            Response object if successful, None otherwise
        """
        retry_count = 0
        while retry_count <= max_retries:
            self._wait_for_rate_limit()
            try:
                response = requests.get(url, timeout=self.timeout)

                if response.status_code == 429:
                    if retry_count < max_retries:
                        wait_time = 2**retry_count
                        logger.warning(
                            "Rate limited by Open Library. Retrying in %d seconds...",
                            wait_time,
                        )
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        logger.error("Rate limited. Max retries exceeded.")
                        return None

                return response

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
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for books by title, author, or general query.

        Args:
            query: Search query string
            limit: Maximum number of results (default: 10)
            fields: Specific fields to return (default: common fields)

        Returns:
            List of book dictionaries with metadata
        """
        cache_key = f"search:{query}:{limit}"
        cached = self._get_from_cache(self.search_cache, cache_key)
        if cached is not None:
            return cached

        if fields is None:
            fields = [
                "key",
                "title",
                "author_name",
                "author_key",
                "first_publish_year",
                "isbn",
                "cover_i",
                "number_of_pages_median",
                "subject",
                "publisher",
                "language",
            ]

        encoded_query = quote(query)
        fields_param = ",".join(fields)
        url = (
            f"{self.BASE_URL}/search.json"
            f"?q={encoded_query}&limit={limit}&fields={fields_param}"
        )

        response = self._make_request(url)
        if response is None or response.status_code != 200:
            return []

        try:
            data = response.json()
            results = data.get("docs", [])
            self._set_in_cache(self.search_cache, cache_key, results)
            return results
        except (ValueError, KeyError) as exc:
            logger.warning("Failed to parse search results: %s", exc)
            return []

    def search_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Look up a book by ISBN.

        Args:
            isbn: ISBN-10 or ISBN-13

        Returns:
            Book metadata dictionary or None if not found
        """
        # Clean ISBN (remove hyphens)
        clean_isbn = isbn.replace("-", "").strip()

        cache_key = f"isbn:{clean_isbn}"
        cached = self._get_from_cache(self.edition_cache, cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/isbn/{clean_isbn}.json"
        response = self._make_request(url)

        if response is None or response.status_code != 200:
            return None

        try:
            data = response.json()
            self._set_in_cache(self.edition_cache, cache_key, data)
            return data
        except ValueError as exc:
            logger.warning("Failed to parse ISBN response: %s", exc)
            return None

    def get_work(self, work_id: str) -> Optional[Dict[str, Any]]:
        """
        Get work (logical book) details by Open Library work ID.

        Works represent the abstract concept of a book, while editions
        represent specific published versions.

        Args:
            work_id: Open Library work ID (e.g., "OL45804W")

        Returns:
            Work metadata dictionary or None if not found
        """
        # Normalize work_id
        if not work_id.startswith("/works/"):
            work_id = f"/works/{work_id}"

        cache_key = f"work:{work_id}"
        cached = self._get_from_cache(self.work_cache, cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}{work_id}.json"
        response = self._make_request(url)

        if response is None or response.status_code != 200:
            return None

        try:
            data = response.json()
            self._set_in_cache(self.work_cache, cache_key, data)
            return data
        except ValueError as exc:
            logger.warning("Failed to parse work response: %s", exc)
            return None

    def get_author(self, author_id: str) -> Optional[Dict[str, Any]]:
        """
        Get author details by Open Library author ID.

        Args:
            author_id: Open Library author ID (e.g., "OL23919A")

        Returns:
            Author metadata dictionary or None if not found
        """
        # Normalize author_id
        if not author_id.startswith("/authors/"):
            author_id = f"/authors/{author_id}"

        cache_key = f"author:{author_id}"
        cached = self._get_from_cache(self.author_cache, cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}{author_id}.json"
        response = self._make_request(url)

        if response is None or response.status_code != 200:
            return None

        try:
            data = response.json()
            self._set_in_cache(self.author_cache, cache_key, data)
            return data
        except ValueError as exc:
            logger.warning("Failed to parse author response: %s", exc)
            return None

    def get_cover_url(
        self,
        cover_id: int,
        size: str = "M",
        id_type: str = "id",
    ) -> str:
        """
        Get the URL for a book cover image.

        Args:
            cover_id: Cover ID, ISBN, OLID, etc.
            size: Size - "S" (small), "M" (medium), "L" (large)
            id_type: Type of ID - "id", "isbn", "olid", "oclc", "lccn"

        Returns:
            URL string for the cover image
        """
        return f"{self.COVERS_URL}/b/{id_type}/{cover_id}-{size}.jpg"

    def get_book_info(
        self, title: str, author: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for a book and return comprehensive metadata.

        This is a convenience method that searches by title/author and
        enriches the result with additional data.

        Args:
            title: Book title
            author: Optional author name

        Returns:
            Dictionary with comprehensive book metadata:
                - title: Book title
                - authors: List of author names
                - author_keys: List of Open Library author IDs
                - first_publish_year: Year of first publication
                - isbn: List of ISBNs
                - cover_url: URL to cover image (medium size)
                - subjects: List of subjects/genres
                - publishers: List of publishers
                - work_key: Open Library work ID
                - description: Book description (if available)
        """
        # Build search query
        query = title
        if author:
            query = f"{title} {author}"

        results = self.search_books(query, limit=5)

        if not results:
            return None

        # Find best match using scoring
        best_match = None
        best_score = 0
        title_lower = title.lower()
        author_lower = author.lower() if author else None

        for result in results:
            score = 0
            result_title = result.get("title", "").lower()
            result_authors = [a.lower() for a in result.get("author_name", [])]

            # Author match is most important when specified
            if author_lower and result_authors:
                for result_author in result_authors:
                    if author_lower in result_author or result_author in author_lower:
                        score += 100
                        break

            # Exact title match
            if result_title == title_lower:
                score += 50
            # Title starts with our search (stronger than general contains)
            elif result_title.startswith(title_lower):
                score += 40
            # Title contains our search
            elif title_lower in result_title:
                score += 30

            # Prefer older publications (likely the original)
            pub_year = result.get("first_publish_year")
            if pub_year and pub_year < 2000:
                score += 10

            if score > best_score:
                best_score = score
                best_match = result

        if best_match is None:
            best_match = results[0]

        # Build comprehensive result
        cover_id = best_match.get("cover_i")
        work_key = best_match.get("key", "")

        book_info = {
            "title": best_match.get("title"),
            "authors": best_match.get("author_name", []),
            "author_keys": best_match.get("author_key", []),
            "first_publish_year": best_match.get("first_publish_year"),
            "isbn": best_match.get("isbn", []),
            "cover_url": self.get_cover_url(cover_id) if cover_id else None,
            "cover_id": cover_id,
            "subjects": best_match.get("subject", []),
            "publishers": best_match.get("publisher", []),
            "work_key": work_key,
            "number_of_pages": best_match.get("number_of_pages_median"),
            "languages": best_match.get("language", []),
        }

        # Try to get description from work
        if work_key:
            work_data = self.get_work(work_key)
            if work_data:
                description = work_data.get("description")
                if isinstance(description, dict):
                    description = description.get("value", "")
                book_info["description"] = description

        return book_info


def get_api(
    rate_limit: float = DEFAULT_RATE_LIMIT,
    cache_size: int = DEFAULT_CACHE_SIZE,
) -> OpenLibraryApi:
    """
    Create and return an Open Library API client instance.

    Args:
        rate_limit: Minimum seconds between requests
        cache_size: Maximum number of items to cache

    Returns:
        Configured OpenLibraryApi client
    """
    return OpenLibraryApi(rate_limit=rate_limit, cache_size=cache_size)
