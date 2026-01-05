"""Tests for percentile service."""

from django.core.cache import cache
from django.test import TestCase

from core.models import User
from games.models import Game, PlayedGame
from games.services.percentile_service import (
    calculate_percentile,
    get_played_games_distribution,
)


class PercentileServiceTests(TestCase):
    """Tests for percentile calculation."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_zero_played_returns_none_percentile(self):
        """User with 0 played games gets None percentile."""
        result = calculate_percentile(0)
        self.assertIsNone(result["percentile"])
        self.assertIn("Start tracking", result["message"])

    def test_single_user_returns_first_message(self):
        """Single active user gets special message."""
        user = User.objects.create_user(
            username="test", email="test@example.com", password="pass"
        )
        game = Game.objects.create(name="Test", rank=1, igdb_id=1)
        PlayedGame.objects.create(user=user, game=game, igdb_id=1)

        result = calculate_percentile(1)
        self.assertEqual(result["percentile"], 100)
        self.assertIn("first", result["message"].lower())

    def test_small_population_shows_rank(self):
        """Small populations (< 10 users) show rank instead of percentile."""
        game = Game.objects.create(name="Test", rank=1, igdb_id=1)

        # Create 2 users with different game counts
        user1 = User.objects.create_user(username="user1", email="user1@example.com")
        user2 = User.objects.create_user(username="user2", email="user2@example.com")

        PlayedGame.objects.create(user=user1, game=game, igdb_id=1)
        PlayedGame.objects.create(user=user2, game=game, igdb_id=1)
        PlayedGame.objects.create(user=user2, game=game, igdb_id=2)

        # User with 2 games is #1
        result = calculate_percentile(2)
        self.assertIsNone(result["percentile"])
        self.assertIn("#1 of 2", result["message"])

        # User with 1 game is #2
        result = calculate_percentile(1)
        self.assertIsNone(result["percentile"])
        self.assertIn("#2 of 2", result["message"])

    def test_percentile_calculation_accuracy(self):
        """Percentile calculates correctly with 10+ users."""
        # Create a game
        game = Game.objects.create(name="Test", rank=1, igdb_id=1)

        # Create 10 users with 1-10 games played
        for i in range(1, 11):
            user = User.objects.create_user(
                username=f"user{i}", email=f"user{i}@example.com"
            )
            for j in range(i):
                PlayedGame.objects.create(
                    user=user, game=game, igdb_id=game.igdb_id + j
                )

        # User with 5 games should be at 40th percentile
        # (4 users have fewer games: 1, 2, 3, 4)
        result = calculate_percentile(5)
        self.assertEqual(result["percentile"], 40)
        self.assertEqual(result["total_users"], 10)

    def test_top_one_percent_message(self):
        """Users in top 1% get special message."""
        game = Game.objects.create(name="Test", rank=1, igdb_id=1)

        # Create 100 users with 1 game each
        for i in range(100):
            user = User.objects.create_user(
                username=f"user{i}", email=f"user{i}@example.com"
            )
            PlayedGame.objects.create(user=user, game=game, igdb_id=game.igdb_id)

        # User with 100 games should be in top 1%
        result = calculate_percentile(100)
        self.assertEqual(result["percentile"], 100)
        self.assertIn("top 1%", result["message"])

    def test_excludes_orphaned_played_games(self):
        """Only counts non-orphaned PlayedGame records."""
        user = User.objects.create_user(username="test", email="test@example.com")
        game = Game.objects.create(name="Test", rank=1, igdb_id=1)

        # Create 1 connected and 2 orphaned PlayedGame records
        PlayedGame.objects.create(user=user, game=game, igdb_id=1)
        PlayedGame.objects.create(user=user, game=None, igdb_id=2)  # orphaned
        PlayedGame.objects.create(user=user, game=None, igdb_id=3)  # orphaned

        distribution = get_played_games_distribution()
        self.assertEqual(len(distribution), 1)
        self.assertEqual(distribution[0][1], 1)  # Only 1 non-orphaned game

    def test_excludes_users_with_zero_games(self):
        """Users with no played games are excluded from distribution."""
        User.objects.create_user(username="inactive", email="no@example.com")

        active_user = User.objects.create_user(
            username="active", email="yes@example.com"
        )
        game = Game.objects.create(name="Test", rank=1, igdb_id=1)
        PlayedGame.objects.create(user=active_user, game=game, igdb_id=1)

        distribution = get_played_games_distribution()
        self.assertEqual(len(distribution), 1)

    def test_distribution_is_cached(self):
        """Distribution result is cached."""
        user = User.objects.create_user(username="test", email="test@example.com")
        game = Game.objects.create(name="Test", rank=1, igdb_id=1)
        PlayedGame.objects.create(user=user, game=game, igdb_id=1)

        # First call
        dist1 = get_played_games_distribution()

        # Add another user (won't be in cache)
        user2 = User.objects.create_user(username="test2", email="test2@example.com")
        PlayedGame.objects.create(user=user2, game=game, igdb_id=1)

        # Second call should return cached result
        dist2 = get_played_games_distribution()
        self.assertEqual(len(dist1), len(dist2))

        # After cache clear, should see new user
        cache.clear()
        dist3 = get_played_games_distribution()
        self.assertEqual(len(dist3), 2)

    def test_empty_distribution_returns_none(self):
        """Empty distribution returns None percentile."""
        # No users have played any games
        result = calculate_percentile(5)
        self.assertIsNone(result["percentile"])
        self.assertEqual(result["total_users"], 0)
