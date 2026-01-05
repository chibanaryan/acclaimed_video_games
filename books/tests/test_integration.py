"""
Tests for book metadata integration modules.

Comprehensive tests for:
- OpenLibrary API client (openlibrary.py)
- Hardcover GraphQL API client (hardcover.py)
- BookMetadataService (book_metadata.py)

All external API calls are mocked to ensure tests are fast, reliable,
and don't depend on external services.
"""

import json
import time
from collections import OrderedDict
from unittest import mock

from django.test import TestCase, override_settings

from books import openlibrary, hardcover, book_metadata


class OpenLibraryApiCacheTests(TestCase):
    """Tests for OpenLibrary API caching behavior."""

    def setUp(self):
        """Create a fresh API client for each test."""
        self.api = openlibrary.OpenLibraryApi(
            rate_limit=0.01,  # Fast for tests
            cache_size=3,
            timeout=5.0,
        )

    def test_get_from_cache_returns_none_for_missing_key(self):
        """Test _get_from_cache returns None for missing keys."""
        result = self.api._get_from_cache(self.api.work_cache, "missing_key")
        self.assertIsNone(result)

    def test_set_and_get_from_cache(self):
        """Test setting and getting items from cache."""
        self.api._set_in_cache(self.api.work_cache, "test_key", {"data": "test"})
        result = self.api._get_from_cache(self.api.work_cache, "test_key")
        self.assertEqual(result, {"data": "test"})

    def test_cache_lru_eviction(self):
        """Test LRU cache eviction when size limit reached."""
        # Fill cache to capacity (size=3)
        self.api._set_in_cache(self.api.work_cache, "key1", "value1")
        self.api._set_in_cache(self.api.work_cache, "key2", "value2")
        self.api._set_in_cache(self.api.work_cache, "key3", "value3")

        # Adding a 4th item should evict the oldest (key1)
        self.api._set_in_cache(self.api.work_cache, "key4", "value4")

        # key1 should be evicted
        self.assertIsNone(self.api._get_from_cache(self.api.work_cache, "key1"))
        # key4 should exist
        self.assertEqual(
            self.api._get_from_cache(self.api.work_cache, "key4"), "value4"
        )

    def test_cache_lru_access_updates_order(self):
        """Test that accessing an item moves it to end (most recently used)."""
        self.api._set_in_cache(self.api.work_cache, "key1", "value1")
        self.api._set_in_cache(self.api.work_cache, "key2", "value2")
        self.api._set_in_cache(self.api.work_cache, "key3", "value3")

        # Access key1 to make it most recently used
        self.api._get_from_cache(self.api.work_cache, "key1")

        # Add key4 - should evict key2 (oldest after key1 was accessed)
        self.api._set_in_cache(self.api.work_cache, "key4", "value4")

        # key1 should still exist, key2 should be evicted
        self.assertEqual(
            self.api._get_from_cache(self.api.work_cache, "key1"), "value1"
        )
        self.assertIsNone(self.api._get_from_cache(self.api.work_cache, "key2"))

    def test_set_in_cache_updates_existing_key(self):
        """Test that setting existing key updates value and moves to end."""
        self.api._set_in_cache(self.api.work_cache, "key1", "value1")
        self.api._set_in_cache(self.api.work_cache, "key2", "value2")

        # Update key1 with new value
        self.api._set_in_cache(self.api.work_cache, "key1", "new_value1")

        result = self.api._get_from_cache(self.api.work_cache, "key1")
        self.assertEqual(result, "new_value1")


class OpenLibraryApiRateLimitTests(TestCase):
    """Tests for OpenLibrary API rate limiting."""

    def test_rate_limit_enforcement(self):
        """Test that rate limiting enforces minimum request interval."""
        api = openlibrary.OpenLibraryApi(rate_limit=0.1, timeout=1.0)
        api.last_request_time = time.time()

        start = time.time()
        api._wait_for_rate_limit()
        elapsed = time.time() - start

        # Should have waited approximately 0.1 seconds
        self.assertGreaterEqual(elapsed, 0.08)  # Allow small margin

    def test_no_wait_when_enough_time_passed(self):
        """Test that no waiting occurs when interval has passed."""
        api = openlibrary.OpenLibraryApi(rate_limit=0.1, timeout=1.0)
        api.last_request_time = time.time() - 1.0  # 1 second ago

        start = time.time()
        api._wait_for_rate_limit()
        elapsed = time.time() - start

        # Should not have waited
        self.assertLess(elapsed, 0.05)


