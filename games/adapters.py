from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class ModalAccountAdapter(DefaultAccountAdapter):
    """Custom allauth adapter for modal-based authentication.

    Handles email-as-username and modal-friendly redirects.
    """

    def populate_username(self, request, user):
        """Set username to be the same as email."""
        user.username = user.email

    def get_login_redirect_url(self, request):
        """Return modal-friendly redirect for HTMX requests."""
        if request.headers.get("HX-Request"):
            return "/"
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        """Return modal-friendly redirect for HTMX requests."""
        if request.headers.get("HX-Request"):
            return "/"
        return super().get_signup_redirect_url(request)


class ModalSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter for social account handling (future use).

    Prepared for future social auth integration (Google, Facebook, etc.).
    """

    pass


# Legacy alias for backwards compatibility
EmailAsUsernameAdapter = ModalAccountAdapter
