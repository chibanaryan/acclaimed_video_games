from io import StringIO

from django.test import TestCase

from .. import models, utils


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
        self.assertEqual(foo.aliases.count(), 2)
