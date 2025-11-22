from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from .. import models, utils


class GetIgdbCommandTests(TestCase):

    def test_updates_games_missing_artwork(self):
        models.Game.objects.create(
            name="Needs Art",
            rank=2,
            igdb_id=2,
            year_of_release=1991,
        )

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("get_igdb")

        mock_get.assert_called_once_with()

    def test_command_logs_when_game_update_fails(self):
        models.Game.objects.create(
            name="Broken",
            rank=3,
            igdb_id=3,
            year_of_release=1992,
        )

        with mock.patch.object(
            models.Game, "get_igdb_data", side_effect=ValueError("boom")
        ):
            # Capture stdout to verify error output
            from io import StringIO

            out = StringIO()
            call_command("get_igdb", stdout=out)
            output = out.getvalue()
            # Verify error message is in output
            self.assertIn("boom", output)


class ImportDataRoutingTests(TestCase):

    def test_unknown_import_type_returns_error(self):
        file_content = mock.Mock()
        data = {"file": file_content, "type": "Z"}

        success, message = utils.import_data(data)
        self.assertFalse(success)
        self.assertIn('Unknown import type "Z"', message)


class RefreshIgdbDevelopersCommandTests(TestCase):

    def setUp(self):
        """Set up test games with various states"""
        # Game with IGDB ID and developers with IGDB IDs (should not be refreshed)
        self.game_with_dev = models.Game.objects.create(
            name="Game With Dev",
            slug="game-with-dev",
            rank=1,
            igdb_id=1,
            year_of_release=2020,
        )
        dev = models.Developer.objects.create(
            name="Developer 1", slug="dev-1", igdb_id=101
        )
        dev_alias = models.DeveloperAlias.objects.create(
            name="Developer 1", igdb_id=101, developer=dev
        )
        self.game_with_dev.developers.add(dev_alias)

        # Game with IGDB ID but no developers (should be refreshed by default)
        self.game_without_dev = models.Game.objects.create(
            name="Game Without Dev",
            slug="game-without-dev",
            rank=2,
            igdb_id=2,
            year_of_release=2021,
        )

        # Game with IGDB ID but developers without IGDB IDs
        self.game_with_dev_no_igdb = models.Game.objects.create(
            name="Game With Dev No IGDB",
            slug="game-with-dev-no-igdb",
            rank=3,
            igdb_id=3,
            year_of_release=2022,
        )
        dev_no_igdb = models.Developer.objects.create(name="Developer 2", slug="dev-2")
        dev_alias_no_igdb = models.DeveloperAlias.objects.create(
            name="Developer 2", developer=dev_no_igdb
        )
        self.game_with_dev_no_igdb.developers.add(dev_alias_no_igdb)

        # Game without IGDB ID (should not be refreshed)
        self.game_no_igdb = models.Game.objects.create(
            name="Game No IGDB",
            slug="game-no-igdb",
            rank=4,
            year_of_release=2023,
        )

    def test_default_behavior_finds_games_with_missing_developer_data(self):
        """Test default behavior finds games with missing developer IGDB data"""
        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("refresh_igdb_developers")

        # Should be called for games without developer IGDB data (2 times)
        self.assertEqual(mock_get.call_count, 2)

    def test_refresh_specific_game_by_slug(self):
        """Test refreshing a specific game by slug"""
        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("refresh_igdb_developers", game_slug="game-with-dev")

        # Should call get_igdb_data once for the specific game
        mock_get.assert_called_once_with(cache_results=False)

    def test_refresh_specific_game_by_id(self):
        """Test refreshing a specific game by ID"""
        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("refresh_igdb_developers", game_id=self.game_with_dev.id)

        # Should call get_igdb_data once for the specific game
        mock_get.assert_called_once_with(cache_results=False)

    def test_refresh_all_games_with_all_flag(self):
        """Test that --all flag refreshes all games with IGDB IDs"""
        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("refresh_igdb_developers", all=True)

        # Should be called for all games with IGDB IDs (3 total)
        self.assertEqual(mock_get.call_count, 3)

    def test_invalid_game_slug_returns_error(self):
        """Test that invalid game slug returns error gracefully"""
        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("refresh_igdb_developers", game_slug="invalid-slug")

        mock_get.assert_not_called()

    def test_invalid_game_id_returns_error(self):
        """Test that invalid game ID returns error gracefully"""
        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("refresh_igdb_developers", game_id=9999)

        mock_get.assert_not_called()

    def test_command_handles_get_igdb_data_errors(self):
        """Test that command logs errors when get_igdb_data fails"""
        with mock.patch.object(
            models.Game, "get_igdb_data", side_effect=ValueError("IGDB API error")
        ), mock.patch(
            "games.management.commands.refresh_igdb_developers.logger"
        ) as logger_mock:
            call_command("refresh_igdb_developers")

        # Should have logged the error
        self.assertTrue(logger_mock.error.called)

    def test_command_saves_game_after_refresh(self):
        """Test that command saves the game after calling get_igdb_data"""
        with mock.patch.object(models.Game, "get_igdb_data"), mock.patch.object(
            models.Game, "save"
        ) as mock_save:
            call_command("refresh_igdb_developers", game_slug="game-with-dev")

        # Should have called save after get_igdb_data
        mock_save.assert_called_once()

    def test_passes_cache_results_false_to_get_igdb_data(self):
        """Test that command passes cache_results=False to bypass caching"""
        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("refresh_igdb_developers", game_slug="game-with-dev")

        # Should pass cache_results=False to force fresh fetch
        mock_get.assert_called_once_with(cache_results=False)
