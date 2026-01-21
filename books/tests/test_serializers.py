"""
Tests for books app serializers.
"""

import unittest

from django.db.models import Count
from django.test import TestCase

from books import models
from books.api import serializers


class BookSummarySerializerTests(TestCase):
    """Tests for BookSummarySerializer computed fields."""

    @unittest.skip("GoodreadsBookData model removed")
    def test_primary_goodreads_fields_populated(self):
        book = models.Book.objects.create(
            name="Test Book",
            rank=1,
            slug="test-book",
            goodreads_id="123",
        )
        goodreads = models.GoodreadsBookData.objects.create(
            book=book,
            goodreads_id="123",
            goodreads_url="https://goodreads.example/book/123",
            cover_image_url="https://example.com/cover.jpg",
            description="Test description",
            is_primary=True,
        )
        book.primary_goodreads_book_data = goodreads
        book.save()

        data = serializers.BookSummarySerializer(book).data

        self.assertEqual(data["cover_image_url"], "https://example.com/cover.jpg")
        self.assertEqual(data["goodreads_url"], "https://goodreads.example/book/123")
        self.assertEqual(data["description"], "Test description")

    @unittest.skip("GoodreadsBookData model removed")
    def test_goodreads_url_falls_back_to_generated_url(self):
        book = models.Book.objects.create(
            name="Generated URL Book",
            rank=2,
            slug="generated-url-book",
            goodreads_id="456",
        )
        goodreads = models.GoodreadsBookData.objects.create(
            book=book,
            goodreads_id="456",
            goodreads_url=None,
            is_primary=True,
        )
        book.primary_goodreads_book_data = goodreads
        book.save()

        data = serializers.BookSummarySerializer(book).data

        self.assertEqual(
            data["goodreads_url"],
            "https://www.goodreads.com/book/show/456",
        )


class BookGenreTreeSerializerTests(TestCase):
    """Tests for BookGenreTreeSerializer helpers."""

    def test_book_count_uses_annotation(self):
        genre = models.BookGenre.objects.create(name="Fiction")
        book = models.Book.objects.create(name="Test Book", rank=1)
        book.genres.add(genre)

        annotated_genre = models.BookGenre.objects.annotate(
            book_count_annotated=Count("books")
        ).get(id=genre.id)

        data = serializers.BookGenreTreeSerializer(annotated_genre).data

        self.assertEqual(data["book_count"], 1)
