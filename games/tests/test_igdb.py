from unittest import mock

from django.test import SimpleTestCase

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
        self.api = igdb.IgbdApi.__new__(igdb.IgbdApi)
        self.api.headers = {}
        self.api.company_cache = {}
        self.api.game_cache = {}
        self.api.genre_cache = {}
        self.api.release_date_statuses = {}
        self.api.release_dates = {}
        self.api.themes = {1: "Action"}

    def test_get_game_info_fetches_related_data(self):
        def fake_post(url, headers=None, data=None):
            if "games" in url:
                return DummyResponse(
                    200,
                    [
                        {
                            "slug": "sample",
                            "url": "https://example.com",
                            "cover": 10,
                            "themes": [1],
                            "genres": [2],
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
            if "covers" in url:
                return DummyResponse(200, [{"url": "//images/cover.jpg"}])
            if "genres" in url:
                return DummyResponse(200, [{"name": "Adventure"}])
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
        self.assertEqual(result["developers"][0]["name"], "Foo")
        self.assertIn("Action", result["genres"])

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
