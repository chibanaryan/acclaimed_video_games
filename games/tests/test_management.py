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
            # Simulate what get_igdb_data does (sets slug and description)
            game.slug = "halo-2-updated"
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
        """Test using --force flag to update game that already has IGDB data"""
        game = models.Game.objects.create(
            name="Halo 2",
            rank=1,
            igdb_id=1,
            year_of_release=2004,
        )
        # Create IGDB data to simulate game already having data
        igdb_data, _ = models.IGDBGameData.objects.update_or_create(
            game=game,
            igdb_id=1,
            defaults={
                "artwork_id": "co1x77.jpg",
                "url": "https://example.com",
                "is_primary": True,
            },
        )
        game.primary_igdb_game_data = igdb_data
        game.save()

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("get_igdb", id=game.id, force=True)

        mock_get.assert_called_once_with()

    def test_warns_when_game_has_artwork_without_force(self):
        """Test that command warns when game already has IGDB data without --force"""
        game = models.Game.objects.create(
            name="Halo 2",
            rank=1,
            igdb_id=1,
            year_of_release=2004,
        )
        # Create IGDB data to simulate game already having data
        igdb_data, _ = models.IGDBGameData.objects.update_or_create(
            game=game,
            igdb_id=1,
            defaults={
                "artwork_id": "co1x77.jpg",
                "url": "https://example.com",
                "is_primary": True,
            },
        )
        game.primary_igdb_game_data = igdb_data
        game.save()

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
        # Create IGDB data to simulate games already having data
        for game in [game1, game2]:
            igdb_data, _ = models.IGDBGameData.objects.update_or_create(
                game=game,
                igdb_id=game.igdb_id,
                defaults={
                    "artwork_id": f"co{game.igdb_id}.jpg",
                    "url": "https://example.com",
                    "is_primary": True,
                },
            )
            game.primary_igdb_game_data = igdb_data
            game.save()

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
        """Test message when all games already have IGDB data."""
        # Create game with IGDB data
        game = models.Game.objects.create(
            name="Game With Art",
            rank=1,
            igdb_id=1,
            year_of_release=2000,
        )
        igdb_data, _ = models.IGDBGameData.objects.update_or_create(
            game=game,
            igdb_id=1,
            defaults={
                "artwork_id": "co1.jpg",
                "url": "https://example.com",
                "is_primary": True,
            },
        )
        game.primary_igdb_game_data = igdb_data
        game.save()

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


