from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from games import config
from games.services.wiki_page_lookup_service import (
    PageLookupResult,
    WikiPageLookupService,
)


class WikiPageLookupServiceUnitTests(SimpleTestCase):
    def _build_service(self, **kwargs):
        with (
            mock.patch(
                "games.services.wiki_page_lookup_service.requests.Session"
            ) as session_cls,
            mock.patch(
                "games.services.wiki_page_lookup_service.WikiGenreService"
            ) as genre_cls,
        ):
            session = mock.MagicMock()
            session_cls.return_value = session
            genre_service = mock.MagicMock()
            genre_cls.return_value = genre_service
            service = WikiPageLookupService(**kwargs)

        self.addCleanup(service.close)
        return service, session, genre_service

    def test_page_lookup_result_helpers(self):
        result = PageLookupResult(game_name="Halo")
        self.assertFalse(result.success)
        self.assertIsNone(result.wikipedia_url)

        result.page_title = "Halo Infinite"
        self.assertTrue(result.success)
        self.assertEqual(
            result.wikipedia_url,
            "https://en.wikipedia.org/wiki/Halo_Infinite",
        )

    def test_init_with_explicit_delay(self):
        service, session, _ = self._build_service(delay=0.25)

        self.assertEqual(service.delay, 0.25)
        session.headers.update.assert_called_once_with(
            {"User-Agent": config.WIKI_USER_AGENT}
        )

    def test_init_uses_authenticated_delay_when_token_present(self):
        service, _, _ = self._build_service(access_token="user:pass", delay=None)
        self.assertEqual(service.delay, config.WIKIDATA_AUTHENTICATED_DELAY)

    @override_settings(WIKIDATA_ACCESS_TOKEN=None)
    def test_init_uses_unauthenticated_delay_without_token(self):
        service, _, _ = self._build_service(delay=None)
        self.assertEqual(service.delay, config.WIKIDATA_UNAUTHENTICATED_DELAY)

    def test_context_manager_calls_close(self):
        service, _, _ = self._build_service(delay=0)
        with mock.patch.object(service, "close") as close_mock:
            with service as managed:
                self.assertIs(managed, service)
            close_mock.assert_called_once()

    def test_close_closes_both_sessions(self):
        service, session, genre_service = self._build_service(delay=0)

        service.close()

        session.close.assert_called_once()
        genre_service.close.assert_called_once()
        self.assertIsNone(service.session)
        self.assertIsNone(service.wiki_genre_service)

    def test_wait_for_rate_limit_sleeps_when_needed(self):
        service, _, _ = self._build_service(delay=2)
        service.last_request_time = 10.0

        with (
            mock.patch(
                "games.services.wiki_page_lookup_service.time.time",
                side_effect=[11.0, 15.0],
            ),
            mock.patch(
                "games.services.wiki_page_lookup_service.time.sleep"
            ) as sleep_mock,
        ):
            service._wait_for_rate_limit()

        sleep_mock.assert_called_once_with(1.0)
        self.assertEqual(service.last_request_time, 15.0)

    def test_wait_for_rate_limit_without_sleep(self):
        service, _, _ = self._build_service(delay=1)
        service.last_request_time = 10.0

        with (
            mock.patch(
                "games.services.wiki_page_lookup_service.time.time",
                side_effect=[12.0, 13.0],
            ),
            mock.patch(
                "games.services.wiki_page_lookup_service.time.sleep"
            ) as sleep_mock,
        ):
            service._wait_for_rate_limit()

        sleep_mock.assert_not_called()
        self.assertEqual(service.last_request_time, 13.0)

    def test_make_request_success_with_auth(self):
        service, session, _ = self._build_service(access_token="user:pass", delay=0)
        response = mock.MagicMock()
        session.get.return_value = response

        with mock.patch.object(service, "_wait_for_rate_limit"):
            result = service._make_request(
                "https://example.com", {"k": "v"}, use_auth=True
            )

        self.assertIs(result, response)
        session.get.assert_called_once_with(
            "https://example.com",
            params={"k": "v"},
            headers={},
            auth=("user", "pass"),
            timeout=30,
        )

    def test_make_request_invalid_auth_token_format(self):
        service, session, _ = self._build_service(access_token="invalid-token", delay=0)
        response = mock.MagicMock()
        session.get.return_value = response

        with mock.patch.object(service, "_wait_for_rate_limit"):
            service._make_request("https://example.com", use_auth=True)

        self.assertIsNone(session.get.call_args.kwargs["auth"])

    def test_make_request_retries_transient_errors_then_succeeds(self):
        service, session, _ = self._build_service(delay=0)
        response = mock.MagicMock()
        session.get.side_effect = [requests.Timeout("slow"), response]

        with (
            mock.patch.object(service, "_wait_for_rate_limit"),
            mock.patch(
                "games.services.wiki_page_lookup_service.time.sleep"
            ) as sleep_mock,
        ):
            result = service._make_request("https://example.com")

        self.assertIs(result, response)
        self.assertEqual(session.get.call_count, 2)
        sleep_mock.assert_called_once_with(1.0)

    def test_make_request_returns_none_after_transient_failures(self):
        service, session, _ = self._build_service(delay=0)
        session.get.side_effect = requests.ConnectionError("offline")

        with (
            mock.patch.object(service, "_wait_for_rate_limit"),
            mock.patch(
                "games.services.wiki_page_lookup_service.time.sleep"
            ) as sleep_mock,
        ):
            result = service._make_request("https://example.com")

        self.assertIsNone(result)
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(sleep_mock.call_count, 2)

    def test_make_request_non_retryable_error(self):
        service, session, _ = self._build_service(delay=0)
        session.get.side_effect = requests.RequestException("bad request")

        with mock.patch.object(service, "_wait_for_rate_limit"):
            result = service._make_request("https://example.com")

        self.assertIsNone(result)

    def test_make_request_loop_falls_through_to_none(self):
        service, _, _ = self._build_service(delay=0)

        with mock.patch("builtins.range", return_value=[]):
            result = service._make_request("https://example.com")

        self.assertIsNone(result)

    def test_fetch_wikidata_label_branches(self):
        service, _, _ = self._build_service(delay=0)

        with mock.patch.object(service, "_make_request", return_value=None):
            self.assertIsNone(service._fetch_wikidata_label("Q1"))

        response = mock.MagicMock()
        response.json.return_value = {
            "entities": {"Q1": {"labels": {"en": {"value": "Portal"}}}}
        }
        with mock.patch.object(service, "_make_request", return_value=response):
            self.assertEqual(service._fetch_wikidata_label("Q1"), "Portal")

        bad_response = mock.MagicMock()
        bad_response.json.side_effect = ValueError("bad json")
        with mock.patch.object(service, "_make_request", return_value=bad_response):
            self.assertIsNone(service._fetch_wikidata_label("Q1"))

    def test_get_wikidata_id_from_page_branches(self):
        service, _, _ = self._build_service(delay=0)

        self.assertIsNone(service._get_wikidata_id_from_page(""))

        with mock.patch.object(service, "_make_request", return_value=None):
            self.assertIsNone(service._get_wikidata_id_from_page("Portal"))

        response = mock.MagicMock()
        response.json.return_value = {"entities": {"-1": {}, "Q123": {}}}
        with mock.patch.object(service, "_make_request", return_value=response):
            self.assertEqual(service._get_wikidata_id_from_page("Portal"), "Q123")

        no_match = mock.MagicMock()
        no_match.json.return_value = {"entities": {"-1": {}}}
        with mock.patch.object(service, "_make_request", return_value=no_match):
            self.assertIsNone(service._get_wikidata_id_from_page("Portal"))

        bad_response = mock.MagicMock()
        bad_response.json.side_effect = ValueError("bad json")
        with mock.patch.object(service, "_make_request", return_value=bad_response):
            self.assertIsNone(service._get_wikidata_id_from_page("Portal"))

    def test_lookup_via_wikidata_branches(self):
        service, _, _ = self._build_service(delay=0)

        self.assertIsNone(service._lookup_via_wikidata(""))

        with mock.patch.object(service, "_make_request", return_value=None):
            self.assertIsNone(service._lookup_via_wikidata("Q1"))

        response = mock.MagicMock()
        response.json.return_value = {
            "entities": {
                "Q1": {
                    "sitelinks": {"enwikiquote": {"title": "Quote Page"}},
                    "claims": {
                        "P1733": [
                            {
                                "rank": "preferred",
                                "mainsnak": {"datavalue": {"value": "480"}},
                            }
                        ]
                    },
                }
            }
        }
        with mock.patch.object(service, "_make_request", return_value=response):
            page_title, hltb_id, steam_app_id, wikiquote_title = (
                service._lookup_via_wikidata("Q1")
            )

        self.assertIsNone(page_title)
        self.assertIsNone(hltb_id)
        self.assertEqual(steam_app_id, "480")
        self.assertEqual(wikiquote_title, "Quote Page")

        bad_response = mock.MagicMock()
        bad_response.json.side_effect = ValueError("bad json")
        with mock.patch.object(service, "_make_request", return_value=bad_response):
            self.assertIsNone(service._lookup_via_wikidata("Q1"))

    def test_lookup_via_wikidata_extracts_hltb_and_page_title(self):
        service, _, _ = self._build_service(delay=0)

        response = mock.MagicMock()
        response.json.return_value = {
            "entities": {
                "Q1": {
                    "sitelinks": {"enwiki": {"title": "Portal"}},
                    "claims": {
                        "P2816": [
                            {
                                "rank": "preferred",
                                "mainsnak": {"datavalue": {"value": "123"}},
                            }
                        ]
                    },
                }
            }
        }
        with mock.patch.object(service, "_make_request", return_value=response):
            page_title, hltb_id, _, _ = service._lookup_via_wikidata("Q1")

        self.assertEqual(page_title, "Portal")
        self.assertEqual(hltb_id, "123")

    def test_normalize_and_title_similarity(self):
        service, _, _ = self._build_service(delay=0)

        normalized = service._normalize_title_for_comparison("Halo (Video Game)   ")
        self.assertEqual(normalized, "halo")

        self.assertTrue(service._is_title_similar_enough("Halo", "Halo Infinite"))
        self.assertFalse(service._is_title_similar_enough("Sektori", "Sektor Gaza"))

    def test_title_similarity_with_empty_word_overlap(self):
        service, _, _ = self._build_service(delay=0)

        with mock.patch.object(
            service,
            "_normalize_title_for_comparison",
            side_effect=["alpha", "   "],
        ):
            self.assertFalse(service._is_title_similar_enough("a", "b"))

    def test_lookup_via_opensearch_branches(self):
        service, _, genre_service = self._build_service(delay=0)

        genre_service._search_wikipedia.return_value = None
        self.assertIsNone(service._lookup_via_opensearch("Game", 2024))

        genre_service._search_wikipedia.return_value = (
            "https://example.com/no-wiki-path"
        )
        self.assertIsNone(service._lookup_via_opensearch("Game", 2024))

        genre_service._search_wikipedia.return_value = (
            "https://en.wikipedia.org/wiki/Sektor_Gaza"
        )
        with mock.patch.object(service, "_is_title_similar_enough", return_value=False):
            self.assertIsNone(service._lookup_via_opensearch("Sektori", 2024))

        genre_service._search_wikipedia.return_value = (
            "https://en.wikipedia.org/wiki/Portal_2"
        )
        with mock.patch.object(service, "_is_title_similar_enough", return_value=True):
            self.assertEqual(
                service._lookup_via_opensearch("Portal 2", 2011),
                ("Portal 2", config.WIKI_LOOKUP_SOURCE_OPENSEARCH_YEAR),
            )
            self.assertEqual(
                service._lookup_via_opensearch("Portal 2", None),
                ("Portal 2", config.WIKI_LOOKUP_SOURCE_OPENSEARCH_BASIC),
            )

    def test_merge_wikidata_metadata_branches(self):
        service, _, _ = self._build_service(delay=0)

        self.assertEqual(service._merge_wikidata_metadata(None, None), {})
        self.assertEqual(service._merge_wikidata_metadata(None, {"a": 1}), {"a": 1})
        self.assertEqual(service._merge_wikidata_metadata({"a": 1}, None), {"a": 1})

        merged = service._merge_wikidata_metadata(
            {"hltb_id": "10", "steam_app_id": "20"},
            {"hltb_id": "11", "wikiquote_page_title": "Portal"},
        )
        self.assertEqual(merged["hltb_id"], "10")
        self.assertEqual(merged["steam_app_id"], "20")
        self.assertEqual(merged["wikiquote_page_title"], "Portal")

    def test_lookup_page_uses_wikidata_when_page_exists(self):
        service, _, _ = self._build_service(delay=0)

        with mock.patch.object(
            service,
            "_lookup_via_wikidata",
            return_value=("Portal", "1", "2", "Quote"),
        ):
            result = service.lookup_page("Portal", wikidata_id="Q1", year=2007)

        self.assertTrue(result.success)
        self.assertEqual(result.lookup_source, config.WIKI_LOOKUP_SOURCE_WIKIDATA)
        self.assertEqual(result.page_title, "Portal")
        self.assertEqual(result.hltb_id, "1")
        self.assertEqual(result.steam_app_id, "2")
        self.assertEqual(result.wikiquote_page_title, "Quote")

    def test_lookup_page_merges_stored_and_page_metadata(self):
        service, _, _ = self._build_service(delay=0)

        with (
            mock.patch.object(
                service,
                "_lookup_via_wikidata",
                side_effect=[
                    (None, "stored-hltb", None, "StoredQuote"),
                    (None, "page-hltb", "400", "PageQuote"),
                ],
            ),
            mock.patch.object(
                service,
                "_lookup_via_opensearch",
                side_effect=[("Portal 2", config.WIKI_LOOKUP_SOURCE_OPENSEARCH_YEAR)],
            ),
            mock.patch.object(service, "_get_wikidata_id_from_page", return_value="Q2"),
        ):
            result = service.lookup_page("Portal 2", wikidata_id="Q1", year=2011)

        self.assertTrue(result.success)
        self.assertEqual(
            result.lookup_source, config.WIKI_LOOKUP_SOURCE_OPENSEARCH_YEAR
        )
        self.assertEqual(result.page_title, "Portal 2")
        # Stored metadata should win when both are present
        self.assertEqual(result.hltb_id, "stored-hltb")
        self.assertEqual(result.steam_app_id, "400")
        self.assertEqual(result.wikiquote_page_title, "StoredQuote")

    def test_lookup_page_uses_fallback_source_without_year(self):
        service, _, _ = self._build_service(delay=0)

        with (
            mock.patch.object(service, "_lookup_via_wikidata", return_value=None),
            mock.patch.object(
                service,
                "_lookup_via_opensearch",
                side_effect=[("Portal", config.WIKI_LOOKUP_SOURCE_OPENSEARCH_BASIC)],
            ),
            mock.patch.object(service, "_get_wikidata_id_from_page", return_value="Q1"),
        ):
            result = service.lookup_page("Portal", wikidata_id=None, year=None)

        self.assertEqual(
            result.lookup_source, config.WIKI_LOOKUP_SOURCE_OPENSEARCH_FALLBACK
        )

    def test_lookup_page_returns_not_found(self):
        service, _, _ = self._build_service(delay=0)

        with (
            mock.patch.object(service, "_lookup_via_wikidata", return_value=None),
            mock.patch.object(service, "_lookup_via_opensearch", return_value=None),
        ):
            result = service.lookup_page("Unknown", wikidata_id="Q1", year=1999)

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Page not found on Wikipedia")

    def test_process_games_and_notify_progress(self):
        progress_callback = mock.MagicMock()
        service, _, _ = self._build_service(
            delay=0, progress_callback=progress_callback
        )

        with mock.patch.object(
            service,
            "lookup_page",
            side_effect=[
                PageLookupResult(
                    game_name="Good Game",
                    page_title="Good_Game",
                    lookup_source=config.WIKI_LOOKUP_SOURCE_WIKIDATA,
                ),
                PageLookupResult(
                    game_name="Bad Game",
                    error_message="Not found",
                ),
            ],
        ):
            results, success_count, failure_count = service.process_games(
                [("Good Game", "Q1", 2020), ("Bad Game", None, 2021)]
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(success_count, 1)
        self.assertEqual(failure_count, 1)
        self.assertGreaterEqual(progress_callback.call_count, 4)

    def test_notify_progress_without_callback(self):
        service, _, _ = self._build_service(delay=0, progress_callback=None)
        # Should not raise when callback is absent
        service._notify_progress("progress", {"ok": True})
