from django.contrib import admin
from django.forms import ModelForm
from django.http import HttpRequest

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
        "igdb_artwork_id",
        "igdb_url",
        "_genres",
    ]
    list_filter = ["year_of_release"]
    search_fields = ["name"]
    filter_horizontal = ["developers", "platforms", "genres"]

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
    list_display = ["__str__", "date", "active"]


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
