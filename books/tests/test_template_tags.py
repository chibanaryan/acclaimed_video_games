"""
Tests for book template tags and filters.
"""

from django.test import TestCase

from books.models import Author, Book, BookGenre
from books.templatetags.book_filters import (
    BOOK_GENRE_ICONS,
    DEFAULT_BOOK_GENRE_ICON,
    book_genre_icon,
    book_genres_grouped,
    book_rank_url,
    child_author_ids,
    estimated_reading_time,
    format_page_count,
    format_page_count_short,
    format_rating,
    format_rating_count,
    format_series_position,
    get_author_ids,
    get_list_type_badge_class,
    get_list_type_label,
    rank_pct,
)


class BookGenreIconTests(TestCase):
    """Tests for book_genre_icon filter."""

    def test_string_genre_known(self):
        """Known genre string returns correct icon."""
        self.assertEqual(book_genre_icon("Science Fiction"), "mdi-rocket-launch")
        self.assertEqual(book_genre_icon("Fantasy"), "mdi-sword-cross")
        self.assertEqual(book_genre_icon("Mystery"), "mdi-magnify")
        self.assertEqual(book_genre_icon("Romance"), "mdi-heart")

    def test_string_genre_unknown(self):
        """Unknown genre string returns default icon."""
        self.assertEqual(book_genre_icon("Made Up Genre"), DEFAULT_BOOK_GENRE_ICON)

    def test_genre_object_with_icon_name(self):
        """Genre object with icon_name field uses that icon."""
        genre = BookGenre(name="Custom Genre", icon_name="mdi-custom-icon")
        genre.id = 1
        self.assertEqual(book_genre_icon(genre), "mdi-custom-icon")

    def test_genre_object_level_0(self):
        """Root genre (level 0) uses its own name for icon lookup."""
        genre = BookGenre(name="Fiction", level=0)
        genre.id = 1
        self.assertEqual(book_genre_icon(genre), BOOK_GENRE_ICONS["Fiction"])

    def test_genre_object_unknown(self):
        """Unknown genre object returns default icon."""
        genre = BookGenre(name="Unknown Category", level=0)
        genre.id = 1
        self.assertEqual(book_genre_icon(genre), DEFAULT_BOOK_GENRE_ICON)


class BookGenresGroupedTests(TestCase):
    """Tests for book_genres_grouped filter."""

    def setUp(self):
        """Create test genre hierarchy."""
        self.fiction = BookGenre.objects.create(name="Fiction")
        self.scifi = BookGenre.objects.create(
            name="Science Fiction", parent=self.fiction
        )
        self.fantasy = BookGenre.objects.create(name="Fantasy", parent=self.fiction)
        self.nonfiction = BookGenre.objects.create(name="Non-Fiction")
        self.history = BookGenre.objects.create(name="History", parent=self.nonfiction)

    def test_groups_genres_by_parent(self):
        """Genres are grouped by their parent category."""
        genres = [self.scifi, self.fantasy, self.history]
        result = book_genres_grouped(genres)

        # Should have 2 groups: Fiction and Non-Fiction
        self.assertEqual(len(result), 2)

        # Check group names
        group_names = {g["name"] for g in result}
        self.assertEqual(group_names, {"Fiction", "Non-Fiction"})

    def test_counts_genres_per_group(self):
        """Each group shows correct count."""
        genres = [self.scifi, self.fantasy, self.history]
        result = book_genres_grouped(genres)

        # Find Fiction group
        fiction_group = next(g for g in result if g["name"] == "Fiction")
        self.assertEqual(fiction_group["count"], 2)

        # Find Non-Fiction group
        nonfiction_group = next(g for g in result if g["name"] == "Non-Fiction")
        self.assertEqual(nonfiction_group["count"], 1)

    def test_includes_genre_ids(self):
        """Groups include comma-separated genre IDs."""
        genres = [self.scifi, self.fantasy]
        result = book_genres_grouped(genres)

        fiction_group = next(g for g in result if g["name"] == "Fiction")
        ids = set(fiction_group["genre_ids_str"].split(","))
        self.assertEqual(ids, {str(self.scifi.id), str(self.fantasy.id)})

    def test_empty_list(self):
        """Empty genre list returns empty result."""
        result = book_genres_grouped([])
        self.assertEqual(result, [])


class FormatPageCountTests(TestCase):
    """Tests for page count formatting filters."""

    def test_format_page_count_regular(self):
        """Regular page count formatted correctly."""
        self.assertEqual(format_page_count(342), "342 pages")
        self.assertEqual(format_page_count(1000), "1,000 pages")

    def test_format_page_count_singular(self):
        """Single page formatted correctly."""
        self.assertEqual(format_page_count(1), "1 page")

    def test_format_page_count_none(self):
        """None returns empty string."""
        self.assertEqual(format_page_count(None), "")

    def test_format_page_count_short_regular(self):
        """Short format works for regular values."""
        self.assertEqual(format_page_count_short(342), "342pp")

    def test_format_page_count_short_thousands(self):
        """Short format abbreviates large numbers."""
        self.assertEqual(format_page_count_short(1500), "1.5k pp")

    def test_format_page_count_short_none(self):
        """None returns empty string."""
        self.assertEqual(format_page_count_short(None), "")


