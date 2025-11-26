from unittest import mock

from django.test import TestCase

from .. import constants, models, utils
from django.db import IntegrityError


class RankingUtilsTests(TestCase):
    """Tests for year and decade ranking calculation."""

    def test_update_year_decade_ranks_calculates_correctly(self):
        """Test that update_year_decade_ranks() correctly calculates rankings."""
        # Create games in different years and with different ranks
        g1 = models.Game.objects.create(
            name="Year 1990 Rank 1", rank=1, igdb_id=1, year_of_release=1990
        )
        g2 = models.Game.objects.create(
            name="Year 1990 Rank 2", rank=2, igdb_id=2, year_of_release=1990
        )
        g3 = models.Game.objects.create(
            name="Year 1995 Rank 3", rank=3, igdb_id=3, year_of_release=1995
        )
        g4 = models.Game.objects.create(
            name="Year 1992 Rank 5", rank=5, igdb_id=4, year_of_release=1992
        )

        # Run the bulk ranking update
        games_updated, years_processed = utils.update_year_decade_ranks()

        # Verify correct number of updates
        self.assertEqual(games_updated, 4)
        self.assertEqual(years_processed, 3)  # 1990, 1992, 1995

        # Refresh games from DB
        g1.refresh_from_db()
        g2.refresh_from_db()
        g3.refresh_from_db()
        g4.refresh_from_db()

        # Check year ranks (within each year, ordered by rank)
        self.assertEqual(g1.year_rank, 1)  # First in 1990
        self.assertEqual(g2.year_rank, 2)  # Second in 1990
        self.assertEqual(g3.year_rank, 1)  # Only game in 1995
        self.assertEqual(g4.year_rank, 1)  # Only game in 1992

        # Check decade ranks (1990s decade, ordered by global rank)
        self.assertEqual(g1.decade_rank, 1)  # Rank 1 overall
        self.assertEqual(g2.decade_rank, 2)  # Rank 2 overall
        self.assertEqual(g3.decade_rank, 3)  # Rank 3 overall (3rd in decade)
        self.assertEqual(g4.decade_rank, 4)  # Rank 5 overall (4th in decade)

    def test_update_year_decade_ranks_empty_database(self):
        """Test that update_year_decade_ranks() handles empty database."""
        games_updated, years_processed = utils.update_year_decade_ranks()
        self.assertEqual(games_updated, 0)
        self.assertEqual(years_processed, 0)


