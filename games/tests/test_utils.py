from io import BytesIO, StringIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.models import User
from games import constants, models, utils
from games.models import Post


class ImportDataRoutingTests(TestCase):

    def test_import_data_calls_delete_handler(self):
        with mock.patch(
            "games.services.import_handler.delete_existing_data", return_value=("ok", 0)
        ) as delete_mock:
            result = utils.import_data({"delete": True})
        delete_mock.assert_called_once()
        self.assertEqual(result, ("ok", 0))

    def test_import_data_prefers_batch_files_over_delete_handler(self):
        upload = SimpleUploadedFile("PlatformDB.txt", b"PC\tPersonal Computer\r\n")

        with mock.patch(
            "games.services.import_handler.import_batch",
            return_value=(True, "Imported"),
        ) as batch_mock:
            with mock.patch(
                "games.services.import_handler.delete_existing_data",
                return_value=(True, "Deleted"),
            ) as delete_mock:
                result = utils.import_data({"delete": True, "platforms_file": upload})

        batch_mock.assert_called_once()
        delete_mock.assert_not_called()
        self.assertEqual(result, (True, "Imported"))

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
        models.Developer.objects.create(name="Studio", slug="studio")
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
        # Platform is deleted and will be recreated during re-import via get_or_create
        self.assertEqual(models.Platform.objects.count(), 0)

    def test_delete_existing_data_preserves_user_tracking(self):
        """Verify User, PlayedGame, and WantToPlayGame records survive deletion."""
        # Create user
        user = User.objects.create_user(username="testplayer", email="test@example.com")

        # Create games with igdb_ids
        game1 = models.Game.objects.create(
            name="Played Game", rank=1, igdb_id=1001, year_of_release=2020
        )
        game2 = models.Game.objects.create(
            name="Want to Play Game", rank=2, igdb_id=1002, year_of_release=2021
        )

        # Create tracking records
        played = models.PlayedGame.objects.create(
            user=user, game=game1, igdb_id=game1.igdb_id
        )
        want_to_play = models.WantToPlayGame.objects.create(
            user=user, game=game2, igdb_id=game2.igdb_id
        )

        # Delete game data
        success, message = utils.delete_existing_data()

        self.assertTrue(success)
        self.assertEqual(models.Game.objects.count(), 0)

        # User must survive
        self.assertEqual(User.objects.filter(username="testplayer").count(), 1)

        # PlayedGame must survive with null game but preserved igdb_id
        played.refresh_from_db()
        self.assertIsNone(played.game)
        self.assertEqual(played.igdb_id, 1001)
        self.assertEqual(played.user, user)

        # WantToPlayGame must survive with null game but preserved igdb_id
        want_to_play.refresh_from_db()
        self.assertIsNone(want_to_play.game)
        self.assertEqual(want_to_play.igdb_id, 1002)
        self.assertEqual(want_to_play.user, user)

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
        self.assertIn("1 created", message)

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
        models.Developer.objects.create(name="Canonical", slug="canonical")
        stream = StringIO("Alias\tCanonical\r\n")
        success, message = utils.import_developers(stream)
        self.assertTrue(success)
        self.assertIn("1 updated", message)

    def test_import_developers_with_two_aliases(self):
        stream = StringIO("Alias1\tCanonical\tAlias2\r\n")
        success, message = utils.import_developers(stream)
        self.assertTrue(success)
        self.assertIn("1 created", message)
        # Canonical is created as root, Alias1 and Alias2 as subsidiaries
        root_devs = models.Developer.objects.filter(parent__isnull=True)
        self.assertEqual(root_devs.count(), 1)
        root_dev = root_devs.first()
        self.assertEqual(root_dev.name, "Canonical")
        subsidiary_names = list(root_dev.subsidiaries.values_list("name", flat=True))
        self.assertIn("Alias1", subsidiary_names)
        self.assertIn("Alias2", subsidiary_names)


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
        self.genre_action = models.WikipediaGenre.objects.create(
            name="Test Action Utils", slug="test-action-utils"
        )
        self.genre_rpg = models.WikipediaGenre.objects.create(
            name="Test RPG Utils", slug="test-rpg-utils"
        )
        self.genre_puzzle = models.WikipediaGenre.objects.create(
            name="Test Puzzle Utils", slug="test-puzzle-utils"
        )

        self.game_action = models.Game.objects.create(name="Action Game", rank=1)
        self.game_action.wikipedia_genres.add(self.genre_action)

        self.game_rpg = models.Game.objects.create(name="RPG Game", rank=2)
        self.game_rpg.wikipedia_genres.add(self.genre_rpg)

        self.game_action_rpg = models.Game.objects.create(name="Action RPG", rank=3)
        self.game_action_rpg.wikipedia_genres.add(self.genre_action, self.genre_rpg)

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

    def test_send_contact_email_without_at_symbol_in_base_email(self):
        """Test email when CONTACT_EMAIL doesn't contain @ symbol."""
        from django.core import mail
        from django.test import override_settings

        # Use override_settings to test with CONTACT_EMAIL without @ symbol
        with override_settings(
            CONTACT_EMAIL="contact",  # No @ symbol
            SITE_URL="https://test.com",
            DEFAULT_FROM_EMAIL="from@example.com",
        ):
            result = utils.send_contact_email(
                name="Test User",
                email="test@example.com",
                category="general",
                message="Test message.",
            )

            self.assertTrue(result)
            self.assertEqual(len(mail.outbox), 1)
            # Should use base_email directly without modification
            self.assertEqual(mail.outbox[0].to, ["contact"])


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
        models.WikipediaGenre.objects.create(
            name="Test Action Cache", slug="test-action-cache"
        )
        models.WikipediaGenre.objects.create(
            name="Test RPG Cache", slug="test-rpg-cache"
        )
        models.WikipediaGenre.objects.create(
            name="Test Adventure Cache", slug="test-adventure-cache"
        )

    def test_returns_list_from_queryset(self):
        """Test that function returns list of dicts from queryset."""
        result = utils.get_or_set_cache(
            "test_genres",
            models.WikipediaGenre.objects.filter(slug__startswith="test-"),
            ["id", "name"],
            order_by="name",
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["name"], "Test Action Cache")

    def test_transform_id(self):
        """Test that transform_id converts id to string."""
        result = utils.get_or_set_cache(
            "test_genres_str",
            models.WikipediaGenre.objects.filter(slug__startswith="test-"),
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
            models.WikipediaGenre.objects.filter(slug__startswith="test-"),
            ["id", "name"],
        )

        # Second call should return cached result
        result2 = utils.get_or_set_cache(
            "test_cache_key",
            models.WikipediaGenre.objects.none(),  # Different queryset
            ["id", "name"],
        )

        self.assertEqual(result1, result2)
        self.assertEqual(len(result2), 3)  # Still has 3 genres from cache


