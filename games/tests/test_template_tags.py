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
    genre_icon,
    get_list_type_label,
    markdown,
    pagination_pages,
    pagination_url,
    platform_families,
    platform_families_grouped,
    platform_icon,
    platform_svg_icon,
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
        # Note: from_now is now in core.templatetags.core_filters
        valid_datetime = timezone.now()
        with patch(
            "core.templatetags.core_filters.timezone.now",
            side_effect=Exception("Test error"),
        ):
            result = from_now(valid_datetime)
            self.assertEqual(result, "")


class GameRankUrlTest(TestCase):
    """Test the game_rank_url template tag."""

    def test_basic_rank_url_no_params(self):
        """Test basic rank URL returns base games path with no params."""
        url = game_rank_url(150)
        self.assertEqual(url, "/")
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


class PlatformIconFilterTest(TestCase):
    """Test the platform_icon template filter."""

    def _make_platform(self, code):
        """Create a mock platform with code."""
        p = Mock()
        p.code = code
        return p

    def test_playstation_icon(self):
        """Test PlayStation platform returns correct icon."""
        platform = self._make_platform("PS5")
        result = platform_icon(platform)
        self.assertEqual(result, "mdi-sony-playstation")

    def test_xbox_icon(self):
        """Test Xbox platform returns correct icon."""
        platform = self._make_platform("XBXS")
        result = platform_icon(platform)
        self.assertEqual(result, "mdi-microsoft-xbox")

    def test_nintendo_switch_icon(self):
        """Test Nintendo Switch returns correct icon."""
        platform = self._make_platform("SW")  # SW is the code for Nintendo Switch
        result = platform_icon(platform)
        self.assertEqual(result, "mdi-nintendo-switch")

    def test_pc_icon(self):
        """Test PC platform returns correct icon."""
        platform = self._make_platform("WIN")  # WIN is the code for Windows/PC
        result = platform_icon(platform)
        self.assertEqual(result, "mdi-microsoft-windows")

    def test_string_platform(self):
        """Test passing string instead of object."""
        result = platform_icon("PS5")
        self.assertEqual(result, "mdi-sony-playstation")

    def test_unknown_platform_returns_none(self):
        """Test unknown platform returns None."""
        platform = self._make_platform("UNKNOWN_PLATFORM")
        result = platform_icon(platform)
        self.assertIsNone(result)


class PlatformSvgIconFilterTest(TestCase):
    """Test the platform_svg_icon template filter."""

    def _make_platform(self, code):
        """Create a mock platform with code."""
        p = Mock()
        p.code = code
        return p

    def test_sega_returns_svg_icon(self):
        """Test Sega platform returns SVG icon ID."""
        platform = self._make_platform("GEN")  # GEN is the code for Genesis
        result = platform_svg_icon(platform)
        self.assertEqual(result, "platform-sega")

    def test_playstation_returns_none(self):
        """Test PlayStation returns None (uses MDI icon)."""
        platform = self._make_platform("PS5")
        result = platform_svg_icon(platform)
        self.assertIsNone(result)

    def test_string_platform(self):
        """Test passing string instead of object."""
        result = platform_svg_icon("GEN")  # GEN is the code for Genesis
        self.assertEqual(result, "platform-sega")

    def test_unknown_platform_returns_none(self):
        """Test unknown platform returns None."""
        platform = self._make_platform("UNKNOWN_PLATFORM")
        result = platform_svg_icon(platform)
        self.assertIsNone(result)


