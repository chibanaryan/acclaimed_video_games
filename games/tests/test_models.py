from unittest import mock

from django.test import TestCase

from .. import constants, models, utils
from django.db import IntegrityError


class RankingUtilsTests(TestCase):

    def setUp(self):
        utils.year_rankings.clear()
        utils.decade_rankings.clear()
        models.Game.objects.all().delete()

    def tearDown(self):
        utils.year_rankings.clear()
        utils.decade_rankings.clear()

    def test_get_ranking_for_year(self):
        g1 = models.Game.objects.create(
            name="Year One", rank=1, igdb_id=1, year_of_release=1990
        )
        g2 = models.Game.objects.create(
            name="Year Two", rank=2, igdb_id=2, year_of_release=1990
        )

        utils.year_rankings.clear()
        utils.decade_rankings.clear()
        self.assertEqual(utils.get_ranking_for_year(g1), 1)
        self.assertEqual(utils.get_ranking_for_year(g2), 2)

    def test_get_ranking_for_year_missing_data(self):
        game = models.Game.objects.create(
            name="Missing Year", rank=1, igdb_id=3, year_of_release=1979
        )

        utils.year_rankings.clear()
        models.Game.objects.filter(id=game.id).delete()
        with self.assertRaisesMessage(
            ValueError, "No rankings available for year 1979"
        ):
            utils.get_ranking_for_year(game)

    def test_get_ranking_for_year_missing_game(self):
        models.Game.objects.create(
            name="Ranked", rank=1, igdb_id=5, year_of_release=1985
        )
        utils.year_rankings.clear()
        utils.get_ranking_for_year(models.Game.objects.get(igdb_id=5))
        ghost_game = models.Game(id=999, name="Ghost", rank=99, year_of_release=1985)

        with self.assertRaisesMessage(ValueError, "Game"):
            utils.get_ranking_for_year(ghost_game)

    def test_get_ranking_for_decade(self):
        g1 = models.Game.objects.create(
            name="Decade One", rank=5, igdb_id=3, year_of_release=1995
        )
        g2 = models.Game.objects.create(
            name="Decade Two", rank=2, igdb_id=4, year_of_release=1992
        )

        utils.year_rankings.clear()
        utils.decade_rankings.clear()
        self.assertEqual(utils.get_ranking_for_decade(g2), 1)
        self.assertEqual(utils.get_ranking_for_decade(g1), 2)

    def test_get_ranking_for_decade_missing_data(self):
        game = models.Game.objects.create(
            name="Missing Decade", rank=1, igdb_id=8, year_of_release=1975
        )

        utils.decade_rankings.clear()
        models.Game.objects.filter(id=game.id).delete()
        with self.assertRaisesMessage(
            ValueError, "No rankings available for decade 1970"
        ):
            utils.get_ranking_for_decade(game)

    def test_get_ranking_for_decade_missing_game(self):
        models.Game.objects.create(
            name="Ranked", rank=1, igdb_id=9, year_of_release=1980
        )
        utils.decade_rankings.clear()
        utils.get_ranking_for_decade(models.Game.objects.get(igdb_id=9))
        ghost_game = models.Game(id=1000, name="Ghost", rank=99, year_of_release=1981)

        with self.assertRaisesMessage(ValueError, "Game"):
            utils.get_ranking_for_decade(ghost_game)


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

        with mock.patch("games.models.api", fake_api):
            game.get_igdb_data()

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

        with mock.patch("games.models.api", None):
            with self.assertLogs("games.models", level="WARNING") as cm:
                game.get_igdb_data()

        self.assertIn("IGDB API unavailable", cm.output[0])

    def test_get_igdb_data_requires_igdb_id(self):
        game = models.Game.objects.create(name="Sample", rank=1, igdb_id=None)
        with mock.patch("games.models.api") as api_mock:
            game.get_igdb_data()
        api_mock.get_game_info_by_id.assert_not_called()

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
        with mock.patch("games.models.api", fake_api), mock.patch.object(
            models.DeveloperAlias.objects,
            "update_or_create",
            side_effect=IntegrityError,
        ), mock.patch.object(models.DeveloperAlias.objects, "get", return_value=alias):
            game.get_igdb_data()
        self.assertIn(alias, game.developers.all())


class ModelHelpersTests(TestCase):

    def test_snippet_str_and_slugify(self):
        snippet = models.Snippet.objects.create(slug="My Snippet", text="Content")
        self.assertEqual(str(snippet), "my-snippet")

    def test_platform_str(self):
        platform = models.Platform.objects.create(code="PC", name="Personal Computer")
        self.assertEqual(str(platform), "Personal Computer")

    def test_developer_str_and_other_aliases(self):
        developer = models.Developer.objects.create(name="Studio")
        alias = models.DeveloperAlias.objects.create(developer=developer, name="Studio")
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

    @mock.patch("games.utils.get_ranking_for_decade", return_value=5)
    @mock.patch("games.utils.get_ranking_for_year", return_value=3)
    def test_game_save_normalizes_name(self, year_mock, decade_mock):
        game = models.Game.objects.create(
            name="Álpha", rank=1, igdb_id=10, year_of_release=2000
        )
        self.assertEqual(game.name_normalized, "Alpha")
        self.assertEqual(game.year_rank, 3)
        self.assertEqual(game.decade_rank, 5)

    @mock.patch("games.models.logger.error")
    @mock.patch("games.utils.get_ranking_for_decade", side_effect=ValueError("bad"))
    @mock.patch("games.utils.get_ranking_for_year", side_effect=ValueError("bad"))
    def test_game_save_logs_errors_when_ranking_fails(
        self, year_mock, decade_mock, logger_mock
    ):
        game = models.Game.objects.create(
            name="Sample", rank=1, igdb_id=1, year_of_release=2000
        )
        logger_mock.assert_called()

    def test_game_thumbnail_and_image(self):
        game = models.Game.objects.create(
            name="Art Game",
            rank=1,
            igdb_id=20,
            year_of_release=2001,
            igdb_artwork_id="art123",
        )
        self.assertIn("t_cover_small/art123", game.thumbnail)
        self.assertIn("t_cover_big/art123", game.image)

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
