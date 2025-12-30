"""Tests for authentication adapters and modal-based auth views.

These tests cover the custom allauth adapters (ModalAccountAdapter and
ModalSocialAccountAdapter) and their integration with the modal-based
authentication flow.
"""

from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from games.adapters import ModalAccountAdapter, ModalSocialAccountAdapter

User = get_user_model()


class ModalAccountAdapterTest(TestCase):
    """Test the ModalAccountAdapter for modal-friendly redirects."""

    def setUp(self):
        self.adapter = ModalAccountAdapter()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser@example.com",
            email="testuser@example.com",
            password="testpass123",
        )

    def test_populate_username_uses_email(self):
        """Test that populate_username sets username to email."""
        user = Mock()
        user.email = "newuser@example.com"
        request = self.factory.get("/")

        self.adapter.populate_username(request, user)

        self.assertEqual(user.username, "newuser@example.com")

    def test_get_login_redirect_url_htmx_returns_root(self):
        """Test that HTMX login requests redirect to root."""
        request = self.factory.get("/", HTTP_HX_REQUEST="true")
        request.user = self.user

        url = self.adapter.get_login_redirect_url(request)

        self.assertEqual(url, "/")

    def test_get_login_redirect_url_non_htmx_uses_default(self):
        """Test that non-HTMX login requests use default redirect."""
        request = self.factory.get("/")
        request.user = self.user

        url = self.adapter.get_login_redirect_url(request)

        # Default redirect should be something other than necessarily "/"
        # (depends on allauth settings, but shouldn't be forced to "/" for non-HTMX)
        self.assertIsNotNone(url)

    def test_get_signup_redirect_url_htmx_returns_root(self):
        """Test that HTMX signup requests redirect to root."""
        request = self.factory.get("/", HTTP_HX_REQUEST="true")
        request.user = self.user

        url = self.adapter.get_signup_redirect_url(request)

        self.assertEqual(url, "/")

    def test_get_signup_redirect_url_non_htmx_uses_default(self):
        """Test that non-HTMX signup requests use default redirect."""
        request = self.factory.get("/")
        request.user = self.user

        url = self.adapter.get_signup_redirect_url(request)

        # Default redirect should be valid
        self.assertIsNotNone(url)


class ModalSocialAccountAdapterTest(TestCase):
    """Test the ModalSocialAccountAdapter."""

    def test_adapter_instantiates(self):
        """Test that the social adapter can be instantiated."""
        adapter = ModalSocialAccountAdapter()
        self.assertIsNotNone(adapter)

    def test_adapter_inherits_defaults(self):
        """Test that the adapter inherits from DefaultSocialAccountAdapter."""
        from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

        adapter = ModalSocialAccountAdapter()
        self.assertIsInstance(adapter, DefaultSocialAccountAdapter)


class LegacyAdapterAliasTest(TestCase):
    """Test backwards compatibility of EmailAsUsernameAdapter alias."""

    def test_email_as_username_adapter_alias(self):
        """Test that EmailAsUsernameAdapter is an alias for ModalAccountAdapter."""
        from games.adapters import EmailAsUsernameAdapter

        self.assertIs(EmailAsUsernameAdapter, ModalAccountAdapter)
