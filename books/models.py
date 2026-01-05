"""
Books app models.

This file contains stub models that define the minimum structure needed
for the API to work. These will be replaced with full implementations
in Phase 4.2 that inherit from core abstract base models.

TODO (Phase 4.2): Replace with full model implementations that inherit from:
- Book: MediaItemBase
- Author: CreatorBase
- GoodreadsBookData, WikipediaBookData: ExternalDataBase
- ReadBook, WantToReadBook: UserTrackingBase
"""

from functools import cached_property

from django.conf import settings
from django.db import models


class BookGenre(models.Model):
    """
    Book genre with hierarchical structure.

    Similar to games' WikipediaGenre.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    level = models.PositiveSmallIntegerField(default=0)
    display_order = models.PositiveSmallIntegerField(default=0)
    path = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    icon_name = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["level", "display_order", "name"]
        verbose_name = "Book Genre"
        verbose_name_plural = "Book Genres"

    def __str__(self):
        return self.path if self.path else self.name

    def get_descendant_ids(self, include_self=False):
        """Get IDs of all descendant genres."""
        ids = []
        if include_self:
            ids.append(self.id)
        for child in self.children.all():
            ids.append(child.id)
            ids.extend(child.get_descendant_ids(include_self=False))
        return ids


class Author(models.Model):
    """
    Book author.

    TODO (Phase 4.2): Inherit from CreatorBase for hierarchy support.
    """

    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=210, null=True, blank=True, db_index=True)
    goodreads_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="GoodReads author ID",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class GoodreadsBookData(models.Model):
    """
    Supplemental GoodReads book data.

    Similar to games' IGDBGameData.
    """

    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        related_name="goodreads_book_data_set",
        null=True,
        blank=True,
    )
    goodreads_id = models.CharField(max_length=50, db_index=True)
    cover_image_url = models.URLField(max_length=500, null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_primary = models.BooleanField(default=False, db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GoodReads Book Data"
        verbose_name_plural = "GoodReads Book Data"

    def __str__(self):
        if self.book:
            return f"GoodReads data for {self.book.name}"
        return f"Orphaned GoodReads data (ID: {self.goodreads_id})"


class WikipediaBookData(models.Model):
    """
    Supplemental Wikipedia book data.

    Similar to games' WikipediaGameData.
    """

    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        related_name="wikipedia_book_data_set",
        null=True,
        blank=True,
    )
    wikidata_id = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    page_title = models.CharField(max_length=300, db_index=True)
    primary_genre = models.CharField(max_length=200, null=True, blank=True)
    all_genres = models.TextField(null=True, blank=True)
    is_primary = models.BooleanField(default=False, db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wikipedia Book Data"
        verbose_name_plural = "Wikipedia Book Data"

    def __str__(self):
        if self.book:
            return f"Wikipedia data for {self.book.name}"
        return f"Orphaned Wikipedia data (Wikidata: {self.wikidata_id or 'unknown'})"


class BookQuerySet(models.QuerySet):
    """Custom QuerySet for Book model with common prefetch patterns."""

    def with_relations(self):
        """Prefetch common relations for book lists and search results."""
        return self.prefetch_related(
            "authors",
            "genres",
        ).select_related(
            "primary_goodreads_book_data",
            "primary_wikipedia_book_data",
        )

    def with_list_count(self):
        """Annotate books with count of list appearances."""
        from django.db.models import Count

        return self.annotate(list_count=Count("lists", distinct=True))


class Book(models.Model):
    """
    A book.

    TODO (Phase 4.2): Inherit from MediaItemBase.
    """

    name = models.CharField(max_length=200, db_index=True)
    name_normalized = models.CharField(
        max_length=200, null=True, blank=True, db_index=True
    )
    slug = models.SlugField(max_length=210, null=True, blank=True, db_index=True)
    description = models.TextField(null=True, blank=True)
    rank = models.IntegerField(db_index=True)
    year_published = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    year_rank = models.IntegerField(null=True, blank=True, db_index=True)
    decade_rank = models.IntegerField(null=True, blank=True, db_index=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    goodreads_id = models.CharField(
        max_length=50, null=True, blank=True, db_index=True
    )
    wikidata_id = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    authors = models.ManyToManyField("Author", blank=True, related_name="books")
    genres = models.ManyToManyField("BookGenre", blank=True, related_name="books")

    # Fast access to primary records
    primary_goodreads_book_data = models.OneToOneField(
        "GoodreadsBookData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_book",
    )
    primary_wikipedia_book_data = models.OneToOneField(
        "WikipediaBookData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_book",
    )

    created = models.DateTimeField(auto_now_add=True, db_index=True, null=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    objects = BookQuerySet.as_manager()

    class Meta:
        ordering = ["rank"]

    def __str__(self):
        return self.name

    @cached_property
    def cover_image_url(self):
        """Get cover image URL from primary GoodReads data."""
        if self.primary_goodreads_book_data:
            return self.primary_goodreads_book_data.cover_image_url
        return None


class BookList(models.Model):
    """
    A book list/ranking published by a critic or publication.

    Similar to games' List model.
    """

    publisher = models.ForeignKey(
        "games.Publication",
        null=True,
        blank=True,
        related_name="book_lists",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    url = models.URLField(null=True, blank=True)
    year = models.PositiveSmallIntegerField(db_index=True)
    type = models.CharField(max_length=1, default="E", db_index=True)
    order = models.PositiveIntegerField(unique=True, null=True)

    class Meta:
        ordering = ["order", "type", "publisher", "year", "name"]

    def __str__(self):
        return self.name


class BookListMembership(models.Model):
    """A book's appearance in a list."""

    list = models.ForeignKey("BookList", on_delete=models.CASCADE)
    book = models.ForeignKey("Book", on_delete=models.CASCADE, related_name="lists")
    rank = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["list", "rank"]),
            models.Index(fields=["book", "list"]),
        ]

    def __str__(self):
        return f"{self.list} - {self.book} - {self.rank}"


class ReadBook(models.Model):
    """
    Tracks books a user has marked as read.

    Similar to games' PlayedGame.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="read_books",
    )
    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="read_by",
    )
    goodreads_id = models.CharField(max_length=50, db_index=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "goodreads_id")]

    def __str__(self):
        book_name = self.book.name if self.book else f"GoodReads:{self.goodreads_id}"
        return f"{self.user.username} read {book_name}"


class WantToReadBook(models.Model):
    """
    Tracks books a user wants to read.

    Similar to games' WantToPlayGame.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="want_to_read_books",
    )
    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="want_to_read_by",
    )
    goodreads_id = models.CharField(max_length=50, db_index=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "goodreads_id")]
        verbose_name = "Want to Read Book"
        verbose_name_plural = "Want to Read Books"

    def __str__(self):
        book_name = self.book.name if self.book else f"GoodReads:{self.goodreads_id}"
        return f"{self.user.username} wants to read {book_name}"
