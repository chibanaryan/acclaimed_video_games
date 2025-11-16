from io import BytesIO, StringIO
from unittest import mock

from django.test import TestCase

from games import constants, models, utils


class ImportDataRoutingTests(TestCase):

    def test_import_data_calls_delete_handler(self):
        with mock.patch(
            "games.utils.delete_existing_data", return_value=("ok", 0)
        ) as delete_mock:
            result = utils.import_data({"delete": True})
        delete_mock.assert_called_once()
        self.assertEqual(result, ("ok", 0))

    def test_import_data_calls_igdb_handler(self):
        with mock.patch(
            "games.utils.import_igdb", return_value=("igdb", 1)
        ) as igdb_mock:
            result = utils.import_data({"igdb": True})
        igdb_mock.assert_called_once()
        self.assertEqual(result, ("igdb", 1))

    def test_import_data_validates_type(self):
        stream = BytesIO(b"")
        success, message = utils.import_data({"file": stream, "type": "X"})
        self.assertFalse(success)
        self.assertIn("Unknown import type", message)

    def test_import_data_wraps_handler_errors(self):
        stream = BytesIO(b"")
        with mock.patch("games.utils.import_games", side_effect=ValueError("boom")):
            success, message = utils.import_data(
                {
                    "file": stream,
                    "type": constants.TYPE_GAME,
                }
            )
        self.assertFalse(success)
        self.assertIn("Could not process uploaded file", message)


class ImportHelpersTests(TestCase):

    def test_import_igdb_updates_each_game(self):
        fake_game = mock.Mock()
        with mock.patch("games.utils.models.Game.objects") as manager:
            manager.all.return_value = [fake_game]
            utils.import_igdb()
        fake_game.get_igdb_data.assert_called_once()

    def test_delete_existing_data_deletes_models(self):
        pub = models.Publication.objects.create(name="IGN")
        lst = models.List.objects.create(
            publisher=pub, name="Top", year=2020, type=constants.LIST_EOY, order=1
        )
        platform = models.Platform.objects.create(code="PCX", name="PCX")
        dev = models.Developer.objects.create(name="Studio")
        alias = models.DeveloperAlias.objects.create(developer=dev, name="Studio Alias")
        game = models.Game.objects.create(
            name="Alpha",
            rank=1,
            igdb_id=100,
            year_of_release=2000,
        )
        models.ListMembership.objects.create(list=lst, game=game, rank=1)

        success, message = utils.delete_existing_data()

        self.assertTrue(success)
        self.assertIn("objects deleted", message)
        self.assertEqual(models.Game.objects.count(), 0)
        self.assertEqual(models.Platform.objects.count(), 0)

    def test_import_lists_counts_updates(self):
        pub = models.Publication.objects.create(name="IGN")
        models.List.objects.create(
            publisher=pub,
            name="Top",
            year=2020,
            type=constants.LIST_EOY,
            order=1,
        )
        stream = StringIO("IGN\t2020\tE\tTop\thttps://example.com\r\n")
        success, message = utils.import_lists(stream)
        self.assertTrue(success)
        self.assertIn("1 updated", message)

    def test_import_listmemberships_skips_missing_lists(self):
        pub = models.Publication.objects.create(name="IGN")
        lst = models.List.objects.create(
            publisher=pub,
            name="Top",
            year=2020,
            type=constants.LIST_EOY,
            order=1,
        )
        game = models.Game.objects.create(
            name="Alpha",
            rank=1,
            igdb_id=999,
            year_of_release=2000,
        )

        stream = StringIO("0:1\t3:2\r\n")
        success, message = utils.import_listmemberships(stream)
        self.assertTrue(success)
        self.assertEqual(models.ListMembership.objects.count(), 1)
        membership = models.ListMembership.objects.first()
        self.assertEqual(membership.list, lst)
        self.assertIn("1 created", message)

    def test_import_developers_counts_updates(self):
        developer = models.Developer.objects.create(name="Canonical")
        stream = StringIO("Alias\tCanonical\r\n")
        success, message = utils.import_developers(stream)
        self.assertTrue(success)
        self.assertIn("1 updated", message)

    def test_import_developers_with_two_aliases(self):
        stream = StringIO("Alias1\tCanonical\tAlias2\r\n")
        success, message = utils.import_developers(stream)
        self.assertTrue(success)
        self.assertIn("1 created", message)
        self.assertEqual(models.Developer.objects.count(), 1)
        self.assertEqual(models.DeveloperAlias.objects.count(), 2)
        developer = models.Developer.objects.first()
        self.assertEqual(developer.name, "Canonical")
        alias_names = list(models.DeveloperAlias.objects.values_list("name", flat=True))
        self.assertIn("Alias1", alias_names)
        self.assertIn("Alias2", alias_names)


class FilterTests(TestCase):

    def test_filter_strips_whitespace_from_parameters(self):
        platform = models.Platform.objects.create(code="PC", name="PC")
        game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=1001,
            year_of_release=2020,
        )
        game.platforms.add(platform)

        filter = utils.Filter(param="year", fields=["year_of_release"], coerce=int)
        qs = models.Game.objects.all()
        filtered_qs = filter.filter_queryset(qs, " 2020 ")
        self.assertEqual(filtered_qs.count(), 1)
        self.assertEqual(filtered_qs.first(), game)
