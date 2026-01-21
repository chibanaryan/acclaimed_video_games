"""
Tests for books app API endpoints.

Tests for BookListView, BookDetailView, AuthorListView, AuthorDetailView,
BookMetaView, BookGenreListView, ReadBookListCreateView, and other API views.

Note: All book API views require staff access (IsStaffOrHide permission).
Tests must use staff users to access these endpoints.
"""

import importlib
import unittest
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from books import models


User = get_user_model()


class StaffAPITestMixin:
    """Mixin that provides a staff user and authenticates them for API tests."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        # Create staff user for accessing books API
        self.staff_user = User.objects.create_user(
            username="staffuser",
            password="staffpass",
            is_staff=True,
        )
        # Use force_authenticate for reliable DRF authentication
        self.client.force_authenticate(user=self.staff_user)


class BookListAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookListView API endpoint."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(
            name="Test Author", slug="test-author", goodreads_id="100"
        )
        self.genre = models.BookGenre.objects.create(name="Fiction")

        self.book1 = models.Book.objects.create(
            name="Alpha Book",
            rank=1,
            slug="alpha-book",
            year_published=2020,
            goodreads_id="111",
        )
        self.book1.authors.add(self.author)
        self.book1.genres.add(self.genre)

        self.book2 = models.Book.objects.create(
            name="Beta Book",
            rank=2,
            slug="beta-book",
            year_published=2015,
            goodreads_id="222",
        )
        self.book2.authors.add(self.author)

    def test_list_books(self):
        """Test GET /api/books/ returns books."""
        response = self.client.get("/api/books/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), 2)

    def test_filter_by_search_query(self):
        """Test filtering by search query."""
        response = self.client.get("/api/books/", {"q": "Alpha"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Alpha Book")

    def test_filter_by_year_start(self):
        """Test filtering by year start."""
        response = self.client.get("/api/books/", {"start": 2018})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Alpha Book")

    def test_filter_by_year_end(self):
        """Test filtering by year end."""
        response = self.client.get("/api/books/", {"end": 2016})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Beta Book")

    def test_filter_by_genres(self):
        """Test filtering by genres."""
        response = self.client.get("/api/books/", {"genres": str(self.genre.id)})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Alpha Book")

    def test_order_by_parameter(self):
        """Test order_by parameter."""
        response = self.client.get("/api/books/", {"order_by": "-year_published"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["results"][0]["name"], "Alpha Book")
        self.assertEqual(data["results"][1]["name"], "Beta Book")


class BookDetailAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookDetailView API endpoint."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(
            name="Test Author", slug="test-author"
        )
        self.book = models.Book.objects.create(
            name="Test Book",
            rank=1,
            slug="test-book",
            year_published=2020,
            goodreads_id="12345",
        )
        self.book.authors.add(self.author)

    def test_get_book_detail(self):
        """Test GET /api/books/<slug>/ returns book details."""
        response = self.client.get("/api/books/test-book/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Test Book")
        self.assertEqual(data["slug"], "test-book")

    def test_nonexistent_book_returns_404(self):
        """Test GET for nonexistent book returns 404."""
        response = self.client.get("/api/books/nonexistent/")
        self.assertEqual(response.status_code, 404)


class AuthorListAPITests(StaffAPITestMixin, TestCase):
    """Tests for the AuthorListView API endpoint."""

    def setUp(self):
        super().setUp()
        self.author1 = models.Author.objects.create(name="Alpha Author", slug="alpha")
        self.author2 = models.Author.objects.create(name="Beta Author", slug="beta")

        self.book = models.Book.objects.create(name="Test Book", rank=1)
        self.book.authors.add(self.author1)

    def test_list_authors(self):
        """Test GET /api/books/authors/ returns authors with books."""
        response = self.client.get("/api/books/authors/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Only author1 has books
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Alpha Author")

    def test_filter_by_search_query(self):
        """Test filtering by search query."""
        response = self.client.get("/api/books/authors/", {"q": "Alpha"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)


class AuthorDetailAPITests(StaffAPITestMixin, TestCase):
    """Tests for the AuthorDetailView API endpoint."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(
            name="Test Author",
            slug="test-author",
            bio="Test biography",
        )

    def test_get_author_detail(self):
        """Test GET /api/books/authors/<slug>/ returns author details."""
        response = self.client.get("/api/books/authors/test-author/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Test Author")

    def test_nonexistent_author_returns_404(self):
        """Test GET for nonexistent author returns 404."""
        response = self.client.get("/api/books/authors/nonexistent/")
        self.assertEqual(response.status_code, 404)


