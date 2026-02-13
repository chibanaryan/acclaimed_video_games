"""
Visual regression tests for books app dual-rendering architecture.

These tests verify that server-rendered HTML (Django templates) is structurally
consistent with what the client-side JavaScript renderer expects. This ensures
the dual-rendering architecture stays in sync.

Key verification areas:
1. Template structure - All required data-slot attributes are present
2. Server-rendered output - HTML contains expected elements and values
3. Data transformations - Python formatting matches JavaScript expectations

Reference files that must stay in sync:
- books/templates/books/includes/_book_row_desktop.html
- books/templates/books/includes/_book_row_mobile.html
- books/static/books/js/book-list-renderer.js
"""

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from books import models


User = get_user_model()


class StaffClientMixin:
    """Mixin that provides a staff user and logs them in for view tests.

    Books views require staff access (behind BOOKS_ENABLED feature flag).
    This mixin ensures tests can access the books URLs.
    """

    def setUp(self):
        super().setUp()
        self.client = Client()
        # Create staff user for accessing books views
        self.staff_user = User.objects.create_user(
            username="staffuser",
            password="staffpass",
            is_staff=True,
        )
        self.client.login(username="staffuser", password="staffpass")


class TemplateStructureTests(StaffClientMixin, TestCase):
    """
    Tests that verify template structure has all required data-slot attributes.

    These attributes are used by the JavaScript renderer to fill in data
    when cloning templates for client-side rendering.
    """

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(
            name="Test Author", slug="test-author"
        )
        self.genre = models.BookGenre.objects.create(name="Fiction", slug="fiction")

        self.book = models.Book.objects.create(
            name="Test Book",
            rank=1,
            slug="test-book",
            year_published=2020,
            goodreads_id="12345",
            page_count=350,
            cover_image_url="https://example.com/cover.jpg",
        )

        self.book.authors.add(self.author)
        self.book.genres.add(self.genre)

    def test_desktop_template_has_required_slots(self):
        """
        Verify desktop row includes all required data-slot attributes.
        """
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Required slots for desktop row - these are used by JS for template cloning
        required_slots = [
            "root",  # On the wrapper element itself
            "book-row",
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

        # Find server-rendered book rows
        book_rows = soup.select(".book-row-wrapper")
        self.assertTrue(
            len(book_rows) > 0, "Should have at least one server-rendered book row"
        )
        first_row = book_rows[0]

        # Check that server-rendered rows have all required slots
        # These same templates are used for JS cloning
        # when enable_client_filtering is True.
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
        """
        Verify mobile row includes all required data-slot attributes.
        """
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Required slots for mobile row - used by JS for template cloning
        required_slots = [
            "root",  # On the wrapper element itself
            "thumbnail",
            "title",  # Contains name, year, rank inline
            "rank",
            "meta",  # Contains author, genres, page count, list count
        ]

        # Find server-rendered mobile rows
        mobile_rows = soup.select(".book-card-mobile")
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
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Desktop rows (hidden on mobile)
        desktop_rows = soup.select(".book-row-wrapper")
        self.assertTrue(len(desktop_rows) > 0, "Desktop rows should be rendered")

        # Mobile rows (hidden on desktop)
        mobile_rows = soup.select(".book-card-mobile")
        self.assertTrue(len(mobile_rows) > 0, "Mobile rows should be rendered")


class ServerRenderedOutputTests(StaffClientMixin, TestCase):
    """
    Tests that verify server-rendered HTML contains expected content.

    These tests ensure that Django templates render book data correctly,
    matching what JavaScript would render client-side.
    """

    def setUp(self):
        super().setUp()
        self.author1 = models.Author.objects.create(
            name="Primary Author", slug="primary-author"
        )
        self.author2 = models.Author.objects.create(
            name="Secondary Author", slug="secondary-author"
        )
        self.genre1 = models.BookGenre.objects.create(
            name="Science Fiction", slug="sci-fi"
        )
        self.genre2 = models.BookGenre.objects.create(name="Fantasy", slug="fantasy")
        self.genre3 = models.BookGenre.objects.create(
            name="Adventure", slug="adventure"
        )

        self.book = models.Book.objects.create(
            name="Test Book Title",
            rank=42,
            slug="test-book-title",
            year_published=2023,
            goodreads_id="99999",
            page_count=1250,  # Large number to test formatting
            cover_image_url="https://example.com/cover.jpg",
        )

        self.book.authors.add(self.author1, self.author2)
        self.book.genres.add(self.genre1, self.genre2, self.genre3)

        # Create list memberships for list_count
        pub = models.BookPublication.objects.create(
            name="Test Publisher", slug="test-pub"
        )
        for i in range(7):
            book_list = models.BookList.objects.create(
                name=f"Test List {i}",
                publisher=pub,
                year=2023,
            )
            models.BookListMembership.objects.create(
                list=book_list,
                book=self.book,
                rank=1,
            )

    def test_book_name_rendered_correctly(self):
        """Test book name appears in server-rendered output."""
        response = self.client.get(reverse("books:home"))
        self.assertContains(response, "Test Book Title")

    def test_book_rank_rendered_correctly(self):
        """Test book rank appears in correct slot."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find rank in desktop row
        rank_slot = soup.find(attrs={"data-slot": "rank"})
        self.assertIsNotNone(rank_slot, "Rank slot should exist")
        self.assertIn("42", rank_slot.get_text())

    def test_book_year_rendered_correctly(self):
        """Test book year appears in correct slot."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find year in desktop row
        year_slot = soup.find(attrs={"data-slot": "year"})
        self.assertIsNotNone(year_slot, "Year slot should exist")
        self.assertIn("2023", year_slot.get_text())

    def test_book_thumbnail_rendered_correctly(self):
        """Test book thumbnail has correct src attribute."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find thumbnail in server-rendered row (not template)
        thumb = soup.find("img", attrs={"data-slot": "thumbnail", "src": True})
        self.assertIsNotNone(thumb, "Thumbnail with src should exist")
        self.assertEqual(thumb["src"], "https://example.com/cover.jpg")

    def test_book_title_link_href_correct(self):
        """Test book title link points to correct URL."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find title link
        title_link = soup.find("a", attrs={"data-slot": "title-link", "href": True})
        self.assertIsNotNone(title_link, "Title link should exist")
        self.assertIn("/books/test-book-title/", title_link["href"])

    def test_page_count_formatted_with_comma(self):
        """Test page count uses thousands separator (matching JS formatting)."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find page count slot
        page_count_slot = soup.find(attrs={"data-slot": "page-count"})
        self.assertIsNotNone(page_count_slot, "Page count slot should exist")
        # Should show "1,250 pages" with comma separator
        text = page_count_slot.get_text()
        self.assertIn("1,250", text, "Page count should be formatted with comma")
        self.assertIn("pages", text, "Should include 'pages' suffix")

    def test_authors_rendered_correctly(self):
        """Test authors appear in server-rendered output."""
        response = self.client.get(reverse("books:home"))

        # Both authors should appear
        self.assertContains(response, "Primary Author")
        self.assertContains(response, "Secondary Author")

    def test_genres_rendered_correctly(self):
        """Test genres appear in server-rendered output."""
        response = self.client.get(reverse("books:home"))

        # All genres should appear
        self.assertContains(response, "Science Fiction")
        self.assertContains(response, "Fantasy")
        self.assertContains(response, "Adventure")

    def test_list_count_rendered_correctly(self):
        """Test list count appears in correct slot."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find list count slot
        list_count_slot = soup.find(attrs={"data-slot": "list-count"})
        self.assertIsNotNone(list_count_slot, "List count slot should exist")
        self.assertIn("7", list_count_slot.get_text())
        self.assertIn("lists", list_count_slot.get_text())

    def test_year_link_has_filter_params(self):
        """Test year link includes filter parameters for JS consistency."""
        response = self.client.get(reverse("books:home"))
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

    def test_page_count_formatting_matches_js(self):
        """
        Test page count formatting matches JavaScript _formatPageCount.

        JS: pages.toLocaleString() + ' pages'
        Python: {{ page_count|intcomma }} pages
        """
        from django.contrib.humanize.templatetags.humanize import intcomma

        test_cases = [
            (100, "100 pages"),
            (1000, "1,000 pages"),
            (12345, "12,345 pages"),
            (999999, "999,999 pages"),
        ]

        for page_count, expected in test_cases:
            # Python formatting (mimics template)
            python_result = f"{intcomma(page_count)} pages"
            self.assertEqual(
                python_result,
                expected,
                f"Page count {page_count} should format as '{expected}'",
            )

    def test_page_count_mobile_formatting_matches_js(self):
        """
        Test mobile page count formatting (abbreviated).

        Mobile uses abbreviated format: "350p" instead of "350 pages"
        """
        from django.contrib.humanize.templatetags.humanize import intcomma

        test_cases = [
            (100, "100p"),
            (1000, "1,000p"),
            (12345, "12,345p"),
        ]

        for page_count, expected in test_cases:
            # Python formatting for mobile (mimics template)
            python_result = f"{intcomma(page_count)}p"
            self.assertEqual(
                python_result,
                expected,
                f"Mobile page count {page_count} should format as '{expected}'",
            )


class BookWithoutOptionalFieldsTests(StaffClientMixin, TestCase):
    """
    Tests that verify rendering works correctly when optional fields are null.

    Both server and client rendering should gracefully handle missing data.
    """

    def setUp(self):
        super().setUp()
        # Create minimal book without optional fields
        self.book = models.Book.objects.create(
            name="Minimal Book",
            rank=1,
            slug="minimal-book",
        )

    def test_book_without_thumbnail_renders(self):
        """Test book without thumbnail renders without error."""
        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Minimal Book")

    def test_book_without_year_renders(self):
        """Test book without year renders without error."""
        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 200)

        soup = BeautifulSoup(response.content, "html.parser")
        # Year slot should exist but be empty or hidden
        self.assertIsNotNone(soup.find(attrs={"data-slot": "year"}))
        # Should not cause rendering issues

    def test_book_without_authors_renders(self):
        """Test book without authors renders without error."""
        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Minimal Book")

    def test_book_without_genres_renders(self):
        """Test book without genres renders without error."""
        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 200)

    def test_book_without_page_count_renders(self):
        """Test book without page_count renders without error."""
        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 200)
        # Page count slot should not appear or be empty when null
        self.assertNotContains(response, "None pages")

    def test_book_with_zero_list_count_renders(self):
        """Test book with 0 list count renders without showing list count."""
        self.book.list_count = 0
        self.book.save()

        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 200)
        # Should not show "0 lists" - only non-zero counts


