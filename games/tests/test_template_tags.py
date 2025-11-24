from datetime import timedelta
from unittest.mock import Mock

from django.core.paginator import Paginator
from django.test import RequestFactory, TestCase
from django.utils import timezone

from games.templatetags.game_filters import (
    from_now,
    game_rank_url,
    pagination_pages,
    pagination_url,
    tojson,
)


class PaginationPagesTest(TestCase):
    """Test the pagination_pages template tag."""

    def _create_page_obj(self, page_num, total_pages):
        """Helper to create a page object for testing."""
        items = list(range(1, total_pages * 10 + 1))
        paginator = Paginator(items, 10)
        return paginator.page(page_num)

    def test_no_pagination_for_single_page(self):
        """Test that empty list is returned for single page."""
        page_obj = self._create_page_obj(1, 1)
        result = pagination_pages(page_obj)
        self.assertEqual(result, [])

    def test_show_all_pages_when_flag_is_true(self):
        """Test that all pages are shown when show_all_pages=True."""
        page_obj = self._create_page_obj(1, 10)
        result = pagination_pages(page_obj, show_all_pages=True)
        # Should have all page numbers
        pages = [p for p in result if p is not None]
        self.assertEqual(pages, list(range(1, 11)))

    def test_show_all_pages_with_string_true(self):
        """Test that show_all_pages works with string 'true'."""
        page_obj = self._create_page_obj(1, 10)
        result = pagination_pages(page_obj, show_all_pages="true")
        pages = [p for p in result if p is not None]
        self.assertEqual(pages, list(range(1, 11)))

    def test_ellipsis_for_large_page_count(self):
        """Test that ellipsis (None) is added for large page counts."""
        page_obj = self._create_page_obj(1, 50)
        result = pagination_pages(page_obj)
        # Should have ellipsis somewhere
        self.assertIn(None, result)
        # First page should be included
        self.assertIn(1, result)
        # Last page should be included
        self.assertIn(50, result)

    def test_current_page_in_middle(self):
        """Test pagination when current page is in the middle."""
        page_obj = self._create_page_obj(25, 50)
        result = pagination_pages(page_obj)
        # Current page and neighbors should be included
        self.assertIn(25, result)
        # First and last should be included
        self.assertIn(1, result)
        self.assertIn(50, result)

    def test_handles_empty_page_obj(self):
        """Test that empty page_obj returns empty list."""
        result = pagination_pages(None)
        self.assertEqual(result, [])

    def test_handles_page_obj_without_paginator(self):
        """Test that page_obj without paginator attribute returns empty list."""
        page_obj = Mock(spec=[])
        result = pagination_pages(page_obj)
        self.assertEqual(result, [])


class FromNowFilterTest(TestCase):
    """Test the from_now template filter."""

    def test_just_now_for_recent_time(self):
        """Test that 'just now' is returned for times less than a minute ago."""
        now = timezone.now()
        recent = now - timedelta(seconds=30)
        self.assertEqual(from_now(recent), "just now")

    def test_minutes_ago(self):
        """Test formatting for minutes ago."""
        now = timezone.now()
        past = now - timedelta(minutes=5)
        self.assertEqual(from_now(past), "5 minutes ago")

    def test_singular_minute(self):
        """Test singular 'minute' for exactly 1 minute."""
        now = timezone.now()
        past = now - timedelta(minutes=1)
        self.assertEqual(from_now(past), "1 minute ago")

    def test_hours_ago(self):
        """Test formatting for hours ago."""
        now = timezone.now()
        past = now - timedelta(hours=3)
        self.assertEqual(from_now(past), "3 hours ago")

    def test_singular_hour(self):
        """Test singular 'hour' for exactly 1 hour."""
        now = timezone.now()
        past = now - timedelta(hours=1)
        self.assertEqual(from_now(past), "1 hour ago")

    def test_days_ago(self):
        """Test formatting for days ago."""
        now = timezone.now()
        past = now - timedelta(days=5)
        result = from_now(past)
        self.assertIn("5 day", result)
        self.assertIn("ago", result)

    def test_singular_day(self):
        """Test singular 'day' for exactly 1 day."""
        now = timezone.now()
        past = now - timedelta(days=1)
        self.assertEqual(from_now(past), "1 day ago")

    def test_months_ago(self):
        """Test formatting for months ago."""
        now = timezone.now()
        past = now - timedelta(days=60)  # Roughly 2 months
        result = from_now(past)
        self.assertIn("month", result)
        self.assertIn("ago", result)

    def test_years_ago(self):
        """Test formatting for years ago."""
        now = timezone.now()
        past = now - timedelta(days=400)  # Over a year
        result = from_now(past)
        self.assertIn("year", result)
        self.assertIn("ago", result)

    def test_empty_value_returns_empty_string(self):
        """Test that empty/None value returns empty string."""
        self.assertEqual(from_now(None), "")
        self.assertEqual(from_now(""), "")

    def test_string_datetime_parsing(self):
        """Test that string datetimes are parsed correctly."""
        now = timezone.now()
        past_str = (now - timedelta(hours=2)).isoformat()
        result = from_now(past_str)
        self.assertIn("hour", result)

    def test_invalid_string_returns_empty(self):
        """Test that invalid datetime strings return empty string."""
        result = from_now("not a datetime")
        self.assertEqual(result, "")

    def test_non_datetime_returns_empty(self):
        """Test that non-datetime objects return empty string."""
        result = from_now(12345)
        self.assertEqual(result, "")


