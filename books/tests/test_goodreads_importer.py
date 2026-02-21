"""Tests for Goodreads CSV importer."""

from io import BytesIO, StringIO, TextIOBase
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from books.models import Author, Book, ReadBook, WantToReadBook
from books.services.goodreads_importer import (
    GoodreadsImportSummary,
    _build_isbn_map,
    _determine_status,
    _normalize_text,
    _open_text_file,
    _split_shelves,
    import_goodreads_csv,
    match_goodreads_records,
    parse_goodreads_records,
)


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
            "Book Id,Title,Author,Exclusive Shelf\n" "777,Title Match,Jane Doe,read\n"
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

    def test_normalize_text_handles_empty_value(self):
        self.assertEqual(_normalize_text(""), "")

    def test_open_text_file_wraps_binary_input(self):
        raw = BytesIO(b"Book Id,Title\n1,Book\n")
        handle, should_detach = _open_text_file(raw)
        self.assertTrue(should_detach)
        self.assertIsInstance(handle, TextIOBase)
        handle.detach()

    def test_split_shelves_and_determine_status_none(self):
        shelves = _split_shelves("to-read (1), currently-reading, ,read")
        self.assertEqual(shelves, ("to-read", "currently-reading", "read"))

        row = {
            "Bookshelves": "favorites",
            "Bookshelves with positions": "",
            "Exclusive Shelf": "",
            "Date Read": "",
        }
        header_map = {
            "bookshelves": "Bookshelves",
            "bookshelves with positions": "Bookshelves with positions",
            "exclusive shelf": "Exclusive Shelf",
            "date read": "Date Read",
        }
        self.assertIsNone(_determine_status(row, header_map))

    def test_build_isbn_map_marks_conflicts_ambiguous(self):
        b1 = Book.objects.create(name="A", slug="a", rank=1, isbn="0306406152")
        b2 = Book.objects.create(name="B", slug="b", rank=2, isbn="0306406152")
        b3 = Book.objects.create(name="C", slug="c", rank=3, isbn="0306406152")
        isbn_map, ambiguous = _build_isbn_map(
            {"0306406152"},
            Book.objects.filter(id__in=[b1.id, b2.id, b3.id]).order_by("id"),
        )
        self.assertEqual(isbn_map, {})
        self.assertIn("0306406152", ambiguous)

    def test_parse_records_defaults_summary_and_merges_duplicate_fields(self):
        csv_data = (
            "Book Id,Title,Author,Exclusive Shelf\n"
            "1,,,to-read\n"
            "1,Recovered Title,Recovered Author,read\n"
        )
        records, summary = parse_goodreads_records(StringIO(csv_data))
        self.assertEqual(summary.duplicate_rows, 1)
        self.assertEqual(records["1"]["status"], "read")
        self.assertEqual(records["1"]["title"], "Recovered Title")
        self.assertEqual(records["1"]["author"], "Recovered Author")

    def test_parse_records_missing_header_row_raises(self):
        with self.assertRaisesMessage(ValueError, "Missing header row in CSV."):
            parse_goodreads_records(StringIO(""))

    def test_parse_records_missing_book_id_column_raises(self):
        csv_data = "Title,Author,Exclusive Shelf\nBook,Author,read\n"
        with self.assertRaisesMessage(
            ValueError, "Missing required 'Book Id' column in CSV."
        ):
            parse_goodreads_records(StringIO(csv_data))

    def test_parse_records_skips_rows_without_status(self):
        csv_data = (
            "Book Id,Title,Author,Exclusive Shelf,"
            "Bookshelves,Bookshelves with positions\n"
            "123,No Status,Author,,,,\n"
        )
        records, summary = parse_goodreads_records(
            StringIO(csv_data), GoodreadsImportSummary()
        )
        self.assertEqual(records, {})
        self.assertEqual(summary.skipped_no_status, 1)

    def test_parse_records_ignores_detach_failure(self):
        class DetachFailingHandle(StringIO):
            def detach(self):
                raise RuntimeError("detach failed")

        fake_handle = DetachFailingHandle(
            "Book Id,Title,Author,Exclusive Shelf\n123,Book,Author,read\n"
        )
        with mock.patch(
            "books.services.goodreads_importer._open_text_file",
            return_value=(fake_handle, True),
        ):
            records, _ = parse_goodreads_records(StringIO("placeholder"))
        self.assertIn("123", records)

    def test_match_records_empty_defaults_summary(self):
        resolved, summary = match_goodreads_records({})
        self.assertEqual(resolved, {})
        self.assertIsInstance(summary, GoodreadsImportSummary)

    def test_match_records_counts_ambiguous_isbn13_and_isbn10(self):
        Book.objects.create(
            name="ISBN One",
            slug="isbn-one",
            rank=1,
            isbn="0306406152",
            isbn13="9780306406157",
        )
        Book.objects.create(
            name="ISBN Two",
            slug="isbn-two",
            rank=2,
            isbn="0306406152",
            isbn13="9780306406157",
        )
        records = {
            "999": {
                "status": "read",
                "title": "",
                "author": "",
                "isbn": "0306406152",
                "isbn13": "9780306406157",
                "title_key": "",
                "author_key": "",
            }
        }
        resolved, summary = match_goodreads_records(records, GoodreadsImportSummary())
        self.assertIsNone(resolved["999"])
        self.assertEqual(summary.isbn_ambiguous, 2)

    def test_match_records_counts_ambiguous_title_author(self):
        a1 = Author.objects.create(name="Same Name", slug="same-name-1")
        a2 = Author.objects.create(name="Same Name", slug="same-name-2")
        b1 = Book.objects.create(
            name="Ambiguous Title", slug="ambiguous-title-1", rank=1
        )
        b2 = Book.objects.create(
            name="Ambiguous Title", slug="ambiguous-title-2", rank=2
        )
        b1.authors.add(a1)
        b2.authors.add(a2)

        records = {
            "777": {
                "status": "read",
                "title": "Ambiguous Title",
                "author": "Same Name",
                "isbn": "",
                "isbn13": "",
                "title_key": "ambiguous title",
                "author_key": "same name",
            }
        }
        resolved, summary = match_goodreads_records(records, GoodreadsImportSummary())
        self.assertIsNone(resolved["777"])
        self.assertEqual(summary.title_author_ambiguous, 1)

    def test_import_counts_existing_read_want_and_read_override(self):
        ReadBook.objects.create(user=self.user, goodreads_id="100")
        WantToReadBook.objects.create(user=self.user, goodreads_id="200")
        ReadBook.objects.create(user=self.user, goodreads_id="300")

        csv_data = (
            "Book Id,Title,Author,Exclusive Shelf\n"
            "100,Read Existing,Author A,read\n"
            "200,Want Existing,Author B,to-read\n"
            "300,Read Overrides Want,Author C,to-read\n"
        )
        summary = import_goodreads_csv(StringIO(csv_data), self.user)
        self.assertEqual(summary.read_existing, 1)
        self.assertEqual(summary.want_existing, 1)
        self.assertEqual(summary.read_overrides_want, 1)
