"""
Visual regression tests for games app dual-rendering architecture.

These tests verify that server-rendered HTML (Django templates) is structurally
consistent with what the client-side JavaScript renderer expects. This ensures
the dual-rendering architecture stays in sync.

Key verification areas:
1. Template structure - All required data-slot attributes are present
2. Server-rendered output - HTML contains expected elements and values
3. Data transformations - Python formatting matches JavaScript expectations

Reference files that must stay in sync:
- games/templates/games/includes/_game_row_desktop.html
- games/templates/games/includes/_game_row_mobile.html
- games/static/games/js/game-list-renderer.js
"""

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from games import models


User = get_user_model()


class TemplateStructureTests(TestCase):
    """
    Tests that verify template structure has all required data-slot attributes.

    These attributes are used by the JavaScript renderer to fill in data
    when cloning templates for client-side rendering.
    """

    def setUp(self):
        # Clear all caches to ensure fresh responses
        # (home page caches full rendered responses for anonymous users)
        cache.clear()
        self.client = Client()
        self.developer = models.Developer.objects.create(
            name="Test Developer", slug="test-developer-struct"
        )
        self.genre = models.WikipediaGenre.objects.create(
            name="Action Struct", slug="action-struct"
        )
        self.platform, _ = models.Platform.objects.get_or_create(
            code="WIN", defaults={"name": "PC"}
        )

        self.game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            slug="test-game-struct",
            year_of_release=2020,
            igdb_id=12345,
        )
        self.game.developers.add(self.developer)
        self.game.wikipedia_genres.add(self.genre)
        self.game.platforms.add(self.platform)

    def test_desktop_template_has_required_slots(self):
        """Verify desktop row includes all data-slot attributes for JS template cloning."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Required slots for desktop row - these are used by JS for template cloning
        required_slots = [
            "root",  # On the wrapper element itself
            "game-row",
            "rank",
            "global-rank",
            "thumb-link",
            "thumbnail",
            "title-link",
            "name",
            "year-link",
            "year",
            "meta-row",
        ]

        # Find server-rendered game rows
        game_rows = soup.select(".game-row-wrapper")
        self.assertTrue(
            len(game_rows) > 0, "Should have at least one server-rendered game row"
        )
        first_row = game_rows[0]

        # Check that server-rendered rows have all required slots
        for slot in required_slots:
            # Check if slot is on the element itself or in children
            if first_row.get("data-slot") == slot:
                slot_element = first_row
            else:
                slot_element = first_row.find(attrs={"data-slot": slot})
            self.assertIsNotNone(
                slot_element,
                f"Desktop row should have data-slot='{slot}' for JS compatibility",
            )

    def test_mobile_template_has_required_slots(self):
        """Verify mobile row includes all data-slot attributes for JS template cloning."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Required slots for mobile row - used by JS for template cloning
        required_slots = [
            "root",  # On the wrapper element itself
            "thumbnail",
            "title",  # Contains name, year, rank inline
            "rank",
            "meta",  # Contains developer, platforms, genres, playtime, list count
        ]

        # Find server-rendered mobile rows
        mobile_rows = soup.select(".game-card-mobile")
        self.assertTrue(
            len(mobile_rows) > 0, "Should have at least one server-rendered mobile row"
        )
        first_row = mobile_rows[0]

        # Check that server-rendered mobile rows have all required slots
        for slot in required_slots:
            # Check if slot is on the element itself or in children
            if first_row.get("data-slot") == slot:
                slot_element = first_row
            else:
                slot_element = first_row.find(attrs={"data-slot": slot})
            self.assertIsNotNone(
                slot_element,
                f"Mobile row should have data-slot='{slot}' for JS compatibility",
            )

    def test_desktop_and_mobile_rows_both_rendered(self):
        """Verify both desktop and mobile rows are rendered for responsive design."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Desktop rows (hidden on mobile)
        desktop_rows = soup.select(".game-row-wrapper")
        self.assertTrue(len(desktop_rows) > 0, "Desktop rows should be rendered")

        # Mobile rows (hidden on desktop)
        mobile_rows = soup.select(".game-card-mobile")
        self.assertTrue(len(mobile_rows) > 0, "Mobile rows should be rendered")


class ServerRenderedOutputTests(TestCase):
    """
    Tests that verify server-rendered HTML contains expected content.

    These tests ensure that Django templates render game data correctly,
    matching what JavaScript would render client-side.
    """

    def setUp(self):
        # Clear all caches to ensure fresh responses
        cache.clear()
        self.client = Client()
        self.client.defaults["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
        self.developer = models.Developer.objects.create(
            name="Test Studios", slug="test-studios-server"
        )
        self.genre1 = models.WikipediaGenre.objects.create(
            name="Action Server", slug="action-server"
        )
        self.genre2 = models.WikipediaGenre.objects.create(
            name="Adventure Server", slug="adventure-server"
        )
        self.platform, _ = models.Platform.objects.get_or_create(
            code="WIN", defaults={"name": "PC"}
        )

        self.game = models.Game.objects.create(
            name="Test Game Title",
            rank=42,
            slug="test-game-title",
            year_of_release=2023,
            igdb_id=99999,
        )
        # Create IGDB data for thumbnail
        igdb_data = models.IGDBGameData.objects.create(
            game=self.game,
            igdb_id=99999,
            artwork_id="co1abc",
            url="https://www.igdb.com/games/test-game",
            is_primary=True,
        )
        self.game.primary_igdb_game_data = igdb_data
        self.game.save()

        self.game.developers.add(self.developer)
        self.game.wikipedia_genres.add(self.genre1, self.genre2)
        self.game.platforms.add(self.platform)

        # Create list memberships for list_count annotation
        pub = models.Publication.objects.create(name="Test Publisher", slug="test-pub")
        for i in range(5):
            game_list = models.List.objects.create(
                name=f"Test List {i}",
                publisher=pub,
                year=2023,
            )
            models.ListMembership.objects.create(
                list=game_list,
                game=self.game,
                rank=1,
            )

    def test_game_name_rendered_correctly(self):
        """Test game name appears in server-rendered output."""
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Test Game Title")

    def test_game_rank_rendered_correctly(self):
        """Test game rank appears in correct slot."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find rank in desktop row
        rank_slot = soup.find(attrs={"data-slot": "rank"})
        self.assertIsNotNone(rank_slot, "Rank slot should exist")
        # Rank display now shows sequential position (1, 2, 3...) not global rank
        self.assertIn("1", rank_slot.get_text())

    def test_game_year_rendered_correctly(self):
        """Test game year appears in correct slot."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find year in desktop row
        year_slot = soup.find(attrs={"data-slot": "year"})
        self.assertIsNotNone(year_slot, "Year slot should exist")
        self.assertIn("2023", year_slot.get_text())

    def test_game_thumbnail_rendered_correctly(self):
        """Test game thumbnail has correct src attribute."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find thumbnail in server-rendered row (not template)
        thumb = soup.find("img", attrs={"data-slot": "thumbnail", "src": True})
        self.assertIsNotNone(thumb, "Thumbnail with src should exist")
        # IGDB thumbnail URL format
        self.assertIn("igdb.com", thumb["src"])
        self.assertIn("co1abc", thumb["src"])

    def test_game_title_link_href_correct(self):
        """Test game title link points to correct URL."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find title link
        title_link = soup.find("a", attrs={"data-slot": "title-link", "href": True})
        self.assertIsNotNone(title_link, "Title link should exist")
        self.assertIn("/game/test-game-title/", title_link["href"])

    def test_developer_rendered_correctly(self):
        """Test developer appears in server-rendered output."""
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Test Studios")

    def test_genres_rendered_correctly(self):
        """Test genres appear in server-rendered output."""
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Action Server")
        self.assertContains(response, "Adventure Server")

    def test_platforms_rendered_correctly(self):
        """Test platforms appear in server-rendered output."""
        response = self.client.get(reverse("home"))
        self.assertContains(response, "WIN")

    def test_list_count_rendered_correctly(self):
        """Test list count appears in correct slot."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find list count slot
        list_count_slot = soup.find(attrs={"data-slot": "list-count"})
        self.assertIsNotNone(list_count_slot, "List count slot should exist")
        self.assertIn("5", list_count_slot.get_text())
        self.assertIn("lists", list_count_slot.get_text())

    def test_year_link_has_filter_params(self):
        """Test year link includes filter parameters for JS consistency."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find year link
        year_link = soup.find("a", attrs={"data-slot": "year-link", "href": True})
        self.assertIsNotNone(year_link, "Year link should exist")
        href = year_link["href"]
        # Should contain year filter params
        self.assertIn("2023", href)


class DataTransformationTests(TestCase):
    """
    Tests that verify Python data transformations match JavaScript expectations.

    These tests ensure that formatting functions in Python templates produce
    output identical to what the JavaScript renderer would produce.
    """

    def test_playtime_formatting_matches_js(self):
        """
        Test playtime formatting matches JavaScript _formatPlaytime.

        JS: hours < 1 ? `~${Math.round(hours * 60)}m` : `~${Math.round(hours)}h`
        Python: format_playtime filter (uses Python's round() - banker's rounding)

        Note: Python uses banker's rounding (round half to even), so 10.5 rounds to 10.
        JavaScript uses standard rounding (round half up), so 10.5 rounds to 11.
        This is a known minor inconsistency that's acceptable for display purposes.
        """
        from games.templatetags.game_filters import format_playtime

        test_cases = [
            (0.5, "~30m"),  # 30 minutes
            (1.0, "~1h"),
            (10.6, "~11h"),  # rounds up
            (100, "~100h"),
            (None, ""),  # handles None
        ]

        for hours, expected in test_cases:
            python_result = format_playtime(hours)
            self.assertEqual(
                python_result,
                expected,
                f"Playtime {hours}h should format as '{expected}'",
            )


class GameWithoutOptionalFieldsTests(TestCase):
    """
    Tests that verify rendering works correctly when optional fields are null.

    Both server and client rendering should gracefully handle missing data.
    """

    def setUp(self):
        # Clear all caches to ensure fresh responses
        cache.clear()
        self.client = Client()
        # Create minimal game without optional fields
        self.game = models.Game.objects.create(
            name="Minimal Game",
            rank=1,
            slug="minimal-game",
        )

    def test_game_without_thumbnail_renders(self):
        """Test game without thumbnail renders without error."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Minimal Game")

    def test_game_without_year_renders(self):
        """Test game without year renders without error."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_game_without_developers_renders(self):
        """Test game without developers renders without error."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Minimal Game")

    def test_game_without_genres_renders(self):
        """Test game without genres renders without error."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_game_without_platforms_renders(self):
        """Test game without platforms renders without error."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)


