"""
Tests for the BookMetadataService unified API coordinator.

Tests cover:
- Service initialization and configuration
- Source preference and fallback logic
- ISBN vs title+author lookups
- Result normalization between sources
- Search functionality across sources
- Error handling and resilience
"""

from unittest import mock

from django.test import TestCase

from books.book_metadata import (
    BookMetadataService,
    get_service,
)


class ServiceInitializationTests(TestCase):
    """Tests for BookMetadataService initialization."""

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_default_initialization(self, mock_get_hardcover):
        """Test service initializes with default settings."""
        mock_get_hardcover.return_value = None

        service = BookMetadataService()

        self.assertEqual(service.rate_limit, 1.0)
        self.assertTrue(service.use_hardcover)
        mock_get_hardcover.assert_called_once()

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_custom_rate_limit(self, mock_get_hardcover):
        """Test service accepts custom rate limit."""
        mock_get_hardcover.return_value = None

        service = BookMetadataService(rate_limit=2.5)

        self.assertEqual(service.rate_limit, 2.5)

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_disable_hardcover(self, mock_get_hardcover):
        """Test service can disable Hardcover."""
        service = BookMetadataService(use_hardcover=False)

        self.assertFalse(service.use_hardcover)
        mock_get_hardcover.assert_not_called()

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_hardcover_token_passed(self, mock_get_hardcover):
        """Test Hardcover token is passed to API."""
        mock_get_hardcover.return_value = mock.Mock()

        BookMetadataService(hardcover_token="test_token")

        mock_get_hardcover.assert_called_once_with(
            api_token="test_token",
            rate_limit=1.0,
        )


class HardcoverAvailabilityTests(TestCase):
    """Tests for hardcover_available property."""

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_hardcover_available_when_configured(self, mock_get_hardcover):
        """Test hardcover_available returns True when API is configured."""
        mock_get_hardcover.return_value = mock.Mock()

        service = BookMetadataService()

        self.assertTrue(service.hardcover_available)

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_hardcover_not_available_when_no_token(self, mock_get_hardcover):
        """Test hardcover_available returns False when no token."""
        mock_get_hardcover.return_value = None

        service = BookMetadataService()

        self.assertFalse(service.hardcover_available)

    def test_hardcover_not_available_when_disabled(self):
        """Test hardcover_available returns False when disabled."""
        service = BookMetadataService(use_hardcover=False)

        self.assertFalse(service.hardcover_available)


class OpenLibraryLazyInitTests(TestCase):
    """Tests for lazy Open Library API initialization."""

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_openlibrary_lazy_init(self, mock_hc, mock_ol):
        """Test Open Library API is lazily initialized."""
        mock_hc.return_value = None
        mock_ol.return_value = mock.Mock()

        service = BookMetadataService()

        # Not called during init
        mock_ol.assert_not_called()

        # Called on first access
        _ = service.openlibrary_api
        mock_ol.assert_called_once_with(rate_limit=1.0)

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_openlibrary_cached_after_init(self, mock_hc, mock_ol):
        """Test Open Library API is cached after first access."""
        mock_hc.return_value = None
        mock_api = mock.Mock()
        mock_ol.return_value = mock_api

        service = BookMetadataService()
        api1 = service.openlibrary_api
        api2 = service.openlibrary_api

        self.assertIs(api1, api2)
        self.assertEqual(mock_ol.call_count, 1)


class SourceOrderTests(TestCase):
    """Tests for _get_source_order method."""

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_default_order_openlibrary_first(self, mock_get_hardcover):
        """Test default order is Open Library first."""
        mock_get_hardcover.return_value = mock.Mock()

        service = BookMetadataService()
        order = service._get_source_order(None)

        self.assertEqual(order, ["openlibrary", "hardcover"])

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_prefer_hardcover(self, mock_get_hardcover):
        """Test preferring Hardcover changes order."""
        mock_get_hardcover.return_value = mock.Mock()

        service = BookMetadataService()
        order = service._get_source_order("hardcover")

        self.assertEqual(order, ["hardcover", "openlibrary"])

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_only_openlibrary_when_hardcover_unavailable(self, mock_get_hardcover):
        """Test only Open Library when Hardcover not configured."""
        mock_get_hardcover.return_value = None

        service = BookMetadataService()
        order = service._get_source_order(None)

        self.assertEqual(order, ["openlibrary"])