class OpenLibraryApiRequestTests(TestCase):
    """Tests for OpenLibrary API request handling."""

    def setUp(self):
        self.api = openlibrary.OpenLibraryApi(rate_limit=0.01, timeout=5.0)

    @mock.patch("books.openlibrary.requests.get")
    def test_make_request_success(self, mock_get):
        """Test successful API request."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = self.api._make_request("https://openlibrary.org/test.json")

        self.assertEqual(result, mock_response)
        mock_get.assert_called_once()

    @mock.patch("books.openlibrary.requests.get")
    def test_make_request_rate_limited_retries(self, mock_get):
        """Test rate limited request retries with backoff."""
        # First call returns 429, second returns 200
        mock_rate_limited = mock.Mock()
        mock_rate_limited.status_code = 429
        mock_success = mock.Mock()
        mock_success.status_code = 200
        mock_get.side_effect = [mock_rate_limited, mock_success]

        result = self.api._make_request("https://openlibrary.org/test.json")

        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)

    @mock.patch("books.openlibrary.requests.get")
    def test_make_request_max_retries_exceeded(self, mock_get):
        """Test max retries exceeded returns None."""
        mock_rate_limited = mock.Mock()
        mock_rate_limited.status_code = 429
        mock_get.return_value = mock_rate_limited

        result = self.api._make_request(
            "https://openlibrary.org/test.json", max_retries=2
        )

        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 3)  # Initial + 2 retries

    @mock.patch("books.openlibrary.requests.get")
    def test_make_request_network_error_retries(self, mock_get):
        """Test network error triggers retry."""
        import requests

        mock_get.side_effect = [
            requests.RequestException("Connection error"),
            mock.Mock(status_code=200),
        ]

        result = self.api._make_request("https://openlibrary.org/test.json")

        self.assertEqual(result.status_code, 200)

    @mock.patch("books.openlibrary.requests.get")
    def test_make_request_network_error_max_retries(self, mock_get):
        """Test network errors exhaust retries."""
        import requests

        mock_get.side_effect = requests.RequestException("Connection error")

        result = self.api._make_request(
            "https://openlibrary.org/test.json", max_retries=2
        )

        self.assertIsNone(result)


class OpenLibrarySearchTests(TestCase):
    """Tests for OpenLibrary search functionality."""

    def setUp(self):
        self.api = openlibrary.OpenLibraryApi(rate_limit=0.01, timeout=5.0)

    @mock.patch("books.openlibrary.requests.get")
    def test_search_books_success(self, mock_get):
        """Test successful book search."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "docs": [
                {"key": "/works/OL123W", "title": "Test Book", "author_name": ["Author"]}
            ]
        }
        mock_get.return_value = mock_response

        results = self.api.search_books("Test Book", limit=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Book")

    @mock.patch("books.openlibrary.requests.get")
    def test_search_books_uses_cache(self, mock_get):
        """Test search results are cached."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"docs": [{"title": "Cached Book"}]}
        mock_get.return_value = mock_response

        # First call hits API
        results1 = self.api.search_books("Cached Book", limit=10)
        # Second call should use cache
        results2 = self.api.search_books("Cached Book", limit=10)

        # API should only be called once
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(results1, results2)

    @mock.patch("books.openlibrary.requests.get")
    def test_search_books_request_failure(self, mock_get):
        """Test search returns empty list on failure."""
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        results = self.api.search_books("Test Book")

        self.assertEqual(results, [])

    @mock.patch("books.openlibrary.requests.get")
    def test_search_books_json_parse_error(self, mock_get):
        """Test search handles JSON parse errors gracefully."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        results = self.api.search_books("Test Book")

        self.assertEqual(results, [])


class OpenLibraryIsbnTests(TestCase):
    """Tests for OpenLibrary ISBN lookup."""

    def setUp(self):
        self.api = openlibrary.OpenLibraryApi(rate_limit=0.01, timeout=5.0)

    @mock.patch("books.openlibrary.requests.get")
    def test_search_by_isbn_success(self, mock_get):
        """Test successful ISBN lookup."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "1984",
            "works": [{"key": "/works/OL123W"}],
        }
        mock_get.return_value = mock_response

        result = self.api.search_by_isbn("978-0-452-28423-4")

        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "1984")

    @mock.patch("books.openlibrary.requests.get")
    def test_search_by_isbn_cleans_hyphens(self, mock_get):
        """Test ISBN hyphens are removed."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Test"}
        mock_get.return_value = mock_response

        self.api.search_by_isbn("978-0-452-28423-4")

        # Check that URL contains cleaned ISBN
        call_url = mock_get.call_args[0][0]
        self.assertIn("9780452284234", call_url)

    @mock.patch("books.openlibrary.requests.get")
    def test_search_by_isbn_not_found(self, mock_get):
        """Test ISBN not found returns None."""
        mock_response = mock.Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = self.api.search_by_isbn("0000000000")

        self.assertIsNone(result)

    @mock.patch("books.openlibrary.requests.get")
    def test_search_by_isbn_uses_cache(self, mock_get):
        """Test ISBN lookup uses cache."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Cached"}
        mock_get.return_value = mock_response

        result1 = self.api.search_by_isbn("9780452284234")
        result2 = self.api.search_by_isbn("9780452284234")

        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(result1, result2)


class OpenLibraryWorkTests(TestCase):
    """Tests for OpenLibrary work retrieval."""

    def setUp(self):
        self.api = openlibrary.OpenLibraryApi(rate_limit=0.01, timeout=5.0)

    @mock.patch("books.openlibrary.requests.get")
    def test_get_work_success(self, mock_get):
        """Test successful work retrieval."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Test Work",
            "description": "A great book",
        }
        mock_get.return_value = mock_response

        result = self.api.get_work("OL123W")

        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Test Work")

    @mock.patch("books.openlibrary.requests.get")
    def test_get_work_normalizes_id(self, mock_get):
        """Test work ID is normalized with /works/ prefix."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Test"}
        mock_get.return_value = mock_response

        self.api.get_work("OL123W")

        call_url = mock_get.call_args[0][0]
        self.assertIn("/works/OL123W.json", call_url)

    @mock.patch("books.openlibrary.requests.get")
    def test_get_work_with_full_path(self, mock_get):
        """Test work with full path doesn't double prefix."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Test"}
        mock_get.return_value = mock_response

        self.api.get_work("/works/OL123W")

        call_url = mock_get.call_args[0][0]
        # Should not have /works//works/
        self.assertNotIn("/works//works/", call_url)
        self.assertIn("/works/OL123W.json", call_url)


