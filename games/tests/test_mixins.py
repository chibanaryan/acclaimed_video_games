"""Tests for view mixins."""

from django.test import RequestFactory, TestCase
from django.views.generic import ListView

from games import models
from core.mixins import HTMXPartialMixin, RobustPaginationMixin


class RobustPaginationMixinTest(TestCase):
    """Tests for RobustPaginationMixin."""

    def setUp(self):
        self.factory = RequestFactory()
        # Create test games
        for i in range(25):
            models.Game.objects.create(name=f"Game {i}", rank=i)

    def test_valid_page_number(self):
        """Test pagination with valid page number."""

        class TestView(RobustPaginationMixin, ListView):
            model = models.Game
            paginate_by = 10
            paginate_orphans = 0

        view = TestView()
        view.request = self.factory.get("/?page=2")
        queryset = models.Game.objects.all()

        paginator, page_obj, object_list, has_other_pages = view.paginate_queryset(
            queryset, 10
        )

        self.assertEqual(page_obj.number, 2)
        self.assertEqual(len(object_list), 10)
        self.assertTrue(has_other_pages)

    def test_invalid_page_number_returns_last_page(self):
        """Test that invalid page number returns last valid page."""

        class TestView(RobustPaginationMixin, ListView):
            model = models.Game
            paginate_by = 10
            paginate_orphans = 0

        view = TestView()
        view.request = self.factory.get("/?page=999")
        queryset = models.Game.objects.all()

        paginator, page_obj, object_list, has_other_pages = view.paginate_queryset(
            queryset, 10
        )

        # Should return last page (page 3 with 25 items, 10 per page)
        self.assertEqual(page_obj.number, 3)

    def test_non_numeric_page_defaults_to_first(self):
        """Test that non-numeric page defaults to page 1."""

        class TestView(RobustPaginationMixin, ListView):
            model = models.Game
            paginate_by = 10
            paginate_orphans = 0

        view = TestView()
        view.request = self.factory.get("/?page=invalid")
        queryset = models.Game.objects.all()

        paginator, page_obj, object_list, has_other_pages = view.paginate_queryset(
            queryset, 10
        )

        self.assertEqual(page_obj.number, 1)

    def test_empty_queryset(self):
        """Test pagination with empty queryset returns page 1 with no items."""
        models.Game.objects.all().delete()

        class TestView(RobustPaginationMixin, ListView):
            model = models.Game
            paginate_by = 10
            paginate_orphans = 0

        view = TestView()
        view.request = self.factory.get("/")
        queryset = models.Game.objects.all()

        paginator, page_obj, object_list, has_other_pages = view.paginate_queryset(
            queryset, 10
        )

        # Empty queryset returns page 1 with no items
        self.assertEqual(page_obj.number, 1)
        self.assertEqual(len(object_list), 0)
        self.assertFalse(has_other_pages)

    def test_no_page_param_defaults_to_first(self):
        """Test that missing page param defaults to page 1."""

        class TestView(RobustPaginationMixin, ListView):
            model = models.Game
            paginate_by = 10
            paginate_orphans = 0

        view = TestView()
        view.request = self.factory.get("/")
        queryset = models.Game.objects.all()

        paginator, page_obj, object_list, has_other_pages = view.paginate_queryset(
            queryset, 10
        )

        self.assertEqual(page_obj.number, 1)

    def test_empty_paginator_with_page_error_returns_none(self):
        """Test graceful handling when paginator has no pages and page 1 fails."""
        from unittest import mock

        from django.core.paginator import EmptyPage

        class TestView(RobustPaginationMixin, ListView):
            model = models.Game
            paginate_by = 10
            paginate_orphans = 0

        view = TestView()
        view.request = self.factory.get("/?page=999")
        queryset = models.Game.objects.none()  # Empty queryset

        # Mock Paginator to simulate edge case where page(1) also fails
        # Note: Paginator is now in core.mixins (games.mixins re-exports from core)
        with mock.patch("core.mixins.Paginator") as MockPaginator:
            mock_paginator = MockPaginator.return_value
            mock_paginator.num_pages = 0
            mock_paginator.page.side_effect = EmptyPage("No results")

            paginator, page_obj, object_list, has_other_pages = view.paginate_queryset(
                queryset, 10
            )

            # Should return None page_obj and empty list
            self.assertIsNone(page_obj)
            self.assertEqual(object_list, [])
            self.assertFalse(has_other_pages)


class HTMXPartialMixinTest(TestCase):
    """Tests for HTMXPartialMixin."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_htmx_request_returns_partial_template(self):
        """Test that HTMX requests return partial template."""

        class TestView(HTMXPartialMixin, ListView):
            model = models.Game
            template_name = "games/home.html"
            htmx_partial_template = "games/includes/_game_list_content.html"

        view = TestView()
        view.request = self.factory.get("/", HTTP_HX_REQUEST="true")

        templates = view.get_template_names()

        self.assertEqual(templates, ["games/includes/_game_list_content.html"])

    def test_non_htmx_request_returns_full_template(self):
        """Test that non-HTMX requests return full template."""

        class TestView(HTMXPartialMixin, ListView):
            model = models.Game
            template_name = "games/home.html"
            htmx_partial_template = "games/includes/_game_list_content.html"

        view = TestView()
        view.request = self.factory.get("/")
        view.object_list = models.Game.objects.all()

        templates = view.get_template_names()

        # Full template should be first (partial not used for non-HTMX)
        self.assertEqual(templates[0], "games/home.html")
        self.assertNotIn("games/includes/_game_list_content.html", templates)

    def test_htmx_request_without_partial_template_returns_full(self):
        """Test that HTMX request without partial template configured returns full."""

        class TestView(HTMXPartialMixin, ListView):
            model = models.Game
            template_name = "games/home.html"
            # htmx_partial_template not set

        view = TestView()
        view.request = self.factory.get("/", HTTP_HX_REQUEST="true")
        view.object_list = models.Game.objects.all()

        templates = view.get_template_names()

        # Without partial configured, full template is returned
        self.assertEqual(templates[0], "games/home.html")
