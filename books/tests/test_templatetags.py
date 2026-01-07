"""
Tests for books app template tags and filters.
"""

from decimal import Decimal

from django.test import TestCase

from books import models
from books.templatetags.book_filters import (
    author_display_name,
    book_genre_categories_grouped,
    book_genre_icon,
    book_rank_url,
    book_series_label,
    format_author_list,
    format_page_count,
    get_author_ids,
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


class BookGenreCategoriesGroupedTests(TestCase):
    """Tests for book_genre_categories_grouped template filter."""

    def test_groups_genres_by_parent(self):
        """book_genre_categories_grouped should group genres by parent category."""
        # Create parent category
        fiction = models.BookGenre.objects.create(
            name="Fiction", slug="fiction", level=0
        )
        # Create child genres
        scifi = models.BookGenre.objects.create(
            name="Sci-Fi", slug="scifi", parent=fiction, level=1
        )
        fantasy = models.BookGenre.objects.create(
            name="Fantasy", slug="fantasy", parent=fiction, level=1
        )

        result = book_genre_categories_grouped([scifi, fantasy])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Fiction")
        self.assertEqual(result[0]["count"], 2)
        self.assertIn("Sci-Fi", result[0]["tooltip"])
        self.assertIn("Fantasy", result[0]["tooltip"])

    def test_handles_root_level_genres(self):
        """book_genre_categories_grouped should handle root-level genres."""
        root = models.BookGenre.objects.create(
            name="Science Fiction", slug="science-fiction", level=0
        )

        result = book_genre_categories_grouped([root])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Science Fiction")
        self.assertEqual(result[0]["icon"], "mdi-rocket-launch")

    def test_returns_empty_for_empty_list(self):
        """book_genre_categories_grouped should return empty list for no genres."""
        result = book_genre_categories_grouped([])
        self.assertEqual(result, [])

    def test_multiple_categories(self):
        """book_genre_categories_grouped should handle multiple categories."""
        fiction = models.BookGenre.objects.create(
            name="Fiction", slug="fiction-cat", level=0
        )
        nonfiction = models.BookGenre.objects.create(
            name="Non-Fiction", slug="nonfiction-cat", level=0
        )
        fantasy = models.BookGenre.objects.create(
            name="Epic Fantasy", slug="epic-fantasy", parent=fiction, level=1
        )
        history = models.BookGenre.objects.create(
            name="World History", slug="world-history", parent=nonfiction, level=1
        )

        result = book_genre_categories_grouped([fantasy, history])

        self.assertEqual(len(result), 2)
        category_names = {r["name"] for r in result}
        self.assertIn("Fiction", category_names)
        self.assertIn("Non-Fiction", category_names)


class BookRankUrlTests(TestCase):
    """Tests for book_rank_url template tag."""

    def test_basic_url(self):
        """book_rank_url should generate basic URL."""
        url = book_rank_url(1)
        self.assertEqual(url, "/books/")

    def test_url_with_highlight(self):
        """book_rank_url should include highlight parameter."""
        url = book_rank_url(1, book_id=123)
        self.assertIn("highlight=123", url)

    def test_url_with_year_range(self):
        """book_rank_url should include year range parameters."""
        url = book_rank_url(1, start=2000, end=2010)
        self.assertIn("start=2000", url)
        self.assertIn("end=2010", url)

    def test_url_with_all_params(self):
        """book_rank_url should handle all parameters."""
        url = book_rank_url(1, book_id=456, start=1990, end=2000)
        self.assertIn("highlight=456", url)
        self.assertIn("start=1990", url)
        self.assertIn("end=2000", url)


class GetAuthorIdsTests(TestCase):
    """Tests for get_author_ids template filter."""

    def test_returns_author_ids(self):
        """get_author_ids should return author IDs from mapping."""
        book_author_map = {
            1: [10, 20, 30],
            2: [40, 50],
        }
        result = get_author_ids(book_author_map, 1)
        self.assertEqual(result, [10, 20, 30])

    def test_returns_empty_for_missing_book(self):
        """get_author_ids should return empty list for missing book."""
        book_author_map = {1: [10, 20]}
        result = get_author_ids(book_author_map, 999)
        self.assertEqual(result, [])

    def test_handles_none_map(self):
        """get_author_ids should handle None map."""
        result = get_author_ids(None, 1)
        self.assertEqual(result, [])

    def test_handles_non_dict_map(self):
        """get_author_ids should handle non-dict map."""
        result = get_author_ids("not a dict", 1)
        self.assertEqual(result, [])


class BookGenreIconEdgeCasesTests(TestCase):
    """Additional edge case tests for book_genre_icon."""

    def test_genre_with_icon_name_attribute(self):
        """book_genre_icon should use icon_name if present."""

        class MockGenre:
            icon_name = "mdi-custom-icon"
            name = "Custom"

        result = book_genre_icon(MockGenre())
        self.assertEqual(result, "mdi-custom-icon")

    def test_genre_without_parent_or_level(self):
        """book_genre_icon should fall back for genre without parent/level."""

        class MockGenre:
            name = "Mystery"
            parent = None

        result = book_genre_icon(MockGenre())
        self.assertEqual(result, "mdi-magnify")


class ReadingTimeEstimateEdgeCasesTests(TestCase):
    """Additional edge case tests for reading_time_estimate."""

    def test_negative_page_count(self):
        """reading_time_estimate should handle negative page count."""
        self.assertEqual(reading_time_estimate(-10), "")

    def test_custom_words_per_minute(self):
        """reading_time_estimate should accept custom reading speed."""
        # 100 pages * 250 words = 25000 words / 500 wpm = 50 min
        self.assertEqual(reading_time_estimate(100, 500), "~50m")

    def test_invalid_words_per_minute(self):
        """reading_time_estimate should handle invalid wpm."""
        self.assertEqual(reading_time_estimate(100, "invalid"), "")
        self.assertEqual(reading_time_estimate(100, 0), "")


class RatingStarsEdgeCasesTests(TestCase):
    """Additional edge case tests for rating_stars."""

    def test_negative_rating(self):
        """rating_stars should handle negative rating."""
        result = rating_stars(-2)
        self.assertEqual(result["full"], 0)
        self.assertEqual(result["empty"], 5)

    def test_over_max_rating(self):
        """rating_stars should cap at max_stars."""
        result = rating_stars(7, max_stars=5)
        self.assertEqual(result["full"], 5)
        self.assertEqual(result["empty"], 0)

    def test_custom_max_stars(self):
        """rating_stars should handle custom max_stars."""
        result = rating_stars(8, max_stars=10)
        self.assertEqual(result["full"], 8)
        self.assertEqual(result["empty"], 2)

    def test_invalid_rating(self):
        """rating_stars should handle invalid rating."""
        result = rating_stars("invalid")
        self.assertEqual(result["full"], 0)
        self.assertEqual(result["empty"], 5)
