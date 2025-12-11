from django.contrib import admin
from django.forms import ModelForm
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.text import Truncator

from . import models


class StudioInlineAdmin(admin.TabularInline):
    model = models.Studio
    extra = 0


@admin.register(models.Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ["name", "code"]


@admin.register(models.IGDBGenre)
class IGDBGenreAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(models.WikipediaGenre)
class WikipediaGenreAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["__str__", "slug"]
    search_fields = ["name"]
    inlines = [StudioInlineAdmin]


@admin.register(models.Studio)
class StudioAdmin(admin.ModelAdmin):
    list_display = ["__str__", "igdb_id"]
    search_fields = ["name"]


class GameQuoteInline(admin.TabularInline):
    """Inline editor for game quotes."""

    model = models.GameQuote
    extra = 1
    fields = ["text", "attribution", "is_featured"]


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "rank",
        "year_rank",
        "decade_rank",
        "year_of_release",
        "igdb_id",
        "wikidata_id",
        "_igdb_data_link",
        "_wikipedia_data_link",
        "_igdb_genres",
        "_wikipedia_genres",
    ]
    list_filter = ["year_of_release"]
    search_fields = ["name"]
    filter_horizontal = ["studios", "platforms", "genres", "wikipedia_genres"]
    inlines = [GameQuoteInline]

    def get_queryset(self, request: HttpRequest):
        """Prefetch genres and select primary data records to avoid N+1 queries."""
        return (
            super()
            .get_queryset(request)
            .select_related("primary_igdb_game_data", "primary_wikipedia_game_data")
            .prefetch_related("genres", "wikipedia_genres")
        )

    def save_model(
        self, request: HttpRequest, obj: models.Game, form: ModelForm, change: bool
    ) -> None:
        """Save the game model, fetching fresh IGDB data."""
        obj.get_igdb_data(cache_results=False)
        obj.save()

    def _igdb_genres(self, obj: models.Game) -> str:
        """Display comma-separated list of IGDB genres for the game."""
        # Use prefetched genres instead of values_list to avoid extra query
        genres = [genre.name for genre in obj.genres.all()]
        return ", ".join(genres) if genres else "-"

    _igdb_genres.short_description = "IGDB Genres"

    def _wikipedia_genres(self, obj: models.Game) -> str:
        """Display comma-separated list of Wikipedia genres for the game."""
        # Use prefetched genres instead of values_list to avoid extra query
        genres = [genre.name for genre in obj.wikipedia_genres.all()]
        return ", ".join(genres) if genres else "-"

    _wikipedia_genres.short_description = "Wikipedia Genres"

    def _igdb_data_link(self, obj: models.Game) -> str:
        """Display link to IGDB data admin page."""
        if obj.primary_igdb_game_data:
            url = f"/admin/games/igdbgamedata/{obj.primary_igdb_game_data.id}/change/"
            return format_html('<a href="{}">View IGDB Data</a>', url)
        return "-"

    _igdb_data_link.short_description = "IGDB Data"

    def _wikipedia_data_link(self, obj: models.Game) -> str:
        """Display link to Wikipedia data admin page."""
        if obj.primary_wikipedia_game_data:
            url = (
                f"/admin/games/wikipediagamedata/"
                f"{obj.primary_wikipedia_game_data.id}/change/"
            )
            return format_html('<a href="{}">View Wikipedia Data</a>', url)
        return "-"

    _wikipedia_data_link.short_description = "Wikipedia Data"


