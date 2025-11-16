from unittest import mock

from django.test import TestCase

from .. import models, utils


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
