import threading
from unittest import mock

from django.test import SimpleTestCase, override_settings

from .. import igdb


class DummyResponse:

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or []

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError("Request failed")


class IgbdApiTests(SimpleTestCase):

    def setUp(self):
        from collections import OrderedDict

        self.api = igdb.IgbdApi.__new__(igdb.IgbdApi)
        self.api.headers = {}
        self.api.company_cache = OrderedDict()
        self.api.game_cache = OrderedDict()
        self.api.genre_cache = OrderedDict()
        self.api.series_cache = OrderedDict()
        self.api.company_cache_max_size = 1000
        self.api.game_cache_max_size = 1000
        self.api.genre_cache_max_size = 500
        self.api.series_cache_max_size = 500
        self.api.release_date_statuses = {}
        self.api.release_dates = {}
        self.api.themes = {1: "Action"}
        # Thread safety locks
        self.api.rate_limit_lock = threading.Lock()
        self.api.cache_lock = threading.Lock()
        # Rate limiting attributes
        self.api.use_pro_tier = False
        self.api.min_request_interval = 1.0 / 3.8
        self.api.last_request_time = 0.0

    @mock.patch.object(igdb.IgbdApi, "_get_themes")
    @mock.patch.object(igdb.IgbdApi, "_get_release_statuses")
    @mock.patch.object(igdb.IgbdApi, "_get_auth_token")
    def test_init_calls_helpers(self, auth_mock, status_mock, theme_mock):
        auth_mock.return_value = True
        api = igdb.IgbdApi("cid", "secret")
        auth_mock.assert_called_once()
        status_mock.assert_called_once()
        theme_mock.assert_called_once()
        self.assertEqual(api.client_id, "cid")

    @override_settings(IGDB_CLIENT_ID="cid")
    def test_auth_token_success_updates_headers(self):
        self.api.client_id = "cid"
        self.api.client_secret = "secret"
        response = mock.Mock()
        response.json.return_value = {"access_token": "token"}
        with mock.patch("games.igdb.requests.post", return_value=response):
            self.assertTrue(self.api._get_auth_token())
        self.assertEqual(
            self.api.headers,
            {
                "Client-Id": "cid",
                "Authorization": "Bearer token",
            },
        )

    @override_settings(IGDB_CLIENT_ID="cid")
    def test_auth_token_failure_returns_false(self):
        self.api.client_id = "cid"
        self.api.client_secret = "secret"
        response = mock.Mock()
        response.json.return_value = {}
        with mock.patch("games.igdb.requests.post", return_value=response):
            self.assertFalse(self.api._get_auth_token())

    def test_get_game_info_fetches_related_data(self):
        def fake_post(url, headers=None, data=None):
            if "games" in url:
                return DummyResponse(
                    200,
                    [
                        {
                            "id": 1,
                            "slug": "sample",
                            "url": "https://example.com",
                            "cover": {"url": "//images/cover.jpg"},
                            "themes": [1],
                            "genres": [{"id": 2, "name": "Adventure"}],
                            "summary": "Summary",
                            "storyline": "Story",
                            "involved_companies": [
                                {
                                    "company": 5,
                                    "developer": True,
                                    "supporting": False,
                                    "publisher": False,
                                    "porting": False,
                                }
                            ],
                        }
                    ],
                )
            if "companies" in url:
                return DummyResponse(
                    200, [{"id": 5, "name": "Foo", "slug": "foo", "parent": None}]
                )
            if "release_date_statuses" in url:
                return DummyResponse(200, [{"name": "released", "id": 1}])
            if "themes" in url:
                return DummyResponse(200, [{"id": 1, "name": "Action"}])
            if "oauth2" in url:
                return DummyResponse(200, {"access_token": "token"})
            return DummyResponse(200, [])

        with mock.patch("games.igdb.requests.post", side_effect=fake_post):
            result = self.api.get_game_info_by_id(1, cache_results=False)

        self.assertEqual(result["slug"], "sample")
        self.assertEqual(result["cover"], "cover.jpg")
        self.assertEqual(result["developers"][0]["name"], "Foo")
        self.assertIn("Action", result["genres"])
        self.assertIn("Adventure", result["genres"])

    def test_company_lookup_caches_result(self):
        response = DummyResponse(
            200, [{"id": 5, "name": "Foo", "slug": "foo", "parent": None}]
        )
        with mock.patch("games.igdb.requests.post", return_value=response) as post:
            company = self.api._get_company_by_id(5, cache_results=True)
            self.assertEqual(company["name"], "Foo")
            self.api._get_company_by_id(5, cache_results=True)
        self.assertEqual(post.call_count, 1)

    def test_cover_helper_returns_filename(self):
        response = DummyResponse(200, [{"url": "//images/cover.jpg"}])
        with mock.patch("games.igdb.requests.post", return_value=response):
            name = self.api._get_cover_by_id(1)
        self.assertEqual(name, "cover.jpg")

    def test_cover_helper_handles_error(self):
        with mock.patch("games.igdb.requests.post", side_effect=ValueError("boom")):
            self.assertIsNone(self.api._get_cover_by_id(1))

    def test_cover_helper_handles_unexpected_length(self):
        response = DummyResponse(200, [])
        with mock.patch("games.igdb.requests.post", return_value=response):
            self.assertIsNone(self.api._get_cover_by_id(1))

    def test_genre_lookup_handles_errors(self):
        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(500, [])
        ):
            result = self.api._get_genre_by_id(1, cache_results=False)
        self.assertIsNone(result)

    def test_genre_lookup_uses_cache(self):
        self.api.genre_cache = {2: "Indie"}
        self.assertEqual(self.api._get_genre_by_id(2, cache_results=True), "Indie")

    def test_genre_lookup_handles_unexpected_response(self):
        response = DummyResponse(200, [])
        with mock.patch("games.igdb.requests.post", return_value=response):
            self.assertIsNone(self.api._get_genre_by_id(5, cache_results=False))

    def test_release_status_fetch_handles_errors(self):
        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(500, [])
        ):
            self.api._get_release_statuses()
        self.assertEqual(self.api.release_date_statuses, {})

    def test_release_status_fetch_populates_cache_on_success(self):
        payload = [{"id": 7, "name": "rumored"}]
        # Set headers so the method doesn't skip
        self.api.headers = {"Authorization": "Bearer test"}
        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, payload)
        ):
            self.api._get_release_statuses()
        self.assertEqual(self.api.release_date_statuses, {"rumored": 7})

    def test_theme_fetch_handles_errors(self):
        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(500, [])
        ):
            self.api._get_themes()
        self.assertEqual(self.api.themes, {})

    def test_theme_fetch_populates_cache_on_success(self):
        payload = [{"id": 1, "name": "Action"}]
        # Set headers so the method doesn't skip
        self.api.headers = {"Authorization": "Bearer test"}
        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, payload)
        ):
            self.api._get_themes()
        self.assertEqual(self.api.themes, {1: "Action"})

    def test_get_game_info_handles_401_and_refreshes_token(self):
        call_state = {"attempts": 0}

        def fake_post(url, headers=None, data=None):
            if "games" in url:
                call_state["attempts"] += 1
                if call_state["attempts"] == 1:
                    return DummyResponse(401, [])
                return DummyResponse(
                    200,
                    [
                        {
                            "id": 1,
                            "slug": "sample",
                            "url": "https://example.com",
                            "cover": {"url": "//images/cover.jpg"},
                            "themes": [],
                            "genres": [],
                            "summary": "",
                            "storyline": "",
                            "involved_companies": [],
                        }
                    ],
                )
            if "oauth2" in url:
                return DummyResponse(200, {"access_token": "token"})
            return DummyResponse(200, [])

        with mock.patch("games.igdb.requests.post", side_effect=fake_post):
            with mock.patch.object(
                self.api, "_get_auth_token", return_value=True
            ) as auth:
                result = self.api.get_game_info_by_id(1, cache_results=False)

        self.assertEqual(result["slug"], "sample")
        auth.assert_called_once()

    def test_get_game_info_returns_none_when_token_refresh_fails(self):

        def fake_post(url, headers=None, data=None):
            if "games" in url:
                return DummyResponse(401, [])
            return DummyResponse(200, [])

        with mock.patch("games.igdb.requests.post", side_effect=fake_post):
            with mock.patch.object(self.api, "_get_auth_token", return_value=False):
                self.assertIsNone(self.api.get_game_info_by_id(1, cache_results=False))

    def test_get_game_info_falls_back_to_supporters(self):
        game_payload = [
            {
                "id": 2,
                "slug": "support-game",
                "url": "https://example.com/support-game",
                "cover": {"url": "//images/cover.jpg"},
                "themes": [],
                "genres": [{"id": 1, "name": "Adventure"}],
                "summary": "",
                "storyline": "",
                "involved_companies": [
                    {
                        "company": 9,
                        "developer": False,
                        "supporting": True,
                        "publisher": False,
                        "porting": False,
                    }
                ],
            }
        ]

        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, game_payload)
        ):
            # Mock get_companies_by_ids to return batch data
            # Company ID 9 from the test payload, with parent ID 10
            def mock_get_companies(ids, cache=True):
                data = {
                    9: {"name": "Support Co", "slug": "support", "parent": 10},
                    10: {"name": "Parent Co", "slug": "parent", "parent": None},
                }
                return {k: v for k, v in data.items() if k in ids}

            with mock.patch.object(
                self.api, "get_companies_by_ids", side_effect=mock_get_companies
            ):
                result = self.api.get_game_info_by_id(2, cache_results=False)

        self.assertEqual(result["developers"][0]["name"], "Support Co")
        self.assertEqual(result["developers"][0]["parent"]["name"], "Parent Co")
        self.assertIn("Adventure", result["genres"])

    def test_get_game_info_falls_back_to_publishers_then_porters(self):
        game_payload = [
            {
                "id": 3,
                "slug": "publisher-game",
                "url": "https://example.com/publisher-game",
                "cover": {"url": "//images/cover.jpg"},
                "themes": [],
                "genres": [],
                "summary": "",
                "storyline": "",
                "involved_companies": [
                    {
                        "company": 7,
                        "developer": False,
                        "supporting": False,
                        "publisher": True,
                        "porting": False,
                    }
                ],
            }
        ]

        porter_payload = [
            {
                "id": 4,
                "slug": "porter-game",
                "url": "https://example.com/porter-game",
                "cover": {"url": "//images/cover.jpg"},
                "themes": [],
                "genres": [],
                "summary": "",
                "storyline": "",
                "involved_companies": [
                    {
                        "company": 8,
                        "developer": False,
                        "supporting": False,
                        "publisher": False,
                        "porting": True,
                    }
                ],
            }
        ]

        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, game_payload)
        ), mock.patch.object(
            self.api,
            "get_companies_by_ids",
            return_value={7: {"name": "Pub Co", "slug": "pub", "parent": None}},
        ):
            publisher_result = self.api.get_game_info_by_id(3, cache_results=False)

        self.assertEqual(publisher_result["developers"][0]["name"], "Pub Co")

        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, porter_payload)
        ), mock.patch.object(
            self.api,
            "get_companies_by_ids",
            return_value={8: {"name": "Port Co", "slug": "port", "parent": None}},
        ):
            porter_result = self.api.get_game_info_by_id(4, cache_results=False)

        self.assertEqual(porter_result["developers"][0]["name"], "Port Co")

    def test_get_game_info_skips_missing_company_records(self):
        game_payload = [
            {
                "id": 5,
                "slug": "missing-dev",
                "url": "https://example.com/missing",
                "cover": {"url": "//images/cover.jpg"},
                "themes": [],
                "genres": [],
                "summary": "",
                "storyline": "",
                "involved_companies": [
                    {
                        "company": 42,
                        "developer": True,
                        "supporting": False,
                        "publisher": False,
                        "porting": False,
                    }
                ],
            }
        ]
        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, game_payload)
        ), mock.patch.object(self.api, "get_companies_by_ids", return_value={}):
            result = self.api.get_game_info_by_id(5, cache_results=False)

        self.assertEqual(result["developers"], [])

    def test_get_game_info_uses_cache(self):
        cached = {"slug": "cached"}
        self.api.game_cache = {9: cached}
        with mock.patch("games.igdb.requests.post") as post:
            result = self.api.get_game_info_by_id(9, cache_results=True)
        self.assertIs(result, cached)
        post.assert_not_called()

    def test_company_lookup_handles_errors(self):
        with mock.patch("games.igdb.requests.post", side_effect=ValueError("boom")):
            self.assertIsNone(self.api._get_company_by_id(1, cache_results=False))

    def test_company_lookup_handles_unexpected_length(self):
        response = DummyResponse(200, [])
        with mock.patch("games.igdb.requests.post", return_value=response):
            self.assertIsNone(self.api._get_company_by_id(1, cache_results=False))

    def test_wait_for_rate_limit_enforces_delay(self):
        """Test that _wait_for_rate_limit() enforces minimum delay."""
        self.api.last_request_time = 0
        self.api.min_request_interval = 0.1  # 100ms minimum

        self.api._wait_for_rate_limit()
        first_call_time = self.api.last_request_time

        # Make immediate second call - should be delayed
        self.api._wait_for_rate_limit()
        second_call_time = self.api.last_request_time

        # Verify delay was applied (~100ms)
        self.assertGreaterEqual(second_call_time - first_call_time, 0.09)

    def test_make_request_with_retry_success(self):
        """Test that _make_request_with_retry() returns successful response."""
        response = DummyResponse(200, [{"id": 1, "name": "Test"}])
        with mock.patch("games.igdb.requests.post", return_value=response):
            result = self.api._make_request_with_retry("http://test.com", "data")

        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 200)

    def test_make_request_with_retry_handles_429_with_backoff(self):
        """Test retry with exponential backoff on 429 rate limit errors."""
        # First two calls return 429 (rate limited), third succeeds
        responses = [
            DummyResponse(429, []),
            DummyResponse(429, []),
            DummyResponse(200, [{"id": 1}]),
        ]
        response_iter = iter(responses)

        def mock_post(*args, **kwargs):
            return next(response_iter)

        with mock.patch("games.igdb.requests.post", side_effect=mock_post):
            with mock.patch("time.sleep") as sleep_mock:
                result = self.api._make_request_with_retry(
                    "http://test.com", "data", max_retries=3
                )

        # Should have succeeded on third attempt
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 200)

        # Verify exponential backoff was applied
        self.assertGreaterEqual(sleep_mock.call_count, 2)
        # Check that exponential backoff values (1 and 2) are called
        sleep_calls = [call[0][0] for call in sleep_mock.call_args_list]
        self.assertIn(1, sleep_calls)  # 2^0
        self.assertIn(2, sleep_calls)  # 2^1

    def test_make_request_with_retry_exhausts_retries(self):
        """Test retry exhaustion returns None when max retries exceeded."""
        response = DummyResponse(429, [])
        with mock.patch("games.igdb.requests.post", return_value=response):
            with mock.patch("time.sleep"):
                result = self.api._make_request_with_retry(
                    "http://test.com", "data", max_retries=2
                )

        # Should return None after exhausting retries
        self.assertIsNone(result)

    def test_make_request_with_retry_handles_request_exception(self):
        """Test request exception handling returns None gracefully."""
        import requests

        with mock.patch(
            "games.igdb.requests.post",
            side_effect=requests.RequestException("Connection error"),
        ):
            result = self.api._make_request_with_retry("http://test.com", "data")

        self.assertIsNone(result)

    def test_get_api_handles_failures(self):
        fake_instance = object()
        with mock.patch("games.igdb.IgbdApi", return_value=fake_instance):
            self.assertIs(igdb.get_api(), fake_instance)

        with mock.patch("games.igdb.IgbdApi", side_effect=ValueError("boom")):
            with self.assertLogs("games.igdb", level="ERROR") as cm:
                self.assertIsNone(igdb.get_api())
            self.assertIn("Failed to initialize IGDB API: boom", cm.output[0])

    @mock.patch.object(igdb.IgbdApi, "_get_themes")
    @mock.patch.object(igdb.IgbdApi, "_get_release_statuses")
    @mock.patch.object(igdb.IgbdApi, "_get_auth_token")
    def test_init_with_pro_tier_sets_faster_rate_limit(
        self, auth_mock, status_mock, theme_mock
    ):
        """Test that Pro tier initialization sets higher rate limit."""
        auth_mock.return_value = True
        api = igdb.IgbdApi("cid", "secret", use_pro_tier=True)
        self.assertTrue(api.use_pro_tier)
        # Pro tier should have much smaller interval (~0.4ms vs ~263ms)
        self.assertLess(api.min_request_interval, 0.001)

    @mock.patch.object(igdb.IgbdApi, "_get_themes")
    @mock.patch.object(igdb.IgbdApi, "_get_release_statuses")
    @mock.patch.object(igdb.IgbdApi, "_get_auth_token")
    def test_init_without_pro_tier_uses_standard_rate_limit(
        self, auth_mock, status_mock, theme_mock
    ):
        """Test that free tier initialization uses standard rate limit."""
        auth_mock.return_value = True
        api = igdb.IgbdApi("cid", "secret", use_pro_tier=False)
        self.assertFalse(api.use_pro_tier)
        # Free tier should be around 263ms between requests
        self.assertGreater(api.min_request_interval, 0.2)

    def test_get_endpoint_url_uses_pro_path_when_enabled(self):
        """Test that _get_endpoint_url returns Pro tier path when enabled."""
        self.api.use_pro_tier = True
        url = self.api._get_endpoint_url("games")
        self.assertEqual(url, "https://api.igdb.com/pro/v4/games/")

    def test_get_endpoint_url_uses_standard_path_when_disabled(self):
        """Test that _get_endpoint_url returns standard path for free tier."""
        self.api.use_pro_tier = False
        url = self.api._get_endpoint_url("games")
        self.assertEqual(url, "https://api.igdb.com/v4/games/")

    def test_get_companies_by_ids_batches_requests(self):
        """Test that get_companies_by_ids fetches multiple companies at once."""
        company_data = [
            {"id": 1, "name": "Company1", "slug": "company1", "parent": None},
            {"id": 2, "name": "Company2", "slug": "company2", "parent": None},
        ]
        response = DummyResponse(200, company_data)

        with mock.patch("games.igdb.requests.post", return_value=response):
            result = self.api.get_companies_by_ids([1, 2], cache_results=False)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["name"], "Company1")
        self.assertEqual(result[2]["name"], "Company2")

    def test_get_companies_by_ids_uses_cache(self):
        """Test that get_companies_by_ids uses cached data when available."""
        self.api.company_cache = {1: {"id": 1, "name": "Cached", "slug": "cached"}}

        result = self.api.get_companies_by_ids([1], cache_results=True)

        self.assertEqual(result[1]["name"], "Cached")

    def test_get_games_info_by_ids_batches_requests(self):
        """Test that get_games_info_by_ids fetches multiple games at once."""
        game_data = [
            {
                "id": 1,
                "slug": "game1",
                "url": "http://example.com/game1",
                "cover": {"url": "//images/cover1.jpg"},
                "genres": [{"id": 1, "name": "Action"}],
                "themes": [],
                "summary": "Summary 1",
                "storyline": "Story 1",
                "involved_companies": [],
            },
            {
                "id": 2,
                "slug": "game2",
                "url": "http://example.com/game2",
                "cover": {"url": "//images/cover2.jpg"},
                "genres": [{"id": 2, "name": "Adventure"}],
                "themes": [],
                "summary": "Summary 2",
                "storyline": "Story 2",
                "involved_companies": [],
            },
        ]

        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, game_data)
        ):
            result = self.api.get_games_info_by_ids([1, 2], cache_results=False)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["slug"], "game1")
        self.assertEqual(result[2]["slug"], "game2")
        self.assertEqual(result[1]["cover"], "cover1.jpg")
        self.assertEqual(result[2]["cover"], "cover2.jpg")

    def test_get_games_info_by_ids_uses_cache(self):
        """Test that get_games_info_by_ids uses cached data when available."""
        from collections import OrderedDict

        cached_data = {"slug": "cached", "cover": "cached.jpg"}
        self.api.game_cache = OrderedDict({1: cached_data})

        result = self.api.get_games_info_by_ids([1], cache_results=True)

        self.assertEqual(result[1]["slug"], "cached")

    def test_company_cache_lru_eviction(self):
        """Test that company cache evicts oldest entries when max size reached."""
        from collections import OrderedDict

        # Fill cache to max size
        self.api.company_cache = OrderedDict(
            {i: {"id": i, "name": f"Company {i}"} for i in range(1000)}
        )

        # Add one more - should evict the oldest (0)
        with self.api.cache_lock:
            self.api._set_in_company_cache(1000, {"id": 1000, "name": "Company 1000"})

        self.assertEqual(len(self.api.company_cache), 1000)
        self.assertNotIn(0, self.api.company_cache)
        self.assertIn(1000, self.api.company_cache)

    def test_game_cache_lru_eviction(self):
        """Test that game cache evicts oldest entries when max size reached."""
        from collections import OrderedDict

        # Fill cache to max size
        self.api.game_cache = OrderedDict(
            {i: {"id": i, "slug": f"game-{i}"} for i in range(1000)}
        )

        # Add one more - should evict the oldest (0)
        with self.api.cache_lock:
            self.api._set_in_game_cache(1000, {"id": 1000, "slug": "game-1000"})

        self.assertEqual(len(self.api.game_cache), 1000)
        self.assertNotIn(0, self.api.game_cache)
        self.assertIn(1000, self.api.game_cache)

    def test_genre_cache_lru_eviction(self):
        """Test that genre cache evicts oldest entries when max size reached."""
        from collections import OrderedDict

        # Fill cache to max size
        self.api.genre_cache = OrderedDict({i: f"Genre {i}" for i in range(500)})

        # Add one more - should evict the oldest (0)
        with self.api.cache_lock:
            self.api._set_in_genre_cache(500, "Genre 500")

        self.assertEqual(len(self.api.genre_cache), 500)
        self.assertNotIn(0, self.api.genre_cache)
        self.assertIn(500, self.api.genre_cache)

    def test_cache_lru_access_moves_to_end(self):
        """Test that accessing cached items moves them to end (most recently used)."""
        from collections import OrderedDict

        # Set up cache with items
        self.api.company_cache = OrderedDict(
            {1: {"id": 1, "name": "Company 1"}, 2: {"id": 2, "name": "Company 2"}}
        )

        # Access first item - should move to end
        with self.api.cache_lock:
            result = self.api._get_from_company_cache(1)

        self.assertIsNotNone(result)
        # Check that item 1 is now at the end (last item in OrderedDict)
        self.assertEqual(list(self.api.company_cache.keys())[-1], 1)

    def test_genre_cache_miss_returns_none(self):
        """Test that genre cache miss returns None (line 140)."""
        self.api.genre_cache = {}
        result = self.api._get_from_genre_cache(999)
        self.assertIsNone(result)

    def test_get_themes_returns_none_from_request(self):
        """Test _get_themes when request returns None (lines 301-302)."""
        self.api.headers = {"Authorization": "Bearer test"}
        with mock.patch.object(self.api, "_make_request_with_retry", return_value=None):
            self.api._get_themes()
        self.assertEqual(self.api.themes, {})

    def test_get_themes_exception_handling(self):
        """Test _get_themes exception handling (lines 305-308)."""
        self.api.headers = {"Authorization": "Bearer test"}
        response = DummyResponse(200, [])
        response.raise_for_status = mock.Mock(side_effect=Exception("Test error"))
        with mock.patch.object(
            self.api, "_make_request_with_retry", return_value=response
        ):
            self.api._get_themes()
        self.assertEqual(self.api.themes, {})

    def test_get_release_statuses_returns_none_from_request(self):
        """Test _get_release_statuses when request returns None (lines 333-334)."""
        self.api.headers = {"Authorization": "Bearer test"}
        with mock.patch.object(self.api, "_make_request_with_retry", return_value=None):
            self.api._get_release_statuses()
        self.assertEqual(self.api.release_date_statuses, {})

    def test_get_release_statuses_exception_handling(self):
        """Test _get_release_statuses exception handling (lines 337-340)."""
        self.api.headers = {"Authorization": "Bearer test"}
        response = DummyResponse(200, [])
        response.raise_for_status = mock.Mock(side_effect=Exception("Test error"))
        with mock.patch.object(
            self.api, "_make_request_with_retry", return_value=response
        ):
            self.api._get_release_statuses()
        self.assertEqual(self.api.release_date_statuses, {})

    def test_get_cover_by_id_returns_none_when_request_returns_none(self):
        """Test _get_cover_by_id returns None when request returns None (line 360)."""
        with mock.patch.object(self.api, "_make_request_with_retry", return_value=None):
            result = self.api._get_cover_by_id(123)
        self.assertIsNone(result)

    def test_get_company_by_id_returns_none_when_request_returns_none(self):
        """Test _get_company_by_id returns None when request returns None (line 401)."""
        with mock.patch.object(self.api, "_make_request_with_retry", return_value=None):
            result = self.api._get_company_by_id(123, cache_results=False)
        self.assertIsNone(result)

    def test_get_genre_by_id_returns_none_when_request_returns_none(self):
        """Test _get_genre_by_id returns None when request returns None (line 446)."""
        with mock.patch.object(self.api, "_make_request_with_retry", return_value=None):
            result = self.api._get_genre_by_id(123, cache_results=False)
        self.assertIsNone(result)

    def test_get_genre_by_id_caches_successful_result(self):
        """Test _get_genre_by_id caches result on success (lines 457-461)."""
        response = DummyResponse(200, [{"id": 5, "name": "RPG"}])
        with mock.patch("games.igdb.requests.post", return_value=response):
            result = self.api._get_genre_by_id(5, cache_results=True)
        self.assertEqual(result, "RPG")
        self.assertEqual(self.api.genre_cache[5], "RPG")

    def test_get_companies_by_ids_returns_when_request_returns_none(self):
        """Test get_companies_by_ids when request returns None."""
        # Pre-cache one company
        self.api.company_cache = {1: {"id": 1, "name": "Cached Co"}}
        with mock.patch.object(self.api, "_make_request_with_retry", return_value=None):
            result = self.api.get_companies_by_ids([1, 2], cache_results=True)
        # Should return cached result only
        self.assertEqual(len(result), 1)
        self.assertEqual(result[1]["name"], "Cached Co")

    def test_get_companies_by_ids_exception_handling(self):
        """Test get_companies_by_ids exception handling (lines 510-512)."""
        response = DummyResponse(200, [])
        response.raise_for_status = mock.Mock(side_effect=Exception("Test error"))
        with mock.patch.object(
            self.api, "_make_request_with_retry", return_value=response
        ):
            result = self.api.get_companies_by_ids([1, 2], cache_results=False)
        self.assertEqual(result, {})

    def test_get_games_info_by_ids_empty_returns_empty_dict(self):
        """Test get_games_info_by_ids with empty list returns {} (line 550)."""
        result = self.api.get_games_info_by_ids([], cache_results=False)
        self.assertEqual(result, {})

    def test_get_games_info_by_ids_returns_when_request_returns_none(self):
        """Test get_games_info_by_ids when request returns None."""
        # Pre-cache one game
        cached_game = {"slug": "cached-game", "cover": "cached.jpg"}
        self.api.game_cache = {1: cached_game}
        with mock.patch.object(self.api, "_make_request_with_retry", return_value=None):
            result = self.api.get_games_info_by_ids([1, 2], cache_results=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[1]["slug"], "cached-game")

    def test_get_games_info_by_ids_exception_handling(self):
        """Test get_games_info_by_ids exception handling (lines 585-587)."""
        response = DummyResponse(200, [])
        response.raise_for_status = mock.Mock(side_effect=Exception("Test error"))
        with mock.patch.object(
            self.api, "_make_request_with_retry", return_value=response
        ):
            result = self.api.get_games_info_by_ids([1, 2], cache_results=False)
        self.assertEqual(result, {})

    def test_get_games_info_by_ids_with_parent_company(self):
        """Test get_games_info_by_ids handles parent company (line 598)."""
        game_data = [
            {
                "id": 1,
                "slug": "game1",
                "url": "http://example.com/game1",
                "cover": {"url": "//images/cover1.jpg"},
                "genres": [],
                "themes": [],
                "summary": "Summary",
                "storyline": "Story",
                "involved_companies": [
                    {
                        "company": 10,
                        "parent": 20,  # Parent company ID in involved_companies
                        "developer": True,
                        "supporting": False,
                        "publisher": False,
                        "porting": False,
                    }
                ],
            }
        ]
        company_data = [
            {"id": 10, "name": "Child Co", "slug": "child-co", "parent": 20},
            {"id": 20, "name": "Parent Co", "slug": "parent-co", "parent": None},
        ]

        def fake_post(url, headers=None, data=None):
            if "games" in url:
                return DummyResponse(200, game_data)
            if "companies" in url:
                return DummyResponse(200, company_data)
            return DummyResponse(200, [])

        with mock.patch("games.igdb.requests.post", side_effect=fake_post):
            result = self.api.get_games_info_by_ids([1], cache_results=False)

        self.assertEqual(result[1]["developers"][0]["name"], "Child Co")
        self.assertEqual(result[1]["developers"][0]["parent"]["name"], "Parent Co")

    def test_get_games_info_by_ids_missing_company_id(self):
        """Test get_games_info_by_ids skips entries without company id (line 616)."""
        game_data = [
            {
                "id": 1,
                "slug": "game1",
                "url": "http://example.com/game1",
                "cover": None,
                "genres": [],
                "themes": [],
                "summary": "Summary",
                "storyline": "Story",
                "involved_companies": [
                    {
                        # Missing 'company' key
                        "developer": True,
                        "supporting": False,
                        "publisher": False,
                        "porting": False,
                    }
                ],
            }
        ]

        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, game_data)
        ):
            result = self.api.get_games_info_by_ids([1], cache_results=False)

        self.assertEqual(result[1]["developers"], [])

    def test_get_games_info_by_ids_supporters_fallback(self):
        """Test get_games_info_by_ids uses supporters when no developers (line 621)."""
        game_data = [
            {
                "id": 1,
                "slug": "game1",
                "url": "http://example.com/game1",
                "cover": None,
                "genres": [],
                "themes": [],
                "summary": "Summary",
                "storyline": "Story",
                "involved_companies": [
                    {
                        "company": 10,
                        "developer": False,
                        "supporting": True,
                        "publisher": False,
                        "porting": False,
                    }
                ],
            }
        ]
        company_data = [
            {"id": 10, "name": "Support Co", "slug": "support", "parent": None}
        ]

        def fake_post(url, headers=None, data=None):
            if "games" in url:
                return DummyResponse(200, game_data)
            if "companies" in url:
                return DummyResponse(200, company_data)
            return DummyResponse(200, [])

        with mock.patch("games.igdb.requests.post", side_effect=fake_post):
            result = self.api.get_games_info_by_ids([1], cache_results=False)

        self.assertEqual(result[1]["developers"][0]["name"], "Support Co")

    def test_get_games_info_by_ids_porters_fallback(self):
        """Test get_games_info_by_ids uses porters as last fallback (line 625)."""
        game_data = [
            {
                "id": 1,
                "slug": "game1",
                "url": "http://example.com/game1",
                "cover": None,
                "genres": [],
                "themes": [],
                "summary": "Summary",
                "storyline": "Story",
                "involved_companies": [
                    {
                        "company": 10,
                        "developer": False,
                        "supporting": False,
                        "publisher": False,
                        "porting": True,
                    }
                ],
            }
        ]
        company_data = [{"id": 10, "name": "Port Co", "slug": "port", "parent": None}]

        def fake_post(url, headers=None, data=None):
            if "games" in url:
                return DummyResponse(200, game_data)
            if "companies" in url:
                return DummyResponse(200, company_data)
            return DummyResponse(200, [])

        with mock.patch("games.igdb.requests.post", side_effect=fake_post):
            result = self.api.get_games_info_by_ids([1], cache_results=False)

        self.assertEqual(result[1]["developers"][0]["name"], "Port Co")

    def test_get_games_info_by_ids_missing_company_obj(self):
        """Test get_games_info_by_ids skips missing company object (line 642)."""
        game_data = [
            {
                "id": 1,
                "slug": "game1",
                "url": "http://example.com/game1",
                "cover": None,
                "genres": [],
                "themes": [],
                "summary": "Summary",
                "storyline": "Story",
                "involved_companies": [
                    {
                        "company": 99,  # Company ID that won't be found
                        "developer": True,
                        "supporting": False,
                        "publisher": False,
                        "porting": False,
                    }
                ],
            }
        ]

        def fake_post(url, headers=None, data=None):
            if "games" in url:
                return DummyResponse(200, game_data)
            if "companies" in url:
                return DummyResponse(200, [])  # No company data returned
            return DummyResponse(200, [])

        with mock.patch("games.igdb.requests.post", side_effect=fake_post):
            result = self.api.get_games_info_by_ids([1], cache_results=False)

        self.assertEqual(result[1]["developers"], [])

    def test_get_game_info_by_id_returns_none_when_request_returns_none(self):
        """Test get_game_info_by_id returns None when request returns None."""
        with mock.patch.object(self.api, "_make_request_with_retry", return_value=None):
            result = self.api.get_game_info_by_id(123, cache_results=False)
        self.assertIsNone(result)

    def test_get_game_info_by_id_caches_successful_result(self):
        """Test get_game_info_by_id caches result on success (lines 838-839)."""
        game_payload = [
            {
                "id": 99,
                "slug": "cache-test",
                "url": "https://example.com/cache-test",
                "cover": None,
                "themes": [],
                "genres": [],
                "summary": "",
                "storyline": "",
                "involved_companies": [],
            }
        ]
        self.api.game_cache = {}  # Clear cache

        with mock.patch(
            "games.igdb.requests.post", return_value=DummyResponse(200, game_payload)
        ):
            result = self.api.get_game_info_by_id(99, cache_results=True)

        self.assertEqual(result["slug"], "cache-test")
        self.assertIn(99, self.api.game_cache)
        self.assertEqual(self.api.game_cache[99]["slug"], "cache-test")

    @override_settings(DEBUG=False)
    def test_get_api_network_error_handling(self):
        """Test get_api handles network errors (lines 864-867)."""
        import requests

        with mock.patch(
            "games.igdb.IgbdApi", side_effect=requests.RequestException("Network error")
        ):
            with self.assertLogs("games.igdb", level="ERROR") as cm:
                result = igdb.get_api()
        self.assertIsNone(result)
        self.assertIn("Network error", cm.output[0])

    def test_series_cache_get_and_set(self):
        """Test series cache get and set behavior."""
        self.api.series_cache[1] = {"id": 1, "name": "Series One"}

        result = self.api._get_from_series_cache(1)
        self.assertEqual(result, {"id": 1, "name": "Series One"})

        # Update existing entry
        self.api._set_in_series_cache(1, {"id": 1, "name": "Series One Updated"})
        self.assertEqual(self.api.series_cache[1]["name"], "Series One Updated")

        # Evict oldest when full
        self.api.series_cache_max_size = 1
        self.api._set_in_series_cache(2, {"id": 2, "name": "Series Two"})
        self.assertIn(2, self.api.series_cache)
        self.assertNotIn(1, self.api.series_cache)

    def test_series_cache_miss_returns_none(self):
        """Test series cache miss returns None."""
        self.assertIsNone(self.api._get_from_series_cache(999))

    def test_get_companies_by_ids_caches_results(self):
        """Test company batch fetch stores results in cache."""
        response = DummyResponse(
            200, [{"id": 5, "name": "Foo", "slug": "foo", "parent": None}]
        )
        with mock.patch.object(
            self.api, "_make_request_with_retry", return_value=response
        ):
            result = self.api.get_companies_by_ids([5], cache_results=True)

        self.assertIn(5, result)
        self.assertIn(5, self.api.company_cache)

    def test_get_games_info_by_ids_handles_publishers_and_series(self):
        """Test batch game info handles publishers, series, videos, and caching."""
        game_payload = [
            {
                "id": 1,
                "slug": "sample-game",
                "url": "https://example.com",
                "cover": {"url": "//images/cover.jpg"},
                "themes": [1],
                "genres": [{"id": 2, "name": "Adventure"}],
                "summary": "Summary",
                "storyline": "Story",
                "involved_companies": [
                    {
                        "company": 10,
                        "developer": False,
                        "supporting": False,
                        "publisher": True,
                        "porting": False,
                    }
                ],
                "collections": [
                    {"id": 55, "name": "Series Name", "slug": "series-name"}
                ],
                "videos": [{"video_id": "vid123"}],
            }
        ]
        response = DummyResponse(200, game_payload)

        companies_initial = {
            10: {"id": 10, "name": "Pub Co", "slug": "pub", "parent": 11}
        }
        companies_parent = {
            11: {"id": 11, "name": "Parent Co", "slug": "parent", "parent": 10}
        }

        with mock.patch.object(
            self.api, "_make_request_with_retry", return_value=response
        ):
            with mock.patch.object(
                self.api,
                "get_companies_by_ids",
                side_effect=[companies_initial, companies_parent],
            ):
                result = self.api.get_games_info_by_ids([1], cache_results=True)

        game_data = result[1]
        self.assertEqual(game_data["cover"], "cover.jpg")
        self.assertEqual(game_data["youtube_video_id"], "vid123")
        self.assertEqual(game_data["series"][0]["id"], 55)
        self.assertIn(1, self.api.game_cache)
        self.assertIn(55, self.api.series_cache)

    def test_get_game_info_by_id_handles_series_and_cycles(self):
        """Test single game info handles series data and parent cycles."""
        game_payload = [
            {
                "id": 2,
                "slug": "single-game",
                "url": "https://example.com",
                "cover": {"url": "//images/cover.jpg"},
                "themes": [1],
                "genres": [{"id": 2, "name": "Adventure"}],
                "summary": "Summary",
                "storyline": "Story",
                "involved_companies": [
                    {
                        "company": 20,
                        "developer": False,
                        "supporting": False,
                        "publisher": True,
                        "porting": False,
                    }
                ],
                "collections": [{"id": 77, "name": "Series Two", "slug": "series-two"}],
                "videos": [{"video_id": "vid999"}],
            }
        ]
        response = DummyResponse(200, game_payload)

        companies_initial = {
            20: {"id": 20, "name": "Pub Two", "slug": "pub-two", "parent": 21}
        }
        companies_parent = {
            21: {"id": 21, "name": "Parent Two", "slug": "parent-two", "parent": 20}
        }

        with mock.patch.object(
            self.api, "_make_request_with_retry", return_value=response
        ):
            with mock.patch.object(
                self.api,
                "get_companies_by_ids",
                side_effect=[companies_initial, companies_parent],
            ):
                result = self.api.get_game_info_by_id(2, cache_results=True)

        self.assertEqual(result["youtube_video_id"], "vid999")
        self.assertEqual(result["series"][0]["id"], 77)
        self.assertIn(77, self.api.series_cache)


