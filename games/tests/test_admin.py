from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory, TestCase

from core.models import User
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

    def test_wikipedia_genres_with_genres(self):
        """Test _wikipedia_genres displays comma-separated genre names."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        genre1 = models.WikipediaGenre.objects.create(
            name="Test Action", slug="test-action-admin"
        )
        genre2 = models.WikipediaGenre.objects.create(
            name="Test RPG", slug="test-rpg-admin"
        )
        game.wikipedia_genres.add(genre1, genre2)

        value = self.admin._wikipedia_genres(game)
        self.assertIn("Test Action", value)
        self.assertIn("Test RPG", value)

    def test_wikipedia_genres_without_genres(self):
        """Test _wikipedia_genres returns '-' when no genres."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        value = self.admin._wikipedia_genres(game)
        self.assertEqual(value, "-")

    def test_hltb_data_link_with_data(self):
        """Test _hltb_data_link displays admin link to HLTB data."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        hltb_data = models.HLTBGameData.objects.create(
            game=game,
            igdb_id=123,
            hltb_id="12345",
            main_story_hours=10.5,
            is_primary=True,
        )
        game.primary_hltb_game_data = hltb_data
        game.save(update_fields=["primary_hltb_game_data"])

        value = self.admin._hltb_data_link(game)
        self.assertIn(f"/admin/games/hltbgamedata/{hltb_data.id}/change/", value)
        self.assertIn("View HLTB Data", value)
        self.assertIn("<a href=", value)

    def test_hltb_data_link_without_data(self):
        """Test _hltb_data_link returns '-' when no HLTB data."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        value = self.admin._hltb_data_link(game)
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

    def test_all_genres_preview_with_genres(self):
        """Test _all_genres_preview displays all genres."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        wiki_data = models.WikipediaGameData.objects.create(
            game=game,
            all_genres="Action, Adventure, RPG",
            is_primary=True,
        )

        value = self.admin._all_genres_preview(wiki_data)
        self.assertEqual(value, "Action, Adventure, RPG")

    def test_all_genres_preview_without_genres(self):
        """Test _all_genres_preview returns '-' when no genres."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        wiki_data = models.WikipediaGameData.objects.create(
            game=game,
            all_genres="",
            is_primary=True,
        )

        value = self.admin._all_genres_preview(wiki_data)
        self.assertEqual(value, "-")


class HLTBGameDataAdminTests(TestCase):
    """Tests for HLTBGameData admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.HLTBGameDataAdmin(models.HLTBGameData, self.site)

    def test_hltb_link_with_url(self):
        """Test _hltb_link displays clickable HLTB URL."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        hltb_data = models.HLTBGameData.objects.create(
            game=game,
            igdb_id=123,
            hltb_id="12345",
            main_story_hours=10.5,
            is_primary=True,
        )

        value = self.admin._hltb_link(hltb_data)
        self.assertIn("howlongtobeat.com", value)
        self.assertIn("<a href=", value)
        self.assertIn("View on HLTB", value)

    def test_hltb_link_without_url(self):
        """Test _hltb_link returns '-' when no hltb_id (no URL)."""
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        hltb_data = models.HLTBGameData.objects.create(
            game=game,
            igdb_id=123,
            hltb_id="",
            is_primary=True,
        )

        value = self.admin._hltb_link(hltb_data)
        self.assertEqual(value, "-")


