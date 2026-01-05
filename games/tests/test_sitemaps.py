"""
Tests for sitemap configuration.

These tests directly test the sitemap classes to ensure coverage
of their methods beyond the integration tests in test_main_views.py.
"""

from django.test import TestCase
from django.urls import reverse

from games.models import Developer, Game
from games.sitemaps import DeveloperSitemap, GameSitemap, StaticViewSitemap, sitemaps


class StaticViewSitemapTests(TestCase):
    """Tests for the StaticViewSitemap class."""

    def setUp(self):
        self.sitemap = StaticViewSitemap()

    def test_items_returns_expected_pages(self):
        """Test that items() returns the correct static page names."""
        items = self.sitemap.items()
        self.assertEqual(
            items,
            ["home", "developers-list", "list-list", "books:home", "books:author-list"],
        )

    def test_location_returns_valid_urls(self):
        """Test that location() returns valid URLs for each item."""
        for item in self.sitemap.items():
            location = self.sitemap.location(item)
            self.assertTrue(location.startswith("/"))
            self.assertEqual(location, reverse(item))

    def test_priority_is_set(self):
        """Test that priority is correctly set."""
        self.assertEqual(self.sitemap.priority, 0.5)

    def test_changefreq_is_set(self):
        """Test that changefreq is correctly set."""
        self.assertEqual(self.sitemap.changefreq, "weekly")


class GameSitemapTests(TestCase):
    """Tests for the GameSitemap class."""

    def setUp(self):
        self.sitemap = GameSitemap()
        self.game1 = Game.objects.create(
            name="Test Game 1",
            slug="test-game-1",
            rank=1,
        )
        self.game2 = Game.objects.create(
            name="Test Game 2",
            slug="test-game-2",
            rank=2,
        )

    def test_items_returns_all_games(self):
        """Test that items() returns all games."""
        items = list(self.sitemap.items())
        self.assertEqual(len(items), 2)
        self.assertIn(self.game1, items)
        self.assertIn(self.game2, items)

    def test_location_returns_game_detail_url(self):
        """Test that location() returns the correct game detail URL."""
        location = self.sitemap.location(self.game1)
        expected = reverse("game-detail", kwargs={"slug": self.game1.slug})
        self.assertEqual(location, expected)

    def test_lastmod_returns_updated_at_when_present(self):
        """Test that lastmod() returns updated_at when the object has it."""
        from django.utils import timezone

        # Create a mock object with updated_at
        class MockGameWithUpdatedAt:
            updated_at = timezone.now()

        mock_game = MockGameWithUpdatedAt()
        lastmod = self.sitemap.lastmod(mock_game)
        self.assertEqual(lastmod, mock_game.updated_at)

    def test_lastmod_returns_none_when_no_updated_at(self):
        """Test that lastmod() returns None when object has no updated_at."""
        # Game model doesn't have updated_at, so it returns None
        lastmod = self.sitemap.lastmod(self.game1)
        self.assertIsNone(lastmod)

    def test_priority_is_set(self):
        """Test that priority is correctly set."""
        self.assertEqual(self.sitemap.priority, 0.8)

    def test_changefreq_is_set(self):
        """Test that changefreq is correctly set."""
        self.assertEqual(self.sitemap.changefreq, "monthly")


class DeveloperSitemapTests(TestCase):
    """Tests for the DeveloperSitemap class."""

    def setUp(self):
        self.sitemap = DeveloperSitemap()
        self.dev1 = Developer.objects.create(name="Test Dev 1", slug="test-dev-1")
        self.dev2 = Developer.objects.create(name="Test Dev 2", slug="test-dev-2")

    def test_items_returns_developers_with_slugs(self):
        """Test that items() returns only developers with slugs."""
        items = list(self.sitemap.items())
        self.assertEqual(len(items), 2)
        self.assertIn(self.dev1, items)
        self.assertIn(self.dev2, items)

    def test_items_excludes_developers_without_slugs(self):
        """Test that items() excludes subsidiary developers without slugs."""
        # Create a subsidiary developer without a slug
        subsidiary = Developer.objects.create(
            name="Subsidiary Dev", slug="", parent=self.dev1
        )
        items = list(self.sitemap.items())
        self.assertEqual(len(items), 2)
        self.assertNotIn(subsidiary, items)

    def test_location_returns_developer_detail_url(self):
        """Test that location() returns the correct developer detail URL."""
        location = self.sitemap.location(self.dev1)
        expected = reverse("developer-detail", kwargs={"slug": self.dev1.slug})
        self.assertEqual(location, expected)

    def test_priority_is_set(self):
        """Test that priority is correctly set."""
        self.assertEqual(self.sitemap.priority, 0.6)

    def test_changefreq_is_set(self):
        """Test that changefreq is correctly set."""
        self.assertEqual(self.sitemap.changefreq, "monthly")


class SitemapsConfigurationTests(TestCase):
    """Tests for the sitemaps dictionary configuration."""

    def test_sitemaps_dict_has_expected_keys(self):
        """Test that the sitemaps dict has all expected keys."""
        self.assertIn("static", sitemaps)
        self.assertIn("games", sitemaps)
        self.assertIn("developers", sitemaps)

    def test_sitemaps_dict_has_correct_classes(self):
        """Test that the sitemaps dict maps to correct classes."""
        self.assertEqual(sitemaps["static"], StaticViewSitemap)
        self.assertEqual(sitemaps["games"], GameSitemap)
        self.assertEqual(sitemaps["developers"], DeveloperSitemap)