class YouTubeEmbeddableTests(SimpleTestCase):
    """Tests for YouTube video embeddability check functions."""

    @mock.patch("games.igdb.requests.get")
    def test_is_youtube_video_embeddable_empty_id(self, mock_get):
        """Empty video_id returns False without making API call."""
        result = igdb.is_youtube_video_embeddable("")
        self.assertFalse(result)
        mock_get.assert_not_called()

    @mock.patch("games.igdb.requests.get")
    def test_is_youtube_video_embeddable_none_id(self, mock_get):
        """None video_id returns False without making API call."""
        result = igdb.is_youtube_video_embeddable(None)
        self.assertFalse(result)
        mock_get.assert_not_called()

    @mock.patch("games.igdb.requests.get")
    def test_is_youtube_video_embeddable_success(self, mock_get):
        """Embeddable video returns True."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": [{"status": {"embeddable": True}}]}
        mock_get.return_value = mock_response

        result = igdb.is_youtube_video_embeddable("test123")
        self.assertTrue(result)

    @mock.patch("games.igdb.requests.get")
    def test_is_youtube_video_embeddable_not_embeddable(self, mock_get):
        """Non-embeddable video returns False."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": [{"status": {"embeddable": False}}]}
        mock_get.return_value = mock_response

        result = igdb.is_youtube_video_embeddable("test123")
        self.assertFalse(result)

    @mock.patch("games.igdb.requests.get")
    def test_is_youtube_video_embeddable_non_200(self, mock_get):
        """Non-200 response returns False."""
        mock_response = mock.Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        result = igdb.is_youtube_video_embeddable("test123")
        self.assertFalse(result)

    @mock.patch("games.igdb.requests.get")
    def test_is_youtube_video_embeddable_no_items(self, mock_get):
        """Empty items (video not found) returns False."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response

        result = igdb.is_youtube_video_embeddable("nonexistent")
        self.assertFalse(result)

    @mock.patch("games.igdb.requests.get")
    def test_is_youtube_video_embeddable_request_exception(self, mock_get):
        """RequestException returns False."""
        import requests

        mock_get.side_effect = requests.RequestException("Network error")

        result = igdb.is_youtube_video_embeddable("test123")
        self.assertFalse(result)

    @mock.patch("games.igdb.requests.get")
    def test_check_youtube_videos_embeddable_empty_list(self, mock_get):
        """Empty list returns empty dict."""
        result = igdb.check_youtube_videos_embeddable([])
        self.assertEqual(result, {})
        mock_get.assert_not_called()

    @mock.patch("games.igdb.requests.get")
    def test_check_youtube_videos_embeddable_success(self, mock_get):
        """Batch check returns correct embeddable status."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {"id": "vid1", "status": {"embeddable": True}},
                {"id": "vid2", "status": {"embeddable": False}},
            ]
        }
        mock_get.return_value = mock_response

        result = igdb.check_youtube_videos_embeddable(["vid1", "vid2", "vid3"])
        self.assertEqual(result["vid1"], True)
        self.assertEqual(result["vid2"], False)
        self.assertEqual(result["vid3"], False)  # Not in response

    @mock.patch("games.igdb.requests.get")
    def test_check_youtube_videos_embeddable_batching(self, mock_get):
        """More than 50 videos are batched correctly."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response

        # Create 75 video IDs (should make 2 API calls)
        video_ids = [f"vid{i}" for i in range(75)]
        result = igdb.check_youtube_videos_embeddable(video_ids)

        # Should have made 2 calls (50 + 25)
        self.assertEqual(mock_get.call_count, 2)
        # All should be False since not in response
        self.assertEqual(len(result), 75)
        self.assertTrue(all(v is False for v in result.values()))

    @mock.patch("games.igdb.requests.get")
    def test_check_youtube_videos_embeddable_request_exception(self, mock_get):
        """RequestException sets all videos to False."""
        import requests

        mock_get.side_effect = requests.RequestException("Network error")

        result = igdb.check_youtube_videos_embeddable(["vid1", "vid2"])
        self.assertEqual(result["vid1"], False)
        self.assertEqual(result["vid2"], False)
