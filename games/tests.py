from io import StringIO
from unittest import mock

from django.test import TestCase

from . import models, utils


class ImportGamesTests(TestCase):

    def test_import_games_creates_and_updates(self):
        data = "1\tFirst Game\t1990\t101\tPC\r\n"
        success, message = utils.import_games(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(message, "Games: 1 created, 0 updated")
        game = models.Game.objects.get()
        self.assertEqual(game.name, "First Game")
        self.assertEqual(game.year_of_release, 1990)
        self.assertEqual(game.platforms.get().code, "PC")

        # Import again with the same igdb_id to trigger an update
        updated_data = "1\tFirst Game Deluxe\t1991\t101\tPC,PS5\r\n"
        success, message = utils.import_games(StringIO(updated_data))

        self.assertTrue(success)
        self.assertEqual(message, "Games: 0 created, 1 updated")
        game.refresh_from_db()
        self.assertEqual(game.name, "First Game Deluxe")
        self.assertEqual(game.year_of_release, 1991)
        self.assertCountEqual(
            game.platforms.values_list("code", flat=True),
            ["PC", "PS5"],
        )


class ImportPlatformsTests(TestCase):

    def test_import_platforms_creates_and_updates(self):
        data = "PC\tPersonal Computer\r\n"
        success, message = utils.import_platforms(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(message, "Platforms: 1 created, 0 updated")
        platform = models.Platform.objects.get()
        self.assertEqual(platform.name, "Personal Computer")

        updated_data = "PC\tPC (Updated)\r\n"
        success, message = utils.import_platforms(StringIO(updated_data))

        self.assertTrue(success)
        self.assertEqual(message, "Platforms: 0 created, 1 updated")
        platform.refresh_from_db()
        self.assertEqual(platform.name, "PC (Updated)")


class ImportListsTests(TestCase):

    def test_import_lists_assigns_order_and_publication(self):
        data = (
            "IGN\t2020\tE\tTop 10\thttps://example.com/ign\r\n"
            "Edge\t2021\tA\tBest Ever\thttps://example.com/edge\r\n"
        )

        success, message = utils.import_lists(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(message, "Lists: 2 created, 0 updated")
        orders = list(
            models.List.objects.order_by("order").values_list("order", flat=True)
        )
        self.assertEqual(orders, [1, 2])
        self.assertEqual(models.List.objects.first().publisher.name, "IGN")


class ImportListMembershipsTests(TestCase):

    def setUp(self):
        list_data = (
            "IGN\t2020\tE\tTop 10\thttps://example.com/ign\r\n"
            "Edge\t2021\tA\tBest Ever\thttps://example.com/edge\r\n"
        )
        utils.import_lists(StringIO(list_data))
        models.Game.objects.create(
            name="Game 1", rank=1, igdb_id=1, year_of_release=1990
        )
        models.Game.objects.create(
            name="Game 2", rank=2, igdb_id=2, year_of_release=1991
        )

    def test_import_listmemberships_creates_entries(self):
        data = "0:1\t1:3\r\n0:2\r\n"
        success, message = utils.import_listmemberships(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(message, "List memberships: 3 created")
        self.assertEqual(models.ListMembership.objects.count(), 3)
        top_entry = models.ListMembership.objects.get(game__rank=1, list__order=1)
        self.assertEqual(top_entry.rank, 1)


class ImportDevelopersTests(TestCase):

    def test_import_developers_creates_aliases(self):
        data = "Foo Studio\tFoo Studio\tFoo Devs\r\n" "Bar Alias\tBar Studio\r\n"
        success, message = utils.import_developers(StringIO(data))

        self.assertTrue(success)
        self.assertEqual(message, "Developers: 2 created, 0 updated")
        self.assertEqual(models.Developer.objects.count(), 2)
        foo = models.Developer.objects.get(name="Foo Studio")
        self.assertEqual(foo.aliases.count(), 2)  # canonical + extra alias


class RankingUtilsTests(TestCase):

    def setUp(self):
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


class GameListApiTests(TestCase):

    def setUp(self):
        self.platform_pc = models.Platform.objects.create(code="PC", name="PC")
        self.platform_ps = models.Platform.objects.create(code="PS", name="PlayStation")
        self.genre_action = models.Genre.objects.create(name="Action")
        self.genre_adventure = models.Genre.objects.create(name="Adventure")

        developer = models.Developer.objects.create(name="Studio", igdb_id=10)
        self.alias = models.DeveloperAlias.objects.create(
            developer=developer, name="Studio Alias", igdb_id=11
        )

        self.game1 = models.Game.objects.create(
            name="Alpha Quest",
            rank=1,
            igdb_id=1001,
            year_of_release=2000,
            slug="alpha-quest",
        )
        self.game1.platforms.add(self.platform_pc)
        self.game1.genres.add(self.genre_action)
        self.game1.developers.add(self.alias)

        self.game2 = models.Game.objects.create(
            name="Beta Saga",
            rank=2,
            igdb_id=1002,
            year_of_release=2010,
            slug="beta-saga",
        )
        self.game2.platforms.add(self.platform_ps)
        self.game2.genres.add(self.genre_adventure)

    def _get_game_names(self, **params):
        response = self.client.get("/api/games/", params)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data["results"] if "results" in data else data
        return [item["name"] for item in results]

    def test_filter_by_platform(self):
        names = self._get_game_names(platforms=str(self.platform_ps.id))
        self.assertEqual(names, ["Beta Saga"])

    def test_filter_by_genres_all_option(self):
        self.game1.genres.add(self.genre_adventure)
        names = self._get_game_names(
            genres=f"{self.genre_action.id},{self.genre_adventure.id}",
        )
        self.assertEqual(names, ["Alpha Quest"])

    def test_filter_by_developer(self):
        names = self._get_game_names(developer=str(self.alias.developer.igdb_id))
        self.assertEqual(names, ["Alpha Quest"])