class OpenLibraryAuthorTests(TestCase):
    """Tests for OpenLibrary author retrieval."""

    def setUp(self):
        self.api = openlibrary.OpenLibraryApi(rate_limit=0.01, timeout=5.0)

    @mock.patch("books.openlibrary.requests.get")
    def test_get_author_success(self, mock_get):
        """Test successful author retrieval."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "George Orwell",
            "birth_date": "June 25, 1903",
        }
        mock_get.return_value = mock_response

        result = self.api.get_author("OL123A")

        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "George Orwell")

    @mock.patch("books.openlibrary.requests.get")
    def test_get_author_normalizes_id(self, mock_get):
        """Test author ID is normalized with /authors/ prefix."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Test"}
        mock_get.return_value = mock_response

        self.api.get_author("OL123A")

        call_url = mock_get.call_args[0][0]
        self.assertIn("/authors/OL123A.json", call_url)


class OpenLibraryCoverUrlTests(TestCase):
    """Tests for OpenLibrary cover URL generation."""

    def setUp(self):
        self.api = openlibrary.OpenLibraryApi()

    def test_get_cover_url_default_size(self):
        """Test cover URL with default medium size."""
        url = self.api.get_cover_url(12345)

        self.assertEqual(url, "https://covers.openlibrary.org/b/id/12345-M.jpg")

    def test_get_cover_url_small_size(self):
        """Test cover URL with small size."""
        url = self.api.get_cover_url(12345, size="S")

        self.assertEqual(url, "https://covers.openlibrary.org/b/id/12345-S.jpg")

    def test_get_cover_url_large_size(self):
        """Test cover URL with large size."""
        url = self.api.get_cover_url(12345, size="L")

        self.assertEqual(url, "https://covers.openlibrary.org/b/id/12345-L.jpg")

    def test_get_cover_url_by_isbn(self):
        """Test cover URL by ISBN."""
        url = self.api.get_cover_url("9780452284234", id_type="isbn")

        self.assertEqual(
            url, "https://covers.openlibrary.org/b/isbn/9780452284234-M.jpg"
        )


