"""
Tests for books app template tags and filters.
"""

from decimal import Decimal

from django.test import TestCase

from books import models
from books.templatetags.book_filters import (
    author_display_name,
    book_genre_icon,
    book_series_label,
    format_author_list,
    format_page_count,
    get_list_type_badge_class,
    get_list_type_label,
    isbn_display,
    rating_stars,
    reading_time_estimate,
)


class BookGenreIconTests(TestCase):
    """Tests for book_genre_icon template filter."""

    def test_with_string(self):
        """book_genre_icon should return icon for genre name string."""
        self.assertEqual(book_genre_icon("Science Fiction"), "mdi-rocket-launch")
        self.assertEqual(book_genre_icon("Fantasy"), "mdi-wizard-hat")
        self.assertEqual(book_genre_icon("Mystery"), "mdi-magnify")
        self.assertEqual(book_genre_icon("Unknown Genre"), "mdi-book")

    def test_with_genre_object(self):
        """book_genre_icon should work with BookGenre objects."""
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


class FormatPageCountTests(TestCase):
    """Tests for format_page_count template filter."""

    def test_format_page_count(self):
        """format_page_count should format page counts correctly."""
        self.assertEqual(format_page_count(324), "324 pages")
        self.assertEqual(format_page_count(1), "1 page")
        self.assertEqual(format_page_count(1000), "1,000 pages")
        self.assertEqual(format_page_count(None), "")
        self.assertEqual(format_page_count("invalid"), "")


class ReadingTimeEstimateTests(TestCase):
    """Tests for reading_time_estimate template filter."""

    def test_reading_time_estimate(self):
        """reading_time_estimate should calculate reading time correctly."""
        # 300 pages * 250 words/page = 75000 words / 250 wpm = 300 min = 5h
        self.assertEqual(reading_time_estimate(300), "~5h")
        # 100 pages = 25000 words / 250 wpm = 100 min = 1h 40m
        self.assertEqual(reading_time_estimate(100), "~1h 40m")
        # 20 pages = 5000 words / 250 wpm = 20 min
        self.assertEqual(reading_time_estimate(20), "~20m")
        self.assertEqual(reading_time_estimate(None), "")
        self.assertEqual(reading_time_estimate(0), "")


class FormatAuthorListTests(TestCase):
    """Tests for format_author_list template filter."""

    def test_format_author_list(self):
        """format_author_list should format author lists correctly."""
        # Create test authors
        author1 = models.Author.objects.create(name="Author One", slug="author-one")
        author2 = models.Author.objects.create(name="Author Two", slug="author-two")
        author3 = models.Author.objects.create(
            name="Author Three", slug="author-three"
        )
        author4 = models.Author.objects.create(name="Author Four", slug="author-four")
        author5 = models.Author.objects.create(name="Author Five", slug="author-five")

        # Test with 2 authors (under limit)
        self.assertEqual(format_author_list([author1, author2]), "Author One, Author Two")

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


class BookSeriesLabelTests(TestCase):
    """Tests for book_series_label template filter."""

    def test_book_series_label(self):
        """book_series_label should format series position correctly."""
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


class IsbnDisplayTests(TestCase):
    """Tests for isbn_display template filter."""

    def test_isbn_display(self):
        """isbn_display should format ISBNs with hyphens."""
        # ISBN-13
        self.assertEqual(isbn_display("9780132350884"), "978-0-132-35088-4")
        # ISBN-10
        self.assertEqual(isbn_display("0132350882"), "0-132-35088-2")
        # Empty
        self.assertEqual(isbn_display(""), "")
        self.assertEqual(isbn_display(None), "")
        # Invalid length returns original
        self.assertEqual(isbn_display("12345"), "12345")


class RatingStarsTests(TestCase):
    """Tests for rating_stars template filter."""

    def test_rating_stars(self):
        """rating_stars should calculate star counts correctly."""
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


class AuthorDisplayNameTests(TestCase):
    """Tests for author_display_name template filter."""

    def test_author_display_name(self):
        """author_display_name should format author names correctly."""
        # Create parent and child author
        parent = models.Author.objects.create(
            name="Stephen King", slug="stephen-king"
        )
        child = models.Author.objects.create(
            name="Richard Bachman", slug="richard-bachman", parent=parent
        )

        self.assertEqual(author_display_name(parent), "Stephen King")
        self.assertEqual(
            author_display_name(child), "Richard Bachman (Stephen King)"
        )
        self.assertEqual(author_display_name(None), "")

        # Clean up
        child.delete()
        parent.delete()


class ListTypeLabelTests(TestCase):
    """Tests for get_list_type_label template filter."""

    def test_get_list_type_label(self):
        """get_list_type_label should return correct labels."""
        self.assertEqual(get_list_type_label("A"), "All time")
        self.assertEqual(get_list_type_label("E"), "End of year")
        self.assertEqual(get_list_type_label("D"), "Decade")
        self.assertEqual(get_list_type_label("M"), "Miscellaneous")
        self.assertEqual(get_list_type_label("X"), "X")  # Unknown returns itself


class ListTypeBadgeClassTests(TestCase):
    """Tests for get_list_type_badge_class template filter."""

    def test_get_list_type_badge_class(self):
        """get_list_type_badge_class should return correct badge classes."""
        self.assertEqual(get_list_type_badge_class("A"), "badge-info font-semibold")
        self.assertEqual(get_list_type_badge_class("E"), "badge-error font-semibold")
        self.assertEqual(get_list_type_badge_class("D"), "badge-success font-semibold")
        self.assertEqual(get_list_type_badge_class("M"), "badge-warning font-semibold")
        self.assertEqual(get_list_type_badge_class("X"), "badge-ghost")