class SendPostNotificationEmailTests(TestCase):
    """Test send_post_notification_email utility function."""

    def test_sends_multipart_notification_email(self):
        """Test sending multipart notification email."""
        from django.core import mail

        from core.models import User
        from games.models import Post

        author = User.objects.create_user(
            username="testuser", email="author@example.com"
        )

        post = Post.objects.create(
            title="Test Post",
            text="# Test\n\n[Link](https://example.com)",
            author=author,
        )

        subscriber = User.objects.create_user(
            username="subscriber",
            email="subscriber@example.com",
            email_subscribed=True,
        )
        subscriber.generate_unsubscribe_token()
        subscriber.save()

        result = utils.send_post_notification_email(post, subscriber)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertIn("Test Post", email.subject)
        self.assertIn("subscriber@example.com", email.to)
        self.assertIn("Test Post", email.body)
        self.assertIn(subscriber.unsubscribe_token, email.body)

        # Check multipart (HTML alternative)
        self.assertEqual(len(email.alternatives), 1)
        html_content, content_type = email.alternatives[0]
        self.assertEqual(content_type, "text/html")
        self.assertIn("<h1>Test</h1>", html_content)
        self.assertIn('href="https://example.com"', html_content)

    def test_handles_exception(self):
        """Test notification sending with exception."""
        from core.models import User
        from games.models import Post

        author = User.objects.create_user(
            username="testuser", email="author@example.com"
        )

        post = Post.objects.create(
            title="Test Post", text="Test content", author=author
        )

        subscriber = User.objects.create_user(
            username="subscriber",
            email="test@example.com",
            email_subscribed=True,
        )
        subscriber.generate_unsubscribe_token()
        subscriber.save()

        with mock.patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=Exception("Error"),
        ):
            result = utils.send_post_notification_email(post, subscriber)
            self.assertFalse(result)

    def test_post_without_author_uses_default_name(self):
        """Test notification email for post without author."""
        from django.core import mail

        from core.models import User
        from games.models import Post

        # Create post without author
        post = Post.objects.create(
            title="Test Post",
            text="Test content",
            author=None,  # No author
        )

        subscriber = User.objects.create_user(
            username="subscriber",
            email="subscriber@example.com",
            email_subscribed=True,
        )
        subscriber.generate_unsubscribe_token()
        subscriber.save()

        result = utils.send_post_notification_email(post, subscriber)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        # Should use default author name
        self.assertIn("Acclaimed Video Games", mail.outbox[0].body)


