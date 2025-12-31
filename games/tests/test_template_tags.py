from datetime import timedelta
from unittest.mock import Mock

from django.core.paginator import Paginator
from django.test import RequestFactory, TestCase
from django.utils import timezone

from games.templatetags.game_filters import (
    format_decade,
    format_duration,
    from_now,
    game_rank_url,
    get_list_type_label,
    markdown,
    pagination_pages,
    pagination_url,
    platform_families,
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

    def test_second_page_uses_min_distance_3(self):
        """Test that second page (page 2) uses min_distance=3."""
        page_obj = self._create_page_obj(2, 20)
        result = pagination_pages(page_obj)
        # At page 2 with min_distance=3, pages 1-4 should be included
        self.assertIn(1, result)
        self.assertIn(2, result)
        self.assertIn(3, result)
        self.assertIn(4, result)

    def test_second_last_page_uses_min_distance_3(self):
        """Test that second-to-last page uses min_distance=3."""
        page_obj = self._create_page_obj(19, 20)
        result = pagination_pages(page_obj)
        # At page 19 with min_distance=3, pages 17-20 should be included
        self.assertIn(17, result)
        self.assertIn(18, result)
        self.assertIn(19, result)
        self.assertIn(20, result)


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

    def test_future_date_returns_in_x(self):
        """Test that future dates return 'in X' format."""
        now = timezone.now()
        future = now + timedelta(days=5)
        result = from_now(future)
        self.assertIn("in ", result)
        self.assertIn("day", result)
        self.assertNotIn("ago", result)

    def test_future_hours(self):
        """Test future hours formatting."""
        now = timezone.now()
        future = now + timedelta(hours=3)
        result = from_now(future)
        self.assertIn("in ", result)
        self.assertIn("hour", result)

    def test_future_minutes(self):
        """Test future minutes formatting."""
        now = timezone.now()
        future = now + timedelta(minutes=15)
        result = from_now(future)
        self.assertIn("in ", result)
        self.assertIn("minute", result)

    def test_future_months(self):
        """Test future months formatting."""
        now = timezone.now()
        future = now + timedelta(days=60)
        result = from_now(future)
        self.assertIn("in ", result)
        self.assertIn("month", result)

    def test_future_years(self):
        """Test future years formatting."""
        now = timezone.now()
        future = now + timedelta(days=400)
        result = from_now(future)
        self.assertIn("in ", result)
        self.assertIn("year", result)

    def test_exception_returns_empty_string(self):
        """Test that exceptions during calculation return empty string."""
        from unittest.mock import patch

        # Pass a valid datetime but mock timezone.now to raise inside from_now
        valid_datetime = timezone.now()
        with patch(
            "games.templatetags.game_filters.timezone.now",
            side_effect=Exception("Test error"),
        ):
            result = from_now(valid_datetime)
            self.assertEqual(result, "")


class GameRankUrlTest(TestCase):
    """Test the game_rank_url template tag."""

    def test_basic_rank_url_no_params(self):
        """Test basic rank URL returns base games path with no params."""
        url = game_rank_url(150)
        self.assertEqual(url, "/rankings/")
        self.assertNotIn("page=", url)  # No page param - view handles dynamic loading

    def test_rank_with_game_id_highlight(self):
        """Test rank URL with game ID for highlighting."""
        url = game_rank_url(50, game_id=123)
        self.assertNotIn("page=", url)  # No page param
        self.assertIn("highlight=123", url)

    def test_rank_with_single_year_filter(self):
        """Test rank URL with single year uses start/end params."""
        url = game_rank_url(25, start=2020, end=2020)
        self.assertIn("start=2020", url)
        self.assertIn("end=2020", url)
        self.assertNotIn("year=", url)  # No legacy year param
        self.assertNotIn("decade=", url)
        self.assertNotIn("page=", url)

    def test_rank_with_decade_range(self):
        """Test rank URL with decade range uses start/end params."""
        url = game_rank_url(25, start=1990, end=1999)
        self.assertIn("start=1990", url)
        self.assertIn("end=1999", url)
        self.assertNotIn("decade=", url)  # No legacy decade param
        self.assertNotIn("page=", url)

    def test_rank_with_custom_range(self):
        """Test rank URL with custom year range."""
        url = game_rank_url(25, start=2015, end=2020)
        self.assertIn("start=2015", url)
        self.assertIn("end=2020", url)
        self.assertNotIn("decade=", url)
        self.assertNotIn("year=", url)
        self.assertNotIn("page=", url)

    def test_rank_with_only_start(self):
        """Test rank URL with only start year."""
        url = game_rank_url(25, start=2010)
        self.assertIn("start=2010", url)
        self.assertNotIn("end=", url)
        self.assertNotIn("page=", url)

    def test_rank_with_only_end(self):
        """Test rank URL with only end year."""
        url = game_rank_url(25, end=2020)
        self.assertIn("end=2020", url)
        self.assertNotIn("start=", url)
        self.assertNotIn("page=", url)

    def test_highlight_with_year_filter(self):
        """Test rank URL with both highlight and year filter."""
        url = game_rank_url(150, game_id=456, start=2020, end=2020)
        self.assertIn("highlight=456", url)
        self.assertIn("start=2020", url)
        self.assertIn("end=2020", url)
        self.assertNotIn("page=", url)

    def test_highlight_with_decade_range(self):
        """Test rank URL with both highlight and decade range."""
        url = game_rank_url(150, game_id=789, start=1990, end=1999)
        self.assertIn("highlight=789", url)
        self.assertIn("start=1990", url)
        self.assertIn("end=1999", url)
        self.assertNotIn("page=", url)


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


class GetListTypeLabelTest(TestCase):
    """Test the get_list_type_label template filter."""

    def test_all_time_type(self):
        """Test that 'A' returns 'All time'."""
        self.assertEqual(get_list_type_label("A"), "All time")

    def test_end_of_year_type(self):
        """Test that 'E' returns 'End of year'."""
        self.assertEqual(get_list_type_label("E"), "End of year")

    def test_miscellaneous_type(self):
        """Test that 'M' returns 'Miscellaneous'."""
        self.assertEqual(get_list_type_label("M"), "Miscellaneous")

    def test_decade_type(self):
        """Test that 'D' returns 'Decade'."""
        self.assertEqual(get_list_type_label("D"), "Decade")

    def test_unknown_type_returns_code(self):
        """Test that unknown type code returns the code itself."""
        self.assertEqual(get_list_type_label("X"), "X")


class FormatDecadeFilterTest(TestCase):
    """Test the format_decade template filter."""

    def test_format_1990s(self):
        """Test formatting 1990s decade."""
        self.assertEqual(format_decade("1990-99"), "1990s")

    def test_format_2000s(self):
        """Test formatting 2000s decade."""
        self.assertEqual(format_decade("2000-09"), "2000s")

    def test_format_2010s(self):
        """Test formatting 2010s decade."""
        self.assertEqual(format_decade("2010-19"), "2010s")

    def test_empty_value_returns_empty_string(self):
        """Test that empty/None value returns empty string."""
        self.assertEqual(format_decade(None), "")
        self.assertEqual(format_decade(""), "")

    def test_value_without_dash(self):
        """Test that value without dash uses the whole value."""
        self.assertEqual(format_decade("1990"), "1990s")


class FormatDurationFilterTest(TestCase):
    """Test the format_duration template filter."""

    def test_seconds_only(self):
        """Test formatting for seconds only."""
        self.assertEqual(format_duration(30), "30s")

    def test_minutes_and_seconds(self):
        """Test formatting for minutes and seconds."""
        self.assertEqual(format_duration(90), "1m 30s")

    def test_minutes_only(self):
        """Test formatting for exact minutes."""
        self.assertEqual(format_duration(120), "2m")

    def test_hours_and_minutes(self):
        """Test formatting for hours and minutes."""
        self.assertEqual(format_duration(3660), "1h 1m")

    def test_hours_only(self):
        """Test formatting for exact hours."""
        self.assertEqual(format_duration(3600), "1h")

    def test_zero_returns_zero_seconds(self):
        """Test that 0 returns '0s'."""
        self.assertEqual(format_duration(0), "0s")

    def test_none_returns_zero_seconds(self):
        """Test that None returns '0s'."""
        self.assertEqual(format_duration(None), "0s")

    def test_negative_returns_zero_seconds(self):
        """Test that negative returns '0s'."""
        self.assertEqual(format_duration(-10), "0s")


class PlatformFamiliesFilterTest(TestCase):
    """Test the platform_families template filter."""

    def _make_platform(self, code, id, name):
        """Create a mock platform with proper attributes."""
        p = Mock()
        p.code = code
        p.id = id
        p.name = name
        return p

    def test_returns_unique_families(self):
        """Test that duplicate platform families are deduplicated."""
        # Create mock platforms in same family (PS4 and PS5)
        ps4 = self._make_platform("PS4", 1, "PlayStation 4")
        ps5 = self._make_platform("PS5", 2, "PlayStation 5")
        result = platform_families([ps4, ps5])
        # Should only have one PlayStation family
        family_keys = [f["key"] for f in result]
        self.assertEqual(family_keys.count("playstation"), 1)

    def test_preserves_encounter_order(self):
        """Test that families are returned in encounter order."""
        # Use correct platform codes: XBXS for Xbox Series, PS5 for PlayStation 5
        xbox = self._make_platform("XBXS", 1, "Xbox Series X")
        ps5 = self._make_platform("PS5", 2, "PlayStation 5")
        result = platform_families([xbox, ps5])
        # Xbox encountered first
        self.assertEqual(result[0]["key"], "xbox")
        self.assertEqual(result[1]["key"], "playstation")

    def test_includes_platform_info(self):
        """Test that result includes platform ID and name."""
        ps5 = self._make_platform("PS5", 42, "PlayStation 5")
        result = platform_families([ps5])
        self.assertEqual(result[0]["platform_id"], 42)
        self.assertEqual(result[0]["platform_name"], "PlayStation 5")

    def test_empty_list_returns_empty(self):
        """Test that empty list returns empty list."""
        result = platform_families([])
        self.assertEqual(result, [])


class MarkdownFilterTest(TestCase):
    """Test the markdown template filter."""

    def test_bold_text(self):
        """Test that bold markdown is converted."""
        result = markdown("**bold text**")
        self.assertIn("<strong>", result)
        self.assertIn("bold text", result)

    def test_italic_text(self):
        """Test that italic markdown is converted."""
        result = markdown("*italic text*")
        self.assertIn("<em>", result)
        self.assertIn("italic text", result)

    def test_empty_value_returns_empty(self):
        """Test that empty value returns empty string."""
        self.assertEqual(markdown(None), "")
        self.assertEqual(markdown(""), "")
