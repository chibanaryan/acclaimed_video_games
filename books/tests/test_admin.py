"""
Basic tests for books app admin configuration.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase

from books import models
from books.admin import (
    AuthorAdmin,
    BookAdmin,
    BookGenreAdmin,
    BookListMembershipAdmin,
    BookSeriesAdmin,
    ReadBookAdmin,
    WantToReadBookAdmin,
    WikipediaBookDataAdmin,
)


class AdminRegistrationTests(TestCase):
    """Test that all admin classes are properly registered."""

    def test_author_admin_registered(self):
        """Author model should be registered with AuthorAdmin."""
        self.assertIn(models.Author, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.Author], AuthorAdmin)

    def test_book_admin_registered(self):
        """Book model should be registered with BookAdmin."""
        self.assertIn(models.Book, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.Book], BookAdmin)

    def test_book_genre_admin_registered(self):
        """BookGenre model should be registered with BookGenreAdmin."""
        self.assertIn(models.BookGenre, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.BookGenre], BookGenreAdmin)

    def test_book_series_admin_registered(self):
        """BookSeries model should be registered with BookSeriesAdmin."""
        self.assertIn(models.BookSeries, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.BookSeries], BookSeriesAdmin)

    def test_wikipedia_book_data_admin_registered(self):
        """WikipediaBookData model should be registered."""
        self.assertIn(models.WikipediaBookData, admin.site._registry)
        self.assertIsInstance(
            admin.site._registry[models.WikipediaBookData], WikipediaBookDataAdmin
        )

    def test_book_list_membership_admin_registered(self):
        """BookListMembership model should be registered."""
        self.assertIn(models.BookListMembership, admin.site._registry)
        self.assertIsInstance(
            admin.site._registry[models.BookListMembership], BookListMembershipAdmin
        )

    def test_read_book_admin_registered(self):
        """ReadBook model should be registered with ReadBookAdmin."""
        self.assertIn(models.ReadBook, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.ReadBook], ReadBookAdmin)

    def test_want_to_read_book_admin_registered(self):
        """WantToReadBook model should be registered."""
        self.assertIn(models.WantToReadBook, admin.site._registry)
        self.assertIsInstance(
            admin.site._registry[models.WantToReadBook], WantToReadBookAdmin
        )


class AdminConfigurationTests(TestCase):
    """Test admin configuration options."""

    def test_book_admin_list_display(self):
        """BookAdmin should have expected list_display fields."""
        admin_instance = admin.site._registry[models.Book]
        expected_fields = ["name", "slug", "rank", "year_published", "goodreads_id"]
        for field in expected_fields:
            self.assertIn(
                field,
                admin_instance.list_display,
                f"{field} should be in BookAdmin.list_display",
            )

    def test_book_admin_search_fields(self):
        """BookAdmin should allow searching by name and IDs."""
        admin_instance = admin.site._registry[models.Book]
        expected_fields = ["name", "goodreads_id", "isbn"]
        for field in expected_fields:
            self.assertIn(
                field,
                admin_instance.search_fields,
                f"{field} should be in BookAdmin.search_fields",
            )

    def test_author_admin_has_inline(self):
        """AuthorAdmin should have SubsidiaryAuthorInline."""
        admin_instance = admin.site._registry[models.Author]
        self.assertTrue(
            len(admin_instance.inlines) > 0,
            "AuthorAdmin should have at least one inline",
        )


class BookFiltersTests(TestCase):
    """Test book template tags and filters."""

    def test_book_genre_icon_with_string(self):
        """book_genre_icon should return icon for genre name string."""
        from books.templatetags.book_filters import book_genre_icon

        self.assertEqual(book_genre_icon("Science Fiction"), "mdi-rocket-launch")
        self.assertEqual(book_genre_icon("Fantasy"), "mdi-wizard-hat")
        self.assertEqual(book_genre_icon("Mystery"), "mdi-magnify")
        self.assertEqual(book_genre_icon("Unknown Genre"), "mdi-book")

    def test_book_genre_icon_with_genre_object(self):
        """book_genre_icon should work with BookGenre objects."""
        from books.templatetags.book_filters import book_genre_icon

        # Create a root genre (level 0)
        root_genre = models.BookGenre.objects.create(
            name="Fiction", slug="fiction", level=0
        )
        self.assertEqual(book_genre_icon(root_genre), "mdi-book-open-page-variant")

        # Create a child genre
        child_genre = models.BookGenre.objects.create(
            name="Space Opera", slug="space-opera", parent=root_genre, level=1
        )
        # Child should use parent's category, which is Fiction
        self.assertEqual(book_genre_icon(child_genre), "mdi-book-open-page-variant")

        # Clean up
        child_genre.delete()
        root_genre.delete()

    def test_format_page_count(self):
        """format_page_count should format page counts correctly."""
        from books.templatetags.book_filters import format_page_count

        self.assertEqual(format_page_count(324), "324 pages")
        self.assertEqual(format_page_count(1), "1 page")
        self.assertEqual(format_page_count(1000), "1,000 pages")
        self.assertEqual(format_page_count(None), "")
        self.assertEqual(format_page_count("invalid"), "")

    def test_reading_time_estimate(self):
        """reading_time_estimate should calculate reading time correctly."""
        from books.templatetags.book_filters import reading_time_estimate

        # 300 pages * 250 words/page = 75000 words / 250 wpm = 300 min = 5h
        self.assertEqual(reading_time_estimate(300), "~5h")
        # 100 pages = 25000 words / 250 wpm = 100 min = 1h 40m
        self.assertEqual(reading_time_estimate(100), "~1h 40m")
        # 20 pages = 5000 words / 250 wpm = 20 min
        self.assertEqual(reading_time_estimate(20), "~20m")
        self.assertEqual(reading_time_estimate(None), "")
        self.assertEqual(reading_time_estimate(0), "")

    def test_format_author_list(self):
        """format_author_list should format author lists correctly."""
        from books.templatetags.book_filters import format_author_list

        # Create test authors
        author1 = models.Author.objects.create(name="Author One", slug="author-one")
        author2 = models.Author.objects.create(name="Author Two", slug="author-two")
        author3 = models.Author.objects.create(name="Author Three", slug="author-three")
        author4 = models.Author.objects.create(name="Author Four", slug="author-four")
        author5 = models.Author.objects.create(name="Author Five", slug="author-five")

        # Test with 2 authors (under limit)
        self.assertEqual(
            format_author_list([author1, author2]), "Author One, Author Two"
        )

        # Test with 3 authors (at limit)
        self.assertEqual(
            format_author_list([author1, author2, author3]),
            "Author One, Author Two, Author Three",
        )

        # Test with 4 authors (over limit)
        self.assertEqual(
            format_author_list([author1, author2, author3, author4]),
            "Author One, Author Two & 2 more",
        )

        # Test with 5 authors
        self.assertEqual(
            format_author_list([author1, author2, author3, author4, author5]),
            "Author One, Author Two & 3 more",
        )

        # Test with empty list
        self.assertEqual(format_author_list([]), "")
        self.assertEqual(format_author_list(None), "")

        # Clean up
        models.Author.objects.filter(
            id__in=[author1.id, author2.id, author3.id, author4.id, author5.id]
        ).delete()

    def test_book_series_label(self):
        """book_series_label should format series position correctly."""
        from decimal import Decimal

        from books.templatetags.book_filters import book_series_label

        # Create a test series and book
        series = models.BookSeries.objects.create(
            name="Harry Potter", slug="harry-potter"
        )
        book = models.Book.objects.create(
            name="Philosopher's Stone",
            slug="philosophers-stone",
            rank=1,
            series=series,
            series_position=Decimal("1"),
        )

        self.assertEqual(book_series_label(book), "Harry Potter #1")

        # Test with decimal position
        book.series_position = Decimal("2.5")
        book.save()
        self.assertEqual(book_series_label(book), "Harry Potter #2.5")

        # Test without series position
        book.series_position = None
        book.save()
        self.assertEqual(book_series_label(book), "Harry Potter")

        # Test without series
        book.series = None
        book.save()
        self.assertEqual(book_series_label(book), "")

        # Clean up
        book.delete()
        series.delete()

    def test_isbn_display(self):
        """isbn_display should format ISBNs with hyphens."""
        from books.templatetags.book_filters import isbn_display

        # ISBN-13
        self.assertEqual(isbn_display("9780132350884"), "978-0-132-35088-4")
        # ISBN-10
        self.assertEqual(isbn_display("0132350882"), "0-132-35088-2")
        # Empty
        self.assertEqual(isbn_display(""), "")
        self.assertEqual(isbn_display(None), "")
        # Invalid length returns original
        self.assertEqual(isbn_display("12345"), "12345")

    def test_rating_stars(self):
        """rating_stars should calculate star counts correctly."""
        from books.templatetags.book_filters import rating_stars

        # Full 5 stars
        result = rating_stars(5.0)
        self.assertEqual(result["full"], 5)
        self.assertEqual(result["half"], 0)
        self.assertEqual(result["empty"], 0)
        self.assertEqual(result["percentage"], 100)

        # 4.5 stars (rounds to 5 since 0.5 >= 0.25 and < 0.75 = half)
        result = rating_stars(4.5)
        self.assertEqual(result["full"], 4)
        self.assertEqual(result["half"], 1)
        self.assertEqual(result["empty"], 0)

        # 3.8 stars (rounds up to 4)
        result = rating_stars(3.8)
        self.assertEqual(result["full"], 4)
        self.assertEqual(result["half"], 0)
        self.assertEqual(result["empty"], 1)

        # 3.3 stars (3 full, 1 half)
        result = rating_stars(3.3)
        self.assertEqual(result["full"], 3)
        self.assertEqual(result["half"], 1)
        self.assertEqual(result["empty"], 1)

        # 0 stars
        result = rating_stars(0)
        self.assertEqual(result["full"], 0)
        self.assertEqual(result["half"], 0)
        self.assertEqual(result["empty"], 5)
        self.assertEqual(result["percentage"], 0)

        # None rating
        result = rating_stars(None)
        self.assertEqual(result["full"], 0)
        self.assertEqual(result["empty"], 5)

    def test_author_display_name(self):
        """author_display_name should format author names correctly."""
        from books.templatetags.book_filters import author_display_name

        # Create parent and child author
        parent = models.Author.objects.create(name="Stephen King", slug="stephen-king")
        child = models.Author.objects.create(
            name="Richard Bachman", slug="richard-bachman", parent=parent
        )

        self.assertEqual(author_display_name(parent), "Stephen King")
        self.assertEqual(author_display_name(child), "Richard Bachman (Stephen King)")
        self.assertEqual(author_display_name(None), "")

        # Clean up
        child.delete()
        parent.delete()

    def test_get_list_type_label(self):
        """get_list_type_label should return correct labels."""
        from books.templatetags.book_filters import get_list_type_label

        self.assertEqual(get_list_type_label("A"), "All time")
        self.assertEqual(get_list_type_label("E"), "End of year")
        self.assertEqual(get_list_type_label("D"), "Decade")
        self.assertEqual(get_list_type_label("M"), "Miscellaneous")
        self.assertEqual(get_list_type_label("X"), "X")  # Unknown returns itself

    def test_get_list_type_badge_class(self):
        """get_list_type_badge_class should return correct badge classes."""
        from books.templatetags.book_filters import get_list_type_badge_class

        self.assertEqual(get_list_type_badge_class("A"), "badge-info font-semibold")
        self.assertEqual(get_list_type_badge_class("E"), "badge-error font-semibold")
        self.assertEqual(get_list_type_badge_class("D"), "badge-success font-semibold")
        self.assertEqual(get_list_type_badge_class("M"), "badge-warning font-semibold")
        self.assertEqual(get_list_type_badge_class("X"), "badge-ghost")


class AdminBehaviorCoverageTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/")
        self.user = get_user_model().objects.create_user(
            username="books-admin-user",
            email="books-admin@example.com",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        self.request.user = self.user

    def test_author_admin_get_queryset_and_fallback_count(self):
        author = models.Author.objects.create(name="Author Admin", slug="author-admin")
        book = models.Book.objects.create(name="Book Admin", slug="book-admin", rank=1)
        book.authors.add(author)
        admin_instance = admin.site._registry[models.Author]
        qs = admin_instance.get_queryset(self.request)
        obj = qs.get(pk=author.pk)
        self.assertEqual(obj._book_count, 1)
        self.assertEqual(admin_instance.book_count(author), 1)

    def test_book_genre_admin_book_count(self):
        genre = models.BookGenre.objects.create(name="Genre Admin", slug="genre-admin")
        book = models.Book.objects.create(name="Genre Book", slug="genre-book", rank=2)
        book.genres.add(genre)
        admin_instance = admin.site._registry[models.BookGenre]
        self.assertEqual(admin_instance.book_count(genre), 1)

    def test_book_series_admin_get_queryset_and_fallback_count(self):
        series = models.BookSeries.objects.create(
            name="Series Admin", slug="series-admin"
        )
        book = models.Book.objects.create(
            name="Series Book", slug="series-book", rank=3, series=series
        )
        admin_instance = admin.site._registry[models.BookSeries]
        qs = admin_instance.get_queryset(self.request)
        obj = qs.get(pk=series.pk)
        self.assertEqual(obj._book_count, 1)
        self.assertEqual(admin_instance.book_count(series), 1)
        self.assertEqual(book.series_id, series.id)

    def test_book_admin_queryset_and_helpers(self):
        genre = models.BookGenre.objects.create(name="Admin Genre", slug="admin-genre")
        book = models.Book.objects.create(
            name="Admin Book",
            slug="admin-book",
            rank=4,
        )
        book.genres.add(genre)
        wiki = models.WikipediaBookData.objects.create(
            book=book, page_title="Admin Book Page", all_genres="Drama"
        )
        book.primary_wikipedia_book_data = wiki
        book.save(update_fields=["primary_wikipedia_book_data"])

        admin_instance = admin.site._registry[models.Book]
        qs = admin_instance.get_queryset(self.request)
        obj = qs.get(pk=book.pk)
        self.assertIn("Admin Genre", admin_instance._genres_display(obj))
        link = admin_instance._wikipedia_data_link(obj)
        self.assertIn("/admin/books/wikipediabookdata/", link)
        self.assertIn("View", link)

    def test_book_admin_wikipedia_link_returns_dash_when_missing(self):
        book = models.Book.objects.create(
            name="No Wiki Book",
            slug="no-wiki-book",
            rank=40,
        )
        admin_instance = admin.site._registry[models.Book]
        self.assertEqual(admin_instance._wikipedia_data_link(book), "-")

    def test_wikipedia_book_data_admin_helpers(self):
        book = models.Book.objects.create(name="Wiki Book", slug="wiki-book", rank=5)
        data = models.WikipediaBookData.objects.create(
            book=book,
            page_title="Wiki Book",
            all_genres="Action, RPG",
        )
        admin_instance = admin.site._registry[models.WikipediaBookData]
        self.assertEqual(admin_instance._all_genres_preview(data), "Action, RPG")
        link = admin_instance._wikipedia_link(data)
        self.assertIn("Wiki Book", link)
        self.assertIn("<a href=", link)

    def test_wikipedia_book_data_admin_empty_helpers(self):
        book = models.Book.objects.create(
            name="No Meta Book", slug="no-meta-book", rank=41
        )
        data = models.WikipediaBookData.objects.create(
            book=book,
            page_title="",
            all_genres="",
        )
        admin_instance = admin.site._registry[models.WikipediaBookData]
        self.assertEqual(admin_instance._all_genres_preview(data), "-")
        self.assertEqual(admin_instance._wikipedia_link(data), "-")

    def test_read_and_want_admin_connected_status_and_name(self):
        book = models.Book.objects.create(
            name="Tracked Book", slug="tracked-book", rank=6
        )
        read = models.ReadBook.objects.create(
            user=self.user, book=book, goodreads_id="10"
        )
        want = models.WantToReadBook.objects.create(
            user=self.user, book=book, goodreads_id="11"
        )
        read_admin = admin.site._registry[models.ReadBook]
        want_admin = admin.site._registry[models.WantToReadBook]
        self.assertEqual(read_admin.book_name(read), "Tracked Book")
        self.assertEqual(read_admin.book_status(read), "Connected")
        self.assertEqual(want_admin.book_name(want), "Tracked Book")
        self.assertEqual(want_admin.book_status(want), "Connected")

    def test_read_and_want_admin_orphaned_status_and_name(self):
        read = models.ReadBook.objects.create(
            user=self.user, book=None, goodreads_id="12"
        )
        want = models.WantToReadBook.objects.create(
            user=self.user, book=None, goodreads_id="13"
        )
        read_admin = admin.site._registry[models.ReadBook]
        want_admin = admin.site._registry[models.WantToReadBook]
        self.assertEqual(read_admin.book_name(read), "(orphaned) Goodreads:12")
        self.assertEqual(read_admin.book_status(read), "Orphaned")
        self.assertEqual(want_admin.book_name(want), "(orphaned) Goodreads:13")
        self.assertEqual(want_admin.book_status(want), "Orphaned")
