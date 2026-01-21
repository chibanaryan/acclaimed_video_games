"""Tests for user tracking service reconnection and merging."""

import time

from django.core.cache import cache
from django.test import TestCase

from core.models import User
from games.models import Game, PlayedGame, WantToPlayGame
from games.services.user_tracking_service import reconnect_tracking_records


class ReconnectTrackingRecordsTests(TestCase):
    """Test cases for reconnect_tracking_records function."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        cls.user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

    def setUp(self):
        cache.clear()

    def test_reconnect_orphaned_record_primary_id(self):
        """Test reconnecting orphaned record via primary IGDB ID."""
        # Create orphaned record
        played = PlayedGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=12345,
        )

        # Create game
        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345],
        )

        # Reconnect
        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[12345],
            primary_igdb_id=12345,
        )

        played.refresh_from_db()
        self.assertEqual(played.game, game)
        self.assertEqual(played.igdb_id, 12345)
        self.assertEqual(stats["played_reconnected"], 1)
        self.assertEqual(stats["played_merged"], 0)

    def test_reconnect_orphaned_record_secondary_id_normalizes(self):
        """Test that reconnecting via secondary ID normalizes igdb_id to primary."""
        # Create orphaned record with secondary ID
        played = PlayedGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=67890,  # Secondary ID
        )

        # Create game with 12345 as primary, 67890 as secondary
        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345, 67890],
        )

        # Reconnect
        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[12345, 67890],
            primary_igdb_id=12345,
        )

        played.refresh_from_db()
        self.assertEqual(played.game, game)
        # igdb_id should be normalized to primary
        self.assertEqual(played.igdb_id, 12345)
        self.assertEqual(stats["played_reconnected"], 1)

    def test_merge_duplicates_keeps_earliest(self):
        """Test that merging duplicates keeps the earliest record."""
        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345, 67890],
        )

        # Create two orphaned records for same user with different IDs
        # (simulates game merge scenario)
        played1 = PlayedGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=12345,
        )
        # Force a later created timestamp
        time.sleep(0.01)
        played2 = PlayedGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=67890,
        )

        # Reconnect - should merge and keep played1
        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[12345, 67890],
            primary_igdb_id=12345,
        )

        # Only one record should remain
        self.assertEqual(
            PlayedGame.objects.filter(user=self.user, game=game).count(), 1
        )
        # The surviving record should be the earliest (played1)
        surviving = PlayedGame.objects.get(user=self.user, game=game)
        self.assertEqual(surviving.id, played1.id)
        self.assertEqual(stats["played_merged"], 1)
        self.assertEqual(stats["played_reconnected"], 1)

    def test_different_users_not_merged(self):
        """Test that records from different users are not merged."""
        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345],
        )

        # Create records for two different users
        PlayedGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=12345,
        )
        PlayedGame.objects.create(
            user=self.user2,
            game=None,
            igdb_id=12345,
        )

        # Reconnect
        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[12345],
            primary_igdb_id=12345,
        )

        # Both records should still exist
        self.assertEqual(PlayedGame.objects.filter(game=game).count(), 2)
        self.assertEqual(stats["played_merged"], 0)
        self.assertEqual(stats["played_reconnected"], 2)

    def test_want_to_play_reconnection(self):
        """Test WantToPlayGame records are also reconnected."""
        want = WantToPlayGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=12345,
        )

        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345],
        )

        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[12345],
            primary_igdb_id=12345,
        )

        want.refresh_from_db()
        self.assertEqual(want.game, game)
        self.assertEqual(stats["want_reconnected"], 1)

    def test_want_to_play_secondary_id_normalizes(self):
        """Test WantToPlayGame igdb_id is normalized to primary."""
        want = WantToPlayGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=67890,  # Secondary ID
        )

        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345, 67890],
        )

        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[12345, 67890],
            primary_igdb_id=12345,
        )

        want.refresh_from_db()
        self.assertEqual(want.game, game)
        self.assertEqual(want.igdb_id, 12345)
        self.assertEqual(stats["want_reconnected"], 1)

    def test_no_orphaned_records(self):
        """Test that no errors occur when there are no orphaned records."""
        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345],
        )

        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[12345],
            primary_igdb_id=12345,
        )

        self.assertEqual(stats["played_reconnected"], 0)
        self.assertEqual(stats["want_reconnected"], 0)

    def test_empty_igdb_ids_list(self):
        """Test that empty igdb_ids list doesn't cause errors."""
        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345],
        )

        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[],
            primary_igdb_id=12345,
        )

        self.assertEqual(stats["played_reconnected"], 0)
        self.assertEqual(stats["want_reconnected"], 0)

    def test_both_played_and_want_reconnected(self):
        """Test both PlayedGame and WantToPlayGame are reconnected for different users."""
        PlayedGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=12345,
        )
        WantToPlayGame.objects.create(
            user=self.user2,
            game=None,
            igdb_id=12345,
        )

        game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
            all_igdb_ids=[12345],
        )

        stats = reconnect_tracking_records(
            game=game,
            igdb_ids=[12345],
            primary_igdb_id=12345,
        )

        self.assertEqual(stats["played_reconnected"], 1)
        self.assertEqual(stats["want_reconnected"], 1)
        self.assertEqual(len(stats["users_affected"]), 2)