class PlatformFamiliesGroupedFilterTest(TestCase):
    """Test the platform_families_grouped template filter."""

    def _make_platform(self, code, id, name, year_start=None, year_end=None):
        """Create a mock platform with year data."""
        p = Mock()
        p.code = code
        p.id = id
        p.name = name
        p.year_start = year_start
        p.year_end = year_end
        return p

    def test_groups_same_family_platforms(self):
        """Test that platforms in same family are grouped."""
        ps4 = self._make_platform("PS4", 1, "PlayStation 4", 2013, 2027)
        ps5 = self._make_platform("PS5", 2, "PlayStation 5", 2020, None)
        result = platform_families_grouped([ps4, ps5])
        # Should have one group
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["key"], "playstation")
        self.assertEqual(result[0]["count"], 2)
        self.assertIn("1", result[0]["platform_ids_str"])
        self.assertIn("2", result[0]["platform_ids_str"])

    def test_different_families(self):
        """Test platforms from different families create separate groups."""
        ps5 = self._make_platform("PS5", 1, "PlayStation 5", 2020, None)
        xbox = self._make_platform("XBXS", 2, "Xbox Series X", 2020, None)
        result = platform_families_grouped([ps5, xbox])
        self.assertEqual(len(result), 2)
        keys = [r["key"] for r in result]
        self.assertIn("playstation", keys)
        self.assertIn("xbox", keys)

    def test_unknown_platform_skipped(self):
        """Test that platforms with unknown family keys are skipped."""
        unknown = self._make_platform("UNKNOWN_CODE", 1, "Unknown Platform")
        result = platform_families_grouped([unknown])
        self.assertEqual(result, [])

    def test_tooltip_contains_all_names(self):
        """Test tooltip contains all platform names."""
        ps4 = self._make_platform("PS4", 1, "PlayStation 4", 2013, 2027)
        ps5 = self._make_platform("PS5", 2, "PlayStation 5", 2020, None)
        result = platform_families_grouped([ps4, ps5])
        self.assertIn("PlayStation 4", result[0]["tooltip"])
        self.assertIn("PlayStation 5", result[0]["tooltip"])

    def test_empty_list_returns_empty(self):
        """Test empty list returns empty result."""
        result = platform_families_grouped([])
        self.assertEqual(result, [])

    def test_platforms_sorted_by_year_start(self):
        """Test platforms within a family are sorted by year_start, year_end, name."""
        # Create platforms out of order
        ps5 = self._make_platform("PS5", 1, "PlayStation 5", 2020, None)
        ps2 = self._make_platform("PS2", 2, "PlayStation 2", 2000, 2013)
        ps4 = self._make_platform("PS4", 3, "PlayStation 4", 2013, 2027)
        result = platform_families_grouped([ps5, ps2, ps4])
        # Should be sorted: PS2 (2000), PS4 (2013), PS5 (2020)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["platforms"][0]["code"], "PS2")
        self.assertEqual(result[0]["platforms"][1]["code"], "PS4")
        self.assertEqual(result[0]["platforms"][2]["code"], "PS5")

    def test_families_sorted_by_first_platform(self):
        """Test families are ordered by their first platform's sort position."""
        # PlayStation 5 (2020) vs NES (1983) - NES should come first
        ps5 = self._make_platform("PS5", 1, "PlayStation 5", 2020, None)
        nes = self._make_platform("NES", 2, "Nintendo Entertainment System", 1983, 2003)
        result = platform_families_grouped([ps5, nes])
        # Nintendo (NES 1983) should come before PlayStation (PS5 2020)
        self.assertEqual(result[0]["key"], "nintendo")
        self.assertEqual(result[1]["key"], "playstation")


class GenreIconFilterTest(TestCase):
    """Test the genre_icon template filter."""

    def _make_genre(self, name, parent_name=None, level=1):
        """Create a mock genre."""
        g = Mock()
        g.name = name
        g.level = level
        if parent_name:
            g.parent = Mock()
            g.parent.name = parent_name
        else:
            g.parent = None
        return g

    def test_genre_with_parent_returns_parent_icon(self):
        """Test genre with parent returns parent's icon."""
        fighting = self._make_genre("Fighting", parent_name="Action")
        result = genre_icon(fighting)
        self.assertEqual(result, "mdi-run-fast")

    def test_category_genre_returns_own_icon(self):
        """Test top-level category returns its own icon."""
        action = self._make_genre("Action", parent_name=None, level=0)
        result = genre_icon(action)
        self.assertEqual(result, "mdi-run-fast")

    def test_string_category_name(self):
        """Test passing category name string directly."""
        result = genre_icon("Action")
        self.assertEqual(result, "mdi-run-fast")

    def test_unknown_category_returns_default(self):
        """Test unknown category returns default icon."""
        unknown = self._make_genre("Unknown Genre", parent_name="Unknown Category")
        result = genre_icon(unknown)
        self.assertEqual(result, "mdi-gamepad-variant")

    def test_genre_name_matches_category(self):
        """Test genre whose name matches category gets correct icon."""
        # Genre with name that matches a category but no parent
        rpg = self._make_genre("Role-Playing", parent_name=None, level=1)
        result = genre_icon(rpg)
        self.assertEqual(result, "mdi-wizard-hat")

    def test_adventure_icon(self):
        """Test Adventure category icon."""
        result = genre_icon("Adventure")
        self.assertEqual(result, "mdi-image-filter-hdr")

    def test_strategy_icon(self):
        """Test Strategy category icon."""
        result = genre_icon("Strategy")
        self.assertEqual(result, "mdi-chess-knight")

    def test_genre_without_name_attribute_returns_default(self):
        """Test genre object without name attribute returns default icon."""
        # Create an object that has no 'name' attribute
        genre_without_name = Mock(spec=[])  # Empty spec means no attributes
        result = genre_icon(genre_without_name)
        self.assertEqual(result, "mdi-gamepad-variant")

    def test_none_genre_returns_default(self):
        """Test None returns default icon."""
        result = genre_icon(None)
        self.assertEqual(result, "mdi-gamepad-variant")