class IsbnLookupTests(TestCase):
    """Tests for ISBN lookup error handling."""

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_isbn_lookup_hardcover_exception(
        self, mock_get_hardcover, mock_get_openlibrary
    ):
        """Test Hardcover ISBN lookup exceptions are handled gracefully."""
        mock_openlibrary = mock.Mock()
        mock_openlibrary.search_by_isbn.return_value = None
        mock_get_openlibrary.return_value = mock_openlibrary

        mock_hardcover = mock.Mock()
        mock_hardcover.get_book_by_isbn.side_effect = Exception("boom")
        mock_get_hardcover.return_value = mock_hardcover

        service = BookMetadataService()

        result = service._lookup_by_isbn("9780000000000")

        self.assertIsNone(result)


class NormalizationTests(TestCase):
    """Tests for result normalization methods."""

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_normalize_openlibrary_result(self, mock_get_hardcover):
        """Test Open Library result normalization."""
        mock_get_hardcover.return_value = None
        service = BookMetadataService()

        result = {
            "title": "Test Book",
            "authors": ["Author One"],
            "first_publish_year": 2020,
            "isbn": ["1234567890"],
            "cover_url": "http://example.com/cover.jpg",
            "subjects": ["Fiction", "Adventure"],
            "description": "A test book",
            "number_of_pages": 300,
            "source": "openlibrary",
            "source_ids": {"work_key": "/works/OL123W"},
        }

        normalized = service._normalize_openlibrary_result(result)

        self.assertEqual(normalized["title"], "Test Book")
        self.assertEqual(normalized["authors"], ["Author One"])
        self.assertEqual(normalized["year"], 2020)
        self.assertEqual(normalized["isbn"], ["1234567890"])
        self.assertEqual(normalized["genres"], ["Fiction", "Adventure"])
        self.assertEqual(normalized["pages"], 300)

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_normalize_openlibrary_limits_genres(self, mock_get_hardcover):
        """Test Open Library normalization limits genres to 10."""
        mock_get_hardcover.return_value = None
        service = BookMetadataService()

        result = {
            "subjects": [f"Genre{i}" for i in range(20)],
        }

        normalized = service._normalize_openlibrary_result(result)

        self.assertEqual(len(normalized["genres"]), 10)

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_normalize_hardcover_result(self, mock_get_hardcover):
        """Test Hardcover result normalization."""
        mock_get_hardcover.return_value = None
        service = BookMetadataService()

        result = {
            "title": "Hardcover Book",
            "authors": ["HC Author"],
            "year": 2021,
            "isbn": ["9876543210"],
            "cover_url": "http://hardcover.app/cover.jpg",
            "genres": ["Sci-Fi"],
            "description": "A hardcover book",
            "pages": 400,
            "source": "hardcover",
            "source_ids": {"hardcover_id": 12345},
        }

        normalized = service._normalize_hardcover_result(result)

        self.assertEqual(normalized["title"], "Hardcover Book")
        self.assertEqual(normalized["authors"], ["HC Author"])
        self.assertEqual(normalized["year"], 2021)
        self.assertEqual(normalized["pages"], 400)


