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


class CreateDeveloperAliasCommandTests(TestCase):

    def setUp(self):
        """Set up test developer"""
        self.developer = models.Developer.objects.create(
            name="Test Developer", slug="test-developer"
        )

    def test_creates_new_alias_for_existing_developer(self):
        """Test creating a new developer alias"""
        from io import StringIO

        out = StringIO()
        call_command(
            "create_developer_alias",
            "Test Alias",
            "test-developer",
            stdout=out,
        )
        output = out.getvalue()

        # Verify alias was created
        self.assertTrue(
            models.DeveloperAlias.objects.filter(name="Test Alias").exists()
        )
        alias = models.DeveloperAlias.objects.get(name="Test Alias")
        self.assertEqual(alias.developer_id, self.developer.id)
        # Verify output message
        self.assertIn("Created alias", output)

    def test_warns_when_alias_already_exists(self):
        """Test that command warns when alias already exists"""
        # Create an existing alias
        models.DeveloperAlias.objects.create(
            name="Existing Alias", developer=self.developer
        )

        from io import StringIO

        out = StringIO()
        call_command(
            "create_developer_alias",
            "Existing Alias",
            "test-developer",
            stdout=out,
        )
        output = out.getvalue()

        # Verify output contains warning
        self.assertIn("already exists", output)

    def test_returns_error_for_nonexistent_developer(self):
        """Test that command returns error for nonexistent developer"""
        from io import StringIO

        out = StringIO()
        call_command(
            "create_developer_alias",
            "New Alias",
            "nonexistent-developer",
            stdout=out,
        )
        output = out.getvalue()

        # Verify error message
        self.assertIn("not found", output)


class SyncDeveloperCommandTests(TestCase):

    def test_creates_developer_with_alias_and_game_association(self):
        """Test that sync_developer creates developer, alias, and associates games"""
        # Create a test game
        game = models.Game.objects.create(
            name="The Binding of Isaac",
            slug="the-binding-of-isaac",
            rank=1,
            year_of_release=2011,
        )

        from io import StringIO

        out = StringIO()
        call_command("sync_developer", "florian-himsl", stdout=out)
        output = out.getvalue()

        # Verify developer was created
        developer = models.Developer.objects.filter(slug="florian-himsl").first()
        self.assertIsNotNone(developer)
        self.assertEqual(developer.name, "Florian Himsl")
        self.assertEqual(developer.igdb_id, 40025)

        # Verify alias was created
        alias = models.DeveloperAlias.objects.filter(
            name="Florian Himsl", developer=developer
        ).first()
        self.assertIsNotNone(alias)

        # Verify game association
        self.assertTrue(game.developers.filter(developer=developer).exists())

        # Verify output
        self.assertIn("Created developer", output)
        self.assertIn("The Binding of Isaac", output)

    def test_warns_when_developer_already_exists(self):
        """Test that command warns when developer already exists"""
        # Create developer first
        models.Developer.objects.create(
            name="Florian Himsl",
            slug="florian-himsl",
            igdb_id=40025,
        )

        from io import StringIO

        out = StringIO()
        call_command("sync_developer", "florian-himsl", stdout=out)
        output = out.getvalue()

        # Verify warning message
        self.assertIn("already exists", output)

    def test_returns_error_for_unknown_developer_slug(self):
        """Test that command returns error for unknown developer"""
        from io import StringIO

        out = StringIO()
        call_command("sync_developer", "unknown-developer", stdout=out)
        output = out.getvalue()

        # Verify error message
        self.assertIn("Unknown developer slug", output)

    def test_force_flag_updates_existing_developer(self):
        """Test that --force flag updates existing developer"""
        # Create developer first
        dev = models.Developer.objects.create(
            name="Florian Himsl",
            slug="florian-himsl",
            igdb_id=12345,  # Wrong IGDB ID
        )

        from io import StringIO

        out = StringIO()
        call_command("sync_developer", "florian-himsl", "--force", stdout=out)
        output = out.getvalue()

        # Verify output indicates update
        self.assertIn("Updating existing developer", output)

        # Verify developer record was used
        dev.refresh_from_db()
        self.assertEqual(dev.name, "Florian Himsl")

    def test_syncs_all_three_developers(self):
        """Test syncing each of the three developers"""
        # Create test games
        for game_name, game_slug in [
            ("The Binding of Isaac", "the-binding-of-isaac"),
            ("Streets of Rage 2 / Bare Knuckle II", "streets-of-rage-2"),
            ("Paperboy", "paperboy"),
        ]:
            models.Game.objects.create(
                name=game_name,
                slug=game_slug,
                rank=1,
                year_of_release=2000,
            )

        from io import StringIO

        # Sync all three
        for dev_slug in [
            "florian-himsl",
            "shout-designworks",
            "vivid-games",
        ]:
            out = StringIO()
            call_command("sync_developer", dev_slug, stdout=out)
            output = out.getvalue()
            self.assertIn("Successfully synced developer", output)