class WikipediaGenreAdminTests(TestCase):
    """Tests for WikipediaGenre admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.WikipediaGenreAdmin(models.WikipediaGenre, self.site)

    def test_game_count_returns_count(self):
        """Test game_count returns the number of games with this genre."""
        genre = models.WikipediaGenre.objects.create(
            name="Test Admin Genre", slug="test-admin-genre"
        )
        game1 = models.Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        game2 = models.Game.objects.create(name="Game 2", rank=2, year_of_release=2021)
        game1.wikipedia_genres.add(genre)
        game2.wikipedia_genres.add(genre)

        count = self.admin.game_count(genre)
        self.assertEqual(count, 2)


class SeriesAdminTests(TestCase):
    """Tests for Series admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.SeriesAdmin(models.Series, self.site)

    def test_get_queryset_annotates_game_count(self):
        """Test get_queryset annotates _game_count."""
        series = models.Series.objects.create(
            name="Test Series Admin", slug="test-series-admin", igdb_id=99991
        )
        game = models.Game.objects.create(
            name="Test Series Game", rank=1, year_of_release=2020
        )
        game.series.add(series)

        qs = self.admin.get_queryset(request=None)
        series_from_qs = qs.get(pk=series.pk)
        self.assertEqual(series_from_qs._game_count, 1)

    def test_game_count_uses_annotation(self):
        """Test game_count uses the _game_count annotation."""
        series = models.Series.objects.create(
            name="Test Series Admin 2", slug="test-series-admin-2", igdb_id=99992
        )
        game1 = models.Game.objects.create(
            name="Test Series Game 1", rank=1, year_of_release=2020
        )
        game2 = models.Game.objects.create(
            name="Test Series Game 2", rank=2, year_of_release=2021
        )
        game1.series.add(series)
        game2.series.add(series)

        qs = self.admin.get_queryset(request=None)
        series_from_qs = qs.get(pk=series.pk)
        count = self.admin.game_count(series_from_qs)
        self.assertEqual(count, 2)


class DeveloperAdminTests(TestCase):
    """Tests for Developer admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.DeveloperAdmin(models.Developer, self.site)

    def test_get_queryset_annotates_game_count(self):
        """Test get_queryset annotates _game_count and selects parent."""
        parent = models.Developer.objects.create(
            name="Nintendo", slug="nintendo", igdb_id=1
        )
        dev = models.Developer.objects.create(
            name="Nintendo EAD", slug="nintendo-ead", igdb_id=2, parent=parent
        )
        game = models.Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        game.developers.add(dev)

        qs = self.admin.get_queryset(request=None)
        dev_from_qs = qs.get(pk=dev.pk)
        self.assertEqual(dev_from_qs._game_count, 1)
        self.assertEqual(dev_from_qs.parent.name, "Nintendo")

    def test_game_count_uses_annotation(self):
        """Test game_count uses the _game_count annotation."""
        dev = models.Developer.objects.create(name="Valve", slug="valve", igdb_id=3)
        game1 = models.Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        game2 = models.Game.objects.create(name="Game 2", rank=2, year_of_release=2021)
        game1.developers.add(dev)
        game2.developers.add(dev)

        qs = self.admin.get_queryset(request=None)
        dev_from_qs = qs.get(pk=dev.pk)
        count = self.admin.game_count(dev_from_qs)
        self.assertEqual(count, 2)


class PlayedGameAdminTests(TestCase):
    """Tests for PlayedGame admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.PlayedGameAdmin(models.PlayedGame, self.site)
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_game_name_with_game(self):
        """Test game_name returns game name when game is connected."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=123, year_of_release=2020
        )
        played = models.PlayedGame.objects.create(
            user=self.user, game=game, igdb_id=123
        )

        value = self.admin.game_name(played)
        self.assertEqual(value, "Test Game")

    def test_game_name_orphaned(self):
        """Test game_name returns orphaned message when game is None."""
        played = models.PlayedGame.objects.create(
            user=self.user, game=None, igdb_id=456
        )

        value = self.admin.game_name(played)
        self.assertEqual(value, "(orphaned) IGDB:456")

    def test_game_status_connected(self):
        """Test game_status returns 'Connected' when game exists."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=123, year_of_release=2020
        )
        played = models.PlayedGame.objects.create(
            user=self.user, game=game, igdb_id=123
        )

        value = self.admin.game_status(played)
        self.assertEqual(value, "Connected")

    def test_game_status_orphaned(self):
        """Test game_status returns 'Orphaned' when game is None."""
        played = models.PlayedGame.objects.create(
            user=self.user, game=None, igdb_id=789
        )

        value = self.admin.game_status(played)
        self.assertEqual(value, "Orphaned")