class NotifySubscribersOfNewPostTests(TestCase):
    """Test notify_subscribers_of_new_post utility function."""

    def _create_subscriber(self, email, verified=True, subscribed=True):
        """Helper to create a subscriber user with EmailAddress verification."""
        from allauth.account.models import EmailAddress

        username = email.split("@")[0]
        user = User.objects.create_user(
            username=username,
            email=email,
            email_subscribed=subscribed,
        )
        user.generate_unsubscribe_token()
        user.save()

        # Create EmailAddress record with verification status
        EmailAddress.objects.create(
            user=user,
            email=email,
            verified=verified,
            primary=True,
        )
        return user

    def test_notifies_confirmed_active_subscribers(self):
        """Test batch notification to confirmed subscribers."""
        from django.core import mail

        from core.models import User
        from games.models import Post

        author = User.objects.create_user(
            username="testuser", email="author@example.com"
        )

        post = Post.objects.create(
            title="Test Post", text="Test content", author=author
        )

        # Create confirmed subscribers
        self._create_subscriber(
            "confirmed1@example.com", verified=True, subscribed=True
        )
        self._create_subscriber(
            "confirmed2@example.com", verified=True, subscribed=True
        )

        # Create unconfirmed subscriber (should not receive email)
        self._create_subscriber(
            "unconfirmed@example.com", verified=False, subscribed=True
        )

        # Create unsubscribed user (should not receive email)
        self._create_subscriber("inactive@example.com", verified=True, subscribed=False)

        sent_count = utils.notify_subscribers_of_new_post(post)

        self.assertEqual(sent_count, 2)
        self.assertEqual(len(mail.outbox), 2)

        recipient_emails = [email.to[0] for email in mail.outbox]
        self.assertIn("confirmed1@example.com", recipient_emails)
        self.assertIn("confirmed2@example.com", recipient_emails)
        self.assertNotIn("unconfirmed@example.com", recipient_emails)
        self.assertNotIn("inactive@example.com", recipient_emails)

    def test_handles_individual_failures(self):
        """Test that individual email failures don't stop batch."""
        from core.models import User
        from games.models import Post

        author = User.objects.create_user(
            username="testuser", email="author@example.com"
        )

        post = Post.objects.create(
            title="Test Post", text="Test content", author=author
        )

        self._create_subscriber(
            "subscriber1@example.com", verified=True, subscribed=True
        )
        self._create_subscriber(
            "subscriber2@example.com", verified=True, subscribed=True
        )

        # Mock to fail on first, succeed on second
        original_func = utils.send_post_notification_email
        call_count = [0]

        def side_effect_func(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return False  # First call fails
            return original_func(*args, **kwargs)  # Rest succeed

        with mock.patch(
            "games.utils.send_post_notification_email",
            side_effect=side_effect_func,
        ):
            sent_count = utils.notify_subscribers_of_new_post(post)

        # Should send to 1 (second one succeeded)
        self.assertEqual(sent_count, 1)


class PostSignalTests(TestCase):
    """Test Post signal handlers for notifications."""

    def setUp(self):
        """Create test author."""
        self.author = User.objects.create_user(
            username="author", email="author@example.com"
        )

    def test_notification_signal_triggers_when_conditions_met(self):
        """Test that notification is sent when post is active with send_notification."""
        with mock.patch("games.utils.notify_subscribers_of_new_post") as mock_notify:
            mock_notify.return_value = 5
            # Create post with notification enabled
            post = Post.objects.create(
                title="Test Post",
                text="Test content",
                author=self.author,
                active=True,
                send_notification=True,
            )
            # Signal should have triggered notification
            mock_notify.assert_called_once_with(post)
            # notification_sent should be marked True
            post.refresh_from_db()
            self.assertTrue(post.notification_sent)

    def test_notification_not_sent_when_inactive(self):
        """Test that notification is not sent for inactive posts."""
        with mock.patch("games.utils.notify_subscribers_of_new_post") as mock_notify:
            Post.objects.create(
                title="Draft Post",
                text="Draft content",
                author=self.author,
                active=False,
                send_notification=True,
            )
            mock_notify.assert_not_called()

    def test_notification_not_sent_when_flag_false(self):
        """Test that notification is not sent when send_notification is False."""
        with mock.patch("games.utils.notify_subscribers_of_new_post") as mock_notify:
            Post.objects.create(
                title="Silent Post",
                text="Silent content",
                author=self.author,
                active=True,
                send_notification=False,
            )
            mock_notify.assert_not_called()

    def test_notification_not_sent_twice(self):
        """Test that notification is not sent again on re-save."""
        with mock.patch("games.utils.notify_subscribers_of_new_post") as mock_notify:
            mock_notify.return_value = 1
            post = Post.objects.create(
                title="Test Post",
                text="Test content",
                author=self.author,
                active=True,
                send_notification=True,
            )
            # First save triggers notification
            self.assertEqual(mock_notify.call_count, 1)

            # Refresh from DB to get updated notification_sent flag
            post.refresh_from_db()
            self.assertTrue(post.notification_sent)

            # Update and save again
            post.text = "Updated content"
            post.save()

            # Should not trigger again (notification_sent is True)
            self.assertEqual(mock_notify.call_count, 1)
