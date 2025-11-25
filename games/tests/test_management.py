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
            # Disable batch mode to use sequential processing
            call_command("get_igdb", batch_games=0, concurrency=1)

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
            # Disable batch mode to use sequential processing
            call_command("get_igdb", batch_games=0, concurrency=1, stdout=out)
            output = out.getvalue()
            # Verify error message is in output
            self.assertIn("boom", output)

    def test_update_game_by_name(self):
        """Test updating a game by name using --game flag"""
        models.Game.objects.create(
            name="Halo 2",
            rank=1,
            igdb_id=1,
            year_of_release=2004,
        )

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("get_igdb", game="Halo 2")

        mock_get.assert_called_once_with()

    def test_igdb_import_does_not_update_modified_timestamp(self):
        """Test that IGDB import does not update the modified timestamp"""
        import time

        game = models.Game.objects.create(
            name="Halo 2",
            rank=1,
            igdb_id=1,
            year_of_release=2004,
        )

        # Wait a moment and record the original modified time
        time.sleep(0.1)
        original_modified = game.modified

        # Mock get_igdb_data to set some fields
        def mock_get_igdb(cache_results=True):
            # Simulate what get_igdb_data does
            game.slug = "halo-2-updated"
            game.igdb_url = "https://igdb.com/games/halo-2"
            game.igdb_artwork_id = "co1234"
            game.description = "A test game"

        with mock.patch.object(models.Game, "get_igdb_data", side_effect=mock_get_igdb):
            call_command("get_igdb", game="Halo 2")

        # Refresh from database and verify modified timestamp hasn't changed
        game.refresh_from_db()
        self.assertEqual(
            game.modified,
            original_modified,
            "Modified timestamp should not change during IGDB import",
        )

    def test_update_game_by_slug(self):
        """Test updating a game by slug using --slug flag"""
        models.Game.objects.create(
            name="Halo 2",
            slug="halo-2",
            rank=1,
            igdb_id=1,
            year_of_release=2004,
        )

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("get_igdb", slug="halo-2")

        mock_get.assert_called_once_with()

    def test_update_game_by_id(self):
        """Test updating a game by database ID using --id flag"""
        game = models.Game.objects.create(
            name="Halo 2",
            rank=1,
            igdb_id=1,
            year_of_release=2004,
        )

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("get_igdb", id=game.id)

        mock_get.assert_called_once_with()

    def test_force_update_game_with_existing_artwork(self):
        """Test using --force flag to update game that already has artwork"""
        game = models.Game.objects.create(
            name="Halo 2",
            rank=1,
            igdb_id=1,
            igdb_artwork_id="co1x77.jpg",
            year_of_release=2004,
        )

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("get_igdb", id=game.id, force=True)

        mock_get.assert_called_once_with()

    def test_warns_when_game_has_artwork_without_force(self):
        """Test that command warns when game already has artwork without --force"""
        models.Game.objects.create(
            name="Halo 2",
            rank=1,
            igdb_id=1,
            igdb_artwork_id="co1x77.jpg",
            year_of_release=2004,
        )

        from io import StringIO

        out = StringIO()
        call_command("get_igdb", id=1, stdout=out)
        output = out.getvalue()

        self.assertIn("already has IGDB data", output)
        self.assertIn("Use --force", output)

    def test_error_when_game_not_found_by_name(self):
        """Test error when game not found by name"""
        from io import StringIO

        out = StringIO()
        call_command("get_igdb", game="Nonexistent Game", stdout=out)
        output = out.getvalue()

        self.assertIn("Game not found", output)

    def test_error_when_game_has_no_igdb_id(self):
        """Test error when game has no IGDB ID"""
        models.Game.objects.create(
            name="No IGDB",
            rank=1,
            year_of_release=2004,
        )

        from io import StringIO

        out = StringIO()
        call_command("get_igdb", game="No IGDB", stdout=out)
        output = out.getvalue()

        self.assertIn("has no IGDB ID", output)

    def test_batch_update_with_force_flag(self):
        """Test batch update with --force flag updates all games with IGDB IDs"""
        models.Game.objects.create(
            name="Game 1",
            rank=1,
            igdb_id=1,
            igdb_artwork_id="co1.jpg",
            year_of_release=2000,
        )
        models.Game.objects.create(
            name="Game 2",
            rank=2,
            igdb_id=2,
            igdb_artwork_id="co2.jpg",
            year_of_release=2001,
        )

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            # Disable batch mode to use sequential processing
            call_command("get_igdb", force=True, batch_games=0, concurrency=1)

        # Should update both games since they have IGDB IDs
        self.assertEqual(mock_get.call_count, 2)

    def test_batch_mode_does_not_update_modified_timestamp(self):
        """Test that batch mode does not update modified timestamp"""
        import time
        from games import igdb

        game = models.Game.objects.create(
            name="Game 1",
            rank=1,
            igdb_id=1,
            year_of_release=2000,
        )

        # Wait and record original modified time
        time.sleep(0.1)
        original_modified = game.modified

        # Mock the API client to return game data
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_api.use_pro_tier = False
        mock_api.get_games_info_by_ids.return_value = {
            1: {
                "slug": "game-1",
                "url": "https://igdb.com/games/game-1",
                "cover": "co1.jpg",
                "summary": "Test game",
                "developers": [],
                "genres": [],
            }
        }

        with mock.patch.object(igdb, "get_api", return_value=mock_api):
            # Use batch mode (batch_games > 0)
            call_command("get_igdb", batch_games=10, concurrency=1)

        # Refresh and verify modified timestamp hasn't changed
        game.refresh_from_db()
        self.assertEqual(
            game.modified,
            original_modified,
            "Batch mode should not update modified timestamp",
        )

    def test_concurrent_mode_does_not_update_modified_timestamp(self):
        """Test that concurrent processing does not update modified timestamp"""
        import time

        game1 = models.Game.objects.create(
            name="Game 1",
            rank=1,
            igdb_id=1,
            year_of_release=2000,
        )
        game2 = models.Game.objects.create(
            name="Game 2",
            rank=2,
            igdb_id=2,
            year_of_release=2001,
        )

        # Wait and record original modified times
        time.sleep(0.1)
        original_modified_1 = game1.modified
        original_modified_2 = game2.modified

        # Mock get_igdb_data to update fields
        def mock_get_igdb(cache_results=True):
            pass  # Do nothing, we just want to test save behavior

        with mock.patch.object(models.Game, "get_igdb_data", side_effect=mock_get_igdb):
            # Use concurrent mode with batch_games=0 to test _process_game path
            call_command("get_igdb", concurrency=2, batch_games=0)

        # Refresh and verify modified timestamps haven't changed
        game1.refresh_from_db()
        game2.refresh_from_db()
        self.assertEqual(
            game1.modified,
            original_modified_1,
            "Concurrent mode should not update modified timestamp for game 1",
        )
        self.assertEqual(
            game2.modified,
            original_modified_2,
            "Concurrent mode should not update modified timestamp for game 2",
        )

    def test_error_handling_in_single_game_update(self):
        """Test that errors in single game update are handled gracefully"""
        models.Game.objects.create(
            name="Error Game",
            rank=1,
            igdb_id=1,
            year_of_release=2000,
        )

        from io import StringIO

        with mock.patch.object(
            models.Game, "get_igdb_data", side_effect=ValueError("API Error")
        ):
            out = StringIO()
            call_command("get_igdb", game="Error Game", stdout=out)
            output = out.getvalue()

            self.assertIn("Error updating game", output)

    def test_no_games_to_fetch_message(self):
        """Test message when all games already have IGDB data (lines 110-115)."""
        # Create games that all have igdb_artwork_id
        models.Game.objects.create(
            name="Game With Art",
            rank=1,
            igdb_id=1,
            igdb_artwork_id="co1.jpg",
            year_of_release=2000,
        )

        from io import StringIO

        out = StringIO()
        call_command("get_igdb", stdout=out)
        output = out.getvalue()

        self.assertIn("No games to fetch", output)
        self.assertIn("All games already have IGDB data", output)

    def test_service_init_failure(self):
        """Test error handling when IGDB service fails to initialize (lines 138-140)."""
        from games.services.igdb_importer import IGDBImportService

        models.Game.objects.create(
            name="Needs Art",
            rank=1,
            igdb_id=1,
            year_of_release=2000,
        )

        from io import StringIO

        with mock.patch.object(
            IGDBImportService, "__init__", side_effect=RuntimeError("API init failed")
        ):
            out = StringIO()
            call_command("get_igdb", stdout=out)
            output = out.getvalue()

            self.assertIn("Failed to initialize IGDB service", output)

    def test_multiple_games_same_name_error(self):
        """Test error when multiple games match name query (line 205)."""
        # Create two games with same name (case-insensitive)
        models.Game.objects.create(
            name="duplicate game",
            rank=1,
            igdb_id=1,
            year_of_release=2000,
        )
        models.Game.objects.create(
            name="Duplicate Game",
            rank=2,
            igdb_id=2,
            year_of_release=2001,
        )

        from io import StringIO

        out = StringIO()
        call_command("get_igdb", game="duplicate game", stdout=out)
        output = out.getvalue()

        self.assertIn("Multiple games found", output)
        self.assertIn("Please use --slug or --id", output)


class ImportDataRoutingTests(TestCase):

    def test_unknown_import_type_returns_error(self):
        file_content = mock.Mock()
        data = {"file": file_content, "type": "Z"}

        success, message = utils.import_data(data)
        self.assertFalse(success)
        self.assertIn('Unknown import type "Z"', message)
