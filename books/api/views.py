"""
Books API views.

These views follow the same patterns as games/api/views.py.
They will be fully functional once the books models are created in Phase 4.2.
"""

from datetime import datetime

from django.db import connection
from django.db.models import Count, F, Min, Prefetch
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView, Response

from games import config  # Shared cache config
from games import models as games_models
from games import utils  # Shared utilities

from .. import models
from . import serializers


@method_decorator(cache_page(60 * 15), name="dispatch")  # 15 min cache
class BookListView(ListAPIView):
    """
    List all books with filtering and search.

    Supports filtering by:
    - q: Search query (title search)
    - author: Author ID
    - start/end: Year range
    - genres: Comma-separated genre IDs
    """

    serializer_class = serializers.BookSummarySerializer
    # Build search fields based on database vendor
    search_fields = ["name_normalized__icontains", "name__icontains"]
    if connection.vendor == "postgresql":
        search_fields = [
            "name_normalized__search",
            "name__search",
        ] + search_fields
    filters = [
        utils.Filter(
            param="q",
            fields=search_fields,
        ),
        utils.Filter(param="author", fields=["authors__goodreads_id"], coerce=int),
        utils.Filter(param="start", fields=["year_published__gte"], coerce=int),
        utils.Filter(param="end", fields=["year_published__lte"], coerce=int),
    ]

    def get_queryset(self):
        qs = models.Book.objects.with_relations()

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        # Genre filtering
        genres = self.request.GET.get("genres")
        if genres:
            genre_ids = [int(x) for x in genres.split(",")]
            qs = qs.filter(genres__id__in=genre_ids)

        order_by = self.request.GET.get("order_by")
        if order_by:
            qs = qs.order_by(order_by)

        return qs.distinct()


@method_decorator(cache_page(60 * 30), name="dispatch")  # 30 min cache
class BookDetailView(RetrieveAPIView):
    """Get detailed book information including list appearances."""

    lookup_field = "slug"
    serializer_class = serializers.BookDetailSerializer
    queryset = models.Book.objects.select_related(
        "primary_goodreads_book_data",
        "primary_wikipedia_book_data",
    ).prefetch_related(
        Prefetch(
            "lists",
            queryset=models.BookListMembership.objects.select_related(
                "list__publisher",
            ),
        )
    )


@method_decorator(cache_page(60 * 30), name="dispatch")  # 30 min cache
class AuthorDetailView(RetrieveAPIView):
    """API endpoint for author details."""

    lookup_field = "slug"
    serializer_class = serializers.AuthorSerializer
    queryset = models.Author.objects.all()