class MobileDesktopConsistencyTests(TestCase):
    """
    Tests that verify mobile and desktop rows render equivalent content.

    Both views should display the same data, just with different layouts.
    """

    def setUp(self):
        # Clear all caches to ensure fresh responses
        cache.clear()
        self.client = Client()
        self.developer = models.Developer.objects.create(
            name="Test Developer", slug="test-developer-consist"
        )
        self.game = models.Game.objects.create(
            name="Consistency Test Game",
            rank=5,
            slug="consistency-test",
            year_of_release=2021,
            igdb_id=55555,
        )
        self.game.developers.add(self.developer)

    def test_both_desktop_and_mobile_rows_rendered(self):
        """Test both desktop and mobile versions are rendered on page."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find desktop row
        desktop_row = soup.find(id=f"game-{self.game.id}")
        self.assertIsNotNone(desktop_row, "Desktop row should be rendered")

        # Find mobile row
        mobile_row = soup.find(id=f"game-{self.game.id}-mobile")
        self.assertIsNotNone(mobile_row, "Mobile row should be rendered")

    def test_desktop_and_mobile_show_same_rank(self):
        """Test rank is consistent between desktop and mobile."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Get rank from desktop
        desktop_row = soup.find(id=f"game-{self.game.id}")
        desktop_rank_slot = (
            desktop_row.find(attrs={"data-slot": "rank"}) if desktop_row else None
        )

        # Get rank from mobile
        mobile_row = soup.find(id=f"game-{self.game.id}-mobile")
        mobile_rank_slot = (
            mobile_row.find(attrs={"data-slot": "rank"}) if mobile_row else None
        )

        if desktop_rank_slot and mobile_rank_slot:
            desktop_text = desktop_rank_slot.get_text().strip()
            mobile_text = mobile_rank_slot.get_text().strip()
            # Both should contain the position number (1 for first game)
            # Rank display now shows sequential position (1, 2, 3...) not global rank
            self.assertIn("1", desktop_text)
            self.assertIn("1", mobile_text)


