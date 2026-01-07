"""Tests for Goodreads CSV importer."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase

from books.models import Author, Book, ReadBook, WantToReadBook
from books.services.goodreads_importer import import_goodreads_csv


User = get_user_model()


class GoodreadsImporterTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="reader",
            password="password",
        )

    def test_import_creates_read_and_want(self):
        Book.objects.create(
            name="Book One",
            slug="book-one",
            rank=1,
            goodreads_id="123",
        )

        csv_data = (
            "Book Id,Title,Author,Exclusive Shelf,Date Read,Bookshelves\n"
            "123,Book One,Author A,read,2020/01/01,\n"
            "456,Book Two,Author B,to-read,,\n"
            "789,Book Three,Author C,currently-reading,,\n"
            "123,Book One,Author A,to-read,,\n"
            ",Book Four,Author D,read,,\n"
        )

        summary = import_goodreads_csv(StringIO(csv_data), self.user)

        self.assertEqual(summary.total_rows, 5)
        self.assertEqual(summary.processed_books, 3)
        self.assertEqual(summary.read_added, 1)
        self.assertEqual(summary.want_added, 2)
        self.assertEqual(summary.skipped_no_id, 1)
        self.assertEqual(summary.duplicate_rows, 1)

        self.assertTrue(
            ReadBook.objects.filter(user=self.user, goodreads_id="123").exists()
        )
        self.assertTrue(
            WantToReadBook.objects.filter(user=self.user, goodreads_id="456").exists()
        )
        self.assertTrue(
            WantToReadBook.objects.filter(user=self.user, goodreads_id="789").exists()
        )

        read_entry = ReadBook.objects.get(user=self.user, goodreads_id="123")
        self.assertIsNotNone(read_entry.book)
        self.assertEqual(summary.matched_by_goodreads, 1)

    def test_import_read_overrides_want(self):
        WantToReadBook.objects.create(user=self.user, goodreads_id="999")

        csv_data = "Book Id,Title,Author,Exclusive Shelf\n999,Book X,Author X,read\n"
        summary = import_goodreads_csv(StringIO(csv_data), self.user)

        self.assertFalse(
            WantToReadBook.objects.filter(user=self.user, goodreads_id="999").exists()
        )
        self.assertTrue(
            ReadBook.objects.filter(user=self.user, goodreads_id="999").exists()
        )
        self.assertEqual(summary.removed_from_want, 1)

    def test_import_links_by_isbn_and_backfills_goodreads(self):
        book = Book.objects.create(
            name="ISBN Match",
            slug="isbn-match",
            rank=1,
            isbn13="9780306406157",
        )

        csv_data = (
            "Book Id,Title,Author,ISBN13,Exclusive Shelf\n"
            "555,ISBN Match,Author Z,978-0-306-40615-7,read\n"
        )

        summary = import_goodreads_csv(StringIO(csv_data), self.user)

        book.refresh_from_db()
        self.assertEqual(book.goodreads_id, "555")
        read_entry = ReadBook.objects.get(user=self.user, goodreads_id="555")
        self.assertEqual(read_entry.book_id, book.id)
        self.assertEqual(summary.matched_by_isbn, 1)
        self.assertEqual(summary.goodreads_id_backfilled, 1)

    def test_import_links_by_title_author(self):
        author = Author.objects.create(name="Jane Doe", slug="jane-doe")
        book = Book.objects.create(
            name="Title Match",
            slug="title-match",
            rank=1,
        )
        book.authors.add(author)

        csv_data = (
            "Book Id,Title,Author,Exclusive Shelf\n"
            "777,Title Match,Jane Doe,read\n"
        )

        summary = import_goodreads_csv(StringIO(csv_data), self.user)

        book.refresh_from_db()
        self.assertEqual(book.goodreads_id, "777")
        read_entry = ReadBook.objects.get(user=self.user, goodreads_id="777")
        self.assertEqual(read_entry.book_id, book.id)
        self.assertEqual(summary.matched_by_title_author, 1)
        self.assertEqual(summary.goodreads_id_backfilled, 1)

    def test_import_skips_conflicting_goodreads_id(self):
        Book.objects.create(
            name="Conflict Book",
            slug="conflict-book",
            rank=1,
            isbn="0306406152",
            goodreads_id="111",
        )

        csv_data = (
            "Book Id,Title,Author,ISBN,Exclusive Shelf\n"
            "999,Conflict Book,Author X,0-306-40615-2,read\n"
        )

        summary = import_goodreads_csv(StringIO(csv_data), self.user)

        self.assertEqual(summary.goodreads_id_conflicts, 1)
        read_entry = ReadBook.objects.get(user=self.user, goodreads_id="999")
        self.assertIsNone(read_entry.book)
