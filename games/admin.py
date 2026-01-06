from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count
from django.forms import ModelForm
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.text import Truncator

from core.models import User
from . import models


class SubsidiaryInlineAdmin(admin.TabularInline):
    """Inline admin for subsidiary developers."""

    model = models.Developer
    fk_name = "parent"
    extra = 0
    fields = ["name", "slug", "igdb_id"]
    show_change_link = True


@admin.register(models.Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "year_start", "year_end"]
    list_editable = ["year_start", "year_end"]
    ordering = ["name"]


@admin.register(models.IGDBGenre)
class IGDBGenreAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(models.WikipediaGenre)
class WikipediaGenreAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "level", "path", "game_count", "display_order"]
    list_filter = ["level", "parent"]
    search_fields = ["name", "path"]
    ordering = ["level", "display_order", "name"]
    readonly_fields = ["game_count"]

    @admin.display(description="Games")
    def game_count(self, obj):
        return obj.games_with_wikipedia_genre.count()


@admin.register(models.WikipediaCountry)
class WikipediaCountryAdmin(admin.ModelAdmin):
    list_display = ["name", "wikidata_id", "slug", "game_count"]
    search_fields = ["name", "wikidata_id"]
    ordering = ["name"]
    readonly_fields = ["game_count"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_game_count=Count("games"))

    @admin.display(description="Games", ordering="_game_count")
    def game_count(self, obj):
        return getattr(obj, "_game_count", obj.games.count())


@admin.register(models.WikipediaGameMode)
class WikipediaGameModeAdmin(admin.ModelAdmin):
    list_display = ["name", "wikidata_id", "slug", "game_count"]
    search_fields = ["name", "wikidata_id"]
    ordering = ["name"]
    readonly_fields = ["game_count"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_game_count=Count("games"))

    @admin.display(description="Games", ordering="_game_count")
    def game_count(self, obj):
        return getattr(obj, "_game_count", obj.games.count())


@admin.register(models.Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "igdb_id", "game_count"]
    search_fields = ["name", "slug"]
    ordering = ["name"]
    readonly_fields = ["game_count"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_game_count=Count("games"))

    @admin.display(description="Games", ordering="_game_count")
    def game_count(self, obj):
        return getattr(obj, "_game_count", obj.games.count())


