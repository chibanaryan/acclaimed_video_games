from io import BytesIO, StringIO
from unittest import mock

from django.test import TestCase

from games import constants, models, utils


class ImportDataRoutingTests(TestCase):

    def test_import_data_calls_delete_handler(self):
        with mock.patch(
            "games.services.import_handler.delete_existing_data", return_value=("ok", 0)
        ) as delete_mock:
            result = utils.import_data({"delete": True})
        delete_mock.assert_called_once()
        self.assertEqual(result, ("ok", 0))

    def test_import_data_validates_type(self):
        stream = BytesIO(b"")
        success, message = utils.import_data({"file": stream, "type": "X"})
        self.assertFalse(success)
        self.assertIn("Unknown import type", message)

    def test_import_data_wraps_handler_errors(self):
        stream = BytesIO(b"")
        with mock.patch(
            "games.services.import_handler.import_games", side_effect=ValueError("boom")
        ):
            success, message = utils.import_data(
                {
                    "file": stream,
                    "type": constants.TYPE_GAME,
                }
            )
        self.assertFalse(success)
        self.assertIn("Could not process uploaded file", message)


class ImportHelpersTests(TestCase):

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


class ApplyGenreFilterTests(TestCase):
    """Tests for apply_genre_filter utility function."""

    def setUp(self):
        self.genre_action = models.Genre.objects.create(name="Action")
        self.genre_rpg = models.Genre.objects.create(name="RPG")
        self.genre_puzzle = models.Genre.objects.create(name="Puzzle")

        self.game_action = models.Game.objects.create(name="Action Game", rank=1)
        self.game_action.genres.add(self.genre_action)

        self.game_rpg = models.Game.objects.create(name="RPG Game", rank=2)
        self.game_rpg.genres.add(self.genre_rpg)

        self.game_action_rpg = models.Game.objects.create(name="Action RPG", rank=3)
        self.game_action_rpg.genres.add(self.genre_action, self.genre_rpg)

    def test_empty_genre_list_returns_all(self):
        """Empty genre list should return all games."""
        qs = models.Game.objects.all()
        result = utils.apply_genre_filter(qs, [])
        self.assertEqual(result.count(), 3)

    def test_match_all_requires_all_genres(self):
        """match_all=True should require games to have ALL genres."""
        qs = models.Game.objects.all()
        result = utils.apply_genre_filter(
            qs, [self.genre_action.id, self.genre_rpg.id], match_all=True
        )
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first(), self.game_action_rpg)

    def test_match_any_accepts_any_genre(self):
        """match_all=False should return games with ANY of the genres."""
        qs = models.Game.objects.all()
        result = utils.apply_genre_filter(
            qs, [self.genre_action.id, self.genre_rpg.id], match_all=False
        )
        # Action Game, RPG Game, and Action RPG all match (use distinct)
        self.assertEqual(result.distinct().count(), 3)

    def test_single_genre_filter(self):
        """Single genre should work correctly."""
        qs = models.Game.objects.all()
        result = utils.apply_genre_filter(qs, [self.genre_action.id], match_all=True)
        self.assertEqual(result.count(), 2)  # Action Game and Action RPG


class ApplyPlatformFilterTests(TestCase):
    """Tests for apply_platform_filter utility function."""

    def setUp(self):
        self.pc = models.Platform.objects.create(code="PC", name="PC")
        self.ps5 = models.Platform.objects.create(code="PS5", name="PlayStation 5")

        self.game_pc = models.Game.objects.create(name="PC Game", rank=1)
        self.game_pc.platforms.add(self.pc)

        self.game_ps5 = models.Game.objects.create(name="PS5 Game", rank=2)
        self.game_ps5.platforms.add(self.ps5)

        self.game_both = models.Game.objects.create(name="Multi-platform Game", rank=3)
        self.game_both.platforms.add(self.pc, self.ps5)

    def test_empty_platform_list_returns_all(self):
        """Empty platform list should return all games."""
        qs = models.Game.objects.all()
        result = utils.apply_platform_filter(qs, [])
        self.assertEqual(result.count(), 3)

    def test_single_platform_filter(self):
        """Single platform should filter correctly."""
        qs = models.Game.objects.all()
        result = utils.apply_platform_filter(qs, [self.pc.id])
        self.assertEqual(result.count(), 2)  # PC Game and Multi-platform

    def test_multiple_platforms_uses_any(self):
        """Multiple platforms should use ANY match."""
        qs = models.Game.objects.all()
        result = utils.apply_platform_filter(qs, [self.pc.id, self.ps5.id])
        # All 3 games match (use distinct for unique count)
        self.assertEqual(result.distinct().count(), 3)


class SendContactEmailTests(TestCase):
    """Test send_contact_email utility function."""

    def test_send_contact_email_success(self):
        """Test sending email successfully."""
        from django.core import mail

        result = utils.send_contact_email(
            name="Test User",
            email="test@example.com",
            category="general",
            message="This is a test message.",
        )

        # In DEBUG mode, email goes to console backend, so this will succeed
        self.assertTrue(result)

        # Check that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check email details
        email = mail.outbox[0]
        self.assertIn("General", email.subject)
        self.assertIn("Test User", email.subject)
        self.assertIn("Test User", email.body)
        self.assertIn("test@example.com", email.body)
        self.assertIn("This is a test message.", email.body)

    def test_send_contact_email_all_categories(self):
        """Test sending email with all category types."""
        from django.core import mail

        categories = {
            "feature": "Feature Request",
            "bug": "Bug Report",
            "data": "Data Issue",
            "general": "General",
            "partnership": "Partnership/Business",
            "press": "Press Inquiry",
        }

        for category, label in categories.items():
            mail.outbox.clear()  # Clear previous emails

            result = utils.send_contact_email(
                name="Test User",
                email="test@example.com",
                category=category,
                message="Test message.",
            )

            self.assertTrue(result)
            self.assertEqual(len(mail.outbox), 1)
            self.assertIn(label, mail.outbox[0].subject)

    def test_send_contact_email_exception_handling(self):
        """Test email sending with exception."""
        with mock.patch(
            "django.core.mail.send_mail", side_effect=Exception("SMTP error")
        ):
            result = utils.send_contact_email(
                name="Test User",
                email="test@example.com",
                category="general",
                message="Test message.",
            )

            # Should return False on exception
            self.assertFalse(result)