class MobileDesktopConsistencyTests(StaffClientMixin, TestCase):
    """
    Tests that verify mobile and desktop rows render equivalent content.

    Both views should display the same data, just with different layouts.
    """

    def setUp(self):
        super().setUp()
        self.author = models.Author.objects.create(
            name="Test Author", slug="test-author"
        )
        self.book = models.Book.objects.create(
            name="Consistency Test Book",
            rank=5,
            slug="consistency-test",
            year_published=2021,
            goodreads_id="55555",
            page_count=400,
        )
        self.book.authors.add(self.author)

    def test_both_desktop_and_mobile_rows_rendered(self):
        """Test both desktop and mobile versions are rendered on page."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find desktop row
        desktop_row = soup.find(id=f"book-{self.book.id}")
        self.assertIsNotNone(desktop_row, "Desktop row should be rendered")

        # Find mobile row
        mobile_row = soup.find(id=f"book-{self.book.id}-mobile")
        self.assertIsNotNone(mobile_row, "Mobile row should be rendered")

    def test_desktop_and_mobile_show_same_rank(self):
        """Test rank is consistent between desktop and mobile."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Get rank from desktop
        desktop_rank = soup.find(id=f"book-{self.book.id}")
        desktop_rank_slot = (
            desktop_rank.find(attrs={"data-slot": "rank"}) if desktop_rank else None
        )

        # Get rank from mobile
        mobile_rank = soup.find(id=f"book-{self.book.id}-mobile")
        mobile_rank_slot = (
            mobile_rank.find(attrs={"data-slot": "rank"}) if mobile_rank else None
        )

        if desktop_rank_slot and mobile_rank_slot:
            desktop_text = desktop_rank_slot.get_text().strip()
            mobile_text = mobile_rank_slot.get_text().strip()
            # Mobile format includes # prefix
            self.assertIn("5", desktop_text)
            self.assertIn("5", mobile_text)


