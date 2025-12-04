from django.contrib import admin
from django.forms import ModelForm
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.text import Truncator

from . import models


class DeveloperAliasInlineAdmin(admin.TabularInline):
    model = models.DeveloperAlias
    extra = 0


@admin.register(models.Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ["name", "code"]


@admin.register(models.Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = ["__str__", "slug"]
    search_fields = ["name"]
    inlines = [DeveloperAliasInlineAdmin]


@admin.register(models.DeveloperAlias)
class DeveloperAliasAdmin(admin.ModelAdmin):
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
        "wikipedia_page_title",
        "wikipedia_lookup_source",
        "_wikipedia_url",
        "igdb_artwork_id",
        "igdb_url",
        "_genres",
    ]
    list_filter = ["year_of_release"]
    search_fields = ["name", "wikipedia_page_title"]
    filter_horizontal = ["developers", "platforms", "genres"]
    inlines = [GameQuoteInline]

    def get_queryset(self, request: HttpRequest):
        """Prefetch genres to avoid N+1 queries in list display."""
        return super().get_queryset(request).prefetch_related("genres")

    def save_model(
        self, request: HttpRequest, obj: models.Game, form: ModelForm, change: bool
    ) -> None:
        """Save the game model, fetching fresh IGDB data."""
        obj.get_igdb_data(cache_results=False)
        obj.save()

    def _genres(self, obj: models.Game) -> str:
        """Display comma-separated list of genres for the game."""
        # Use prefetched genres instead of values_list to avoid extra query
        return ", ".join(genre.name for genre in obj.genres.all())

    def _wikipedia_url(self, obj: models.Game) -> str:
        """Display clickable Wikipedia URL if page title exists."""
        if obj.wikipedia_page_title:
            url = f"https://en.wikipedia.org/wiki/{obj.wikipedia_page_title.replace(' ', '_')}"
            return format_html('<a href="{}" target="_blank">{}</a>', url, url)
        return "-"

    _wikipedia_url.short_description = "Wikipedia URL"


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
