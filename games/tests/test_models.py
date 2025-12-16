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
            "studios": [
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
        # Check IGDB data is in IGDBGameData record
        game.refresh_from_db()
        self.assertIsNotNone(game.primary_igdb_game_data)
        self.assertEqual(game.primary_igdb_game_data.url, "https://example.com/sample")
        self.assertEqual(game.primary_igdb_game_data.artwork_id, "cover_hash")
        self.assertIn("Story", game.description)
        self.assertEqual(game.genres.get().name, "Action")
        self.assertEqual(game.studios.get().name, "Foo Dev")

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
        alias = models.Studio.objects.create(
            company=models.Company.objects.create(name="Existing Dev"),
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
            "studios": [
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
            models.Studio.objects,
            "update_or_create",
            side_effect=IntegrityError,
        ), mock.patch.object(
            models.Studio.objects, "get", return_value=alias
        ):
            game.get_igdb_data()
        self.assertIn(alias, game.studios.all())

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
            "studios": [
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
        developer = models.Company.objects.get(name="Indie Studio")
        self.assertEqual(developer.igdb_id, 123)

        # Verify matching DeveloperAlias was created
        alias = models.Studio.objects.get(name="Indie Studio")
        self.assertEqual(alias.company, developer)
        self.assertEqual(alias.igdb_id, 123)

        # Verify game is linked to the alias
        self.assertIn(alias, game.studios.all())

        # Verify no orphaned developers
        orphaned_devs = models.Company.objects.filter(studios__isnull=True)
        self.assertEqual(orphaned_devs.count(), 0)

    def test_get_igdb_data_preserves_slug_when_igdb_returns_empty(self):
        """Test that existing slugs are preserved when IGDB returns None/empty slug."""
        # Create game with an existing slug
        game = models.Game.objects.create(
            name="The Legend of Zelda",
            slug="the-legend-of-zelda",
            rank=1,
            igdb_id=999,
            year_of_release=1986,
        )

        # Mock IGDB API returning None for slug
        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = {
            "slug": None,  # IGDB returns None
            "url": "https://example.com/zelda",
            "cover": "cover_hash",
            "storyline": "Story",
            "summary": "Summary",
            "genres": [],
            "studios": [],
        }

        game.get_igdb_data(api_client=fake_api)

        # Verify slug is preserved
        self.assertEqual(game.slug, "the-legend-of-zelda")

    def test_get_igdb_data_generates_slug_when_none_exists(self):
        """Test that slug is generated from name when game has no slug."""
        # Create game without a slug
        game = models.Game.objects.create(
            name="Super Mario Bros",
            rank=1,
            igdb_id=999,
            year_of_release=1985,
        )

        # Mock IGDB API returning None for slug
        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = {
            "slug": None,
            "url": "https://example.com/mario",
            "cover": "cover_hash",
            "storyline": "",
            "summary": "",
            "genres": [],
            "studios": [],
        }

        game.get_igdb_data(api_client=fake_api)

        # Verify slug was generated from name
        self.assertEqual(game.slug, "super-mario-bros")

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
            "studios": [
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

        # Verify parent Company was created
        parent_dev = models.Company.objects.get(name="Nintendo")
        self.assertEqual(parent_dev.igdb_id, 789)

        # Verify child Studio exists and is linked to parent Company
        child_alias = models.Studio.objects.get(name="Nintendo EPD")
        self.assertEqual(child_alias.company, parent_dev)
        self.assertEqual(child_alias.igdb_id, 456)

        # Verify game is linked to the child Studio
        self.assertIn(child_alias, game.studios.all())

        # Parent companies can exist without Studios (not orphaned)
        parent_studios = models.Studio.objects.filter(
            company=parent_dev, name="Nintendo"
        )
        self.assertEqual(parent_studios.count(), 0)  # No auto-created parent Studio

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
            "studios": [
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

            initial_dev_count = models.Company.objects.count()
            initial_alias_count = models.Studio.objects.count()

            # Import again
            game.get_igdb_data()
            game.save()

            # Should not create duplicates
            self.assertEqual(models.Company.objects.count(), initial_dev_count)
            self.assertEqual(models.Studio.objects.count(), initial_alias_count)

            # Verify no orphaned developers
            orphaned_devs = models.Company.objects.filter(studios__isnull=True)
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
                    "studios": [
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
                    "studios": [
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

        # Verify only ONE parent Company was created (shared)
        parent_devs = models.Company.objects.filter(
            name="Sony Interactive Entertainment"
        )
        self.assertEqual(parent_devs.count(), 1)
        parent_dev = parent_devs.first()

        # Verify both child Studios are linked to the same parent Company
        studio_a_alias = models.Studio.objects.get(name="Sony Studio A")
        studio_b_alias = models.Studio.objects.get(name="Sony Studio B")
        self.assertEqual(studio_a_alias.company, parent_dev)
        self.assertEqual(studio_b_alias.company, parent_dev)

        # Parent company exists without its own Studio (expected behavior)
        parent_studios = models.Studio.objects.filter(
            company=parent_dev, name="Sony Interactive Entertainment"
        )
        self.assertEqual(parent_studios.count(), 0)  # No auto-created parent Studio

    def test_update_igdb_relationships_success(self):
        """Test update_igdb_relationships updates M2M relationships."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=123, year_of_release=2020
        )

        # Create existing IGDBGameData
        models.IGDBGameData.objects.create(
            game=game,
            igdb_id=123,
            artwork_id="cover_hash",
            url="https://example.com/test",
            description="Test description",
            is_primary=True,
        )

        # Mock API response
        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = {
            "genres": ["Action", "Adventure"],
            "studios": [
                {
                    "id": 1,
                    "name": "Test Studio",
                    "slug": "test-studio",
                }
            ],
        }

        # Update relationships
        result = game.update_igdb_relationships(api_client=fake_api)

        # Verify success
        self.assertTrue(result)

        # Verify relationships were created
        self.assertEqual(game.genres.count(), 2)
        self.assertIn("Action", [g.name for g in game.genres.all()])
        self.assertIn("Adventure", [g.name for g in game.genres.all()])
        self.assertEqual(game.studios.count(), 1)
        self.assertEqual(game.studios.first().name, "Test Studio")

        # Verify IGDBGameData was NOT modified
        igdb_data = models.IGDBGameData.objects.get(game=game)
        self.assertEqual(igdb_data.artwork_id, "cover_hash")
        self.assertEqual(igdb_data.description, "Test description")

    def test_update_igdb_relationships_no_igdb_id(self):
        """Test update_igdb_relationships returns False without igdb_id."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, year_of_release=2020
        )
        result = game.update_igdb_relationships()
        self.assertFalse(result)

    def test_update_igdb_relationships_api_unavailable(self):
        """Test update_igdb_relationships handles missing API."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=123, year_of_release=2020
        )
        with mock.patch("games.models.igdb.get_api", return_value=None):
            with self.assertLogs("games.models", level="WARNING"):
                result = game.update_igdb_relationships()
        self.assertFalse(result)

    def test_update_igdb_relationships_no_game_data(self):
        """Test update_igdb_relationships handles API returning None."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=123, year_of_release=2020
        )
        fake_api = mock.Mock()
        fake_api.get_game_info_by_id.return_value = None
        result = game.update_igdb_relationships(api_client=fake_api)
        self.assertFalse(result)


class GameWikipediaTests(TestCase):
    """Tests for Game.get_wikipedia_data() method."""

    @mock.patch("games.services.wiki_genre_service.WikiGenreService")
    def test_get_wikipedia_data_populates_fields(self, mock_service_class):
        """Test get_wikipedia_data() populates WikipediaGameData fields."""
        from games.services.wiki_genre_service import GenreResult, GenreSource

        game = models.Game.objects.create(
            name="Test Game", rank=1, year_of_release=2020
        )

        # Mock WikiGenreService.get_genre() to return successful result
        mock_service = mock_service_class.return_value
        mock_result = GenreResult(
            game_name="Test Game",
            source=GenreSource.WIKIPEDIA,
            primary_genre="Action",
            all_genres=["Action", "Adventure"],
            source_url="https://en.wikipedia.org/wiki/Test_Game",
        )
        mock_service.get_genre.return_value = mock_result

        # Call get_wikipedia_data
        game.get_wikipedia_data(page_titles="Test Game")

        # Verify WikipediaGameData was created/updated
        wiki_data = models.WikipediaGameData.objects.get(game=game, is_primary=True)
        self.assertEqual(wiki_data.page_title, "Test Game")
        self.assertEqual(wiki_data.primary_genre, "Action")
        self.assertEqual(wiki_data.all_genres, "Action, Adventure")
        self.assertEqual(
            wiki_data.lookup_source, "https://en.wikipedia.org/wiki/Test_Game"
        )
        self.assertTrue(wiki_data.is_primary)

    @mock.patch("games.services.wiki_genre_service.WikiGenreService")
    def test_get_wikipedia_data_comma_separated_titles(self, mock_service_class):
        """Test get_wikipedia_data() with comma-separated page titles."""
        from games.services.wiki_genre_service import GenreResult, GenreSource

        game = models.Game.objects.create(
            name="Pokémon Red", rank=1, year_of_release=1996
        )

        # Mock WikiGenreService to return different results for each title
        mock_service = mock_service_class.return_value
        mock_service.get_genre.side_effect = [
            GenreResult(
                game_name="Pokémon Red and Blue",
                source=GenreSource.WIKIPEDIA,
                primary_genre="RPG",
                all_genres=["RPG"],
                source_url="https://en.wikipedia.org/wiki/Pokemon_Red_and_Blue",
            ),
            GenreResult(
                game_name="Pokémon Red",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Role-playing",
                all_genres=["Role-playing"],
                source_url="https://en.wikipedia.org/wiki/Pokemon_Red",
            ),
        ]

        # Call with comma-separated titles
        game.get_wikipedia_data(page_titles="Pokémon Red and Blue,Pokémon Red")

        # Verify 2 records created from API call
        wiki_records = models.WikipediaGameData.objects.filter(game=game)
        self.assertEqual(wiki_records.count(), 2)

        # First API record should be primary
        primary = models.WikipediaGameData.objects.get(game=game, is_primary=True)
        self.assertEqual(primary.page_title, "Pokémon Red and Blue")
        self.assertEqual(primary.primary_genre, "RPG")

        # Second API record should not be primary
        secondary = models.WikipediaGameData.objects.get(
            game=game, page_title="Pokémon Red"
        )
        self.assertFalse(secondary.is_primary)


class ModelHelpersTests(TestCase):

    def test_snippet_str_and_slugify(self):
        snippet = models.Snippet.objects.create(slug="My Snippet", text="Content")
        self.assertEqual(str(snippet), "my-snippet")

    def test_platform_str(self):
        platform = models.Platform.objects.create(code="PC", name="Personal Computer")
        self.assertEqual(str(platform), "Personal Computer")

    def test_developer_str_and_other_aliases(self):
        developer = models.Company.objects.create(name="Studio")
        models.Studio.objects.create(company=developer, name="Studio")
        other = models.Studio.objects.create(company=developer, name="Alt Studio")
        self.assertEqual(str(developer), "Studio")
        self.assertEqual(list(developer.subsidiary_studios), [other])

    def test_developer_alias_str_variants(self):
        developer = models.Company.objects.create(name="Studio")
        alias_same = models.Studio.objects.create(company=developer, name="Studio")
        alias_other = models.Studio.objects.create(company=developer, name="Studio Alt")
        self.assertEqual(str(alias_same), "Studio")
        self.assertEqual(str(alias_other), "Studio Alt (Studio)")

    def test_genre_str(self):
        genre = models.IGDBGenre.objects.create(name="Action")
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
        )
        # Create IGDB data with artwork
        igdb_data, _ = models.IGDBGameData.objects.update_or_create(
            game=game,
            igdb_id=20,
            defaults={
                "artwork_id": "art123",
                "url": "https://example.com",
                "is_primary": True,
            },
        )
        game.primary_igdb_game_data = igdb_data
        game.save()
        self.assertIn("t_cover_small/art123", game.thumbnail)
        self.assertIn("t_cover_small_2x/art123", game.thumbnail_2x)
        self.assertIn("t_cover_big/art123", game.image)
        self.assertIn("t_cover_big_2x/art123", game.image_2x)
        self.assertIn("t_cover_small_2x/art123", game.homepage_thumb)
        self.assertIn("t_cover_big/art123", game.homepage_thumb_2x)

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


class IGDBGameDataTests(TestCase):
    """Tests for IGDBGameData model."""

    def setUp(self):
        """Create a test game with IGDB data."""
        self.game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=123,
            year_of_release=2020,
        )
        # Manually create IGDBGameData record
        self.igdb_data = models.IGDBGameData.objects.create(
            game=self.game,
            igdb_id=123,
            artwork_id="test_artwork_id",
            url="https://www.igdb.com/games/test-game",
            description="Test description",
            is_primary=True,
        )
        self.game.primary_igdb_game_data = self.igdb_data
        self.game.save(update_fields=["primary_igdb_game_data"])

    def test_str(self):
        """Test __str__ returns correct format."""
        self.assertEqual(str(self.igdb_data), "IGDB data for Test Game (ID: 123)")

    def test_thumbnail(self):
        """Test thumbnail property returns correct URL."""
        expected = (
            "https://images.igdb.com/igdb/image/upload/t_cover_small/test_artwork_id"
        )
        self.assertEqual(self.igdb_data.thumbnail, expected)

    def test_thumbnail_2x(self):
        """Test thumbnail_2x property returns correct URL."""
        expected = (
            "https://images.igdb.com/igdb/image/upload/t_cover_small_2x/test_artwork_id"
        )
        self.assertEqual(self.igdb_data.thumbnail_2x, expected)

    def test_image(self):
        """Test image property returns correct URL."""
        expected = (
            "https://images.igdb.com/igdb/image/upload/t_cover_big/test_artwork_id"
        )
        self.assertEqual(self.igdb_data.image, expected)

    def test_image_2x(self):
        """Test image_2x property returns correct URL."""
        expected = (
            "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/test_artwork_id"
        )
        self.assertEqual(self.igdb_data.image_2x, expected)

    def test_homepage_thumb_small(self):
        """Test homepage_thumb_small property returns correct URL."""
        expected = (
            "https://images.igdb.com/igdb/image/upload/t_cover_small/test_artwork_id"
        )
        self.assertEqual(self.igdb_data.homepage_thumb_small, expected)

    def test_homepage_thumb(self):
        """Test homepage_thumb property returns correct URL."""
        expected = (
            "https://images.igdb.com/igdb/image/upload/t_cover_small_2x/test_artwork_id"
        )
        self.assertEqual(self.igdb_data.homepage_thumb, expected)

    def test_homepage_thumb_2x(self):
        """Test homepage_thumb_2x property returns correct URL."""
        expected = (
            "https://images.igdb.com/igdb/image/upload/t_cover_big/test_artwork_id"
        )
        self.assertEqual(self.igdb_data.homepage_thumb_2x, expected)

    def test_thumbnail_square(self):
        """Test thumbnail_square property returns correct URL."""
        expected = "https://images.igdb.com/igdb/image/upload/t_thumb/test_artwork_id"
        self.assertEqual(self.igdb_data.thumbnail_square, expected)

    def test_image_properties_without_artwork_id(self):
        """Test image properties return None when no artwork_id."""
        self.igdb_data.artwork_id = ""
        self.igdb_data.save()
        self.igdb_data.refresh_from_db()
        # Clear cached_property cache
        for attr in [
            "thumbnail",
            "thumbnail_2x",
            "image",
            "image_2x",
            "homepage_thumb_small",
            "homepage_thumb",
            "homepage_thumb_2x",
            "thumbnail_square",
        ]:
            if attr in self.igdb_data.__dict__:
                del self.igdb_data.__dict__[attr]

        self.assertIsNone(self.igdb_data.thumbnail)
        self.assertIsNone(self.igdb_data.thumbnail_2x)
        self.assertIsNone(self.igdb_data.image)
        self.assertIsNone(self.igdb_data.image_2x)
        self.assertIsNone(self.igdb_data.homepage_thumb_small)
        self.assertIsNone(self.igdb_data.homepage_thumb)
        self.assertIsNone(self.igdb_data.homepage_thumb_2x)
        self.assertIsNone(self.igdb_data.thumbnail_square)


class WikipediaGameDataTests(TestCase):
    """Tests for WikipediaGameData model."""

    def setUp(self):
        """Create a test game with Wikipedia data."""
        self.game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
        )
        # Create WikipediaGameData manually
        self.wiki_data = models.WikipediaGameData.objects.create(
            game=self.game,
            page_title="Test_Game_(video_game)",
            wikidata_id="Q12345",
            primary_genre="Action",
            all_genres="Action, Adventure",
            is_primary=True,
        )
        self.game.primary_wikipedia_game_data = self.wiki_data
        self.game.save()

    def test_str(self):
        """Test __str__ returns correct format."""
        self.assertEqual(str(self.wiki_data), "Wikipedia data for Test Game")

    def test_wikipedia_url(self):
        """Test wikipedia_url property returns correct URL."""
        expected = "https://en.wikipedia.org/wiki/Test_Game_(video_game)"
        self.assertEqual(self.wiki_data.wikipedia_url, expected)

    def test_wikipedia_url_with_spaces(self):
        """Test wikipedia_url property handles spaces correctly."""
        self.wiki_data.page_title = "Test Game"
        expected = "https://en.wikipedia.org/wiki/Test_Game"
        self.assertEqual(self.wiki_data.wikipedia_url, expected)

    def test_wikipedia_url_without_page_title(self):
        """Test wikipedia_url property returns None when no page title."""
        self.wiki_data.page_title = ""
        self.assertIsNone(self.wiki_data.wikipedia_url)