class GameRankUrlTest(TestCase):
    """Test the game_rank_url template tag."""

    def test_basic_rank_url(self):
        """Test basic rank URL generation."""
        url = game_rank_url(150)
        self.assertIn("/games/", url)
        self.assertIn("page=2", url)  # Rank 150 is on page 2

    def test_rank_with_game_id_highlight(self):
        """Test rank URL with game ID for highlighting."""
        url = game_rank_url(50, game_id=123)
        self.assertIn("page=1", url)
        self.assertIn("highlight=123", url)

    def test_rank_with_year_filter(self):
        """Test rank URL with single year filter."""
        url = game_rank_url(25, start=2020, end=2020)
        self.assertIn("year=2020", url)
        self.assertNotIn("decade", url)

    def test_rank_with_decade_filter(self):
        """Test rank URL with decade filter."""
        url = game_rank_url(25, start=1990, end=1999)
        self.assertIn("decade=1990-99", url)

    def test_rank_with_custom_range(self):
        """Test rank URL with custom year range."""
        url = game_rank_url(25, start=2015, end=2020)
        self.assertIn("start=2015", url)
        self.assertIn("end=2020", url)
        self.assertNotIn("decade", url)
        self.assertNotIn("year", url)

    def test_rank_with_only_start(self):
        """Test rank URL with only start year."""
        url = game_rank_url(25, start=2010)
        self.assertIn("start=2010", url)

    def test_rank_with_only_end(self):
        """Test rank URL with only end year."""
        url = game_rank_url(25, end=2020)
        self.assertIn("end=2020", url)

    def test_rank_1_is_page_1(self):
        """Test that rank 1 maps to page 1."""
        url = game_rank_url(1)
        self.assertIn("page=1", url)

    def test_rank_100_is_page_1(self):
        """Test that rank 100 is still on page 1."""
        url = game_rank_url(100)
        self.assertIn("page=1", url)

    def test_rank_101_is_page_2(self):
        """Test that rank 101 is on page 2."""
        url = game_rank_url(101)
        self.assertIn("page=2", url)


class ToJsonFilterTest(TestCase):
    """Test the tojson template filter."""

    def test_dict_to_json(self):
        """Test converting dict to JSON."""
        data = {"key": "value", "number": 42}
        result = tojson(data)
        self.assertIn('"key"', result)
        self.assertIn('"value"', result)
        self.assertIn("42", result)

    def test_list_to_json(self):
        """Test converting list to JSON."""
        data = [1, 2, 3, "four"]
        result = tojson(data)
        self.assertIn("[", result)
        self.assertIn("1", result)
        self.assertIn('"four"', result)

    def test_string_to_json(self):
        """Test converting string to JSON."""
        data = "hello world"
        result = tojson(data)
        self.assertEqual(result, '"hello world"')

    def test_number_to_json(self):
        """Test converting number to JSON."""
        result = tojson(42)
        self.assertEqual(result, "42")

    def test_boolean_to_json(self):
        """Test converting boolean to JSON."""
        result = tojson(True)
        self.assertEqual(result, "true")

    def test_none_to_json(self):
        """Test converting None to JSON."""
        result = tojson(None)
        self.assertEqual(result, "null")

    def test_nested_structure(self):
        """Test converting nested data structures."""
        data = {
            "users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}],
            "count": 2,
        }
        result = tojson(data)
        self.assertIn("Alice", result)
        self.assertIn("Bob", result)
        self.assertIn("30", result)


class PaginationUrlTest(TestCase):
    """Test the pagination_url template tag."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_basic_pagination_url(self):
        """Test basic pagination URL generation."""
        request = self.factory.get("/games/")
        context = {"request": request}
        url = pagination_url(context, 2)
        self.assertEqual(url, "/games/?page=2")

    def test_preserves_existing_query_params(self):
        """Test that existing query parameters are preserved."""
        request = self.factory.get("/games/?decade=1990-99&year=1995")
        context = {"request": request}
        url = pagination_url(context, 3)
        self.assertIn("page=3", url)
        self.assertIn("decade=1990-99", url)
        self.assertIn("year=1995", url)

    def test_replaces_existing_page_param(self):
        """Test that existing page parameter is replaced."""
        request = self.factory.get("/games/?page=1&decade=2000-09")
        context = {"request": request}
        url = pagination_url(context, 5)
        self.assertIn("page=5", url)
        self.assertNotIn("page=1", url)
        self.assertIn("decade=2000-09", url)

    def test_preserves_search_query(self):
        """Test that search queries are preserved."""
        request = self.factory.get("/games/search/?q=zelda&start=1990&end=2000")
        context = {"request": request}
        url = pagination_url(context, 2)
        self.assertIn("page=2", url)
        self.assertIn("q=zelda", url)
        self.assertIn("start=1990", url)
        self.assertIn("end=2000", url)

    def test_handles_empty_query_string(self):
        """Test URL generation with no existing query parameters."""
        request = self.factory.get("/developers/")
        context = {"request": request}
        url = pagination_url(context, 1)
        self.assertEqual(url, "/developers/?page=1")
