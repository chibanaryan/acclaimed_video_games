"""
Tests for main site views (Django + HTMX + Alpine.js).

Comprehensive test coverage for all user-facing views.
"""

from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from games.models import (
    Company,
    Studio,
    Game,
    IGDBGenre,
    List,
    ListMembership,
    Platform,
    Post,
    Publication,
    SiteMetadata,
    WikipediaGenre,
)


class HomePageViewTest(TestCase):
    """Test the home page view."""

    def setUp(self):
        # Create test data
        self.site_metadata = SiteMetadata.objects.create()

        # Create games
        self.game1 = Game.objects.create(
            name="Test Game 1", rank=1, year_of_release=2020
        )
        self.game2 = Game.objects.create(
            name="Test Game 2", rank=2, year_of_release=2021
        )

        # Create posts
        self.post1 = Post.objects.create(title="Post 1", text="Content 1", active=True)
        self.post2 = Post.objects.create(title="Post 2", text="Content 2", active=True)

        # Create lists and publications for counts
        pub = Publication.objects.create(name="Test Pub")
        List.objects.create(name="List 1", publisher=pub, year=2020, type="A")

    def test_home_page_loads(self):
        """Test that home page loads successfully."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")

    def test_context_contains_posts(self):
        """Test that context includes latest posts."""
        response = self.client.get(reverse("home"))
        self.assertIn("posts", response.context)
        posts = list(response.context["posts"])
        self.assertTrue(len(posts) > 0)

    def test_context_contains_top_games(self):
        """Test that context includes top 10 games."""
        response = self.client.get(reverse("home"))
        self.assertIn("games", response.context)
        games = list(response.context["games"])
        self.assertEqual(len(games), 2)  # We created 2 games

    def test_context_contains_counts(self):
        """Test that context includes list and publication counts."""
        response = self.client.get(reverse("home"))
        self.assertIn("list_count", response.context)
        self.assertIn("publication_count", response.context)
        self.assertEqual(response.context["list_count"], 1)
        self.assertEqual(response.context["publication_count"], 1)

    def test_context_contains_last_update(self):
        """Test that context includes last update metadata."""
        response = self.client.get(reverse("home"))
        self.assertIn("last_update", response.context)

    def test_context_contains_contact_form(self):
        """Test that context includes contact form."""
        response = self.client.get(reverse("home"))
        self.assertIn("form", response.context)

    def test_contact_form_post_valid(self):
        """Test valid contact form submission."""
        from unittest import mock

        with mock.patch("games.utils.send_contact_email", return_value=True):
            response = self.client.post(
                reverse("home"),
                {
                    "name": "Test User",
                    "email": "test@example.com",
                    "category": "general",
                    "message": "Test message",
                    "website": "",  # Honeypot
                },
            )
            # Should redirect to thank you page
            self.assertEqual(response.status_code, 302)
            self.assertRedirects(response, reverse("contact_thank_you"))

    def test_contact_form_post_invalid(self):
        """Test invalid contact form submission."""
        response = self.client.post(
            reverse("home"),
            {
                "name": "",  # Missing name
                "email": "test@example.com",
                "category": "general",
                "message": "Test message",
                "website": "",
            },
        )
        # Should stay on same page with errors
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertFalse(response.context["form"].is_valid())
        self.assertIn("name", response.context["form"].errors)

    def test_contact_form_honeypot_spam(self):
        """Test contact form with honeypot filled (spam)."""
        response = self.client.post(
            reverse("home"),
            {
                "name": "Test User",
                "email": "test@example.com",
                "category": "general",
                "message": "Test message",
                "website": "http://spam.com",  # Honeypot filled
            },
        )
        # Should stay on same page with errors
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertFalse(response.context["form"].is_valid())

    def test_contact_form_email_failure(self):
        """Test contact form when email sending fails."""
        from unittest import mock

        with mock.patch("games.utils.send_contact_email", return_value=False):
            response = self.client.post(
                reverse("home"),
                {
                    "name": "Test User",
                    "email": "test@example.com",
                    "category": "general",
                    "message": "Test message",
                    "website": "",
                },
            )
            # Should stay on same page with error
            self.assertEqual(response.status_code, 200)
            self.assertIn("form", response.context)
            self.assertFalse(response.context["form"].is_valid())


class ContactThankYouViewTest(TestCase):
    """Test the contact thank you page view."""

    def test_thank_you_page_loads(self):
        """Test that thank you page loads successfully."""
        response = self.client.get(reverse("contact_thank_you"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contact_thank_you.html")


class GameListViewTest(TestCase):
    """Test the game list view (now uses GameSearchView with legacy param support)."""

    def setUp(self):
        # Create 150 games for pagination testing
        for i in range(1, 151):
            Game.objects.create(
                name=f"Game {i}", rank=i, year_of_release=1990 + (i % 30)
            )

    def test_game_list_loads(self):
        """Test that game list page loads."""
        response = self.client.get(reverse("games-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/game_list.html")

    def test_pagination(self):
        """Test that pagination works correctly."""
        response = self.client.get(reverse("games-list"))
        self.assertIn("page_obj", response.context)
        # Should have 100 games per page
        self.assertEqual(len(response.context["games"]), 100)

    def test_second_page(self):
        """Test accessing second page."""
        response = self.client.get(reverse("games-list") + "?page=2")
        self.assertEqual(response.status_code, 200)
        # Second page should have 50 games (150 total - 100 on first page)
        self.assertEqual(len(response.context["games"]), 50)

    def test_decade_filter(self):
        """Test filtering by decade (legacy param support)."""
        response = self.client.get(reverse("games-list") + "?decade=1990-99")
        self.assertEqual(response.status_code, 200)
        # All games should be from 1990-1999
        for game in response.context["games"]:
            self.assertGreaterEqual(game.year_of_release, 1990)
            self.assertLessEqual(game.year_of_release, 1999)

    def test_year_filter(self):
        """Test filtering by single year (legacy param support)."""
        response = self.client.get(reverse("games-list") + "?year=1995")
        self.assertEqual(response.status_code, 200)
        # All games should be from 1995
        for game in response.context["games"]:
            self.assertEqual(game.year_of_release, 1995)

    def test_htmx_request_returns_partial(self):
        """Test that HTMX requests return partial template."""
        response = self.client.get(reverse("games-list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_list_content.html")

    def test_invalid_page_returns_last_page(self):
        """Test that invalid page number returns last page."""
        response = self.client.get(reverse("games-list") + "?page=999")
        self.assertEqual(response.status_code, 200)
        # Should return the last page (page 2 with our 150 games)
        self.assertEqual(response.context["page_obj"].number, 2)

    def test_non_numeric_page_defaults_to_first(self):
        """Test that non-numeric page parameter defaults to page 1."""
        response = self.client.get(reverse("games-list") + "?page=invalid")
        self.assertEqual(response.status_code, 200)
        # Should default to first page
        self.assertEqual(response.context["page_obj"].number, 1)

    def test_context_has_filters(self):
        """Test that context includes filter information with legacy params."""
        response = self.client.get(reverse("games-list") + "?decade=2000-09")
        self.assertIn("filters", response.context)
        # Decade is preserved in filters for legacy compatibility
        self.assertEqual(response.context["filters"]["decade"], "2000-09")
        # Decade is also converted to start/end
        self.assertEqual(response.context["filters"]["start"], 2000)
        self.assertEqual(response.context["filters"]["end"], 2009)

    def test_context_has_year_counts(self):
        """Test that context includes year counts for year grid."""
        response = self.client.get(reverse("games-list"))
        self.assertIn("year_counts", response.context)

    def test_year_counts_reflects_genre_filter(self):
        """Test that year counts reflect genre filter."""
        from django.core.cache import cache

        # Clear only year-related caches to avoid affecting other tests
        cache.delete("game_year_stats")
        cache.delete("game_list_meta")

        # Use WikipediaGenre for filtering (views now use Wikipedia genres)
        action, _ = WikipediaGenre.objects.get_or_create(
            name="ActionTestGenre", defaults={"slug": "actiontest"}
        )
        rpg, _ = WikipediaGenre.objects.get_or_create(
            name="RPGTestGenre", defaults={"slug": "rpgtest"}
        )

        # Create games with specific genres and years
        # Use years covered by setUp (1990-2019 range)
        game1 = Game.objects.create(
            name="Action Game 2010", slug="action-2010", rank=200, year_of_release=2010
        )
        game1.wikipedia_genres.add(action)

        game2 = Game.objects.create(
            name="RPG Game 2015", slug="rpg-2015", rank=201, year_of_release=2015
        )
        game2.wikipedia_genres.add(rpg)

        # Without filter, both years should have counts
        response = self.client.get(reverse("games-list"))
        year_counts = {
            yc["year"]: yc["count"] for yc in response.context["year_counts"]
        }
        self.assertGreaterEqual(year_counts.get(2010, 0), 1)
        self.assertGreaterEqual(year_counts.get(2015, 0), 1)

        # With genre filter, only matching year should have count
        response = self.client.get(reverse("games-list") + f"?genres={action.id}")
        year_counts = {
            yc["year"]: yc["count"] for yc in response.context["year_counts"]
        }
        self.assertGreaterEqual(year_counts.get(2010, 0), 1)
        self.assertEqual(year_counts.get(2015, 0), 0)

    def test_year_counts_reflects_search_filter(self):
        """Test that year counts reflect search filter."""
        from django.core.cache import cache

        # Clear only year-related caches to avoid affecting other tests
        cache.delete("game_year_stats")
        cache.delete("game_list_meta")

        # Create games with distinct names and years
        # Use years covered by setUp (1990-2019 range)
        Game.objects.create(
            name="ZeldaTest Adventure",
            slug="zelda-adventure",
            rank=202,
            year_of_release=2018,
        )
        Game.objects.create(
            name="MarioTest Quest", slug="mario-quest", rank=203, year_of_release=2019
        )

        # With search filter, only matching year should have count
        response = self.client.get(reverse("games-list") + "?q=ZeldaTest")
        year_counts = {
            yc["year"]: yc["count"] for yc in response.context["year_counts"]
        }
        self.assertGreaterEqual(year_counts.get(2018, 0), 1)
        self.assertEqual(year_counts.get(2019, 0), 0)


class GameDetailViewTest(TestCase):
    """Test the game detail view."""

    def setUp(self):
        self.game = Game.objects.create(
            name="Test Game", slug="test-game", rank=1, year_of_release=2020
        )

        # Add a list membership
        pub = Publication.objects.create(name="Test Pub")
        game_list = List.objects.create(
            name="Best Games 2020", publisher=pub, year=2020, type="A"
        )
        ListMembership.objects.create(game=self.game, list=game_list, rank=1)

    def test_game_detail_loads(self):
        """Test that game detail page loads."""
        response = self.client.get(
            reverse("game-detail", kwargs={"slug": self.game.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/game_detail.html")

    def test_context_contains_game(self):
        """Test that context includes the game."""
        response = self.client.get(
            reverse("game-detail", kwargs={"slug": self.game.slug})
        )
        self.assertEqual(response.context["game"], self.game)

    def test_context_contains_grouped_lists(self):
        """Test that context includes grouped lists."""
        response = self.client.get(
            reverse("game-detail", kwargs={"slug": self.game.slug})
        )
        self.assertIn("grouped_lists", response.context)
        # Should have lists grouped by type
        self.assertTrue(len(response.context["grouped_lists"]) > 0)

    def test_invalid_slug_returns_404(self):
        """Test that invalid slug returns 404."""
        response = self.client.get(
            reverse("game-detail", kwargs={"slug": "invalid-slug"})
        )
        self.assertEqual(response.status_code, 404)

    def test_game_description_displayed_when_present(self):
        """Test that game description is displayed when it exists."""
        game_with_desc = Game.objects.create(
            name="Game With Desc",
            slug="game-with-desc",
            rank=10,
            year_of_release=2020,
            description="This is a great game with an interesting storyline.",
        )

        response = self.client.get(
            reverse("game-detail", kwargs={"slug": game_with_desc.slug})
        )

        # Description should be in the response
        self.assertContains(
            response, "This is a great game with an interesting storyline."
        )

    def test_game_description_not_shown_when_absent(self):
        """Test that page works fine when game has no description."""
        game_no_desc = Game.objects.create(
            name="Game No Desc",
            slug="game-no-desc",
            rank=11,
            year_of_release=2020,
            description="",
        )

        response = self.client.get(
            reverse("game-detail", kwargs={"slug": game_no_desc.slug})
        )

        # Page should load successfully
        self.assertEqual(response.status_code, 200)


class GameSearchViewTest(TestCase):
    """Test the game search view (at /rankings/ URL)."""

    def setUp(self):
        # Create test games with different attributes
        self.game1 = Game.objects.create(
            name="The Legend of Zelda", rank=1, year_of_release=1986
        )
        self.game2 = Game.objects.create(name="Zelda II", rank=50, year_of_release=1987)
        self.game3 = Game.objects.create(
            name="Super Mario Bros", rank=2, year_of_release=1985
        )

        # Create genres and platforms (using WikipediaGenre for filtering)
        self.action_genre, _ = WikipediaGenre.objects.get_or_create(
            name="Action", defaults={"slug": "action"}
        )
        self.rpg_genre, _ = WikipediaGenre.objects.get_or_create(
            name="Role-Playing", defaults={"slug": "role-playing"}
        )
        self.nes_platform = Platform.objects.create(name="NES", code="NES")

        self.game1.wikipedia_genres.add(self.action_genre, self.rpg_genre)
        self.game1.platforms.add(self.nes_platform)
        self.game2.wikipedia_genres.add(self.rpg_genre)
        self.game3.wikipedia_genres.add(self.action_genre)

        # Clear genre cache to ensure fresh data for each test
        cache.delete("search_wikipedia_genres_list_with_counts")

    def test_search_page_loads(self):
        """Test that search page loads."""
        response = self.client.get(reverse("games-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/game_list.html")

    def test_old_search_url_redirects(self):
        """Test that old /games/search/ URL redirects to /rankings/."""
        response = self.client.get(reverse("games-search"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/rankings/")

    def test_old_search_url_preserves_query_params(self):
        """Test that redirect preserves query parameters."""
        response = self.client.get(reverse("games-search") + "?q=zelda&page=2")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/rankings/?q=zelda&page=2")

    def test_old_games_url_redirects(self):
        """Test that old /games/ URL redirects to /rankings/."""
        response = self.client.get(reverse("games-redirect"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/rankings/")

    def test_old_games_url_preserves_query_params(self):
        """Test that /games/ redirect preserves query parameters."""
        response = self.client.get(reverse("games-redirect") + "?q=zelda&page=2")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/rankings/?q=zelda&page=2")

    def test_search_by_name(self):
        """Test searching games by name."""
        response = self.client.get(reverse("games-list") + "?q=zelda")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertEqual(len(games), 2)  # Should find both Zelda games

    def test_search_with_year_range(self):
        """Test searching with year range filter."""
        response = self.client.get(reverse("games-list") + "?start=1986&end=1987")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertEqual(len(games), 2)  # Zelda games from 1986-1987

    def test_search_with_genre_filter(self):
        """Test searching with genre filter."""
        response = self.client.get(
            reverse("games-list") + f"?genres={self.rpg_genre.id}"
        )
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Both Zelda games have RPG genre
        self.assertIn(self.game1, games)
        self.assertIn(self.game2, games)

    def test_filter_title_genre_without_video_prefix(self):
        """Test that genre filter title does not include 'Video' prefix."""
        response = self.client.get(
            reverse("games-list") + f"?genres={self.action_genre.id}"
        )
        self.assertEqual(response.status_code, 200)
        filter_title = response.context["filter_title"]
        # Should be "Action Games" not "Video Action Games"
        self.assertIn("Action Games", filter_title)
        self.assertNotIn("Video Action", filter_title)

    def test_filter_title_no_filters_has_video(self):
        """Test that filter title with no filters includes 'Video Games'."""
        response = self.client.get(reverse("games-list"))
        self.assertEqual(response.status_code, 200)
        filter_title = response.context["filter_title"]
        self.assertIn("Video Games", filter_title)

    def test_search_with_platform_filter(self):
        """Test searching with platform filter."""
        response = self.client.get(
            reverse("games-list") + f"?platforms={self.nes_platform.id}"
        )
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertIn(self.game1, games)

    def test_htmx_request_returns_partial(self):
        """Test that HTMX requests return partial template."""
        response = self.client.get(
            reverse("games-list") + "?q=zelda",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_list_content.html")

    def test_htmx_request_with_target_returns_results_template(self):
        """Test that HTMX request with HX-Target returns results-only template."""
        response = self.client.get(
            reverse("games-list") + "?q=zelda",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="game-results-container",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_list_results.html")

    def test_context_has_filters(self):
        """Test that context includes filter data."""
        response = self.client.get(reverse("games-list"))
        self.assertIn("filters", response.context)
        self.assertIn("genres", response.context)
        self.assertIn("platforms", response.context)

    def test_invalid_page_defaults_to_first(self):
        """Test that invalid page parameter defaults to page 1."""
        response = self.client.get(reverse("games-list") + "?page=invalid")
        self.assertEqual(response.status_code, 200)

    def test_out_of_range_page_returns_last(self):
        """Test that out of range page returns last page."""
        response = self.client.get(reverse("games-list") + "?page=999")
        self.assertEqual(response.status_code, 200)

    def test_highlight_parameter_in_context(self):
        """Test that highlight parameter is passed to context as integer."""
        response = self.client.get(
            reverse("games-list") + f"?highlight={self.game1.id}"
        )
        self.assertEqual(response.status_code, 200)
        # Should be converted to integer for comparison with game.id
        self.assertEqual(response.context["highlight"], self.game1.id)
        self.assertIsInstance(response.context["highlight"], int)

    def test_highlight_invalid_value_is_none(self):
        """Test that invalid highlight value results in None."""
        response = self.client.get(reverse("games-list") + "?highlight=invalid")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["highlight"])

    def test_sort_by_rank_default(self):
        """Test that default sort is by rank."""
        response = self.client.get(reverse("games-list"))
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should be sorted by rank (1, 2, 50)
        self.assertEqual(games[0], self.game1)  # rank 1
        self.assertEqual(games[1], self.game3)  # rank 2
        self.assertEqual(games[2], self.game2)  # rank 50

    def test_sort_by_year(self):
        """Test sorting by year of release."""
        response = self.client.get(reverse("games-list") + "?sort=year")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should be sorted by year (1985, 1986, 1987)
        self.assertEqual(games[0], self.game3)  # 1985
        self.assertEqual(games[1], self.game1)  # 1986
        self.assertEqual(games[2], self.game2)  # 1987

    def test_sort_by_name(self):
        """Test sorting alphabetically by name."""
        response = self.client.get(reverse("games-list") + "?sort=name")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should be sorted alphabetically
        self.assertEqual(games[0], self.game3)  # Super Mario Bros
        self.assertEqual(games[1], self.game1)  # The Legend of Zelda
        self.assertEqual(games[2], self.game2)  # Zelda II

    def test_sort_with_filters(self):
        """Test that sort persists with genre and platform filters."""
        response = self.client.get(
            reverse("games-list")
            + f"?sort=year&genres={self.rpg_genre.id}&platforms={self.nes_platform.id}"
        )
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should find game1 (has both RPG genre and NES platform)
        self.assertIn(self.game1, games)
        # Verify sort parameter is in context
        self.assertEqual(response.context["filters"]["sort"], "year")

    def test_sort_parameter_in_context(self):
        """Test that sort parameter is passed to template context."""
        response = self.client.get(reverse("games-list") + "?sort=year")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filters"]["sort"], "year")

    def test_sort_defaults_to_rank_when_invalid(self):
        """Test that invalid sort value falls back to rank."""
        response = self.client.get(reverse("games-list") + "?sort=invalid")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should fall back to rank sorting
        self.assertEqual(games[0], self.game1)  # rank 1
        self.assertEqual(games[1], self.game3)  # rank 2


class GameSearchLoadMoreTest(TestCase):
    """Test the Load More functionality in game search."""

    def setUp(self):
        # Create 150 test games to test pagination
        for i in range(150):
            Game.objects.create(
                name=f"Game {i:03d}",
                rank=i + 1,
                year_of_release=2020,
            )

    def test_initial_load_includes_load_more_context(self):
        """Test that initial load includes load more context variables."""
        response = self.client.get(reverse("games-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["games"]), 100)
        self.assertTrue(response.context["has_more"])
        self.assertEqual(response.context["next_page"], 2)
        self.assertEqual(response.context["loaded_count"], 100)
        self.assertEqual(response.context["total_count"], 150)
        self.assertEqual(response.context["remaining_count"], 50)
        self.assertFalse(response.context["max_loaded"])

    def test_append_mode_returns_append_template(self):
        """Test that append=true returns the append template."""
        response = self.client.get(
            reverse("games-list"),
            {"page": 2, "append": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_list_append.html")

    def test_append_mode_contains_game_rows(self):
        """Test that append mode response contains game rows."""
        response = self.client.get(
            reverse("games-list"),
            {"page": 2, "append": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "game-row")
        self.assertContains(response, "Game 100")  # First game of page 2

    def test_append_mode_contains_metadata(self):
        """Test that append mode returns JSON metadata."""
        response = self.client.get(
            reverse("games-list"),
            {"page": 2, "append": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "load-more-meta")
        self.assertContains(response, '"hasMore": false')
        self.assertContains(response, '"loadedCount": 150')

    def test_last_page_has_no_more(self):
        """Test that last page correctly reports no more items."""
        response = self.client.get(reverse("games-list"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_more"])
        self.assertIsNone(response.context["next_page"])

    def test_filter_with_few_results_no_load_more(self):
        """Test that filters with few results don't show load more."""
        Game.objects.create(name="Unique2021Game", rank=200, year_of_release=2021)

        response = self.client.get(reverse("games-list"), {"start": 2021, "end": 2021})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["games"]), 1)
        self.assertFalse(response.context["has_more"])

    def test_highlight_beyond_100_loads_enough_games(self):
        """Test that highlighting a game beyond position 100 loads enough games."""
        # Get the game at position 120 (rank 121)
        game_120 = Game.objects.get(rank=121)

        response = self.client.get(reverse("games-list") + f"?highlight={game_120.id}")
        self.assertEqual(response.status_code, 200)
        # Should load 200 games to include position 121
        self.assertEqual(len(response.context["games"]), 150)  # All 150 games
        # Verify the highlighted game is in the results
        game_ids = [g.id for g in response.context["games"]]
        self.assertIn(game_120.id, game_ids)

    def test_highlight_within_100_loads_normal_page(self):
        """Test that highlighting a game within position 100 loads normal page size."""
        # Get the game at position 50 (rank 51)
        game_50 = Game.objects.get(rank=51)

        response = self.client.get(reverse("games-list") + f"?highlight={game_50.id}")
        self.assertEqual(response.status_code, 200)
        # Should load normal 100 games
        self.assertEqual(len(response.context["games"]), 100)
        # Verify the highlighted game is in the results
        game_ids = [g.id for g in response.context["games"]]
        self.assertIn(game_50.id, game_ids)


