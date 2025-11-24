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