class AuthorListView(ListAPIView):
    """API endpoint for listing authors."""

    serializer_class = serializers.AuthorSerializer
    search_fields = ["name__icontains"]
    if connection.vendor == "postgresql":
        search_fields = ["name__search"] + search_fields
    filters = [
        utils.Filter(
            param="q",
            fields=search_fields,
        )
    ]

    def get_queryset(self):
        qs = (
            models.Author.objects.annotate(
                books_count=Count("books"),
            )
            .filter(books_count__gt=0)  # Only show authors with books
            .order_by(Lower("name"))
            .distinct()
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        return qs


class AuthorDetailByIdView(RetrieveAPIView):
    """API endpoint for author details by GoodReads ID."""

    lookup_field = "goodreads_id"
    serializer_class = serializers.AuthorSerializer
    queryset = models.Author.objects.annotate(
        books_count=Count("books"),
    )


class BookListListView(ListAPIView):
    """List all book lists/rankings."""

    serializer_class = serializers.BookListSerializer
    filters = [
        utils.Filter(param="publisher", fields=["publisher_id"], coerce=int),
        utils.Filter(param="year", fields=["year"], coerce=int),
        utils.Filter(param="type", fields=["type"], coerce=str),
    ]

    def get_queryset(self):
        # Use games.List with media_type='B' for books
        qs = games_models.List.objects.filter(
            media_type="B"
        ).select_related(
            "publisher",
        ).order_by(
            "publisher",
            "year",
            "name",
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        return qs


@method_decorator(cache_page(config.CACHE_TIMEOUT_1_HOUR), name="dispatch")
class BookMetaView(APIView):
    """
    Metadata about the books database.

    Returns counts, year ranges, and statistics.
    """

    def get(self, *args, **kwargs):
        data = {}

        # Book lists (games.List with media_type='B')
        book_lists = games_models.List.objects.filter(media_type="B")
        list_year_counts = (
            book_lists.order_by("year")
            .values("year")
            .annotate(count=Count("id"))
            .values("year", "count")
        )

        data["lists"] = {
            "years": list_year_counts,
            "total_count": book_lists.count(),
        }

        # Books
        book_stats = models.Book.objects.aggregate(
            min_year=Min("year_published"),
        )
        min_year = book_stats["min_year"] or 1900
        max_year = datetime.today().year
        all_years = range(min_year, max_year)
        year_count_map = {
            entry["year_published"]: entry["count"]
            for entry in models.Book.objects.values("year_published")
            .annotate(count=Count("id"))
            .order_by("year_published")
        }

        all_years_with_counts = [
            {"year": x, "count": year_count_map.get(x, 0)} for x in all_years
        ]

        # Calculate counts for each decade
        from django.db.models.functions import Floor

        decades_data = (
            models.Book.objects.annotate(
                decade_start=Floor(F("year_published") / 10) * 10
            )
            .values("decade_start")
            .annotate(count=Count("id"))
            .order_by("decade_start")
        )

        decades_with_counts = [
            {
                "decade": (
                    f"{item['decade_start']}-{str(item['decade_start'] + 9)[2:4]}"
                ),
                "count": item["count"],
            }
            for item in decades_data
        ]

        data["books"] = {
            "years": all_years_with_counts,
            "decades": decades_with_counts,
        }

        # Authors
        data["authors"] = {
            "total_count": models.Author.objects.count(),
        }

        return Response(data)


@method_decorator(cache_page(config.CACHE_TIMEOUT_24_HOURS), name="dispatch")
class BookGenreListView(ListAPIView):
    """List all book genres (flat list with hierarchy metadata)."""

    serializer_class = serializers.BookGenreSerializer
    queryset = models.BookGenre.objects.all().order_by("level", "display_order", "name")


@method_decorator(cache_page(config.CACHE_TIMEOUT_24_HOURS), name="dispatch")
class BookGenreTreeView(ListAPIView):
    """List book genres as hierarchical tree structure."""

    serializer_class = serializers.BookGenreTreeSerializer

    def get_queryset(self):
        """Return only root categories for tree building."""
        return models.BookGenre.objects.filter(parent=None).order_by(
            "display_order", "name"
        )


class BookSearchAPIView(APIView):
    """
    API endpoint for navbar search - returns JSON list of books matching query.
    """

    def get(self, request):
        from django.http import JsonResponse

        q = request.GET.get("q", "").strip()
        limit = int(request.GET.get("limit", 5))

        if len(q) < 2:
            return JsonResponse({"results": [], "count": 0})

        books = (
            models.Book.objects.filter(name__icontains=q)
            .select_related("primary_goodreads_book_data")
            .only(
                "id",
                "name",
                "slug",
                "year_published",
                "rank",
                "primary_goodreads_book_data__cover_image_url",
            )
            .order_by("rank")[:limit]
        )

        results = []
        for book in books:
            results.append(
                {
                    "id": book.id,
                    "name": book.name,
                    "slug": book.slug,
                    "year_published": book.year_published,
                    "rank": book.rank,
                    "cover_image_url": book.thumbnail,
                }
            )

        return JsonResponse({"results": results, "count": len(results)})


class UnifiedBookSearchView(APIView):
    """
    Unified search endpoint for navbar - returns both authors and books.
    """

    def get(self, request):
        from django.http import JsonResponse

        q = request.GET.get("q", "").strip()
        book_limit = int(request.GET.get("book_limit", 5))
        author_limit = int(request.GET.get("author_limit", 3))

        if len(q) < 2:
            return JsonResponse({"authors": [], "books": []})

        # Search authors
        authors = (
            models.Author.objects.filter(name__icontains=q)
            .annotate(books_count=Count("books"))
            .filter(books_count__gt=0)
            .order_by("-books_count")[:author_limit]
        )

        author_results = [
            {
                "id": author.id,
                "name": author.name,
                "slug": author.slug,
                "books_count": author.books_count,
            }
            for author in authors
        ]

        # Search books
        books = (
            models.Book.objects.filter(name__icontains=q)
            .select_related("primary_goodreads_book_data")
            .only(
                "id",
                "name",
                "slug",
                "year_published",
                "rank",
                "primary_goodreads_book_data__cover_image_url",
            )
            .order_by("rank")[:book_limit]
        )

        book_results = [
            {
                "id": book.id,
                "name": book.name,
                "slug": book.slug,
                "year_published": book.year_published,
                "rank": book.rank,
                "cover_image_url": book.thumbnail,
            }
            for book in books
        ]

        return JsonResponse(
            {
                "authors": author_results,
                "books": book_results,
            }
        )


def _compute_book_data_version():
    """
    Compute a version hash for cache invalidation.

    Uses schema version, max modified timestamp of books, and genre count.
    """
    import hashlib

    SCHEMA_VERSION = "1"

    latest_book = models.Book.objects.order_by("-modified").first()
    book_modified = latest_book.modified.isoformat() if latest_book else ""

    genre_count = models.BookGenre.objects.count()

    version_string = f"{SCHEMA_VERSION}:{book_modified}:{genre_count}"
    return hashlib.md5(version_string.encode()).hexdigest()[:12]


@method_decorator(cache_page(config.CACHE_TIMEOUT_1_HOUR), name="dispatch")
class BookDataVersionView(APIView):
    """Lightweight endpoint returning only the data version hash."""

    def get(self, request):
        return Response({"version": _compute_book_data_version()})


@method_decorator(cache_page(config.CACHE_TIMEOUT_1_HOUR), name="dispatch")
class BookAllDataView(APIView):
    """
    Complete book data endpoint for client-side filtering.

    Returns all books with minimal payload for efficient client-side filtering.
    """

    def get(self, request):
        version = _compute_book_data_version()

        # Fetch all books with required relations
        books = (
            models.Book.objects.select_related(
                "primary_goodreads_book_data",
            )
            .prefetch_related(
                "authors",
                "genres",
            )
            .with_list_count()
            .order_by("rank")
        )

        # Build books list with minimal field names
        books_data = []
        authors_dict = {}
        genres_data = []

        for book in books:
            # Collect author IDs
            author_ids = []
            for author in book.authors.all():
                author_ids.append(author.id)
                if author.id not in authors_dict:
                    authors_dict[author.id] = {
                        "n": author.name,
                        "s": author.slug,
                    }

            # Collect genre IDs
            genre_ids = [g.id for g in book.genres.all()]

            # Get cover image from primary GoodReads data
            cover_image = None
            if book.primary_goodreads_book_data:
                cover_image = book.primary_goodreads_book_data.cover_image_url

            books_data.append(
                {
                    "id": book.id,
                    "gi": book.goodreads_id,  # GoodReads ID for read book tracking
                    "n": book.name,
                    "s": book.slug,
                    "r": book.rank,
                    "y": book.year_published,
                    "c": cover_image,  # Cover image URL
                    "au": author_ids,  # Author IDs
                    "g": genre_ids,  # Genre IDs
                    "lc": book.list_count,  # List count
                    "pc": book.page_count,  # Page count
                }
            )

        # Build genre hierarchy
        all_genres = models.BookGenre.objects.prefetch_related("children").all()
        for genre in all_genres:
            descendant_ids = genre.get_descendant_ids(include_self=False)
            genres_data.append(
                {
                    "id": genre.id,
                    "n": genre.name,
                    "s": genre.slug,
                    "p": genre.parent_id,
                    "l": genre.level,
                    "d": descendant_ids,
                }
            )

        return Response(
            {
                "version": version,
                "data": {
                    "books": books_data,
                    "authors": authors_dict,
                    "genres": genres_data,
                },
            }
        )


class ReadBookListCreateView(APIView):
    """
    List read books for current user (GET).
    Mark a book as read (POST).
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all read books for current user."""
        read_books = models.ReadBook.objects.filter(user=request.user).select_related(
            "book"
        )

        data = [
            {
                "id": rb.id,
                "book_id": rb.book_id,
                "goodreads_id": rb.goodreads_id,
                "created": rb.created.isoformat(),
            }
            for rb in read_books
        ]
        return Response({"read_books": data, "count": len(data)})

    def post(self, request):
        """Mark a book as read."""
        goodreads_id = request.data.get("goodreads_id")
        if not goodreads_id:
            return Response(
                {"error": "goodreads_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the book
        book = get_object_or_404(models.Book, goodreads_id=goodreads_id)

        # Create or get the ReadBook record
        read_book, created = models.ReadBook.objects.get_or_create(
            user=request.user,
            goodreads_id=goodreads_id,
            defaults={"book": book},
        )

        # If the book was on want-to-read, remove it
        models.WantToReadBook.objects.filter(
            user=request.user, goodreads_id=goodreads_id
        ).delete()

        return Response(
            {
                "id": read_book.id,
                "book_id": read_book.book_id,
                "goodreads_id": read_book.goodreads_id,
                "created": read_book.created.isoformat(),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ReadBookDeleteView(APIView):
    """Remove a book from read list."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, goodreads_id):
        """Unmark a book as read."""
        deleted, _ = models.ReadBook.objects.filter(
            user=request.user, goodreads_id=goodreads_id
        ).delete()

        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"error": "Book not found in read list."},
            status=status.HTTP_404_NOT_FOUND,
        )


class WantToReadBookListCreateView(APIView):
    """
    List want-to-read books for current user (GET).
    Add a book to want-to-read list (POST).
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all want-to-read books for current user."""
        want_books = models.WantToReadBook.objects.filter(
            user=request.user
        ).select_related("book")

        data = [
            {
                "id": wb.id,
                "book_id": wb.book_id,
                "goodreads_id": wb.goodreads_id,
                "created": wb.created.isoformat(),
            }
            for wb in want_books
        ]
        return Response({"want_to_read_books": data, "count": len(data)})

    def post(self, request):
        """Add a book to want-to-read list."""
        goodreads_id = request.data.get("goodreads_id")
        if not goodreads_id:
            return Response(
                {"error": "goodreads_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if already read
        if models.ReadBook.objects.filter(
            user=request.user, goodreads_id=goodreads_id
        ).exists():
            return Response(
                {"error": "Book is already marked as read."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the book
        book = get_object_or_404(models.Book, goodreads_id=goodreads_id)

        # Create or get the WantToReadBook record
        want_book, created = models.WantToReadBook.objects.get_or_create(
            user=request.user,
            goodreads_id=goodreads_id,
            defaults={"book": book},
        )

        return Response(
            {
                "id": want_book.id,
                "book_id": want_book.book_id,
                "goodreads_id": want_book.goodreads_id,
                "created": want_book.created.isoformat(),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class WantToReadBookDeleteView(APIView):
    """Remove a book from want-to-read list."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, goodreads_id):
        """Remove a book from want-to-read list."""
        deleted, _ = models.WantToReadBook.objects.filter(
            user=request.user, goodreads_id=goodreads_id
        ).delete()

        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"error": "Book not found in want-to-read list."},
            status=status.HTTP_404_NOT_FOUND,
        )
