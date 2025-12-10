from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from games import admin, models


class GameAdminTests(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.GameAdmin(models.Game, self.site)

    def test_save_model_fetches_fresh_igdb_data(self):
        game = mock.Mock(spec=models.Game)
        self.admin.save_model(request=None, obj=game, form=None, change=False)
        game.get_igdb_data.assert_called_once_with(cache_results=False)
        game.save.assert_called_once()

    def test_genres_helper_returns_joined_names(self):
        genre = models.Genre.objects.create(name="Action")
        game = models.Game.objects.create(
            name="Sample",
            rank=1,
            igdb_id=1,
            year_of_release=1990,
        )
        game.genres.add(genre)
        value = self.admin._genres(game)
        self.assertEqual(value, "Action")

    def test_igdb_data_link_with_data(self):
        """Test _igdb_data_link displays admin link to IGDB data."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        # Create IGDBGameData
        igdb_data = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=123,
            artwork_id="test_art_id",
            is_primary=True,
        )
        game.primary_igdb_game_data = igdb_data
        game.save(update_fields=["primary_igdb_game_data"])

        value = self.admin._igdb_data_link(game)
        self.assertIn(f"/admin/games/igdbgamedata/{igdb_data.id}/change/", value)
        self.assertIn("View IGDB Data", value)
        self.assertIn("<a href=", value)

    def test_igdb_data_link_without_data(self):
        """Test _igdb_data_link returns '-' when no IGDB data."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        value = self.admin._igdb_data_link(game)
        self.assertEqual(value, "-")

    def test_wikipedia_data_link_with_data(self):
        """Test _wikipedia_data_link displays admin link to Wikipedia data."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        # Create WikipediaGameData
        wiki_data = models.WikipediaGameData.objects.create(
            game=game,
            page_title="Test_Game_(video_game)",
            is_primary=True,
        )
        game.primary_wikipedia_game_data = wiki_data
        game.save(update_fields=["primary_wikipedia_game_data"])

        value = self.admin._wikipedia_data_link(game)
        self.assertIn(f"/admin/games/wikipediagamedata/{wiki_data.id}/change/", value)
        self.assertIn("View Wikipedia Data", value)
        self.assertIn("<a href=", value)

    def test_wikipedia_data_link_without_data(self):
        """Test _wikipedia_data_link returns '-' when no Wikipedia data."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        value = self.admin._wikipedia_data_link(game)
        self.assertEqual(value, "-")


class SiteMetadataAdminTests(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.SiteMetadataAdmin(models.SiteMetadata, self.site)

    def test_has_add_permission_allows_when_none_exists(self):
        # Should allow adding when no SiteMetadata exists
        result = self.admin.has_add_permission(request=None)
        self.assertTrue(result)

    def test_has_add_permission_blocks_when_exists(self):
        # Create a SiteMetadata instance
        models.SiteMetadata.get_instance()
        # Should block adding when SiteMetadata already exists
        result = self.admin.has_add_permission(request=None)
        self.assertFalse(result)

    def test_has_delete_permission_always_false(self):
        # Should never allow deletion
        result = self.admin.has_delete_permission(request=None)
        self.assertFalse(result)
        # Even with an object specified
        metadata = models.SiteMetadata.get_instance()
        result = self.admin.has_delete_permission(request=None, obj=metadata)
        self.assertFalse(result)


class IGDBGameDataAdminTests(TestCase):
    """Tests for IGDBGameData admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.IGDBGameDataAdmin(models.IGDBGameData, self.site)

    def test_url_link_with_url(self):
        """Test _url_link displays clickable IGDB URL."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        igdb_data = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=123,
            url="https://www.igdb.com/games/test-game",
            is_primary=True,
        )
        game.primary_igdb_game_data = igdb_data
        game.save(update_fields=["primary_igdb_game_data"])

        value = self.admin._url_link(igdb_data)
        self.assertIn("https://www.igdb.com/games/test-game", value)
        self.assertIn("<a href=", value)

    def test_url_link_without_url(self):
        """Test _url_link returns '-' when no URL."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        igdb_data = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=123,
            url="",
            is_primary=True,
        )
        game.primary_igdb_game_data = igdb_data
        game.save(update_fields=["primary_igdb_game_data"])

        value = self.admin._url_link(igdb_data)
        self.assertEqual(value, "-")

    def test_description_preview_with_description(self):
        """Test _description_preview displays truncated description."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        long_description = "This is a very long description " * 10
        igdb_data = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=123,
            description=long_description,
            is_primary=True,
        )

        value = self.admin._description_preview(igdb_data)
        # Should be truncated to 10 words
        self.assertIn("This is a very", value)
        self.assertLess(len(value), len(long_description))

    def test_description_preview_without_description(self):
        """Test _description_preview returns '-' when no description."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        igdb_data = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=123,
            description="",
            is_primary=True,
        )

        value = self.admin._description_preview(igdb_data)
        self.assertEqual(value, "-")


class WikipediaGameDataAdminTests(TestCase):
    """Tests for WikipediaGameData admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.WikipediaGameDataAdmin(models.WikipediaGameData, self.site)

    def test_wikipedia_link_with_page_title(self):
        """Test _wikipedia_link displays clickable Wikipedia URL."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        wiki_data = models.WikipediaGameData.objects.create(
            game=game,
            page_title="Test_Game_(video_game)",
            is_primary=True,
        )

        value = self.admin._wikipedia_link(wiki_data)
        self.assertIn("Test_Game_(video_game)", value)
        self.assertIn("<a href=", value)

    def test_wikipedia_link_without_page_title(self):
        """Test _wikipedia_link returns '-' when no page title."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        wiki_data = models.WikipediaGameData.objects.create(
            game=game,
            page_title="",
            is_primary=True,
        )

        value = self.admin._wikipedia_link(wiki_data)
        self.assertEqual(value, "-")
