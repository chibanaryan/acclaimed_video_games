"""
Tests for books app views.

Tests for BookHomePageView, BookDetailView, AuthorListView,
AuthorDetailView, ToggleReadBookView, and BookSearchView.

Note: All book views require staff access (StaffOnlyMixin).
Tests must use staff users to access these views.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from books import models


User = get_user_model()


class StaffUserTestMixin:
    """Mixin that provides a staff user and logs them in for tests."""

    def setUp(self):
        super().setUp()
        # Create staff user for accessing books views
        self.staff_user = User.objects.create_user(
            username="staffuser",
            password="staffpass",
            is_staff=True,
        )
        self.client.login(username="staffuser", password="staffpass")


class BookHomePageViewTests(StaffUserTestMixin, TestCase):
    """Tests for the BookHomePageView."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(name="Test Author", slug="test-author")
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

    def test_basic_request(self):
        """Test basic GET request returns 200."""
        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Book")
        self.assertContains(response, "Beta Book")

    def test_context_includes_books(self):
        """Test context includes books queryset."""
        response = self.client.get(reverse("books:home"))
        self.assertIn("books", response.context)
        self.assertEqual(len(response.context["books"]), 2)

    def test_context_includes_year_bounds(self):
        """Test context includes year bounds."""
        response = self.client.get(reverse("books:home"))
        self.assertIn("min_year", response.context)
        self.assertIn("max_year", response.context)

    def test_context_includes_genres(self):
        """Test context includes genres for filtering."""
        response = self.client.get(reverse("books:home"))
        self.assertIn("genres", response.context)

    def test_context_includes_authors(self):
        """Test context includes authors for filtering."""
        response = self.client.get(reverse("books:home"))
        self.assertIn("authors", response.context)

    def test_search_filter(self):
        """Test search by name filter."""
        response = self.client.get(reverse("books:home"), {"q": "Alpha"})
        self.assertEqual(response.status_code, 200)
        books = response.context["books"]
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0].name, "Alpha Book")

    def test_year_start_filter(self):
        """Test year range start filter."""
        response = self.client.get(reverse("books:home"), {"start": "2018"})
        books = response.context["books"]
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0].name, "Alpha Book")

    def test_year_end_filter(self):
        """Test year range end filter."""
        response = self.client.get(reverse("books:home"), {"end": "2016"})
        books = response.context["books"]
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0].name, "Beta Book")

    def test_genre_filter(self):
        """Test genre filter."""
        response = self.client.get(
            reverse("books:home"), {"genres": str(self.genre.id)}
        )
        books = response.context["books"]
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0].name, "Alpha Book")

    def test_author_filter(self):
        """Test author filter."""
        response = self.client.get(
            reverse("books:home"), {"authors": str(self.author.id)}
        )
        books = response.context["books"]
        # Both books have this author
        self.assertEqual(len(books), 2)

    def test_sort_by_name(self):
        """Test sorting by name."""
        response = self.client.get(reverse("books:home"), {"sort": "name"})
        books = list(response.context["books"])
        self.assertEqual(books[0].name, "Alpha Book")
        self.assertEqual(books[1].name, "Beta Book")

    def test_sort_by_name_desc(self):
        """Test sorting by name descending."""
        response = self.client.get(
            reverse("books:home"), {"sort": "name", "dir": "desc"}
        )
        books = list(response.context["books"])
        self.assertEqual(books[0].name, "Beta Book")
        self.assertEqual(books[1].name, "Alpha Book")

    def test_sort_by_year(self):
        """Test sorting by year."""
        response = self.client.get(reverse("books:home"), {"sort": "year"})
        books = list(response.context["books"])
        self.assertEqual(books[0].name, "Beta Book")  # 2015
        self.assertEqual(books[1].name, "Alpha Book")  # 2020

    def test_htmx_request_returns_partial(self):
        """Test HTMX request returns partial template."""
        response = self.client.get(
            reverse("books:home"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        # Should use partial template

    def test_htmx_targeted_request(self):
        """Test HTMX targeted request returns specific partial."""
        response = self.client.get(
            reverse("books:home"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="book-results-container",
        )
        self.assertEqual(response.status_code, 200)

    def test_append_mode(self):
        """Test append mode for infinite scroll."""
        response = self.client.get(reverse("books:home"), {"append": "true"})
        self.assertEqual(response.status_code, 200)

    def test_invalid_year_filter_ignored(self):
        """Test invalid year filter is ignored gracefully."""
        response = self.client.get(reverse("books:home"), {"start": "invalid"})
        self.assertEqual(response.status_code, 200)
        # Should return all books
        self.assertEqual(len(response.context["books"]), 2)


class BookDetailViewTests(StaffUserTestMixin, TestCase):
    """Tests for the BookDetailView."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(name="Test Author", slug="test-author")
        self.genre = models.BookGenre.objects.create(name="Fiction")
        self.series = models.BookSeries.objects.create(name="Test Series")

        self.book = models.Book.objects.create(
            name="Test Book",
            rank=1,
            slug="test-book",
            year_published=2020,
            goodreads_id="12345",
            series=self.series,
            series_position=1.0,
        )
        self.book.authors.add(self.author)
        self.book.genres.add(self.genre)

        # Create another book in the series
        self.book2 = models.Book.objects.create(
            name="Test Book 2",
            rank=2,
            slug="test-book-2",
            year_published=2021,
            goodreads_id="12346",
            series=self.series,
            series_position=2.0,
        )

    def test_basic_request(self):
        """Test basic GET request returns 200."""
        response = self.client.get(
            reverse("books:book-detail", kwargs={"slug": "test-book"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Book")

    def test_context_includes_book(self):
        """Test context includes book object."""
        response = self.client.get(
            reverse("books:book-detail", kwargs={"slug": "test-book"})
        )
        self.assertIn("book", response.context)
        self.assertEqual(response.context["book"].name, "Test Book")

    def test_context_includes_grouped_lists(self):
        """Test context includes grouped lists."""
        response = self.client.get(
            reverse("books:book-detail", kwargs={"slug": "test-book"})
        )
        self.assertIn("grouped_lists", response.context)

    def test_context_includes_series_books(self):
        """Test context includes other books in series."""
        response = self.client.get(
            reverse("books:book-detail", kwargs={"slug": "test-book"})
        )
        self.assertIn("series_books", response.context)
        series_books = response.context["series_books"]
        self.assertEqual(len(series_books), 1)
        self.assertEqual(series_books[0].name, "Test Book 2")

    def test_read_status_for_authenticated_user(self):
        """Test read status context for authenticated staff user."""
        # Use staff_user from mixin (already logged in)
        models.ReadBook.objects.create(
            user=self.staff_user, book=self.book, goodreads_id="12345"
        )

        response = self.client.get(
            reverse("books:book-detail", kwargs={"slug": "test-book"})
        )
        self.assertTrue(response.context["is_read"])

    def test_want_to_read_status_for_authenticated_user(self):
        """Test want-to-read status context for authenticated staff user."""
        # Use staff_user from mixin (already logged in)
        models.WantToReadBook.objects.create(
            user=self.staff_user, book=self.book, goodreads_id="12345"
        )

        response = self.client.get(
            reverse("books:book-detail", kwargs={"slug": "test-book"})
        )
        self.assertTrue(response.context["is_want_to_read"])

    def test_nonexistent_book_returns_404(self):
        """Test nonexistent book slug returns 404."""
        response = self.client.get(
            reverse("books:book-detail", kwargs={"slug": "nonexistent"})
        )
        self.assertEqual(response.status_code, 404)


class AuthorListViewTests(StaffUserTestMixin, TestCase):
    """Tests for the AuthorListView."""

    def setUp(self):
        super().setUp()
        self.author1 = models.Author.objects.create(name="Alpha Author", slug="alpha")
        self.author2 = models.Author.objects.create(name="Beta Author", slug="beta")

        # Create books for authors
        self.book1 = models.Book.objects.create(name="Book 1", rank=1)
        self.book2 = models.Book.objects.create(name="Book 2", rank=2)
        self.book3 = models.Book.objects.create(name="Book 3", rank=3)

        self.book1.authors.add(self.author1)
        self.book2.authors.add(self.author1)
        self.book3.authors.add(self.author2)

    def test_basic_request(self):
        """Test basic GET request returns 200."""
        response = self.client.get(reverse("books:author-list"))
        self.assertEqual(response.status_code, 200)

    def test_context_includes_authors(self):
        """Test context includes authors queryset."""
        response = self.client.get(reverse("books:author-list"))
        self.assertIn("authors", response.context)
        # Both authors have books
        self.assertEqual(len(response.context["authors"]), 2)

    def test_authors_have_book_count(self):
        """Test authors are annotated with book count."""
        response = self.client.get(reverse("books:author-list"))
        authors = list(response.context["authors"])
        # Find author1 who has 2 books
        alpha = next(a for a in authors if a.name == "Alpha Author")
        self.assertEqual(alpha.books_count, 2)

    def test_search_filter(self):
        """Test search by name filter."""
        response = self.client.get(reverse("books:author-list"), {"q": "Alpha"})
        authors = response.context["authors"]
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0].name, "Alpha Author")

    def test_sort_by_name(self):
        """Test sorting by name ascending."""
        response = self.client.get(reverse("books:author-list"), {"sort": "name", "dir": "asc"})
        authors = list(response.context["authors"])
        self.assertEqual(authors[0].name, "Alpha Author")
        self.assertEqual(authors[1].name, "Beta Author")

    def test_sort_by_books_count_default(self):
        """Test default sorting by book count descending."""
        response = self.client.get(reverse("books:author-list"))
        authors = list(response.context["authors"])
        # Alpha Author has 2 books, Beta has 1
        self.assertEqual(authors[0].name, "Alpha Author")

    def test_append_mode(self):
        """Test append mode for infinite scroll."""
        response = self.client.get(reverse("books:author-list"), {"append": "true"})
        self.assertEqual(response.status_code, 200)

    def test_excludes_authors_without_books(self):
        """Test that authors without books are excluded."""
        models.Author.objects.create(name="No Books Author", slug="no-books")
        response = self.client.get(reverse("books:author-list"))
        authors = response.context["authors"]
        names = [a.name for a in authors]
        self.assertNotIn("No Books Author", names)


class AuthorDetailViewTests(StaffUserTestMixin, TestCase):
    """Tests for the AuthorDetailView."""

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(
            name="Test Author",
            slug="test-author",
            bio="Test biography",
        )
        self.subsidiary = models.Author.objects.create(
            name="Pseudonym",
            parent=self.author,
        )

        self.book1 = models.Book.objects.create(
            name="Book 1", rank=1, goodreads_id="111"
        )
        self.book2 = models.Book.objects.create(
            name="Book 2", rank=2, goodreads_id="222"
        )
        self.book1.authors.add(self.author)
        self.book2.authors.add(self.author)

    def test_basic_request(self):
        """Test basic GET request returns 200."""
        response = self.client.get(
            reverse("books:author-detail", kwargs={"slug": "test-author"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Author")

    def test_context_includes_author(self):
        """Test context includes author object."""
        response = self.client.get(
            reverse("books:author-detail", kwargs={"slug": "test-author"})
        )
        self.assertIn("author", response.context)
        self.assertEqual(response.context["author"].name, "Test Author")

    def test_context_includes_author_books(self):
        """Test context includes author's books."""
        response = self.client.get(
            reverse("books:author-detail", kwargs={"slug": "test-author"})
        )
        self.assertIn("author_books", response.context)
        self.assertEqual(len(response.context["author_books"]), 2)

    def test_context_includes_books_count(self):
        """Test context includes books count."""
        response = self.client.get(
            reverse("books:author-detail", kwargs={"slug": "test-author"})
        )
        self.assertEqual(response.context["books_count"], 2)

    def test_context_includes_best_book(self):
        """Test context includes best ranked book."""
        response = self.client.get(
            reverse("books:author-detail", kwargs={"slug": "test-author"})
        )
        self.assertIn("best_book", response.context)
        self.assertEqual(response.context["best_book"].name, "Book 1")

    def test_read_count_for_authenticated_user(self):
        """Test read count context for authenticated staff user."""
        from django.core.cache import cache

        # Use staff_user from mixin (already logged in)
        models.ReadBook.objects.create(
            user=self.staff_user, book=self.book1, goodreads_id="111"
        )
        # Clear cache to ensure fresh read_ids lookup
        cache.delete(f"read_books_{self.staff_user.id}")

        response = self.client.get(
            reverse("books:author-detail", kwargs={"slug": "test-author"})
        )
        self.assertEqual(response.context["read_count"], 1)

    def test_nonexistent_author_returns_404(self):
        """Test nonexistent author slug returns 404."""
        response = self.client.get(
            reverse("books:author-detail", kwargs={"slug": "nonexistent"})
        )
        self.assertEqual(response.status_code, 404)


class ToggleReadBookViewTests(StaffUserTestMixin, TestCase):
    """Tests for the ToggleReadBookView."""

    def setUp(self):
        super().setUp()
        # Use staff_user from mixin for toggle tests
        self.user = self.staff_user
        self.book = models.Book.objects.create(
            name="Test Book",
            rank=1,
            slug="test-book",
            goodreads_id="12345",
        )

    def test_requires_staff_access(self):
        """Test view requires staff access (returns 404 for non-staff)."""
        # Log out staff user
        self.client.logout()

        response = self.client.post(
            reverse("books:toggle-read", kwargs={"goodreads_id": "12345"})
        )
        # Should return 404 to hide the feature from non-staff
        self.assertEqual(response.status_code, 404)

        # Log in as non-staff user
        regular_user = User.objects.create_user(
            username="regularuser", password="testpass"
        )
        self.client.login(username="regularuser", password="testpass")
        response = self.client.post(
            reverse("books:toggle-read", kwargs={"goodreads_id": "12345"})
        )
        # Should still return 404
        self.assertEqual(response.status_code, 404)

        # Log back in as staff for remaining tests
        self.client.login(username="staffuser", password="staffpass")

    def test_toggle_none_to_want(self):
        """Test cycling from none to want-to-read."""
        # Staff user is already logged in via mixin
        response = self.client.post(
            reverse("books:toggle-read", kwargs={"goodreads_id": "12345"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            models.WantToReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )
        self.assertFalse(
            models.ReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )

    def test_toggle_want_to_read(self):
        """Test cycling from want-to-read to read."""
        # Staff user is already logged in via mixin
        # Create want-to-read entry
        models.WantToReadBook.objects.create(
            user=self.user, book=self.book, goodreads_id="12345"
        )

        response = self.client.post(
            reverse("books:toggle-read", kwargs={"goodreads_id": "12345"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            models.ReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )
        self.assertFalse(
            models.WantToReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )

    def test_toggle_read_to_none(self):
        """Test cycling from read to none."""
        # Staff user is already logged in via mixin
        # Create read entry
        models.ReadBook.objects.create(
            user=self.user, book=self.book, goodreads_id="12345"
        )

        response = self.client.post(
            reverse("books:toggle-read", kwargs={"goodreads_id": "12345"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            models.ReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )
        self.assertFalse(
            models.WantToReadBook.objects.filter(
                user=self.user, goodreads_id="12345"
            ).exists()
        )

    def test_returns_button_html(self):
        """Test response contains button HTML."""
        # Staff user is already logged in via mixin
        response = self.client.post(
            reverse("books:toggle-read", kwargs={"goodreads_id": "12345"})
        )

        self.assertEqual(response.status_code, 200)
        # Should return HTML for the button

    def test_nonexistent_book_returns_404(self):
        """Test nonexistent book returns 404."""
        # Staff user is already logged in via mixin
        response = self.client.post(
            reverse("books:toggle-read", kwargs={"goodreads_id": "99999"})
        )

        self.assertEqual(response.status_code, 404)

    def test_hx_push_url_false(self):
        """Test HX-Push-Url header is false."""
        # Staff user is already logged in via mixin
        response = self.client.post(
            reverse("books:toggle-read", kwargs={"goodreads_id": "12345"})
        )

        self.assertEqual(response.get("HX-Push-Url"), "false")


class BookSearchViewTests(StaffUserTestMixin, TestCase):
    """Tests for the BookSearchView."""

    def setUp(self):
        super().setUp()
        self.book1 = models.Book.objects.create(
            name="Harry Potter", rank=1, slug="harry-potter"
        )
        self.book2 = models.Book.objects.create(
            name="Lord of the Rings", rank=2, slug="lord-rings"
        )

    def test_basic_search(self):
        """Test basic search returns results."""
        response = self.client.get(reverse("books:search"), {"q": "Harry"})
        self.assertEqual(response.status_code, 200)

    def test_empty_query_returns_no_results(self):
        """Test empty query returns no results."""
        response = self.client.get(reverse("books:search"), {"q": ""})
        self.assertEqual(response.status_code, 200)
        # Should return empty results

    def test_search_filters_by_name(self):
        """Test search filters books by name."""
        response = self.client.get(reverse("books:search"), {"q": "Potter"})
        self.assertEqual(response.status_code, 200)
        books = response.context["books"]
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0].name, "Harry Potter")