@admin.register(models.Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = ["__str__", "slug", "igdb_id", "parent", "game_count"]
    list_filter = ["parent"]
    search_fields = ["name"]
    inlines = [SubsidiaryInlineAdmin]
    raw_id_fields = ["parent"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("parent").annotate(
            _game_count=Count("developed_games")
        )

    @admin.display(description="Games", ordering="_game_count")
    def game_count(self, obj):
        return getattr(obj, "_game_count", obj.developed_games.count())


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
        "_hltb_data_link",
        "_igdb_genres",
        "_wikipedia_genres",
    ]
    list_filter = ["year_of_release"]
    search_fields = ["name"]
    filter_horizontal = [
        "developers",
        "platforms",
        "genres",
        "wikipedia_genres",
        "wikipedia_countries",
        "wikipedia_game_modes",
        "series",
    ]

    def get_queryset(self, request: HttpRequest):
        """Prefetch genres and select primary data records to avoid N+1 queries."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "primary_igdb_game_data",
                "primary_wikipedia_game_data",
                "primary_hltb_game_data",
            )
            .prefetch_related(
                "genres",
                "wikipedia_genres",
                "wikipedia_countries",
                "wikipedia_game_modes",
            )
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

    def _hltb_data_link(self, obj: models.Game) -> str:
        """Display link to HLTB data admin page."""
        if obj.primary_hltb_game_data:
            url = f"/admin/games/hltbgamedata/{obj.primary_hltb_game_data.id}/change/"
            return format_html('<a href="{}">View HLTB Data</a>', url)
        return "-"

    _hltb_data_link.short_description = "HLTB Data"


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
        "hltb_id",
        "wikiquote_page_title",
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
        "hltb_id",
        "wikiquote_page_title",
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


@admin.register(models.HLTBGameData)
class HLTBGameDataAdmin(admin.ModelAdmin):
    """Admin interface for HowLongToBeat game data records.

    Fetch Methods:
    - wikidata: HLTB ID was found via Wikidata external identifiers (most reliable)
    - name_search: HLTB ID was found by searching HLTB by game name (fallback)

    Typical distribution: ~87% wikidata, ~13% name_search
    """

    list_display = [
        "game",
        "igdb_id",
        "hltb_id",
        "hltb_name",
        "fetch_method",
        "main_story_hours",
        "main_extra_hours",
        "completionist_hours",
        "_hltb_link",
        "is_primary",
        "fetched_at",
        "updated_at",
    ]
    list_filter = ["fetch_method", "is_primary", "fetched_at", "updated_at"]
    search_fields = ["game__name", "igdb_id", "hltb_id"]
    raw_id_fields = ["game"]
    readonly_fields = ["fetched_at", "updated_at"]

    def _hltb_link(self, obj: models.HLTBGameData) -> str:
        """Display clickable HowLongToBeat URL."""
        if obj.hltb_url:
            return format_html(
                '<a href="{}" target="_blank">View on HLTB</a>', obj.hltb_url
            )
        return "-"

    _hltb_link.short_description = "HLTB Link"


@admin.register(models.List)
class ListAdmin(admin.ModelAdmin):
    list_display = ["__str__", "order", "publisher", "type", "media_type"]
    list_filter = ["media_type", "type", "publisher"]
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
    list_display = [
        "__str__",
        "author",
        "date",
        "active",
        "send_notification",
        "notification_sent",
    ]
    list_filter = ["author", "active", "send_notification", "notification_sent"]
    readonly_fields = ["notification_sent"]


@admin.register(models.Article)
class ArticleAdmin(admin.ModelAdmin):
    """Admin interface for blog articles with markdown preview."""

    list_display = [
        "title",
        "author",
        "status",
        "published_at",
        "created_at",
    ]
    list_filter = ["status", "author", "published_at"]
    search_fields = ["title", "content"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "published_at"

    fieldsets = (
        (
            None,
            {
                "fields": ("title", "slug", "author", "status"),
            },
        ),
        (
            "Content",
            {
                "fields": ("excerpt", "content", "featured_image"),
                "classes": ("wide",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("published_at", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    class Media:
        js = ("games/js/admin/markdown-preview.js",)
        css = {"all": ("games/css/admin-article.css",)}


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


@admin.register(models.PlayedGame)
class PlayedGameAdmin(admin.ModelAdmin):
    """Admin interface for PlayedGame records."""

    list_display = ["user", "game_name", "igdb_id", "created", "game_status"]
    list_filter = ["created"]
    search_fields = ["user__username", "user__email", "game__name", "igdb_id"]
    raw_id_fields = ["user", "game"]
    readonly_fields = ["created"]
    ordering = ["-created"]

    @admin.display(description="Game")
    def game_name(self, obj):
        """Display game name or IGDB ID if game is orphaned."""
        if obj.game:
            return obj.game.name
        return f"(orphaned) IGDB:{obj.igdb_id}"

    @admin.display(description="Status")
    def game_status(self, obj):
        """Show if the game record is connected or orphaned."""
        return "Connected" if obj.game else "Orphaned"


@admin.register(models.WantToPlayGame)
class WantToPlayGameAdmin(admin.ModelAdmin):
    """Admin interface for WantToPlayGame records (backlog/wishlist)."""

    list_display = ["user", "game_name", "igdb_id", "created", "game_status"]
    list_filter = ["created"]
    search_fields = ["user__username", "user__email", "game__name", "igdb_id"]
    raw_id_fields = ["user", "game"]
    readonly_fields = ["created"]
    ordering = ["-created"]

    @admin.display(description="Game")
    def game_name(self, obj):
        """Display game name or IGDB ID if game is orphaned."""
        if obj.game:
            return obj.game.name
        return f"(orphaned) IGDB:{obj.igdb_id}"

    @admin.display(description="Status")
    def game_status(self, obj):
        """Show if the game record is connected or orphaned."""
        return "Connected" if obj.game else "Orphaned"


@admin.register(models.SavedFilterSet)
class SavedFilterSetAdmin(admin.ModelAdmin):
    """Admin interface for SavedFilterSet records."""

    list_display = ["name", "user", "filter_summary", "modified", "created"]
    list_filter = ["modified", "created"]
    search_fields = ["name", "user__username", "user__email"]
    raw_id_fields = ["user"]
    readonly_fields = ["created", "modified"]
    ordering = ["-modified"]

    @admin.display(description="Filters")
    def filter_summary(self, obj):
        """Display a summary of the filter configuration."""
        f = obj.filters or {}
        parts = []
        if f.get("q"):
            parts.append(f"search: {f['q'][:20]}")
        if f.get("genres"):
            parts.append(f"{len(f['genres'])} genres")
        if f.get("platforms"):
            parts.append(f"{len(f['platforms'])} platforms")
        if f.get("series"):
            parts.append(f"{len(f['series'])} series")
        if f.get("start") or f.get("end"):
            parts.append(f"{f.get('start', '?')}-{f.get('end', '?')}")
        return ", ".join(parts) if parts else "(no filters)"


class PlayedGameInline(admin.TabularInline):
    """Inline admin for PlayedGame on User admin."""

    model = models.PlayedGame
    extra = 0
    fields = ["game", "igdb_id", "created"]
    readonly_fields = ["game", "igdb_id", "created"]
    can_delete = True
    ordering = ["-created"]

    def has_add_permission(self, request, obj=None):
        return False


class EmailAddressInline(admin.TabularInline):
    """Inline admin for allauth EmailAddress to show verification status."""

    from allauth.account.models import EmailAddress

    model = EmailAddress
    extra = 0
    fields = ["email", "verified", "primary"]
    readonly_fields = ["email"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for custom User model with subscription fields."""

    list_display = [
        "username",
        "email",
        "is_staff",
        "email_subscribed",
        "email_verified_display",
        "played_games_count",
        "date_joined",
    ]
    list_filter = [
        "is_staff",
        "is_superuser",
        "is_active",
        "email_subscribed",
    ]
    search_fields = ["email", "username"]
    ordering = ["-date_joined"]
    inlines = [EmailAddressInline, PlayedGameInline]

    # Extend the default fieldsets with our custom fields
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Newsletter Subscription",
            {
                "fields": (
                    "email_subscribed",
                    "date_subscribed",
                    "unsubscribe_token",
                ),
            },
        ),
    )

    readonly_fields = ["unsubscribe_token", "date_subscribed"]

    @admin.display(description="Email Verified", boolean=True)
    def email_verified_display(self, obj):
        """Show email verification status from allauth EmailAddress."""
        return obj.email_verified

    @admin.display(description="Played")
    def played_games_count(self, obj):
        """Show count of games marked as played."""
        return obj.played_games.count()
