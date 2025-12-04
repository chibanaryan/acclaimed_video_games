from django.apps import AppConfig


class GamesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "games"

    def ready(self):
        """Import signals when the app is ready."""
        import games.signals  # noqa: F401