class GameIgdbTests(TestCase):

    def test_get_igdb_data_populates_fields(self):
        game = models.Game.objects.create(
            name="Sample", rank=1, igdb_id=999, year_of_release=1990
        )

        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = {
            "slug": "sample-game",
            "url": "https://example.com/sample",
            "cover": "cover_hash",
            "storyline": "Story",
            "summary": "Summary",
            "genres": ["Action"],
            "developers": [
                {
                    "id": 1,
                    "name": "Foo Dev",
                    "slug": "foo-dev",
                    "parent": {
                        "id": 2,
                        "name": "Foo Parent",
                        "slug": "foo-parent",
                    },
                }
            ],
        }

        game.get_igdb_data(api_client=fake_api)

        self.assertEqual(game.slug, "sample-game")
        self.assertEqual(game.igdb_url, "https://example.com/sample")
        self.assertEqual(game.igdb_artwork_id, "cover_hash")
        self.assertIn("Story", game.description)
        self.assertEqual(game.genres.get().name, "Action")
        self.assertEqual(game.developers.get().name, "Foo Dev")

    def test_get_igdb_data_handles_missing_api(self):
        game = models.Game.objects.create(
            name="Sample", rank=1, igdb_id=999, year_of_release=1990
        )

        with mock.patch("games.models.igdb.get_api", return_value=None):
            with self.assertLogs("games.models", level="WARNING") as cm:
                game.get_igdb_data()

        self.assertIn("IGDB API unavailable", cm.output[0])

    def test_get_igdb_data_requires_igdb_id(self):
        game = models.Game.objects.create(name="Sample", rank=1, igdb_id=None)
        with mock.patch("games.models.igdb.get_api") as get_api_mock:
            game.get_igdb_data()
        get_api_mock.assert_not_called()

    def test_get_igdb_data_handles_alias_integrity_error(self):
        game = models.Game.objects.create(
            name="Sample", rank=1, igdb_id=555, year_of_release=1990
        )
        alias = models.DeveloperAlias.objects.create(
            developer=models.Developer.objects.create(name="Existing Dev"),
            name="Existing Alias",
        )
        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = {
            "slug": "sample-game",
            "url": "https://example.com/sample",
            "cover": "cover_hash",
            "storyline": "",
            "summary": "",
            "genres": [],
            "developers": [
                {
                    "id": 1,
                    "name": "Existing Alias",
                    "slug": "existing-alias",
                    "parent": None,
                }
            ],
        }
        with mock.patch(
            "games.models.igdb.get_api", return_value=fake_api
        ), mock.patch.object(
            models.DeveloperAlias.objects,
            "update_or_create",
            side_effect=IntegrityError,
        ), mock.patch.object(
            models.DeveloperAlias.objects, "get", return_value=alias
        ):
            game.get_igdb_data()
        self.assertIn(alias, game.developers.all())

    def test_get_igdb_data_creates_alias_for_standalone_developer(self):
        """Test that standalone developers (no parent) get a matching DeveloperAlias"""
        game = models.Game.objects.create(
            name="Indie Game", rank=1, igdb_id=100, year_of_release=2020
        )

        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = {
            "slug": "indie-game",
            "url": "https://example.com/indie",
            "cover": "cover_hash",
            "storyline": "",
            "summary": "",
            "genres": [],
            "developers": [
                {
                    "id": 123,
                    "name": "Indie Studio",
                    "slug": "indie-studio",
                    "parent": None,
                }
            ],
        }

        with mock.patch("games.models.igdb.get_api", return_value=fake_api):
            game.get_igdb_data()
            game.save()

        # Verify Developer was created
        developer = models.Developer.objects.get(name="Indie Studio")
        self.assertEqual(developer.igdb_id, 123)

        # Verify matching DeveloperAlias was created
        alias = models.DeveloperAlias.objects.get(name="Indie Studio")
        self.assertEqual(alias.developer, developer)
        self.assertEqual(alias.igdb_id, 123)

        # Verify game is linked to the alias
        self.assertIn(alias, game.developers.all())

        # Verify no orphaned developers
        orphaned_devs = models.Developer.objects.filter(aliases__isnull=True)
        self.assertEqual(orphaned_devs.count(), 0)

    def test_get_igdb_data_creates_alias_for_parent_company(self):
        """Test that parent companies get their own DeveloperAlias (prevents orphans)"""
        game = models.Game.objects.create(
            name="Nintendo Game", rank=1, igdb_id=200, year_of_release=2017
        )

        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = {
            "slug": "nintendo-game",
            "url": "https://example.com/nintendo",
            "cover": "cover_hash",
            "storyline": "",
            "summary": "",
            "genres": [],
            "developers": [
                {
                    "id": 456,
                    "name": "Nintendo EPD",
                    "slug": "nintendo-epd",
                    "parent": {
                        "id": 789,
                        "name": "Nintendo",
                        "slug": "nintendo",
                    },
                }
            ],
        }

        with mock.patch("games.models.igdb.get_api", return_value=fake_api):
            game.get_igdb_data()
            game.save()

        # Verify parent Developer was created
        parent_dev = models.Developer.objects.get(name="Nintendo")
        self.assertEqual(parent_dev.igdb_id, 789)

        # Verify parent has its own DeveloperAlias (this prevents orphans!)
        parent_alias = models.DeveloperAlias.objects.get(
            developer=parent_dev, name="Nintendo"
        )
        self.assertEqual(parent_alias.igdb_id, 789)

        # Verify child alias exists and is linked to parent Developer
        child_alias = models.DeveloperAlias.objects.get(name="Nintendo EPD")
        self.assertEqual(child_alias.developer, parent_dev)
        self.assertEqual(child_alias.igdb_id, 456)

        # Verify game is linked to the child alias
        self.assertIn(child_alias, game.developers.all())

        # Verify no orphaned developers
        orphaned_devs = models.Developer.objects.filter(aliases__isnull=True)
        self.assertEqual(orphaned_devs.count(), 0)

    def test_get_igdb_data_multiple_imports_idempotent(self):
        """Test that importing the same game multiple times doesn't create duplicates"""
        game = models.Game.objects.create(
            name="Re-import Test", rank=1, igdb_id=300, year_of_release=2019
        )

        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = {
            "slug": "reimport-test",
            "url": "https://example.com/reimport",
            "cover": "cover_hash",
            "storyline": "",
            "summary": "",
            "genres": [],
            "developers": [
                {
                    "id": 111,
                    "name": "Studio One",
                    "slug": "studio-one",
                    "parent": None,
                }
            ],
        }

        with mock.patch("games.models.igdb.get_api", return_value=fake_api):
            # Import once
            game.get_igdb_data()
            game.save()

            initial_dev_count = models.Developer.objects.count()
            initial_alias_count = models.DeveloperAlias.objects.count()

            # Import again
            game.get_igdb_data()
            game.save()

            # Should not create duplicates
            self.assertEqual(models.Developer.objects.count(), initial_dev_count)
            self.assertEqual(models.DeveloperAlias.objects.count(), initial_alias_count)

            # Verify no orphaned developers
            orphaned_devs = models.Developer.objects.filter(aliases__isnull=True)
            self.assertEqual(orphaned_devs.count(), 0)

    def test_get_igdb_data_multiple_games_same_parent(self):
        """Test multiple games from subsidiaries of same parent"""
        game1 = models.Game.objects.create(
            name="Game One", rank=1, igdb_id=401, year_of_release=2018
        )
        game2 = models.Game.objects.create(
            name="Game Two", rank=2, igdb_id=402, year_of_release=2019
        )

        fake_api = mock.Mock()

        def fake_get_game_info(game_id, cache_results=True):
            if game_id == 401:
                return {
                    "slug": "game-one",
                    "url": "https://example.com/one",
                    "cover": "cover1",
                    "storyline": "",
                    "summary": "",
                    "genres": [],
                    "developers": [
                        {
                            "id": 501,
                            "name": "Sony Studio A",
                            "slug": "sony-studio-a",
                            "parent": {
                                "id": 600,
                                "name": "Sony Interactive Entertainment",
                                "slug": "sony-ie",
                            },
                        }
                    ],
                }
            else:
                return {
                    "slug": "game-two",
                    "url": "https://example.com/two",
                    "cover": "cover2",
                    "storyline": "",
                    "summary": "",
                    "genres": [],
                    "developers": [
                        {
                            "id": 502,
                            "name": "Sony Studio B",
                            "slug": "sony-studio-b",
                            "parent": {
                                "id": 600,
                                "name": "Sony Interactive Entertainment",
                                "slug": "sony-ie",
                            },
                        }
                    ],
                }

        fake_api.get_game_info_by_id.side_effect = fake_get_game_info

        with mock.patch("games.models.igdb.get_api", return_value=fake_api):
            game1.get_igdb_data()
            game1.save()
            game2.get_igdb_data()
            game2.save()

        # Verify only ONE parent Developer was created (shared)
        parent_devs = models.Developer.objects.filter(
            name="Sony Interactive Entertainment"
        )
        self.assertEqual(parent_devs.count(), 1)
        parent_dev = parent_devs.first()

        # Verify parent has its own alias
        parent_alias = models.DeveloperAlias.objects.get(
            developer=parent_dev, name="Sony Interactive Entertainment"
        )
        self.assertEqual(parent_alias.igdb_id, 600)

        # Verify both child studios have aliases linked to the same parent
        studio_a_alias = models.DeveloperAlias.objects.get(name="Sony Studio A")
        studio_b_alias = models.DeveloperAlias.objects.get(name="Sony Studio B")
        self.assertEqual(studio_a_alias.developer, parent_dev)
        self.assertEqual(studio_b_alias.developer, parent_dev)

        # Verify no orphaned developers
        orphaned_devs = models.Developer.objects.filter(aliases__isnull=True)
        self.assertEqual(orphaned_devs.count(), 0)


