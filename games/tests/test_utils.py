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
        models.Platform.objects.create(code="PCX", name="PCX")
        developer = models.Developer.objects.create(name="Studio")
        models.DeveloperAlias.objects.create(developer=developer, name="Studio Alias")
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
        models.Game.objects.create(
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
        models.Developer.objects.create(name="Canonical")
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


class RankingCacheTests(TestCase):
    """Tests for ranking cache TTL and memory leak prevention."""

    def setUp(self):
        """Clear caches before each test."""
        utils.clear_ranking_caches()

    def tearDown(self):
        """Clear caches after each test."""
        utils.clear_ranking_caches()

    def test_clear_ranking_caches_clears_dictionaries(self):
        """Test that clear_ranking_caches() empties the cache dictionaries."""
        # Create some test games
        models.Game.objects.create(
            name="Game 1", rank=1, igdb_id=1, year_of_release=2020
        )
        models.Game.objects.create(
            name="Game 2", rank=2, igdb_id=2, year_of_release=2020
        )

        # Load rankings (populates caches)
        utils._load_rankings()
        self.assertTrue(len(utils.year_rankings) > 0)
        self.assertTrue(len(utils.decade_rankings) > 0)

        # Clear caches
        utils.clear_ranking_caches()
        self.assertEqual(len(utils.year_rankings), 0)
        self.assertEqual(len(utils.decade_rankings), 0)
        self.assertIsNone(utils._rankings_cache_timestamp)

    def test_ranking_cache_expires_after_ttl(self):
        """Test that ranking caches expire after TTL."""
        # Create test games
        models.Game.objects.create(
            name="Game 1", rank=1, igdb_id=1, year_of_release=2020
        )

        # Load rankings
        utils._load_rankings()
        self.assertTrue(len(utils.year_rankings) > 0)
        initial_timestamp = utils._rankings_cache_timestamp

        # Mock time to simulate cache expiration
        with mock.patch("time.time") as mock_time:
            # Set current time to be past the TTL (5 minutes + 1 second)
            mock_time.return_value = initial_timestamp + utils._RANKINGS_CACHE_TTL + 1

            # Trigger cache reload by calling _load_rankings again
            utils._load_rankings()

            # Cache should have been cleared and reloaded
            # The timestamp should be updated to the new time
            self.assertEqual(utils._rankings_cache_timestamp, mock_time.return_value)

    def test_ranking_cache_persists_within_ttl(self):
        """Test that ranking caches persist when accessed within TTL."""
        # Create test games
        models.Game.objects.create(
            name="Game 1", rank=1, igdb_id=1, year_of_release=2020
        )

        # Load rankings
        utils._load_rankings()
        initial_timestamp = utils._rankings_cache_timestamp
        initial_year_rankings = utils.year_rankings.copy()

        # Mock time to be within TTL (2 minutes later)
        with mock.patch("time.time") as mock_time:
            mock_time.return_value = initial_timestamp + 120  # 2 minutes

            # Call _load_rankings again
            utils._load_rankings()

            # Cache should NOT have been cleared (timestamp unchanged)
            self.assertEqual(utils._rankings_cache_timestamp, initial_timestamp)
            # Rankings should be the same
            self.assertEqual(utils.year_rankings, initial_year_rankings)