class AuthorDetailByIdAPITests(StaffAPITestMixin, TestCase):
    """Tests for the AuthorDetailByIdView API endpoint."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(
            name="Test Author",
            slug="test-author",
            goodreads_id="12345",
        )

    def test_get_author_by_goodreads_id(self):
        """Test GET /api/books/author-aliases/<goodreads_id>/ returns author."""
        response = self.client.get("/api/books/authors/by-id/12345/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Test Author")

    def test_nonexistent_id_returns_404(self):
        """Test GET for nonexistent ID returns 404."""
        response = self.client.get("/api/books/authors/by-id/99999/")
        self.assertEqual(response.status_code, 404)


class BookListListAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookListListView API endpoint."""

    def setUp(self):
        super().setUp()
        self.publication = models.BookPublication.objects.create(name="Test Pub")
        self.book_list = models.BookList.objects.create(
            publisher=self.publication,
            name="Best Books 2024",
            year=2024,
            type="A",
        )

    def test_list_book_lists(self):
        """Test GET /api/books/lists/ returns book lists."""
        response = self.client.get("/api/books/lists/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Best Books 2024")

    def test_filter_by_year(self):
        """Test filtering by year."""
        response = self.client.get("/api/books/lists/", {"year": 2024})
        self.assertEqual(response.status_code, 200)


class BookMetaAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookMetaView API endpoint."""

    def setUp(self):
        super().setUp()
        self.publication = models.BookPublication.objects.create(name="Test Pub")
        models.BookList.objects.create(
            publisher=self.publication,
            name="Best Books",
            year=2024,
            type="A",
        )
        models.Book.objects.create(name="Test Book", rank=1, year_published=2020)
        models.Author.objects.create(name="Test Author", slug="test")

    def test_get_meta(self):
        """Test GET /api/books/meta/ returns metadata."""
        response = self.client.get("/api/books/meta/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check structure
        self.assertIn("lists", data)
        self.assertIn("books", data)
        self.assertIn("authors", data)

        # Check lists data
        self.assertIn("years", data["lists"])
        self.assertIn("total_count", data["lists"])

        # Check books data
        self.assertIn("years", data["books"])
        self.assertIn("decades", data["books"])

        # Check authors data
        self.assertIn("total_count", data["authors"])


class BookGenreListAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookGenreListView API endpoint."""

    def setUp(self):
        super().setUp()
        self.fiction = models.BookGenre.objects.create(name="Fiction")
        self.scifi = models.BookGenre.objects.create(
            name="Science Fiction", parent=self.fiction
        )

    def test_list_genres(self):
        """Test GET /api/books/genres/ returns genres."""
        response = self.client.get("/api/books/genres/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)


class BookGenreTreeAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookGenreTreeView API endpoint."""

    def setUp(self):
        super().setUp()
        self.fiction = models.BookGenre.objects.create(name="Fiction")
        self.scifi = models.BookGenre.objects.create(
            name="Science Fiction", parent=self.fiction
        )

    def test_get_genre_tree(self):
        """Test GET /api/books/genres/tree/ returns tree structure."""
        response = self.client.get("/api/books/genres/tree/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Should only return root genres
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Fiction")


class BookSearchAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookSearchAPIView."""

    def setUp(self):
        super().setUp()
        self.book = models.Book.objects.create(
            name="Harry Potter", rank=1, slug="harry-potter"
        )

    def test_search_books(self):
        """Test GET /api/books/search/ returns matching books."""
        response = self.client.get("/api/books/search/", {"q": "Harry"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Harry Potter")

    def test_short_query_returns_empty(self):
        """Test short query returns empty results."""
        response = self.client.get("/api/books/search/", {"q": "H"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)


class UnifiedBookSearchAPITests(StaffAPITestMixin, TestCase):
    """Tests for the UnifiedBookSearchView."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(name="J.K. Rowling", slug="jk")
        self.book = models.Book.objects.create(
            name="Harry Potter", rank=1, slug="harry-potter"
        )
        self.book.authors.add(self.author)

    def test_unified_search(self):
        """Test GET /api/books/unified-search/ returns authors and books."""
        response = self.client.get("/api/books/unified-search/", {"q": "Harry"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("authors", data)
        self.assertIn("books", data)

    def test_short_query_returns_empty(self):
        """Test short query returns empty results."""
        response = self.client.get("/api/books/unified-search/", {"q": "H"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["authors"], [])
        self.assertEqual(data["books"], [])


class BookDataVersionAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookDataVersionView."""

    def setUp(self):
        super().setUp()
        models.Book.objects.create(name="Test Book", rank=1)

    def test_get_version(self):
        """Test GET /api/books/data-version/ returns version hash."""
        response = self.client.get("/api/books/version/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("version", data)
        # Version should be a 12-character hash
        self.assertEqual(len(data["version"]), 12)


@unittest.skip("GoodreadsBookData model removed")
class BookAllDataAPITests(StaffAPITestMixin, TestCase):
    """Tests for the BookAllDataView."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(name="Test Author", slug="test")
        self.genre = models.BookGenre.objects.create(name="Fiction")
        self.book = models.Book.objects.create(
            name="Test Book", rank=1, goodreads_id="123"
        )
        self.book.authors.add(self.author)
        self.book.genres.add(self.genre)
        self.goodreads_data = models.GoodreadsBookData.objects.create(
            book=self.book,
            goodreads_id="123",
            cover_image_url="https://example.com/cover.jpg",
            is_primary=True,
        )
        self.book.primary_goodreads_book_data = self.goodreads_data
        self.book.save()

    def test_get_all_data(self):
        """Test GET /api/books/all/ returns complete data."""
        response = self.client.get("/api/books/all/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("version", data)
        self.assertIn("data", data)
        self.assertIn("books", data["data"])
        self.assertIn("authors", data["data"])
        self.assertIn("genres", data["data"])

        # Check book structure
        books = data["data"]["books"]
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]["n"], "Test Book")
        self.assertEqual(books[0]["c"], "https://example.com/cover.jpg")


class ReadBookAPITests(StaffAPITestMixin, TestCase):
    """Tests for the ReadBookListCreateView and ReadBookDeleteView."""

    def setUp(self):
        super().setUp()
        # Use staff user for read book tests (already logged in via mixin)
        self.user = self.staff_user
        self.book = models.Book.objects.create(
            name="Test Book", rank=1, goodreads_id="12345"
        )

    def test_list_read_books_requires_staff(self):
        """Test GET /api/books/read-books/ requires staff access."""
        # Clear authentication
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/books/read-books/")
        # Non-staff/unauthenticated gets 404 (hidden feature)
        self.assertEqual(response.status_code, 404)

        # Authenticate as non-staff user
        regular_user = User.objects.create_user(
            username="regularuser", password="testpass"
        )
        self.client.force_authenticate(user=regular_user)
        response = self.client.get("/api/books/read-books/")
        self.assertEqual(response.status_code, 404)

        # Re-authenticate as staff
        self.client.force_authenticate(user=self.staff_user)

    def test_list_read_books_authenticated(self):
        """Test GET /api/books/read-books/ returns user's read books."""
        # Staff user is already logged in via mixin
        models.ReadBook.objects.create(
            user=self.user, book=self.book, goodreads_id="12345"
        )

        response = self.client.get("/api/books/read-books/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)

    def test_mark_book_as_read(self):
        """Test POST /api/books/read-books/ marks book as read."""
        # Staff user is already logged in via mixin
        response = self.client.post(
            "/api/books/read-books/", {"goodreads_id": "12345"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            models.ReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )

    def test_mark_book_as_read_requires_goodreads_id(self):
        """Test POST without goodreads_id returns 400."""
        response = self.client.post("/api/books/read-books/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "goodreads_id is required.")

    def test_mark_book_as_read_removes_want_to_read(self):
        """Test marking as read removes from want-to-read."""
        # Staff user is already logged in via mixin
        models.WantToReadBook.objects.create(
            user=self.user, book=self.book, goodreads_id="12345"
        )

        response = self.client.post(
            "/api/books/read-books/", {"goodreads_id": "12345"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(
            models.WantToReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )

    def test_unmark_book_as_read(self):
        """Test DELETE /api/books/read-books/<id>/ removes read status."""
        # Staff user is already logged in via mixin
        models.ReadBook.objects.create(
            user=self.user, book=self.book, goodreads_id="12345"
        )

        response = self.client.delete("/api/books/read-books/12345/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            models.ReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )

    def test_unmark_nonexistent_returns_404(self):
        """Test DELETE for nonexistent read book returns 404."""
        # Staff user is already logged in via mixin
        response = self.client.delete("/api/books/read-books/99999/")
        self.assertEqual(response.status_code, 404)


class WantToReadBookAPITests(StaffAPITestMixin, TestCase):
    """Tests for the WantToReadBookListCreateView and WantToReadBookDeleteView."""

    def setUp(self):
        super().setUp()
        # Use staff user for want to read tests (already logged in via mixin)
        self.user = self.staff_user
        self.book = models.Book.objects.create(
            name="Test Book", rank=1, goodreads_id="12345"
        )

    def test_list_want_to_read_requires_staff(self):
        """Test GET /api/books/want-to-read/ requires staff access."""
        # Clear authentication
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/books/want-to-read/")
        # Non-staff/unauthenticated gets 404 (hidden feature)
        self.assertEqual(response.status_code, 404)

        # Authenticate as non-staff user
        regular_user = User.objects.create_user(
            username="regularuser", password="testpass"
        )
        self.client.force_authenticate(user=regular_user)
        response = self.client.get("/api/books/want-to-read/")
        self.assertEqual(response.status_code, 404)

        # Re-authenticate as staff
        self.client.force_authenticate(user=self.staff_user)

    def test_list_want_to_read_authenticated(self):
        """Test GET /api/books/want-to-read/ returns user's want-to-read books."""
        # Staff user is already logged in via mixin
        models.WantToReadBook.objects.create(
            user=self.user, book=self.book, goodreads_id="12345"
        )

        response = self.client.get("/api/books/want-to-read/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)

    def test_add_to_want_to_read(self):
        """Test POST /api/books/want-to-read/ adds book to list."""
        # Staff user is already logged in via mixin
        response = self.client.post(
            "/api/books/want-to-read/", {"goodreads_id": "12345"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            models.WantToReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )

    def test_add_to_want_to_read_requires_goodreads_id(self):
        """Test POST without goodreads_id returns 400."""
        response = self.client.post("/api/books/want-to-read/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "goodreads_id is required.")

    def test_add_already_read_book_fails(self):
        """Test adding a read book to want-to-read fails."""
        # Staff user is already logged in via mixin
        models.ReadBook.objects.create(
            user=self.user, book=self.book, goodreads_id="12345"
        )

        response = self.client.post(
            "/api/books/want-to-read/", {"goodreads_id": "12345"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_remove_from_want_to_read(self):
        """Test DELETE /api/books/want-to-read/<id>/ removes from list."""
        # Staff user is already logged in via mixin
        models.WantToReadBook.objects.create(
            user=self.user, book=self.book, goodreads_id="12345"
        )

        response = self.client.delete("/api/books/want-to-read/12345/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            models.WantToReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )

    def test_remove_nonexistent_returns_404(self):
        """Test DELETE for nonexistent want-to-read book returns 404."""
        # Staff user is already logged in via mixin
        response = self.client.delete("/api/books/want-to-read/99999/")
        self.assertEqual(response.status_code, 404)


class PostgresSearchFieldsTests(TestCase):
    """Tests for PostgreSQL-specific search fields."""

    def test_postgres_search_fields_added(self):
        """Test postgres vendor adds full-text search fields."""
        import books.api.views as views

        with mock.patch("django.db.connection.vendor", "postgresql"):
            importlib.reload(views)
            self.assertIn("name__search", views.BookListView.search_fields)
            self.assertIn("name__search", views.AuthorListView.search_fields)

        importlib.reload(views)
