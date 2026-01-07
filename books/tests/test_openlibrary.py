"""
Tests for the Open Library API client.

Tests cover:
- API client initialization and configuration
- Rate limiting logic
- LRU cache behavior
- Request handling with mocking
- Book search functionality
- ISBN lookup
- Work and author retrieval
- Cover URL generation
- Comprehensive book info retrieval
"""

from collections import OrderedDict
from unittest import mock

from django.test import TestCase

from books.openlibrary import (
    DEFAULT_CACHE_SIZE,
    DEFAULT_RATE_LIMIT,
    DEFAULT_REQUEST_TIMEOUT,
    OpenLibraryApi,
    get_api,
)


class OpenLibraryApiInitTests(TestCase):
    """Tests for OpenLibraryApi initialization."""

    def test_default_initialization(self):
        """Test API initializes with default values."""
        api = OpenLibraryApi()
        self.assertEqual(api.timeout, DEFAULT_REQUEST_TIMEOUT)
        self.assertEqual(api.min_request_interval, DEFAULT_RATE_LIMIT)
        self.assertEqual(api.cache_max_size, DEFAULT_CACHE_SIZE)

    def test_custom_initialization(self):
        """Test API initializes with custom values."""
        api = OpenLibraryApi(rate_limit=2.0, cache_size=100, timeout=5.0)
        self.assertEqual(api.timeout, 5.0)
        self.assertEqual(api.min_request_interval, 2.0)
        self.assertEqual(api.cache_max_size, 100)

    def test_caches_initialized_empty(self):
        """Test all caches are initialized as empty OrderedDicts."""
        api = OpenLibraryApi()
        self.assertIsInstance(api.work_cache, OrderedDict)
        self.assertIsInstance(api.edition_cache, OrderedDict)
        self.assertIsInstance(api.author_cache, OrderedDict)
        self.assertIsInstance(api.search_cache, OrderedDict)
        self.assertEqual(len(api.work_cache), 0)
        self.assertEqual(len(api.edition_cache), 0)


class CacheBehaviorTests(TestCase):
    """Tests for LRU cache behavior."""

    def test_cache_hit_returns_value(self):
        """Test cache returns value when key exists."""
        api = OpenLibraryApi()
        api.work_cache["test_key"] = {"data": "test"}
        result = api._get_from_cache(api.work_cache, "test_key")
        self.assertEqual(result, {"data": "test"})

    def test_cache_miss_returns_none(self):
        """Test cache returns None when key doesn't exist."""
        api = OpenLibraryApi()
        result = api._get_from_cache(api.work_cache, "nonexistent")
        self.assertIsNone(result)

    def test_cache_hit_updates_lru_order(self):
        """Test accessing cache item moves it to end (LRU update)."""
        api = OpenLibraryApi()
        api.work_cache["first"] = 1
        api.work_cache["second"] = 2
        api.work_cache["third"] = 3

        # Access first item, should move to end
        api._get_from_cache(api.work_cache, "first")

        keys = list(api.work_cache.keys())
        self.assertEqual(keys, ["second", "third", "first"])

    def test_set_in_cache_adds_new_item(self):
        """Test setting a new cache item."""
        api = OpenLibraryApi()
        api._set_in_cache(api.work_cache, "new_key", {"new": "data"})
        self.assertEqual(api.work_cache["new_key"], {"new": "data"})

    def test_set_in_cache_updates_existing_item(self):
        """Test updating existing cache item moves it to end."""
        api = OpenLibraryApi()
        api.work_cache["existing"] = {"old": "data"}
        api.work_cache["other"] = {"other": "data"}

        api._set_in_cache(api.work_cache, "existing", {"new": "data"})

        self.assertEqual(api.work_cache["existing"], {"new": "data"})
        keys = list(api.work_cache.keys())
        self.assertEqual(keys[-1], "existing")

    def test_set_in_cache_evicts_oldest_when_full(self):
        """Test cache evicts oldest item when at max capacity."""
        api = OpenLibraryApi(cache_size=2)
        api._set_in_cache(api.work_cache, "first", 1)
        api._set_in_cache(api.work_cache, "second", 2)
        api._set_in_cache(api.work_cache, "third", 3)

        # First should be evicted
        self.assertNotIn("first", api.work_cache)
        self.assertIn("second", api.work_cache)
        self.assertIn("third", api.work_cache)


