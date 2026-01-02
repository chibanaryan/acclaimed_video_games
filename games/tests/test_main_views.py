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
    Developer,
    Game,
    IGDBGenre,
    List,
    ListMembership,
    Platform,
    PlayedGame,
    Post,
    Publication,
    SiteMetadata,
    User,
    WikipediaGenre,
)


class HomePageViewTest(TestCase):
    """Test the home page view."""

    def setUp(self):
        # Clear hero stats cache to ensure fresh counts
        cache.delete("homepage_hero_stats")

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
        self.assertTemplateUsed(response, "games/home.html")

    def test_news_page_contains_posts(self):
        """Test that news page includes posts."""
        response = self.client.get(reverse("news-list"))
        self.assertEqual(response.status_code, 200)
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

    def test_contact_form_post_valid(self):
        """Test valid contact form submission."""
        from unittest import mock

        with mock.patch("games.utils.send_contact_email", return_value=True):
            response = self.client.post(
                reverse("contact"),
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
            reverse("contact"),
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
            reverse("contact"),
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
                reverse("contact"),
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

    def test_home_page_shows_signup_for_anonymous(self):
        """Test that home page shows sign up button for anonymous users."""
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")
        self.assertIn("Sign Up", content)


class ContactPageViewTest(TestCase):
    """Test the dedicated contact page view."""

    def test_contact_page_loads(self):
        """Test that contact page loads successfully."""
        response = self.client.get(reverse("contact"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contact.html")
        self.assertIn("form", response.context)


class ContactThankYouViewTest(TestCase):
    """Test the contact thank you page view."""

    def test_thank_you_page_loads(self):
        """Test that thank you page loads successfully."""
        response = self.client.get(reverse("contact_thank_you"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contact_thank_you.html")


class GameListViewTest(TestCase):
    """Test the game list view (HomePageView with legacy param support)."""

    @classmethod
    def setUpTestData(cls):
        # Create 150 games for pagination testing (once per class, not per test)
        for i in range(1, 151):
            Game.objects.create(
                name=f"Game {i}", rank=i, year_of_release=1990 + (i % 30)
            )

    def test_game_list_loads(self):
        """Test that game list page loads."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/home.html")

    def test_pagination(self):
        """Test that pagination works correctly."""
        response = self.client.get(reverse("home"))
        self.assertIn("page_obj", response.context)
        # Should have 100 games per page
        self.assertEqual(len(response.context["games"]), 100)

    def test_second_page(self):
        """Test accessing second page."""
        response = self.client.get(reverse("home") + "?page=2")
        self.assertEqual(response.status_code, 200)
        # Second page should have 50 games (150 total - 100 on first page)
        self.assertEqual(len(response.context["games"]), 50)

    def test_decade_filter(self):
        """Test filtering by decade (legacy param support)."""
        response = self.client.get(reverse("home") + "?decade=1990-99")
        self.assertEqual(response.status_code, 200)
        # All games should be from 1990-1999
        for game in response.context["games"]:
            self.assertGreaterEqual(game.year_of_release, 1990)
            self.assertLessEqual(game.year_of_release, 1999)

    def test_year_filter(self):
        """Test filtering by single year (legacy param support)."""
        response = self.client.get(reverse("home") + "?year=1995")
        self.assertEqual(response.status_code, 200)
        # All games should be from 1995
        for game in response.context["games"]:
            self.assertEqual(game.year_of_release, 1995)

    def test_htmx_request_returns_partial(self):
        """Test that HTMX requests return partial template."""
        response = self.client.get(reverse("home"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_list_content.html")

    def test_invalid_page_returns_last_page(self):
        """Test that invalid page number returns last page."""
        response = self.client.get(reverse("home") + "?page=999")
        self.assertEqual(response.status_code, 200)
        # Should return the last page (page 2 with our 150 games)
        self.assertEqual(response.context["page_obj"].number, 2)

    def test_non_numeric_page_defaults_to_first(self):
        """Test that non-numeric page parameter defaults to page 1."""
        response = self.client.get(reverse("home") + "?page=invalid")
        self.assertEqual(response.status_code, 200)
        # Should default to first page
        self.assertEqual(response.context["page_obj"].number, 1)

    def test_context_has_filters(self):
        """Test that context includes filter information with legacy params."""
        response = self.client.get(reverse("home") + "?decade=2000-09")
        self.assertIn("filters", response.context)
        # Decade is preserved in filters for legacy compatibility
        self.assertEqual(response.context["filters"]["decade"], "2000-09")
        # Decade is also converted to start/end
        self.assertEqual(response.context["filters"]["start"], 2000)
        self.assertEqual(response.context["filters"]["end"], 2009)

    def test_context_has_year_counts(self):
        """Test that context includes year counts for year grid."""
        response = self.client.get(reverse("home"))
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
        response = self.client.get(reverse("home"))
        year_counts = {
            yc["year"]: yc["count"] for yc in response.context["year_counts"]
        }
        self.assertGreaterEqual(year_counts.get(2010, 0), 1)
        self.assertGreaterEqual(year_counts.get(2015, 0), 1)

        # With genre filter, only matching year should have count
        response = self.client.get(reverse("home") + f"?genres={action.id}")
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
        response = self.client.get(reverse("home") + "?q=ZeldaTest")
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

    def test_is_played_context_for_authenticated_user(self):
        """Test that is_played context is set for authenticated users."""
        # Create user and log in
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client.login(username="testuser", password="testpass123")

        # Create a game with igdb_id
        game_with_igdb = Game.objects.create(
            name="Game With IGDB",
            slug="game-with-igdb",
            rank=12,
            year_of_release=2020,
            igdb_id=12345,
        )

        # Initially not played
        response = self.client.get(
            reverse("game-detail", kwargs={"slug": game_with_igdb.slug})
        )
        self.assertFalse(response.context.get("is_played", False))

        # Mark as played
        PlayedGame.objects.create(user=user, igdb_id=12345)

        # Now should show as played
        response = self.client.get(
            reverse("game-detail", kwargs={"slug": game_with_igdb.slug})
        )
        self.assertTrue(response.context.get("is_played", False))


class HomePageFilterTest(TestCase):
    """Test the home page filtering and search functionality."""

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
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/home.html")

    def test_old_search_url_redirects(self):
        """Test that old /games/search/ URL redirects to /."""
        response = self.client.get(reverse("games-search"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/")

    def test_old_search_url_preserves_query_params(self):
        """Test that redirect preserves query parameters."""
        response = self.client.get(reverse("games-search") + "?q=zelda&page=2")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/?q=zelda&page=2")

    def test_old_games_url_redirects(self):
        """Test that old /games/ URL redirects to /."""
        response = self.client.get(reverse("games-redirect"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/")

    def test_old_games_url_preserves_query_params(self):
        """Test that /games/ redirect preserves query parameters."""
        response = self.client.get(reverse("games-redirect") + "?q=zelda&page=2")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/?q=zelda&page=2")

    def test_old_rankings_url_redirects(self):
        """Test that old /rankings/ URL redirects to /."""
        response = self.client.get(reverse("rankings-redirect"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/")

    def test_old_rankings_url_preserves_query_params(self):
        """Test that /rankings/ redirect preserves query parameters."""
        response = self.client.get(reverse("rankings-redirect") + "?q=zelda&page=2")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, "/?q=zelda&page=2")

    def test_search_by_name(self):
        """Test searching games by name."""
        response = self.client.get(reverse("home") + "?q=zelda")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertEqual(len(games), 2)  # Should find both Zelda games

    def test_search_with_year_range(self):
        """Test searching with year range filter."""
        response = self.client.get(reverse("home") + "?start=1986&end=1987")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertEqual(len(games), 2)  # Zelda games from 1986-1987

    def test_search_with_genre_filter(self):
        """Test searching with genre filter."""
        response = self.client.get(reverse("home") + f"?genres={self.rpg_genre.id}")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Both Zelda games have RPG genre
        self.assertIn(self.game1, games)
        self.assertIn(self.game2, games)

    def test_filter_title_genre_without_video_prefix(self):
        """Test that genre filter title does not include 'Video' prefix."""
        response = self.client.get(reverse("home") + f"?genres={self.action_genre.id}")
        self.assertEqual(response.status_code, 200)
        filter_title = response.context["filter_title"]
        # Should be "Action Games" not "Video Action Games"
        self.assertIn("Action Games", filter_title)
        self.assertNotIn("Video Action", filter_title)

    def test_filter_title_no_filters_has_video(self):
        """Test that filter title with no filters includes 'Video Games'."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        filter_title = response.context["filter_title"]
        self.assertIn("Video Games", filter_title)

    def test_filter_title_series_without_video_prefix(self):
        """Test that series filter title does not include 'Video' prefix."""
        from games.models import Series

        # Create a series with 2+ games (required for series to appear in list)
        zelda_series = Series.objects.create(
            name="The Legend of Zelda",
            slug="the-legend-of-zelda",
            igdb_id=12345,
        )
        self.game1.series.add(zelda_series)
        self.game2.series.add(zelda_series)

        # Clear series cache
        cache.clear()

        response = self.client.get(reverse("home") + f"?series={zelda_series.id}")
        self.assertEqual(response.status_code, 200)
        filter_title = response.context["filter_title"]
        # Should be "The Legend of Zelda Games" not "Video The Legend of Zelda Games"
        self.assertIn("The Legend of Zelda Games", filter_title)
        self.assertNotIn("Video The Legend", filter_title)

    def test_search_with_platform_filter(self):
        """Test searching with platform filter."""
        response = self.client.get(
            reverse("home") + f"?platforms={self.nes_platform.id}"
        )
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertIn(self.game1, games)

    def test_htmx_request_returns_partial(self):
        """Test that HTMX requests return partial template."""
        response = self.client.get(
            reverse("home") + "?q=zelda",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_list_content.html")

    def test_htmx_request_with_target_returns_results_template(self):
        """Test that HTMX request with HX-Target returns results-only template."""
        response = self.client.get(
            reverse("home") + "?q=zelda",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="game-results-container",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_list_results.html")

    def test_context_has_filters(self):
        """Test that context includes filter data."""
        response = self.client.get(reverse("home"))
        self.assertIn("filters", response.context)
        self.assertIn("genres", response.context)
        self.assertIn("platforms", response.context)

    def test_invalid_page_defaults_to_first(self):
        """Test that invalid page parameter defaults to page 1."""
        response = self.client.get(reverse("home") + "?page=invalid")
        self.assertEqual(response.status_code, 200)

    def test_out_of_range_page_returns_last(self):
        """Test that out of range page returns last page."""
        response = self.client.get(reverse("home") + "?page=999")
        self.assertEqual(response.status_code, 200)

    def test_highlight_parameter_in_context(self):
        """Test that highlight parameter is passed to context as integer."""
        response = self.client.get(reverse("home") + f"?highlight={self.game1.id}")
        self.assertEqual(response.status_code, 200)
        # Should be converted to integer for comparison with game.id
        self.assertEqual(response.context["highlight"], self.game1.id)
        self.assertIsInstance(response.context["highlight"], int)

    def test_highlight_invalid_value_is_none(self):
        """Test that invalid highlight value results in None."""
        response = self.client.get(reverse("home") + "?highlight=invalid")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["highlight"])

    def test_sort_by_rank_default(self):
        """Test that default sort is by rank."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should be sorted by rank (1, 2, 50)
        self.assertEqual(games[0], self.game1)  # rank 1
        self.assertEqual(games[1], self.game3)  # rank 2
        self.assertEqual(games[2], self.game2)  # rank 50

    def test_sort_by_year(self):
        """Test sorting by year of release."""
        response = self.client.get(reverse("home") + "?sort=year")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should be sorted by year (1985, 1986, 1987)
        self.assertEqual(games[0], self.game3)  # 1985
        self.assertEqual(games[1], self.game1)  # 1986
        self.assertEqual(games[2], self.game2)  # 1987

    def test_sort_by_name(self):
        """Test sorting alphabetically by name."""
        response = self.client.get(reverse("home") + "?sort=name")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should be sorted alphabetically
        self.assertEqual(games[0], self.game3)  # Super Mario Bros
        self.assertEqual(games[1], self.game1)  # The Legend of Zelda
        self.assertEqual(games[2], self.game2)  # Zelda II

    def test_sort_with_filters(self):
        """Test that sort persists with genre and platform filters."""
        response = self.client.get(
            reverse("home")
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
        response = self.client.get(reverse("home") + "?sort=year")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filters"]["sort"], "year")

    def test_sort_defaults_to_rank_when_invalid(self):
        """Test that invalid sort value falls back to rank."""
        response = self.client.get(reverse("home") + "?sort=invalid")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should fall back to rank sorting
        self.assertEqual(games[0], self.game1)  # rank 1
        self.assertEqual(games[1], self.game3)  # rank 2


class GameSearchPlayedFilterTest(TestCase):
    """Test the played games filter in game search view."""

    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create test games
        self.game1 = Game.objects.create(
            name="Played Game 1", rank=1, year_of_release=2020, igdb_id=1001
        )
        self.game2 = Game.objects.create(
            name="Played Game 2", rank=2, year_of_release=2021, igdb_id=1002
        )
        self.game3 = Game.objects.create(
            name="Unplayed Game", rank=3, year_of_release=2022, igdb_id=1003
        )

        # Mark games 1 and 2 as played by the user
        PlayedGame.objects.create(user=self.user, game=self.game1, igdb_id=1001)
        PlayedGame.objects.create(user=self.user, game=self.game2, igdb_id=1002)

    def test_played_filter_ignored_when_not_authenticated(self):
        """Test that played filter is ignored for anonymous users."""
        response = self.client.get(reverse("home") + "?played=yes")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should return all games since user is not authenticated
        self.assertEqual(len(games), 3)

    def test_played_filter_yes_shows_played_games(self):
        """Test that played=yes filter shows only played games."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("home") + "?played=yes")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should only show played games
        self.assertEqual(len(games), 2)
        self.assertIn(self.game1, games)
        self.assertIn(self.game2, games)
        self.assertNotIn(self.game3, games)

    def test_played_filter_no_shows_unplayed_games(self):
        """Test that played=no filter shows only unplayed games."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("home") + "?played=no")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should only show unplayed games
        self.assertEqual(len(games), 1)
        self.assertIn(self.game3, games)
        self.assertNotIn(self.game1, games)
        self.assertNotIn(self.game2, games)

    def test_played_filter_empty_shows_all_games(self):
        """Test that empty played filter shows all games."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Should show all games
        self.assertEqual(len(games), 3)

    def test_filter_title_includes_played_suffix(self):
        """Test that filter title includes ': Played' suffix."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("home") + "?played=yes")
        self.assertEqual(response.status_code, 200)
        filter_title = response.context["filter_title"]
        self.assertTrue(filter_title.endswith(": Played"))

    def test_filter_title_includes_unplayed_suffix(self):
        """Test that filter title includes ': Unplayed' suffix."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("home") + "?played=no")
        self.assertEqual(response.status_code, 200)
        filter_title = response.context["filter_title"]
        self.assertTrue(filter_title.endswith(": Unplayed"))

    def test_played_in_filters_context(self):
        """Test that played parameter is in filters context."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("home") + "?played=yes")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filters"]["played"], "yes")

    def test_played_filter_not_in_context_for_anonymous(self):
        """Test that played filter is empty for anonymous users."""
        response = self.client.get(reverse("home") + "?played=yes")
        self.assertEqual(response.status_code, 200)
        # For anonymous users, played should be empty
        self.assertEqual(response.context["filters"]["played"], "")


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
        response = self.client.get(reverse("home"))
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
            reverse("home"),
            {"page": 2, "append": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_list_append.html")

    def test_append_mode_contains_game_rows(self):
        """Test that append mode response contains game rows."""
        response = self.client.get(
            reverse("home"),
            {"page": 2, "append": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "game-row")
        self.assertContains(response, "Game 100")  # First game of page 2

    def test_append_mode_contains_metadata(self):
        """Test that append mode returns JSON metadata."""
        response = self.client.get(
            reverse("home"),
            {"page": 2, "append": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, "load-more-meta")
        self.assertContains(response, '"hasMore": false')
        self.assertContains(response, '"loadedCount": 150')

    def test_last_page_has_no_more(self):
        """Test that last page correctly reports no more items."""
        response = self.client.get(reverse("home"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_more"])
        self.assertIsNone(response.context["next_page"])

    def test_filter_with_few_results_no_load_more(self):
        """Test that filters with few results don't show load more."""
        Game.objects.create(name="Unique2021Game", rank=200, year_of_release=2021)

        response = self.client.get(reverse("home"), {"start": 2021, "end": 2021})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["games"]), 1)
        self.assertFalse(response.context["has_more"])

    def test_highlight_beyond_100_uses_standard_page_size(self):
        """Test that highlighting a game beyond position 100 still loads standard page.

        Client-side JS handles loading more games via CSF (client-side filtering).
        The server always returns the standard page size for fast initial load.
        """
        # Get the game at position 120 (rank 121)
        game_120 = Game.objects.get(rank=121)

        response = self.client.get(reverse("home") + f"?highlight={game_120.id}")
        self.assertEqual(response.status_code, 200)
        # Server returns standard page size - client-side loads more if needed
        self.assertEqual(len(response.context["games"]), 100)
        # The highlight parameter is passed to context for client-side handling
        self.assertEqual(response.context["highlight"], game_120.id)

    def test_highlight_within_100_loads_normal_page(self):
        """Test that highlighting a game within position 100 loads normal page size."""
        # Get the game at position 50 (rank 51)
        game_50 = Game.objects.get(rank=51)

        response = self.client.get(reverse("home") + f"?highlight={game_50.id}")
        self.assertEqual(response.status_code, 200)
        # Should load normal 100 games
        self.assertEqual(len(response.context["games"]), 100)
        # Verify the highlighted game is in the results
        game_ids = [g.id for g in response.context["games"]]
        self.assertIn(game_50.id, game_ids)


class DeveloperListViewTest(TestCase):
    """Test the developer list view."""

    def setUp(self):
        # Create developers
        self.dev1 = Developer.objects.create(
            name="Nintendo", slug="nintendo", igdb_id=1
        )
        self.dev2 = Developer.objects.create(name="Capcom", slug="capcom", igdb_id=2)

        # Create games for the developers
        game1 = Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        game1.developers.add(self.dev1)

    def test_developer_list_loads(self):
        """Test that developer list page loads."""
        response = self.client.get(reverse("developers-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "developers/developer_list.html")

    def test_only_shows_developers_with_games(self):
        """Test that only developers with games are shown."""
        response = self.client.get(reverse("developers-list"))
        developers = list(response.context["developers"])
        # Only dev1 has games
        self.assertEqual(len(developers), 1)
        self.assertIn(self.dev1, developers)

    def test_search_filter(self):
        """Test searching developers by name."""
        response = self.client.get(reverse("developers-list") + "?q=nintendo")
        self.assertEqual(response.status_code, 200)
        developers = list(response.context["developers"])
        self.assertIn(self.dev1, developers)

    def test_htmx_request_returns_partial(self):
        """Test that HTMX requests return partial template."""
        response = self.client.get(reverse("developers-list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "developers/includes/_developer_list_content.html"
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
        self.dev = Developer.objects.create(name="Nintendo", slug="nintendo", igdb_id=1)

        # Create games for this developer
        self.game1 = Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        self.game2 = Game.objects.create(name="Game 2", rank=2, year_of_release=2021)
        self.game1.developers.add(self.dev)
        self.game2.developers.add(self.dev)

    def test_developer_detail_loads(self):
        """Test that developer detail page loads."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.dev.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "developers/developer_detail.html")

    def test_context_contains_developer(self):
        """Test that context includes the developer."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.dev.slug})
        )
        self.assertEqual(response.context["developer"], self.dev)

    def test_context_contains_games(self):
        """Test that context includes developer's games."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.dev.slug})
        )
        # Root games are in root_games, subsidiaries in subsidiaries_with_games
        root_games = response.context.get("root_games", [])
        all_games = list(root_games)
        # Also check subsidiaries_with_games for subsidiary games
        subsidiaries_with_games = response.context.get("subsidiaries_with_games", [])
        for subsidiary_data in subsidiaries_with_games:
            all_games.extend(subsidiary_data["games"])
        self.assertEqual(len(all_games), 2)
        self.assertIn(self.game1, all_games)
        self.assertIn(self.game2, all_games)

    def test_context_contains_aliases_data(self):
        """Test that context includes subsidiaries data."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.dev.slug})
        )
        # Root developer's games are in root_games,
        # subsidiaries in subsidiaries_with_games
        self.assertIn("root_games", response.context)

    def test_context_contains_games_data(self):
        """Test that context includes games data."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.dev.slug})
        )
        # Games attributed directly to root developer are in root_games
        root_games = response.context.get("root_games", [])
        # Count all games (root + subsidiaries)
        subsidiaries_with_games = response.context.get("subsidiaries_with_games", [])
        subsidiary_games = sum(len(s["games"]) for s in subsidiaries_with_games)
        total_games = len(root_games) + subsidiary_games
        self.assertEqual(total_games, 2)

    def test_invalid_slug_returns_404(self):
        """Test that invalid slug returns 404."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": "invalid-slug"})
        )
        self.assertEqual(response.status_code, 404)

    def test_unique_game_count_with_sibling_developers(self):
        """
        Test that games attributed to multiple sibling developers
        are only counted once in the total count.
        """
        # Create a parent developer with two sibling subsidiaries
        parent = Developer.objects.create(
            name="Sony Interactive Entertainment", slug="sie"
        )
        dev_a = Developer.objects.create(
            name="Sony Studio A", parent=parent, igdb_id=100
        )
        dev_b = Developer.objects.create(
            name="Sony Studio B", parent=parent, igdb_id=101
        )

        # Create a game attributed to both sibling developers
        shared_game = Game.objects.create(
            name="Shared Game", rank=1, year_of_release=2020
        )
        shared_game.developers.add(dev_a, dev_b)

        # Create games unique to each developer
        game_a_only = Game.objects.create(
            name="Game A Only", rank=2, year_of_release=2021
        )
        game_a_only.developers.add(dev_a)

        game_b_only = Game.objects.create(
            name="Game B Only", rank=3, year_of_release=2022
        )
        game_b_only.developers.add(dev_b)

        # Fetch the developer detail page
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": parent.slug})
        )

        # The total_games count should be 3 (not 4)
        # shared_game appears in both developers but should only be counted once
        self.assertEqual(response.context["total_games"], 3)

        # Verify individual developer counts
        subsidiaries_with_games = response.context["subsidiaries_with_games"]
        dev_a_data = next(
            s for s in subsidiaries_with_games if s["developer"].id == dev_a.id
        )
        dev_b_data = next(
            s for s in subsidiaries_with_games if s["developer"].id == dev_b.id
        )

        # Each developer shows both games (including shared)
        self.assertEqual(dev_a_data["games_count"], 2)
        self.assertEqual(dev_b_data["games_count"], 2)

        # total_games_count includes only that developer + its sub-developers
        # (not sibling developers). Both have no sub-developers, so count is
        # their own games.
        self.assertEqual(dev_a_data["total_games_count"], 2)
        self.assertEqual(dev_b_data["total_games_count"], 2)

    def test_nested_developer_hierarchy(self):
        """
        Test that nested developer hierarchies work correctly.
        When a developer has subsidiaries with their own subsidiaries,
        games from sub-developers should be filtered out from parent's list.
        """
        # Create Nintendo parent developer
        nintendo = Developer.objects.create(name="Nintendo", slug="nintendo-test")

        # Create Nintendo EPD as subsidiary of Nintendo
        nintendo_epd = Developer.objects.create(
            name="Nintendo EPD", parent=nintendo, igdb_id=200
        )

        # Create Nintendo EPD Production Group No. 3 (sub-subsidiary)
        epd_group_3 = Developer.objects.create(
            name="Nintendo EPD Production Group No. 3",
            parent=nintendo_epd,
            igdb_id=300,
        )

        # Create games
        # Game 1: Attributed to BOTH Nintendo EPD AND EPD Group 3
        # (should only show at deepest level - Group 3)
        game1 = Game.objects.create(name="Zelda BOTW", rank=1, year_of_release=2017)
        game1.developers.add(nintendo_epd, epd_group_3)

        # Game 2: Attributed to Nintendo EPD only (should show at EPD level)
        game2 = Game.objects.create(name="Splatoon", rank=2, year_of_release=2015)
        game2.developers.add(nintendo_epd)

        # Fetch the Nintendo developer detail page
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": nintendo.slug})
        )

        # Verify the hierarchy is correct
        subsidiaries_with_games = response.context["subsidiaries_with_games"]
        # Should have Nintendo EPD as a subsidiary
        self.assertGreaterEqual(len(subsidiaries_with_games), 1)

        # Find the Nintendo EPD developer
        epd_data = None
        for dev_data in subsidiaries_with_games:
            if dev_data["developer"].name == "Nintendo EPD":
                epd_data = dev_data
                break

        self.assertIsNotNone(epd_data, "Nintendo EPD should be in the list")

        # EPD should have 1 direct game (Splatoon) - Zelda should be filtered out
        self.assertEqual(epd_data["games_count"], 1)
        self.assertEqual(epd_data["games"][0].name, "Splatoon")

        # EPD should have 1 sub-developer
        self.assertEqual(len(epd_data["sub_developers"]), 1)

        # Check the sub-developer
        group3_data = epd_data["sub_developers"][0]
        self.assertEqual(
            group3_data["developer"].name, "Nintendo EPD Production Group No. 3"
        )
        self.assertEqual(group3_data["games_count"], 1)
        self.assertEqual(group3_data["games"][0].name, "Zelda BOTW")


class DeveloperAliasRedirectViewTest(TestCase):
    """Test the developer alias redirect view."""

    def setUp(self):
        self.parent_dev = Developer.objects.create(name="Nintendo", slug="nintendo")
        self.subsidiary = Developer.objects.create(
            name="Nintendo EAD", parent=self.parent_dev, igdb_id=1
        )

    def test_redirects_to_developer_detail(self):
        """Test that subsidiary redirects to root developer detail page."""
        response = self.client.get(
            reverse("developer-alias-redirect", kwargs={"id": self.subsidiary.id})
        )
        self.assertEqual(response.status_code, 301)  # Permanent redirect
        self.assertRedirects(
            response,
            reverse("developer-detail", kwargs={"slug": self.parent_dev.slug}),
            status_code=301,
        )

    def test_invalid_id_returns_404(self):
        """Test that invalid alias ID returns 404."""
        response = self.client.get(
            reverse("developer-alias-redirect", kwargs={"id": 99999})
        )
        self.assertEqual(response.status_code, 404)


class ListListViewTest(TestCase):
    """Test the list list view with grouped publications."""

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

    def test_context_contains_publication_groups(self):
        """Test that context includes publication_groups with lists."""
        response = self.client.get(reverse("list-list"))
        groups = response.context["publication_groups"]
        self.assertEqual(len(groups), 2)  # Two publishers
        # Check that each group has lists
        total_lists = sum(len(g["lists"]) for g in groups)
        self.assertEqual(total_lists, 2)

    def test_filter_by_year(self):
        """Test filtering lists by year."""
        response = self.client.get(reverse("list-list") + "?year=2020")
        self.assertEqual(response.status_code, 200)
        groups = response.context["publication_groups"]
        # Only IGN has lists in 2020
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["publication"].name, "IGN")
        self.assertEqual(len(groups[0]["lists"]), 1)
        self.assertEqual(groups[0]["lists"][0].year, 2020)

    def test_filter_by_type(self):
        """Test filtering lists by type using URL slug."""
        response = self.client.get(reverse("list-list") + "?type=all-time")
        self.assertEqual(response.status_code, 200)
        groups = response.context["publication_groups"]
        # Only IGN has all-time lists
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["publication"].name, "IGN")
        self.assertEqual(groups[0]["lists"][0].type, "A")

    def test_filter_by_invalid_year_is_ignored(self):
        """Test that invalid (non-numeric) year is ignored."""
        response = self.client.get(reverse("list-list") + "?year=invalid")
        self.assertEqual(response.status_code, 200)
        # All publications should be returned since invalid filter is ignored
        groups = response.context["publication_groups"]
        self.assertEqual(len(groups), 2)

    def test_context_has_meta_data(self):
        """Test that context includes metadata."""
        response = self.client.get(reverse("list-list"))
        self.assertIn("meta", response.context)
        self.assertIn("list_types", response.context)
        self.assertIn("type_counts", response.context)
        self.assertIn("sort", response.context)

    def test_publication_groups_have_type_counts(self):
        """Test that publication groups have type counts."""
        response = self.client.get(reverse("list-list"))
        groups = response.context["publication_groups"]
        ign_group = next(g for g in groups if g["publication"].name == "IGN")
        self.assertEqual(ign_group["alltime_count"], 1)
        self.assertEqual(ign_group["eoy_count"], 0)

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

    def test_sort_by_importance(self):
        """Test that default sort is by importance."""
        # Add more all-time lists to GameSpot so it ranks higher
        List.objects.create(
            name="GS All-time 1", publisher=self.pub2, year=2020, type="A"
        )
        List.objects.create(
            name="GS All-time 2", publisher=self.pub2, year=2020, type="A"
        )
        response = self.client.get(reverse("list-list"))
        groups = response.context["publication_groups"]
        # GameSpot should be first (more all-time lists)
        self.assertEqual(groups[0]["publication"].name, "GameSpot")

    def test_sort_by_alpha(self):
        """Test alphabetical sort."""
        response = self.client.get(reverse("list-list") + "?sort=alpha")
        groups = response.context["publication_groups"]
        # GameSpot comes before IGN alphabetically
        self.assertEqual(groups[0]["publication"].name, "GameSpot")
        self.assertEqual(groups[1]["publication"].name, "IGN")


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

    def test_year_counts_filter_by_type(self):
        """Year counts should reflect type filter."""
        response = self.client.get(reverse("list-list") + "?type=all-time")
        years = response.context["meta"]["lists"]["years"]
        year_dict = {y["year"]: y["count"] for y in years}

        # All-time lists: 2020 has 1 (IGN), 2021 has 1 (Polygon)
        self.assertEqual(year_dict.get(2020), 1)
        self.assertEqual(year_dict.get(2021), 1)

    def test_publication_groups_filter_by_year(self):
        """Publication groups should reflect year filter."""
        response = self.client.get(reverse("list-list") + "?year=2020")
        groups = response.context["publication_groups"]
        pub_names = [g["publication"].name for g in groups]

        # 2020: IGN has 1, GameSpot has 1, Polygon has 0 (should be hidden)
        self.assertIn("IGN", pub_names)
        self.assertIn("GameSpot", pub_names)
        self.assertNotIn("Polygon", pub_names)  # 0 count in 2020

    def test_publication_groups_filter_by_type(self):
        """Publication groups should reflect type filter."""
        response = self.client.get(reverse("list-list") + "?type=end-of-year")
        groups = response.context["publication_groups"]
        pub_names = [g["publication"].name for g in groups]

        # End-of-year: IGN has 1, GameSpot has 2, Polygon has 0
        self.assertIn("IGN", pub_names)
        self.assertIn("GameSpot", pub_names)
        self.assertNotIn("Polygon", pub_names)

    def test_type_counts_filter_by_year(self):
        """Type counts should reflect year filter."""
        response = self.client.get(reverse("list-list") + "?year=2020")
        type_counts = response.context["type_counts"]
        type_dict = {t["type"]: t["count"] for t in type_counts}

        # 2020: 1 All-time (IGN), 1 End-of-year (GameSpot)
        self.assertEqual(type_dict.get("A"), 1)
        self.assertEqual(type_dict.get("E"), 1)

    def test_combined_filters_affect_counts(self):
        """Multiple filters should combine to affect counts."""
        response = self.client.get(reverse("list-list") + "?year=2020&type=all-time")

        # Only IGN 2020 All-time should match
        groups = response.context["publication_groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["publication"].name, "IGN")
        self.assertEqual(len(groups[0]["lists"]), 1)

        # Year counts (filtered by type only)
        years = response.context["meta"]["lists"]["years"]
        year_dict = {y["year"]: y["count"] for y in years}
        self.assertEqual(year_dict.get(2020), 1)  # IGN all-time
        self.assertEqual(year_dict.get(2021), 1)  # Polygon all-time

        # Type counts (filtered by year only)
        type_counts = response.context["type_counts"]
        type_dict = {t["type"]: t["count"] for t in type_counts}
        self.assertEqual(type_dict.get("A"), 1)  # IGN 2020 All-time
        self.assertEqual(type_dict.get("E"), 1)  # GameSpot 2020 EOY

    def test_publications_with_zero_lists_hidden(self):
        """Publications with 0 matching lists should be hidden."""
        response = self.client.get(reverse("list-list") + "?year=2020")
        groups = response.context["publication_groups"]

        # Polygon has 0 lists in 2020
        pub_names = [g["publication"].name for g in groups]
        self.assertNotIn("Polygon", pub_names)


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
        self.wiki_genre, _ = WikipediaGenre.objects.get_or_create(name="Action")
        self.platform = Platform.objects.create(name="PC", code="PC")
        self.dev = Developer.objects.create(name="Test Dev", slug="test-dev", igdb_id=1)

        self.game1 = Game.objects.create(name="Game 1", rank=1, year_of_release=1995)
        self.game1.genres.add(self.genre)
        self.game1.wikipedia_genres.add(self.wiki_genre)
        self.game1.platforms.add(self.platform)
        self.game1.developers.add(self.dev)

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
        expected = (
            "Filtered Rank,Global Rank,Name,Year,Developers,Platforms,Genres,Series"
        )
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
        # Filename uses page title format "the 1990s"
        self.assertIn("1990s", response["Content-Disposition"])
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

    def test_csv_includes_played_column_for_authenticated_user(self):
        """Test that CSV includes Played column for authenticated users."""
        User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("games-download"))
        content = response.content.decode("utf-8")
        lines = content.strip().split("\n")
        header = "Filtered Rank,Global Rank,Name,Year,Developers,Platforms,"
        header += "Genres,Series,Played"
        self.assertEqual(lines[0].strip(), header)

    def test_csv_shows_yes_for_played_games(self):
        """Test that CSV shows 'Yes' for games user has marked as played."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Set igdb_id for game1 and mark as played
        self.game1.igdb_id = 1001
        self.game1.save()
        PlayedGame.objects.create(user=user, game=self.game1, igdb_id=1001)
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("games-download"))
        content = response.content.decode("utf-8")
        # Game 1 should show "Yes" in played column
        self.assertIn("Game 1", content)
        lines = content.strip().split("\n")
        # Find the line with Game 1 (strip \r from CSV line endings)
        game1_line = next(line.strip() for line in lines if "Game 1" in line)
        self.assertTrue(game1_line.endswith(",Yes"))

    def test_csv_shows_no_for_unplayed_games(self):
        """Test that CSV shows 'No' for games user has not marked as played."""
        User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("games-download"))
        content = response.content.decode("utf-8")
        lines = content.strip().split("\n")
        # Both games should show "No" since none are marked as played
        game1_line = next(line.strip() for line in lines if "Game 1" in line)
        game2_line = next(line.strip() for line in lines if "Game 2" in line)
        self.assertTrue(game1_line.endswith(",No"))
        self.assertTrue(game2_line.endswith(",No"))

    def test_csv_respects_played_yes_filter(self):
        """Test that CSV respects played=yes filter."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Set igdb_id for game1 and mark as played
        self.game1.igdb_id = 1001
        self.game1.save()
        PlayedGame.objects.create(user=user, game=self.game1, igdb_id=1001)
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("games-download") + "?played=yes")
        content = response.content.decode("utf-8")
        # Should only include Game 1 (played)
        self.assertIn("Game 1", content)
        self.assertNotIn("Game 2", content)

    def test_csv_respects_played_no_filter(self):
        """Test that CSV respects played=no filter."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Set igdb_id for game1 and mark as played
        self.game1.igdb_id = 1001
        self.game1.save()
        PlayedGame.objects.create(user=user, game=self.game1, igdb_id=1001)
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get(reverse("games-download") + "?played=no")
        content = response.content.decode("utf-8")
        # Should only include Game 2 (unplayed)
        self.assertNotIn("Game 1", content)
        self.assertIn("Game 2", content)

    def test_csv_respects_series_filter(self):
        """Test that CSV respects series filter."""
        from games.models import Series

        # Create a series and add game1 to it
        series = Series.objects.create(name="Test Series", igdb_id=9001)
        self.game1.series.add(series)
        response = self.client.get(reverse("games-download") + f"?series={series.id}")
        content = response.content.decode("utf-8")
        # Should only include Game 1 (in series)
        self.assertIn("Game 1", content)
        self.assertNotIn("Game 2", content)


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
        self.dev = Developer.objects.create(name="Test Dev", slug="test-dev")

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
        # Check for static page paths (homepage at / contains rankings)
        self.assertIn("/developers/", content)
        self.assertIn("/lists/", content)

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


class AuthModalViewsTest(TestCase):
    """Test auth modal views (HTMX partials)."""

    def test_auth_modal_login_get_returns_200(self):
        """Test that login form GET returns 200."""
        response = self.client.get(reverse("auth-modal-login"))
        self.assertEqual(response.status_code, 200)

    def test_auth_modal_login_contains_form_fields(self):
        """Test that login form contains expected fields."""
        response = self.client.get(reverse("auth-modal-login"))
        content = response.content.decode("utf-8")
        self.assertIn('name="login"', content)
        self.assertIn('name="password"', content)
        self.assertIn("Login", content)

    def test_auth_modal_login_post_invalid_credentials(self):
        """Test login with invalid credentials shows error."""
        response = self.client.post(
            reverse("auth-modal-login"),
            {"login": "invalid@example.com", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Should show error, not redirect
        self.assertIn('name="login"', content)

    def test_auth_modal_login_post_valid_credentials(self):
        """Test login with valid credentials returns HX-Redirect."""
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        # Create verified EmailAddress for the user
        EmailAddress.objects.create(
            user=user, email="test@example.com", verified=True, primary=True
        )

        response = self.client.post(
            reverse("auth-modal-login"),
            {"login": "test@example.com", "password": "testpass123"},
        )
        # Should return HX-Redirect header to redirect after login
        self.assertIn("HX-Redirect", response)

    def test_auth_modal_signup_get_returns_200(self):
        """Test that signup form GET returns 200."""
        response = self.client.get(reverse("auth-modal-signup"))
        self.assertEqual(response.status_code, 200)

    def test_auth_modal_signup_contains_form_fields(self):
        """Test that signup form contains expected fields."""
        response = self.client.get(reverse("auth-modal-signup"))
        content = response.content.decode("utf-8")
        self.assertIn('name="email"', content)
        self.assertIn('name="password1"', content)
        self.assertIn('name="password2"', content)
        self.assertIn("Create Account", content)

    def test_auth_modal_signup_post_mismatched_passwords(self):
        """Test signup with mismatched passwords shows error."""
        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "new@example.com",
                "password1": "testpass123",
                "password2": "differentpass",
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Should show form again with error, not redirect
        self.assertIn('name="email"', content)

    def test_auth_modal_signup_post_valid_creates_user(self):
        """Test signup with valid data creates user and shows verification screen."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.assertFalse(User.objects.filter(email="newuser@example.com").exists())

        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "newuser@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        # With mandatory email verification, should show verification screen
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Check Your Email", content)
        self.assertIn("newuser@example.com", content)

        # User should be created
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_auth_modal_signup_sets_username_to_email(self):
        """Test that signup sets username equal to email address."""
        from django.contrib.auth import get_user_model

        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "usernametest@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        # With mandatory verification, shows verification screen (not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Check Your Email", response.content.decode("utf-8"))

        # Username should be the same as email
        User = get_user_model()
        user = User.objects.get(email="usernametest@example.com")
        self.assertEqual(user.username, "usernametest@example.com")

    def test_auth_modal_signup_creates_user_with_profile_fields(self):
        """Test that signup creates User with profile fields."""
        from django.contrib.auth import get_user_model

        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "profileuser@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        # With mandatory verification, shows verification screen (not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Check Your Email", response.content.decode("utf-8"))

        # User should have profile fields directly on the model
        User = get_user_model()
        user = User.objects.get(email="profileuser@example.com")
        self.assertTrue(hasattr(user, "username"))
        self.assertTrue(hasattr(user, "email_subscribed"))
        self.assertFalse(user.email_subscribed)  # Default False

    def test_auth_modal_signup_back_button(self):
        """Test that signup form has back button to login."""
        response = self.client.get(reverse("auth-modal-signup"))
        content = response.content.decode("utf-8")
        self.assertIn("Back", content)
        self.assertIn(reverse("auth-modal-login"), content)

    def test_auth_modal_signup_has_signin_link(self):
        """Test that signup form has link to sign in form."""
        response = self.client.get(reverse("auth-modal-signup"))
        content = response.content.decode("utf-8")
        self.assertIn("Already have an account?", content)
        self.assertIn(reverse("auth-modal-login"), content)

    def test_auth_logout_logs_out_and_redirects(self):
        """Test that logout view logs out user and redirects."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(reverse("auth-logout"))
        # Should redirect to home
        self.assertEqual(response.status_code, 302)
        # User should be logged out
        response = self.client.get(reverse("home"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_auth_modal_profile_unauthenticated_redirects_to_login(self):
        """Test that profile view redirects to login if not authenticated."""
        response = self.client.get(reverse("auth-modal-profile"))
        self.assertEqual(response.status_code, 200)
        # Should have HX-Redirect header to login
        self.assertIn("HX-Redirect", response)

    def test_auth_modal_profile_authenticated_shows_form(self):
        """Test that profile view shows form when authenticated."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

        response = self.client.get(reverse("auth-modal-profile"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Account", content)
        self.assertIn('name="username"', content)
        self.assertIn('name="email_subscribed"', content)
        # Should show played games count
        self.assertIn("games played", content)

    def test_auth_modal_profile_post_updates_profile(self):
        """Test that profile form POST updates user profile."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

        response = self.client.post(
            reverse("auth-modal-profile"),
            {"username": "newusername", "email_subscribed": "on"},
        )
        self.assertEqual(response.status_code, 200)
        # Should trigger page refresh to show updated name
        self.assertEqual(response.get("HX-Refresh"), "true")

        # Verify profile was updated
        user.refresh_from_db()
        self.assertEqual(user.username, "newusername")
        self.assertTrue(user.email_subscribed)

    def test_auth_modal_profile_post_unauthenticated_redirects(self):
        """Test that profile POST without auth returns HX-Redirect."""
        response = self.client.post(
            reverse("auth-modal-profile"),
            {"username": "newusername"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("HX-Redirect"), "/")

    def test_auth_modal_profile_subscribes_user(self):
        """Test that checking email_subscribed updates User subscription fields."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

        # User starts unsubscribed
        self.assertFalse(user.email_subscribed)

        # Subscribe via profile form
        response = self.client.post(
            reverse("auth-modal-profile"),
            {"username": "testuser", "email_subscribed": "on"},
        )
        self.assertEqual(response.status_code, 200)

        # User should now be subscribed (email already verified via allauth)
        user.refresh_from_db()
        self.assertTrue(user.email_subscribed)
        self.assertIsNotNone(user.unsubscribe_token)

    def test_auth_modal_profile_unsubscribes_user(self):
        """Test that unchecking email_subscribed sets User.email_subscribed=False."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            email_subscribed=True,
        )
        self.client.login(username="testuser", password="testpass123")

        # Unsubscribe via profile form (checkbox not checked)
        response = self.client.post(
            reverse("auth-modal-profile"),
            {"username": "testuser"},  # No email_subscribed
        )
        self.assertEqual(response.status_code, 200)

        # User should now be unsubscribed
        user.refresh_from_db()
        self.assertFalse(user.email_subscribed)

    def test_auth_modal_profile_shows_subscription_checkbox_state(self):
        """Test that profile GET shows correct subscription checkbox state."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            email_subscribed=True,
        )
        self.client.login(username="testuser", password="testpass123")

        # GET the profile form - checkbox should be checked
        response = self.client.get(reverse("auth-modal-profile"))
        self.assertEqual(response.status_code, 200)

        # Checkbox should be checked in the form
        content = response.content.decode("utf-8")
        self.assertIn("checked", content)

    def test_auth_modal_forgot_password_get_returns_200(self):
        """Test that forgot password form GET returns 200."""
        response = self.client.get(reverse("auth-modal-forgot-password"))
        self.assertEqual(response.status_code, 200)

    def test_auth_modal_forgot_password_contains_form_fields(self):
        """Test that forgot password form contains expected fields."""
        response = self.client.get(reverse("auth-modal-forgot-password"))
        content = response.content.decode("utf-8")
        self.assertIn('name="email"', content)
        self.assertIn("Send Reset Link", content)
        self.assertIn("Reset Password", content)

    def test_auth_modal_forgot_password_back_button(self):
        """Test that forgot password form has back button to login."""
        response = self.client.get(reverse("auth-modal-forgot-password"))
        content = response.content.decode("utf-8")
        self.assertIn("Back", content)
        self.assertIn(reverse("auth-modal-login"), content)

    def test_auth_modal_forgot_password_post_invalid_email(self):
        """Test forgot password with invalid email shows error."""
        response = self.client.post(
            reverse("auth-modal-forgot-password"),
            {"email": "notanemail"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Should show form again with error
        self.assertIn('name="email"', content)

    def test_auth_modal_forgot_password_post_valid_email_shows_sent(self):
        """Test forgot password with valid email shows success message."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        response = self.client.post(
            reverse("auth-modal-forgot-password"),
            {"email": "test@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Should show success message
        self.assertIn("Check Your Email", content)
        self.assertIn("Return to Login", content)

    def test_auth_modal_forgot_password_has_signin_link(self):
        """Test that forgot password form has link to sign in form."""
        response = self.client.get(reverse("auth-modal-forgot-password"))
        content = response.content.decode("utf-8")
        self.assertIn("Remember your password?", content)
        self.assertIn(reverse("auth-modal-login"), content)

    def test_auth_modal_login_has_forgot_password_link(self):
        """Test that login form has HTMX link to forgot password."""
        response = self.client.get(reverse("auth-modal-login"))
        content = response.content.decode("utf-8")
        self.assertIn("Forgot password?", content)
        self.assertIn(reverse("auth-modal-forgot-password"), content)

    def test_auth_modal_login_unverified_email_shows_message(self):
        """Test that login with unverified email shows verification message."""
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="unverified@example.com",
            email="unverified@example.com",
            password="testpass123",
        )
        # Create EmailAddress record (unverified)
        EmailAddress.objects.create(
            user=user, email="unverified@example.com", verified=False, primary=True
        )

        response = self.client.post(
            reverse("auth-modal-login"),
            {"login": "unverified@example.com", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Email Not Verified", content)
        self.assertIn("unverified@example.com", content)
        self.assertIn("Resend Verification Email", content)

    def test_auth_modal_login_verified_email_logs_in(self):
        """Test that login with verified email logs in successfully."""
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="verified@example.com",
            email="verified@example.com",
            password="testpass123",
        )
        # Create verified EmailAddress record
        EmailAddress.objects.create(
            user=user, email="verified@example.com", verified=True, primary=True
        )

        response = self.client.post(
            reverse("auth-modal-login"),
            {"login": "verified@example.com", "password": "testpass123"},
        )
        # Should return HX-Redirect header (successful login)
        self.assertIn("HX-Redirect", response)

    def test_auth_modal_resend_verification_post_returns_success(self):
        """Test resend verification shows success message."""
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="resend@example.com",
            email="resend@example.com",
            password="testpass123",
        )
        EmailAddress.objects.create(
            user=user, email="resend@example.com", verified=False, primary=True
        )

        response = self.client.post(
            reverse("auth-modal-resend-verification"),
            {"email": "resend@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Email Sent", content)
        self.assertIn("resend@example.com", content)

    def test_auth_modal_resend_verification_nonexistent_email_same_response(self):
        """Test resend shows same message for nonexistent email."""
        response = self.client.post(
            reverse("auth-modal-resend-verification"),
            {"email": "nonexistent@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Should show same success message (prevents enumeration)
        self.assertIn("Email Sent", content)

    def test_verification_sent_template_has_resend_button(self):
        """Test that verification sent screen has resend button."""
        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "newuser2@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        content = response.content.decode("utf-8")
        self.assertIn("Resend email", content)
        self.assertIn(reverse("auth-modal-resend-verification"), content)

    def test_signup_form_has_email_subscribed_checkbox(self):
        """Test that signup form includes newsletter subscription checkbox."""
        response = self.client.get(reverse("auth-modal-signup"))
        content = response.content.decode("utf-8")
        self.assertIn('name="email_subscribed"', content)
        self.assertIn("Email me about news and updates", content)

    def test_signup_with_email_subscribed_sets_subscription(self):
        """Test that signup with checkbox checked sets email_subscribed."""
        from django.contrib.auth import get_user_model

        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "subscriber@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
                "email_subscribed": "on",
            },
        )
        self.assertEqual(response.status_code, 200)

        User = get_user_model()
        user = User.objects.get(email="subscriber@example.com")
        self.assertTrue(user.email_subscribed)
        self.assertIsNotNone(user.date_subscribed)
        self.assertIsNotNone(user.unsubscribe_token)

    def test_signup_without_email_subscribed_stays_unsubscribed(self):
        """Test that signup without checkbox leaves email_subscribed False."""
        from django.contrib.auth import get_user_model

        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "nonsubscriber@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
                # No email_subscribed field
            },
        )
        self.assertEqual(response.status_code, 200)

        User = get_user_model()
        user = User.objects.get(email="nonsubscriber@example.com")
        self.assertFalse(user.email_subscribed)

    def test_signup_username_too_short(self):
        """Test signup with username less than 3 characters shows error."""
        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "short@example.com",
                "username": "ab",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("at least 3 characters", content)

    def test_signup_username_too_long(self):
        """Test signup with username over 30 characters shows error."""
        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "long@example.com",
                "username": "a" * 31,
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("30 characters or fewer", content)

    def test_signup_username_invalid_chars(self):
        """Test signup with special characters in username shows error."""
        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "invalid@example.com",
                "username": "user@name!",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("letters, numbers, underscores", content)

    def test_signup_username_already_taken(self):
        """Test signup with existing username shows error."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="takenuser", email="taken@example.com", password="testpass123"
        )

        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "new@example.com",
                "username": "takenuser",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("already taken", content)

    def test_signup_existing_unverified_email_shows_resend(self):
        """Test signup with existing unverified email shows resend option."""
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="testpass123",
        )
        EmailAddress.objects.create(
            user=user, email="existing@example.com", verified=False, primary=True
        )

        response = self.client.post(
            reverse("auth-modal-signup"),
            {
                "email": "existing@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Email Not Verified", content)
        self.assertIn("Resend Verification Email", content)

    def test_profile_username_too_short(self):
        """Test profile edit with username less than 3 characters shows error."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="profileuser", email="profile@example.com", password="testpass123"
        )
        self.client.login(username="profileuser", password="testpass123")

        response = self.client.post(
            reverse("auth-modal-profile"),
            {"username": "ab"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("at least 3 characters", content)

    def test_profile_username_too_long(self):
        """Test profile edit with username over 30 characters shows error."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="profileuser2",
            email="profile2@example.com",
            password="testpass123",
        )
        self.client.login(username="profileuser2", password="testpass123")

        response = self.client.post(
            reverse("auth-modal-profile"),
            {"username": "a" * 31},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("30 characters or fewer", content)

    def test_profile_username_invalid_chars(self):
        """Test profile edit with special characters shows error."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="profileuser3",
            email="profile3@example.com",
            password="testpass123",
        )
        self.client.login(username="profileuser3", password="testpass123")

        response = self.client.post(
            reverse("auth-modal-profile"),
            {"username": "bad@name!"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("letters, numbers, underscores", content)

    def test_profile_username_already_taken(self):
        """Test profile edit with taken username shows error."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="existingname",
            email="existing2@example.com",
            password="testpass123",
        )
        User.objects.create_user(
            username="myuser", email="myuser@example.com", password="testpass123"
        )
        self.client.login(username="myuser", password="testpass123")

        response = self.client.post(
            reverse("auth-modal-profile"),
            {"username": "existingname"},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("already taken", content)

    def test_email_confirmation_invalid_key(self):
        """Test email confirmation with invalid key shows error."""
        response = self.client.get(
            reverse("account_confirm_email", kwargs={"key": "invalid-key"})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Invalid Verification Link", content)


class ViewHelperFunctionTests(TestCase):
    """Tests for helper functions in views.py."""

    def test_join_names_empty(self):
        """Test _join_names with empty list."""
        from games.views import _join_names

        result = _join_names([])
        self.assertEqual(result, "")

    def test_join_names_single(self):
        """Test _join_names with one name."""
        from games.views import _join_names

        result = _join_names(["Mario"])
        self.assertEqual(result, "Mario")

    def test_join_names_two(self):
        """Test _join_names with two names."""
        from games.views import _join_names

        result = _join_names(["Mario", "Luigi"])
        self.assertEqual(result, "Mario and Luigi")

    def test_join_names_three(self):
        """Test _join_names with three names uses Oxford comma."""
        from games.views import _join_names

        result = _join_names(["Mario", "Luigi", "Peach"])
        self.assertEqual(result, "Mario, Luigi, and Peach")

    def test_build_time_window_empty(self):
        """Test _build_time_window with None values."""
        from games.views import _build_time_window

        result = _build_time_window(None, None, 1970, 2024)
        self.assertEqual(result, "")

    def test_build_time_window_all_time(self):
        """Test _build_time_window returns All Time for full range."""
        from games.views import _build_time_window

        result = _build_time_window(1970, 2024, 1970, 2024)
        self.assertEqual(result, "All Time")

    def test_build_time_window_single_year(self):
        """Test _build_time_window for single year."""
        from games.views import _build_time_window

        result = _build_time_window(2020, 2020, 1970, 2024)
        self.assertEqual(result, "2020")

    def test_build_time_window_decade(self):
        """Test _build_time_window for full decade."""
        from games.views import _build_time_window

        result = _build_time_window(1990, 1999, 1970, 2024)
        self.assertEqual(result, "the 1990s")

    def test_build_time_window_custom_range(self):
        """Test _build_time_window for custom range."""
        from games.views import _build_time_window

        result = _build_time_window(2015, 2020, 1970, 2024)
        self.assertEqual(result, "2015-2020")
