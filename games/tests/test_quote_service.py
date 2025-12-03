"""Tests for Wikiquote quote scraping service."""

import json
from unittest.mock import Mock, patch

from django.test import TestCase

from games.services.quote_service import QuoteService, QuoteSource


class QuoteServiceTest(TestCase):
    """Test quote fetching service."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = QuoteService(delay=0.0)  # No delay in tests

    @patch("requests.Session.get")
    def test_search_wikiquote_finds_page(self, mock_get):
        """Test Wikiquote page search."""
        mock_response = Mock()
        mock_response.json.return_value = [
            "Portal (video game)",
            ["Portal (video game)"],
            [""],
            ["https://en.wikiquote.org/wiki/Portal_(video_game)"],
        ]
        mock_get.return_value = mock_response

        url = self.service._search_wikiquote("Portal")

        self.assertEqual(url, "https://en.wikiquote.org/wiki/Portal_(video_game)")
        mock_get.assert_called()

    @patch("requests.Session.get")
    def test_search_wikiquote_returns_none_when_not_found(self, mock_get):
        """Test Wikiquote search returns None for non-existent game."""
        mock_response = Mock()
        mock_response.json.return_value = ["NonExistentGame", [], [], []]
        mock_get.return_value = mock_response

        url = self.service._search_wikiquote("NonExistentGame")

        self.assertIsNone(url)

    @patch("requests.Session.get")
    def test_search_skips_disambiguation_pages(self, mock_get):
        """Test that disambiguation pages are skipped."""
        mock_response = Mock()
        mock_response.json.return_value = [
            "Game (disambiguation)",
            ["Game (disambiguation)"],
            [""],
            ["https://en.wikiquote.org/wiki/Game_(disambiguation)"],
        ]
        mock_get.return_value = mock_response

        url = self.service._search_wikiquote("Game")

        self.assertIsNone(url)

    def test_get_name_variants_handles_slash_separator(self):
        """Test name variant generation for games with / in name."""
        variants = self.service._get_name_variants("Pokémon Red/Blue")

        self.assertIn("Pokémon Red and Blue", variants)
        self.assertIn("Pokémon Red", variants)

    def test_get_name_variants_handles_spaced_slash(self):
        """Test name variant generation for games with ' / ' in name."""
        variants = self.service._get_name_variants("Game A / Game B")

        self.assertIn("Game A", variants)
        self.assertIn("Game B", variants)

    def test_get_name_variants_handles_subtitle(self):
        """Test name variant generation extracts subtitles."""
        variants = self.service._get_name_variants(
            "Maniac Mansion: Day of the Tentacle"
        )

        self.assertIn("Maniac Mansion: Day of the Tentacle", variants)
        self.assertIn("Day of the Tentacle", variants)

    def test_clean_quote_text_removes_references(self):
        """Test quote cleaning removes reference markers."""
        text = self.service._clean_quote_text("This is a quote[1] with references[a]")

        self.assertEqual(text, "This is a quote with references")

    def test_clean_quote_text_removes_citation_needed(self):
        """Test quote cleaning removes [citation needed]."""
        text = self.service._clean_quote_text("A quote[citation needed] here")

        self.assertEqual(text, "A quote here")

    def test_is_valid_quote_accepts_good_quotes(self):
        """Test quote validation accepts valid quotes."""
        self.assertTrue(self.service._is_valid_quote("The cake is a lie."))
        self.assertTrue(self.service._is_valid_quote("Wake up, Mr. Freeman."))

    def test_is_valid_quote_rejects_too_short(self):
        """Test quote validation rejects quotes that are too short."""
        self.assertFalse(self.service._is_valid_quote("Hi"))

    def test_is_valid_quote_rejects_too_long(self):
        """Test quote validation rejects quotes that are too long."""
        long_text = "A" * 501
        self.assertFalse(self.service._is_valid_quote(long_text))

    def test_is_valid_quote_rejects_no_letters(self):
        """Test quote validation rejects quotes without letters."""
        self.assertFalse(self.service._is_valid_quote("123456789"))
        self.assertFalse(self.service._is_valid_quote("!!!!!!!!!"))

    def test_is_valid_quote_rejects_common_patterns(self):
        """Test quote validation rejects common non-quote patterns."""
        self.assertFalse(self.service._is_valid_quote("..."))
        self.assertFalse(self.service._is_valid_quote("!!!!"))
        self.assertFalse(self.service._is_valid_quote("????"))

    @patch("requests.Session.get")
    def test_parse_wikiquote_page_extracts_quotes(self, mock_get):
        """Test quote extraction from Wikiquote page."""
        mock_response = Mock()
        mock_response.text = """
        <html>
        <body>
        <div class="mw-parser-output">
            <h2>Dialogue</h2>
            <ul>
                <li>The cake is a lie.</li>
                <li>Hello, and again, welcome to the Aperture Science
                Computer-Aided Enrichment Center.</li>
            </ul>
            <h3>GLaDOS</h3>
            <ul>
                <li>This was a triumph.</li>
            </ul>
        </div>
        </body>
        </html>
        """
        mock_get.return_value = mock_response

        quotes = self.service._parse_wikiquote_page("https://example.com")

        self.assertEqual(len(quotes), 3)
        self.assertEqual(quotes[0]["text"], "The cake is a lie.")
        self.assertEqual(quotes[0]["attribution"], "Dialogue")
        self.assertEqual(quotes[2]["text"], "This was a triumph.")
        self.assertEqual(quotes[2]["attribution"], "GLaDOS")

    @patch("requests.Session.get")
    def test_parse_wikiquote_page_skips_external_links_section(self, mock_get):
        """Test that External Links section is skipped."""
        mock_response = Mock()
        mock_response.text = """
        <html>
        <body>
        <div class="mw-parser-output">
            <h2>Dialogue</h2>
            <ul>
                <li>Good quote here with enough text to pass validation.</li>
            </ul>
            <h2>External links</h2>
            <ul>
                <li>Should not be extracted from external links section.</li>
            </ul>
        </div>
        </body>
        </html>
        """
        mock_get.return_value = mock_response

        quotes = self.service._parse_wikiquote_page("https://example.com")

        # Only the first quote should be extracted
        self.assertEqual(len(quotes), 1)
        self.assertEqual(
            quotes[0]["text"], "Good quote here with enough text to pass validation."
        )

    @patch("requests.Session.get")
    def test_parse_wikiquote_page_removes_sup_tags(self, mock_get):
        """Test that <sup> reference tags are removed."""
        mock_response = Mock()
        mock_response.text = """
        <html>
        <body>
        <div class="mw-parser-output">
            <h2>Dialogue</h2>
            <ul>
                <li>A quote with reference<sup>[1]</sup></li>
            </ul>
        </div>
        </body>
        </html>
        """
        mock_get.return_value = mock_response

        quotes = self.service._parse_wikiquote_page("https://example.com")

        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["text"], "A quote with reference")

    @patch("requests.Session.get")
    def test_parse_wikiquote_page_returns_empty_for_no_content(self, mock_get):
        """Test parsing returns empty list when no content div found."""
        mock_response = Mock()
        mock_response.text = "<html><body>No content here</body></html>"
        mock_get.return_value = mock_response

        quotes = self.service._parse_wikiquote_page("https://example.com")

        self.assertEqual(len(quotes), 0)

    @patch("games.services.quote_service.QuoteService._parse_wikiquote_page")
    @patch("games.services.quote_service.QuoteService._search_wikiquote")
    def test_get_quotes_returns_result_with_quotes(self, mock_search, mock_parse):
        """Test get_quotes returns QuoteResult with quotes."""
        mock_search.return_value = "https://example.com"
        mock_parse.return_value = [
            {"text": "Quote 1", "attribution": "Character A"},
            {"text": "Quote 2", "attribution": "Character B"},
        ]

        result = self.service.get_quotes("Portal")

        self.assertEqual(result.source, QuoteSource.WIKIQUOTE)
        self.assertEqual(len(result.quotes), 2)
        self.assertEqual(result.quotes[0]["text"], "Quote 1")
        self.assertEqual(result.source_url, "https://example.com")
        self.assertIsNone(result.error_message)

    @patch("games.services.quote_service.QuoteService._search_wikiquote")
    def test_get_quotes_returns_failed_when_page_not_found(self, mock_search):
        """Test get_quotes returns FAILED when page not found."""
        mock_search.return_value = None

        result = self.service.get_quotes("NonExistentGame")

        self.assertEqual(result.source, QuoteSource.FAILED)
        self.assertEqual(len(result.quotes), 0)
        self.assertEqual(result.error_message, "Page not found on Wikiquote")
        self.assertIsNone(result.source_url)

    @patch("games.services.quote_service.QuoteService._parse_wikiquote_page")
    @patch("games.services.quote_service.QuoteService._search_wikiquote")
    def test_get_quotes_returns_failed_when_no_quotes_found(
        self, mock_search, mock_parse
    ):
        """Test get_quotes returns FAILED when no quotes found."""
        mock_search.return_value = "https://example.com"
        mock_parse.return_value = []

        result = self.service.get_quotes("GameWithNoQuotes")

        self.assertEqual(result.source, QuoteSource.FAILED)
        self.assertEqual(len(result.quotes), 0)
        self.assertEqual(result.error_message, "No quotes found on Wikiquote page")
        self.assertEqual(result.source_url, "https://example.com")

    def test_quote_result_quotes_json_property(self):
        """Test QuoteResult.quotes_json returns valid JSON."""
        from games.services.quote_service import QuoteResult

        result = QuoteResult(
            game_name="Test Game",
            source=QuoteSource.WIKIQUOTE,
            quotes=[
                {"text": "Quote 1", "attribution": "Character"},
                {"text": "Quote 2", "attribution": "Character 2"},
            ],
        )

        json_str = result.quotes_json
        parsed = json.loads(json_str)

        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["text"], "Quote 1")

    def test_quote_result_quotes_json_empty(self):
        """Test QuoteResult.quotes_json returns empty string for no quotes."""
        from games.services.quote_service import QuoteResult

        result = QuoteResult(
            game_name="Test Game",
            source=QuoteSource.FAILED,
            quotes=[],
        )

        self.assertEqual(result.quotes_json, "")

    @patch("time.sleep")
    @patch("time.time")
    def test_rate_limiting_enforced(self, mock_time, mock_sleep):
        """Test that rate limiting enforces delay between requests."""
        # Set up time mock to simulate passage of time
        times = [0.0, 0.5, 0.5, 1.0, 1.0]
        mock_time.side_effect = times

        service = QuoteService(delay=1.0)
        service.last_request_time = 0.0

        # First wait - should sleep for 1.0 seconds
        service._wait_for_rate_limit()

        # Second wait - should sleep for 0.5 seconds
        service._wait_for_rate_limit()

        # Verify sleep was called at least once
        self.assertGreater(mock_sleep.call_count, 0)

    @patch("games.services.quote_service.QuoteService._wait_for_rate_limit")
    @patch("requests.Session.get")
    def test_make_request_handles_timeout(self, mock_get, mock_wait):
        """Test that _make_request handles timeout errors."""
        import requests

        mock_get.side_effect = requests.RequestException("Timeout")

        response = self.service._make_request("https://example.com")

        self.assertIsNone(response)
        mock_wait.assert_called_once()

    @patch("games.services.quote_service.QuoteService._wait_for_rate_limit")
    @patch("requests.Session.get")
    def test_make_request_handles_http_error(self, mock_get, mock_wait):
        """Test that _make_request handles HTTP errors."""
        import requests

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.RequestException(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        response = self.service._make_request("https://example.com")

        self.assertIsNone(response)
        mock_wait.assert_called_once()