class RateLimitingTests(TestCase):
    """Tests for rate limiting behavior."""

    @mock.patch("time.sleep")
    @mock.patch("time.time")
    def test_rate_limit_waits_when_too_fast(self, mock_time, mock_sleep):
        """Test rate limiter sleeps when requests are too fast."""
        api = OpenLibraryApi(rate_limit=1.0)
        mock_time.return_value = 0.5  # Only 0.5 seconds since last request
        api.last_request_time = 0.0

        api._wait_for_rate_limit()

        mock_sleep.assert_called_once_with(0.5)  # Should wait remaining 0.5s

    @mock.patch("time.sleep")
    @mock.patch("time.time")
    def test_rate_limit_no_wait_when_slow_enough(self, mock_time, mock_sleep):
        """Test rate limiter doesn't sleep when enough time has passed."""
        api = OpenLibraryApi(rate_limit=1.0)
        mock_time.return_value = 2.0  # 2 seconds since last request
        api.last_request_time = 0.0

        api._wait_for_rate_limit()

        mock_sleep.assert_not_called()


class MakeRequestTests(TestCase):
    """Tests for the _make_request method."""

    @mock.patch("books.openlibrary.OpenLibraryApi._wait_for_rate_limit")
    @mock.patch("requests.get")
    def test_successful_request(self, mock_get, mock_rate_limit):
        """Test successful request returns response."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = api._make_request("http://example.com")

        self.assertEqual(result, mock_response)
        mock_get.assert_called_once_with("http://example.com", timeout=api.timeout)

    @mock.patch("time.sleep")
    @mock.patch("books.openlibrary.OpenLibraryApi._wait_for_rate_limit")
    @mock.patch("requests.get")
    def test_rate_limited_retries(self, mock_get, mock_rate_limit, mock_sleep):
        """Test 429 response triggers retry with exponential backoff."""
        api = OpenLibraryApi()
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_get.side_effect = [mock_response_429, mock_response_200]

        result = api._make_request("http://example.com")

        self.assertEqual(result, mock_response_200)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(1)  # 2^0 = 1 second wait

    @mock.patch("time.sleep")
    @mock.patch("books.openlibrary.OpenLibraryApi._wait_for_rate_limit")
    @mock.patch("requests.get")
    def test_rate_limited_max_retries_exceeded(
        self, mock_get, mock_rate_limit, mock_sleep
    ):
        """Test max retries returns None when all requests are rate limited."""
        api = OpenLibraryApi()
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        mock_get.return_value = mock_response_429

        result = api._make_request("http://example.com", max_retries=2)

        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 3)  # Initial + 2 retries

    @mock.patch("requests.get")
    def test_make_request_negative_max_retries_skips_loop(self, mock_get):
        """Test negative max_retries returns None without making a request."""
        api = OpenLibraryApi()

        result = api._make_request("http://example.com", max_retries=-1)

        self.assertIsNone(result)
        mock_get.assert_not_called()

    @mock.patch("time.sleep")
    @mock.patch("books.openlibrary.OpenLibraryApi._wait_for_rate_limit")
    @mock.patch("requests.get")
    def test_request_exception_retries(self, mock_get, mock_rate_limit, mock_sleep):
        """Test request exception triggers retry."""
        import requests

        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_get.side_effect = [requests.RequestException("Connection error"), mock_response]

        result = api._make_request("http://example.com")

        self.assertEqual(result, mock_response)
        self.assertEqual(mock_get.call_count, 2)

    @mock.patch("time.sleep")
    @mock.patch("books.openlibrary.OpenLibraryApi._wait_for_rate_limit")
    @mock.patch("requests.get")
    def test_request_exception_max_retries_exceeded(
        self, mock_get, mock_rate_limit, mock_sleep
    ):
        """Test request exception returns None after max retries exhausted."""
        import requests

        api = OpenLibraryApi()
        mock_get.side_effect = requests.RequestException("Connection error")

        result = api._make_request("http://example.com", max_retries=2)

        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 3)  # Initial + 2 retries


class SearchBooksTests(TestCase):
    """Tests for search_books method."""

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_search_returns_results(self, mock_request):
        """Test search returns parsed results."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "docs": [
                {"title": "Test Book", "author_name": ["Author"]}
            ]
        }
        mock_request.return_value = mock_response

        results = api.search_books("test query")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Book")

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_search_caches_results(self, mock_request):
        """Test search results are cached."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"docs": [{"title": "Cached"}]}
        mock_request.return_value = mock_response

        # First call
        api.search_books("test", limit=5)
        # Second call should hit cache
        results = api.search_books("test", limit=5)

        self.assertEqual(mock_request.call_count, 1)  # Only one actual request
        self.assertEqual(results[0]["title"], "Cached")

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_search_returns_empty_on_failure(self, mock_request):
        """Test search returns empty list on request failure."""
        api = OpenLibraryApi()
        mock_request.return_value = None

        results = api.search_books("test query")

        self.assertEqual(results, [])

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_search_returns_empty_on_non_200(self, mock_request):
        """Test search returns empty list on non-200 status."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        results = api.search_books("test query")

        self.assertEqual(results, [])

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_search_returns_empty_on_json_error(self, mock_request):
        """Test search returns empty list when JSON parsing fails."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_response

        results = api.search_books("test query")

        self.assertEqual(results, [])


class SearchByIsbnTests(TestCase):
    """Tests for search_by_isbn method."""

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_isbn_search_returns_data(self, mock_request):
        """Test ISBN search returns book data."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "ISBN Book"}
        mock_request.return_value = mock_response

        result = api.search_by_isbn("9780123456789")

        self.assertEqual(result["title"], "ISBN Book")

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_isbn_cleans_hyphens(self, mock_request):
        """Test ISBN search removes hyphens."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Book"}
        mock_request.return_value = mock_response

        api.search_by_isbn("978-0-123-45678-9")

        # Check URL doesn't contain hyphens
        call_url = mock_request.call_args[0][0]
        self.assertIn("9780123456789", call_url)
        self.assertNotIn("-", call_url.split("/")[-1].replace(".json", ""))

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_isbn_caches_result(self, mock_request):
        """Test ISBN lookup is cached."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Cached Book"}
        mock_request.return_value = mock_response

        api.search_by_isbn("1234567890")
        api.search_by_isbn("1234567890")

        self.assertEqual(mock_request.call_count, 1)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_isbn_returns_none_on_json_error(self, mock_request):
        """Test ISBN returns None when JSON parsing fails."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_response

        result = api.search_by_isbn("1234567890")

        self.assertIsNone(result)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_isbn_returns_none_on_request_failure(self, mock_request):
        """Test ISBN returns None when request fails."""
        api = OpenLibraryApi()
        mock_request.return_value = None

        result = api.search_by_isbn("1234567890")

        self.assertIsNone(result)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_isbn_returns_none_on_non_200(self, mock_request):
        """Test ISBN returns None on non-200 status."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        result = api.search_by_isbn("1234567890")

        self.assertIsNone(result)