class OpenLibraryGetBookInfoTests(TestCase):
    """Tests for OpenLibrary get_book_info convenience method."""

    def setUp(self):
        self.api = openlibrary.OpenLibraryApi(rate_limit=0.01, timeout=5.0)

    @mock.patch("books.openlibrary.requests.get")
    def test_get_book_info_success(self, mock_get):
        """Test get_book_info returns comprehensive metadata."""
        # Mock search response
        search_response = mock.Mock()
        search_response.status_code = 200
        search_response.json.return_value = {
            "docs": [
                {
                    "key": "/works/OL123W",
                    "title": "1984",
                    "author_name": ["George Orwell"],
                    "author_key": ["OL123A"],
                    "first_publish_year": 1949,
                    "isbn": ["9780452284234"],
                    "cover_i": 12345,
                    "subject": ["Dystopia", "Science Fiction"],
                    "publisher": ["Signet"],
                    "number_of_pages_median": 328,
                }
            ]
        }

        # Mock work response
        work_response = mock.Mock()
        work_response.status_code = 200
        work_response.json.return_value = {
            "description": {"value": "A dystopian novel."}
        }

        mock_get.side_effect = [search_response, work_response]

        result = self.api.get_book_info("1984", "George Orwell")

        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "1984")
        self.assertEqual(result["authors"], ["George Orwell"])
        self.assertEqual(result["first_publish_year"], 1949)
        self.assertEqual(result["description"], "A dystopian novel.")
        self.assertIn("cover_url", result)

    @mock.patch("books.openlibrary.requests.get")
    def test_get_book_info_no_results(self, mock_get):
        """Test get_book_info returns None when no results."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"docs": []}
        mock_get.return_value = mock_response

        result = self.api.get_book_info("Nonexistent Book")

        self.assertIsNone(result)

    @mock.patch("books.openlibrary.requests.get")
    def test_get_book_info_best_match_scoring(self, mock_get):
        """Test get_book_info selects best match by scoring."""
        search_response = mock.Mock()
        search_response.status_code = 200
        search_response.json.return_value = {
            "docs": [
                # Worse match - different author
                {
                    "key": "/works/OL1W",
                    "title": "1984",
                    "author_name": ["Wrong Author"],
                },
                # Better match - correct author
                {
                    "key": "/works/OL2W",
                    "title": "1984",
                    "author_name": ["George Orwell"],
                },
            ]
        }

        work_response = mock.Mock()
        work_response.status_code = 200
        work_response.json.return_value = {}

        mock_get.side_effect = [search_response, work_response]

        result = self.api.get_book_info("1984", "George Orwell")

        self.assertEqual(result["authors"], ["George Orwell"])


class OpenLibraryGetApiTests(TestCase):
    """Tests for the get_api factory function."""

    def test_get_api_default_params(self):
        """Test get_api with default parameters."""
        api = openlibrary.get_api()

        self.assertIsInstance(api, openlibrary.OpenLibraryApi)
        self.assertEqual(api.min_request_interval, openlibrary.DEFAULT_RATE_LIMIT)
        self.assertEqual(api.cache_max_size, openlibrary.DEFAULT_CACHE_SIZE)

    def test_get_api_custom_params(self):
        """Test get_api with custom parameters."""
        api = openlibrary.get_api(rate_limit=2.0, cache_size=100)

        self.assertEqual(api.min_request_interval, 2.0)
        self.assertEqual(api.cache_max_size, 100)


# ============================================================================
# Hardcover API Tests
# ============================================================================


class HardcoverApiCacheTests(TestCase):
    """Tests for Hardcover API caching behavior."""

    def setUp(self):
        self.api = hardcover.HardcoverApi(
            api_token="test_token",
            rate_limit=0.01,
            cache_size=3,
            timeout=5.0,
        )

    def test_get_from_cache_returns_none_for_missing_key(self):
        """Test _get_from_cache returns None for missing keys."""
        result = self.api._get_from_cache(self.api.book_cache, "missing_key")
        self.assertIsNone(result)

    def test_set_and_get_from_cache(self):
        """Test setting and getting items from cache."""
        self.api._set_in_cache(self.api.book_cache, "test_key", {"data": "test"})
        result = self.api._get_from_cache(self.api.book_cache, "test_key")
        self.assertEqual(result, {"data": "test"})

    def test_cache_lru_eviction(self):
        """Test LRU cache eviction when size limit reached."""
        self.api._set_in_cache(self.api.book_cache, "key1", "value1")
        self.api._set_in_cache(self.api.book_cache, "key2", "value2")
        self.api._set_in_cache(self.api.book_cache, "key3", "value3")
        self.api._set_in_cache(self.api.book_cache, "key4", "value4")

        self.assertIsNone(self.api._get_from_cache(self.api.book_cache, "key1"))
        self.assertEqual(
            self.api._get_from_cache(self.api.book_cache, "key4"), "value4"
        )


class HardcoverApiRequestTests(TestCase):
    """Tests for Hardcover API request handling."""

    def setUp(self):
        self.api = hardcover.HardcoverApi(
            api_token="test_token",
            rate_limit=0.01,
            timeout=5.0,
        )

    @mock.patch("books.hardcover.requests.post")
    def test_make_request_success(self, mock_post):
        """Test successful GraphQL request."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"books": []}}
        mock_post.return_value = mock_response

        result = self.api._make_request("query { books { id } }")

        self.assertEqual(result, {"books": []})
        mock_post.assert_called_once()

    @mock.patch("books.hardcover.requests.post")
    def test_make_request_includes_auth_header(self, mock_post):
        """Test request includes authorization header."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {}}
        mock_post.return_value = mock_response

        self.api._make_request("query { test }")

        call_kwargs = mock_post.call_args[1]
        self.assertIn("Authorization", call_kwargs["headers"])
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer test_token")

    @mock.patch("books.hardcover.requests.post")
    def test_make_request_rate_limited_retries(self, mock_post):
        """Test rate limited request retries."""
        mock_rate_limited = mock.Mock()
        mock_rate_limited.status_code = 429
        mock_success = mock.Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {"data": {"result": "ok"}}
        mock_post.side_effect = [mock_rate_limited, mock_success]

        result = self.api._make_request("query { test }")

        self.assertEqual(result, {"result": "ok"})

    @mock.patch("books.hardcover.requests.post")
    def test_make_request_graphql_errors(self, mock_post):
        """Test request with GraphQL errors returns None."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}]
        }
        mock_post.return_value = mock_response

        result = self.api._make_request("query { invalid }")

        self.assertIsNone(result)

    @mock.patch("books.hardcover.requests.post")
    def test_make_request_http_error(self, mock_post):
        """Test request with HTTP error returns None."""
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = self.api._make_request("query { test }")

        self.assertIsNone(result)