class ApplyYearFiltersTests(TestCase):
    """Tests for apply_year_filters utility function."""

    def setUp(self):
        """Create test games with different years."""
        models.Game.objects.create(name="Game 1980", year_of_release=1980, rank=1)
        models.Game.objects.create(name="Game 1985", year_of_release=1985, rank=2)
        models.Game.objects.create(name="Game 1990", year_of_release=1990, rank=3)
        models.Game.objects.create(name="Game 1995", year_of_release=1995, rank=4)
        models.Game.objects.create(name="Game 2000", year_of_release=2000, rank=5)

    def test_no_filters_returns_all(self):
        """Test that no filters returns all games."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs)
        self.assertEqual(result.count(), 5)

    def test_decade_filter(self):
        """Test filtering by decade."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs, decade="1980-89")
        self.assertEqual(result.count(), 2)
        names = list(result.values_list("name", flat=True))
        self.assertIn("Game 1980", names)
        self.assertIn("Game 1985", names)

    def test_year_filter(self):
        """Test filtering by single year."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs, year="1990")
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().name, "Game 1990")

    def test_start_end_filters(self):
        """Test filtering by year range."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs, start="1985", end="1995")
        self.assertEqual(result.count(), 3)

    def test_invalid_year_ignored(self):
        """Test that invalid year values are ignored."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs, year="invalid")
        self.assertEqual(result.count(), 5)

    def test_decade_takes_precedence_over_year(self):
        """Test that decade filter ignores year filter."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs, decade="1990-99", year="1980")
        self.assertEqual(result.count(), 2)  # 1990 and 1995

    def test_invalid_start_year_ignored(self):
        """Test that invalid start year value is ignored."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs, start="invalid")
        self.assertEqual(result.count(), 5)

    def test_invalid_end_year_ignored(self):
        """Test that invalid end year value is ignored."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs, end="invalid")
        self.assertEqual(result.count(), 5)

    def test_mixed_valid_invalid_start_end(self):
        """Test that valid start with invalid end ignores only invalid."""
        qs = models.Game.objects.all()
        result = utils.apply_year_filters(qs, start="1985", end="invalid")
        # Should filter by start >= 1985 but ignore invalid end
        self.assertEqual(result.count(), 4)  # 1985, 1990, 1995, 2000


class SafeIntFilterTests(TestCase):
    """Tests for safe_int_filter utility function."""

    def setUp(self):
        """Create test games."""
        models.Game.objects.create(name="Game 1", year_of_release=1990, rank=1)
        models.Game.objects.create(name="Game 2", year_of_release=2000, rank=2)

    def test_valid_filter(self):
        """Test filtering with valid integer."""
        qs = models.Game.objects.all()
        result = utils.safe_int_filter(qs, "1990", "year_of_release")
        self.assertEqual(result.count(), 1)

    def test_invalid_filter_ignored(self):
        """Test that invalid values are ignored."""
        qs = models.Game.objects.all()
        result = utils.safe_int_filter(qs, "invalid", "year_of_release")
        self.assertEqual(result.count(), 2)

    def test_none_value_returns_queryset(self):
        """Test that None value returns unchanged queryset."""
        qs = models.Game.objects.all()
        result = utils.safe_int_filter(qs, None, "year_of_release")
        self.assertEqual(result.count(), 2)


class GetOrSetCacheTests(TestCase):
    """Tests for get_or_set_cache utility function."""

    def setUp(self):
        """Create test genres."""
        models.Genre.objects.create(name="Action")
        models.Genre.objects.create(name="RPG")
        models.Genre.objects.create(name="Adventure")

    def test_returns_list_from_queryset(self):
        """Test that function returns list of dicts from queryset."""
        result = utils.get_or_set_cache(
            "test_genres",
            models.Genre.objects.all(),
            ["id", "name"],
            order_by="name",
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["name"], "Action")

    def test_transform_id(self):
        """Test that transform_id converts id to string."""
        result = utils.get_or_set_cache(
            "test_genres_str",
            models.Genre.objects.all(),
            ["id", "name"],
            transform_id=True,
        )
        self.assertIsInstance(result[0]["id"], str)

    def test_caches_result(self):
        """Test that result is cached."""
        from django.core.cache import cache

        cache.delete("test_cache_key")

        # First call should query database
        result1 = utils.get_or_set_cache(
            "test_cache_key",
            models.Genre.objects.all(),
            ["id", "name"],
        )

        # Second call should return cached result
        result2 = utils.get_or_set_cache(
            "test_cache_key",
            models.Genre.objects.none(),  # Different queryset
            ["id", "name"],
        )

        self.assertEqual(result1, result2)
        self.assertEqual(len(result2), 3)  # Still has 3 genres from cache