class GetWorkTests(TestCase):
    """Tests for get_work method."""

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_work_returns_data(self, mock_request):
        """Test get_work returns work data."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Work Title",
            "description": "A description"
        }
        mock_request.return_value = mock_response

        result = api.get_work("OL12345W")

        self.assertEqual(result["title"], "Work Title")

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_work_normalizes_id(self, mock_request):
        """Test work ID is normalized to include /works/ prefix."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Work"}
        mock_request.return_value = mock_response

        api.get_work("OL12345W")

        call_url = mock_request.call_args[0][0]
        self.assertIn("/works/OL12345W", call_url)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_work_already_prefixed(self, mock_request):
        """Test work ID with prefix is not double-prefixed."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Work"}
        mock_request.return_value = mock_response

        api.get_work("/works/OL12345W")

        call_url = mock_request.call_args[0][0]
        self.assertNotIn("/works//works/", call_url)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_work_caches_result(self, mock_request):
        """Test work lookup is cached."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Cached Work"}
        mock_request.return_value = mock_response

        api.get_work("OL123W")
        api.get_work("OL123W")

        self.assertEqual(mock_request.call_count, 1)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_work_returns_none_on_failure(self, mock_request):
        """Test get_work returns None on request failure."""
        api = OpenLibraryApi()
        mock_request.return_value = None

        result = api.get_work("OL123W")

        self.assertIsNone(result)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_work_returns_none_on_non_200(self, mock_request):
        """Test get_work returns None on non-200 status."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        result = api.get_work("OL123W")

        self.assertIsNone(result)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_work_returns_none_on_json_error(self, mock_request):
        """Test get_work returns None when JSON parsing fails."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_response

        result = api.get_work("OL123W")

        self.assertIsNone(result)