@admin.register(models.IGDBGameData)
class IGDBGameDataAdmin(admin.ModelAdmin):
    """Admin interface for IGDB game data records."""

    list_display = [
        "game",
        "igdb_id",
        "artwork_id",
        "_url_link",
        "_description_preview",
        "is_primary",
        "fetched_at",
        "updated_at",
    ]
    list_filter = ["is_primary", "fetched_at", "updated_at"]
    search_fields = ["game__name", "igdb_id", "artwork_id", "description"]
    raw_id_fields = ["game"]
    readonly_fields = ["fetched_at", "updated_at"]

    def _url_link(self, obj: models.IGDBGameData) -> str:
        """Display clickable IGDB URL."""
        if obj.url:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.url, obj.url)
        return "-"

    _url_link.short_description = "IGDB URL"

    def _description_preview(self, obj: models.IGDBGameData) -> str:
        """Display truncated description."""
        if obj.description:
            return Truncator(obj.description).words(10)
        return "-"

    _description_preview.short_description = "Description"


@admin.register(models.WikipediaGameData)
class WikipediaGameDataAdmin(admin.ModelAdmin):
    """Admin interface for Wikipedia game data records."""

    list_display = [
        "game",
        "page_title",
        "wikidata_id",
        "primary_genre",
        "_all_genres_preview",
        "lookup_source",
        "_wikipedia_link",
        "is_primary",
        "fetched_at",
        "updated_at",
    ]
    list_filter = ["is_primary", "lookup_source", "fetched_at", "updated_at"]
    search_fields = [
        "game__name",
        "page_title",
        "wikidata_id",
        "primary_genre",
        "lookup_source",
    ]
    raw_id_fields = ["game"]
    readonly_fields = ["fetched_at", "updated_at"]

    def _all_genres_preview(self, obj: models.WikipediaGameData) -> str:
        """Display all genres from Wikipedia."""
        if obj.all_genres:
            return obj.all_genres
        return "-"

    _all_genres_preview.short_description = "All Genres"

    def _wikipedia_link(self, obj: models.WikipediaGameData) -> str:
        """Display clickable Wikipedia URL."""
        if obj.page_title:
            url = f"https://en.wikipedia.org/wiki/{obj.page_title.replace(' ', '_')}"
            return format_html(
                '<a href="{}" target="_blank">{}</a>', url, obj.page_title
            )
        return "-"

    _wikipedia_link.short_description = "Wikipedia Link"


@admin.register(models.GameQuote)
class GameQuoteAdmin(admin.ModelAdmin):
    """Admin interface for game quotes."""

    list_display = ["game", "quote_preview", "attribution", "is_featured", "created"]
    list_filter = ["is_featured", "created"]
    search_fields = ["game__name", "text", "attribution"]
    raw_id_fields = ["game"]

    def quote_preview(self, obj: models.GameQuote) -> str:
        """Display truncated quote text."""
        return Truncator(obj.text).words(15)

    quote_preview.short_description = "Quote"


@admin.register(models.List)
class ListAdmin(admin.ModelAdmin):
    list_display = ["__str__", "order", "publisher", "type"]
    list_filter = ["type", "publisher"]
    search_fields = ["name"]


@admin.register(models.ListMembership)
class ListMembershipAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ["__str__", "slug"]


@admin.register(models.Snippet)
class SnippetAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["__str__", "author", "date", "active", "notification_sent"]
    list_filter = ["author", "active", "notification_sent"]
    readonly_fields = ["notification_sent"]


@admin.register(models.SiteMetadata)
class SiteMetadataAdmin(admin.ModelAdmin):
    list_display = ["__str__", "last_full_update"]
    fields = ["last_full_update"]

    def has_add_permission(self, request):
        # Only allow one instance (singleton pattern)
        return not models.SiteMetadata.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the singleton instance
        return False


@admin.register(models.Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    """Admin interface for newsletter subscribers."""

    list_display = [
        "email",
        "is_confirmed",
        "is_active",
        "date_subscribed",
    ]
    list_filter = ["is_confirmed", "is_active", "date_subscribed"]
    search_fields = ["email"]
    readonly_fields = [
        "email",
        "date_subscribed",
        "confirmation_token",
        "unsubscribe_token",
    ]
    ordering = ["-date_subscribed"]

    def has_add_permission(self, request):
        # Prevent manual addition of subscribers through admin
        # Subscribers should only be added via the public subscription form
        return False