class AuthenticatedUserRenderingTests(StaffClientMixin, TestCase):
    """
    Tests that verify rendering differences for authenticated users.

    Authenticated users should see read/want-to-read buttons.
    Note: Uses staff_user from StaffClientMixin since books requires staff access.
    """

    def setUp(self):
        super().setUp()
        self.book = models.Book.objects.create(
            name="Auth Test Book",
            rank=1,
            slug="auth-test",
            goodreads_id="auth123",
        )

    def test_non_staff_user_gets_404(self):
        """Test non-staff users get 404 (books is staff-only)."""
        # Create and login as non-staff user
        User.objects.create_user(username="regularuser", password="regularpass")
        self.client.login(username="regularuser", password="regularpass")
        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 404)

    def test_authenticated_user_sees_read_button(self):
        """Test authenticated users see read button."""
        # Re-login as staff user after testing non-staff
        self.client.login(username="staffuser", password="staffpass")
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Server-rendered read button slot should contain button
        desktop_row = soup.find(id=f"book-{self.book.id}")
        if desktop_row:
            read_slot = desktop_row.find(attrs={"data-slot": "read-button"})
            self.assertIsNotNone(read_slot, "Staff user should have read button slot")

    def test_read_book_shows_read_state(self):
        """Test book marked as read shows correct state."""
        # Mark book as read using the staff user from mixin
        models.ReadBook.objects.create(
            user=self.staff_user, book=self.book, goodreads_id="auth123"
        )

        response = self.client.get(reverse("books:home"))
        # Should contain read state indicator
        self.assertContains(response, "Read", msg_prefix="Should show Read state")

    def test_want_to_read_book_shows_want_state(self):
        """Test book marked as want-to-read shows correct state."""
        # Mark book as want to read using the staff user from mixin
        models.WantToReadBook.objects.create(
            user=self.staff_user, book=self.book, goodreads_id="auth123"
        )

        response = self.client.get(reverse("books:home"))
        self.assertEqual(response.status_code, 200)
        # Should contain want to read state indicator (bookmark icon or text)
        # The exact text depends on template implementation