class FormatPlaytimeFilterTest(TestCase):
    """Test the format_playtime template filter."""

    def test_hours_formatting(self):
        """Test formatting hours as hours."""
        from games.templatetags.game_filters import format_playtime

        self.assertEqual(format_playtime(10), "~10h")
        self.assertEqual(format_playtime(100), "~100h")
        self.assertEqual(format_playtime(1.5), "~2h")  # Rounds to nearest hour

    def test_minutes_formatting(self):
        """Test formatting partial hours as minutes."""
        from games.templatetags.game_filters import format_playtime

        self.assertEqual(format_playtime(0.5), "~30m")
        self.assertEqual(format_playtime(0.25), "~15m")
        self.assertEqual(format_playtime(0.1), "~6m")

    def test_none_returns_empty(self):
        """Test that None returns empty string."""
        from games.templatetags.game_filters import format_playtime

        self.assertEqual(format_playtime(None), "")

    def test_invalid_type_returns_empty(self):
        """Test that invalid type returns empty string."""
        from games.templatetags.game_filters import format_playtime

        self.assertEqual(format_playtime("invalid"), "")
        self.assertEqual(format_playtime([1, 2, 3]), "")

    def test_exact_one_hour(self):
        """Test formatting exactly 1 hour."""
        from games.templatetags.game_filters import format_playtime

        self.assertEqual(format_playtime(1), "~1h")


class GetDeveloperIdsFilterTest(TestCase):
    """Test the get_developer_ids template filter."""

    def test_returns_developer_ids(self):
        """Test getting developer IDs from mapping."""
        from games.templatetags.game_filters import get_developer_ids

        game_dev_map = {1: [10, 20, 30], 2: [40, 50]}
        result = get_developer_ids(game_dev_map, 1)
        self.assertEqual(result, [10, 20, 30])

    def test_missing_game_returns_empty(self):
        """Test missing game ID returns empty list."""
        from games.templatetags.game_filters import get_developer_ids

        game_dev_map = {1: [10, 20]}
        result = get_developer_ids(game_dev_map, 999)
        self.assertEqual(result, [])

    def test_none_map_returns_empty(self):
        """Test None mapping returns empty list."""
        from games.templatetags.game_filters import get_developer_ids

        result = get_developer_ids(None, 1)
        self.assertEqual(result, [])

    def test_non_dict_returns_empty(self):
        """Test non-dict mapping returns empty list."""
        from games.templatetags.game_filters import get_developer_ids

        result = get_developer_ids([1, 2, 3], 1)
        self.assertEqual(result, [])


class ChildDeveloperIdsFilterTest(TestCase):
    """Test the child_developer_ids template filter."""

    def test_extracts_developer_ids(self):
        """Test extracting IDs from sub_developers list."""
        from games.templatetags.game_filters import child_developer_ids

        sub_devs = [
            {"developer": Mock(id=1)},
            {"developer": Mock(id=2)},
            {"developer": Mock(id=3)},
        ]
        result = child_developer_ids(sub_devs)
        self.assertEqual(result, [1, 2, 3])

    def test_empty_list_returns_empty(self):
        """Test empty list returns empty list."""
        from games.templatetags.game_filters import child_developer_ids

        result = child_developer_ids([])
        self.assertEqual(result, [])

    def test_none_returns_empty(self):
        """Test None returns empty list."""
        from games.templatetags.game_filters import child_developer_ids

        result = child_developer_ids(None)
        self.assertEqual(result, [])


class HasPublishedArticlesTagTest(TestCase):
    """Test the has_published_articles template tag."""

    def test_returns_false_when_no_articles(self):
        """Test returns False when no published articles exist."""
        from games.templatetags.game_filters import has_published_articles

        result = has_published_articles()
        self.assertFalse(result)

    def test_returns_true_with_published_article(self):
        """Test returns True when published article exists."""
        from core.models import User
        from games.models import Article
        from games.templatetags.game_filters import has_published_articles

        author = User.objects.create_user(username="author", email="author@test.com")
        Article.objects.create(
            title="Test Article",
            slug="test-article",
            content="Test content",
            author=author,
            status=Article.Status.PUBLISHED,
        )

        result = has_published_articles()
        self.assertTrue(result)

    def test_returns_false_with_only_draft(self):
        """Test returns False when only draft articles exist."""
        from core.models import User
        from games.models import Article
        from games.templatetags.game_filters import has_published_articles

        author = User.objects.create_user(username="author2", email="author2@test.com")
        Article.objects.create(
            title="Draft Article",
            slug="draft-article",
            content="Draft content",
            author=author,
            status=Article.Status.DRAFT,
        )

        result = has_published_articles()
        self.assertFalse(result)
