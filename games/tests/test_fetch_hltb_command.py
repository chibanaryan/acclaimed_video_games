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
        self.assertIn("Wikidata HLTB ID(s) [12345] lookup failed", output)

    def test_multi_wikidata_fallback_to_alternate_hltb_id(self):
        """Test that command iterates through multiple WikipediaGameData records.

        When primary WikipediaGameData doesn't have an HLTB ID but an alternate
        record does (like Counter-Strike), the command should find and use it.
        """
        # Create a game with multiple WikipediaGameData records
        game = Game.objects.create(
            name="Counter-Strike",
            rank=100,
            igdb_id=99999,
        )

        # Primary record - NO HLTB ID (like Counter-Strike's main Wikidata entry)
        primary_wiki = WikipediaGameData.objects.create(
            game=game,
            page_title="Counter-Strike",
            wikidata_id="Q1111111",  # Main Wikidata entry without HLTB
            hltb_id=None,  # No HLTB ID
            is_primary=True,
        )
        game.primary_wikipedia_game_data = primary_wiki
        game.save()

        # Alternate record - HAS HLTB ID (specific version entry in Wikidata)
        WikipediaGameData.objects.create(
            game=game,
            page_title="Counter-Strike (video game)",
            wikidata_id="Q2222222",  # Alternate Wikidata entry with HLTB
            hltb_id="5555",  # Has HLTB ID
            is_primary=False,
        )

        out = StringIO()

        with mock.patch("howlongtobeatpy.HowLongToBeat") as mock_hltb_class:
            mock_hltb = mock_hltb_class.return_value

            # Direct lookup succeeds for the alternate HLTB ID
            # Create a proper mock object that won't create auto-attributes
            class MockHLTBResult:
                game_id = 5555
                game_name = "Counter-Strike"
                main_story = 0.0
                main_extra = 0.0
                completionist = 0.0
                similarity = 1.0
                release_world = None
                profile_platform = None

            mock_result = MockHLTBResult()
            mock_hltb.async_search_from_id = mock.AsyncMock(return_value=mock_result)

            call_command(
                "fetch_hltb_data",
                "--game",
                "Counter-Strike",
                stdout=out,
            )

        output = out.getvalue()

        # Should find HLTB data via alternate record
        mock_hltb.async_search_from_id.assert_called_once_with(5555)
        self.assertIn("Direct lookup via Wikidata HLTB ID 5555", output)
        self.assertIn("via alternate Wikidata Q2222222", output)

    def test_multi_wikidata_primary_used_first(self):
        """Test that primary WikipediaGameData is checked first.

        If primary has an HLTB ID, it should be used without checking alternates.
        """
        # Create a game with multiple WikipediaGameData records
        game = Game.objects.create(
            name="Test Multi Game",
            rank=101,
            igdb_id=88888,
        )

        # Primary record - HAS HLTB ID
        primary_wiki = WikipediaGameData.objects.create(
            game=game,
            page_title="Test Multi Game",
            wikidata_id="Q3333333",
            hltb_id="1111",  # Primary has HLTB ID
            is_primary=True,
        )
        game.primary_wikipedia_game_data = primary_wiki
        game.save()

        # Alternate record - also has HLTB ID (but should not be used)
        WikipediaGameData.objects.create(
            game=game,
            page_title="Test Multi Game (alternate)",
            wikidata_id="Q4444444",
            hltb_id="2222",  # Alternate also has HLTB ID
            is_primary=False,
        )

        out = StringIO()

        with mock.patch("howlongtobeatpy.HowLongToBeat") as mock_hltb_class:
            mock_hltb = mock_hltb_class.return_value

            mock_result = mock.MagicMock()
            mock_result.game_id = 1111
            mock_result.game_name = "Test Multi Game"
            mock_result.main_story = 10.0
            mock_result.main_extra = 15.0
            mock_result.completionist = 20.0
            mock_result.similarity = 1.0
            mock_hltb.async_search_from_id = mock.AsyncMock(return_value=mock_result)

            call_command(
                "fetch_hltb_data",
                "--game",
                "Test Multi Game",
                stdout=out,
            )

        output = out.getvalue()

        # Should use primary's HLTB ID (1111), not alternate's (2222)
        mock_hltb.async_search_from_id.assert_called_once_with(1111)
        self.assertIn("Direct lookup via Wikidata HLTB ID 1111", output)
        # Should NOT mention alternate Wikidata
        self.assertNotIn("via alternate Wikidata", output)
