"""
Book views for the multi-media platform.

This module contains Django class-based views for the books app,
following the same patterns established in the games app.
"""

from collections import defaultdict

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Lower
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import DetailView, ListView

from books import config, models
from books.forms import GoodreadsImportForm
from books.services.goodreads_importer import import_goodreads_csv
from core.cache_helpers import get_year_bounds
from core.mixins import HTMXPartialMixin, RobustPaginationMixin


class StaffOnlyMixin(UserPassesTestMixin):
    """
    Mixin that restricts access to staff/admin users only.

    Returns 404 (not 403) for non-staff users so the feature
    remains hidden until publicly launched.
    """

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        raise Http404("Page not found")


def _get_year_bounds():
    """Return cached global min/max publication years."""
    return get_year_bounds(
        model_class=models.Book,
        year_field="year_published",
        cache_key=config.CACHE_KEY_YEAR_STATS,
        cache_timeout=config.CACHE_TIMEOUT_24_HOURS,
        default_min=config.DEFAULT_MIN_YEAR,
    )


def _get_read_book_ids(user):
    """Return cached list of read book Goodreads IDs for a user."""
    cache_key = f"read_books_{user.id}"
    ids = cache.get(cache_key)
    if ids is None:
        ids = list(
            models.ReadBook.objects.filter(user=user).values_list(
                "goodreads_id", flat=True
            )
        )
        cache.set(cache_key, ids, 300)  # 5 minutes
    return ids


def invalidate_read_books_cache(user_id):
    """Invalidate the read books cache for a specific user."""
    cache.delete(f"read_books_{user_id}")


def _get_want_to_read_book_ids(user):
    """Return cached list of want-to-read book Goodreads IDs for a user."""
    cache_key = f"want_to_read_books_{user.id}"
    ids = cache.get(cache_key)
    if ids is None:
        ids = list(
            models.WantToReadBook.objects.filter(user=user).values_list(
                "goodreads_id", flat=True
            )
        )
        cache.set(cache_key, ids, 300)  # 5 minutes
    return ids


def invalidate_want_to_read_cache(user_id):
    """Invalidate the want-to-read books cache for a specific user."""
    cache.delete(f"want_to_read_books_{user_id}")


def _apply_read_filter(qs, user, read_param):
    """
    Filter queryset by read status.

    Args:
        qs: Book queryset
        user: Current user (may be AnonymousUser)
        read_param: "read", "unread", "want", or None

    Returns:
        Filtered queryset
    """
    if not user.is_authenticated or not read_param:
        return qs

    if read_param == "read":
        read_ids = _get_read_book_ids(user)
        qs = qs.filter(goodreads_id__in=read_ids)
    elif read_param == "unread":
        read_ids = _get_read_book_ids(user)
        qs = qs.exclude(goodreads_id__in=read_ids)
    elif read_param == "want":
        want_ids = _get_want_to_read_book_ids(user)
        qs = qs.filter(goodreads_id__in=want_ids)

    return qs


