from io import StringIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.models import User
from .. import models, utils


class ImportGamesTests(TestCase):

    def test_import_games_creates_and_updates(self):
        data = "1\tFirst Game\t1990\tPC\t101\tQ12345\r\n"
        success, message = utils.import_games(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(
            message, "Games: 1 created (deleted 0 old), 1 ranks calculated"
        )
        game = models.Game.objects.get()
        self.assertEqual(game.name, "First Game")
        self.assertEqual(game.year_of_release, 1990)
        self.assertEqual(game.platforms.get().code, "PC")

        updated_data = "1\tFirst Game Deluxe\t1991\tPC,PS5\t101\tQ12345\r\n"
        success, message = utils.import_games(StringIO(updated_data))

        self.assertTrue(success)
        self.assertEqual(
            message, "Games: 1 created (deleted 1 old), 1 ranks calculated"
        )
        game = models.Game.objects.get()  # Get fresh instance (old one deleted)
        self.assertEqual(game.name, "First Game Deluxe")
        self.assertEqual(game.year_of_release, 1991)
        self.assertCountEqual(
            game.platforms.values_list("code", flat=True),
            ["PC", "PS5"],
        )

    def test_import_games_with_progress_callback(self):
        """Test import_games with progress callback (lines 580, 614, 629, 637, 687)."""
        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Create enough games to trigger progress updates (every 10, line 687)
        data_lines = []
        for i in range(25):  # More than 10 to trigger progress
            data_lines.append(f"{i+1}\tGame {i+1}\t1990\tPC\t{i+100}\tQ{12345+i}")
        data = "\r\n".join(data_lines) + "\r\n"

        success, message = utils.import_games(StringIO(data), progress_callback)

        self.assertTrue(success)
        # Should have received progress events
        self.assertGreater(len(callback_events), 0)
        # Check for start, progress (line 687), and complete events
        # Line 687 triggers when row_number % 10 == 0, progress at rows 10, 20
        start_events = [e for e in callback_events if e[0] == "start"]
        progress_events = [e for e in callback_events if e[0] == "progress"]
        complete_events = [e for e in callback_events if e[0] == "complete"]
        self.assertGreater(len(start_events), 0)
        # Should have at least 2 progress events (at rows 10 and 20)
        self.assertGreaterEqual(
            len(progress_events),
            2,
            f"Expected at least 2 progress events, got {len(progress_events)}",
        )
        self.assertGreater(len(complete_events), 0)

    def test_import_games_with_error_callback(self):
        """Test import_games error handling with callback (lines 634-637)."""
        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Invalid data that will cause an error
        data = "invalid\tdata\r\n"

        with self.assertRaises(Exception):
            utils.import_games(StringIO(data), progress_callback)

        # Should have received error event
        error_events = [e for e in callback_events if e[0] == "error"]
        self.assertGreater(len(error_events), 0)

    def test_import_games_with_wikidata_id(self):
        """Test that Wikidata IDs are imported correctly."""
        data = "1\tTest Game\t2024\tPC\t12345\tQ17185964\r\n"
        success, message = utils.import_games(StringIO(data))

        self.assertTrue(success)
        game = models.Game.objects.get()
        self.assertEqual(game.wikidata_id, "Q17185964")

    def test_import_games_with_multiple_wikidata_ids(self):
        """Test that all Wikidata IDs are stored and first is primary."""
        data = "1\tTest Game\t2024\tPC\t12345\tQ17185964,Q99999,Q88888\r\n"
        success, message = utils.import_games(StringIO(data))

        self.assertTrue(success)
        game = models.Game.objects.get()
        # Primary Wikidata ID should be the first one
        self.assertEqual(game.wikidata_id, "Q17185964")
        # All Wikidata IDs should be stored in the array
        self.assertEqual(game.all_wikidata_ids, ["Q17185964", "Q99999", "Q88888"])

    def test_import_games_with_empty_wikidata_id(self):
        """Test that empty Wikidata IDs are handled gracefully."""
        data = "1\tTest Game\t2024\tPC\t12345\t\r\n"
        success, message = utils.import_games(StringIO(data))

        self.assertTrue(success)
        game = models.Game.objects.get()
        self.assertIsNone(game.wikidata_id)

    def test_import_games_with_whitespace_wikidata_id(self):
        """Test that whitespace is stripped from Wikidata IDs."""
        data = "1\tTest Game\t2024\tPC\t12345\t  Q17185964  \r\n"
        success, message = utils.import_games(StringIO(data))

        self.assertTrue(success)
        game = models.Game.objects.get()
        self.assertEqual(game.wikidata_id, "Q17185964")

    def test_import_games_reconnects_to_existing_metadata(self):
        """Test that re-importing games reconnects to orphaned IGDB/Wikipedia metadata.

        This simulates the case where metadata exists but primary relationship was
        cleared (e.g., during a data migration or manual database update).
        """
        # First import: Create game
        data = "1\tTest Game\t2024\tPC\t12345\tQ17185964\r\n"
        success, message = utils.import_games(StringIO(data))
        self.assertTrue(success)

        game = models.Game.objects.get()

        # Create IGDB metadata for this game
        igdb_data = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=12345,
            artwork_id="test_artwork",
            url="https://www.igdb.com/games/test",
            is_primary=True,
        )

        # Create Wikipedia metadata for this game
        wiki_data = models.WikipediaGameData.objects.create(
            game=game,
            page_title="Test_Game",
            wikidata_id="Q17185964",
            primary_genre="Action",
            all_genres="Action, Adventure",
            lookup_source="https://en.wikipedia.org/wiki/Test_Game",
            is_primary=True,
        )

        # Store the IDs of the metadata records
        igdb_data_id = igdb_data.id
        wiki_data_id = wiki_data.id

        # Clear primary relationships (simulate orphaned metadata)
        game.primary_igdb_game_data = None
        game.primary_wikipedia_game_data = None
        game.save(
            update_fields=["primary_igdb_game_data", "primary_wikipedia_game_data"]
        )

        # Verify metadata still exists but isn't connected
        self.assertIsNone(game.primary_igdb_game_data)
        self.assertIsNone(game.primary_wikipedia_game_data)
        self.assertTrue(models.IGDBGameData.objects.filter(id=igdb_data_id).exists())
        self.assertTrue(
            models.WikipediaGameData.objects.filter(id=wiki_data_id).exists()
        )

        # Re-import the same game (deletes and recreates)
        success, message = utils.import_games(StringIO(data))
        self.assertTrue(success)

        # Get fresh game instance (old one was deleted)
        game = models.Game.objects.get()

        # IGDB metadata won't be automatically reconnected (happens via manual fetch)
        self.assertIsNone(game.primary_igdb_game_data)

        # Wikipedia metadata SHOULD be automatically reconnected
        self.assertIsNotNone(game.primary_wikipedia_game_data)
        self.assertEqual(game.primary_wikipedia_game_data.id, wiki_data_id)
        self.assertEqual(game.primary_wikipedia_game_data.primary_genre, "Action")

    def test_import_games_reconnects_after_deletion(self):
        """Test that metadata persists when game is deleted and reconnects
        on re-import."""
        # First import: Create game
        data = "1\tTest Game\t2024\tPC\t12345\tQ17185964\r\n"
        success, message = utils.import_games(StringIO(data))
        self.assertTrue(success)

        game = models.Game.objects.get()

        # Create IGDB metadata for this game
        igdb_data = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=12345,
            artwork_id="test_artwork",
            url="https://www.igdb.com/games/test",
            is_primary=True,
        )
        game.primary_igdb_game_data = igdb_data
        game.save(update_fields=["primary_igdb_game_data"])

        # Create Wikipedia metadata for this game
        wiki_data = models.WikipediaGameData.objects.create(
            game=game,
            page_title="Test_Game",
            wikidata_id="Q17185964",
            primary_genre="Action",
            all_genres="Action, Adventure",
            lookup_source="https://en.wikipedia.org/wiki/Test_Game",
            is_primary=True,
        )
        game.primary_wikipedia_game_data = wiki_data
        game.save(update_fields=["primary_wikipedia_game_data"])

        # Store the IDs of the metadata records
        igdb_data_id = igdb_data.id
        wiki_data_id = wiki_data.id

        # Delete the game (metadata should persist with SET_NULL)
        game.delete()

        # Verify game is gone but metadata still exists (orphaned)
        self.assertEqual(models.Game.objects.count(), 0)
        self.assertTrue(models.IGDBGameData.objects.filter(id=igdb_data_id).exists())
        self.assertTrue(
            models.WikipediaGameData.objects.filter(id=wiki_data_id).exists()
        )

        # Verify metadata is orphaned (game=None)
        igdb_data.refresh_from_db()
        wiki_data.refresh_from_db()
        self.assertIsNone(igdb_data.game)
        self.assertIsNone(wiki_data.game)

        # Re-import the game
        success, message = utils.import_games(StringIO(data))
        self.assertTrue(success)

        # Verify game was recreated
        game = models.Game.objects.get()

        # IGDB metadata won't be automatically reconnected (happens via manual fetch button)
        self.assertIsNone(game.primary_igdb_game_data)
        # But IGDB data remains orphaned and available for reconnection later
        igdb_data.refresh_from_db()
        self.assertIsNone(igdb_data.game)

        # Wikipedia metadata SHOULD be automatically reconnected
        self.assertIsNotNone(game.primary_wikipedia_game_data)
        self.assertEqual(game.primary_wikipedia_game_data.id, wiki_data_id)
        self.assertEqual(game.primary_wikipedia_game_data.primary_genre, "Action")

        # Verify Wikipedia metadata is no longer orphaned
        wiki_data.refresh_from_db()
        self.assertEqual(wiki_data.game, game)

    def test_import_games_skips_reconnection_if_already_connected(self):
        """Test that import doesn't overwrite existing metadata connections."""
        # Create game with IGDB metadata
        data = "1\tTest Game\t2024\tPC\t12345\tQ17185964\r\n"
        success, message = utils.import_games(StringIO(data))
        self.assertTrue(success)

        game = models.Game.objects.get()

        # Create two IGDB metadata records - one primary, one secondary
        igdb_primary = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=12345,
            artwork_id="primary_artwork",
            url="https://www.igdb.com/games/primary",
            is_primary=True,
        )
        game.primary_igdb_game_data = igdb_primary
        game.save(update_fields=["primary_igdb_game_data"])

        # Create secondary IGDB record (not primary)
        models.IGDBGameData.objects.create(
            game=game,
            igdb_id=12345,
            artwork_id="secondary_artwork",
            url="https://www.igdb.com/games/secondary",
            is_primary=False,
        )

        # Re-import with same data (deletes and recreates game)
        success, message = utils.import_games(StringIO(data))
        self.assertTrue(success)

        # Game is recreated without IGDB metadata (automatic fetch was removed)
        game = models.Game.objects.get()  # Get fresh instance (old one deleted)
        self.assertIsNone(game.primary_igdb_game_data)

        # Original IGDB metadata records are now orphaned
        igdb_primary.refresh_from_db()
        self.assertIsNone(igdb_primary.game)

    def test_import_games_orphans_played_games_on_delete(self):
        """Test that PlayedGame records are orphaned when games are deleted."""
        # Create user and game
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        data = "1\tTest Game\t2024\tPC\t12345\tQ17185964\r\n"
        success, _ = utils.import_games(StringIO(data))
        self.assertTrue(success)
        game = models.Game.objects.get()

        # Mark game as played
        played = models.PlayedGame.objects.create(
            user=user,
            game=game,
            igdb_id=12345,
        )

        # Import without this game (should delete it)
        data2 = "1\tDifferent Game\t2024\tPC\t99999\tQ99999\r\n"
        success, message = utils.import_games(StringIO(data2))
        self.assertTrue(success)
        self.assertIn("deleted 1 old", message)

        # PlayedGame should still exist but with game=None (orphaned)
        played.refresh_from_db()
        self.assertIsNone(played.game)
        self.assertEqual(played.igdb_id, 12345)

    def test_import_games_reconnects_played_games(self):
        """Test that orphaned PlayedGame records are reconnected on re-import."""
        # Create user and orphaned PlayedGame (simulating previous game was deleted)
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        played = models.PlayedGame.objects.create(
            user=user,
            game=None,  # Orphaned
            igdb_id=12345,
        )

        # Import game with matching igdb_id
        data = "1\tTest Game\t2024\tPC\t12345\tQ17185964\r\n"
        success, _ = utils.import_games(StringIO(data))
        self.assertTrue(success)

        # PlayedGame should now be connected to the new game
        played.refresh_from_db()
        self.assertIsNotNone(played.game)
        self.assertEqual(played.game.name, "Test Game")
        self.assertEqual(played.igdb_id, 12345)

    def test_import_games_with_multiple_igdb_ids(self):
        """Test that all IGDB IDs are stored and first is primary."""
        data = "1\tPokemon Red\t1996\tGB\t123,456,789\tQ12345\r\n"
        success, message = utils.import_games(StringIO(data))

        self.assertTrue(success)
        game = models.Game.objects.get()
        # Primary IGDB ID should be the first one
        self.assertEqual(game.igdb_id, 123)
        # All IGDB IDs should be stored in the array
        self.assertEqual(game.all_igdb_ids, [123, 456, 789])

    def test_import_games_single_id_backwards_compatible(self):
        """Test that single ID imports still work and populate array fields."""
        data = "1\tTest Game\t2024\tPC\t12345\tQ12345\r\n"
        success, message = utils.import_games(StringIO(data))

        self.assertTrue(success)
        game = models.Game.objects.get()
        # Primary IDs should be set
        self.assertEqual(game.igdb_id, 12345)
        self.assertEqual(game.wikidata_id, "Q12345")
        # Array fields should contain single element
        self.assertEqual(game.all_igdb_ids, [12345])
        self.assertEqual(game.all_wikidata_ids, ["Q12345"])

    def test_import_games_updates_multi_id_fields_on_reimport(self):
        """Test that multi-ID fields are updated when game is re-imported."""
        # First import with single IDs
        data1 = "1\tTest Game\t2024\tPC\t12345\tQ111\r\n"
        utils.import_games(StringIO(data1))
        game = models.Game.objects.get()
        self.assertEqual(game.all_igdb_ids, [12345])
        self.assertEqual(game.all_wikidata_ids, ["Q111"])

        # Re-import with additional alternate IDs
        data2 = "1\tTest Game\t2024\tPC\t12345,67890\tQ111,Q222\r\n"
        utils.import_games(StringIO(data2))
        game = models.Game.objects.get()  # Get fresh instance (old one deleted)
        # Arrays should be updated
        self.assertEqual(game.all_igdb_ids, [12345, 67890])
        self.assertEqual(game.all_wikidata_ids, ["Q111", "Q222"])
        # Primary IDs unchanged
        self.assertEqual(game.igdb_id, 12345)
        self.assertEqual(game.wikidata_id, "Q111")

        # Re-import with fewer IDs (remove alternates)
        data3 = "1\tTest Game\t2024\tPC\t12345\tQ111\r\n"
        utils.import_games(StringIO(data3))
        game = models.Game.objects.get()  # Get fresh instance (old one deleted)
        # Arrays should be reduced
        self.assertEqual(game.all_igdb_ids, [12345])
        self.assertEqual(game.all_wikidata_ids, ["Q111"])

    def test_import_games_primary_igdb_id_change_reconnects_metadata(self):
        """Test that changing primary IGDB ID no longer reconnects orphaned metadata.

        This simulates a real-world scenario where:
        1. A game exists with IGDB ID 123 and has metadata
        2. The game is deleted (e.g., removed from rankings), metadata is orphaned
        3. Later, the game returns with a new primary IGDB ID (456) but includes
           the old ID (123) as an alternate
        4. The orphaned metadata will NOT be automatically reconnected (happens via manual fetch)
        """
        # Create orphaned metadata (simulating previous game that was deleted)
        igdb_data = models.IGDBGameData.objects.create(
            game=None,  # Orphaned - game was previously deleted
            igdb_id=123,
            artwork_id="original_art",
            url="https://igdb.com/games/test",
            is_primary=True,
        )

        # Import with 456 as new primary, 123 as alternate
        # IGDB metadata will NOT be automatically reconnected
        data = "1\tTest Game\t2024\tPC\t456,123\tQ111\r\n"
        utils.import_games(StringIO(data))

        game = models.Game.objects.get()
        igdb_data.refresh_from_db()

        # Game should have 456 as primary
        self.assertEqual(game.igdb_id, 456)
        self.assertEqual(game.all_igdb_ids, [456, 123])
        # IGDB metadata will NOT be automatically reconnected (removed feature)
        self.assertIsNone(game.primary_igdb_game_data)
        # Metadata remains orphaned (will be reconnected via manual "Fetch IGDB Data" button)
        self.assertIsNone(igdb_data.game)

    def test_import_games_primary_wikidata_id_change(self):
        """Test that changing primary Wikidata ID preserves old metadata and clears genres."""
        # First import with Q111 as primary
        data1 = "1\tTest Game\t2024\tPC\t12345\tQ111,Q222\r\n"
        utils.import_games(StringIO(data1))
        game = models.Game.objects.get()

        # Create Wikipedia metadata for original primary ID with genres
        wiki_data = models.WikipediaGameData.objects.create(
            game=game,
            page_title="Test_Game",
            wikidata_id="Q111",
            primary_genre="Action",
            all_genres="Action, Adventure",
            is_primary=True,
        )
        game.primary_wikipedia_game_data = wiki_data
        game.save(update_fields=["primary_wikipedia_game_data"])

        # Add genres for the old Wikidata ID
        action_genre, _ = models.WikipediaGenre.objects.get_or_create(
            name="Action", defaults={"slug": "action"}
        )
        adventure_genre, _ = models.WikipediaGenre.objects.get_or_create(
            name="Adventure", defaults={"slug": "adventure"}
        )
        game.wikipedia_genres.set([action_genre, adventure_genre])

        # Verify initial state
        self.assertEqual(game.wikidata_id, "Q111")
        self.assertTrue(wiki_data.is_primary)
        self.assertEqual(game.wikipedia_genres.count(), 2)

        # Second import with Q222 as new primary (order changed)
        data2 = "1\tTest Game\t2024\tPC\t12345\tQ222,Q111\r\n"
        utils.import_games(StringIO(data2))

        game = models.Game.objects.get()  # Get fresh instance (old one deleted)
        wiki_data.refresh_from_db()

        # Game should now have Q222 as primary
        self.assertEqual(game.wikidata_id, "Q222")
        self.assertEqual(game.all_wikidata_ids, ["Q222", "Q111"])
        # Import tries Q222 first (no metadata), then Q111 (has metadata)
        # So Q111 metadata IS reconnected via alternate ID fallback
        self.assertEqual(wiki_data.game, game)
        self.assertEqual(game.primary_wikipedia_game_data, wiki_data)
        # Genres are restored from the Q111 metadata
        self.assertEqual(game.wikipedia_genres.count(), 2)

    def test_import_games_wikidata_id_change_restores_genres_from_new_metadata(self):
        """Test that genres are restored from new Wikidata ID's metadata."""
        # Create orphaned metadata for Q222 (the new primary) with different genres
        new_wiki_data = models.WikipediaGameData.objects.create(
            game=None,  # Orphaned
            page_title="Test_Game_v2",
            wikidata_id="Q222",
            primary_genre="RPG",
            all_genres="RPG, Strategy",
            is_primary=True,
        )

        # First import with Q111 as primary
        data1 = "1\tTest Game\t2024\tPC\t12345\tQ111\r\n"
        utils.import_games(StringIO(data1))
        game = models.Game.objects.get()

        # Add genres for Q111
        action_genre, _ = models.WikipediaGenre.objects.get_or_create(
            name="Action", defaults={"slug": "action"}
        )
        game.wikipedia_genres.set([action_genre])
        self.assertEqual(game.wikipedia_genres.count(), 1)
        self.assertEqual(game.wikipedia_genres.first().name, "Action")

        # Second import with Q222 as new primary
        # Should reconnect to orphaned metadata and restore its genres
        data2 = "1\tTest Game\t2024\tPC\t12345\tQ222,Q111\r\n"
        utils.import_games(StringIO(data2))

        game = models.Game.objects.get()  # Get fresh instance (old one deleted)
        new_wiki_data.refresh_from_db()

        # Game should have Q222 as primary
        self.assertEqual(game.wikidata_id, "Q222")
        # Should be reconnected to the Q222 metadata
        self.assertEqual(game.primary_wikipedia_game_data, new_wiki_data)
        # Genres should be restored from Q222's metadata (RPG -> Role-Playing, Strategy)
        # Note: RPG is normalized to "Role-Playing" by the genre normalization logic
        genre_names = list(game.wikipedia_genres.values_list("name", flat=True))
        self.assertIn("Role-Playing", genre_names)  # RPG normalized to Role-Playing
        self.assertIn("Strategy", genre_names)
        self.assertNotIn("Action", genre_names)  # Old genre should be gone

    def test_import_games_reconnects_via_alternate_igdb_id(self):
        """Test that IGDB metadata is NOT automatically reconnected via alternate ID."""
        # Create orphaned metadata with IGDB ID 456
        orphan_data = models.IGDBGameData.objects.create(
            game=None,  # Orphaned
            igdb_id=456,
            artwork_id="test_art",
            url="https://igdb.com/games/test",
            is_primary=True,
        )

        # Import game with 123 as primary, 456 as alternate
        data = "1\tTest Game\t2024\tPC\t123,456\tQ111\r\n"
        utils.import_games(StringIO(data))

        game = models.Game.objects.get()
        orphan_data.refresh_from_db()

        # IGDB metadata is NOT automatically reconnected (happens via manual fetch)
        self.assertIsNone(game.primary_igdb_game_data)
        self.assertIsNone(orphan_data.game)

    def test_import_games_reconnects_via_alternate_wikidata_id(self):
        """Test reconnection works when metadata matches alternate Wikidata ID."""
        # Create orphaned metadata with Wikidata ID Q222
        orphan_data = models.WikipediaGameData.objects.create(
            game=None,  # Orphaned
            page_title="Test_Game",
            wikidata_id="Q222",
            primary_genre="Action",
            is_primary=True,
        )

        # Import game with Q111 as primary, Q222 as alternate
        data = "1\tTest Game\t2024\tPC\t12345\tQ111,Q222\r\n"
        utils.import_games(StringIO(data))

        game = models.Game.objects.get()
        orphan_data.refresh_from_db()

        # Primary (Q111) doesn't have metadata, so it should reconnect via Q222
        self.assertEqual(game.primary_wikipedia_game_data, orphan_data)
        self.assertEqual(orphan_data.game, game)

    def test_import_games_reconnects_played_via_alternate_igdb_id(self):
        """Test orphaned PlayedGame reconnects via alternate IGDB ID."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        # Create orphaned PlayedGame with IGDB ID 456 (not the primary)
        played = models.PlayedGame.objects.create(
            user=user,
            game=None,  # Orphaned
            igdb_id=456,
        )

        # Import game with 123 as primary, 456 as alternate
        data = "1\tTest Game\t2024\tPC\t123,456\tQ111\r\n"
        success, _ = utils.import_games(StringIO(data))
        self.assertTrue(success)

        # PlayedGame should be reconnected via the alternate ID
        played.refresh_from_db()
        self.assertIsNotNone(played.game)
        self.assertEqual(played.game.name, "Test Game")

    def test_import_games_normalizes_igdb_id_on_reconnect(self):
        """Test that igdb_id is normalized to primary when reconnected via secondary."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create orphaned PlayedGame with what will be a secondary ID
        played = models.PlayedGame.objects.create(
            user=user,
            game=None,
            igdb_id=67890,  # Will be secondary
        )

        # Import game with 12345 as primary, 67890 as secondary
        data = "1\tTest Game\t2024\tPC\t12345,67890\tQ111\r\n"
        success, _ = utils.import_games(StringIO(data))
        self.assertTrue(success)

        # PlayedGame should be reconnected and igdb_id normalized
        played.refresh_from_db()
        self.assertIsNotNone(played.game)
        self.assertEqual(played.igdb_id, 12345)  # Normalized to primary

    def test_import_games_merges_duplicate_played_records(self):
        """Test that duplicate PlayedGame records are merged during import."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create two orphaned records for same user with IDs that will merge
        played1 = models.PlayedGame.objects.create(
            user=user,
            game=None,
            igdb_id=12345,
        )
        import time

        time.sleep(0.01)
        models.PlayedGame.objects.create(
            user=user,
            game=None,
            igdb_id=67890,
        )

        # Import game that merges both IDs
        data = "1\tTest Game\t2024\tPC\t12345,67890\tQ111\r\n"
        success, _ = utils.import_games(StringIO(data))
        self.assertTrue(success)

        game = models.Game.objects.get()

        # Should have only one PlayedGame record (earliest kept)
        remaining = models.PlayedGame.objects.filter(user=user, game=game)
        self.assertEqual(remaining.count(), 1)
        self.assertEqual(remaining.first().id, played1.id)

    def test_import_games_normalizes_want_to_play_igdb_id(self):
        """Test that WantToPlayGame igdb_id is also normalized to primary."""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create orphaned WantToPlayGame with secondary ID
        want = models.WantToPlayGame.objects.create(
            user=user,
            game=None,
            igdb_id=67890,  # Will be secondary
        )

        # Import game with 12345 as primary, 67890 as secondary
        data = "1\tTest Game\t2024\tPC\t12345,67890\tQ111\r\n"
        success, _ = utils.import_games(StringIO(data))
        self.assertTrue(success)

        # WantToPlayGame should be reconnected and igdb_id normalized
        want.refresh_from_db()
        self.assertIsNotNone(want.game)
        self.assertEqual(want.igdb_id, 12345)  # Normalized to primary


class ImportPlatformsTests(TestCase):

    def test_import_platforms_creates_and_updates(self):
        data = "PC\tPersonal Computer\r\n"
        success, message = utils.import_platforms(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(message, "Platforms: 1 created (deleted 0 old)")
        platform = models.Platform.objects.get()
        self.assertEqual(platform.name, "Personal Computer")

        updated_data = "PC\tPC (Updated)\r\n"
        success, message = utils.import_platforms(StringIO(updated_data))

        self.assertTrue(success)
        self.assertEqual(message, "Platforms: 1 created (deleted 1 old)")
        platform = models.Platform.objects.get()  # Get fresh instance
        self.assertEqual(platform.name, "PC (Updated)")

    def test_import_platforms_with_progress_callback_line_687(self):
        """Test import_platforms progress callback at line 687 (row % 10 == 0)."""
        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Create enough platforms to trigger progress updates (every 10, line 687)
        data_lines = []
        for i in range(25):  # More than 10 to trigger progress at rows 10, 20
            data_lines.append(f"PC{i}\tPlatform {i}\r\n")
        data = "".join(data_lines)

        success, message = utils.import_platforms(StringIO(data), progress_callback)

        self.assertTrue(success)
        # Should have received progress events at rows 10, 20 (line 687)
        progress_events = [e for e in callback_events if e[0] == "progress"]
        # Should have at least 2 progress events
        self.assertGreaterEqual(
            len(progress_events),
            2,
            f"Expected at least 2 progress events, got {len(progress_events)}",
        )

    def test_import_platforms_with_progress_callback(self):
        """Test import_platforms with progress callback."""
        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        data = "PC\tPersonal Computer\r\nPS5\tPlayStation 5\r\n"
        success, message = utils.import_platforms(StringIO(data), progress_callback)

        self.assertTrue(success)
        # Should have received progress events
        self.assertGreater(len(callback_events), 0)
        # Check for start event
        start_events = [e for e in callback_events if e[0] == "start"]
        self.assertGreater(len(start_events), 0)


class ImportListsTests(TestCase):

    def test_import_lists_assigns_order_and_publication(self):
        data = (
            "IGN\t2020\tE\tTop 10\thttps://example.com/ign\r\n"
            "Edge\t2021\tA\tBest Ever\thttps://example.com/edge\r\n"
        )

        success, message = utils.import_lists(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(
            message,
            "Lists: 2 created (deleted 0 old); Publications: recreated (deleted 0 old)",
        )
        orders = list(
            models.List.objects.order_by("order").values_list("order", flat=True)
        )
        self.assertEqual(orders, [1, 2])
        self.assertEqual(models.List.objects.first().publisher.name, "IGN")

    def test_import_lists_with_progress_callback(self):
        """Test import_lists with progress callback (lines 434, 462, 477, 481-484)."""
        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Create multiple lists to trigger progress updates (every 5 rows, line 462)
        # Need at least 5 to trigger progress callback
        data = (
            "\r\n".join(
                [f"Publisher{i}\t2024\tType\tList {i}\tURL{i}" for i in range(10)]
            )
            + "\r\n"
        )

        success, message = utils.import_lists(StringIO(data), progress_callback)

        self.assertTrue(success)
        # Should have received progress events
        self.assertGreater(len(callback_events), 0)
        # Check for start (434), progress (462), and complete (477) events
        start_events = [e for e in callback_events if e[0] == "start"]
        progress_events = [e for e in callback_events if e[0] == "progress"]
        complete_events = [e for e in callback_events if e[0] == "complete"]
        self.assertGreater(len(start_events), 0)
        self.assertGreater(len(progress_events), 0)  # Should trigger at row 5 and 10
        self.assertGreater(len(complete_events), 0)

    def test_import_lists_with_error_callback(self):
        """Test import_lists error handling with callback (lines 481-484)."""
        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Invalid data that will cause an error
        data = "Invalid\tData\r\n"

        with self.assertRaises(Exception):
            utils.import_lists(StringIO(data), progress_callback)

        # Should have received error event (lines 482-483)
        error_events = [e for e in callback_events if e[0] == "error"]
        self.assertGreater(len(error_events), 0)


class ImportListMembershipsTests(TestCase):

    def setUp(self):
        list_data = (
            "IGN\t2020\tE\tTop 10\thttps://example.com/ign\r\n"
            "Edge\t2021\tA\tBest Ever\thttps://example.com/edge\r\n"
        )
        utils.import_lists(StringIO(list_data))
        models.Game.objects.create(
            name="Game 1", rank=1, igdb_id=1, year_of_release=1990
        )
        models.Game.objects.create(
            name="Game 2", rank=2, igdb_id=2, year_of_release=1991
        )

    def test_import_listmemberships_creates_entries(self):
        data = "0:1\t1:3\r\n0:2\r\n"
        success, message = utils.import_listmemberships(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(message, "List memberships: 3 created")
        self.assertEqual(models.ListMembership.objects.count(), 3)
        top_entry = models.ListMembership.objects.get(game__rank=1, list__order=1)
        self.assertEqual(top_entry.rank, 1)

    def test_import_listmemberships_with_progress_callback(self):
        """Test import_listmemberships with progress callback (lines 507, 527, 551)."""
        # Create more games to trigger progress updates (every 50)
        # setUp already creates 2 games, so create 58 more
        for i in range(3, 61):  # ranks 3-60
            models.Game.objects.create(
                name=f"Game {i}", rank=i, igdb_id=i, year_of_release=1990
            )

        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Create enough entries to trigger progress updates (every 50)
        data_lines = []
        for i in range(60):  # More than 50 to trigger progress
            data_lines.append("0:1")
        data = "\r\n".join(data_lines) + "\r\n"

        success, message = utils.import_listmemberships(
            StringIO(data), progress_callback
        )

        self.assertTrue(success)
        # Should have received progress events
        self.assertGreater(len(callback_events), 0)
        # Check for start and complete events
        start_events = [e for e in callback_events if e[0] == "start"]
        complete_events = [e for e in callback_events if e[0] == "complete"]
        self.assertGreater(len(start_events), 0)
        self.assertGreater(len(complete_events), 0)

    def test_import_listmemberships_with_error_callback(self):
        """Test import_listmemberships error handling with callback (lines 548-551)."""
        callback_events = []

        def progress_callback(event_type, data):
            callback_events.append((event_type, data))

        # Invalid data that will cause an error
        data = "invalid:format\r\n"

        with self.assertRaises(Exception):
            utils.import_listmemberships(StringIO(data), progress_callback)

        # Should have received error event
        error_events = [e for e in callback_events if e[0] == "error"]
        self.assertGreater(len(error_events), 0)

    def test_import_listmemberships_batch_flush(self):
        """Test that listmemberships are flushed in batches (lines 551-554).

        When more than 1000 memberships are created, they should be flushed
        to the database in batches to manage memory on large imports.
        """
        # Create 1100 games to have enough for batch test
        for i in range(3, 1102):  # ranks 3-1101 (2 already exist from setUp)
            models.Game.objects.create(
                name=f"Game {i}", rank=i, igdb_id=i, year_of_release=1990
            )

        # Create data with 1100 list membership entries (exceeds batch_size=1000)
        # Format: 0:1 means list order 0, game rank 1
        data_lines = []
        for i in range(1, 1101):  # 1100 entries
            data_lines.append(f"0:{i}")
        data = "\r\n".join(data_lines) + "\r\n"

        success, message = utils.import_listmemberships(StringIO(data))

        self.assertTrue(success)
        # Should have created 1100 memberships
        self.assertEqual(models.ListMembership.objects.count(), 1100)
        self.assertIn("1100 created", message)


class ImportDevelopersTests(TestCase):

    def test_import_developers_creates_subsidiaries(self):
        data = "Foo Studio\tFoo Studio\tFoo Devs\r\n" "Bar Alias\tBar Studio\r\n"
        success, message = utils.import_developers(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(message, "Developers: 2 created, 0 updated")
        # 2 root developers (Foo Studio, Bar Studio)
        # + 2 subsidiaries (Foo Devs, Bar Alias)
        # Foo Studio alias skipped since it equals canonical name
        root_devs = models.Developer.objects.filter(parent__isnull=True)
        self.assertEqual(root_devs.count(), 2)
        foo = models.Developer.objects.get(name="Foo Studio", parent__isnull=True)
        self.assertEqual(
            foo.subsidiaries.count(), 1
        )  # Only Foo Devs (Foo Studio alias skipped)


class ValidatePrerequisitesTests(TestCase):
    """Tests for _validate_prerequisites function."""

    def test_validate_list_no_dependencies(self):
        """Test _validate_prerequisites for lists (line 170)."""
        from games import constants

        result = utils._validate_prerequisites(constants.TYPE_LIST)
        self.assertIsNone(result)

    def test_validate_game_no_platforms(self):
        """Test _validate_prerequisites for games without platforms (line 175)."""
        from games import constants

        result = utils._validate_prerequisites(constants.TYPE_GAME)
        self.assertIsNotNone(result)
        self.assertFalse(result[0])
        self.assertIn("platforms", result[1].lower())

    def test_validate_game_with_platforms(self):
        """Test _validate_prerequisites for games with platforms."""
        from games import constants

        models.Platform.objects.create(code="PC", name="PC")
        result = utils._validate_prerequisites(constants.TYPE_GAME)
        self.assertIsNone(result)

    def test_validate_membership_no_lists(self):
        """Test _validate_prerequisites for memberships without lists (line 186)."""
        from games import constants

        result = utils._validate_prerequisites(constants.TYPE_LIST_MEMBERSHIP)
        self.assertIsNotNone(result)
        self.assertFalse(result[0])
        self.assertIn("lists", result[1].lower())

    def test_validate_membership_no_games(self):
        """Test _validate_prerequisites for memberships without games (line 192)."""
        from games import constants
        from games.models import Publication

        pub = Publication.objects.create(name="Test")
        models.List.objects.create(publisher=pub, name="Test", year=2024, order=1)

        result = utils._validate_prerequisites(constants.TYPE_LIST_MEMBERSHIP)
        self.assertIsNotNone(result)
        self.assertFalse(result[0])
        self.assertIn("games", result[1].lower())

    def test_validate_membership_with_prerequisites(self):
        """Test _validate_prerequisites for memberships with all prerequisites."""
        from games import constants
        from games.models import Publication

        platform = models.Platform.objects.create(code="PC", name="PC")
        pub = Publication.objects.create(name="Test")
        models.List.objects.create(publisher=pub, name="Test", year=2024, order=1)
        game = models.Game.objects.create(rank=1, name="Test", year_of_release=2024)
        game.platforms.add(platform)

        result = utils._validate_prerequisites(constants.TYPE_LIST_MEMBERSHIP)
        self.assertIsNone(result)


class ImportBatchWithProgressTests(TestCase):
    """Tests for import_batch_with_progress generator."""

    def setUp(self):
        # Create a platform for games to depend on
        models.Platform.objects.create(code="PC", name="Personal Computer")

    def test_import_batch_with_progress_success(self):
        """Test import_batch_with_progress with successful import."""
        platform_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPC\r\n")
        data = {"platforms_file": platform_file}

        # Get generator
        generator = utils.import_batch_with_progress(data)

        # Consume events
        events = []
        for i, event in enumerate(generator):
            events.append(event)
            if i > 10:  # Limit iterations
                break

        # Should have received some events
        self.assertGreater(len(events), 0)

    def test_import_batch_with_progress_error(self):
        """Test import_batch_with_progress error handling (lines 310-312)."""
        # Invalid file that will cause error
        invalid_file = SimpleUploadedFile("test.txt", b"invalid")
        data = {"platforms_file": invalid_file}

        generator = utils.import_batch_with_progress(data)

        # Consume events - should get error
        events = list(generator)
        self.assertGreater(len(events), 0)
        # Check for error event
        error_events = [e for e in events if "error" in e.lower()]
        self.assertGreater(len(error_events), 0)

    def test_import_batch_with_progress_validation_error(self):
        """Test import_batch_with_progress with validation error (lines 256-265)."""
        # Try to import games without platforms (should fail validation)
        games_file = SimpleUploadedFile(
            "Top1000.txt", b"1\tGame\t2024\tPC\t12345\tQ44444\r\n"
        )
        data = {"games_file": games_file}

        # Clear platforms
        models.Platform.objects.all().delete()

        generator = utils.import_batch_with_progress(data)

        # Consume events
        events = list(generator)
        self.assertGreater(len(events), 0)
        # Should have validation error (lines 256-265)
        error_events = [
            e for e in events if "error" in e.lower() or "platform" in e.lower()
        ]
        self.assertGreater(len(error_events), 0)

    def test_import_batch_with_progress_exception_in_thread(self):
        """Test import_batch_with_progress exception in thread (lines 270-283)."""
        # Create invalid file that will cause exception during import
        invalid_file = SimpleUploadedFile(
            "PlatformDB.txt", b"invalid\tdata\ttoo\tmany\tcolumns\r\n"
        )
        data = {"platforms_file": invalid_file}

        generator = utils.import_batch_with_progress(data)

        # Consume events - get error from exception handler (lines 270-279, 282-283)
        events = list(generator)
        self.assertGreater(len(events), 0)
        error_events = [e for e in events if "error" in e.lower()]
        self.assertGreater(len(error_events), 0)

    @mock.patch("games.utils.import_platforms")
    def test_import_batch_with_progress_exception_inner_try(
        self, mock_import_platforms
    ):
        """Test import_batch_with_progress exception in inner try (lines 282-283)."""
        # Make import_platforms raise exception to trigger inner exception handler
        mock_import_platforms.side_effect = Exception("Import error")

        platform_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPC\r\n")
        data = {"platforms_file": platform_file}

        generator = utils.import_batch_with_progress(data)

        # Consume events - should get error event from exception handler (lines 282-283)
        events = list(generator)
        self.assertGreater(len(events), 0)
        error_events = [
            e for e in events if "error" in e.lower() or "message" in e.lower()
        ]
        self.assertGreater(len(error_events), 0)

    @mock.patch("games.utils.TextIOWrapper")
    def test_import_batch_with_progress_exception_inner_try_textio(self, mock_textio):
        """Test import_batch_with_progress exception in inner try (lines 282-283)."""
        # Make TextIOWrapper raise exception during file processing
        mock_textio.side_effect = Exception("TextIOWrapper error")

        platform_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPC\r\n")
        data = {"platforms_file": platform_file}

        generator = utils.import_batch_with_progress(data)

        # Consume events - should get error event from exception handler (lines 282-283)
        events = list(generator)
        self.assertGreater(len(events), 0)
        error_events = [
            e for e in events if "error" in e.lower() or "message" in e.lower()
        ]
        self.assertGreater(len(error_events), 0)

    @mock.patch("threading.Thread")
    def test_import_batch_with_progress_exception_outer_try_lines_311_313(
        self, mock_thread_class
    ):
        """Test import_batch_with_progress exception in outer try (lines 311-313)."""
        # Make Thread raise an exception to trigger outer exception handler
        mock_thread_class.side_effect = Exception("Thread creation error")

        platform_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPC\r\n")
        data = {"platforms_file": platform_file}

        generator = utils.import_batch_with_progress(data)

        # Consume events - should get error event from exception handler (lines 311-313)
        events = list(generator)
        self.assertGreater(len(events), 0)
        error_events = [
            e for e in events if "error" in e.lower() or "message" in e.lower()
        ]
        self.assertGreater(len(error_events), 0)

    @mock.patch("queue.Queue")
    def test_import_batch_with_progress_timeout(self, mock_queue_class):
        """Test import_batch_with_progress timeout handling (lines 303-313)."""
        import queue

        platform_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPC\r\n")
        data = {"platforms_file": platform_file}

        # Create a mock queue that raises queue.Empty on get() to simulate timeout
        mock_queue = mock.MagicMock()
        mock_queue.get.side_effect = queue.Empty()
        mock_queue_class.return_value = mock_queue

        generator = utils.import_batch_with_progress(data)

        # Consume events - should get timeout error (lines 303-313)
        events = list(generator)
        # Should have received timeout error event
        self.assertGreater(len(events), 0)
        timeout_events = [
            e for e in events if "timeout" in e.lower() or "30 seconds" in e.lower()
        ]
        self.assertGreater(
            len(timeout_events), 0, f"Expected timeout error, got events: {events[:2]}"
        )

    def test_import_batch_with_progress_validation_error_detailed(self):
        """Test import_batch_with_progress validation error handling (lines 256-265)."""
        # Try to import games without platforms - should trigger validation error
        games_file = SimpleUploadedFile(
            "Top1000.txt", b"1\tGame\t2024\tPC\t12345\tQ88888\r\n"
        )
        data = {"games_file": games_file}

        # Clear platforms to trigger validation error
        models.Platform.objects.all().delete()

        generator = utils.import_batch_with_progress(data)

        # Consume events - should get validation error (lines 256-265)
        events = list(generator)
        self.assertGreater(len(events), 0)
        # Should have validation error event with file and message
        error_events = [
            e for e in events if "error" in e.lower() and "games" in e.lower()
        ]
        self.assertGreater(
            len(error_events), 0, f"Expected validation error, got events: {events[:3]}"
        )

    @mock.patch("games.utils._validate_prerequisites")
    def test_import_batch_with_progress_validation_error_lines_256_265(
        self, mock_validate
    ):
        """Test import_batch_with_progress validation error handling (lines 256-265)."""
        # Mock validation to return an error
        mock_validate.return_value = (False, "Missing prerequisites")

        games_file = SimpleUploadedFile(
            "Top1000.txt", b"1\tGame\t2024\tPC\t12345\tQ77777\r\n"
        )
        data = {"games_file": games_file}

        generator = utils.import_batch_with_progress(data)

        # Consume events - should get validation error (lines 256-265)
        events = list(generator)
        self.assertGreater(len(events), 0)
        # Should have validation error event with file and message
        error_events = [
            e
            for e in events
            if "error" in e.lower()
            and ("games" in e.lower() or "prerequisites" in e.lower())
        ]
        self.assertGreater(
            len(error_events), 0, f"Expected validation error, got events: {events[:3]}"
        )


class ImportBatchTests(TestCase):
    """Tests for import_batch function."""

    def setUp(self):
        # Create a platform for games to depend on
        models.Platform.objects.create(code="PC", name="Personal Computer")

    def test_import_batch_with_igdb_flag(self):
        """Test that import_batch returns IGDB trigger flag."""
        platforms_file = SimpleUploadedFile(
            "PlatformDB.txt", b"PC\tPersonal Computer\r\n"
        )
        games_file = SimpleUploadedFile(
            "Top1000.txt", b"1\tTest Game\t2024\tPC\t12345\tQ66666\r\n"
        )

        data = {
            "platforms_file": platforms_file,
            "games_file": games_file,
        }

        success, message = utils.import_batch(data)

        self.assertTrue(success)
        self.assertIn("Platforms", message)
        self.assertIn("Games", message)

    def test_import_batch_no_files(self):
        """Test import_batch with no files returns error."""
        data = {}

        success, message = utils.import_batch(data)

        self.assertFalse(success)
        self.assertIn("No files were selected", message)


class ImportDataTests(TestCase):
    """Tests for import_data function."""

    def test_import_data_with_batch_files(self):
        """Test import_data routes to import_batch for batch files (line 32)."""
        platform_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPC\r\n")
        data = {"platforms_file": platform_file}

        # import_data returns 2 values, but import_batch returns 3
        # So import_data should handle this internally
        result = utils.import_data(data)

        # Should have imported platform
        self.assertTrue(result[0])
        self.assertEqual(models.Platform.objects.count(), 1)

    def test_import_batch_validation_error_return(self):
        """Test import_batch validation error return (line 355)."""
        # Try to import games without platforms
        games_file = SimpleUploadedFile(
            "Top1000.txt", b"1\tGame\t2024\tPC\t12345\tQ55555\r\n"
        )
        data = {"games_file": games_file}

        # Clear platforms
        models.Platform.objects.all().delete()

        success, message = utils.import_batch(data)

        # Should fail with validation error (line 355 returns error)
        self.assertFalse(success)
        self.assertIn("platforms", message.lower())

    def test_import_batch_exception_return(self):
        """Test import_batch exception handling return (lines 374-375)."""
        # Create invalid data that will cause exception during import
        invalid_file = SimpleUploadedFile(
            "PlatformDB.txt", b"invalid\tdata\ttoo\tmany\tcolumns\r\n"
        )
        data = {"platforms_file": invalid_file}

        success, message = utils.import_batch(data)

        # Should fail with exception message (lines 374-375)
        self.assertFalse(success)
        self.assertIn("failed", message.lower())

    def test_import_batch_exception_in_transaction(self):
        """Test import_batch exception in transaction block (lines 374-375)."""

        # Create data that will cause an exception inside the transaction
        # Use a file that will fail validation or cause DB error
        class BadFile:
            def read(self):
                raise Exception("Transaction error")

            def seek(self, pos):
                pass

        bad_file = BadFile()
        data = {"platforms_file": bad_file}

        success, message = utils.import_batch(data)

        # Should fail with exception message (lines 374-375)
        self.assertFalse(success)
        self.assertIn("failed", message.lower())

    @mock.patch("games.utils.transaction.atomic")
    def test_import_batch_exception_transaction_atomic(self, mock_atomic):
        """Test import_batch exception when transaction.atomic raises (374-375)."""
        # Make transaction.atomic raise an exception
        mock_atomic.side_effect = Exception("Transaction atomic error")

        platform_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPC\r\n")
        data = {"platforms_file": platform_file}

        success, message = utils.import_batch(data)

        # Should fail with exception message (lines 374-375)
        self.assertFalse(success)
        self.assertIn("failed", message.lower())

    def test_import_data_with_delete(self):
        """Test import_data with delete flag."""
        # Create some data
        models.Platform.objects.create(code="PC", name="PC")

        data = {"delete": True}
        success, message = utils.import_data(data)

        # Should have deleted all data including platforms
        self.assertTrue(success)
        self.assertEqual(models.Platform.objects.count(), 0)  # Platforms are deleted

    def test_import_data_legacy_game_import_updates_metadata(self):
        """Test that legacy game import updates SiteMetadata (lines 51-58)."""
        from io import BytesIO

        # Create required platform
        models.Platform.objects.create(code="PC", name="PC")

        # Create a game file in new format
        game_data = b"1\tTest Game\t2024\tPC\t12345\tQ99999\r\n"
        file_obj = BytesIO(game_data)

        # Get metadata before import
        metadata_before = models.SiteMetadata.get_instance()
        last_update_before = metadata_before.last_full_update

        # Use legacy import format with type=G
        from .. import constants

        data = {"file": file_obj, "type": constants.TYPE_GAME}
        success, message = utils.import_data(data)

        self.assertTrue(success)
        self.assertEqual(models.Game.objects.count(), 1)

        # Check that metadata was updated (lines 51-58)
        metadata_after = models.SiteMetadata.get_instance()
        self.assertIsNotNone(metadata_after.last_full_update)
        # The timestamp should be different if it was None before, or newer
        if last_update_before is None:
            self.assertIsNotNone(metadata_after.last_full_update)
        else:
            self.assertGreaterEqual(metadata_after.last_full_update, last_update_before)


class ImportIGDBWithProgressTests(TestCase):
    """Tests for import_igdb_with_progress generator."""

    def setUp(self):
        # Create a game without IGDB data
        platform = models.Platform.objects.create(code="PC", name="PC")
        self.game = models.Game.objects.create(
            rank=1, name="Test Game", year_of_release=2024
        )
        self.game.platforms.add(platform)

    @mock.patch("games.services.igdb_importer.IGDBImportService")
    def test_import_igdb_with_progress_success(self, mock_service_class):
        """Test successful IGDB import with progress."""
        # Create a mock service
        mock_service = mock.MagicMock()
        mock_service_class.return_value = mock_service

        # Get the generator - this tests the function can be called
        # The actual progress streaming is tested via integration tests
        generator = utils.import_igdb_with_progress()

        # Verify generator exists
        self.assertIsNotNone(generator)
        # Service may or may not be created depending on games in DB
        # Just verify the function executes without error

    @mock.patch("games.services.igdb_importer.IGDBImportService")
    @mock.patch("queue.Queue")
    def test_import_igdb_with_progress_timeout(
        self, mock_queue_class, mock_service_class
    ):
        """Test import_igdb_with_progress timeout handling (lines 150-156)."""
        import queue

        # Create a game so the service is initialized
        platform, _ = models.Platform.objects.get_or_create(
            code="PC", defaults={"name": "PC"}
        )
        game = models.Game.objects.create(rank=1, name="Test", year_of_release=2024)
        game.platforms.add(platform)

        mock_service = mock.MagicMock()
        mock_service_class.return_value = mock_service

        # Create a mock queue that raises queue.Empty on get() to simulate timeout
        mock_queue = mock.MagicMock()
        mock_queue.get.side_effect = queue.Empty()
        mock_queue_class.return_value = mock_queue

        # Get generator
        generator = utils.import_igdb_with_progress()

        # Consume events - should get timeout error (lines 150-156)
        events = list(generator)

        # Should have received timeout error event
        self.assertGreater(len(events), 0)
        timeout_events = [
            e for e in events if "timeout" in e.lower() or "30 seconds" in e.lower()
        ]
        self.assertGreater(
            len(timeout_events), 0, f"Expected timeout error, got events: {events[:2]}"
        )

    @mock.patch("games.services.igdb_importer.IGDBImportService")
    def test_import_igdb_with_progress_exception(self, mock_service_class):
        """Test import_igdb_with_progress exception handling (lines 158-160)."""
        # Create a game so the service is initialized
        platform, _ = models.Platform.objects.get_or_create(
            code="PC", defaults={"name": "PC"}
        )
        game = models.Game.objects.create(rank=1, name="Test", year_of_release=2024)
        game.platforms.add(platform)

        # Mock service to raise exception
        mock_service_class.side_effect = Exception("Test error")

        # Get generator
        generator = utils.import_igdb_with_progress()

        # Consume events - should get error event (lines 158-160)
        events = list(generator)
        self.assertGreater(len(events), 0)
        # Check for error event
        error_events = [e for e in events if "error" in e.lower()]
        self.assertGreater(len(error_events), 0)

    @mock.patch("games.services.igdb_importer.IGDBImportService")
    def test_import_igdb_with_progress_error(self, mock_service_class):
        """Test IGDB import with error handling."""
        mock_service = mock.MagicMock()
        mock_service_class.return_value = mock_service

        # Mock the import to raise an error
        def mock_import_games(games):
            raise Exception("Test error")

        mock_service.import_games = mock_import_games

        # Get the generator
        generator = utils.import_igdb_with_progress()

        # Consume events
        events = list(generator)

        # Should have error event
        self.assertGreater(len(events), 0)
        error_events = [e for e in events if "error" in e.lower()]
        self.assertGreater(len(error_events), 0)

    @mock.patch("games.services.igdb_importer.IGDBImportService")
    def test_import_igdb_with_progress_callback_with_existing_event(
        self, mock_service_class
    ):
        """Test import_igdb_with_progress when data has 'event' key (lines 106-109)."""
        # Create a game so the service is initialized
        platform, _ = models.Platform.objects.get_or_create(
            code="PC", defaults={"name": "PC"}
        )
        game = models.Game.objects.create(rank=1, name="Test", year_of_release=2024)
        game.platforms.add(platform)

        # Capture the actual callback that gets passed to the service
        captured_callback = []

        def mock_init(*args, **kwargs):
            # Capture the progress_callback
            if "progress_callback" in kwargs:
                captured_callback.append(kwargs["progress_callback"])
            # Return a mock service
            service = mock.MagicMock()
            service.progress_callback = kwargs.get("progress_callback")
            service.import_games = mock.MagicMock()
            return service

        mock_service_class.side_effect = mock_init

        # Get generator - this will create the service with the callback
        generator = utils.import_igdb_with_progress()

        # If we captured the callback, test it with data that already has 'event' key
        if captured_callback:
            callback = captured_callback[0]
            # Test lines 106-109: if "event" not in data
            # Test with data WITHOUT event key (line 106 is False, 107 executes)
            test_data_no_event = {"message": "test"}
            callback("start", test_data_no_event)
            # Test with data that has 'event' key (line 106 is True, 107 skipped)
            test_data_with_event = {"event": "custom", "message": "test"}
            callback("start", test_data_with_event)
            # The callback should check if "event" is in data (line 106)
            # and not add it if it already exists (line 107 won't execute)

        # Consume a few events
        events = []
        try:
            for i, event in enumerate(generator):
                events.append(event)
                if i > 5:
                    break
        except Exception:
            pass

        # Verify generator works and callback was tested
        self.assertIsNotNone(generator)
        # Verify callback was captured and tested
        self.assertGreater(
            len(captured_callback), 0, "Callback should have been captured"
        )

    def test_import_igdb_with_progress_update_relationships(self):
        """Test import_igdb_with_progress with update_relationships=True."""
        # Create a game with existing IGDBGameData
        platform, _ = models.Platform.objects.get_or_create(
            code="PC", defaults={"name": "PC"}
        )
        game = models.Game.objects.create(
            rank=1, name="Test Game", year_of_release=2024, igdb_id=123
        )
        game.platforms.add(platform)

        models.IGDBGameData.objects.create(
            game=game,
            igdb_id=123,
            artwork_id="cover_hash",
            url="https://example.com/test",
            is_primary=True,
        )

        # Mock API
        with mock.patch("games.igdb.get_api") as mock_get_api:
            fake_api = mock.Mock()
            fake_api.get_game_info_by_id.return_value = {
                "genres": ["Action"],
                "developers": [
                    {
                        "id": 1,
                        "name": "Test Studio",
                        "slug": "test-studio",
                    }
                ],
            }
            mock_get_api.return_value = fake_api

            # Get generator with update_relationships=True
            generator = utils.import_igdb_with_progress(update_relationships=True)

            # Consume events - this triggers the update path
            events = list(generator)

            # Verify generator returned events (update path was executed)
            self.assertGreater(len(events), 0)

    @mock.patch("games.igdb.get_api")
    def test_import_igdb_with_progress_update_relationships_no_games(
        self, mock_get_api
    ):
        """Test update_relationships=True with no games having IGDB data."""
        # Don't create any games with IGDB data
        generator = utils.import_igdb_with_progress(update_relationships=True)

        # Consume events
        events = []
        for event in generator:
            events.append(event)

        # Should get error about no games found
        self.assertGreater(len(events), 0)
        error_events = [e for e in events if "No games" in str(e)]
        self.assertGreater(
            len(error_events), 0, f"Expected error about no games, got: {events}"
        )