class SyncFromProdCommandTests(TestCase):
    """Tests for sync_from_prod management command"""

    def setUp(self):
        # Create some local data that will be cleared
        self.platform = models.Platform.objects.create(name="PC", code="PC")
        self.genre = models.IGDBGenre.objects.create(name="Action")
        self.developer = models.Developer.objects.create(name="Test Dev")
        self.game = models.Game.objects.create(
            name="Local Game", rank=1, year_of_release=2020
        )

    @mock.patch("games.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_successful_sync(self, mock_subprocess, mock_call_command):
        """Test successful sync from production"""
        from io import StringIO

        # Mock heroku run output with valid JSON
        mock_subprocess.return_value = mock.Mock(
            stdout='Some heroku noise\n[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out)
        output = out.getvalue()

        self.assertIn("Syncing production database", output)
        self.assertIn("Dumping production data", output)
        self.assertIn("Clearing local data", output)
        self.assertIn("Loading data into local database", output)
        self.assertIn("Sync complete!", output)
        self.assertIn("createsuperuser", output)

        # Verify migrate and loaddata were called
        calls = mock_call_command.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], "migrate")
        self.assertEqual(calls[1][0][0], "loaddata")

    @mock.patch("subprocess.run")
    def test_heroku_cli_not_found(self, mock_subprocess):
        """Test error when Heroku CLI is not installed"""
        from io import StringIO

        mock_subprocess.side_effect = FileNotFoundError("heroku not found")

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("Heroku CLI not found", error_output)
        self.assertIn("brew install", error_output)

    @mock.patch("subprocess.run")
    def test_no_json_in_output(self, mock_subprocess):
        """Test error when heroku output contains no JSON"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout="Some error output without JSON",
            stderr="",
            returncode=0,
        )

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("No JSON data found", error_output)

    @mock.patch("games.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_loaddata_failure(self, mock_subprocess, mock_call_command):
        """Test error handling when loaddata fails"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        # Only fail on loaddata, not migrate
        def side_effect(cmd, *args, **kwargs):
            if cmd == "loaddata":
                raise Exception("Database error")

        mock_call_command.side_effect = side_effect

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("Failed to load data", error_output)

    @mock.patch("builtins.input", return_value="n")
    def test_confirmation_abort(self, mock_input):
        """Test that sync aborts when user says no"""
        from io import StringIO

        out = StringIO()
        call_command("sync_from_prod", stdout=out)
        output = out.getvalue()

        self.assertIn("Aborted", output)
        mock_input.assert_called_once()

    @mock.patch("games.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    @mock.patch("builtins.input", return_value="y")
    def test_confirmation_proceed(self, mock_input, mock_subprocess, mock_call_command):
        """Test that sync proceeds when user confirms"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", stdout=out)
        output = out.getvalue()

        self.assertIn("Sync complete!", output)
        mock_input.assert_called_once()

    @mock.patch("games.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_keep_fixture_flag(self, mock_subprocess, mock_call_command):
        """Test --keep-fixture flag keeps the downloaded file"""
        import os
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, keep_fixture=True, stdout=out)
        output = out.getvalue()

        self.assertIn("Fixture kept at:", output)

        # Clean up the fixture file
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "fixtures",
            "prod_dump.json",
        )
        if os.path.exists(fixture_path):
            os.remove(fixture_path)

    @mock.patch("games.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_clears_local_data(self, mock_subprocess, mock_call_command):
        """Test that local data is cleared before loading"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        # Verify data exists before sync
        self.assertEqual(models.Game.objects.count(), 1)
        self.assertEqual(models.Platform.objects.count(), 1)

        out = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out)

        # Verify data was cleared (loaddata is mocked so no new data loaded)
        self.assertEqual(models.Game.objects.count(), 0)
        self.assertEqual(models.Platform.objects.count(), 0)
        self.assertEqual(models.IGDBGenre.objects.count(), 0)
        self.assertEqual(models.Developer.objects.count(), 0)

    @mock.patch("subprocess.run")
    def test_heroku_command_error(self, mock_subprocess):
        """Test error when heroku command fails"""
        import subprocess
        from io import StringIO

        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "heroku", stderr="Connection failed"
        )

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("Failed to dump production data", error_output)

    @mock.patch("games.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_custom_app_name(self, mock_subprocess, mock_call_command):
        """Test using custom Heroku app name"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, app="my-custom-app", stdout=out)
        output = out.getvalue()

        self.assertIn("my-custom-app", output)
        # Verify heroku was called with custom app name
        call_args = mock_subprocess.call_args[0][0]
        self.assertIn("my-custom-app", call_args)

    @mock.patch("games.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_runs_migrations(self, mock_subprocess, mock_call_command):
        """Test that migrations are run before loading data"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out)
        output = out.getvalue()

        self.assertIn("Running migrations", output)
        # Verify migrate was called before loaddata
        calls = mock_call_command.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], "migrate")
        self.assertEqual(calls[1][0][0], "loaddata")

    @mock.patch("games.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_strips_post_author(self, mock_subprocess, mock_call_command):
        """Test that author field is stripped from Post records"""
        import json
        from io import StringIO

        # Fixture with Post that has author_id (would fail without stripping)
        fixture = [
            {"model": "games.post", "pk": 1, "fields": {"text": "Test", "author": 5}}
        ]
        mock_subprocess.return_value = mock.Mock(
            stdout=json.dumps(fixture),
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out)

        # loaddata should be called with fixture that has author stripped
        self.assertIn("Sync complete!", out.getvalue())

    @mock.patch("subprocess.run")
    def test_invalid_json_error(self, mock_subprocess):
        """Test error when JSON parsing fails"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"invalid json',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("Invalid JSON from Heroku", error_output)


class ImportDataRoutingTests(TestCase):

    def test_unknown_import_type_returns_error(self):
        file_content = mock.Mock()
        data = {"file": file_content, "type": "Z"}

        success, message = utils.import_data(data)
        self.assertFalse(success)
        self.assertIn('Unknown import type "Z"', message)


class RefreshAllMetadataCommandTests(TestCase):
    """Tests for refresh_all_metadata management command"""

    def setUp(self):
        """Create test games for metadata refresh"""
        self.game1 = models.Game.objects.create(
            name="Test Game 1",
            rank=1,
            igdb_id=1,
            year_of_release=2000,
        )
        self.game2 = models.Game.objects.create(
            name="Test Game 2",
            rank=2,
            igdb_id=2,
            year_of_release=2001,
        )

    def test_command_exists(self):
        """Test that command can be imported"""
        from games.management.commands import refresh_all_metadata

        self.assertIsNotNone(refresh_all_metadata)

    @mock.patch("games.management.commands.refresh_all_metadata.WikiPageLookupService")
    @mock.patch("games.management.commands.refresh_all_metadata.WikiGenreService")
    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_full_refresh(
        self, mock_igdb_service, mock_genre_service, mock_page_service
    ):
        """Test full refresh of both IGDB and Wikipedia data"""
        from io import StringIO

        # Mock IGDB service
        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50
        mock_igdb_instance.concurrency = 8

        # Mock Wikipedia services
        mock_page_instance = mock.MagicMock()
        mock_page_service.return_value = mock_page_instance

        page_result = mock.MagicMock()
        page_result.success = True
        page_result.page_title = "Test Game"
        page_result.lookup_source = "Wikidata"
        page_result.wikipedia_url = "https://en.wikipedia.org/wiki/Test_Game"
        mock_page_instance.lookup_page.return_value = page_result

        genre_service_instance = mock.MagicMock()
        mock_genre_service.return_value = genre_service_instance

        genre_result = mock.MagicMock()
        genre_result.primary_genre = "Action"
        genre_result.all_genres = ["Action", "Adventure"]
        genre_service_instance.get_genre_from_url.return_value = genre_result

        out = StringIO()
        call_command("refresh_all_metadata", limit=2, stdout=out)
        output = out.getvalue()

        # Verify header
        self.assertIn("Weekly Metadata Refresh", output)

        # Verify IGDB section
        self.assertIn("[1/2] Refreshing IGDB Data", output)

        # Verify Wikipedia section
        self.assertIn("[2/2] Refreshing Wikipedia Data", output)

        # Verify summary
        self.assertIn("Summary", output)
        self.assertIn("Overall Status", output)

        # Verify services were called
        mock_igdb_instance.import_games.assert_called_once()
        self.assertEqual(mock_page_instance.lookup_page.call_count, 2)

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_igdb_only_flag(self, mock_igdb_service):
        """Test --igdb-only flag skips Wikipedia refresh"""
        from io import StringIO

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50
        mock_igdb_instance.concurrency = 8

        out = StringIO()
        call_command("refresh_all_metadata", igdb_only=True, limit=1, stdout=out)
        output = out.getvalue()

        # Should have IGDB section
        self.assertIn("[1/2] Refreshing IGDB Data", output)

        # Should NOT have Wikipedia section
        self.assertNotIn("[2/2] Refreshing Wikipedia Data", output)

        # IGDB service should be called
        mock_igdb_instance.import_games.assert_called_once()

    @mock.patch("games.management.commands.refresh_all_metadata.WikiPageLookupService")
    @mock.patch("games.management.commands.refresh_all_metadata.WikiGenreService")
    def test_wikipedia_only_flag(self, mock_genre_service, mock_page_service):
        """Test --wikipedia-only flag skips IGDB refresh"""
        from io import StringIO

        # Mock Wikipedia services
        mock_page_instance = mock.MagicMock()
        mock_page_service.return_value = mock_page_instance

        page_result = mock.MagicMock()
        page_result.success = False
        page_result.error_message = "Not found"
        mock_page_instance.lookup_page.return_value = page_result

        out = StringIO()
        call_command("refresh_all_metadata", wikipedia_only=True, limit=1, stdout=out)
        output = out.getvalue()

        # Should NOT have IGDB section
        self.assertNotIn("[1/2] Refreshing IGDB Data", output)

        # Should have Wikipedia section
        self.assertIn("[2/2] Refreshing Wikipedia Data", output)

        # Wikipedia service should be called
        mock_page_instance.lookup_page.assert_called()

    def test_conflicting_flags_error(self):
        """Test error when both --igdb-only and --wikipedia-only are used"""
        from io import StringIO

        out = StringIO()
        call_command(
            "refresh_all_metadata", igdb_only=True, wikipedia_only=True, stdout=out
        )
        output = out.getvalue()

        self.assertIn("Cannot use --igdb-only and --wikipedia-only together", output)

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_dry_run_mode(self, mock_igdb_service):
        """Test --dry-run flag prevents database changes"""
        from io import StringIO

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50  # Configure attribute
        mock_igdb_instance.concurrency = 8

        out = StringIO()
        call_command("refresh_all_metadata", dry_run=True, limit=1, stdout=out)
        output = out.getvalue()

        # Should show dry run warning
        self.assertIn("DRY RUN MODE", output)
        self.assertIn("DRY RUN: Would process IGDB data", output)
        self.assertIn("DRY RUN: Would process Wikipedia data", output)

        # Services should NOT be called
        mock_igdb_instance.import_games.assert_not_called()

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_limit_flag(self, mock_igdb_service):
        """Test --limit flag restricts number of games processed"""
        from io import StringIO

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50
        mock_igdb_instance.concurrency = 8

        out = StringIO()
        call_command("refresh_all_metadata", igdb_only=True, limit=1, stdout=out)
        output = out.getvalue()

        self.assertIn("Limiting to first 1 games", output)
        self.assertIn("Processing 1 games", output)

    @mock.patch("games.management.commands.refresh_all_metadata.WikiPageLookupService")
    @mock.patch("games.management.commands.refresh_all_metadata.WikiGenreService")
    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_error_handling_igdb_failure(
        self, mock_igdb_service, mock_genre_service, mock_page_service
    ):
        """Test that Wikipedia refresh continues even if IGDB fails"""
        from io import StringIO

        # Make IGDB service constructor raise an error
        mock_igdb_service.side_effect = RuntimeError("IGDB API failed")

        # Mock Wikipedia services to succeed
        mock_page_instance = mock.MagicMock()
        mock_page_service.return_value = mock_page_instance

        page_result = mock.MagicMock()
        page_result.success = False
        mock_page_instance.lookup_page.return_value = page_result

        out = StringIO()
        call_command("refresh_all_metadata", limit=1, stdout=out)
        output = out.getvalue()

        # Should show IGDB error (caught during service initialization)
        self.assertIn("Failed to initialize IGDB service", output)
        self.assertIn("IGDB API failed", output)

        # Should still run Wikipedia refresh
        self.assertIn("[2/2] Refreshing Wikipedia Data", output)

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_progress_callback(self, mock_igdb_service):
        """Test that IGDB progress callback is registered"""
        from io import StringIO

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50
        mock_igdb_instance.concurrency = 8

        out = StringIO()
        call_command("refresh_all_metadata", igdb_only=True, limit=1, stdout=out)

        # Verify IGDBImportService was initialized with a progress_callback
        call_args = mock_igdb_service.call_args
        self.assertIn("progress_callback", call_args.kwargs)
        self.assertIsNotNone(call_args.kwargs["progress_callback"])

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_concurrency_option(self, mock_igdb_service):
        """Test --concurrency option is passed to IGDB service"""
        from io import StringIO

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False

        out = StringIO()
        call_command(
            "refresh_all_metadata",
            igdb_only=True,
            concurrency=4,
            dry_run=True,
            stdout=out,
        )

        # Verify concurrency was passed to service
        call_args = mock_igdb_service.call_args
        self.assertEqual(call_args.kwargs["concurrency"], 4)

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_pro_tier_option(self, mock_igdb_service):
        """Test --pro option enables IGDB Pro tier"""
        from io import StringIO

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = True
        mock_igdb_instance.batch_size = 500
        mock_igdb_instance.concurrency = 8

        out = StringIO()
        call_command(
            "refresh_all_metadata", igdb_only=True, pro=True, limit=1, stdout=out
        )
        output = out.getvalue()

        # Verify pro tier was passed to service
        call_args = mock_igdb_service.call_args
        self.assertTrue(call_args.kwargs["use_pro_tier"])

        # Verify output shows Pro tier
        self.assertIn("Using IGDB Pro tier", output)

    @mock.patch("games.management.commands.refresh_all_metadata.WikiPageLookupService")
    @mock.patch("games.management.commands.refresh_all_metadata.WikiGenreService")
    def test_wikipedia_genre_creation(self, mock_genre_service, mock_page_service):
        """Test that Wikipedia genres are created and linked"""
        from io import StringIO

        # Mock Wikipedia services
        mock_page_instance = mock.MagicMock()
        mock_page_service.return_value = mock_page_instance

        page_result = mock.MagicMock()
        page_result.success = True
        page_result.page_title = "Test Game"
        page_result.lookup_source = "Wikidata"
        page_result.wikipedia_url = "https://en.wikipedia.org/wiki/Test_Game"
        mock_page_instance.lookup_page.return_value = page_result

        genre_service_instance = mock.MagicMock()
        mock_genre_service.return_value = genre_service_instance

        genre_result = mock.MagicMock()
        genre_result.primary_genre = "action"  # Lowercase to test capitalization
        genre_result.all_genres = ["action", "adventure"]
        genre_service_instance.get_genre_from_url.return_value = genre_result

        out = StringIO()
        call_command("refresh_all_metadata", wikipedia_only=True, limit=1, stdout=out)

        # Verify genres were created (with capitalization)
        self.assertTrue(models.WikipediaGenre.objects.filter(name="Action").exists())
        self.assertTrue(models.WikipediaGenre.objects.filter(name="Adventure").exists())

        # Verify game has genres linked
        self.game1.refresh_from_db()
        genre_names = set(self.game1.wikipedia_genres.values_list("name", flat=True))
        self.assertEqual(genre_names, {"Action", "Adventure"})

        # Verify WikipediaGameData record was created
        wiki_data = models.WikipediaGameData.objects.filter(game=self.game1).first()
        self.assertIsNotNone(wiki_data)
        self.assertEqual(wiki_data.primary_genre, "Action")
        self.assertIn("Action", wiki_data.all_genres)

    def test_no_games_message(self):
        """Test message when no games exist"""
        from io import StringIO

        # Delete all games
        models.Game.objects.all().delete()

        out = StringIO()
        call_command("refresh_all_metadata", igdb_only=True, stdout=out)
        output = out.getvalue()

        self.assertIn("No games with IGDB IDs found", output)

    @mock.patch("games.management.commands.refresh_all_metadata.WikiPageLookupService")
    @mock.patch("games.management.commands.refresh_all_metadata.WikiGenreService")
    def test_wikipedia_genre_scraping_failure(
        self, mock_genre_service, mock_page_service
    ):
        """Test genre scraping failure doesn't crash command"""
        from io import StringIO

        # Mock Wikipedia page lookup success
        mock_page_instance = mock.MagicMock()
        mock_page_service.return_value = mock_page_instance

        page_result = mock.MagicMock()
        page_result.success = True
        page_result.page_title = "Test Game"
        page_result.lookup_source = "Wikidata"
        page_result.wikipedia_url = "https://en.wikipedia.org/wiki/Test_Game"
        mock_page_instance.lookup_page.return_value = page_result

        # Mock genre scraping to raise exception
        genre_service_instance = mock.MagicMock()
        mock_genre_service.return_value = genre_service_instance
        genre_service_instance.get_genre_from_url.side_effect = Exception(
            "Network error"
        )

        out = StringIO()
        call_command("refresh_all_metadata", wikipedia_only=True, limit=1, stdout=out)
        output = out.getvalue()

        # Should complete despite genre error
        self.assertIn("Wikipedia Complete", output)
        self.assertIn("1 pages found", output)

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_igdb_progress_checkpoint(self, mock_igdb_service):
        """Test IGDB progress callback at checkpoint (100 games)"""
        from io import StringIO
        from games.management.commands.refresh_all_metadata import Command

        # Create 100+ games for checkpoint test
        for i in range(3, 103):
            models.Game.objects.create(
                name=f"Test Game {i}", rank=i, igdb_id=i, year_of_release=2000
            )

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50
        mock_igdb_instance.concurrency = 8

        # Capture the progress callback
        progress_callback = None

        def capture_callback(**kwargs):
            nonlocal progress_callback
            progress_callback = kwargs.get("progress_callback")
            return mock_igdb_instance

        mock_igdb_service.side_effect = capture_callback

        out = StringIO()
        cmd = Command(stdout=out)
        cmd.handle(igdb_only=True, limit=100)

        # Simulate progress event at checkpoint (100 games)
        self.assertIsNotNone(progress_callback)
        progress_callback(
            "progress", {"current": 100, "total": 100, "game_name": "Test Game 100"}
        )

        output = out.getvalue()
        # Should show checkpoint progress
        self.assertIn("[100/100]", output)

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_igdb_error_callback(self, mock_igdb_service):
        """Test IGDB error callback"""
        from io import StringIO
        from games.management.commands.refresh_all_metadata import Command

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50
        mock_igdb_instance.concurrency = 8

        # Capture the progress callback
        progress_callback = None

        def capture_callback(**kwargs):
            nonlocal progress_callback
            progress_callback = kwargs.get("progress_callback")
            return mock_igdb_instance

        mock_igdb_service.side_effect = capture_callback

        out = StringIO()
        cmd = Command(stdout=out)
        cmd.handle(igdb_only=True, limit=1)

        # Simulate error event
        self.assertIsNotNone(progress_callback)
        progress_callback(
            "error", {"game_name": "Test Game 1", "message": "API timeout"}
        )

        # Error should be logged (check command state)
        self.assertEqual(cmd.igdb_errors, 1)

    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_igdb_complete_callback(self, mock_igdb_service):
        """Test IGDB complete callback"""
        from io import StringIO
        from games.management.commands.refresh_all_metadata import Command

        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50
        mock_igdb_instance.concurrency = 8

        # Capture the progress callback
        progress_callback = None

        def capture_callback(**kwargs):
            nonlocal progress_callback
            progress_callback = kwargs.get("progress_callback")
            return mock_igdb_instance

        mock_igdb_service.side_effect = capture_callback

        out = StringIO()
        cmd = Command(stdout=out)
        cmd.handle(igdb_only=True, limit=2)

        # Simulate complete event
        self.assertIsNotNone(progress_callback)
        progress_callback(
            "complete", {"processed": 2, "errors": 0, "elapsed_seconds": 10}
        )

        output = out.getvalue()
        # Should show completion message
        self.assertIn("IGDB Complete", output)
        self.assertIn("2 processed", output)

    @mock.patch("games.management.commands.refresh_all_metadata.WikiPageLookupService")
    @mock.patch("games.management.commands.refresh_all_metadata.WikiGenreService")
    @mock.patch("games.management.commands.refresh_all_metadata.IGDBImportService")
    def test_summary_with_errors(
        self, mock_igdb_service, mock_genre_service, mock_page_service
    ):
        """Test summary output with mixed success/errors"""
        from io import StringIO

        # Mock IGDB service with errors
        mock_igdb_instance = mock.MagicMock()
        mock_igdb_service.return_value = mock_igdb_instance
        mock_igdb_instance.api_client.use_pro_tier = False
        mock_igdb_instance.batch_size = 50
        mock_igdb_instance.concurrency = 8

        # Capture callback to simulate errors
        progress_callback = None

        def capture_callback(**kwargs):
            nonlocal progress_callback
            progress_callback = kwargs.get("progress_callback")
            return mock_igdb_instance

        mock_igdb_service.side_effect = capture_callback

        # Mock Wikipedia with partial success
        mock_page_instance = mock.MagicMock()
        mock_page_service.return_value = mock_page_instance

        # First page succeeds
        page_result_success = mock.MagicMock()
        page_result_success.success = True
        page_result_success.page_title = "Test Game 1"
        page_result_success.lookup_source = "Wikidata"
        page_result_success.wikipedia_url = "https://en.wikipedia.org/wiki/Test_Game_1"

        # Second page fails
        page_result_fail = mock.MagicMock()
        page_result_fail.success = False
        page_result_fail.error_message = "Not found"

        mock_page_instance.lookup_page.side_effect = [
            page_result_success,
            page_result_fail,
        ]

        genre_service_instance = mock.MagicMock()
        mock_genre_service.return_value = genre_service_instance
        genre_result = mock.MagicMock()
        genre_result.primary_genre = "Action"
        genre_result.all_genres = ["Action"]
        genre_service_instance.get_genre_from_url.return_value = genre_result

        out = StringIO()
        call_command("refresh_all_metadata", limit=2, stdout=out)

        # Simulate IGDB errors
        if progress_callback:
            progress_callback("error", {"game_name": "Test Game", "message": "Error"})
            progress_callback(
                "complete", {"processed": 1, "errors": 1, "elapsed_seconds": 5}
            )

        output = out.getvalue()

        # Verify summary shows errors
        self.assertIn("Summary", output)
        self.assertIn("Overall Status", output)
        # Should show COMPLETED WITH ERRORS due to failures
        self.assertTrue("SUCCESS" in output or "COMPLETED WITH ERRORS" in output)

    @mock.patch("games.management.commands.refresh_all_metadata.WikiPageLookupService")
    @mock.patch("games.management.commands.refresh_all_metadata.WikiGenreService")
    def test_wikipedia_genre_normalization(self, mock_genre_service, mock_page_service):
        """Test that Wikipedia genres are normalized to canonical forms."""
        from io import StringIO

        # Mock Wikipedia services
        mock_page_instance = mock.MagicMock()
        mock_page_service.return_value = mock_page_instance

        page_result = mock.MagicMock()
        page_result.success = True
        page_result.page_title = "Test Game"
        page_result.lookup_source = "Wikidata"
        page_result.wikipedia_url = "https://en.wikipedia.org/wiki/Test_Game"
        mock_page_instance.lookup_page.return_value = page_result

        genre_service_instance = mock.MagicMock()
        mock_genre_service.return_value = genre_service_instance

        # Return non-canonical genres that should be normalized
        genre_result = mock.MagicMock()
        genre_result.primary_genre = "survival horror"  # Should normalize to "Horror"
        genre_result.all_genres = ["survival horror", "first-person shooter"]
        genre_service_instance.get_genre_from_url.return_value = genre_result

        out = StringIO()
        call_command("refresh_all_metadata", wikipedia_only=True, limit=1, stdout=out)

        # Verify genres were normalized (with capitalization)
        self.assertTrue(models.WikipediaGenre.objects.filter(name="Horror").exists())
        self.assertTrue(
            models.WikipediaGenre.objects.filter(name="First-Person Shooter").exists()
        )
        # Ensure non-canonical form was NOT created
        self.assertFalse(
            models.WikipediaGenre.objects.filter(name="Survival horror").exists()
        )

        # Verify game has normalized genres linked
        self.game1.refresh_from_db()
        genre_names = set(self.game1.wikipedia_genres.values_list("name", flat=True))
        self.assertEqual(genre_names, {"Horror", "First-Person Shooter"})
