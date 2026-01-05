"""
Basic tests for books app admin configuration.
"""

from django.contrib import admin
from django.test import TestCase

from . import models
from .admin import (
    AuthorAdmin,
    BookAdmin,
    BookGenreAdmin,
    BookListMembershipAdmin,
    BookSeriesAdmin,
    GoodreadsBookDataAdmin,
    ReadBookAdmin,
    WantToReadBookAdmin,
    WikipediaBookDataAdmin,
)


class AdminRegistrationTests(TestCase):
    """Test that all admin classes are properly registered."""

    def test_author_admin_registered(self):
        """Author model should be registered with AuthorAdmin."""
        self.assertIn(models.Author, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.Author], AuthorAdmin)

    def test_book_admin_registered(self):
        """Book model should be registered with BookAdmin."""
        self.assertIn(models.Book, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.Book], BookAdmin)

    def test_book_genre_admin_registered(self):
        """BookGenre model should be registered with BookGenreAdmin."""
        self.assertIn(models.BookGenre, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.BookGenre], BookGenreAdmin)

    def test_book_series_admin_registered(self):
        """BookSeries model should be registered with BookSeriesAdmin."""
        self.assertIn(models.BookSeries, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.BookSeries], BookSeriesAdmin)

    def test_goodreads_book_data_admin_registered(self):
        """GoodreadsBookData model should be registered."""
        self.assertIn(models.GoodreadsBookData, admin.site._registry)
        self.assertIsInstance(
            admin.site._registry[models.GoodreadsBookData], GoodreadsBookDataAdmin
        )

    def test_wikipedia_book_data_admin_registered(self):
        """WikipediaBookData model should be registered."""
        self.assertIn(models.WikipediaBookData, admin.site._registry)
        self.assertIsInstance(
            admin.site._registry[models.WikipediaBookData], WikipediaBookDataAdmin
        )

    def test_book_list_membership_admin_registered(self):
        """BookListMembership model should be registered."""
        self.assertIn(models.BookListMembership, admin.site._registry)
        self.assertIsInstance(
            admin.site._registry[models.BookListMembership], BookListMembershipAdmin
        )

    def test_read_book_admin_registered(self):
        """ReadBook model should be registered with ReadBookAdmin."""
        self.assertIn(models.ReadBook, admin.site._registry)
        self.assertIsInstance(admin.site._registry[models.ReadBook], ReadBookAdmin)

    def test_want_to_read_book_admin_registered(self):
        """WantToReadBook model should be registered."""
        self.assertIn(models.WantToReadBook, admin.site._registry)
        self.assertIsInstance(
            admin.site._registry[models.WantToReadBook], WantToReadBookAdmin
        )


class AdminConfigurationTests(TestCase):
    """Test admin configuration options."""

    def test_book_admin_list_display(self):
        """BookAdmin should have expected list_display fields."""
        admin_instance = admin.site._registry[models.Book]
        expected_fields = ["name", "slug", "rank", "year_published", "goodreads_id"]
        for field in expected_fields:
            self.assertIn(
                field,
                admin_instance.list_display,
                f"{field} should be in BookAdmin.list_display",
            )

    def test_book_admin_search_fields(self):
        """BookAdmin should allow searching by name and IDs."""
        admin_instance = admin.site._registry[models.Book]
        expected_fields = ["name", "goodreads_id", "isbn"]
        for field in expected_fields:
            self.assertIn(
                field,
                admin_instance.search_fields,
                f"{field} should be in BookAdmin.search_fields",
            )

    def test_author_admin_has_inline(self):
        """AuthorAdmin should have SubsidiaryAuthorInline."""
        admin_instance = admin.site._registry[models.Author]
        self.assertTrue(
            len(admin_instance.inlines) > 0,
            "AuthorAdmin should have at least one inline",
        )