class BookHomePageView(StaffOnlyMixin, RobustPaginationMixin, ListView):
    """
    Main book listing page with filtering, search, and HTMX support.

    Supports:
    - Text search by name
    - Year range filtering
    - Genre filtering
    - Author filtering
    - Read status filtering (authenticated users)
    - HTMX partial responses for dynamic updates
    """

    model = models.Book
    template_name = "books/home.html"
    context_object_name = "books"
    paginate_by = 100
    paginate_orphans = 0

    def get_paginate_by(self, queryset):
        """Always use standard page size - client-side handles deep jumps."""
        return self.paginate_by

    def get_template_names(self):
        """Support HTMX partial responses."""
        is_htmx = (
            self.request.headers.get("HX-Request")
            or self.request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or self.request.GET.get("partial") == "true"
        )

        # Append mode for Load More - returns just book rows
        if self.request.GET.get("append") == "true":
            return ["books/includes/_book_list_append.html"]

        if is_htmx:
            # Targeted update for just the results container
            if self.request.headers.get("HX-Target") == "book-results-container":
                return ["books/includes/_book_list_results.html"]
            # Full content partial for pagination and initial loads
            return ["books/includes/_book_list_content.html"]
        return super().get_template_names()

    def get_queryset(self):
        qs = (
            models.Book.objects.with_relations()
            .with_read_status(self.request.user)
            .with_list_count()
        )

        # Basic search by name
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(name_normalized__icontains=q))

        # Year range filtering
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        if start:
            try:
                qs = qs.filter(year_published__gte=int(start))
            except (TypeError, ValueError):
                pass
        if end:
            try:
                qs = qs.filter(year_published__lte=int(end))
            except (TypeError, ValueError):
                pass

        # Genre filtering
        genres = self.request.GET.get("genres")
        if genres:
            try:
                genre_ids = [int(x) for x in genres.split(",") if x.strip()]
                if genre_ids:
                    qs = qs.filter(genres__id__in=genre_ids).distinct()
            except (TypeError, ValueError):
                pass

        # Author filtering
        authors = self.request.GET.get("authors")
        if authors:
            try:
                author_ids = [int(x) for x in authors.split(",") if x.strip()]
                if author_ids:
                    qs = qs.filter(authors__id__in=author_ids).distinct()
            except (TypeError, ValueError):
                pass

        # Series filtering
        series = self.request.GET.get("series")
        if series:
            try:
                series_id = int(series)
                qs = qs.filter(series_id=series_id)
            except (TypeError, ValueError):
                pass

        # Read status filtering (authenticated users only)
        read_param = self.request.GET.get("read")
        qs = _apply_read_filter(qs, self.request.user, read_param)

        # Sort order
        sort = self.request.GET.get("sort", "rank")
        direction = self.request.GET.get("dir", "asc")

        if sort == "name":
            if direction == "desc":
                qs = qs.order_by(Lower("name").desc())
            else:
                qs = qs.order_by(Lower("name"))
        elif sort == "year":
            if direction == "desc":
                qs = qs.order_by("-year_published", "rank")
            else:
                qs = qs.order_by("year_published", "rank")
        elif sort == "pages":
            if direction == "desc":
                qs = qs.order_by("-page_count", "rank")
            else:
                qs = qs.order_by("page_count", "rank")
        else:
            # Default: sort by rank
            if direction == "desc":
                qs = qs.order_by("-rank")
            else:
                qs = qs.order_by("rank")

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Year bounds for slider
        min_year, max_year = _get_year_bounds()
        context["min_year"] = min_year
        context["max_year"] = max_year

        # All genres for filtering (hierarchical)
        genres_cache_key = f"{config.CACHE_VERSION}:book_genres_list"
        genres_list = cache.get(genres_cache_key)
        if genres_list is None:
            genres_list = list(
                models.BookGenre.objects.order_by(
                    "level", "display_order", "name"
                ).values("id", "name", "slug", "level", "parent_id", "path")
            )
            cache.set(genres_cache_key, genres_list, config.CACHE_TIMEOUT_24_HOURS)
        context["genres"] = genres_list

        # All authors for filtering
        authors_cache_key = f"{config.CACHE_VERSION}:book_authors_list"
        authors_list = cache.get(authors_cache_key)
        if authors_list is None:
            authors_list = list(
                models.Author.objects.annotate(books_count=Count("books"))
                .filter(books_count__gt=0)
                .order_by(Lower("name"))
                .values("id", "name", "slug", "books_count")
            )
            cache.set(authors_cache_key, authors_list, config.CACHE_TIMEOUT_24_HOURS)
        context["authors"] = authors_list

        # Hero stats
        stats_cache_key = "bookpage_hero_stats"
        stats = cache.get(stats_cache_key)
        if stats is None:
            stats = {
                "book_count": models.Book.objects.count(),
                "author_count": models.Author.objects.count(),
            }
            cache.set(stats_cache_key, stats, config.CACHE_TIMEOUT_24_HOURS)
        context.update(stats)

        # Current filter state for UI
        context["current_q"] = self.request.GET.get("q", "")
        context["current_start"] = self.request.GET.get("start", "")
        context["current_end"] = self.request.GET.get("end", "")
        context["current_genres"] = self.request.GET.get("genres", "")
        context["current_authors"] = self.request.GET.get("authors", "")
        context["current_series"] = self.request.GET.get("series", "")
        context["current_read"] = self.request.GET.get("read", "")
        context["current_sort"] = self.request.GET.get("sort", "rank")
        context["current_dir"] = self.request.GET.get("dir", "asc")

        return context


class GoodreadsImportView(StaffOnlyMixin, View):
    """
    Import Goodreads CSV exports for read/want-to-read shelves.
    """

    template_name = "books/import.html"

    def get(self, request):
        form = GoodreadsImportForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = GoodreadsImportForm(request.POST, request.FILES)
        summary = None

        if form.is_valid():
            try:
                summary = import_goodreads_csv(form.cleaned_data["file"], request.user)
            except ValueError as exc:
                form.add_error("file", str(exc))

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "summary": summary,
            },
        )