class EstimatedReadingTimeTests(TestCase):
    """Tests for estimated_reading_time filter."""

    def test_short_book(self):
        """Short book shows minutes."""
        # 15 pages at 30 pages/hour = 30 minutes
        self.assertEqual(estimated_reading_time(15), "~30 min")

    def test_medium_book(self):
        """Medium book shows hours."""
        # 300 pages at 30 pages/hour = 10 hours
        self.assertEqual(estimated_reading_time(300), "~10 hours")

    def test_long_book(self):
        """Very long book shows days."""
        # 1200 pages at 30 pages/hour = 40 hours = 5 days
        self.assertEqual(estimated_reading_time(1200), "~5 days")

    def test_none(self):
        """None returns empty string."""
        self.assertEqual(estimated_reading_time(None), "")

    def test_custom_reading_speed(self):
        """Custom reading speed is respected."""
        # 60 pages at 60 pages/hour = 1 hour
        self.assertEqual(estimated_reading_time(60, pages_per_hour=60), "~1 hours")


class FormatSeriesPositionTests(TestCase):
    """Tests for format_series_position filter."""

    def test_whole_number(self):
        """Whole number position formatted without decimal."""
        self.assertEqual(format_series_position(1), "#1")
        self.assertEqual(format_series_position(5), "#5")

    def test_decimal_position(self):
        """Decimal position (novellas) formatted with decimal."""
        self.assertEqual(format_series_position(2.5), "#2.5")

    def test_none(self):
        """None returns empty string."""
        self.assertEqual(format_series_position(None), "")


class FormatRatingTests(TestCase):
    """Tests for rating formatting filters."""

    def test_format_rating(self):
        """Rating formatted correctly."""
        self.assertEqual(format_rating(4.5), "4.5/5")
        self.assertEqual(format_rating(3.83), "3.8/5")

    def test_format_rating_none(self):
        """None returns empty string."""
        self.assertEqual(format_rating(None), "")

    def test_format_rating_count_small(self):
        """Small count displayed as-is."""
        self.assertEqual(format_rating_count(892), "892")

    def test_format_rating_count_thousands(self):
        """Thousands abbreviated with K."""
        self.assertEqual(format_rating_count(45000), "45.0K")

    def test_format_rating_count_millions(self):
        """Millions abbreviated with M."""
        self.assertEqual(format_rating_count(1200000), "1.2M")

    def test_format_rating_count_none(self):
        """None returns empty string."""
        self.assertEqual(format_rating_count(None), "")


class BookRankUrlTests(TestCase):
    """Tests for book_rank_url tag."""

    def test_basic_url(self):
        """Basic URL with no parameters."""
        url = book_rank_url(1)
        self.assertIn("/books/", url)

    def test_with_highlight(self):
        """URL includes highlight parameter."""
        url = book_rank_url(1, book_id=42)
        self.assertIn("highlight=42", url)

    def test_with_year_filter(self):
        """URL includes year filter parameters."""
        url = book_rank_url(1, start=1990, end=1999)
        self.assertIn("start=1990", url)
        self.assertIn("end=1999", url)


class AuthorMappingTests(TestCase):
    """Tests for author mapping filters."""

    def test_get_author_ids_found(self):
        """Returns author IDs when book exists in mapping."""
        mapping = {1: [10, 20, 30], 2: [40, 50]}
        result = get_author_ids(mapping, 1)
        self.assertEqual(result, [10, 20, 30])

    def test_get_author_ids_not_found(self):
        """Returns empty list when book not in mapping."""
        mapping = {1: [10, 20]}
        result = get_author_ids(mapping, 99)
        self.assertEqual(result, [])

    def test_get_author_ids_invalid_mapping(self):
        """Returns empty list for invalid mapping."""
        self.assertEqual(get_author_ids(None, 1), [])
        self.assertEqual(get_author_ids("not a dict", 1), [])

    def test_child_author_ids(self):
        """Extracts author IDs from sub_author dicts."""
        author1 = Author(name="Author 1")
        author1.id = 10
        author2 = Author(name="Author 2")
        author2.id = 20

        sub_authors = [{"author": author1}, {"author": author2}]
        result = child_author_ids(sub_authors)
        self.assertEqual(result, [10, 20])

    def test_child_author_ids_empty(self):
        """Returns empty list for empty input."""
        self.assertEqual(child_author_ids([]), [])
        self.assertEqual(child_author_ids(None), [])


class RankPctTests(TestCase):
    """Tests for rank_pct filter."""

    def test_first_place(self):
        """Rank 1 returns 100%."""
        self.assertEqual(rank_pct(1, 100), 100)

    def test_last_place(self):
        """Last rank returns close to 0%."""
        self.assertEqual(rank_pct(100, 100), 0)

    def test_middle(self):
        """Middle rank returns ~50%."""
        result = rank_pct(50, 100)
        self.assertAlmostEqual(result, 51, delta=2)

    def test_invalid_inputs(self):
        """Invalid inputs return 0."""
        self.assertEqual(rank_pct(None, 100), 0)
        self.assertEqual(rank_pct(1, None), 0)
        self.assertEqual(rank_pct(1, 1), 0)  # Only 1 item


class ListTypeFilterTests(TestCase):
    """Tests for list type filters."""

    def test_get_list_type_label(self):
        """Returns correct label for type code."""
        self.assertEqual(get_list_type_label("A"), "All time")
        self.assertEqual(get_list_type_label("D"), "Decade")
        self.assertEqual(get_list_type_label("E"), "End of year")

    def test_get_list_type_label_unknown(self):
        """Returns code for unknown type."""
        self.assertEqual(get_list_type_label("X"), "X")

    def test_get_list_type_badge_class(self):
        """Returns correct badge class for type code."""
        self.assertIn("badge-info", get_list_type_badge_class("A"))
        self.assertIn("badge-success", get_list_type_badge_class("D"))
        self.assertIn("badge-ghost", get_list_type_badge_class("X"))