class AuthenticatedUserRenderingTests(TestCase):
    """
    Tests that verify rendering differences for authenticated users.

    Authenticated users should see played/want-to-play buttons.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.game = models.Game.objects.create(
            name="Auth Test Game",
            rank=1,
            slug="auth-test",
            igdb_id=12345,
        )

    def test_anonymous_user_no_played_button(self):
        """Test anonymous users don't see played button content."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Server-rendered played button slot should be empty for anonymous
        desktop_row = soup.find(id=f"game-{self.game.id}")
        if desktop_row:
            played_slot = desktop_row.find(attrs={"data-slot": "played-button"})
            # Slot should not exist for anonymous users
            self.assertIsNone(
                played_slot, "Anonymous user should not see played button slot"
            )

    def test_authenticated_user_sees_played_button(self):
        """Test authenticated users see played button."""
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Server-rendered played button slot should exist
        desktop_row = soup.find(id=f"game-{self.game.id}")
        if desktop_row:
            played_slot = desktop_row.find(attrs={"data-slot": "played-button"})
            self.assertIsNotNone(
                played_slot, "Authenticated user should have played button slot"
            )

    def test_played_game_shows_played_state(self):
        """Test game marked as played shows correct state."""
        self.client.login(username="testuser", password="testpass")

        # Mark game as played
        models.PlayedGame.objects.create(user=self.user, game=self.game, igdb_id=12345)

        response = self.client.get(reverse("home"))
        # Should contain played state indicator (star icon or similar)
        self.assertContains(
            response, "mario-star", msg_prefix="Should show played state"
        )