class ModelHelpersTests(TestCase):

    def test_snippet_str_and_slugify(self):
        snippet = models.Snippet.objects.create(slug="My Snippet", text="Content")
        self.assertEqual(str(snippet), "my-snippet")

    def test_platform_str(self):
        platform = models.Platform.objects.create(code="PC", name="Personal Computer")
        self.assertEqual(str(platform), "Personal Computer")

    def test_developer_str_and_other_aliases(self):
        developer = models.Developer.objects.create(name="Studio")
        models.DeveloperAlias.objects.create(developer=developer, name="Studio")
        other = models.DeveloperAlias.objects.create(
            developer=developer, name="Alt Studio"
        )
        self.assertEqual(str(developer), "Studio")
        self.assertEqual(list(developer.other_aliases), [other])

    def test_developer_alias_str_variants(self):
        developer = models.Developer.objects.create(name="Studio")
        alias_same = models.DeveloperAlias.objects.create(
            developer=developer, name="Studio"
        )
        alias_other = models.DeveloperAlias.objects.create(
            developer=developer, name="Studio Alt"
        )
        self.assertEqual(str(alias_same), "Studio")
        self.assertEqual(str(alias_other), "Studio Alt (Studio)")

    def test_genre_str(self):
        genre = models.Genre.objects.create(name="Action")
        self.assertEqual(str(genre), "Action")

    def test_game_save_normalizes_name(self):
        """Test that Game.save() normalizes non-ASCII characters in name."""
        game = models.Game.objects.create(
            name="Álpha", rank=1, igdb_id=10, year_of_release=2000
        )
        self.assertEqual(game.name_normalized, "Alpha")

    def test_game_thumbnail_and_image(self):
        game = models.Game.objects.create(
            name="Art Game",
            rank=1,
            igdb_id=20,
            year_of_release=2001,
            igdb_artwork_id="art123",
        )
        self.assertIn("t_cover_small/art123", game.thumbnail)
        self.assertIn("t_cover_small_2x/art123", game.thumbnail_2x)
        self.assertIn("t_cover_big/art123", game.image)
        self.assertIn("t_cover_big_2x/art123", game.image_2x)

    def test_publication_str_and_slug_default(self):
        publication = models.Publication.objects.create(name="GameSpot")
        self.assertEqual(str(publication), "GameSpot")
        self.assertEqual(publication.slug, "gamespot")

    def test_list_str(self):
        pub = models.Publication.objects.create(name="IGN")
        lst = models.List.objects.create(
            publisher=pub,
            name="Top 10",
            year=2020,
            type=constants.LIST_EOY,
            order=1,
        )
        self.assertEqual(str(lst), "Top 10")

    def test_list_membership_str(self):
        pub = models.Publication.objects.create(name="IGN")
        lst = models.List.objects.create(
            publisher=pub,
            name="Top 10",
            year=2020,
            type=constants.LIST_EOY,
            order=1,
        )
        game = models.Game.objects.create(
            name="Alpha", rank=1, igdb_id=5, year_of_release=2000
        )
        membership = models.ListMembership.objects.create(list=lst, game=game, rank=1)
        self.assertEqual(str(membership), "Top 10 - Alpha - 1")

    def test_post_str_and_rendered_text(self):
        post = models.Post.objects.create(title="", text="**Hello**", active=True)
        self.assertIn("Hello", str(post))
        self.assertIn("<strong>Hello</strong>", post.text_rendered)

    def test_post_with_author(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="testauthor", first_name="John", last_name="Doe"
        )
        post = models.Post.objects.create(
            title="Authored Post", text="Content", active=True, author=user
        )
        self.assertEqual(post.author, user)
        self.assertEqual(post.author.get_full_name(), "John Doe")

    def test_post_without_author(self):
        post = models.Post.objects.create(
            title="No Author", text="Content", active=True
        )
        self.assertIsNone(post.author)

    def test_game_decade_property(self):
        # Test decade property with year_of_release
        game = models.Game.objects.create(
            name="Test", rank=1, igdb_id=100, year_of_release=1995
        )
        self.assertEqual(game.decade, 1990)

        # Test with different decade
        game2 = models.Game.objects.create(
            name="Test2", rank=2, igdb_id=101, year_of_release=2005
        )
        self.assertEqual(game2.decade, 2000)

        # Test decade property without year_of_release
        game3 = models.Game.objects.create(
            name="Test3", rank=3, igdb_id=102, year_of_release=None
        )
        self.assertIsNone(game3.decade)

    def test_site_metadata_str(self):
        """Test SiteMetadata.__str__ returns correct format."""
        metadata = models.SiteMetadata.get_instance()
        self.assertEqual(str(metadata), "Site Metadata (default)")
