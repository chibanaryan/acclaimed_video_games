"""
Tests for Game of the Day service.
"""

from datetime import datetime

from django.core.cache import cache
from django.test import TestCase

from games.models import Developer, DeveloperAlias, Game, GameQuote
from games.services import game_of_the_day


class GameOfTheDayServiceTest(TestCase):
    """Test Game of the Day selection and caching."""

    def setUp(self):
        """Create test games with varying completeness."""
        cache.clear()

        # Create developer (required for complete games)
        dev = Developer.objects.create(name="Test Developer", slug="test-dev")
        dev_alias = DeveloperAlias.objects.create(developer=dev, name="Test Developer")

        # Complete game (has everything)
        self.complete_game = Game.objects.create(
            name="Complete Game",
            slug="complete-game",
            rank=1,
            igdb_artwork_id="test1",
            year_of_release=2023,
            description="A complete game with all required fields.",
        )
        self.complete_game.developers.add(dev_alias)
        GameQuote.objects.create(
            game=self.complete_game,
            text="An amazing game!",
            attribution="IGN",
            is_featured=True,
        )

        # Complete game (no quote - quotes are optional)
        self.no_quote_game = Game.objects.create(
            name="No Quote Game",
            slug="no-quote",
            rank=2,
            igdb_artwork_id="test2",
            year_of_release=2022,
            description="A complete game without a quote.",
        )
        self.no_quote_game.developers.add(dev_alias)

        # Incomplete game (missing description)
        self.no_desc_game = Game.objects.create(
            name="No Desc Game",
            slug="no-desc",
            rank=3,
            igdb_artwork_id="test3",
            year_of_release=2021,
        )
        self.no_desc_game.developers.add(dev_alias)
        GameQuote.objects.create(
            game=self.no_desc_game, text="A quote", is_featured=True
        )

        # Incomplete game (missing developer)
        self.no_dev_game = Game.objects.create(
            name="No Dev Game",
            slug="no-dev",
            rank=4,
            igdb_artwork_id="test4",
            year_of_release=2020,
            description="Missing developer.",
        )
        GameQuote.objects.create(
            game=self.no_dev_game, text="A quote", is_featured=True
        )

        # Incomplete game (missing IGDB artwork)
        self.no_image_game = Game.objects.create(
            name="No Image Game",
            slug="no-image",
            rank=5,
            year_of_release=2019,
            description="Missing image.",
        )
        self.no_image_game.developers.add(dev_alias)
        GameQuote.objects.create(
            game=self.no_image_game, text="A quote", is_featured=True
        )

    def test_only_selects_complete_games(self):
        """Test that only complete games are selected."""
        # Run selection multiple times
        for _ in range(20):
            game = game_of_the_day.get_game_of_the_day()
            cache.clear()

            # Should only select one of the complete games (not incomplete ones)
            self.assertIn(game.id, [self.complete_game.id, self.no_quote_game.id])

    def test_get_game_of_the_day_returns_complete_game(self):
        """Test that a complete game is returned."""
        game = game_of_the_day.get_game_of_the_day()

        self.assertIsNotNone(game)
        self.assertIn(game.id, [self.complete_game.id, self.no_quote_game.id])

        # Verify it has all required fields
        self.assertIsNotNone(game.igdb_artwork_id)
        self.assertIsNotNone(game.description)
        self.assertTrue(len(game.description) > 0)
        self.assertIsNotNone(game.year_of_release)
        self.assertTrue(game.developers.exists())
        # Quotes are optional now

    def test_game_selection_cached_daily(self):
        """Test that game selection is cached for the day."""
        game1 = game_of_the_day.get_game_of_the_day()
        game2 = game_of_the_day.get_game_of_the_day()

        # Should return same game (cached)
        self.assertEqual(game1.id, game2.id)

    def test_cache_key_includes_date(self):
        """Test that cache key includes current date."""
        today = datetime.utcnow().date()
        expected_key = f"game_of_the_day_{today.isoformat()}"

        # Get game (populates cache)
        game_of_the_day.get_game_of_the_day()

        # Check cache key exists
        cached_id = cache.get(expected_key)
        self.assertIsNotNone(cached_id)

    def test_returns_none_when_no_complete_games(self):
        """Test that None is returned when no complete games exist."""
        # Delete all complete games
        self.complete_game.delete()
        self.no_quote_game.delete()

        game = game_of_the_day.get_game_of_the_day()
        self.assertIsNone(game)

    def test_weighted_selection_with_multiple_complete_games(self):
        """Test weighted random selection with multiple eligible games."""
        # Create another complete game with higher rank
        dev_alias = DeveloperAlias.objects.first()

        game2 = Game.objects.create(
            name="Complete Game 2",
            slug="complete-2",
            rank=100,
            igdb_artwork_id="test100",
            year_of_release=2023,
            description="Another complete game.",
        )
        game2.developers.add(dev_alias)

        # Run many selections (200 trials to ensure all games get selected)
        selections = []
        for _ in range(200):
            cache.clear()
            game = game_of_the_day._select_weighted_random_game()
            selections.append(game.rank)

        # All three complete games should be selected at some point
        self.assertIn(1, selections)  # complete_game
        self.assertIn(2, selections)  # no_quote_game
        self.assertIn(100, selections)  # game2

        # Rank 1 should be selected more often than rank 100
        rank1_count = selections.count(1)
        rank100_count = selections.count(100)
        self.assertGreater(rank1_count, rank100_count)

    def test_cache_invalidation_on_deletion(self):
        """Test that cache handles deleted games gracefully."""
        # Get a game (caches it)
        game = game_of_the_day.get_game_of_the_day()
        game_id = game.id

        # Delete the game
        game.delete()

        # Should return a different game (we have 2 complete games)
        new_game = game_of_the_day.get_game_of_the_day()
        self.assertIsNotNone(new_game)
        self.assertNotEqual(new_game.id, game_id)

    def test_get_featured_quote_returns_featured(self):
        """Test that featured quotes are prioritized."""
        # Add a non-featured quote
        GameQuote.objects.create(
            game=self.complete_game, text="Not featured", is_featured=False
        )

        quote = game_of_the_day.get_featured_quote(self.complete_game)

        self.assertIsNotNone(quote)
        self.assertTrue(quote.is_featured)
        self.assertEqual(quote.text, "An amazing game!")

    def test_get_featured_quote_falls_back(self):
        """Test fallback to any quote when no featured quotes."""
        # Remove featured flag
        featured_quote = self.complete_game.quotes.first()
        featured_quote.is_featured = False
        featured_quote.save()

        quote = game_of_the_day.get_featured_quote(self.complete_game)

        self.assertIsNotNone(quote)
        self.assertEqual(quote.game_id, self.complete_game.id)

    def test_returns_none_for_game_with_empty_description(self):
        """Test that games with empty descriptions are excluded."""
        # Create game with empty description
        dev_alias = DeveloperAlias.objects.first()
        empty_desc_game = Game.objects.create(
            name="Empty Desc Game",
            slug="empty-desc",
            rank=6,
            igdb_artwork_id="test6",
            year_of_release=2022,
            description="",  # Empty string
        )
        empty_desc_game.developers.add(dev_alias)
        GameQuote.objects.create(game=empty_desc_game, text="Quote", is_featured=True)

        # Should only select complete games (not the empty desc one)
        for _ in range(10):
            game = game_of_the_day.get_game_of_the_day()
            cache.clear()
            # Should be one of the two complete games, not the empty desc game
            self.assertIn(game.id, [self.complete_game.id, self.no_quote_game.id])
            self.assertNotEqual(game.id, empty_desc_game.id)
