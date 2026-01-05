"""
Django admin configuration for books app.

Provides admin interfaces for all book-related models, following the same
patterns established in the games app.
"""

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils.text import Truncator

from . import models


class SubsidiaryAuthorInline(admin.TabularInline):
    """Inline admin for subsidiary authors (pen names, pseudonyms)."""

    model = models.Author
    fk_name = "parent"
    extra = 0
    fields = ["name", "slug", "goodreads_id", "open_library_id"]
    show_change_link = True


@admin.register(models.Author)
class AuthorAdmin(admin.ModelAdmin):
    """Admin interface for Author model with hierarchy support."""

    list_display = [
        "__str__",
        "slug",
        "goodreads_id",
        "open_library_id",
        "parent",
        "book_count",
    ]
    list_filter = ["parent"]
    search_fields = ["name", "goodreads_id", "open_library_id"]
    inlines = [SubsidiaryAuthorInline]
    raw_id_fields = ["parent"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("parent").annotate(_book_count=Count("books"))

    @admin.display(description="Books", ordering="_book_count")
    def book_count(self, obj):
        return getattr(obj, "_book_count", obj.books.count())


class BookGenreChildInline(admin.TabularInline):
    """Inline admin for child genres."""

    model = models.BookGenre
    fk_name = "parent"
    extra = 0
    fields = ["name", "slug", "level", "display_order"]
    show_change_link = True


@admin.register(models.BookGenre)
class BookGenreAdmin(admin.ModelAdmin):
    """Admin interface for BookGenre with hierarchy display."""

    list_display = [
        "name",
        "parent",
        "level",
        "path",
        "book_count",
        "display_order",
    ]
    list_filter = ["level", "parent"]
    search_fields = ["name", "path"]
    ordering = ["level", "display_order", "name"]
    readonly_fields = ["book_count", "level", "path"]
    inlines = [BookGenreChildInline]
    raw_id_fields = ["parent"]

    @admin.display(description="Books")
    def book_count(self, obj):
        return obj.books.count()


@admin.register(models.BookSeries)
class BookSeriesAdmin(admin.ModelAdmin):
    """Admin interface for BookSeries."""

    list_display = ["name", "slug", "goodreads_id", "book_count"]
    search_fields = ["name", "slug", "goodreads_id"]
    ordering = ["name"]
    readonly_fields = ["book_count"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_book_count=Count("books"))

    @admin.display(description="Books", ordering="_book_count")
    def book_count(self, obj):
        return getattr(obj, "_book_count", obj.books.count())


@admin.register(models.Book)
class BookAdmin(admin.ModelAdmin):
    """Admin interface for Book model."""

    list_display = [
        "name",
        "slug",
        "rank",
        "year_rank",
        "decade_rank",
        "year_published",
        "goodreads_id",
        "wikidata_id",
        "_goodreads_data_link",
        "_wikipedia_data_link",
        "_genres_display",
    ]
    list_filter = ["year_published"]
    search_fields = ["name", "slug", "goodreads_id", "isbn", "isbn13"]
    filter_horizontal = [
        "authors",
        "genres",
    ]
    raw_id_fields = ["series", "primary_goodreads_book_data", "primary_wikipedia_book_data"]
    readonly_fields = ["created", "modified"]

    def get_queryset(self, request):
        """Prefetch genres and select primary data records to avoid N+1 queries."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "series",
                "primary_goodreads_book_data",
                "primary_wikipedia_book_data",
            )
            .prefetch_related(
                "authors",
                "genres",
            )
        )

    @admin.display(description="Genres")
    def _genres_display(self, obj):
        """Display comma-separated list of genres for the book."""
        genres = [genre.name for genre in obj.genres.all()]
        return ", ".join(genres) if genres else "-"

    @admin.display(description="Goodreads Data")
    def _goodreads_data_link(self, obj):
        """Display link to Goodreads data admin page."""
        if obj.primary_goodreads_book_data:
            url = f"/admin/books/goodreadsbookdata/{obj.primary_goodreads_book_data.id}/change/"
            return format_html('<a href="{}">View</a>', url)
        return "-"

    @admin.display(description="Wikipedia Data")
    def _wikipedia_data_link(self, obj):
        """Display link to Wikipedia data admin page."""
        if obj.primary_wikipedia_book_data:
            url = f"/admin/books/wikipediabookdata/{obj.primary_wikipedia_book_data.id}/change/"
            return format_html('<a href="{}">View</a>', url)
        return "-"


@admin.register(models.GoodreadsBookData)
class GoodreadsBookDataAdmin(admin.ModelAdmin):
    """Admin interface for Goodreads book data records."""

    list_display = [
        "book",
        "goodreads_id",
        "average_rating",
        "ratings_count",
        "_goodreads_link",
        "_description_preview",
        "is_primary",
        "fetched_at",
        "updated_at",
    ]
    list_filter = ["is_primary", "fetched_at", "updated_at"]
    search_fields = ["book__name", "goodreads_id", "description"]
    raw_id_fields = ["book"]
    readonly_fields = ["fetched_at", "updated_at"]

    @admin.display(description="Goodreads URL")
    def _goodreads_link(self, obj):
        """Display clickable Goodreads URL."""
        url = obj.goodreads_book_url
        if url:
            return format_html('<a href="{}" target="_blank">View</a>', url)
        return "-"

    @admin.display(description="Description")
    def _description_preview(self, obj):
        """Display truncated description."""
        if obj.description:
            return Truncator(obj.description).words(10)
        return "-"


@admin.register(models.WikipediaBookData)
class WikipediaBookDataAdmin(admin.ModelAdmin):
    """Admin interface for Wikipedia book data records."""

    list_display = [
        "book",
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
        "book__name",
        "page_title",
        "wikidata_id",
        "primary_genre",
        "lookup_source",
    ]
    raw_id_fields = ["book"]
    readonly_fields = ["fetched_at", "updated_at"]

    @admin.display(description="All Genres")
    def _all_genres_preview(self, obj):
        """Display all genres from Wikipedia."""
        if obj.all_genres:
            return obj.all_genres
        return "-"

    @admin.display(description="Wikipedia Link")
    def _wikipedia_link(self, obj):
        """Display clickable Wikipedia URL."""
        url = obj.wikipedia_url
        if url:
            return format_html('<a href="{}" target="_blank">{}</a>', url, obj.page_title)
        return "-"


@admin.register(models.BookListMembership)
class BookListMembershipAdmin(admin.ModelAdmin):
    """Admin interface for BookListMembership records."""

    list_display = ["list", "book", "rank"]
    list_filter = ["list"]
    search_fields = ["book__name", "list__name"]
    raw_id_fields = ["list", "book"]
    ordering = ["list", "rank"]


@admin.register(models.ReadBook)
class ReadBookAdmin(admin.ModelAdmin):
    """Admin interface for ReadBook records."""

    list_display = ["user", "book_name", "goodreads_id", "created", "book_status"]
    list_filter = ["created"]
    search_fields = ["user__username", "user__email", "book__name", "goodreads_id"]
    raw_id_fields = ["user", "book"]
    readonly_fields = ["created"]
    ordering = ["-created"]

    @admin.display(description="Book")
    def book_name(self, obj):
        """Display book name or Goodreads ID if book is orphaned."""
        if obj.book:
            return obj.book.name
        return f"(orphaned) Goodreads:{obj.goodreads_id}"

    @admin.display(description="Status")
    def book_status(self, obj):
        """Show if the book record is connected or orphaned."""
        return "Connected" if obj.book else "Orphaned"


@admin.register(models.WantToReadBook)
class WantToReadBookAdmin(admin.ModelAdmin):
    """Admin interface for WantToReadBook records (reading list/backlog)."""

    list_display = ["user", "book_name", "goodreads_id", "created", "book_status"]
    list_filter = ["created"]
    search_fields = ["user__username", "user__email", "book__name", "goodreads_id"]
    raw_id_fields = ["user", "book"]
    readonly_fields = ["created"]
    ordering = ["-created"]

    @admin.display(description="Book")
    def book_name(self, obj):
        """Display book name or Goodreads ID if book is orphaned."""
        if obj.book:
            return obj.book.name
        return f"(orphaned) Goodreads:{obj.goodreads_id}"

    @admin.display(description="Status")
    def book_status(self, obj):
        """Show if the book record is connected or orphaned."""
        return "Connected" if obj.book else "Orphaned"