class NormalizeOpenLibraryWorkTests(TestCase):
    """Tests for _normalize_openlibrary_work method."""

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_normalize_work_with_full_data(self, mock_hc, mock_ol):
        """Test normalizing full edition + work data."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.get_author.return_value = {"name": "Test Author"}
        mock_ol_api.get_cover_url.return_value = (
            "http://covers.openlibrary.org/b/id/123-L.jpg"
        )
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        # Force lazy init
        _ = service.openlibrary_api

        edition = {
            "title": "Edition Title",
            "publish_date": "2020-01-15",
            "number_of_pages": 250,
            "covers": [123],
            "key": "/books/OL123M",
        }
        work = {
            "title": "Work Title",
            "key": "/works/OL456W",
            "description": "Work description",
            "subjects": ["Fantasy", "Magic"],
            "authors": [{"author": {"key": "/authors/OL789A"}}],
        }

        normalized = service._normalize_openlibrary_work(edition, work, "9781234567890")

        self.assertEqual(normalized["title"], "Edition Title")
        self.assertEqual(normalized["authors"], ["Test Author"])
        self.assertEqual(normalized["year"], "2020")
        self.assertEqual(normalized["isbn"], ["9781234567890"])
        self.assertEqual(normalized["genres"], ["Fantasy", "Magic"])
        self.assertEqual(normalized["source"], "openlibrary")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_normalize_work_with_dict_description(self, mock_hc, mock_ol):
        """Test normalizing work with description as dict."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.get_author.return_value = None
        mock_ol_api.get_cover_url.return_value = None
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        _ = service.openlibrary_api

        edition = {"title": "Book", "key": "/books/OL1M"}
        work = {
            "title": "Book",
            "key": "/works/OL1W",
            "description": {"type": "/type/text", "value": "Description text"},
            "authors": [],
        }

        normalized = service._normalize_openlibrary_work(edition, work, "123")

        self.assertEqual(normalized["description"], "Description text")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_normalize_work_falls_back_to_work_title(self, mock_hc, mock_ol):
        """Test falling back to work title when edition has none."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.get_author.return_value = None
        mock_ol_api.get_cover_url.return_value = None
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        _ = service.openlibrary_api

        edition = {"key": "/books/OL1M"}  # No title
        work = {"title": "Work Title", "key": "/works/OL1W", "authors": []}

        normalized = service._normalize_openlibrary_work(edition, work, "123")

        self.assertEqual(normalized["title"], "Work Title")


class GetBookInfoTests(TestCase):
    """Tests for get_book_info method."""

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_get_book_info_from_openlibrary(self, mock_hc, mock_ol):
        """Test getting book info from Open Library."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.get_book_info.return_value = {
            "title": "Test Book",
            "authors": ["Test Author"],
            "first_publish_year": 2020,
        }
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        result = service.get_book_info("Test Book")

        self.assertEqual(result["title"], "Test Book")
        self.assertEqual(result["source"], "openlibrary")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_get_book_info_from_hardcover_when_preferred(self, mock_hc, mock_ol):
        """Test getting book info from Hardcover when preferred."""
        mock_hc_api = mock.Mock()
        mock_hc_api.get_book_info.return_value = {
            "title": "HC Book",
            "hardcover_id": 123,
        }
        mock_hc.return_value = mock_hc_api

        service = BookMetadataService()
        result = service.get_book_info("HC Book", prefer_source="hardcover")

        self.assertEqual(result["title"], "HC Book")
        self.assertEqual(result["source"], "hardcover")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_get_book_info_fallback_on_failure(self, mock_hc, mock_ol):
        """Test fallback when preferred source fails."""
        mock_hc_api = mock.Mock()
        mock_hc_api.get_book_info.side_effect = Exception("API Error")
        mock_hc.return_value = mock_hc_api

        mock_ol_api = mock.Mock()
        mock_ol_api.get_book_info.return_value = {
            "title": "Fallback Book",
            "first_publish_year": 2019,
        }
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        result = service.get_book_info("Book", prefer_source="hardcover")

        self.assertEqual(result["title"], "Fallback Book")
        self.assertEqual(result["source"], "openlibrary")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_get_book_info_returns_none_when_all_fail(self, mock_hc, mock_ol):
        """Test returns None when all sources fail."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.get_book_info.return_value = None
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        result = service.get_book_info("Nonexistent Book")

        self.assertIsNone(result)


class ISBNLookupTests(TestCase):
    """Tests for ISBN lookup functionality."""

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_isbn_lookup_uses_openlibrary_first(self, mock_hc, mock_ol):
        """Test ISBN lookup tries Open Library first."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.search_by_isbn.return_value = {
            "title": "ISBN Book",
            "works": [{"key": "/works/OL123W"}],
        }
        mock_ol_api.get_work.return_value = {
            "title": "ISBN Book",
            "key": "/works/OL123W",
            "authors": [],
        }
        mock_ol_api.get_author.return_value = None
        mock_ol_api.get_cover_url.return_value = None
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        result = service.get_book_info("Any", isbn="9781234567890")

        self.assertEqual(result["source"], "openlibrary")
        mock_ol_api.search_by_isbn.assert_called_once_with("9781234567890")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_isbn_lookup_falls_back_to_hardcover(self, mock_hc, mock_ol):
        """Test ISBN lookup falls back to Hardcover."""
        mock_ol_api = mock.Mock()
        mock_ol_api.search_by_isbn.return_value = None
        mock_ol.return_value = mock_ol_api

        mock_hc_api = mock.Mock()
        mock_hc_api.get_book_by_isbn.return_value = {
            "title": "HC ISBN Book",
            "hardcover_id": 456,
        }
        mock_hc.return_value = mock_hc_api

        service = BookMetadataService()
        result = service.get_book_info("Any", isbn="9780987654321")

        self.assertEqual(result["source"], "hardcover")
        mock_hc_api.get_book_by_isbn.assert_called_once_with("9780987654321")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_isbn_lookup_handles_exception(self, mock_hc, mock_ol):
        """Test ISBN lookup handles exceptions gracefully."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.search_by_isbn.side_effect = Exception("Network error")
        mock_ol_api.get_book_info.return_value = {"title": "Fallback"}
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        # Should fall back to title search
        result = service.get_book_info("Fallback Book", isbn="123")

        self.assertEqual(result["title"], "Fallback")


class SearchBooksTests(TestCase):
    """Tests for search_books method."""

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_search_openlibrary_only(self, mock_hc, mock_ol):
        """Test search using only Open Library."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.search_books.return_value = [
            {"title": "Result 1"},
            {"title": "Result 2"},
        ]
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        results = service.search_books("query", source="openlibrary")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["source"], "openlibrary")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_search_hardcover_only(self, mock_hc, mock_ol):
        """Test search using only Hardcover."""
        mock_hc_api = mock.Mock()
        mock_hc_api.search_books.return_value = [
            {"title": "HC Result"},
        ]
        mock_hc.return_value = mock_hc_api

        service = BookMetadataService()
        results = service.search_books("query", source="hardcover")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "hardcover")

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_search_combined_sources(self, mock_hc, mock_ol):
        """Test search combining results from both sources."""
        mock_ol_api = mock.Mock()
        mock_ol_api.search_books.return_value = [
            {"title": "OL Result 1"},
            {"title": "OL Result 2"},
        ]
        mock_ol.return_value = mock_ol_api

        mock_hc_api = mock.Mock()
        mock_hc_api.search_books.return_value = [
            {"title": "HC Result 1"},
            {"title": "HC Result 2"},
        ]
        mock_hc.return_value = mock_hc_api

        service = BookMetadataService()
        results = service.search_books("query", limit=10)

        # Should have results from both sources
        ol_results = [r for r in results if r.get("source") == "openlibrary"]
        hc_results = [r for r in results if r.get("source") == "hardcover"]

        self.assertTrue(len(ol_results) > 0)
        self.assertTrue(len(hc_results) > 0)

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_search_respects_limit(self, mock_hc, mock_ol):
        """Test search respects limit parameter."""
        mock_ol_api = mock.Mock()
        mock_ol_api.search_books.return_value = [{"title": f"OL{i}"} for i in range(10)]
        mock_ol.return_value = mock_ol_api

        mock_hc_api = mock.Mock()
        mock_hc_api.search_books.return_value = [{"title": f"HC{i}"} for i in range(10)]
        mock_hc.return_value = mock_hc_api

        service = BookMetadataService()
        results = service.search_books("query", limit=5)

        self.assertLessEqual(len(results), 5)

    @mock.patch("books.book_metadata.openlibrary.get_api")
    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_search_defaults_to_openlibrary_when_no_hardcover(self, mock_hc, mock_ol):
        """Test search defaults to Open Library when Hardcover unavailable."""
        mock_hc.return_value = None
        mock_ol_api = mock.Mock()
        mock_ol_api.search_books.return_value = [{"title": "OL Only"}]
        mock_ol.return_value = mock_ol_api

        service = BookMetadataService()
        results = service.search_books("query")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "openlibrary")


class GetServiceFactoryTests(TestCase):
    """Tests for get_service factory function."""

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_get_service_default(self, mock_hc):
        """Test get_service returns configured service."""
        mock_hc.return_value = None

        service = get_service()

        self.assertIsInstance(service, BookMetadataService)
        self.assertTrue(service.use_hardcover)

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_get_service_disable_hardcover(self, mock_hc):
        """Test get_service can disable Hardcover."""
        service = get_service(use_hardcover=False)

        self.assertFalse(service.use_hardcover)
        mock_hc.assert_not_called()

    @mock.patch("books.book_metadata.hardcover.get_api")
    def test_get_service_with_token(self, mock_hc):
        """Test get_service passes Hardcover token."""
        mock_hc.return_value = mock.Mock()

        get_service(hardcover_token="my_token")

        mock_hc.assert_called_once_with(
            api_token="my_token",
            rate_limit=1.0,
        )
