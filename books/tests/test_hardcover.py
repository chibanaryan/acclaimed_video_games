"""
Tests for the Hardcover GraphQL API client.

Tests cover:
- API client initialization and authentication
- Rate limiting logic
- LRU cache behavior
- GraphQL request handling
- Book search functionality
- Book lookup by ID and ISBN
- Comprehensive book info retrieval
"""

from collections import OrderedDict
from unittest import mock

from django.test import TestCase, override_settings

from books.hardcover import (
    DEFAULT_CACHE_SIZE,
    DEFAULT_RATE_LIMIT,
    DEFAULT_REQUEST_TIMEOUT,
    HardcoverApi,
    get_api,
)


class HardcoverApiInitTests(TestCase):
    """Tests for HardcoverApi initialization."""

    def test_default_initialization(self):
        """Test API initializes with default values."""
        api = HardcoverApi(api_token="test_token")
        self.assertEqual(api.timeout, DEFAULT_REQUEST_TIMEOUT)
        self.assertEqual(api.min_request_interval, DEFAULT_RATE_LIMIT)
        self.assertEqual(api.cache_max_size, DEFAULT_CACHE_SIZE)
        self.assertEqual(api.api_token, "test_token")

    def test_custom_initialization(self):
        """Test API initializes with custom values."""
        api = HardcoverApi(
            api_token="custom_token",
            rate_limit=2.0,
            cache_size=100,
            timeout=15.0
        )
        self.assertEqual(api.timeout, 15.0)
        self.assertEqual(api.min_request_interval, 2.0)
        self.assertEqual(api.cache_max_size, 100)

    def test_headers_set_correctly(self):
        """Test authorization headers are set correctly."""
        api = HardcoverApi(api_token="my_token")
        self.assertEqual(api.headers["Authorization"], "Bearer my_token")
        self.assertEqual(api.headers["Content-Type"], "application/json")

    def test_caches_initialized_empty(self):
        """Test all caches are initialized as empty OrderedDicts."""
        api = HardcoverApi(api_token="token")
        self.assertIsInstance(api.book_cache, OrderedDict)
        self.assertIsInstance(api.author_cache, OrderedDict)
        self.assertIsInstance(api.search_cache, OrderedDict)
        self.assertEqual(len(api.book_cache), 0)


class CacheBehaviorTests(TestCase):
    """Tests for LRU cache behavior."""

    def test_cache_hit_returns_value(self):
        """Test cache returns value when key exists."""
        api = HardcoverApi(api_token="token")
        api.book_cache["test_key"] = {"data": "test"}
        result = api._get_from_cache(api.book_cache, "test_key")
        self.assertEqual(result, {"data": "test"})

    def test_cache_miss_returns_none(self):
        """Test cache returns None when key doesn't exist."""
        api = HardcoverApi(api_token="token")
        result = api._get_from_cache(api.book_cache, "nonexistent")
        self.assertIsNone(result)

    def test_cache_evicts_oldest_when_full(self):
        """Test cache evicts oldest item when at max capacity."""
        api = HardcoverApi(api_token="token", cache_size=2)
        api._set_in_cache(api.book_cache, "first", 1)
        api._set_in_cache(api.book_cache, "second", 2)
        api._set_in_cache(api.book_cache, "third", 3)

        self.assertNotIn("first", api.book_cache)
        self.assertIn("second", api.book_cache)
        self.assertIn("third", api.book_cache)

    def test_cache_updates_existing_key(self):
        """Test setting existing cache key updates value."""
        api = HardcoverApi(api_token="token", cache_size=3)
        api._set_in_cache(api.book_cache, "key1", "value1")
        api._set_in_cache(api.book_cache, "key2", "value2")
        # Update existing key
        api._set_in_cache(api.book_cache, "key1", "updated_value1")

        self.assertEqual(api.book_cache["key1"], "updated_value1")
        self.assertEqual(len(api.book_cache), 2)