class WantToPlayGameAdminTests(TestCase):
    """Tests for WantToPlayGame admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.WantToPlayGameAdmin(models.WantToPlayGame, self.site)
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_game_name_with_game(self):
        """Test game_name returns game name when game is connected."""
        game = models.Game.objects.create(
            name="Want Game", rank=1, igdb_id=123, year_of_release=2020
        )
        want = models.WantToPlayGame.objects.create(
            user=self.user, game=game, igdb_id=123
        )

        value = self.admin.game_name(want)
        self.assertEqual(value, "Want Game")

    def test_game_name_orphaned(self):
        """Test game_name returns orphaned message when game is None."""
        want = models.WantToPlayGame.objects.create(
            user=self.user, game=None, igdb_id=456
        )

        value = self.admin.game_name(want)
        self.assertEqual(value, "(orphaned) IGDB:456")

    def test_game_status_connected(self):
        """Test game_status returns 'Connected' when game exists."""
        game = models.Game.objects.create(
            name="Want Game", rank=1, igdb_id=123, year_of_release=2020
        )
        want = models.WantToPlayGame.objects.create(
            user=self.user, game=game, igdb_id=123
        )

        value = self.admin.game_status(want)
        self.assertEqual(value, "Connected")

    def test_game_status_orphaned(self):
        """Test game_status returns 'Orphaned' when game is None."""
        want = models.WantToPlayGame.objects.create(
            user=self.user, game=None, igdb_id=789
        )

        value = self.admin.game_status(want)
        self.assertEqual(value, "Orphaned")


class SavedFilterSetAdminTests(TestCase):
    """Tests for SavedFilterSet admin interface."""

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.SavedFilterSetAdmin(models.SavedFilterSet, self.site)
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_filter_summary_empty_filters(self):
        """Test filter_summary returns '(no filters)' for empty filters."""
        saved = models.SavedFilterSet.objects.create(
            user=self.user, name="Empty Filter", filters={}
        )

        value = self.admin.filter_summary(saved)
        self.assertEqual(value, "(no filters)")

    def test_filter_summary_with_search(self):
        """Test filter_summary includes search query."""
        saved = models.SavedFilterSet.objects.create(
            user=self.user, name="Search Filter", filters={"q": "zelda games test"}
        )

        value = self.admin.filter_summary(saved)
        self.assertIn("search:", value)
        self.assertIn("zelda games test", value)

    def test_filter_summary_truncates_long_search(self):
        """Test filter_summary truncates long search queries."""
        long_query = "this is a very long search query that should be truncated"
        saved = models.SavedFilterSet.objects.create(
            user=self.user, name="Long Search", filters={"q": long_query}
        )

        value = self.admin.filter_summary(saved)
        self.assertIn("search:", value)
        self.assertNotIn(long_query, value)

    def test_filter_summary_with_genres(self):
        """Test filter_summary includes genre count."""
        saved = models.SavedFilterSet.objects.create(
            user=self.user, name="Genre Filter", filters={"genres": [1, 2, 3]}
        )

        value = self.admin.filter_summary(saved)
        self.assertIn("3 genres", value)

    def test_filter_summary_with_platforms(self):
        """Test filter_summary includes platform count."""
        saved = models.SavedFilterSet.objects.create(
            user=self.user, name="Platform Filter", filters={"platforms": [1, 2]}
        )

        value = self.admin.filter_summary(saved)
        self.assertIn("2 platforms", value)

    def test_filter_summary_with_series(self):
        """Test filter_summary includes series count."""
        saved = models.SavedFilterSet.objects.create(
            user=self.user, name="Series Filter", filters={"series": [1]}
        )

        value = self.admin.filter_summary(saved)
        self.assertIn("1 series", value)

    def test_filter_summary_with_year_range(self):
        """Test filter_summary includes year range."""
        saved = models.SavedFilterSet.objects.create(
            user=self.user, name="Year Filter", filters={"start": 1990, "end": 1999}
        )

        value = self.admin.filter_summary(saved)
        self.assertIn("1990-1999", value)

    def test_filter_summary_with_partial_year_range(self):
        """Test filter_summary handles partial year range."""
        saved = models.SavedFilterSet.objects.create(
            user=self.user, name="Start Only", filters={"start": 2000}
        )

        value = self.admin.filter_summary(saved)
        self.assertIn("2000-?", value)

    def test_filter_summary_multiple_filters(self):
        """Test filter_summary combines multiple filters."""
        saved = models.SavedFilterSet.objects.create(
            user=self.user,
            name="Complex Filter",
            filters={
                "q": "mario",
                "genres": [1, 2],
                "platforms": [3],
                "start": 1990,
                "end": 2020,
            },
        )

        value = self.admin.filter_summary(saved)
        self.assertIn("search:", value)
        self.assertIn("2 genres", value)
        self.assertIn("1 platforms", value)
        self.assertIn("1990-2020", value)


class AdditionalAdminCoverageTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/")
        self.user = User.objects.create_user(
            username="admin-extra",
            email="admin-extra@example.com",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.request.user = self.user

    def test_game_admin_get_queryset_prefetches_primary_data(self):
        game_admin = admin.GameAdmin(models.Game, self.site)
        game = models.Game.objects.create(
            name="Admin Coverage Game", rank=1, igdb_id=54321, year_of_release=2020
        )
        qs = game_admin.get_queryset(self.request)
        obj = qs.get(pk=game.pk)
        self.assertEqual(obj.id, game.id)

    def test_list_membership_inline_get_queryset(self):
        inline = admin.ListMembershipInline(models.List, self.site)
        publication = models.Publication.objects.create(name="Inline Pub")
        lst = models.List.objects.create(
            name="Inline List", publisher=publication, year=2024, type="A"
        )
        game = models.Game.objects.create(
            name="Inline Game", rank=2, year_of_release=2021
        )
        models.ListMembership.objects.create(list=lst, game=game, rank=1)
        qs = inline.get_queryset(self.request)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().game.name, "Inline Game")

    def test_list_admin_membership_count_fallback_and_queryset(self):
        list_admin = admin.ListAdmin(models.List, self.site)
        publication = models.Publication.objects.create(name="List Pub")
        lst = models.List.objects.create(
            name="List Admin List", publisher=publication, year=2023, type="E"
        )
        qs = list_admin.get_queryset(self.request)
        self.assertIsNotNone(qs.get(pk=lst.pk))
        self.assertEqual(list_admin.membership_count(lst), 0)

    def test_list_membership_admin_methods_handle_missing_relations(self):
        membership_admin = admin.ListMembershipAdmin(models.ListMembership, self.site)
        mock_obj = mock.Mock()
        mock_obj.game = None
        mock_obj.list = None
        self.assertEqual(membership_admin.game_name(mock_obj), "-")
        self.assertEqual(membership_admin.list_name(mock_obj), "-")
        self.assertEqual(membership_admin.publisher_name(mock_obj), "-")
        self.assertEqual(membership_admin.list_type(mock_obj), "-")
        qs = membership_admin.get_queryset(self.request)
        self.assertIsNotNone(qs)

    def test_inline_has_add_permission_methods(self):
        email_inline = admin.EmailAddressInline(User, self.site)
        self.assertFalse(email_inline.has_add_permission(self.request))

    def test_user_change_page_has_no_tracking_formsets(self):
        # Regression: tracked games used to render one editable inline form per
        # row, exceeding DATA_UPLOAD_MAX_NUMBER_FIELDS and causing a 400 on save
        # for users with many games. They are now read-only summaries instead.
        game = models.Game.objects.create(
            name="Trackee Game", rank=11, igdb_id=5151, year_of_release=2016
        )
        target = User.objects.create_user(
            username="trackee", email="trackee@example.com", password="pw"
        )
        models.PlayedGame.objects.create(user=target, game=game, igdb_id=5151)
        models.WantToPlayGame.objects.create(user=target, game=game, igdb_id=5151)

        client = Client()
        client.force_login(self.user)
        response = client.get(f"/admin/core/user/{target.pk}/change/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("played_games-TOTAL_FORMS", content)
        self.assertNotIn("want_to_play_games-TOTAL_FORMS", content)
        self.assertIn("Trackee Game", content)

    def test_user_admin_tracking_summaries_empty(self):
        user_admin = admin.UserAdmin(User, self.site)
        self.assertEqual(user_admin.played_games_list(self.user), "None")
        self.assertEqual(user_admin.want_to_play_list(self.user), "None")

    def test_user_admin_tracking_summaries_list_games(self):
        user_admin = admin.UserAdmin(User, self.site)
        game = models.Game.objects.create(
            name="Tracked Game", rank=7, igdb_id=4242, year_of_release=2019
        )
        models.PlayedGame.objects.create(user=self.user, game=game, igdb_id=4242)
        models.WantToPlayGame.objects.create(user=self.user, game=game, igdb_id=4242)
        played = user_admin.played_games_list(self.user)
        want = user_admin.want_to_play_list(self.user)
        self.assertIn("Tracked Game", played)
        self.assertIn("1</strong> total", played)
        self.assertIn("Tracked Game", want)

    def test_user_admin_tracking_summary_falls_back_to_igdb_id(self):
        user_admin = admin.UserAdmin(User, self.site)
        # A tracking row whose game was removed falls back to the igdb id.
        models.PlayedGame.objects.create(user=self.user, game=None, igdb_id=222)
        summary = user_admin.played_games_list(self.user)
        self.assertIn("(igdb 222)", summary)

    def test_user_admin_tracking_summary_caps_long_lists(self):
        user_admin = admin.UserAdmin(User, self.site)
        user_admin._TRACKING_LIST_CAP = 1
        g1 = models.Game.objects.create(name="Cap Game 1", rank=8, year_of_release=2018)
        g2 = models.Game.objects.create(name="Cap Game 2", rank=9, year_of_release=2017)
        models.PlayedGame.objects.create(user=self.user, game=g1, igdb_id=111)
        models.PlayedGame.objects.create(user=self.user, game=g2, igdb_id=222)
        summary = user_admin.played_games_list(self.user)
        self.assertIn("2</strong> total", summary)
        self.assertIn("+1 more", summary)

    def test_user_admin_queryset_and_display_fields(self):
        game = models.Game.objects.create(
            name="User Admin Game", rank=3, igdb_id=98765, year_of_release=2022
        )
        models.PlayedGame.objects.create(user=self.user, game=game, igdb_id=98765)
        models.WantToPlayGame.objects.create(user=self.user, game=game, igdb_id=98766)
        user_admin = admin.UserAdmin(User, self.site)
        qs = user_admin.get_queryset(self.request)
        annotated_user = qs.get(pk=self.user.pk)
        self.assertIsNotNone(annotated_user._played_games_count)
        self.assertIsNotNone(annotated_user._want_to_play_count)
        self.assertEqual(
            user_admin.email_verified_display(annotated_user),
            annotated_user.email_verified,
        )
        self.assertEqual(
            user_admin.played_games_count(annotated_user),
            annotated_user._played_games_count,
        )
        self.assertEqual(
            user_admin.want_to_play_count(annotated_user),
            annotated_user._want_to_play_count,
        )