class GetAuthorTests(TestCase):
    """Tests for get_author method."""

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_author_returns_data(self, mock_request):
        """Test get_author returns author data."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Author Name"}
        mock_request.return_value = mock_response

        result = api.get_author("OL12345A")

        self.assertEqual(result["name"], "Author Name")

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_author_normalizes_id(self, mock_request):
        """Test author ID is normalized to include /authors/ prefix."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Author"}
        mock_request.return_value = mock_response

        api.get_author("OL12345A")

        call_url = mock_request.call_args[0][0]
        self.assertIn("/authors/OL12345A", call_url)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_author_caches_result(self, mock_request):
        """Test author lookup is cached."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Cached Author"}
        mock_request.return_value = mock_response

        api.get_author("OL123A")
        api.get_author("OL123A")

        self.assertEqual(mock_request.call_count, 1)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_author_returns_none_on_failure(self, mock_request):
        """Test get_author returns None on request failure."""
        api = OpenLibraryApi()
        mock_request.return_value = None

        result = api.get_author("OL123A")

        self.assertIsNone(result)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_author_returns_none_on_non_200(self, mock_request):
        """Test get_author returns None on non-200 status."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        result = api.get_author("OL123A")

        self.assertIsNone(result)

    @mock.patch.object(OpenLibraryApi, "_make_request")
    def test_get_author_returns_none_on_json_error(self, mock_request):
        """Test get_author returns None when JSON parsing fails."""
        api = OpenLibraryApi()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_response

        result = api.get_author("OL123A")

        self.assertIsNone(result)


class GetCoverUrlTests(TestCase):
    """Tests for get_cover_url method."""

    def test_cover_url_format(self):
        """Test cover URL is correctly formatted."""
        api = OpenLibraryApi()

        url = api.get_cover_url(12345, size="M")

        self.assertEqual(
            url, "https://covers.openlibrary.org/b/id/12345-M.jpg"
        )

    def test_cover_url_different_sizes(self):
        """Test cover URL with different sizes."""
        api = OpenLibraryApi()

        url_s = api.get_cover_url(12345, size="S")
        url_l = api.get_cover_url(12345, size="L")

        self.assertIn("-S.jpg", url_s)
        self.assertIn("-L.jpg", url_l)

    def test_cover_url_by_isbn(self):
        """Test cover URL by ISBN."""
        api = OpenLibraryApi()

        url = api.get_cover_url("9780123456789", id_type="isbn")

        self.assertEqual(
            url, "https://covers.openlibrary.org/b/isbn/9780123456789-M.jpg"
        )