class RateLimitingTests(TestCase):
    """Tests for rate limiting behavior."""

    @mock.patch("time.sleep")
    @mock.patch("time.time")
    def test_rate_limit_waits_when_too_fast(self, mock_time, mock_sleep):
        """Test rate limiter sleeps when requests are too fast."""
        api = HardcoverApi(api_token="token", rate_limit=1.0)
        mock_time.return_value = 0.5
        api.last_request_time = 0.0

        api._wait_for_rate_limit()

        mock_sleep.assert_called_once_with(0.5)


class MakeRequestTests(TestCase):
    """Tests for the _make_request method."""

    @mock.patch("books.hardcover.HardcoverApi._wait_for_rate_limit")
    @mock.patch("requests.post")
    def test_successful_graphql_request(self, mock_post, mock_rate_limit):
        """Test successful GraphQL request returns data."""
        api = HardcoverApi(api_token="token")
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"books": []}}
        mock_post.return_value = mock_response

        result = api._make_request("query { books { id } }")

        self.assertEqual(result, {"books": []})
        mock_post.assert_called_once()

    @mock.patch("books.hardcover.HardcoverApi._wait_for_rate_limit")
    @mock.patch("requests.post")
    def test_request_with_variables(self, mock_post, mock_rate_limit):
        """Test request includes variables in payload."""
        api = HardcoverApi(api_token="token")
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {}}
        mock_post.return_value = mock_response

        api._make_request("query { }", variables={"id": 123})

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        self.assertIn("variables", payload)
        self.assertEqual(payload["variables"]["id"], 123)

    @mock.patch("time.sleep")
    @mock.patch("books.hardcover.HardcoverApi._wait_for_rate_limit")
    @mock.patch("requests.post")
    def test_rate_limited_retries(self, mock_post, mock_rate_limit, mock_sleep):
        """Test 429 response triggers retry."""
        api = HardcoverApi(api_token="token")
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"data": {"result": "ok"}}
        mock_post.side_effect = [mock_response_429, mock_response_200]

        result = api._make_request("query { }")

        self.assertEqual(result, {"result": "ok"})
        self.assertEqual(mock_post.call_count, 2)

    @mock.patch("books.hardcover.HardcoverApi._wait_for_rate_limit")
    @mock.patch("requests.post")
    def test_non_200_returns_none(self, mock_post, mock_rate_limit):
        """Test non-200 status returns None."""
        api = HardcoverApi(api_token="token")
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = api._make_request("query { }")

        self.assertIsNone(result)

    @mock.patch("books.hardcover.HardcoverApi._wait_for_rate_limit")
    @mock.patch("requests.post")
    def test_graphql_errors_returns_none(self, mock_post, mock_rate_limit):
        """Test GraphQL errors in response returns None."""
        api = HardcoverApi(api_token="token")
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": None,
            "errors": [{"message": "Not found"}]
        }
        mock_post.return_value = mock_response

        result = api._make_request("query { }")

        self.assertIsNone(result)

    @mock.patch("time.sleep")
    @mock.patch("books.hardcover.HardcoverApi._wait_for_rate_limit")
    @mock.patch("requests.post")
    def test_rate_limit_max_retries_exceeded(self, mock_post, mock_rate_limit, mock_sleep):
        """Test rate limit returns None after max retries."""
        api = HardcoverApi(api_token="token")
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        # Return 429 for all attempts (more than max_retries)
        mock_post.return_value = mock_response_429

        result = api._make_request("query { }", max_retries=2)

        self.assertIsNone(result)
        self.assertGreaterEqual(mock_post.call_count, 2)

    @mock.patch("requests.post")
    def test_make_request_negative_max_retries_skips_loop(self, mock_post):
        """Test negative max_retries returns None without making a request."""
        api = HardcoverApi(api_token="token")

        result = api._make_request("query { }", max_retries=-1)

        self.assertIsNone(result)
        mock_post.assert_not_called()


