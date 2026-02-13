"""
Unified book metadata service that combines multiple data sources.

This module provides a single interface for fetching book metadata from:
- Open Library (free, no authentication required) - Primary
- Hardcover (requires API token) - Optional, used when configured

Note: GoodReads API was deprecated in December 2020 and is no longer available.
This implementation uses Open Library as the primary source (equivalent to
the original "GoodReads integration" task).

Sources researched and considered:
- GoodReads: API shutdown December 2020 (https://www.goodreads.com/api)
- Open Library: Free, comprehensive, no auth (https://openlibrary.org/dev/docs/api)
- Hardcover: GraphQL API, requires token (https://docs.hardcover.app/api)
- Google Books API: Good coverage but limited metadata
- ISBNdb: Paid service
"""

import logging
from typing import Any, Dict, List, Optional

from books import openlibrary, hardcover

logger = logging.getLogger(__name__)


class BookMetadataService:
    """
    Unified service for fetching book metadata from multiple sources.

    Uses Open Library as the primary source (free, no auth required).
    Falls back to or supplements with Hardcover if configured.
    """

    def __init__(
        self,
        use_hardcover: bool = True,
        hardcover_token: Optional[str] = None,
        rate_limit: float = 1.0,
    ):
        """
        Initialize the book metadata service.

        Args:
            use_hardcover: Whether to try Hardcover API when available
            hardcover_token: Optional Hardcover API token
            rate_limit: Minimum seconds between requests per source
        """
        self.rate_limit = rate_limit
        self.use_hardcover = use_hardcover

        # Initialize Open Library (always available)
        self._openlibrary_api = None

        # Initialize Hardcover (optional)
        self._hardcover_api = None
        if use_hardcover:
            self._hardcover_api = hardcover.get_api(
                api_token=hardcover_token,
                rate_limit=rate_limit,
            )

    @property
    def openlibrary_api(self):
        """Lazy-initialize Open Library API client."""
        if self._openlibrary_api is None:
            self._openlibrary_api = openlibrary.get_api(rate_limit=self.rate_limit)
        return self._openlibrary_api

    @property
    def hardcover_available(self) -> bool:
        """Check if Hardcover API is configured and available."""
        return self._hardcover_api is not None

    def get_book_info(
        self,
        title: str,
        author: Optional[str] = None,
        isbn: Optional[str] = None,
        prefer_source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive book metadata.

        Tries multiple sources and combines results for best coverage.

        Args:
            title: Book title
            author: Optional author name for better matching
            isbn: Optional ISBN for precise lookup
            prefer_source: "openlibrary" or "hardcover" to prefer a source

        Returns:
            Dictionary with normalized book metadata:
                - title: Book title
                - authors: List of author names
                - year: Publication year
                - isbn: List of ISBNs
                - cover_url: URL to cover image
                - genres: List of genres/subjects
                - description: Book description
                - pages: Page count
                - source: Which source provided the data
                - source_ids: Dict of IDs from each source
        """
        result = None

        # Try ISBN lookup first if provided
        if isbn:
            result = self._lookup_by_isbn(isbn)
            if result:
                return result

        # Determine source order
        sources = self._get_source_order(prefer_source)

        # Try each source
        for source in sources:
            try:
                if source == "hardcover" and self._hardcover_api:
                    result = self._hardcover_api.get_book_info(title, author)
                    if result:
                        result["source"] = "hardcover"
                        result["source_ids"] = {
                            "hardcover_id": result.get("hardcover_id")
                        }
                        # Normalize field names
                        result = self._normalize_hardcover_result(result)
                        return result

                elif source == "openlibrary":
                    result = self.openlibrary_api.get_book_info(title, author)
                    if result:
                        result["source"] = "openlibrary"
                        result["source_ids"] = {"work_key": result.get("work_key")}
                        # Normalize field names
                        result = self._normalize_openlibrary_result(result)
                        return result

            except Exception as exc:
                logger.warning("Error fetching from %s: %s", source, exc)
                continue

        return None

    def _lookup_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Look up book by ISBN from available sources."""
        # Try Open Library first (free)
        try:
            result = self.openlibrary_api.search_by_isbn(isbn)
            if result:
                # Get more details via work lookup
                work_key = result.get("works", [{}])[0].get("key")
                if work_key:
                    work_data = self.openlibrary_api.get_work(work_key)
                    if work_data:
                        return self._normalize_openlibrary_work(result, work_data, isbn)
        except Exception as exc:
            logger.debug("Open Library ISBN lookup failed: %s", exc)

        # Try Hardcover if available
        if self._hardcover_api:
            try:
                result = self._hardcover_api.get_book_by_isbn(isbn)
                if result:
                    normalized = self._normalize_hardcover_result(result)
                    normalized["source"] = "hardcover"
                    return normalized
            except Exception as exc:
                logger.debug("Hardcover ISBN lookup failed: %s", exc)

        return None

    def _get_source_order(self, prefer_source: Optional[str]) -> List[str]:
        """Determine order of sources to try."""
        # Default: Open Library first (free, no auth)
        sources = ["openlibrary"]

        if self.hardcover_available:
            if prefer_source == "hardcover":
                sources = ["hardcover", "openlibrary"]
            else:
                sources.append("hardcover")

        return sources

    def _normalize_openlibrary_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Open Library result to standard format."""
        return {
            "title": result.get("title"),
            "authors": result.get("authors", []),
            "year": result.get("first_publish_year"),
            "isbn": result.get("isbn", []),
            "cover_url": result.get("cover_url"),
            "genres": result.get("subjects", [])[:10],  # Limit genres
            "description": result.get("description"),
            "pages": result.get("number_of_pages"),
            "source": result.get("source", "openlibrary"),
            "source_ids": result.get("source_ids", {}),
        }

    def _normalize_openlibrary_work(
        self,
        edition: Dict[str, Any],
        work: Dict[str, Any],
        isbn: str,
    ) -> Dict[str, Any]:
        """Normalize Open Library edition + work data."""
        # Get description
        description = work.get("description")
        if isinstance(description, dict):
            description = description.get("value", "")

        # Get authors
        author_keys = [a.get("author", {}).get("key") for a in work.get("authors", [])]
        authors = []
        for key in author_keys:
            if key:
                author_data = self.openlibrary_api.get_author(key)
                if author_data:
                    authors.append(author_data.get("name", ""))

        # Get cover
        cover_id = edition.get("covers", [None])[0]
        cover_url = self.openlibrary_api.get_cover_url(cover_id) if cover_id else None

        return {
            "title": edition.get("title") or work.get("title"),
            "authors": authors,
            "year": (
                edition.get("publish_date", "")[:4]
                if edition.get("publish_date")
                else None
            ),
            "isbn": [isbn],
            "cover_url": cover_url,
            "genres": work.get("subjects", [])[:10],
            "description": description,
            "pages": edition.get("number_of_pages"),
            "source": "openlibrary",
            "source_ids": {
                "work_key": work.get("key"),
                "edition_key": edition.get("key"),
            },
        }

    def _normalize_hardcover_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Hardcover result to standard format."""
        return {
            "title": result.get("title"),
            "authors": result.get("authors", []),
            "year": result.get("year"),
            "isbn": result.get("isbn", []),
            "cover_url": result.get("cover_url"),
            "genres": result.get("genres", [])[:10],
            "description": result.get("description"),
            "pages": result.get("pages"),
            "source": result.get("source", "hardcover"),
            "source_ids": result.get("source_ids", {}),
        }

    def search_books(
        self,
        query: str,
        limit: int = 10,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for books across configured sources.

        Args:
            query: Search query (title, author, or general)
            limit: Maximum results to return
            source: Specific source to use ("openlibrary" or "hardcover")

        Returns:
            List of book result dictionaries
        """
        results = []

        if source == "hardcover" and self._hardcover_api:
            results = self._hardcover_api.search_books(query, limit=limit)
            for r in results:
                r["source"] = "hardcover"
        elif source == "openlibrary" or not self._hardcover_api:
            results = self.openlibrary_api.search_books(query, limit=limit)
            for r in results:
                r["source"] = "openlibrary"
        else:
            # Combine results from both sources
            ol_results = self.openlibrary_api.search_books(query, limit=limit // 2)
            for r in ol_results:
                r["source"] = "openlibrary"
            results.extend(ol_results)

            if self._hardcover_api:
                hc_results = self._hardcover_api.search_books(query, limit=limit // 2)
                for r in hc_results:
                    r["source"] = "hardcover"
                results.extend(hc_results)

        return results[:limit]


def get_service(
    use_hardcover: bool = True,
    hardcover_token: Optional[str] = None,
) -> BookMetadataService:
    """
    Create and return a BookMetadataService instance.

    Args:
        use_hardcover: Whether to enable Hardcover when configured
        hardcover_token: Optional Hardcover API token

    Returns:
        Configured BookMetadataService
    """
    return BookMetadataService(
        use_hardcover=use_hardcover,
        hardcover_token=hardcover_token,
    )