class BookDetailView(StaffOnlyMixin, DetailView):
    """
    Detail view for a single book showing all metadata and list appearances.
    """

    model = models.Book
    template_name = "books/book_detail.html"
    context_object_name = "book"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        """Prefetch related data for the book detail page."""
        return models.Book.objects.select_related(
            "primary_wikipedia_book_data",
            "series",
        ).prefetch_related(
            "authors",
            "authors__parent",
            "genres",
            Prefetch(
                "lists",
                queryset=models.BookListMembership.objects.select_related(
                    "list__publisher",
                ).order_by(
                    "-list__year",
                    "list__publisher__name",
                    "list__name",
                    "rank",
                ),
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = context["book"]

        # Build grouped lists from prefetched data
        grouped = defaultdict(list)
        for membership in book.lists.all():
            list_type = membership.list.type
            label = _get_list_type_label(list_type)
            grouped[label].append(
                {
                    "id": membership.list.id,
                    "name": membership.list.name,
                    "publication": (
                        membership.list.publisher.name
                        if membership.list.publisher
                        else ""
                    ),
                    "publisher": membership.list.publisher,
                    "type": list_type,
                    "type_name": label,
                    "url": membership.list.url,
                    "year": membership.list.year,
                    "rank": membership.rank,
                }
            )

        # Order groups by type importance
        type_order = ["All time", "Decade", "Miscellaneous", "End of year"]
        sorted_grouped_lists = [(k, grouped[k]) for k in type_order if k in grouped]
        context["grouped_lists"] = sorted_grouped_lists

        # Check if current user has marked this book as read or want-to-read
        if self.request.user.is_authenticated and book.goodreads_id:
            context["is_read"] = models.ReadBook.objects.filter(
                user=self.request.user, goodreads_id=book.goodreads_id
            ).exists()
            context["is_want_to_read"] = models.WantToReadBook.objects.filter(
                user=self.request.user, goodreads_id=book.goodreads_id
            ).exists()

        # Other books in series
        if book.series:
            context["series_books"] = (
                models.Book.objects.filter(series=book.series)
                .exclude(id=book.id)
                .order_by("series_position", "year_published")[:10]
            )

        # Total book count for rank context
        total_book_count = cache.get("total_book_count")
        if total_book_count is None:
            total_book_count = models.Book.objects.count()
            cache.set(
                "total_book_count", total_book_count, config.CACHE_TIMEOUT_24_HOURS
            )
        context["total_book_count"] = total_book_count

        return context


class AuthorListView(StaffOnlyMixin, RobustPaginationMixin, HTMXPartialMixin, ListView):
    """
    List view for authors with book counts and hierarchy support.

    Displays root authors (those without parents) with their book counts
    and supports search and sorting.
    """

    model = models.Author
    template_name = "books/authors/author_list.html"
    context_object_name = "authors"
    paginate_by = 100
    paginate_orphans = 0
    htmx_partial_template = "books/authors/includes/_author_list_results.html"

    def get_template_names(self):
        """Support append mode for Load More."""
        if self.request.GET.get("append") == "true":
            return ["books/authors/includes/_author_list_append.html"]
        return super().get_template_names()

    def get_queryset(self):
        qs = (
            models.Author.objects.annotate(books_count=Count("books"))
            .filter(books_count__gt=0)
            .select_related("parent")
            .prefetch_related("subsidiaries")
        )

        # Search filter
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q))

        # Sort parameter
        sort = self.request.GET.get("sort", "books")
        direction = self.request.GET.get("dir", "desc")

        if sort == "name":
            if direction == "desc":
                qs = qs.order_by(Lower("name").desc())
            else:
                qs = qs.order_by(Lower("name"))
        else:
            # Default: sort by book count
            if direction == "desc":
                qs = qs.order_by("-books_count", Lower("name"))
            else:
                qs = qs.order_by("books_count", Lower("name"))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Stats
        stats_cache_key = "author_list_stats"
        stats = cache.get(stats_cache_key)
        if stats is None:
            stats = {
                "total_authors": models.Author.objects.count(),
                "authors_with_books": models.Author.objects.annotate(
                    books_count=Count("books")
                )
                .filter(books_count__gt=0)
                .count(),
            }
            cache.set(stats_cache_key, stats, config.CACHE_TIMEOUT_24_HOURS)
        context.update(stats)

        # Current filter state
        context["current_q"] = self.request.GET.get("q", "")
        context["current_sort"] = self.request.GET.get("sort", "books")
        context["current_dir"] = self.request.GET.get("dir", "desc")

        return context


