"""Tests for the fetch_hltb_data management command."""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from games.models import Game, WikipediaGameData


class FetchHltbDataCommandTests(TestCase):
    """Tests for the fetch_hltb_data management command."""

    def setUp(self):
        """Set up test games."""
        self.game_with_hltb_id = Game.objects.create(
            name="Test Game With HLTB ID",
            rank=1,
            wikidata_id="Q123456",
        )

        # Create Wikipedia data with HLTB ID
        wiki_data = WikipediaGameData.objects.create(
            game=self.game_with_hltb_id,
            page_title="Test Game With HLTB ID",
            hltb_id="12345",
            is_primary=True,
        )
        self.game_with_hltb_id.primary_wikipedia_game_data = wiki_data
        self.game_with_hltb_id.save()

        self.game_without_hltb_id = Game.objects.create(
            name="Test Game Without HLTB ID",
            rank=2,
        )

    def test_name_search_disabled_by_default(self):
        """Test that name search is disabled by default."""
        out = StringIO()

        # Mock HowLongToBeat at the module where it's imported
        with mock.patch("howlongtobeatpy.HowLongToBeat") as mock_hltb_class:
            mock_hltb = mock_hltb_class.return_value

            # Direct ID lookup succeeds for game with HLTB ID
            mock_result = mock.MagicMock()
            mock_result.game_id = 12345
            mock_result.game_name = "Test Game"
            mock_result.main_story = 10.0
            mock_result.main_extra = 15.0
            mock_result.completionist = 20.0
            mock_result.similarity = 1.0
            mock_hltb.async_search_from_id = mock.AsyncMock(return_value=mock_result)

            # Name search should NOT be called for game without HLTB ID
            mock_hltb.async_search = mock.AsyncMock(return_value=[])

            call_command(
                "fetch_hltb_data",
                "--game",
                "Test Game Without HLTB ID",
                stdout=out,
            )

        output = out.getvalue()

        # Name search should not be called when --use-name-search is not specified
        mock_hltb.async_search.assert_not_called()

        # Output should indicate no Wikidata HLTB ID
        self.assertIn("No Wikidata HLTB ID available", output)

    def test_name_search_enabled_with_flag(self):
        """Test that name search is enabled when --use-name-search is specified."""
        out = StringIO()

        with mock.patch("howlongtobeatpy.HowLongToBeat") as mock_hltb_class:
            mock_hltb = mock_hltb_class.return_value

            # Name search returns results
            mock_result = mock.MagicMock()
            mock_result.game_id = 99999
            mock_result.game_name = "Test Game Without HLTB ID"
            mock_result.main_story = 10.0
            mock_result.main_extra = 15.0
            mock_result.completionist = 20.0
            mock_result.similarity = 0.9
            mock_hltb.async_search = mock.AsyncMock(return_value=[mock_result])

            call_command(
                "fetch_hltb_data",
                "--game",
                "Test Game Without HLTB ID",
                "--use-name-search",
                stdout=out,
            )

        output = out.getvalue()

        # Name search should be called
        mock_hltb.async_search.assert_called()

        # Output should indicate name search enabled
        self.assertIn("name search ENABLED", output)

    def test_wikidata_lookup_used_when_id_available(self):
        """Test that Wikidata HLTB ID is used for direct lookup."""
        out = StringIO()

        with mock.patch("howlongtobeatpy.HowLongToBeat") as mock_hltb_class:
            mock_hltb = mock_hltb_class.return_value

            mock_result = mock.MagicMock()
            mock_result.game_id = 12345
            mock_result.game_name = "Test Game"
            mock_result.main_story = 10.0
            mock_result.main_extra = 15.0
            mock_result.completionist = 20.0
            mock_result.similarity = 1.0
            mock_hltb.async_search_from_id = mock.AsyncMock(return_value=mock_result)

            call_command(
                "fetch_hltb_data",
                "--game",
                "Test Game With HLTB ID",
                stdout=out,
            )

        output = out.getvalue()

        # Should use Wikidata direct lookup
        mock_hltb.async_search_from_id.assert_called_once_with(12345)
        self.assertIn("Direct lookup via Wikidata HLTB ID", output)

    def test_error_message_when_wikidata_lookup_fails(self):
        """Test error message when Wikidata HLTB ID lookup fails."""
        out = StringIO()

        with mock.patch("howlongtobeatpy.HowLongToBeat") as mock_hltb_class:
            mock_hltb = mock_hltb_class.return_value

            # Direct lookup fails
            mock_hltb.async_search_from_id = mock.AsyncMock(return_value=None)

            call_command(
                "fetch_hltb_data",
                "--game",
                "Test Game With HLTB ID",
                stdout=out,
            )

        output = out.getvalue()

        # Should indicate lookup failed
        self.assertIn("Wikidata HLTB ID 12345 lookup failed", output)
