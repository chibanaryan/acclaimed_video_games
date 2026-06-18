"""Tests for core model base classes."""

from django.db import models as django_models
from django.test import TestCase
from django.test.utils import isolate_apps

from core import models


@isolate_apps("core")
class CoreBaseModelStrTests(TestCase):
    """Tests for abstract base model __str__ implementations."""

    def test_external_data_base_str(self):
        class DummyExternal(models.ExternalDataBase):
            class Meta:
                app_label = "core"

        obj = DummyExternal(is_primary=True)
        self.assertEqual(str(obj), "DummyExternal (primary=True)")

    def test_user_tracking_base_str(self):
        class DummyTracking(models.UserTrackingBase):
            user = django_models.ForeignKey(
                models.User, on_delete=django_models.CASCADE
            )

            class Meta:
                app_label = "core"

        user = models.User(username="tester")
        obj = DummyTracking(user=user)
        self.assertEqual(str(obj), "tester tracked DummyTracking")

    def test_list_membership_base_str(self):
        class DummyMembership(models.ListMembershipBase):
            class Meta:
                app_label = "core"

        obj = DummyMembership(rank=5)
        self.assertEqual(str(obj), "Rank 5")


class UserUsernameReclaimTests(TestCase):
    """Tests for username availability / reclaim of unverified accounts."""

    def _make_user(self, username, email, verified=False, **kwargs):
        from allauth.account.models import EmailAddress

        user = models.User.objects.create(username=username, email=email, **kwargs)
        EmailAddress.objects.create(
            user=user, email=email, verified=verified, primary=True
        )
        return user

    def test_username_claimed_only_counts_verified_accounts(self):
        self._make_user("taken", "unverified@example.com", verified=False)
        # Held only by an unverified account -> available (case-insensitive).
        self.assertFalse(models.User.username_claimed("taken"))
        self.assertFalse(models.User.username_claimed("TAKEN"))

        self._make_user("realname", "verified@example.com", verified=True)
        self.assertTrue(models.User.username_claimed("realname"))
        self.assertTrue(models.User.username_claimed("RealName"))

    def test_username_claimed_counts_unverified_staff(self):
        # Staff/superuser accounts always count as claiming the name even when
        # unverified, since reclaim_username refuses to delete them.
        self._make_user("bossman", "boss@example.com", verified=False, is_staff=True)
        self._make_user("chief", "chief@example.com", verified=False, is_superuser=True)
        self.assertTrue(models.User.username_claimed("bossman"))
        self.assertTrue(models.User.username_claimed("chief"))

    def test_username_claimed_excludes_pk(self):
        user = self._make_user("self", "self@example.com", verified=True)
        # Excluding the holder makes it appear available (used on profile rename).
        self.assertTrue(models.User.username_claimed("self"))
        self.assertFalse(models.User.username_claimed("self", exclude_pk=user.pk))

    def test_reclaim_username_deletes_unverified_account(self):
        stale = self._make_user("taken", "typo@example.com", verified=False)
        deleted = models.User.reclaim_username("TAKEN")
        self.assertEqual(deleted, 1)
        self.assertFalse(models.User.objects.filter(pk=stale.pk).exists())

    def test_reclaim_username_keeps_verified_account(self):
        real = self._make_user("taken", "real@example.com", verified=True)
        deleted = models.User.reclaim_username("taken")
        self.assertEqual(deleted, 0)
        self.assertTrue(models.User.objects.filter(pk=real.pk).exists())

    def test_reclaim_username_never_deletes_staff(self):
        staff = self._make_user(
            "taken", "staff@example.com", verified=False, is_staff=True
        )
        superuser = self._make_user(
            "other", "su@example.com", verified=False, is_superuser=True
        )
        self.assertEqual(models.User.reclaim_username("taken"), 0)
        self.assertEqual(models.User.reclaim_username("other"), 0)
        self.assertTrue(models.User.objects.filter(pk=staff.pk).exists())
        self.assertTrue(models.User.objects.filter(pk=superuser.pk).exists())