class HardcoverRequestExceptionTests(TestCase):
    """Tests for HardcoverApi request exception handling and parsing."""

    def test_get_book_by_id_handles_invalid_response(self):
        """Test invalid response data triggers parse error handling."""
        api = HardcoverApi(api_token="token")

        class BadData:
            def get(self, *args, **kwargs):
                raise ValueError("bad data")

        with mock.patch.object(HardcoverApi, "_make_request", return_value=BadData()):
            result = api.get_book_by_id("123")

        self.assertIsNone(result)

    @mock.patch("time.sleep")
    @mock.patch("books.hardcover.HardcoverApi._wait_for_rate_limit")
    @mock.patch("requests.post")
    def test_request_exception_retries(self, mock_post, mock_rate_limit, mock_sleep):
        """Test request exception triggers retry."""
        import requests

        api = HardcoverApi(api_token="token")
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"data": {"result": "success"}}
        mock_post.side_effect = [
            requests.RequestException("Connection error"),
            mock_response_200
        ]

        result = api._make_request("query { }")

        self.assertEqual(result, {"result": "success"})
        self.assertEqual(mock_post.call_count, 2)

    @mock.patch("time.sleep")
    @mock.patch("books.hardcover.HardcoverApi._wait_for_rate_limit")
    @mock.patch("requests.post")
    def test_request_exception_max_retries(self, mock_post, mock_rate_limit, mock_sleep):
        """Test request exception returns None after max retries."""
        import requests

        api = HardcoverApi(api_token="token")
        mock_post.side_effect = requests.RequestException("Connection error")

        result = api._make_request("query { }", max_retries=2)

        self.assertIsNone(result)


