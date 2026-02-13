"""Tests for the Wikipedia genre scraping service."""

from unittest import mock

import requests
from django.test import SimpleTestCase

from games.services.wiki_genre_service import (
    GenreResult,
    GenreSource,
    WikiGenreService,
)


class DummyResponse:
    """Mock response object for testing."""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("Request failed")


class WikiGenreServiceTests(SimpleTestCase):
    """Tests for WikiGenreService class."""

    def setUp(self):
        """Set up test service with minimal delay."""
        self.service = WikiGenreService(delay=0.0)

    def test_init_sets_defaults(self):
        """Test that initialization sets default values."""
        service = WikiGenreService()
        self.assertEqual(service.delay, 1.0)
        self.assertIn("AcclaimedGamesBot", service.user_agent)
        self.assertIsNotNone(service.session)

    def test_init_custom_values(self):
        """Test that initialization accepts custom values."""
        callback = mock.Mock()
        service = WikiGenreService(
            delay=2.0,
            user_agent="CustomBot/1.0",
            progress_callback=callback,
        )
        self.assertEqual(service.delay, 2.0)
        self.assertEqual(service.user_agent, "CustomBot/1.0")
        self.assertEqual(service.progress_callback, callback)

    def test_search_wikipedia_finds_page_with_video_game_suffix(self):
        """Test that Wikipedia search finds page with (video game) suffix."""
        mock_response = DummyResponse(
            200,
            [
                "Tetris (video game)",
                ["Tetris (video game)"],
                [""],
                ["https://en.wikipedia.org/wiki/Tetris_(video_game)"],
            ],
        )

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            url = self.service._search_wikipedia("Tetris")

        self.assertEqual(url, "https://en.wikipedia.org/wiki/Tetris_(video_game)")

    def test_search_wikipedia_skips_disambiguation(self):
        """Test that disambiguation pages are skipped."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First search returns disambiguation
                return DummyResponse(
                    200,
                    [
                        "Doom (disambiguation)",
                        ["Doom (disambiguation)"],
                        [""],
                        ["https://en.wikipedia.org/wiki/Doom_(disambiguation)"],
                    ],
                )
            else:
                # Second search (video game) variant
                return DummyResponse(
                    200,
                    [
                        "Doom (1993 video game)",
                        ["Doom (1993 video game)"],
                        [""],
                        ["https://en.wikipedia.org/wiki/Doom_(1993_video_game)"],
                    ],
                )

        with mock.patch.object(self.service.session, "get", side_effect=side_effect):
            url = self.service._search_wikipedia("Doom")

        self.assertEqual(url, "https://en.wikipedia.org/wiki/Doom_(1993_video_game)")

    def test_search_wikipedia_returns_none_when_not_found(self):
        """Test that None is returned when page is not found."""
        mock_response = DummyResponse(200, ["NonExistentGame", [], [], []])

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            url = self.service._search_wikipedia("NonExistentGame")

        self.assertIsNone(url)

    def test_scrape_infobox_genres_extracts_ordered_list(self):
        """Test that infobox scraping extracts ordered genre list."""
        html = """
        <html>
        <table class="infobox">
            <tr>
                <th>Genre(s)</th>
                <td><a href="/wiki/Action">Action</a>, <a href="/wiki/RPG">RPG</a></td>
            </tr>
        </table>
        </html>
        """
        mock_response = DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )

        self.assertEqual(genres, ["Action", "RPG"])

    def test_scrape_infobox_genres_handles_br_tags(self):
        """Test that <br> tags are handled as separators."""
        html = """
        <html>
        <table class="infobox">
            <tr>
                <th>Genre</th>
                <td>Action-adventure<br/>Survival horror<br/>Shooter</td>
            </tr>
        </table>
        </html>
        """
        mock_response = DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )

        self.assertEqual(genres, ["Action-adventure", "Survival horror", "Shooter"])

    def test_scrape_infobox_genres_handles_list_items(self):
        """Test that <li> list items are handled."""
        html = """
        <html>
        <table class="infobox">
            <tr>
                <th>Genre</th>
                <td>
                    <ul>
                        <li>First-person shooter</li>
                        <li>Action-adventure</li>
                    </ul>
                </td>
            </tr>
        </table>
        </html>
        """
        mock_response = DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )

        self.assertEqual(genres, ["First-person shooter", "Action-adventure"])

    def test_scrape_infobox_genres_cleans_references(self):
        """Test that reference marks are cleaned from genre text."""
        html = """
        <html>
        <table class="infobox">
            <tr>
                <th>Genre</th>
                <td>Action-adventure<sup>[1]</sup>, RPG<sup>[a]</sup></td>
            </tr>
        </table>
        </html>
        """
        mock_response = DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )

        self.assertEqual(genres, ["Action-adventure", "RPG"])

    def test_scrape_infobox_genres_handles_missing_infobox(self):
        """Test that empty list is returned when infobox is missing."""
        html = "<html><p>Just some text without an infobox</p></html>"
        mock_response = DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )

        self.assertEqual(genres, [])

    def test_scrape_infobox_genres_handles_no_genre_row(self):
        """Test that empty list is returned when no Genre row exists."""
        html = """
        <html>
        <table class="infobox">
            <tr>
                <th>Developer</th>
                <td>Some Developer</td>
            </tr>
        </table>
        </html>
        """
        mock_response = DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )

        self.assertEqual(genres, [])

    def test_get_genre_success(self):
        """Test successful genre retrieval."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # opensearch response
                return DummyResponse(
                    200,
                    [
                        "Tetris (video game)",
                        ["Tetris (video game)"],
                        [""],
                        ["https://en.wikipedia.org/wiki/Tetris_(video_game)"],
                    ],
                )
            else:
                # HTML page response
                html = """
                <html>
                <table class="infobox">
                    <tr>
                        <th>Genre</th>
                        <td>Puzzle, Tile-matching</td>
                    </tr>
                </table>
                </html>
                """
                return DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", side_effect=side_effect):
            result = self.service.get_genre("Tetris")

        self.assertIsInstance(result, GenreResult)
        self.assertEqual(result.game_name, "Tetris")
        self.assertEqual(result.primary_genre, "Puzzle")
        self.assertEqual(result.all_genres, ["Puzzle", "Tile-matching"])
        self.assertEqual(result.source, GenreSource.WIKIPEDIA)
        self.assertEqual(
            result.source_url, "https://en.wikipedia.org/wiki/Tetris_(video_game)"
        )

    def test_get_genre_page_not_found(self):
        """Test result when page is not found."""
        mock_response = DummyResponse(200, ["NonExistentGame", [], [], []])

        with mock.patch.object(self.service.session, "get", return_value=mock_response):
            result = self.service.get_genre("NonExistentGame")

        self.assertEqual(result.source, GenreSource.FAILED)
        self.assertIsNone(result.primary_genre)
        self.assertEqual(result.all_genres, [])
        self.assertIn("not found", result.error_message)

    def test_get_genre_no_infobox_genres(self):
        """Test result when page exists but no genres found."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return DummyResponse(
                    200,
                    [
                        "Some Game",
                        ["Some Game"],
                        [""],
                        ["https://en.wikipedia.org/wiki/Some_Game"],
                    ],
                )
            else:
                html = """
                <html>
                <table class="infobox">
                    <tr>
                        <th>Developer</th>
                        <td>Some Dev</td>
                    </tr>
                </table>
                </html>
                """
                return DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", side_effect=side_effect):
            result = self.service.get_genre("Some Game")

        self.assertEqual(result.source, GenreSource.FAILED)
        self.assertIsNone(result.primary_genre)
        self.assertEqual(result.source_url, "https://en.wikipedia.org/wiki/Some_Game")
        self.assertIn("No genre found", result.error_message)

    def test_get_genre_fallback_to_main_page_when_year_page_has_no_genre(self):
        """Test fallback to main page when year-specific page has no genre."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            # Call 1: Search returns year-specific page
            if call_count[0] == 1:
                return DummyResponse(
                    200,
                    [
                        "Tetris (1989 video game)",
                        ["Tetris (1989 video game)"],
                        [""],
                        ["https://en.wikipedia.org/wiki/Tetris_(1989_video_game)"],
                    ],
                )
            # Call 2: Resolve redirect for year-specific page
            elif call_count[0] == 2:
                return DummyResponse(
                    200,
                    {
                        "query": {
                            "pages": {"12345": {"title": "Tetris (1989 video game)"}}
                        }
                    },
                )
            # Call 3: Year-specific page has no genre
            elif call_count[0] == 3:
                html = """
                <html>
                <table class="infobox">
                    <tr><th>Developer</th><td>Bullet-Proof Software</td></tr>
                </table>
                </html>
                """
                return DummyResponse(200, text=html)
            # Call 4: Fallback search returns main page
            elif call_count[0] == 4:
                return DummyResponse(
                    200,
                    [
                        "Tetris (video game)",
                        ["Tetris (video game)"],
                        [""],
                        ["https://en.wikipedia.org/wiki/Tetris_(video_game)"],
                    ],
                )
            # Call 5: Resolve redirect for main page
            elif call_count[0] == 5:
                return DummyResponse(
                    200,
                    {"query": {"pages": {"67890": {"title": "Tetris (video game)"}}}},
                )
            # Call 6: Main page has genre
            else:
                html = """
                <html>
                <table class="infobox">
                    <tr><th>Genre(s)</th><td>Puzzle</td></tr>
                </table>
                </html>
                """
                return DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", side_effect=side_effect):
            result = self.service.get_genre("Tetris", year=1989)

        # Should have found genre from main page
        self.assertEqual(result.source, GenreSource.WIKIPEDIA)
        self.assertEqual(result.primary_genre, "Puzzle")
        self.assertEqual(
            result.source_url, "https://en.wikipedia.org/wiki/Tetris_(video_game)"
        )

    def test_process_games_returns_counts(self):
        """Test that process_games returns correct counts."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            # Game1: success (calls 1-3)
            if call_count[0] == 1:
                return DummyResponse(
                    200,
                    ["Game1", ["Game1"], [""], ["https://en.wikipedia.org/wiki/Game1"]],
                )
            elif call_count[0] == 2:
                return DummyResponse(
                    200,
                    {"query": {"pages": {"123": {"title": "Game1"}}}},
                )
            elif call_count[0] == 3:
                infobox = "<tr><th>Genre</th><td>Action</td></tr>"
                html = f'<table class="infobox">{infobox}</table>'
                return DummyResponse(200, text=html)
            # Game2: failure (calls 4+)
            else:
                return DummyResponse(200, ["Game2", [], [], []])

        with mock.patch.object(self.service.session, "get", side_effect=side_effect):
            results, success, failures = self.service.process_games(["Game1", "Game2"])

        self.assertEqual(len(results), 2)
        self.assertEqual(success, 1)
        self.assertEqual(failures, 1)

    def test_make_request_handles_network_error(self):
        """Test that network errors are handled gracefully."""
        with mock.patch.object(
            self.service.session,
            "get",
            side_effect=requests.RequestException("Network error"),
        ):
            result = self.service._make_request("http://example.com", {})

        self.assertIsNone(result)

    def test_notify_progress_calls_callback(self):
        """Test that progress callback is called when set."""
        callback = mock.Mock()
        service = WikiGenreService(delay=0.0, progress_callback=callback)

        service._notify_progress("test_event", {"key": "value"})

        callback.assert_called_once_with("test_event", {"key": "value"})

    def test_notify_progress_handles_no_callback(self):
        """Test that no error occurs when callback is not set."""
        service = WikiGenreService(delay=0.0)
        # Should not raise any exception
        service._notify_progress("test_event", {"key": "value"})

    def test_clean_genre_text_removes_references(self):
        """Test cleaning of reference markers."""
        self.assertEqual(self.service._clean_genre_text("Action[1]"), "Action")
        self.assertEqual(self.service._clean_genre_text("RPG[a]"), "RPG")
        self.assertEqual(
            self.service._clean_genre_text("Adventure[note 1]"), "Adventure"
        )
        self.assertEqual(
            self.service._clean_genre_text("Puzzle[citation needed]"), "Puzzle"
        )

    def test_get_name_variants_no_slash(self):
        """Test that names without slash return single item list."""
        variants = self.service._get_name_variants("Super Mario Bros.")
        self.assertEqual(variants, ["Super Mario Bros."])

    def test_get_name_variants_with_slash(self):
        """Test that names with slash are split into parts."""
        variants = self.service._get_name_variants("Game A / Game B")
        self.assertEqual(variants, ["Game A", "Game B"])

    def test_get_name_variants_multiple_slashes(self):
        """Test that multiple slashes are handled."""
        variants = self.service._get_name_variants("Name 1 / Name 2 / Name 3")
        self.assertEqual(variants, ["Name 1", "Name 2", "Name 3"])

    def test_get_name_variants_preserves_order(self):
        """Test that variant order is preserved."""
        variants = self.service._get_name_variants(
            "Persona 4 / Shin Megami Tensei: Persona 4"
        )
        self.assertEqual(variants, ["Persona 4", "Shin Megami Tensei: Persona 4"])

    def test_get_name_variants_removes_duplicates(self):
        """Test that duplicate parts are removed."""
        variants = self.service._get_name_variants("Same Name / Same Name")
        self.assertEqual(variants, ["Same Name"])

    def test_get_name_variants_extracts_subtitle(self):
        """Test that subtitles are extracted as separate variants."""
        # Names with colon should also try the subtitle alone
        variants = self.service._get_name_variants(
            "Maniac Mansion II: Day of the Tentacle"
        )
        self.assertEqual(
            variants, ["Maniac Mansion II: Day of the Tentacle", "Day of the Tentacle"]
        )

    def test_get_name_variants_extracts_subtitle_from_slash_parts(self):
        """Test that subtitles are extracted from slash-separated parts."""
        variants = self.service._get_name_variants("Game A: Subtitle / Game B: Another")
        # Should include: Game A: Subtitle, Subtitle, Game B: Another, Another
        self.assertIn("Game A: Subtitle", variants)
        self.assertIn("Subtitle", variants)
        self.assertIn("Game B: Another", variants)
        self.assertIn("Another", variants)

    def test_get_name_variants_skips_short_subtitle(self):
        """Test that very short subtitles are skipped."""
        variants = self.service._get_name_variants("Game: II")
        # "II" is too short (< 5 chars), should not be added
        self.assertEqual(variants, ["Game: II"])

    def test_get_name_variants_unspaced_slash(self):
        """Test that unspaced slash names are handled correctly."""
        # Like "Pokémon Red/Blue/Yellow"
        variants = self.service._get_name_variants("Pokémon Red/Blue/Yellow")
        # Should include "Red and Blue" combination first
        self.assertIn("Pokémon Red and Blue", variants)
        self.assertIn("Pokémon Red", variants)
        # Short parts like "Blue" and "Yellow" should be skipped (< 5 chars)

    def test_get_name_variants_unspaced_slash_two_parts(self):
        """Test that unspaced slash with two parts creates 'and' combination."""
        variants = self.service._get_name_variants("Game One/Game Two")
        # Should include "Game One and Game Two" combination
        self.assertIn("Game One and Game Two", variants)
        self.assertIn("Game One", variants)
        self.assertIn("Game Two", variants)

    def test_get_name_variants_skips_short_slash_parts(self):
        """Test that short parts after slash are skipped unless first."""
        variants = self.service._get_name_variants("Long Name/ABC")
        # "ABC" (3 chars) should be skipped, but "Long Name" should be included
        self.assertIn("Long Name", variants)
        self.assertNotIn("ABC", variants)

    def test_is_video_game_page_detects_game_infobox(self):
        """Test that video game pages are detected by infobox."""
        html = """
        <html>
        <table class="infobox">
            <tr><th>Genre(s)</th><td>Action</td></tr>
            <tr><th>Developer</th><td>Some Studio</td></tr>
        </table>
        </html>
        """
        with mock.patch.object(
            self.service.session, "get", return_value=DummyResponse(200, text=html)
        ):
            self.assertTrue(self.service._is_video_game_page("http://example.com"))

    def test_is_video_game_page_rejects_non_game(self):
        """Test that non-game pages are rejected."""
        html = """
        <html>
        <table class="infobox">
            <tr><th>Born</th><td>1980</td></tr>
            <tr><th>Occupation</th><td>Actor</td></tr>
        </table>
        </html>
        """
        with mock.patch.object(
            self.service.session, "get", return_value=DummyResponse(200, text=html)
        ):
            self.assertFalse(self.service._is_video_game_page("http://example.com"))

    def test_is_video_game_page_rejects_no_infobox(self):
        """Test that pages without infobox are rejected."""
        html = "<html><body>Just some text</body></html>"
        with mock.patch.object(
            self.service.session, "get", return_value=DummyResponse(200, text=html)
        ):
            self.assertFalse(self.service._is_video_game_page("http://example.com"))

    def test_search_fallback_accepts_video_game_page(self):
        """Test fallback search accepts first video game result with different title."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1

            # Opensearch calls return list, redirect resolution returns dict,
            # page scraping returns HTML
            # Pattern: opensearch (odd), redirect (even), until non-strict mode
            # First 20 calls (10 opensearch + 10 redirect): strict search
            # variants all fail (no matching title)
            if call_count[0] <= 20:
                # Odd calls: opensearch results
                if call_count[0] % 2 == 1:
                    return DummyResponse(
                        200,
                        [
                            "Day of the Tentacle",
                            ["Day of the Tentacle"],  # Different title
                            [""],
                            ["https://en.wikipedia.org/wiki/Day_of_the_Tentacle"],
                        ],
                    )
                # Even calls: redirect resolution
                else:
                    return DummyResponse(
                        200,
                        {"query": {"pages": {"123": {"title": "Day of the Tentacle"}}}},
                    )
            # Call 21+: non-strict mode - first call is opensearch, then
            # redirect, then checking if it's a video game page
            elif call_count[0] == 21:
                # Opensearch in non-strict mode
                return DummyResponse(
                    200,
                    [
                        "Day of the Tentacle",
                        ["Day of the Tentacle"],
                        [""],
                        ["https://en.wikipedia.org/wiki/Day_of_the_Tentacle"],
                    ],
                )
            elif call_count[0] == 22:
                # Redirect resolution
                return DummyResponse(
                    200,
                    {"query": {"pages": {"123": {"title": "Day of the Tentacle"}}}},
                )
            else:
                # Call 23+: checking if it's a video game page
                html = """
                <html>
                <table class="infobox">
                    <tr><th>Genre(s)</th><td>Adventure</td></tr>
                </table>
                </html>
                """
                return DummyResponse(200, text=html)

        with mock.patch.object(self.service.session, "get", side_effect=side_effect):
            url = self.service._search_wikipedia(
                "Maniac Mansion II: Day of the Tentacle"
            )

        self.assertEqual(url, "https://en.wikipedia.org/wiki/Day_of_the_Tentacle")

    def test_is_valid_search_result_exact_match(self):
        """Test exact name match is valid."""
        self.assertTrue(self.service._is_valid_search_result("Tetris", "Tetris"))

    def test_is_valid_search_result_with_suffix(self):
        """Test match with (video game) suffix is valid."""
        self.assertTrue(
            self.service._is_valid_search_result("Tetris", "Tetris (video game)")
        )
        self.assertTrue(self.service._is_valid_search_result("Doom", "Doom (game)"))

    def test_is_valid_search_result_with_year_suffix(self):
        """Test match with year suffix is valid."""
        self.assertTrue(
            self.service._is_valid_search_result("Doom", "Doom (1993 video game)")
        )
        self.assertTrue(
            self.service._is_valid_search_result(
                "Resident Evil 4", "Resident Evil 4 (2005 video game)"
            )
        )

    def test_is_valid_search_result_rejects_wrong_page(self):
        """Test that wrong page is rejected."""
        # Searching "Resident Evil 4" should not match "Resident Evil (video game)"
        self.assertFalse(
            self.service._is_valid_search_result(
                "Resident Evil 4", "Resident Evil (video game)"
            )
        )

    def test_is_valid_search_result_partial_match(self):
        """Test partial match within result is valid."""
        self.assertTrue(self.service._is_valid_search_result("Doom", "Doom II"))

    def test_search_wikipedia_with_name_variants(self):
        """Test that search tries name variants for slash-separated names."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            # First 3 calls for "Counter-Strike" variants fail (no results)
            if call_count[0] <= 3:
                return DummyResponse(200, ["Counter-Strike", [], [], []])
            else:
                # 4th call for second variant succeeds - return Counter-Strike 1.6
                return DummyResponse(
                    200,
                    [
                        "Counter-Strike 1.6 (video game)",
                        ["Counter-Strike 1.6 (video game)"],
                        [""],
                        ["https://en.wikipedia.org/wiki/Counter-Strike_1.6"],
                    ],
                )

        with mock.patch.object(self.service.session, "get", side_effect=side_effect):
            url = self.service._search_wikipedia("Counter-Strike / Counter-Strike 1.6")

        self.assertEqual(url, "https://en.wikipedia.org/wiki/Counter-Strike_1.6")

    @mock.patch("time.sleep")
    @mock.patch("time.time")
    def test_wait_for_rate_limit_sleeps_when_needed(self, mock_time, mock_sleep):
        """Test rate limiting sleeps when calls are too close together."""
        service = WikiGenreService(delay=1.0)
        mock_time.side_effect = [0.5, 1.0]
        service.last_request_time = 0.0

        service._wait_for_rate_limit()

        mock_sleep.assert_called_once_with(0.5)

    def test_search_wikipedia_fallback_match(self):
        """Test fallback non-strict search is used when strict fails."""
        with mock.patch.object(
            self.service,
            "_search_single_name",
            side_effect=[None, "https://example.com"],
        ):
            url = self.service._search_wikipedia("Maniac Mansion II")

        self.assertEqual(url, "https://example.com")

    def test_resolve_redirect_returns_original_when_no_wiki(self):
        """Test _resolve_redirect returns original URL without /wiki/."""
        url = "https://example.com/page"
        self.assertEqual(self.service._resolve_redirect(url), url)

    def test_resolve_redirect_returns_original_on_no_response(self):
        """Test _resolve_redirect returns original URL when request fails."""
        with mock.patch.object(self.service, "_make_request", return_value=None):
            url = "https://en.wikipedia.org/wiki/Original"
            self.assertEqual(self.service._resolve_redirect(url), url)

    def test_resolve_redirect_returns_canonical(self):
        """Test _resolve_redirect returns canonical URL when different."""
        response = DummyResponse(
            200,
            {
                "query": {
                    "pages": {
                        "123": {"title": "New Title"},
                    }
                }
            },
        )
        with mock.patch.object(self.service, "_make_request", return_value=response):
            url = "https://en.wikipedia.org/wiki/Old_Title"
            resolved = self.service._resolve_redirect(url)
        self.assertEqual(resolved, "https://en.wikipedia.org/wiki/New_Title")

    def test_resolve_redirect_handles_bad_json(self):
        """Test _resolve_redirect handles JSON parsing errors."""

        class BadResponse:
            def json(self):
                raise ValueError("bad json")

        with mock.patch.object(
            self.service, "_make_request", return_value=BadResponse()
        ):
            url = "https://en.wikipedia.org/wiki/Old_Title"
            self.assertEqual(self.service._resolve_redirect(url), url)

    def test_search_single_name_handles_no_response(self):
        """Test _search_single_name skips when response is None."""
        with mock.patch.object(self.service, "_make_request", return_value=None):
            url = self.service._search_single_name("Test Game")
        self.assertIsNone(url)

    def test_search_single_name_handles_invalid_response_type(self):
        """Test _search_single_name handles invalid response types."""
        response = DummyResponse(200, {"bad": "data"})
        with mock.patch.object(self.service, "_make_request", return_value=response):
            url = self.service._search_single_name("Test Game")
        self.assertIsNone(url)

    def test_search_single_name_skips_year_mismatch(self):
        """Test _search_single_name skips results with mismatched year."""
        response = DummyResponse(
            200,
            [
                "Test Game (1999 video game)",
                ["Test Game (1999 video game)"],
                [""],
                ["https://en.wikipedia.org/wiki/Test_Game_(1999_video_game)"],
            ],
        )
        call_state = {"count": 0}

        def fake_request(*args, **kwargs):
            call_state["count"] += 1
            if call_state["count"] == 1:
                return response
            return None

        with mock.patch.object(self.service, "_make_request", side_effect=fake_request):
            url = self.service._search_single_name("Test Game", year=2000)
        self.assertIsNone(url)

    def test_search_single_name_non_strict_requires_video_game_page(self):
        """Test non-strict search requires a video game page."""
        response = DummyResponse(
            200,
            [
                "Test Game",
                ["Test Game"],
                [""],
                ["https://en.wikipedia.org/wiki/Test_Game"],
            ],
        )
        with mock.patch.object(self.service, "_make_request", return_value=response):
            with mock.patch.object(
                self.service, "_is_video_game_page", return_value=False
            ):
                url = self.service._search_single_name("Test Game", strict=False)
        self.assertIsNone(url)

    def test_search_single_name_handles_json_error(self):
        """Test _search_single_name handles JSON parsing errors."""

        class BadResponse:
            def json(self):
                raise ValueError("bad json")

        with mock.patch.object(
            self.service, "_make_request", return_value=BadResponse()
        ):
            url = self.service._search_single_name("Test Game")
        self.assertIsNone(url)

    def test_is_video_game_page_returns_false_on_no_response(self):
        """Test _is_video_game_page returns False when response is None."""
        with mock.patch.object(self.service, "_make_request", return_value=None):
            self.assertFalse(self.service._is_video_game_page("https://example.com"))

    def test_is_video_game_page_detects_indicators(self):
        """Test _is_video_game_page returns True with developer indicator."""
        html = """
        <html>
        <table class="infobox">
            <tr><th>Developer</th><td>Test Studio</td></tr>
        </table>
        </html>
        """
        response = DummyResponse(200, text=html)
        with mock.patch.object(self.service, "_make_request", return_value=response):
            self.assertTrue(self.service._is_video_game_page("https://example.com"))

    def test_is_valid_search_result_remainder_empty(self):
        """Test exact match with no remainder is valid."""
        self.assertTrue(self.service._is_valid_search_result("Doom", "Doom "))

    def test_is_valid_search_result_remainder_colon(self):
        """Test match with colon remainder is valid."""
        self.assertTrue(self.service._is_valid_search_result("Doom", "Doom: Final"))

    def test_get_genre_from_url_success(self):
        """Test get_genre_from_url returns Wikipedia genre result."""
        from games.services.wiki_genre_service import GenreSource

        with mock.patch.object(
            self.service, "_scrape_infobox_genres", return_value=["RPG", "Action"]
        ):
            result = self.service.get_genre_from_url(
                "Test Game", "https://en.wikipedia.org/wiki/Test_Game"
            )

        self.assertEqual(result.source, GenreSource.WIKIPEDIA)
        self.assertEqual(result.primary_genre, "RPG")
        self.assertEqual(result.all_genres, ["RPG", "Action"])

    def test_scrape_infobox_genres_returns_empty_on_no_response(self):
        """Test _scrape_infobox_genres returns [] when response is None."""
        with mock.patch.object(self.service, "_make_request", return_value=None):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )
        self.assertEqual(genres, [])

    def test_scrape_infobox_genres_handles_missing_data_cell(self):
        """Test _scrape_infobox_genres skips rows without data cell."""
        html = """
        <html>
        <table class="infobox">
            <tr><th>Genre</th></tr>
        </table>
        </html>
        """
        response = DummyResponse(200, text=html)
        with mock.patch.object(self.service, "_make_request", return_value=response):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )
        self.assertEqual(genres, [])

    def test_scrape_infobox_genres_removes_hidden_content(self):
        """Test _scrape_infobox_genres removes hidden content."""
        html = """
        <html>
        <table class="infobox">
            <tr>
                <th>Genre</th>
                <td>Action<span class="reference">[1]</span>
                    <span style="display:none">Hidden</span>
                </td>
            </tr>
        </table>
        </html>
        """
        response = DummyResponse(200, text=html)
        with mock.patch.object(self.service, "_make_request", return_value=response):
            genres = self.service._scrape_infobox_genres(
                "https://en.wikipedia.org/wiki/Test"
            )
        self.assertEqual(genres, ["Action"])

    def test_get_genre_from_url_returns_failed_on_no_genres(self):
        """Test get_genre_from_url returns FAILED when no genres found."""
        with mock.patch.object(self.service, "_scrape_infobox_genres", return_value=[]):
            result = self.service.get_genre_from_url(
                "Test Game", "https://en.wikipedia.org/wiki/Test"
            )
        self.assertEqual(result.source, GenreSource.FAILED)


class GenreResultTests(SimpleTestCase):
    """Tests for GenreResult dataclass."""

    def test_genre_result_creation(self):
        """Test GenreResult can be created with required fields."""
        result = GenreResult(
            game_name="Test Game",
            source=GenreSource.WIKIPEDIA,
            primary_genre="Action",
            all_genres=["Action", "RPG", "Adventure"],
        )
        self.assertEqual(result.game_name, "Test Game")
        self.assertEqual(result.primary_genre, "Action")
        self.assertEqual(result.all_genres, ["Action", "RPG", "Adventure"])
        self.assertEqual(result.source, GenreSource.WIKIPEDIA)
        self.assertIsNone(result.source_url)
        self.assertIsNone(result.error_message)

    def test_genre_result_all_genres_str(self):
        """Test all_genres_str property."""
        result = GenreResult(
            game_name="Test Game",
            source=GenreSource.WIKIPEDIA,
            all_genres=["Action", "RPG", "Adventure"],
        )
        self.assertEqual(result.all_genres_str, "Action, RPG, Adventure")

    def test_genre_result_all_genres_str_empty(self):
        """Test all_genres_str with empty list."""
        result = GenreResult(
            game_name="Test Game",
            source=GenreSource.FAILED,
            all_genres=[],
        )
        self.assertEqual(result.all_genres_str, "")

    def test_genre_result_backwards_compatibility(self):
        """Test backwards compatibility properties."""
        result = GenreResult(
            game_name="Test Game",
            source=GenreSource.WIKIPEDIA,
            primary_genre="Action",
        )
        # genre property should alias primary_genre
        self.assertEqual(result.genre, "Action")
        # wikidata_id should return None (deprecated)
        self.assertIsNone(result.wikidata_id)

    def test_genre_result_with_error(self):
        """Test GenreResult with error message."""
        result = GenreResult(
            game_name="Test Game",
            source=GenreSource.FAILED,
            error_message="Page not found",
        )
        self.assertEqual(result.error_message, "Page not found")
        self.assertIsNone(result.primary_genre)
        self.assertEqual(result.all_genres, [])


class GenreSourceTests(SimpleTestCase):
    """Tests for GenreSource enum."""

    def test_genre_source_values(self):
        """Test GenreSource enum has correct values."""
        self.assertEqual(GenreSource.WIKIPEDIA.value, "Wikipedia")
        self.assertEqual(GenreSource.FAILED.value, "Failed")