class HardcoverSearchTests(TestCase):
    """Tests for Hardcover search functionality."""

    def setUp(self):
        self.api = hardcover.HardcoverApi(
            api_token="test_token",
            rate_limit=0.01,
            timeout=5.0,
        )

    @mock.patch("books.hardcover.requests.post")
    def test_search_books_success(self, mock_post):
        """Test successful book search."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "search": {
                    "results": [{"id": 1, "title": "Test Book"}]
                }
            }
        }
        mock_post.return_value = mock_response

        results = self.api.search_books("Test Book")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Book")

    @mock.patch("books.hardcover.requests.post")
    def test_search_books_handles_json_string_results(self, mock_post):
        """Test search handles results as JSON string."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "search": {
                    "results": '[{"id": 1, "title": "Test"}]'
                }
            }
        }
        mock_post.return_value = mock_response

        results = self.api.search_books("Test")

        self.assertEqual(len(results), 1)

    @mock.patch("books.hardcover.requests.post")
    def test_search_books_uses_cache(self, mock_post):
        """Test search results are cached."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"search": {"results": [{"title": "Cached"}]}}
        }
        mock_post.return_value = mock_response

        results1 = self.api.search_books("Cached", limit=10)
        results2 = self.api.search_books("Cached", limit=10)

        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(results1, results2)


class HardcoverGetBookTests(TestCase):
    """Tests for Hardcover book retrieval."""

    def setUp(self):
        self.api = hardcover.HardcoverApi(
            api_token="test_token",
            rate_limit=0.01,
            timeout=5.0,
        )

    @mock.patch("books.hardcover.requests.post")
    def test_get_book_by_id_success(self, mock_post):
        """Test successful book retrieval by ID."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "books": [
                    {
                        "id": 123,
                        "title": "Test Book",
                        "description": "A test book.",
                    }
                ]
            }
        }
        mock_post.return_value = mock_response

        result = self.api.get_book_by_id(123)

        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Test Book")

    @mock.patch("books.hardcover.requests.post")
    def test_get_book_by_id_not_found(self, mock_post):
        """Test book not found returns None."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"books": []}}
        mock_post.return_value = mock_response

        result = self.api.get_book_by_id(99999)

        self.assertIsNone(result)

    @mock.patch("books.hardcover.requests.post")
    def test_get_book_by_isbn(self, mock_post):
        """Test book retrieval by ISBN."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"search": {"results": [{"title": "ISBN Book"}]}}
        }
        mock_post.return_value = mock_response

        result = self.api.get_book_by_isbn("978-0-452-28423-4")

        self.assertIsNotNone(result)


