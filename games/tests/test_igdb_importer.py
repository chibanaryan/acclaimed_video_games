"""Tests for IGDBImportService."""

from unittest import mock

from django.test import TestCase

from games import models
from games.services.igdb_importer import IGDBImportService


class IGDBImportServiceTests(TestCase):
    """Tests for IGDBImportService class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a platform and game
        self.platform = models.Platform.objects.create(code="PC", name="PC")
        self.game = models.Game.objects.create(
            rank=1, name="Test Game", year_of_release=2024, igdb_id=12345
        )
        self.game.platforms.add(self.platform)

    @mock.patch("games.services.igdb_importer.get_api")
    def test_init_fails_when_api_client_is_none(self, mock_get_api):
        """Test initialization raises RuntimeError when API client is None (line 51)."""
        mock_get_api.return_value = None

        with self.assertRaises(RuntimeError) as cm:
            IGDBImportService()
        self.assertIn("Failed to initialize", str(cm.exception))

    @mock.patch("games.services.igdb_importer.get_api")
    def test_init_auto_detects_batch_size(self, mock_get_api):
        """Test that batch_size is auto-detected from tier when None (line 58)."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        service = IGDBImportService(batch_size=None)
        self.assertEqual(service.batch_size, 50)

    @mock.patch("games.services.igdb_importer.get_api")
    def test_import_games_no_games_in_database(self, mock_get_api):
        """Test import_games with no games returns early (lines 89-98)."""
        mock_api = mock.MagicMock()
        mock_get_api.return_value = mock_api

        service = IGDBImportService()

        # Query games that don't exist
        games = models.Game.objects.filter(igdb_id=99999)

        processed, errors, elapsed = service.import_games(games)

        self.assertEqual(processed, 0)
        self.assertEqual(errors, 0)
        self.assertEqual(elapsed, 0.0)

    @mock.patch("games.services.igdb_importer.get_api")
    def test_import_games_error_notification(self, mock_get_api):
        """Test error notification path (line 163)."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Use batch_size > 0 to trigger _import_batched path (line 163)
        service = IGDBImportService(
            progress_callback=progress_callback, batch_size=10, concurrency=1
        )

        # Mock get_igdb_data to raise an error in the batch processing
        # Actually, we need to mock the batch processing to return an error
        with mock.patch.object(
            service,
            "_process_game_batch",
            return_value=[(False, self.game, "Test error")],
        ):
            processed, errors, elapsed = service.import_games(
                models.Game.objects.filter(pk=self.game.pk)
            )

        # Should have error notification (line 163)
        error_events = [e for e in callback_events if e[0] == "error"]
        self.assertGreater(len(error_events), 0)

    @mock.patch("games.services.igdb_importer.get_api")
    def test_import_games_progress_notification(self, mock_get_api):
        """Test progress notification on success (line 195)."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Use concurrency > 1 to trigger _import_concurrent path (line 195)
        service = IGDBImportService(
            progress_callback=progress_callback, batch_size=0, concurrency=2
        )

        # Mock successful processing
        with mock.patch.object(
            service, "_process_game", return_value=(True, self.game, None)
        ):
            processed, errors, elapsed = service.import_games(
                models.Game.objects.filter(pk=self.game.pk)
            )

        # Should have progress notification (line 195)
        progress_events = [e for e in callback_events if e[0] == "progress"]
        self.assertGreater(len(progress_events), 0)

    @mock.patch("games.services.igdb_importer.get_api")
    def test_process_game_batch_no_igdb_ids(self, mock_get_api):
        """Test _process_game_batch with games that have no IGDB IDs (lines 298-302)."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        service = IGDBImportService()

        # Create game without IGDB ID
        game_no_id = models.Game.objects.create(
            rank=2, name="No IGDB Game", year_of_release=2024
        )
        game_no_id.platforms.add(self.platform)

        results = service._process_game_batch([game_no_id])

        # Should return error for each game (lines 298-302)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])  # success is False
        self.assertEqual(results[0][2], "No IGDB ID")

    @mock.patch("games.services.igdb_importer.get_api")
    def test_process_game_batch_exception_handling(self, mock_get_api):
        """Test _process_game_batch exception handling (lines 402-416)."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        # Make get_games_info_by_ids raise an exception
        mock_api.get_games_info_by_ids.side_effect = Exception("API Error")

        service = IGDBImportService()

        results = service._process_game_batch([self.game])

        # Should mark all games as errors (lines 402-416)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])  # success is False
        self.assertIn("Batch fetch failed", results[0][2])

    @mock.patch("games.services.igdb_importer.get_api")
    def test_process_game_batch_not_found_in_response(self, mock_get_api):
        """Test _process_game_batch when game not found in IGDB (lines 406-409)."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        # Return empty response (game not found)
        mock_api.get_games_info_by_ids.return_value = {}

        service = IGDBImportService()

        results = service._process_game_batch([self.game])

        # Should mark as error (lines 406-409)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])  # success is False
        self.assertEqual(results[0][2], "Not found in IGDB response")

    @mock.patch("games.services.igdb_importer.get_api")
    def test_process_game_batch_exception_during_processing(self, mock_get_api):
        """Test _process_game_batch exception during game processing."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        # Return valid game data
        mock_api.get_games_info_by_ids.return_value = {
            self.game.igdb_id: {"slug": "test-game", "cover": "//cover.jpg"}
        }

        service = IGDBImportService()

        # Make get_igdb_data() raise an exception to test error handling
        with mock.patch.object(
            self.game, "get_igdb_data", side_effect=Exception("Processing error")
        ):
            results = service._process_game_batch([self.game])

        # Should catch exception and mark as error
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])  # success is False
        self.assertIn("Processing error", results[0][2])

    @mock.patch("games.services.igdb_importer.get_api")
    def test_estimate_remaining_with_zero_elapsed(self, mock_get_api):
        """Test _estimate_remaining with zero elapsed time (line 423)."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        service = IGDBImportService()

        # Test with elapsed <= 0 (line 423)
        remaining = service._estimate_remaining(10, 100, 0.0)
        self.assertEqual(remaining, 0)

        remaining = service._estimate_remaining(10, 100, -1.0)
        self.assertEqual(remaining, 0)

    @mock.patch("games.services.igdb_importer.get_api")
    def test_process_game_batch_with_parent_developer(self, mock_get_api):
        """Test _process_game_batch with developer that has parent (lines 339-360)."""
        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        # Return game data with developer that has a parent
        # The data structure needs to match what _process_game_batch expects
        # It looks for "developers" key, not "involved_companies"
        mock_api.get_games_info_by_ids.return_value = {
            self.game.igdb_id: {
                "slug": "test-game",
                "cover": "//cover.jpg",
                "developers": [
                    {
                        "id": 100,
                        "name": "Child Studio",
                        "slug": "child-studio",
                        "parent": {
                            "id": 200,
                            "name": "Parent Corp",
                            "slug": "parent-corp",
                        },
                    }
                ],
            }
        }

        service = IGDBImportService()

        results = service._process_game_batch([self.game])

        # Should process successfully and create parent developer (lines 339-360)
        self.assertEqual(len(results), 1)
        # Check that parent developer was created
        parent_dev = models.Developer.objects.filter(name="Parent Corp").first()
        self.assertIsNotNone(parent_dev)

    @mock.patch("games.services.igdb_importer.get_api")
    def test_process_game_batch_parent_alias_integrity_error(self, mock_get_api):
        """Test _process_game_batch handles IntegrityError for parent (359-360)."""
        from django.db import IntegrityError

        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        # Return game data with developer that has parent
        # Use "developers" key as that's what _process_game_batch expects
        parent_name = "Parent Corp"
        mock_api.get_games_info_by_ids.return_value = {
            self.game.igdb_id: {
                "slug": "test-game",
                "cover": "//cover.jpg",
                "developers": [
                    {
                        "id": 100,
                        "name": "Child Studio",
                        "slug": "child-studio",
                        "parent": {
                            "id": 200,
                            "name": parent_name,
                            "slug": "parent-corp",
                        },
                    }
                ],
            }
        }

        # Create a DeveloperAlias with the same name but different developer
        # This will cause IntegrityError when trying to create parent alias
        # because name has unique constraint
        other_dev = models.Developer.objects.create(name="Other Dev")
        models.DeveloperAlias.objects.create(
            developer=other_dev,
            name=parent_name,  # Same name, different dev - causes IntegrityError
        )

        service = IGDBImportService()

        # Mock update_or_create to raise IntegrityError on parent alias (lines 359-360)
        # Simulates a race condition where the alias already exists
        call_count = [0]
        original_update = models.DeveloperAlias.objects.update_or_create

        def mock_update_or_create(*args, **kwargs):
            call_count[0] += 1
            # Second call (for parent alias) raises IntegrityError
            # This should be caught by the except block at lines 359-360
            if call_count[0] == 2:
                raise IntegrityError("duplicate key value violates unique constraint")
            return original_update(*args, **kwargs)

        with mock.patch(
            "games.models.DeveloperAlias.objects.update_or_create",
            side_effect=mock_update_or_create,
        ):
            results = service._process_game_batch([self.game])

        # Should handle IntegrityError gracefully
        self.assertEqual(len(results), 1)

    @mock.patch("games.services.igdb_importer.get_api")
    def test_process_game_batch_developer_alias_integrity_error(self, mock_get_api):
        """Test _process_game_batch handles IntegrityError for dev (lines 372-373)."""
        from django.db import IntegrityError

        mock_api = mock.MagicMock()
        mock_api.max_batch_size = 50
        mock_get_api.return_value = mock_api

        # Return game data with developer
        # Use "developers" key as that's what _process_game_batch expects
        mock_api.get_games_info_by_ids.return_value = {
            self.game.igdb_id: {
                "slug": "test-game",
                "cover": "//cover.jpg",
                "developers": [{"id": 100, "name": "Test Dev", "slug": "test-dev"}],
            }
        }

        service = IGDBImportService()

        # Mock update_or_create to raise IntegrityError on alias (lines 372-373)
        call_count = [0]
        original_update = models.DeveloperAlias.objects.update_or_create

        def mock_update_or_create(*args, **kwargs):
            call_count[0] += 1
            # Second call (for alias) raises IntegrityError, then get() is called
            if call_count[0] == 2:
                raise IntegrityError("duplicate key")
            return original_update(*args, **kwargs)

        # Create a mock alias to return from get()
        mock_alias = mock.MagicMock()
        mock_alias.developer = models.Developer.objects.create(
            name="Test Dev", igdb_id=100
        )

        with mock.patch(
            "games.models.DeveloperAlias.objects.update_or_create",
            side_effect=mock_update_or_create,
        ):
            with mock.patch(
                "games.models.DeveloperAlias.objects.get",
                return_value=mock_alias,
            ):
                results = service._process_game_batch([self.game])

        # Should handle IntegrityError gracefully
        self.assertEqual(len(results), 1)