class AuthorDetailView(StaffOnlyMixin, DetailView):
    """
    Detail view for an author showing biography and all their books.
    """

    model = models.Author
    template_name = "books/authors/author_detail.html"
    context_object_name = "author"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        """Prefetch books with optimized queryset."""
        books_queryset = models.Book.objects.prefetch_related(
            "authors",
            "authors__parent",
            "genres",
        ).order_by("rank")

        return models.Author.objects.prefetch_related(
            Prefetch(
                "subsidiaries",
                queryset=models.Author.objects.order_by("name"),
            ),
            Prefetch("books", queryset=books_queryset),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author = context["author"]

        # Use prefetched books data to avoid N+1 queries
        # books are already prefetched and sorted by rank in get_queryset()
        books_list = list(author.books.all())
        context["author_books"] = books_list
        context["books_count"] = len(books_list)

        # Best ranked book (already sorted by rank, so first is best)
        if books_list:
            context["best_book"] = books_list[0]

        # Check read status for authenticated users
        if self.request.user.is_authenticated:
            read_ids = set(_get_read_book_ids(self.request.user))
            context["read_count"] = sum(
                1 for book in books_list if book.goodreads_id in read_ids
            )

        return context


class ToggleReadBookView(StaffOnlyMixin, LoginRequiredMixin, View):
    """
    Cycle a book's status: none -> want -> read -> none.

    State transitions:
    - none (untracked) -> want to read
    - want to read -> read (removes want, adds read)
    - read -> none (removes read)

    States are mutually exclusive - a book cannot be both
    "want to read" and "read" simultaneously.
    """

    def post(self, request, goodreads_id):
        book = get_object_or_404(models.Book, goodreads_id=goodreads_id)

        # Check current state
        is_read = models.ReadBook.objects.filter(
            user=request.user, goodreads_id=goodreads_id
        ).exists()
        is_want_to_read = models.WantToReadBook.objects.filter(
            user=request.user, goodreads_id=goodreads_id
        ).exists()

        # Cycle through states: none -> want -> read -> none
        if is_read:
            # read -> none: Remove from read
            models.ReadBook.objects.filter(
                user=request.user, goodreads_id=goodreads_id
            ).delete()
            new_is_read = False
            new_is_want_to_read = False
        elif is_want_to_read:
            # want -> read: Remove from want, add to read
            models.WantToReadBook.objects.filter(
                user=request.user, goodreads_id=goodreads_id
            ).delete()
            models.ReadBook.objects.create(
                user=request.user, goodreads_id=goodreads_id, book=book
            )
            new_is_read = True
            new_is_want_to_read = False
        else:
            # none -> want: Add to want to read
            models.WantToReadBook.objects.create(
                user=request.user, goodreads_id=goodreads_id, book=book
            )
            new_is_read = False
            new_is_want_to_read = True

        # Invalidate caches
        invalidate_read_books_cache(request.user.id)
        invalidate_want_to_read_cache(request.user.id)

        # Preserve button size (large on book detail page, default elsewhere)
        size = request.GET.get("size")

        response = render(
            request,
            "books/includes/_read_button.html",
            {
                "book": book,
                "is_read": new_is_read,
                "is_want_to_read": new_is_want_to_read,
                "size": size,
                "just_toggled": True,
            },
        )
        # Prevent URL push for this HTMX action
        response["HX-Push-Url"] = "false"
        return response


class BookSearchView(StaffOnlyMixin, ListView):
    """
    Search endpoint for HTMX-powered book search.
    Returns just the search results for dynamic updates.
    """

    model = models.Book
    template_name = "books/includes/_book_search_results.html"
    context_object_name = "books"
    paginate_by = 20

    def get_queryset(self):
        qs = models.Book.objects.with_relations()

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(name_normalized__icontains=q))
        else:
            qs = qs.none()

        return qs.order_by("rank")[: self.paginate_by]


def _get_list_type_label(list_type):
    """Convert list type code to display label."""
    type_labels = {
        "AT": "All time",
        "DEC": "Decade",
        "EOY": "End of year",
        "MISC": "Miscellaneous",
    }
    return type_labels.get(list_type, "Other")