class GetBookInfoTests(TestCase):
    """Tests for get_book_info method."""

    @mock.patch.object(OpenLibraryApi, "get_work")
    @mock.patch.object(OpenLibraryApi, "search_books")
    def test_get_book_info_returns_comprehensive_data(
        self, mock_search, mock_get_work
    ):
        """Test get_book_info returns all expected fields."""
        api = OpenLibraryApi()
        mock_search.return_value = [
            {
                "title": "Test Book",
                "author_name": ["Author One"],
                "author_key": ["OL1A"],
                "first_publish_year": 2020,
                "isbn": ["9780123456789"],
                "cover_i": 12345,
                "subject": ["Fiction"],
                "publisher": ["Publisher"],
                "key": "/works/OL1W",
                "number_of_pages_median": 300,
                "language": ["eng"],
            }
        ]
        mock_get_work.return_value = {"description": "A great book"}

        result = api.get_book_info("Test Book", "Author One")

        self.assertEqual(result["title"], "Test Book")
        self.assertEqual(result["authors"], ["Author One"])
        self.assertEqual(result["first_publish_year"], 2020)
        self.assertIn("9780123456789", result["isbn"])
        self.assertIsNotNone(result["cover_url"])
        self.assertEqual(result["description"], "A great book")

    @mock.patch.object(OpenLibraryApi, "search_books")
    def test_get_book_info_no_results_returns_none(self, mock_search):
        """Test get_book_info returns None when no results found."""
        api = OpenLibraryApi()
        mock_search.return_value = []

        result = api.get_book_info("Nonexistent Book")

        self.assertIsNone(result)

    @mock.patch.object(OpenLibraryApi, "get_work")
    @mock.patch.object(OpenLibraryApi, "search_books")
    def test_get_book_info_scores_author_match_highest(
        self, mock_search, mock_get_work
    ):
        """Test scoring prioritizes author match when author is specified."""
        api = OpenLibraryApi()
        mock_search.return_value = [
            {"title": "Wrong Author Book", "author_name": ["Wrong Author"], "key": ""},
            {"title": "Right Author Book", "author_name": ["Target Author"], "key": ""},
        ]
        mock_get_work.return_value = None

        result = api.get_book_info("Book", "Target Author")

        # Should pick the one with matching author
        self.assertEqual(result["authors"], ["Target Author"])

    @mock.patch.object(OpenLibraryApi, "get_work")
    @mock.patch.object(OpenLibraryApi, "search_books")
    def test_get_book_info_description_dict_format(
        self, mock_search, mock_get_work
    ):
        """Test description extraction from dict format."""
        api = OpenLibraryApi()
        mock_search.return_value = [
            {"title": "Book", "key": "/works/OL1W"}
        ]
        mock_get_work.return_value = {
            "description": {"type": "/type/text", "value": "Nested description"}
        }

        result = api.get_book_info("Book")

        self.assertEqual(result["description"], "Nested description")

    @mock.patch.object(OpenLibraryApi, "get_work")
    @mock.patch.object(OpenLibraryApi, "search_books")
    def test_get_book_info_title_starts_with_match(
        self, mock_search, mock_get_work
    ):
        """Test scoring boosts title that starts with search term."""
        api = OpenLibraryApi()
        mock_search.return_value = [
            {"title": "Adventures in Space", "key": ""},
            {"title": "Test Book Extended", "key": ""},  # Starts with "Test"
        ]
        mock_get_work.return_value = None

        result = api.get_book_info("Test")

        # Should prefer title starting with search term
        self.assertEqual(result["title"], "Test Book Extended")

    @mock.patch.object(OpenLibraryApi, "get_work")
    @mock.patch.object(OpenLibraryApi, "search_books")
    def test_get_book_info_prefers_older_publications(
        self, mock_search, mock_get_work
    ):
        """Test scoring boosts publications before 2000."""
        api = OpenLibraryApi()
        mock_search.return_value = [
            {"title": "Classic Book", "first_publish_year": 1985, "key": ""},
            {"title": "Classic Book Reprint", "first_publish_year": 2020, "key": ""},
        ]
        mock_get_work.return_value = None

        result = api.get_book_info("Classic Book")

        # Should prefer the older publication
        self.assertEqual(result["first_publish_year"], 1985)

    @mock.patch.object(OpenLibraryApi, "get_work")
    @mock.patch.object(OpenLibraryApi, "search_books")
    def test_get_book_info_defaults_to_first_result(
        self, mock_search, mock_get_work
    ):
        """Test defaults to first result when no matching scores."""
        api = OpenLibraryApi()
        mock_search.return_value = [
            {"title": "Completely Different 1", "key": ""},
            {"title": "Completely Different 2", "key": ""},
        ]
        mock_get_work.return_value = None

        result = api.get_book_info("Not Found Title", "Unknown Author")

        # Should default to first result
        self.assertEqual(result["title"], "Completely Different 1")


class GetApiFactoryTests(TestCase):
    """Tests for get_api factory function."""

    def test_get_api_returns_instance(self):
        """Test get_api returns an OpenLibraryApi instance."""
        api = get_api()
        self.assertIsInstance(api, OpenLibraryApi)

    def test_get_api_with_custom_params(self):
        """Test get_api passes custom parameters."""
        api = get_api(rate_limit=2.0, cache_size=100)
        self.assertEqual(api.min_request_interval, 2.0)
        self.assertEqual(api.cache_max_size, 100)
