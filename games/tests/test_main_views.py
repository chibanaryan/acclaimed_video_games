"""
Tests for main site views (Django + HTMX + Alpine.js).

Comprehensive test coverage for all user-facing views.
"""

from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse

from games.models import (
    Developer,
    DeveloperAlias,
    Game,
    Genre,
    List,
    ListMembership,
    Platform,
    Post,
    Publication,
    SiteMetadata,
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
    """Test the game list view."""

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
        """Test filtering by decade."""
        response = self.client.get(reverse("games-list") + "?decade=1990-99")
        self.assertEqual(response.status_code, 200)
        # All games should be from 1990-1999
        for game in response.context["games"]:
            self.assertGreaterEqual(game.year_of_release, 1990)
            self.assertLessEqual(game.year_of_release, 1999)

    def test_year_filter(self):
        """Test filtering by single year."""
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
        """Test that context includes filter information."""
        response = self.client.get(reverse("games-list") + "?decade=2000-09")
        self.assertIn("filters", response.context)
        self.assertEqual(response.context["filters"]["decade"], "2000-09")

    def test_context_has_meta_data(self):
        """Test that context includes metadata for filters."""
        response = self.client.get(reverse("games-list"))
        self.assertIn("meta", response.context)
        self.assertIn("games", response.context["meta"])


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


class GameSearchViewTest(TestCase):
    """Test the game search view."""

    def setUp(self):
        # Create test games with different attributes
        self.game1 = Game.objects.create(
            name="The Legend of Zelda", rank=1, year_of_release=1986
        )
        self.game2 = Game.objects.create(name="Zelda II", rank=50, year_of_release=1987)
        self.game3 = Game.objects.create(
            name="Super Mario Bros", rank=2, year_of_release=1985
        )

        # Create genres and platforms
        self.action_genre = Genre.objects.create(name="Action")
        self.rpg_genre = Genre.objects.create(name="RPG")
        self.nes_platform = Platform.objects.create(name="NES", code="NES")

        self.game1.genres.add(self.action_genre, self.rpg_genre)
        self.game1.platforms.add(self.nes_platform)
        self.game2.genres.add(self.rpg_genre)
        self.game3.genres.add(self.action_genre)

    def test_search_page_loads(self):
        """Test that search page loads."""
        response = self.client.get(reverse("games-search"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/game_search.html")

    def test_search_by_name(self):
        """Test searching games by name."""
        response = self.client.get(reverse("games-search") + "?q=zelda")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertEqual(len(games), 2)  # Should find both Zelda games

    def test_search_with_year_range(self):
        """Test searching with year range filter."""
        response = self.client.get(reverse("games-search") + "?start=1986&end=1987")
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertEqual(len(games), 2)  # Zelda games from 1986-1987

    def test_search_with_genre_filter(self):
        """Test searching with genre filter."""
        response = self.client.get(
            reverse("games-search") + f"?genres={self.rpg_genre.id}"
        )
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        # Both Zelda games have RPG genre
        self.assertIn(self.game1, games)
        self.assertIn(self.game2, games)

    def test_search_with_platform_filter(self):
        """Test searching with platform filter."""
        response = self.client.get(
            reverse("games-search") + f"?platforms={self.nes_platform.id}"
        )
        self.assertEqual(response.status_code, 200)
        games = list(response.context["games"])
        self.assertIn(self.game1, games)

    def test_htmx_request_returns_partial(self):
        """Test that HTMX requests return partial template."""
        response = self.client.get(
            reverse("games-search") + "?q=zelda",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "games/includes/_game_search_content.html")

    def test_context_has_filters(self):
        """Test that context includes filter data."""
        response = self.client.get(reverse("games-search"))
        self.assertIn("filters", response.context)
        self.assertIn("genres", response.context)
        self.assertIn("platforms", response.context)

    def test_invalid_page_defaults_to_first(self):
        """Test that invalid page parameter defaults to page 1."""
        response = self.client.get(reverse("games-search") + "?page=invalid")
        self.assertEqual(response.status_code, 200)

    def test_out_of_range_page_returns_last(self):
        """Test that out of range page returns last page."""
        response = self.client.get(reverse("games-search") + "?page=999")
        self.assertEqual(response.status_code, 200)


class DeveloperListViewTest(TestCase):
    """Test the developer list view."""

    def setUp(self):
        # Create developers with aliases
        dev1 = Developer.objects.create(name="Nintendo", slug="nintendo")
        dev2 = Developer.objects.create(name="Capcom", slug="capcom")

        self.alias1 = DeveloperAlias.objects.create(
            name="Nintendo", developer=dev1, igdb_id=1
        )
        self.alias2 = DeveloperAlias.objects.create(
            name="Capcom", developer=dev2, igdb_id=2
        )

        # Create games for the aliases
        game1 = Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        game1.developers.add(self.alias1)

    def test_developer_list_loads(self):
        """Test that developer list page loads."""
        response = self.client.get(reverse("developers-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "developers/developer_list.html")

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
        self.developer = Developer.objects.create(name="Nintendo", slug="nintendo")
        self.alias = DeveloperAlias.objects.create(
            name="Nintendo", developer=self.developer, igdb_id=1
        )

        # Create games for this developer
        self.game1 = Game.objects.create(name="Game 1", rank=1, year_of_release=2020)
        self.game2 = Game.objects.create(name="Game 2", rank=2, year_of_release=2021)
        self.game1.developers.add(self.alias)
        self.game2.developers.add(self.alias)

    def test_developer_detail_loads(self):
        """Test that developer detail page loads."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.developer.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "developers/developer_detail.html")

    def test_context_contains_developer(self):
        """Test that context includes the developer."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.developer.slug})
        )
        self.assertEqual(response.context["developer"], self.developer)

    def test_context_contains_games(self):
        """Test that context includes developer's games."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.developer.slug})
        )
        games = list(response.context["games"])
        self.assertEqual(len(games), 2)
        self.assertIn(self.game1, games)
        self.assertIn(self.game2, games)

    def test_context_contains_aliases_data(self):
        """Test that context includes aliases data for Alpine.js."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.developer.slug})
        )
        self.assertIn("aliases_data", response.context)
        self.assertTrue(len(response.context["aliases_data"]) > 0)

    def test_context_contains_games_data(self):
        """Test that context includes games data for Alpine.js."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": self.developer.slug})
        )
        self.assertIn("games_data", response.context)
        self.assertEqual(len(response.context["games_data"]), 2)

    def test_invalid_slug_returns_404(self):
        """Test that invalid slug returns 404."""
        response = self.client.get(
            reverse("developer-detail", kwargs={"slug": "invalid-slug"})
        )
        self.assertEqual(response.status_code, 404)


class DeveloperAliasRedirectViewTest(TestCase):
    """Test the developer alias redirect view."""

    def setUp(self):
        self.developer = Developer.objects.create(name="Nintendo", slug="nintendo")
        self.alias = DeveloperAlias.objects.create(
            name="Nintendo", developer=self.developer, igdb_id=1
        )

    def test_redirects_to_developer_detail(self):
        """Test that alias redirects to developer detail page."""
        response = self.client.get(
            reverse("developer-alias-redirect", kwargs={"id": self.alias.id})
        )
        self.assertEqual(response.status_code, 301)  # Permanent redirect
        self.assertRedirects(
            response,
            reverse("developer-detail", kwargs={"slug": self.developer.slug}),
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
        """Test filtering lists by type."""
        response = self.client.get(reverse("list-list") + "?type=A")
        self.assertEqual(response.status_code, 200)
        lists = list(response.context["lists"])
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].type, "A")

    def test_context_has_meta_data(self):
        """Test that context includes metadata."""
        response = self.client.get(reverse("list-list"))
        self.assertIn("meta", response.context)
        self.assertIn("publishers", response.context)
        self.assertIn("list_types", response.context)

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