class SearchBooksTests(TestCase):
    """Tests for search_books method."""

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_search_returns_results(self, mock_request):
        """Test search returns parsed results."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = {
            "search": {"results": [{"title": "Test Book", "id": 1}]}
        }

        results = api.search_books("test query")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Book")

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_search_handles_json_string_results(self, mock_request):
        """Test search handles results as JSON string."""
        api = HardcoverApi(api_token="token")
        import json
        mock_request.return_value = {
            "search": {"results": json.dumps([{"title": "Book"}])}
        }

        results = api.search_books("test")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Book")

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_search_caches_results(self, mock_request):
        """Test search results are cached."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = {"search": {"results": [{"title": "Cached"}]}}

        api.search_books("test", limit=5, page=1)
        api.search_books("test", limit=5, page=1)

        self.assertEqual(mock_request.call_count, 1)

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_search_returns_empty_on_failure(self, mock_request):
        """Test search returns empty list on request failure."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = None

        results = api.search_books("test query")

        self.assertEqual(results, [])

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_search_returns_none_when_results_is_none(self, mock_request):
        """Test search returns None when results field is None."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = {"search": {"results": None}}

        results = api.search_books("test")

        self.assertIsNone(results)

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_search_returns_empty_on_missing_key(self, mock_request):
        """Test search returns empty list when key is missing."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = {"wrong_key": {}}

        results = api.search_books("test")

        self.assertEqual(results, [])

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_search_returns_empty_on_json_parse_error(self, mock_request):
        """Test search returns empty list when JSON parsing fails."""
        api = HardcoverApi(api_token="token")
        # Return invalid JSON string that will fail to parse
        mock_request.return_value = {"search": {"results": "not valid json"}}

        results = api.search_books("test")

        self.assertEqual(results, [])


class GetBookByIdTests(TestCase):
    """Tests for get_book_by_id method."""

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_get_book_by_id_returns_data(self, mock_request):
        """Test get_book_by_id returns book data."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = {
            "books": [{"id": 123, "title": "Test Book"}]
        }

        result = api.get_book_by_id(123)

        self.assertEqual(result["title"], "Test Book")

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_get_book_by_id_caches_result(self, mock_request):
        """Test book lookup is cached."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = {"books": [{"id": 123, "title": "Book"}]}

        api.get_book_by_id(123)
        api.get_book_by_id(123)

        self.assertEqual(mock_request.call_count, 1)

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_get_book_by_id_returns_none_if_not_found(self, mock_request):
        """Test get_book_by_id returns None if no books found."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = {"books": []}

        result = api.get_book_by_id(999)

        self.assertIsNone(result)

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_get_book_by_id_returns_none_on_request_failure(self, mock_request):
        """Test get_book_by_id returns None when request fails."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = None

        result = api.get_book_by_id(123)

        self.assertIsNone(result)

    @mock.patch.object(HardcoverApi, "_make_request")
    def test_get_book_by_id_returns_none_on_parse_error(self, mock_request):
        """Test get_book_by_id returns None when parsing fails."""
        api = HardcoverApi(api_token="token")
        mock_request.return_value = {"invalid": "structure"}

        result = api.get_book_by_id(123)

        self.assertIsNone(result)


class GetBookByIsbnTests(TestCase):
    """Tests for get_book_by_isbn method."""

    @mock.patch.object(HardcoverApi, "search_books")
    def test_isbn_search_returns_first_result(self, mock_search):
        """Test ISBN search returns first result."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [{"title": "ISBN Book", "id": 1}]

        result = api.get_book_by_isbn("9780123456789")

        self.assertEqual(result["title"], "ISBN Book")

    @mock.patch.object(HardcoverApi, "search_books")
    def test_isbn_returns_from_cache(self, mock_search):
        """Test ISBN lookup returns cached result."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [{"title": "Cached Book", "id": 1}]

        api.get_book_by_isbn("9780123456789")
        api.get_book_by_isbn("9780123456789")

        self.assertEqual(mock_search.call_count, 1)

    @mock.patch.object(HardcoverApi, "search_books")
    def test_isbn_cleans_hyphens(self, mock_search):
        """Test ISBN search removes hyphens."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [{"title": "Book"}]

        api.get_book_by_isbn("978-0-123-45678-9")

        mock_search.assert_called_with("9780123456789", limit=1)

    @mock.patch.object(HardcoverApi, "search_books")
    def test_isbn_returns_none_if_not_found(self, mock_search):
        """Test ISBN returns None when no results."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = []

        result = api.get_book_by_isbn("0000000000")

        self.assertIsNone(result)


class GetBookInfoTests(TestCase):
    """Tests for get_book_info method."""

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_returns_normalized_data(self, mock_search):
        """Test get_book_info returns normalized book data."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [
            {
                "id": 1,
                "title": "Test Book",
                "slug": "test-book",
                "description": "A description",
                "release_date": "2020-01-15",
                "pages": 300,
                "cached_contributors": [{"name": "Author Name"}],
                "cached_tags": [{"tag": "Fiction"}],
                "cached_image": "https://example.com/cover.jpg",
                "editions": [{"isbn_13": "9780123456789"}]
            }
        ]

        result = api.get_book_info("Test Book")

        self.assertEqual(result["title"], "Test Book")
        self.assertEqual(result["authors"], ["Author Name"])
        self.assertEqual(result["year"], 2020)
        self.assertEqual(result["genres"], ["Fiction"])
        self.assertIn("9780123456789", result["isbn"])

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_handles_missing_fields(self, mock_search):
        """Test get_book_info handles missing optional fields."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [{"id": 1, "title": "Minimal Book"}]

        result = api.get_book_info("Minimal Book")

        self.assertEqual(result["title"], "Minimal Book")
        self.assertEqual(result["authors"], [])
        self.assertIsNone(result["year"])

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_returns_none_if_no_results(self, mock_search):
        """Test get_book_info returns None when no results found."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = []

        result = api.get_book_info("Nonexistent Book")

        self.assertIsNone(result)

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_prefers_exact_title_match(self, mock_search):
        """Test scoring prefers exact title match."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [
            {"id": 1, "title": "Test Book Extended Edition"},
            {"id": 2, "title": "Test Book"},
        ]

        result = api.get_book_info("Test Book")

        self.assertEqual(result["hardcover_id"], 2)

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_extracts_authors_from_dict(self, mock_search):
        """Test author extraction from dict format."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [
            {
                "id": 1,
                "title": "Book",
                "cached_contributors": [
                    {"author": {"name": "Nested Author"}},
                    {"name": "Direct Name"},
                    "String Author"
                ]
            }
        ]

        result = api.get_book_info("Book")

        self.assertIn("Nested Author", result["authors"])
        self.assertIn("Direct Name", result["authors"])
        self.assertIn("String Author", result["authors"])

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_with_author_parameter(self, mock_search):
        """Test get_book_info includes author in query."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [{"id": 1, "title": "Test Book"}]

        api.get_book_info("Test Book", "Author Name")

        # Verify query includes both title and author
        mock_search.assert_called_with("Test Book Author Name", limit=5)

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_defaults_to_first_result(self, mock_search):
        """Test get_book_info defaults to first result when no match."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [
            {"id": 1, "title": "Completely Different"},
            {"id": 2, "title": "Also Different"},
        ]

        result = api.get_book_info("Nonexistent Title")

        # Should default to first result
        self.assertEqual(result["hardcover_id"], 1)

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_handles_string_tags(self, mock_search):
        """Test get_book_info handles tags as strings."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [
            {
                "id": 1,
                "title": "Book",
                "cached_tags": ["Fiction", "Mystery", {"tag": "Thriller"}]
            }
        ]

        result = api.get_book_info("Book")

        self.assertIn("Fiction", result["genres"])
        self.assertIn("Mystery", result["genres"])
        self.assertIn("Thriller", result["genres"])

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_extracts_isbn_10(self, mock_search):
        """Test get_book_info extracts ISBN-10 from editions."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [
            {
                "id": 1,
                "title": "Book",
                "editions": [
                    {"isbn_13": "9780123456789", "isbn_10": "0123456789"},
                    {"isbn_10": "1234567890"}
                ]
            }
        ]

        result = api.get_book_info("Book")

        self.assertIn("9780123456789", result["isbn"])
        self.assertIn("0123456789", result["isbn"])
        self.assertIn("1234567890", result["isbn"])

    @mock.patch.object(HardcoverApi, "search_books")
    def test_get_book_info_handles_invalid_release_date(self, mock_search):
        """Test get_book_info handles invalid release date gracefully."""
        api = HardcoverApi(api_token="token")
        mock_search.return_value = [
            {
                "id": 1,
                "title": "Book",
                "release_date": "invalid-date"
            }
        ]

        result = api.get_book_info("Book")

        self.assertIsNone(result["year"])


class GetApiFactoryTests(TestCase):
    """Tests for get_api factory function."""

    def test_get_api_with_explicit_token(self):
        """Test get_api returns instance with explicit token."""
        api = get_api(api_token="explicit_token")
        self.assertIsInstance(api, HardcoverApi)
        self.assertEqual(api.api_token, "explicit_token")

    @override_settings(HARDCOVER_API_TOKEN="settings_token")
    def test_get_api_reads_from_settings(self):
        """Test get_api reads token from settings."""
        api = get_api()
        self.assertIsInstance(api, HardcoverApi)
        self.assertEqual(api.api_token, "settings_token")

    def test_get_api_returns_none_without_token(self):
        """Test get_api returns None when no token available."""
        api = get_api()
        self.assertIsNone(api)

    @override_settings(HARDCOVER_API_TOKEN="token")
    def test_get_api_with_custom_params(self):
        """Test get_api passes custom parameters."""
        api = get_api(rate_limit=2.0, cache_size=100)
        self.assertEqual(api.min_request_interval, 2.0)
        self.assertEqual(api.cache_max_size, 100)