class DeveloperListViewTest(TestCase):
    """Test the developer list view."""

    def setUp(self):
        # Create developers with aliases
        dev1 = Company.objects.create(name="Nintendo", slug="nintendo")
        dev2 = Company.objects.create(name="Capcom", slug="capcom")

        self.alias1 = Studio.objects.create(name="Nintendo", company=dev1, igdb_id=1)
        self.alias2 = Studio.objects.create(name="Capcom", company=dev2, igdb_id=2)

        # Create games for the aliases
        game1 = Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        game1.studios.add(self.alias1)

    def test_developer_list_loads(self):
        """Test that developer list page loads."""
        response = self.client.get(reverse("developers-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "developers/company_list.html")

    def test_only_shows_developers_with_games(self):
        """Test that only developers with games are shown."""
        response = self.client.get(reverse("developers-list"))
        developers = list(response.context["developers"])
        # Only alias1 has games
        self.assertEqual(len(developers), 1)
        self.assertIn(self.alias1, developers)

    def test_search_filter(self):
        """Test searching developers by name."""
        response = self.client.get(reverse("developers-list") + "?q=nintendo")
        self.assertEqual(response.status_code, 200)
        developers = list(response.context["developers"])
        self.assertIn(self.alias1, developers)

    def test_htmx_request_returns_partial(self):
        """Test that HTMX requests return partial template."""
        response = self.client.get(reverse("developers-list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "developers/includes/_company_list_content.html"
        )

    def test_invalid_page_defaults_to_first(self):
        """Test that invalid page parameter defaults to page 1."""
        response = self.client.get(reverse("developers-list") + "?page=invalid")
        self.assertEqual(response.status_code, 200)

    def test_out_of_range_page_returns_last(self):
        """Test that out of range page returns last page."""
        response = self.client.get(reverse("developers-list") + "?page=999")
        self.assertEqual(response.status_code, 200)


class DeveloperDetailViewTest(TestCase):
    """Test the developer detail view."""

    def setUp(self):
        self.company = Company.objects.create(name="Nintendo", slug="nintendo")
        self.alias = Studio.objects.create(
            name="Nintendo", company=self.company, igdb_id=1
        )

        # Create games for this developer
        self.game1 = Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        self.game2 = Game.objects.create(name="Game 2", rank=2, year_of_release=2021)
        self.game1.studios.add(self.alias)
        self.game2.studios.add(self.alias)

    def test_developer_detail_loads(self):
        """Test that developer detail page loads."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.company.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "developers/company_detail.html")

    def test_context_contains_developer(self):
        """Test that context includes the developer."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.company.slug})
        )
        self.assertEqual(response.context["developer"], self.company)

    def test_context_contains_games(self):
        """Test that context includes developer's games."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.company.slug})
        )
        studios_with_games = response.context["studios_with_games"]
        # Extract all games from all studios
        all_games = []
        for studio_data in studios_with_games:
            all_games.extend(studio_data["games"])
        self.assertEqual(len(all_games), 2)
        self.assertIn(self.game1, all_games)
        self.assertIn(self.game2, all_games)

    def test_context_contains_aliases_data(self):
        """Test that context includes studios with games data."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.company.slug})
        )
        self.assertIn("studios_with_games", response.context)
        self.assertTrue(len(response.context["studios_with_games"]) > 0)

    def test_context_contains_games_data(self):
        """Test that context includes games data grouped by studio."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.company.slug})
        )
        studios_with_games = response.context["studios_with_games"]
        # Count all games across all studios
        total_games = sum(len(s["games"]) for s in studios_with_games)
        self.assertEqual(total_games, 2)

    def test_invalid_slug_returns_404(self):
        """Test that invalid slug returns 404."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": "invalid-slug"})
        )
        self.assertEqual(response.status_code, 404)

    def test_unique_game_count_with_sibling_studios(self):
        """
        Test that games attributed to multiple sibling studios
        are only counted once in the total count.
        """
        # Create a parent company with two sibling studios
        parent = Company.objects.create(
            name="Sony Interactive Entertainment", slug="sie"
        )
        studio_a = Studio.objects.create(
            name="Sony Studio A", company=parent, igdb_id=100
        )
        studio_b = Studio.objects.create(
            name="Sony Studio B", company=parent, igdb_id=101
        )

        # Create a game attributed to both sibling studios
        shared_game = Game.objects.create(
            name="Shared Game", rank=1, year_of_release=2020
        )
        shared_game.studios.add(studio_a, studio_b)

        # Create games unique to each studio
        game_a_only = Game.objects.create(
            name="Game A Only", rank=2, year_of_release=2021
        )
        game_a_only.studios.add(studio_a)

        game_b_only = Game.objects.create(
            name="Game B Only", rank=3, year_of_release=2022
        )
        game_b_only.studios.add(studio_b)

        # Fetch the company detail page
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": parent.slug})
        )

        # The total_games count should be 3 (not 4)
        # shared_game appears in both studios but should only be counted once
        self.assertEqual(response.context["total_games"], 3)

        # Verify individual studio counts
        studios_with_games = response.context["studios_with_games"]
        studio_a_data = next(
            s for s in studios_with_games if s["studio"].id == studio_a.id
        )
        studio_b_data = next(
            s for s in studios_with_games if s["studio"].id == studio_b.id
        )

        # Each studio shows both games (including shared)
        self.assertEqual(studio_a_data["games_count"], 2)
        self.assertEqual(studio_b_data["games_count"], 2)

        # total_games_count for each studio includes only that studio + its sub-studios
        # (not sibling studios). Both have no sub-studios, so count is their own games.
        self.assertEqual(studio_a_data["total_games_count"], 2)
        self.assertEqual(studio_b_data["total_games_count"], 2)

    def test_nested_studio_hierarchy(self):
        """
        Test that nested studio hierarchies work correctly.
        When a studio also exists as a company with sub-studios,
        games from sub-studios should be filtered out from parent's list.
        """
        # Use Nintendo company from setUp (already created)
        nintendo = self.company

        # Create Nintendo EPD studio and company
        nintendo_epd_studio = Studio.objects.create(
            name="Nintendo EPD", company=nintendo, igdb_id=200
        )
        nintendo_epd_company = Company.objects.create(
            name="Nintendo EPD", slug="nintendo-epd"
        )

        # Create Nintendo EPD Production Group No. 3 (sub-studio)
        epd_group_3 = Studio.objects.create(
            name="Nintendo EPD Production Group No. 3",
            company=nintendo_epd_company,
            igdb_id=300,
        )

        # Create games
        # Game 1: Attributed to BOTH Nintendo EPD AND EPD Group 3
        # (should only show at deepest level - Group 3)
        game1 = Game.objects.create(name="Zelda BOTW", rank=1, year_of_release=2017)
        game1.studios.add(nintendo_epd_studio, epd_group_3)

        # Game 2: Attributed to Nintendo EPD only (should show at EPD level)
        game2 = Game.objects.create(name="Splatoon", rank=2, year_of_release=2015)
        game2.studios.add(nintendo_epd_studio)

        # Fetch the Nintendo company detail page
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": nintendo.slug})
        )

        # Verify the hierarchy is correct
        studios_with_games = response.context["studios_with_games"]
        # Should have 2 studios: "Nintendo" (from setUp) and
        # "Nintendo EPD" (from this test)
        self.assertEqual(len(studios_with_games), 2)

        # Find the Nintendo EPD studio (should be second alphabetically)
        epd_data = None
        for studio_data in studios_with_games:
            if studio_data["studio"].name == "Nintendo EPD":
                epd_data = studio_data
                break

        self.assertIsNotNone(epd_data, "Nintendo EPD studio should be in the list")

        # EPD should have 1 direct game (Splatoon) - Zelda should be filtered out
        self.assertEqual(epd_data["games_count"], 1)
        self.assertEqual(epd_data["games"][0].name, "Splatoon")

        # EPD should have 1 sub-studio
        self.assertEqual(len(epd_data["sub_studios"]), 1)

        # Check the sub-studio
        group3_data = epd_data["sub_studios"][0]
        self.assertEqual(
            group3_data["studio"].name, "Nintendo EPD Production Group No. 3"
        )
        self.assertEqual(group3_data["games_count"], 1)
        self.assertEqual(group3_data["games"][0].name, "Zelda BOTW")


