from allauth.account.adapter import DefaultAccountAdapter


class EmailAsUsernameAdapter(DefaultAccountAdapter):
    """Custom allauth adapter that uses email as the username."""

    def populate_username(self, request, user):
        """Set username to be the same as email."""
        user.username = user.email