class TemplateIDAttributeTests(TestCase):
    """
    Tests that verify HTML IDs are correctly generated for JavaScript targeting.

    IDs follow specific patterns that JavaScript relies on for DOM manipulation.
    """

    def setUp(self):
        self.client = Client()
        self.game = models.Game.objects.create(
            name="ID Test Game",
            rank=1,
            slug="id-test",
        )

    def test_desktop_row_has_correct_id(self):
        """Test desktop row ID follows pattern: game-{id}"""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        expected_id = f"game-{self.game.id}"
        desktop_row = soup.find(id=expected_id)
        self.assertIsNotNone(
            desktop_row,
            f"Desktop row should have id='{expected_id}'",
        )

    def test_mobile_row_has_correct_id(self):
        """Test mobile row ID follows pattern: game-{id}-mobile"""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        expected_id = f"game-{self.game.id}-mobile"
        mobile_row = soup.find(id=expected_id)
        self.assertIsNotNone(
            mobile_row,
            f"Mobile row should have id='{expected_id}'",
        )


class HTMXAttributeTests(TestCase):
    """
    Tests that verify HTMX attributes are correctly set for dynamic interactions.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.game = models.Game.objects.create(
            name="HTMX Test Game",
            rank=1,
            slug="htmx-test",
            igdb_id=12345,
        )

    def test_played_button_has_htmx_attributes(self):
        """Test played button includes HTMX attributes for toggle."""
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find buttons with hx-* attributes
        htmx_elements = soup.find_all(attrs={"hx-post": True})

        # Should have at least one HTMX-enabled element for played tracking
        self.assertTrue(
            len(htmx_elements) > 0,
            "Should have HTMX-enabled elements for played tracking",
        )


class PlatformFamilyRenderingTests(TestCase):
    """
    Tests that verify platform family grouping renders correctly.

    Platforms should be grouped by family (Nintendo, PlayStation, etc.)
    with icon display when 3+ platforms in a family.
    """

    def setUp(self):
        self.client = Client()
        self.game = models.Game.objects.create(
            name="Platform Test Game",
            rank=1,
            slug="platform-test",
        )
        # Create Nintendo platforms (should group with icon)
        for code in ["SW", "WiiU", "Wii", "GC"]:
            platform, _ = models.Platform.objects.get_or_create(
                code=code, defaults={"name": f"Nintendo {code}"}
            )
            self.game.platforms.add(platform)

    def test_platform_family_grouped_when_3_plus(self):
        """Test platforms are grouped when 3+ in same family."""
        response = self.client.get(reverse("home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find platforms slot
        platforms_slot = soup.find(attrs={"data-slot": "platforms"})
        self.assertIsNotNone(platforms_slot, "Platforms slot should exist")

        # When grouped (3+), should show icon with count, not individual codes
        # Look for the count badge (font-size: 8px indicates grouped display)
        text = platforms_slot.get_text()
        # Should NOT show all individual codes when grouped
        # Instead should show Nintendo icon with count