class DeveloperAliasRedirectViewTest(TestCase):
    """Test the developer alias redirect view."""

    def setUp(self):
        self.company = Company.objects.create(name="Nintendo", slug="nintendo")
        self.alias = Studio.objects.create(
            name="Nintendo", company=self.company, igdb_id=1
        )

    def test_redirects_to_developer_detail(self):
        """Test that alias redirects to developer detail page."""
        response = self.client.get(
            reverse("developer-alias-redirect", kwargs={"id": self.alias.id})
        )
        self.assertEqual(response.status_code, 301)  # Permanent redirect
        self.assertRedirects(
            response,
            reverse("developer-detail", kwargs={"slug": self.company.slug}),
            status_code=301,
        )

    def test_invalid_id_returns_404(self):
        """Test that invalid alias ID returns 404."""
        response = self.client.get(
            reverse("developer-alias-redirect", kwargs={"id": 99999})
        )
        self.assertEqual(response.status_code, 404)


class ListListViewTest(TestCase):
    """Test the list list view."""

    def setUp(self):
        self.pub1 = Publication.objects.create(name="IGN")
        self.pub2 = Publication.objects.create(name="GameSpot")

        self.list1 = List.objects.create(
            name="Best of 2020", publisher=self.pub1, year=2020, type="A"
        )
        self.list2 = List.objects.create(
            name="Best of 2021", publisher=self.pub2, year=2021, type="E"
        )

    def test_list_list_loads(self):
        """Test that list list page loads."""
        response = self.client.get(reverse("list-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "lists/list_list.html")

    def test_context_contains_lists(self):
        """Test that context includes lists."""
        response = self.client.get(reverse("list-list"))
        lists = list(response.context["lists"])
        self.assertEqual(len(lists), 2)

    def test_filter_by_publisher(self):
        """Test filtering lists by publisher."""
        response = self.client.get(reverse("list-list") + f"?publisher={self.pub1.id}")
        self.assertEqual(response.status_code, 200)
        lists = list(response.context["lists"])
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].publisher, self.pub1)

    def test_filter_by_year(self):
        """Test filtering lists by year."""
        response = self.client.get(reverse("list-list") + "?year=2020")
        self.assertEqual(response.status_code, 200)
        lists = list(response.context["lists"])
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].year, 2020)

    def test_filter_by_type(self):
        """Test filtering lists by type using URL slug."""
        response = self.client.get(reverse("list-list") + "?type=all-time")
        self.assertEqual(response.status_code, 200)
        lists = list(response.context["lists"])
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].type, "A")

    def test_filter_by_invalid_publisher_is_ignored(self):
        """Test that invalid (non-numeric) publisher ID is ignored."""
        response = self.client.get(reverse("list-list") + "?publisher=invalid")
        self.assertEqual(response.status_code, 200)
        # All lists should be returned since invalid filter is ignored
        lists = list(response.context["lists"])
        self.assertEqual(len(lists), 2)

    def test_filter_by_invalid_year_is_ignored(self):
        """Test that invalid (non-numeric) year is ignored."""
        response = self.client.get(reverse("list-list") + "?year=invalid")
        self.assertEqual(response.status_code, 200)
        # All lists should be returned since invalid filter is ignored
        lists = list(response.context["lists"])
        self.assertEqual(len(lists), 2)

    def test_context_has_meta_data(self):
        """Test that context includes metadata."""
        response = self.client.get(reverse("list-list"))
        self.assertIn("meta", response.context)
        self.assertIn("publishers", response.context)
        self.assertIn("list_types", response.context)

    def test_publishers_have_list_counts(self):
        """Test that publishers in context have list_count attribute."""
        response = self.client.get(reverse("list-list"))
        publishers = response.context["publishers"]
        # pub1 has 1 list, pub2 has 1 list
        pub1_count = next(p.list_count for p in publishers if p.name == "IGN")
        pub2_count = next(p.list_count for p in publishers if p.name == "GameSpot")
        self.assertEqual(pub1_count, 1)
        self.assertEqual(pub2_count, 1)

    def test_type_counts_in_context(self):
        """Test that type_counts is in context with correct structure."""
        response = self.client.get(reverse("list-list"))
        self.assertIn("type_counts", response.context)
        type_counts = response.context["type_counts"]
        # Should have counts for types A and E (from setUp)
        type_dict = {t["type"]: t["count"] for t in type_counts}
        self.assertEqual(type_dict.get("A"), 1)  # list1 is type A
        self.assertEqual(type_dict.get("E"), 1)  # list2 is type E

    def test_htmx_request_returns_partial(self):
        """Test that HTMX requests return partial template."""
        response = self.client.get(reverse("list-list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "lists/includes/_list_list_content.html")

    def test_invalid_page_defaults_to_first(self):
        """Test that invalid page parameter defaults to page 1."""
        response = self.client.get(reverse("list-list") + "?page=invalid")
        self.assertEqual(response.status_code, 200)

    def test_out_of_range_page_returns_last(self):
        """Test that out of range page returns last page."""
        response = self.client.get(reverse("list-list") + "?page=999")
        self.assertEqual(response.status_code, 200)


class ListListFacetedFilterTest(TestCase):
    """Test faceted filter counts on list list view."""

    def setUp(self):
        # Create publishers
        self.pub_ign = Publication.objects.create(name="IGN")
        self.pub_gamespot = Publication.objects.create(name="GameSpot")
        self.pub_polygon = Publication.objects.create(name="Polygon")

        # Create diverse set of lists for testing facets
        # IGN: 2020 All-time, 2021 End-of-year
        List.objects.create(
            name="IGN 2020", publisher=self.pub_ign, year=2020, type="A"
        )
        List.objects.create(
            name="IGN 2021", publisher=self.pub_ign, year=2021, type="E"
        )

        # GameSpot: 2020 End-of-year, 2021 End-of-year
        List.objects.create(
            name="GS 2020", publisher=self.pub_gamespot, year=2020, type="E"
        )
        List.objects.create(
            name="GS 2021", publisher=self.pub_gamespot, year=2021, type="E"
        )

        # Polygon: 2021 All-time only
        List.objects.create(
            name="Polygon 2021", publisher=self.pub_polygon, year=2021, type="A"
        )

    def test_year_counts_filter_by_publisher(self):
        """Year counts should reflect publisher filter."""
        response = self.client.get(
            reverse("list-list") + f"?publisher={self.pub_ign.id}"
        )
        years = response.context["meta"]["lists"]["years"]
        year_dict = {y["year"]: y["count"] for y in years}

        # IGN has 1 list in 2020, 1 in 2021
        self.assertEqual(year_dict.get(2020), 1)
        self.assertEqual(year_dict.get(2021), 1)

    def test_year_counts_filter_by_type(self):
        """Year counts should reflect type filter."""
        response = self.client.get(reverse("list-list") + "?type=all-time")
        years = response.context["meta"]["lists"]["years"]
        year_dict = {y["year"]: y["count"] for y in years}

        # All-time lists: 2020 has 1 (IGN), 2021 has 1 (Polygon)
        self.assertEqual(year_dict.get(2020), 1)
        self.assertEqual(year_dict.get(2021), 1)

    def test_publisher_counts_filter_by_year(self):
        """Publisher counts should reflect year filter."""
        response = self.client.get(reverse("list-list") + "?year=2020")
        publishers = response.context["publishers"]
        pub_dict = {p.name: p.list_count for p in publishers}

        # 2020: IGN has 1, GameSpot has 1, Polygon has 0 (should be hidden)
        self.assertEqual(pub_dict.get("IGN"), 1)
        self.assertEqual(pub_dict.get("GameSpot"), 1)
        self.assertNotIn("Polygon", pub_dict)  # 0 count, not selected

    def test_publisher_counts_filter_by_type(self):
        """Publisher counts should reflect type filter."""
        response = self.client.get(reverse("list-list") + "?type=end-of-year")
        publishers = response.context["publishers"]
        pub_dict = {p.name: p.list_count for p in publishers}

        # End-of-year: IGN has 1, GameSpot has 2, Polygon has 0
        self.assertEqual(pub_dict.get("IGN"), 1)
        self.assertEqual(pub_dict.get("GameSpot"), 2)
        self.assertNotIn("Polygon", pub_dict)

    def test_type_counts_filter_by_publisher(self):
        """Type counts should reflect publisher filter."""
        response = self.client.get(
            reverse("list-list") + f"?publisher={self.pub_ign.id}"
        )
        type_counts = response.context["type_counts"]
        type_dict = {t["type"]: t["count"] for t in type_counts}

        # IGN: 1 All-time, 1 End-of-year
        self.assertEqual(type_dict.get("A"), 1)
        self.assertEqual(type_dict.get("E"), 1)

    def test_type_counts_filter_by_year(self):
        """Type counts should reflect year filter."""
        response = self.client.get(reverse("list-list") + "?year=2020")
        type_counts = response.context["type_counts"]
        type_dict = {t["type"]: t["count"] for t in type_counts}

        # 2020: 1 All-time (IGN), 1 End-of-year (GameSpot)
        self.assertEqual(type_dict.get("A"), 1)
        self.assertEqual(type_dict.get("E"), 1)

    def test_combined_filters_affect_all_counts(self):
        """Multiple filters should combine to affect all counts."""
        response = self.client.get(
            reverse("list-list") + f"?publisher={self.pub_ign.id}&year=2020"
        )

        # Year counts (filtered by publisher only)
        years = response.context["meta"]["lists"]["years"]
        year_dict = {y["year"]: y["count"] for y in years}
        self.assertEqual(year_dict.get(2020), 1)  # IGN 2020
        self.assertEqual(year_dict.get(2021), 1)  # IGN 2021

        # Publisher counts (filtered by year only)
        publishers = response.context["publishers"]
        pub_dict = {p.name: p.list_count for p in publishers}
        self.assertEqual(pub_dict.get("IGN"), 1)
        self.assertEqual(pub_dict.get("GameSpot"), 1)

        # Type counts (filtered by publisher + year)
        type_counts = response.context["type_counts"]
        type_dict = {t["type"]: t["count"] for t in type_counts}
        self.assertEqual(type_dict.get("A"), 1)  # IGN 2020 is All-time
        self.assertNotIn("E", type_dict)  # No End-of-year for IGN 2020

    def test_zero_count_options_hidden(self):
        """Options with 0 count should be hidden (unless selected)."""
        response = self.client.get(reverse("list-list") + "?year=2020")
        publishers = response.context["publishers"]

        # Polygon has 0 lists in 2020 and is not selected
        pub_names = [p.name for p in publishers]
        self.assertNotIn("Polygon", pub_names)

    def test_selected_zero_count_remains_visible(self):
        """Currently selected option should remain visible even with 0 count."""
        response = self.client.get(
            reverse("list-list") + f"?publisher={self.pub_polygon.id}&year=2020"
        )
        publishers = response.context["publishers"]
        pub_dict = {p.name: p.list_count for p in publishers}

        # Polygon should still be visible (selected) but with 0 count
        self.assertIn("Polygon", pub_dict)
        self.assertEqual(pub_dict["Polygon"], 0)


class PostListViewTest(TestCase):
    """Test the post list view."""

    def setUp(self):
        # Create test posts
        for i in range(10):
            Post.objects.create(
                title=f"Post {i}",
                text=f"Content {i}",
                active=True,
            )

    def test_post_list_loads(self):
        """Test that post list page loads."""
        response = self.client.get(reverse("post-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/post_list.html")

    def test_pagination(self):
        """Test that pagination works (5 posts per page)."""
        response = self.client.get(reverse("post-list"))
        posts = list(response.context["posts"])
        self.assertEqual(len(posts), 5)

    def test_offset_parameter(self):
        """Test that offset parameter works."""
        response = self.client.get(reverse("post-list") + "?offset=5")
        self.assertEqual(response.status_code, 200)
        # Should return 5 posts (posts 5-9, since we created 10 total)
        posts = response.context["posts"]
        self.assertEqual(len(posts), 5)

    def test_only_shows_active_posts(self):
        """Test that only active posts are shown."""
        # Create an inactive post
        Post.objects.create(title="Inactive", text="Content", active=False)

        response = self.client.get(reverse("post-list"))
        posts = list(response.context["posts"])
        # Should still only show 5 active posts (from the 10 we created)
        self.assertEqual(len(posts), 5)
        for post in posts:
            self.assertTrue(post.active)

    def test_invalid_offset_defaults_to_zero(self):
        """Test that invalid offset parameter defaults to 0."""
        response = self.client.get(reverse("post-list") + "?offset=invalid")
        self.assertEqual(response.status_code, 200)


class PageDetailViewTest(TestCase):
    """Test the page detail view."""

    def setUp(self):
        # Create a site (required for FlatPage)
        site = Site.objects.get_current()

        # Create a flatpage
        self.flatpage = FlatPage.objects.create(
            url="/about/",
            title="About Us",
            content="# About\n\nThis is **markdown** content.",
        )
        self.flatpage.sites.add(site)

    def test_page_detail_loads(self):
        """Test that page detail loads."""
        response = self.client.get(reverse("page-detail", kwargs={"slug": "about"}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/page_detail.html")

    def test_context_contains_flatpage(self):
        """Test that context includes the flatpage."""
        response = self.client.get(reverse("page-detail", kwargs={"slug": "about"}))
        self.assertIn("flatpage", response.context)
        self.assertEqual(response.context["flatpage"].title, "About Us")

    def test_markdown_is_rendered(self):
        """Test that markdown content is rendered to HTML."""
        response = self.client.get(reverse("page-detail", kwargs={"slug": "about"}))
        flatpage = response.context["flatpage"]
        self.assertIn("rendered_content", dir(flatpage))
        # Markdown should be converted to HTML
        self.assertIn("<h1>", flatpage.rendered_content)
        self.assertIn("<strong>", flatpage.rendered_content)

    def test_invalid_slug_returns_404(self):
        """Test that invalid slug returns 404."""
        response = self.client.get(reverse("page-detail", kwargs={"slug": "invalid"}))
        self.assertEqual(response.status_code, 404)


class NotFoundViewTest(TestCase):
    """Test the custom 404 view."""

    def test_not_found_view_returns_404(self):
        """Test that NotFoundView returns 404 status."""
        # Access an invalid URL to trigger the catch-all 404 handler
        response = self.client.get("/this-url-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")


class GameDownloadCSVTest(TestCase):
    """Test the CSV download functionality."""

    def setUp(self):
        # Create test games with related data
        self.genre = IGDBGenre.objects.create(name="Action")
        self.platform = Platform.objects.create(name="PC", code="PC")
        dev = Company.objects.create(name="Test Dev", slug="test-dev")
        self.dev_alias = Studio.objects.create(name="Test Dev", company=dev, igdb_id=1)

        self.game1 = Game.objects.create(name="Game 1", rank=1, year_of_release=1995)
        self.game1.genres.add(self.genre)
        self.game1.platforms.add(self.platform)
        self.game1.studios.add(self.dev_alias)

        self.game2 = Game.objects.create(name="Game 2", rank=2, year_of_release=2005)

    def test_csv_download_works(self):
        """Test that CSV download returns valid CSV."""
        response = self.client.get(reverse("games-download"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".csv", response["Content-Disposition"])

    def test_csv_contains_headers(self):
        """Test that CSV has correct headers."""
        response = self.client.get(reverse("games-download"))
        content = response.content.decode("utf-8")
        lines = content.strip().split("\n")
        # Strip \r from line (CSV uses \r\n line endings)
        expected = "Filtered Rank,Global Rank,Name,Year,Developers,Platforms,Genres"
        self.assertEqual(lines[0].strip(), expected)

    def test_csv_contains_game_data(self):
        """Test that CSV contains game data."""
        response = self.client.get(reverse("games-download"))
        content = response.content.decode("utf-8")
        self.assertIn("Game 1", content)
        self.assertIn("Game 2", content)
        self.assertIn("Action", content)
        self.assertIn("PC", content)
        self.assertIn("Test Dev", content)

    def test_csv_respects_decade_filter(self):
        """Test that CSV respects decade filter and uses filtered rank."""
        response = self.client.get(reverse("games-download") + "?decade=1990-99")
        content = response.content.decode("utf-8")
        self.assertIn("Game 1", content)  # 1995 is in 1990s
        self.assertNotIn("Game 2", content)  # 2005 is not in 1990s
        self.assertIn("1990-99", response["Content-Disposition"])
        # Should use filtered rank (1) not alltime rank
        lines = content.strip().split("\n")
        self.assertTrue(lines[1].startswith("1,"))  # First data row starts with rank 1

    def test_csv_respects_year_filter(self):
        """Test that CSV respects year filter."""
        response = self.client.get(reverse("games-download") + "?year=1995")
        content = response.content.decode("utf-8")
        self.assertIn("Game 1", content)
        self.assertNotIn("Game 2", content)
        self.assertIn("1995", response["Content-Disposition"])

    def test_csv_unfiltered_uses_alltime_rank(self):
        """Test that unfiltered CSV uses alltime rank."""
        # Create a game with a higher rank number
        Game.objects.create(name="Game 3", rank=100, year_of_release=2010)
        response = self.client.get(reverse("games-download"))
        content = response.content.decode("utf-8")
        # Should contain the actual rank (100), not sequential (3)
        self.assertIn("100,Game 3", content)


class RobotsTxtViewTest(TestCase):
    """Test the robots.txt view."""

    def test_robots_txt_returns_200(self):
        """Test that robots.txt returns 200 status."""
        response = self.client.get(reverse("robots-txt"))
        self.assertEqual(response.status_code, 200)

    def test_robots_txt_content_type(self):
        """Test that robots.txt returns plain text content type."""
        response = self.client.get(reverse("robots-txt"))
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_robots_txt_contains_user_agent(self):
        """Test that robots.txt contains User-agent directive."""
        response = self.client.get(reverse("robots-txt"))
        content = response.content.decode("utf-8")
        self.assertIn("User-agent: *", content)

    def test_robots_txt_contains_sitemap(self):
        """Test that robots.txt contains sitemap URL."""
        response = self.client.get(reverse("robots-txt"))
        content = response.content.decode("utf-8")
        self.assertIn("Sitemap:", content)
        self.assertIn("sitemap.xml", content)


class SitemapViewTest(TestCase):
    """Test the XML sitemap."""

    def setUp(self):
        # Create test games
        self.game1 = Game.objects.create(
            name="Test Game 1", slug="test-game-1", rank=1, year_of_release=2020
        )
        self.game2 = Game.objects.create(
            name="Test Game 2", slug="test-game-2", rank=2, year_of_release=2021
        )

        # Create test developers
        self.dev = Company.objects.create(name="Test Dev", slug="test-dev")

    def test_sitemap_returns_200(self):
        """Test that sitemap.xml returns 200 status."""
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)

    def test_sitemap_content_type(self):
        """Test that sitemap returns XML content type."""
        response = self.client.get("/sitemap.xml")
        self.assertIn("xml", response["Content-Type"])

    def test_sitemap_contains_static_urls(self):
        """Test that sitemap contains static page URLs."""
        response = self.client.get("/sitemap.xml")
        content = response.content.decode("utf-8")
        # Check for static page paths
        self.assertIn("/rankings/", content)
        self.assertIn("/developers/", content)
        self.assertIn("/lists/", content)
        self.assertIn("/posts/", content)

    def test_sitemap_contains_game_urls(self):
        """Test that sitemap contains game detail URLs."""
        response = self.client.get("/sitemap.xml")
        content = response.content.decode("utf-8")
        self.assertIn("/game/test-game-1/", content)
        self.assertIn("/game/test-game-2/", content)

    def test_sitemap_contains_developer_urls(self):
        """Test that sitemap contains developer detail URLs."""
        response = self.client.get("/sitemap.xml")
        content = response.content.decode("utf-8")
        self.assertIn("/developers/test-dev/", content)

    def test_sitemap_is_valid_xml(self):
        """Test that sitemap is valid XML with proper namespace."""
        response = self.client.get("/sitemap.xml")
        content = response.content.decode("utf-8")
        self.assertIn('<?xml version="1.0"', content)
        self.assertIn("http://www.sitemaps.org/schemas/sitemap/0.9", content)
