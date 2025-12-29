"""Tests for game_filter_service module."""

from django.test import TestCase, RequestFactory

from games import models
from games.services.game_filter_service import (
    GameFilters,
    apply_game_filters,
    get_filter_context_from_request,
)


class GameFiltersFromRequestTests(TestCase):
    """Tests for GameFilters.from_request() method."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_empty_request_creates_default_filters(self):
        """Empty request should create filters with default values."""
        request = self.factory.get("/games/")
        filters = GameFilters.from_request(request)

        self.assertIsNone(filters.q)
        self.assertEqual(filters.genres, [])
        self.assertEqual(filters.platforms, [])
        self.assertIsNone(filters.start)
        self.assertIsNone(filters.end)
        self.assertIsNone(filters.decade)
        self.assertIsNone(filters.year)
        self.assertIsNone(filters.developer_igdb_id)

    def test_parses_search_query(self):
        """Should parse q parameter and strip whitespace."""
        request = self.factory.get("/games/", {"q": "  zelda  "})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.q, "zelda")

    def test_parses_genres(self):
        """Should parse comma-separated genre IDs."""
        request = self.factory.get("/games/", {"genres": "1,2,3"})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.genres, [1, 2, 3])

    def test_parses_platforms(self):
        """Should parse comma-separated platform IDs."""
        request = self.factory.get("/games/", {"platforms": "10,20"})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.platforms, [10, 20])

    def test_parses_year_range(self):
        """Should parse start and end year parameters."""
        request = self.factory.get("/games/", {"start": "1990", "end": "2000"})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.start, 1990)
        self.assertEqual(filters.end, 2000)

    def test_parses_decade(self):
        """Should parse decade parameter."""
        request = self.factory.get("/games/", {"decade": "1990-99"})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.decade, "1990-99")

    def test_parses_year(self):
        """Should parse single year parameter."""
        request = self.factory.get("/games/", {"year": "1998"})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.year, "1998")

    def test_parses_developer(self):
        """Should parse developer parameter."""
        request = self.factory.get("/games/", {"developer": "12345"})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.developer_igdb_id, 12345)

    def test_invalid_genres_ignored(self):
        """Invalid genre values should be ignored."""
        request = self.factory.get("/games/", {"genres": "abc,def"})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.genres, [])

    def test_invalid_platforms_ignored(self):
        """Invalid platform values should be ignored."""
        request = self.factory.get("/games/", {"platforms": "xyz"})
        filters = GameFilters.from_request(request)
        self.assertEqual(filters.platforms, [])

    def test_invalid_year_values_ignored(self):
        """Invalid year values should be ignored."""
        request = self.factory.get("/games/", {"start": "abc", "end": "xyz"})
        filters = GameFilters.from_request(request)
        self.assertIsNone(filters.start)
        self.assertIsNone(filters.end)

    def test_invalid_developer_ignored(self):
        """Invalid developer value should be ignored."""
        request = self.factory.get("/games/", {"developer": "invalid"})
        filters = GameFilters.from_request(request)
        self.assertIsNone(filters.developer_igdb_id)


class GameFiltersPropertiesTests(TestCase):
    """Tests for GameFilters properties."""

    def test_is_filtered_empty(self):
        """Empty filters should return is_filtered=False."""
        filters = GameFilters()
        self.assertFalse(filters.is_filtered)

    def test_is_filtered_with_query(self):
        """Filter with search query should return is_filtered=True."""
        filters = GameFilters(q="zelda")
        self.assertTrue(filters.is_filtered)

    def test_is_filtered_with_genres(self):
        """Filter with genres should return is_filtered=True."""
        filters = GameFilters(genres=[1, 2])
        self.assertTrue(filters.is_filtered)

    def test_is_filtered_with_platforms(self):
        """Filter with platforms should return is_filtered=True."""
        filters = GameFilters(platforms=[1])
        self.assertTrue(filters.is_filtered)

    def test_is_filtered_with_decade(self):
        """Filter with decade should return is_filtered=True."""
        filters = GameFilters(decade="1990-99")
        self.assertTrue(filters.is_filtered)

    def test_is_filtered_with_year(self):
        """Filter with year should return is_filtered=True."""
        filters = GameFilters(year="1998")
        self.assertTrue(filters.is_filtered)

    def test_is_filtered_with_start(self):
        """Filter with start year should return is_filtered=True."""
        filters = GameFilters(start=1990)
        self.assertTrue(filters.is_filtered)

    def test_is_filtered_with_developer(self):
        """Filter with developer should return is_filtered=True."""
        filters = GameFilters(developer_igdb_id=123)
        self.assertTrue(filters.is_filtered)


class ApplyGameFiltersTests(TestCase):
    """Tests for apply_game_filters function."""

    def setUp(self):
        """Create test data."""
        self.genre_action = models.IGDBGenre.objects.create(name="Action")
        self.genre_rpg = models.IGDBGenre.objects.create(name="RPG")
        self.platform_pc = models.Platform.objects.create(code="PC", name="PC")
        self.platform_ps5 = models.Platform.objects.create(
            code="PS5", name="PlayStation 5"
        )

        # Create developer
        self.developer = models.Developer.objects.create(
            name="TestDev", slug="testdev", igdb_id=999
        )

        # Create games
        self.game1 = models.Game.objects.create(
            name="Zelda", rank=1, year_of_release=1998, igdb_id=1
        )
        self.game1.genres.add(self.genre_action)
        self.game1.platforms.add(self.platform_pc)
        self.game1.developers.add(self.developer)

        self.game2 = models.Game.objects.create(
            name="Final Fantasy", rank=2, year_of_release=1997, igdb_id=2
        )
        self.game2.genres.add(self.genre_rpg)
        self.game2.platforms.add(self.platform_ps5)

        self.game3 = models.Game.objects.create(
            name="Action RPG", rank=3, year_of_release=2005, igdb_id=3
        )
        self.game3.genres.add(self.genre_action, self.genre_rpg)
        self.game3.platforms.add(self.platform_pc, self.platform_ps5)

    def test_no_filters_returns_all(self):
        """Empty filters should return all games."""
        filters = GameFilters()
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 3)

    def test_search_filter(self):
        """Search filter should match game names."""
        filters = GameFilters(q="zelda")
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().name, "Zelda")

    def test_genre_filter_single(self):
        """Single genre filter should work (single-select mode)."""
        filters = GameFilters(genres=[self.genre_action.id])
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 2)  # Zelda and Action RPG

    def test_platform_filter(self):
        """Platform filter should work."""
        filters = GameFilters(platforms=[self.platform_pc.id])
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 2)  # Zelda and Action RPG

    def test_year_range_filter(self):
        """Year range filter should work."""
        filters = GameFilters(start=1997, end=1998)
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 2)  # Zelda and Final Fantasy

    def test_decade_filter(self):
        """Decade filter should work."""
        filters = GameFilters(decade="1990-99")
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 2)  # Zelda and Final Fantasy

    def test_single_year_filter(self):
        """Single year filter should work."""
        filters = GameFilters(year="1998")
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().name, "Zelda")

    def test_developer_filter(self):
        """Developer filter should work."""
        filters = GameFilters(developer_igdb_id=999)
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().name, "Zelda")

    def test_combined_filters(self):
        """Multiple filters should combine correctly."""
        filters = GameFilters(
            genres=[self.genre_action.id], platforms=[self.platform_pc.id]
        )
        qs = models.Game.objects.all()
        result = apply_game_filters(qs, filters)
        self.assertEqual(result.count(), 2)  # Zelda and Action RPG


class GetFilterContextTests(TestCase):
    """Tests for get_filter_context_from_request function."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_empty_request_returns_defaults(self):
        """Empty request should return default context."""
        request = self.factory.get("/games/")
        context = get_filter_context_from_request(request, min_year=1970, max_year=2025)

        self.assertEqual(context["q"], "")
        self.assertEqual(context["start"], 1970)
        self.assertEqual(context["end"], 2025)
        self.assertEqual(context["genres"], [])
        self.assertEqual(context["platforms"], [])

    def test_request_with_filters_populates_context(self):
        """Request with filters should populate context correctly."""
        request = self.factory.get(
            "/games/",
            {
                "q": "zelda",
                "start": "1990",
                "end": "2000",
                "genres": "1",
                "platforms": "3",
            },
        )
        context = get_filter_context_from_request(request, min_year=1970, max_year=2025)

        self.assertEqual(context["q"], "zelda")
        self.assertEqual(context["start"], 1990)
        self.assertEqual(context["end"], 2000)
        self.assertEqual(context["genres"], ["1"])  # Single-select mode
        self.assertEqual(context["platforms"], ["3"])  # Strings for HTML select

    def test_uses_current_year_as_default_max(self):
        """Should use current year as default max_year."""
        from datetime import datetime

        request = self.factory.get("/games/")
        context = get_filter_context_from_request(request, min_year=1970)
        self.assertEqual(context["end"], datetime.today().year)
