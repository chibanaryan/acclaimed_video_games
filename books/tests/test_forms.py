from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import ValidationError
from django.test import TestCase

from books.forms import GoodreadsImportForm, _normalize_header


class GoodreadsImportFormTests(TestCase):
    def test_normalize_header(self):
        self.assertEqual(_normalize_header(" Book-Id_Value "), "book id value")

    def test_clean_file_returns_none_when_missing(self):
        form = GoodreadsImportForm()
        form.cleaned_data = {}
        self.assertIsNone(form.clean_file())

    def test_clean_file_accepts_valid_csv(self):
        upload = SimpleUploadedFile(
            "goodreads.csv",
            b"Book Id,Title\n1,Test\n",
            content_type="text/csv",
        )
        form = GoodreadsImportForm(data={}, files={"file": upload})
        self.assertTrue(form.is_valid(), form.errors)
        cleaned = form.cleaned_data["file"]
        self.assertEqual(cleaned.tell(), 0)

    def test_clean_file_rejects_empty_file(self):
        upload = SimpleUploadedFile("goodreads.csv", b"\n", content_type="text/csv")
        form = GoodreadsImportForm(data={}, files={"file": upload})
        self.assertFalse(form.is_valid())
        self.assertIn("File is empty.", form.errors["file"][0])

    def test_clean_file_rejects_missing_book_id_column(self):
        upload = SimpleUploadedFile(
            "goodreads.csv",
            b"Title,Author\nBook,Author\n",
            content_type="text/csv",
        )
        form = GoodreadsImportForm(data={}, files={"file": upload})
        self.assertFalse(form.is_valid())
        self.assertIn("Missing required 'Book Id' column.", form.errors["file"][0])

    def test_clean_file_wraps_unexpected_read_error(self):
        upload = SimpleUploadedFile(
            "goodreads.csv",
            b"Book Id,Title\n1,Test\n",
            content_type="text/csv",
        )
        form = GoodreadsImportForm()
        form.cleaned_data = {"file": upload}
        with mock.patch("books.forms.csv.reader", side_effect=Exception("boom")):
            with self.assertRaisesMessage(ValidationError, "Could not read file: boom"):
                form.clean_file()

    def test_clean_file_ignores_detach_errors(self):
        upload = SimpleUploadedFile(
            "goodreads.csv",
            b"Book Id,Title\n1,Test\n",
            content_type="text/csv",
        )
        wrapper = mock.MagicMock()
        wrapper.detach.side_effect = RuntimeError("detach failed")
        form = GoodreadsImportForm()
        form.cleaned_data = {"file": upload}
        with mock.patch("books.forms.TextIOWrapper", return_value=wrapper):
            with mock.patch("books.forms.csv.reader", return_value=iter([["Book Id"]])):
                cleaned = form.clean_file()
        self.assertIs(cleaned, upload)
        self.assertEqual(cleaned.tell(), 0)