class HardcoverGetBookInfoTests(TestCase):
    """Tests for Hardcover get_book_info method."""

    def setUp(self):
        self.api = hardcover.HardcoverApi(
            api_token="test_token",
            rate_limit=0.01,
            timeout=5.0,
        )

    @mock.patch("books.hardcover.requests.post")
    def test_get_book_info_extracts_authors(self, mock_post):
        """Test get_book_info extracts authors from cached_contributors."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "search": {
                    "results": [
                        {
                            "title": "Test Book",
                            "cached_contributors": [
                                {"name": "Author One"},
                                {"author": {"name": "Author Two"}},
                            ],
                        }
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        result = self.api.get_book_info("Test Book")

        self.assertIn("Author One", result["authors"])
        self.assertIn("Author Two", result["authors"])

    @mock.patch("books.hardcover.requests.post")
    def test_get_book_info_extracts_genres(self, mock_post):
        """Test get_book_info extracts genres from cached_tags."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "search": {
                    "results": [
                        {
                            "title": "Test",
                            "cached_tags": [
                                {"tag": "Science Fiction"},
                                {"name": "Dystopia"},
                            ],
                        }
                    ]
                }
            }
        }
        mock_post.return_value = mock_response

        result = self.api.get_book_info("Test")

        self.assertIn("Science Fiction", result["genres"])
        self.assertIn("Dystopia", result["genres"])

    @mock.patch("books.hardcover.requests.post")
    def test_get_book_info_parses_release_date(self, mock_post):
        """Test get_book_info parses release date year."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "search": {
                    "results": [{"title": "Test", "release_date": "1984-06-08"}]
                }
            }
        }
        mock_post.return_value = mock_response

        result = self.api.get_book_info("Test")

        self.assertEqual(result["year"], 1984)


class HardcoverGetApiTests(TestCase):
    """Tests for the get_api factory function."""

    @override_settings(HARDCOVER_API_TOKEN="settings_token")
    def test_get_api_uses_settings_token(self):
        """Test get_api uses token from settings."""
        api = hardcover.get_api()

        self.assertIsInstance(api, hardcover.HardcoverApi)
        self.assertEqual(api.api_token, "settings_token")

    def test_get_api_explicit_token(self):
        """Test get_api with explicit token."""
        api = hardcover.get_api(api_token="explicit_token")

        self.assertEqual(api.api_token, "explicit_token")

    @override_settings()
    def test_get_api_no_token_returns_none(self):
        """Test get_api returns None without token."""
        # Remove HARDCOVER_API_TOKEN from settings
        from django.conf import settings
        if hasattr(settings, "HARDCOVER_API_TOKEN"):
            delattr(settings, "HARDCOVER_API_TOKEN")

        api = hardcover.get_api()

        self.assertIsNone(api)


# ============================================================================
# BookMetadataService Tests
# ============================================================================


class BookMetadataServiceInitTests(TestCase):
    """Tests for BookMetadataService initialization."""

    def test_init_openlibrary_always_available(self):
        """Test Open Library is lazy-initialized but always available."""
        service = book_metadata.BookMetadataService(use_hardcover=False)

        # OpenLibrary API should be lazily initialized
        self.assertIsNone(service._openlibrary_api)
        # Accessing property should initialize it
        api = service.openlibrary_api
        self.assertIsInstance(api, openlibrary.OpenLibraryApi)

    @mock.patch("books.hardcover.get_api")
    def test_init_hardcover_when_token_available(self, mock_get_api):
        """Test Hardcover is initialized when token is available."""
        mock_hardcover = mock.Mock()
        mock_get_api.return_value = mock_hardcover

        service = book_metadata.BookMetadataService(
            use_hardcover=True, hardcover_token="test_token"
        )

        self.assertTrue(service.hardcover_available)

    @mock.patch("books.hardcover.get_api")
    def test_init_hardcover_disabled(self, mock_get_api):
        """Test Hardcover is not initialized when disabled."""
        service = book_metadata.BookMetadataService(use_hardcover=False)

        self.assertFalse(service.hardcover_available)
        mock_get_api.assert_not_called()


class BookMetadataServiceSourceOrderTests(TestCase):
    """Tests for BookMetadataService source order selection."""

    def test_get_source_order_openlibrary_default(self):
        """Test default source order is Open Library first."""
        service = book_metadata.BookMetadataService(use_hardcover=False)

        sources = service._get_source_order(None)

        self.assertEqual(sources, ["openlibrary"])

    @mock.patch("books.hardcover.get_api")
    def test_get_source_order_with_hardcover(self, mock_get_api):
        """Test source order includes Hardcover when available."""
        mock_get_api.return_value = mock.Mock()
        service = book_metadata.BookMetadataService(
            use_hardcover=True, hardcover_token="token"
        )

        sources = service._get_source_order(None)

        self.assertEqual(sources, ["openlibrary", "hardcover"])

    @mock.patch("books.hardcover.get_api")
    def test_get_source_order_prefer_hardcover(self, mock_get_api):
        """Test preferring Hardcover changes order."""
        mock_get_api.return_value = mock.Mock()
        service = book_metadata.BookMetadataService(
            use_hardcover=True, hardcover_token="token"
        )

        sources = service._get_source_order("hardcover")

        self.assertEqual(sources, ["hardcover", "openlibrary"])


class BookMetadataServiceGetBookInfoTests(TestCase):
    """Tests for BookMetadataService.get_book_info method."""

    def setUp(self):
        self.service = book_metadata.BookMetadataService(use_hardcover=False)

    @mock.patch.object(openlibrary.OpenLibraryApi, "get_book_info")
    def test_get_book_info_from_openlibrary(self, mock_get_book_info):
        """Test get_book_info retrieves from Open Library."""
        mock_get_book_info.return_value = {
            "title": "1984",
            "authors": ["George Orwell"],
            "first_publish_year": 1949,
            "isbn": ["9780452284234"],
            "cover_url": "https://example.com/cover.jpg",
            "subjects": ["Dystopia"],
            "description": "A novel.",
            "number_of_pages": 328,
            "work_key": "/works/OL123W",
        }

        result = self.service.get_book_info("1984", "George Orwell")

        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "1984")
        self.assertEqual(result["source"], "openlibrary")

    @mock.patch.object(openlibrary.OpenLibraryApi, "get_book_info")
    def test_get_book_info_normalizes_result(self, mock_get_book_info):
        """Test get_book_info normalizes field names."""
        mock_get_book_info.return_value = {
            "title": "Test",
            "authors": ["Author"],
            "first_publish_year": 2000,
            "isbn": [],
            "subjects": ["Subject1", "Subject2"],
            "number_of_pages": 200,
        }

        result = self.service.get_book_info("Test")

        # Check normalized field names
        self.assertEqual(result["year"], 2000)
        self.assertEqual(result["genres"], ["Subject1", "Subject2"])
        self.assertEqual(result["pages"], 200)

    @mock.patch.object(openlibrary.OpenLibraryApi, "get_book_info")
    def test_get_book_info_returns_none_when_not_found(self, mock_get_book_info):
        """Test get_book_info returns None when book not found."""
        mock_get_book_info.return_value = None

        result = self.service.get_book_info("Nonexistent Book")

        self.assertIsNone(result)


class BookMetadataServiceIsbnLookupTests(TestCase):
    """Tests for BookMetadataService ISBN lookup."""

    def setUp(self):
        self.service = book_metadata.BookMetadataService(use_hardcover=False)

    @mock.patch.object(openlibrary.OpenLibraryApi, "search_by_isbn")
    @mock.patch.object(openlibrary.OpenLibraryApi, "get_work")
    def test_lookup_by_isbn_success(self, mock_get_work, mock_search_isbn):
        """Test ISBN lookup retrieves book data."""
        mock_search_isbn.return_value = {
            "title": "1984",
            "works": [{"key": "/works/OL123W"}],
            "covers": [12345],
            "number_of_pages": 328,
        }
        mock_get_work.return_value = {
            "key": "/works/OL123W",
            "title": "1984",
            "description": {"value": "A dystopian novel."},
            "subjects": ["Dystopia"],
            "authors": [],
        }

        result = self.service._lookup_by_isbn("9780452284234")

        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "1984")
        self.assertEqual(result["source"], "openlibrary")

    @mock.patch.object(openlibrary.OpenLibraryApi, "search_by_isbn")
    def test_lookup_by_isbn_not_found(self, mock_search_isbn):
        """Test ISBN lookup returns None when not found."""
        mock_search_isbn.return_value = None

        result = self.service._lookup_by_isbn("0000000000")

        self.assertIsNone(result)


class BookMetadataServiceSearchTests(TestCase):
    """Tests for BookMetadataService search functionality."""

    def setUp(self):
        self.service = book_metadata.BookMetadataService(use_hardcover=False)

    @mock.patch.object(openlibrary.OpenLibraryApi, "search_books")
    def test_search_books_openlibrary_only(self, mock_search):
        """Test search returns results from Open Library."""
        mock_search.return_value = [
            {"title": "Book 1"},
            {"title": "Book 2"},
        ]

        results = self.service.search_books("test", limit=10)

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r["source"], "openlibrary")

    @mock.patch.object(openlibrary.OpenLibraryApi, "search_books")
    def test_search_books_respects_limit(self, mock_search):
        """Test search respects limit parameter."""
        mock_search.return_value = [{"title": f"Book {i}"} for i in range(20)]

        results = self.service.search_books("test", limit=5)

        self.assertEqual(len(results), 5)


class BookMetadataServiceNormalizationTests(TestCase):
    """Tests for result normalization methods."""

    def setUp(self):
        self.service = book_metadata.BookMetadataService(use_hardcover=False)

    def test_normalize_openlibrary_result(self):
        """Test Open Library result normalization."""
        raw = {
            "title": "Test Book",
            "authors": ["Author One"],
            "first_publish_year": 2000,
            "isbn": ["1234567890"],
            "cover_url": "https://example.com/cover.jpg",
            "subjects": ["Fiction", "Drama", "Adventure"] * 5,  # More than 10
            "description": "A test book.",
            "number_of_pages": 250,
            "source": "openlibrary",
            "source_ids": {"work_key": "/works/OL123W"},
        }

        result = self.service._normalize_openlibrary_result(raw)

        self.assertEqual(result["title"], "Test Book")
        self.assertEqual(result["year"], 2000)
        self.assertEqual(result["pages"], 250)
        # Genres should be limited to 10
        self.assertEqual(len(result["genres"]), 10)

    def test_normalize_hardcover_result(self):
        """Test Hardcover result normalization."""
        raw = {
            "title": "Test Book",
            "authors": ["Author One"],
            "year": 2000,
            "isbn": ["1234567890"],
            "cover_url": "https://example.com/cover.jpg",
            "genres": ["Fiction", "Drama"],
            "description": "A test book.",
            "pages": 250,
            "source": "hardcover",
            "source_ids": {"hardcover_id": 123},
        }

        result = self.service._normalize_hardcover_result(raw)

        self.assertEqual(result["title"], "Test Book")
        self.assertEqual(result["year"], 2000)
        self.assertEqual(result["pages"], 250)
        self.assertEqual(result["genres"], ["Fiction", "Drama"])


class BookMetadataServiceFallbackTests(TestCase):
    """Tests for fallback behavior between sources."""

    @mock.patch("books.hardcover.get_api")
    def test_fallback_to_second_source(self, mock_get_hardcover):
        """Test fallback to second source when first fails."""
        mock_hardcover = mock.Mock()
        mock_hardcover.get_book_info.return_value = None
        mock_get_hardcover.return_value = mock_hardcover

        service = book_metadata.BookMetadataService(
            use_hardcover=True, hardcover_token="token"
        )

        with mock.patch.object(
            openlibrary.OpenLibraryApi, "get_book_info"
        ) as mock_ol:
            mock_ol.return_value = {
                "title": "Fallback Book",
                "authors": [],
                "first_publish_year": 2000,
                "isbn": [],
                "subjects": [],
            }

            result = service.get_book_info("Test", prefer_source="hardcover")

            # Should have tried Hardcover first, then fallen back to OpenLibrary
            mock_hardcover.get_book_info.assert_called_once()
            mock_ol.assert_called_once()
            self.assertEqual(result["title"], "Fallback Book")

    @mock.patch("books.hardcover.get_api")
    def test_handles_source_exception(self, mock_get_hardcover):
        """Test service handles exceptions from sources gracefully."""
        mock_hardcover = mock.Mock()
        mock_hardcover.get_book_info.side_effect = Exception("API Error")
        mock_get_hardcover.return_value = mock_hardcover

        service = book_metadata.BookMetadataService(
            use_hardcover=True, hardcover_token="token"
        )

        with mock.patch.object(
            openlibrary.OpenLibraryApi, "get_book_info"
        ) as mock_ol:
            mock_ol.return_value = {
                "title": "Recovered Book",
                "authors": [],
                "isbn": [],
                "subjects": [],
            }

            result = service.get_book_info("Test", prefer_source="hardcover")

            # Should have recovered to OpenLibrary
            self.assertEqual(result["title"], "Recovered Book")


class BookMetadataServiceGetServiceTests(TestCase):
    """Tests for get_service factory function."""

    def test_get_service_creates_instance(self):
        """Test get_service creates BookMetadataService instance."""
        service = book_metadata.get_service(use_hardcover=False)

        self.assertIsInstance(service, book_metadata.BookMetadataService)

    @mock.patch("books.hardcover.get_api")
    def test_get_service_with_hardcover_token(self, mock_get_api):
        """Test get_service with hardcover token."""
        mock_get_api.return_value = mock.Mock()

        service = book_metadata.get_service(
            use_hardcover=True, hardcover_token="test_token"
        )

        self.assertTrue(service.hardcover_available)