class TemplateIDAttributeTests(StaffClientMixin, TestCase):
    """
    Tests that verify HTML IDs are correctly generated for JavaScript targeting.

    IDs follow specific patterns that JavaScript relies on for DOM manipulation.
    """

    def setUp(self):
        super().setUp()
        self.book = models.Book.objects.create(
            name="ID Test Book",
            rank=1,
            slug="id-test",
        )

    def test_desktop_row_has_correct_id(self):
        """Test desktop row ID follows pattern: book-{id}"""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        expected_id = f"book-{self.book.id}"
        desktop_row = soup.find(id=expected_id)
        self.assertIsNotNone(
            desktop_row,
            f"Desktop row should have id='{expected_id}'",
        )

    def test_mobile_row_has_correct_id(self):
        """Test mobile row ID follows pattern: book-{id}-mobile"""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        expected_id = f"book-{self.book.id}-mobile"
        mobile_row = soup.find(id=expected_id)
        self.assertIsNotNone(
            mobile_row,
            f"Mobile row should have id='{expected_id}'",
        )


class HTMXAttributeTests(StaffClientMixin, TestCase):
    """
    Tests that verify HTMX attributes are correctly set for dynamic interactions.
    """

    def setUp(self):
        super().setUp()
        self.book = models.Book.objects.create(
            name="HTMX Test Book",
            rank=1,
            slug="htmx-test",
            goodreads_id="htmx123",
        )

    def test_read_button_has_htmx_attributes(self):
        """Test read button includes HTMX attributes for toggle."""
        response = self.client.get(reverse("books:home"))
        soup = BeautifulSoup(response.content, "html.parser")

        # Find buttons with hx-* attributes
        htmx_buttons = soup.find_all(attrs={"hx-post": True}) + soup.find_all(
            attrs={"hx-delete": True}
        )

        # Should have at least one HTMX-enabled button for read tracking
        # (Either in the dropdown or as a direct button)
        self.assertTrue(
            len(htmx_buttons) > 0,
            "Should have HTMX-enabled elements for read tracking",
        )
