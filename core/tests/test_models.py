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
            user = django_models.ForeignKey(models.User, on_delete=django_models.CASCADE)

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
