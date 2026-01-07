"""
Book models for the multi-media platform.

This module contains all models related to book tracking and ranking,
following the same patterns established in the games app.
"""

from functools import cached_property
from typing import Optional

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from core.models import (
    CreatorBase,
    ExternalDataBase,
    ListBase,
    ListMembershipBase,
    MediaItemBase,
    PublicationBase,
    UserTrackingBase,
)


class Author(CreatorBase):
    """
    A book author with optional parent hierarchy.

    Supports hierarchical relationships for authors who write under
    different names or for author collectives/partnerships.

    Structure:
    - Root authors (parent=None): Primary author entries with slugs for URLs
    - Subsidiary authors (parent=Author): Pen names, pseudonyms, or co-authors

    Books are linked to Author records via Book.authors M2M.
    """

    goodreads_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Goodreads author ID",
    )
    goodreads_url = models.URLField(
        null=True,
        blank=True,
        help_text="Goodreads author profile URL",
    )
    open_library_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Open Library author ID (e.g., 'OL123456A')",
    )
    birth_date = models.DateField(
        null=True,
        blank=True,
        help_text="Author's birth date",
    )
    death_date = models.DateField(
        null=True,
        blank=True,
        help_text="Author's death date (null if living)",
    )
    bio = models.TextField(
        null=True,
        blank=True,
        help_text="Author biography",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Authors"
        indexes = [
            models.Index(fields=["goodreads_id"]),
            models.Index(fields=["open_library_id"]),
        ]

    def __str__(self) -> str:
        if self.parent:
            return f"{self.name} ({self.parent.name})"
        return self.name


class BookGenre(models.Model):
    """
    A book genre with hierarchical structure.

    Supports multi-level hierarchy with parent-child relationships:
    - Level 0: Root categories (e.g., "Fiction", "Non-Fiction")
    - Level 1+: Child genres (e.g., "Science Fiction" under "Fiction")

    The hierarchy enables:
    - Tree-based filtering in UI
    - Multi-level selection (select parent = select all children)
    - Organized genre navigation
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(
        max_length=110,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="URL-friendly identifier",
    )

    # Hierarchy fields
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        db_index=True,
        help_text="Parent genre (NULL for root categories)",
    )
    level = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        help_text="Hierarchy depth: 0=root, 1=category, 2+=subgenre",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        help_text="Manual ordering within parent category",
    )

    # Denormalized path for efficient queries and display
    path = models.CharField(
        max_length=300,
        blank=True,
        db_index=True,
        help_text="Full hierarchy path (e.g., 'Fiction > Science Fiction > Space Opera')",
    )

    # Optional metadata
    description = models.TextField(
        blank=True,
        help_text="Optional description of the genre",
    )
    icon_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon identifier for UI (e.g., 'genre-fiction')",
    )

    class Meta:
        ordering = ["level", "display_order", "name"]
        verbose_name = "Book Genre"
        verbose_name_plural = "Book Genres"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["parent", "level"]),
            models.Index(fields=["level", "display_order"]),
        ]

    def __str__(self) -> str:
        return self.path if self.path else self.name

    def save(self, *args, **kwargs):
        # Auto-generate slug from name if not set
        if not self.slug:
            self.slug = slugify(self.name)

        # Calculate level from parent chain
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0

        # Build hierarchical path
        if self.parent:
            self.path = f"{self.parent.path} > {self.name}"
        else:
            self.path = self.name

        super().save(*args, **kwargs)

    def get_descendants(self, include_self=False):
        """Get all descendant genres recursively."""
        descendants = []
        if include_self:
            descendants.append(self)

        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants(include_self=False))

        return descendants

    def get_descendant_ids(self, include_self=False):
        """Get IDs of all descendant genres (optimized for filtering)."""
        ids = []
        if include_self:
            ids.append(self.id)

        for child in self.children.all():
            ids.append(child.id)
            ids.extend(child.get_descendant_ids(include_self=False))

        return ids

    @property
    def is_root(self):
        """Check if this is a root category (no parent)."""
        return self.parent is None

    @property
    def is_leaf(self):
        """Check if this is a leaf genre (no children)."""
        return not self.children.exists()


class BookSeries(models.Model):
    """
    A book series (e.g., 'Harry Potter', 'A Song of Ice and Fire').

    Books can belong to a series with a position number indicating
    their order in the series.
    """

    name = models.CharField(max_length=200, unique=True, db_index=True)
    slug = models.SlugField(max_length=210, unique=True, db_index=True)
    goodreads_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Goodreads series ID",
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Series description",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Book Series"
        verbose_name_plural = "Book Series"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class GoodreadsBookData(ExternalDataBase):
    """
    Supplemental Goodreads book data.

    Multiple records per book supported (e.g., different editions).
    One record marked as primary for default display.

    Metadata persists when books are deleted (SET_NULL) to allow reconnection
    when books are re-imported.
    """

    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        related_name="goodreads_book_data_set",
        null=True,
        blank=True,
    )
    goodreads_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Goodreads book ID for this specific edition/entry",
    )
    goodreads_url = models.URLField(
        null=True,
        blank=True,
        help_text="Goodreads book detail page URL",
    )
    cover_image_url = models.URLField(
        null=True,
        blank=True,
        help_text="Cover image URL from Goodreads",
    )
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average rating on Goodreads (0.00-5.00)",
    )
    ratings_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of ratings on Goodreads",
    )
    reviews_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of text reviews on Goodreads",
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Book description from Goodreads",
    )

    class Meta:
        db_table = "books_goodreadsbookdata"
        verbose_name = "Goodreads Book Data"
        verbose_name_plural = "Goodreads Book Data"
        indexes = [
            models.Index(fields=["book", "is_primary"]),
            models.Index(fields=["goodreads_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["book"],
                condition=models.Q(is_primary=True) & models.Q(book__isnull=False),
                name="unique_primary_goodreads_per_book",
            )
        ]

    def __str__(self) -> str:
        if self.book:
            return f"Goodreads data for {self.book.name} (ID: {self.goodreads_id})"
        return f"Orphaned Goodreads data (ID: {self.goodreads_id})"

    @cached_property
    def thumbnail(self) -> Optional[str]:
        """Get thumbnail URL for cover art."""
        return self.cover_image_url

    @property
    def goodreads_book_url(self) -> Optional[str]:
        """Generate Goodreads book URL."""
        if self.goodreads_id:
            return f"https://www.goodreads.com/book/show/{self.goodreads_id}"
        return self.goodreads_url


class WikipediaBookData(ExternalDataBase):
    """
    Supplemental Wikipedia/Wikidata book data.

    Multiple records per book supported (e.g., different language editions).
    One record marked as primary for default display.

    Metadata persists when books are deleted (SET_NULL) to allow reconnection
    when books are re-imported.
    """

    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        related_name="wikipedia_book_data_set",
        null=True,
        blank=True,
    )
    wikidata_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Wikidata entity ID (e.g., 'Q12345')",
    )
    page_title = models.CharField(
        max_length=300,
        db_index=True,
        help_text="Wikipedia page title",
    )
    primary_genre = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )
    all_genres = models.TextField(
        null=True,
        blank=True,
    )
    lookup_source = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "books_wikipediabookdata"
        verbose_name = "Wikipedia Book Data"
        verbose_name_plural = "Wikipedia Book Data"
        indexes = [
            models.Index(fields=["book", "is_primary"]),
            models.Index(fields=["wikidata_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["book"],
                condition=models.Q(is_primary=True) & models.Q(book__isnull=False),
                name="unique_primary_wikipedia_per_book",
            )
        ]

    def __str__(self) -> str:
        if self.book:
            return f"Wikipedia data for {self.book.name}"
        return f"Orphaned Wikipedia data (Wikidata: {self.wikidata_id or 'unknown'})"

    @property
    def wikipedia_url(self) -> Optional[str]:
        """Generate Wikipedia article URL from page title."""
        if self.page_title:
            return f"https://en.wikipedia.org/wiki/{self.page_title.replace(' ', '_')}"
        return None


class BookQuerySet(models.QuerySet):
    """Custom QuerySet for Book model with common prefetch patterns."""

    def with_relations(self):
        """Prefetch common relations for book lists and search results."""
        return self.prefetch_related(
            "authors",
            "authors__parent",
            "genres",
        ).select_related(
            "series",
            "primary_goodreads_book_data",
            "primary_wikipedia_book_data",
        )

    def with_read_status(self, user):
        """Annotate books with read and want-to-read status for the given user."""
        if not user or not user.is_authenticated:
            return self
        from django.db.models import Exists, OuterRef

        return self.annotate(
            is_read_by_user=Exists(
                ReadBook.objects.filter(user=user, book=OuterRef("pk"))
            ),
            is_want_to_read_by_user=Exists(
                WantToReadBook.objects.filter(user=user, book=OuterRef("pk"))
            ),
        )

    def with_list_count(self):
        """Annotate books with count of list appearances."""
        from django.db.models import Count

        return self.annotate(list_count=Count("lists", distinct=True))


class Book(MediaItemBase):
    """
    A book in the ranking system.

    Inherits common fields from MediaItemBase:
    - name, name_normalized, slug, description
    - rank, year_rank, decade_rank
    - wikidata_id, created, modified

    Adds book-specific fields for publishing details, ISBN,
    author relationships, and external data source links.
    """

    year_published = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Year the book was first published",
    )
    page_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of pages in the book",
    )
    isbn = models.CharField(
        max_length=13,
        null=True,
        blank=True,
        db_index=True,
        help_text="ISBN-10 identifier",
    )
    isbn13 = models.CharField(
        max_length=17,
        null=True,
        blank=True,
        db_index=True,
        help_text="ISBN-13 identifier",
    )
    goodreads_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Primary Goodreads book ID",
    )
    open_library_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Open Library work ID (e.g., 'OL123456W')",
    )

    # Relationships
    authors = models.ManyToManyField(
        "Author",
        blank=True,
        related_name="books",
        help_text="Book authors",
    )
    genres = models.ManyToManyField(
        "BookGenre",
        blank=True,
        related_name="books",
        help_text="Book genres",
    )
    series = models.ForeignKey(
        "BookSeries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="books",
        help_text="Book series this book belongs to",
    )
    series_position = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Position in the series (e.g., 1, 2, 2.5 for novellas)",
    )

    # Fast access to primary records (OneToOne for performance)
    primary_goodreads_book_data = models.OneToOneField(
        "GoodreadsBookData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_book",
        help_text="Primary Goodreads book data for display",
    )
    primary_wikipedia_book_data = models.OneToOneField(
        "WikipediaBookData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_book",
        help_text="Primary Wikipedia book data for display",
    )

    objects = BookQuerySet.as_manager()

    class Meta:
        ordering = ["rank"]
        indexes = [
            models.Index(fields=["year_published", "rank"]),
            models.Index(fields=["goodreads_id"]),
            models.Index(fields=["isbn"]),
            models.Index(fields=["isbn13"]),
        ]

    def __str__(self) -> str:
        return self.name

    @cached_property
    def decade(self) -> Optional[int]:
        """Get the decade the book was published."""
        if self.year_published:
            return (self.year_published // 10) * 10
        return None

    @cached_property
    def thumbnail(self) -> Optional[str]:
        """Get thumbnail URL from primary Goodreads data."""
        if self.primary_goodreads_book_data:
            return self.primary_goodreads_book_data.cover_image_url
        return None

    @cached_property
    def image(self) -> Optional[str]:
        """Get full-size image URL from primary Goodreads data."""
        if self.primary_goodreads_book_data:
            return self.primary_goodreads_book_data.cover_image_url
        return None

    def get_display_authors(self, max_count: int = None) -> list:
        """
        Get authors for display, filtering out redundant ancestors.

        Args:
            max_count: Maximum number of authors to return (None = no limit)

        Returns:
            List of Author objects, filtered and optionally limited
        """
        authors_list = list(self.authors.all())

        if len(authors_list) <= 1:
            return authors_list

        # Build set of all ancestor IDs across all authors
        ancestor_ids = set()
        for author in authors_list:
            current = author.parent
            visited = set()
            while current and current.id not in visited:
                ancestor_ids.add(current.id)
                visited.add(current.id)
                current = current.parent

        # Filter out any author that is an ancestor of another
        filtered = [a for a in authors_list if a.id not in ancestor_ids]

        if max_count is not None:
            return filtered[:max_count]
        return filtered


class BookPublication(PublicationBase):
    """
    A magazine, website, or organization that publishes book lists.

    Examples: New York Times, Goodreads, Library Journal, Modern Library

    Inherits from PublicationBase which provides:
    - name (CharField, unique)
    - slug (SlugField with auto-generation)
    - __str__, save methods
    """

    class Meta:
        db_table = "books_bookpublication"
        ordering = ["name"]
        verbose_name = "Book Publication"
        verbose_name_plural = "Book Publications"


class BookList(ListBase):
    """
    A book list published by a publication.

    Examples: "NYT Best Books of 2024", "Modern Library 100 Best Novels"

    Inherits from ListBase which provides:
    - name, url, year, type, order fields
    - __str__, get_type_label methods
    """

    # null=True allows importing lists before their publication is created,
    # or for lists from unknown/anonymous sources during data migration.
    publisher = models.ForeignKey(
        "BookPublication",
        null=True,
        blank=True,
        related_name="lists",
        on_delete=models.CASCADE,
    )

    class Meta:
        db_table = "books_booklist"
        ordering = ["order", "type", "publisher", "year", "name"]
        # Note: unique_together with nullable publisher allows multiple lists
        # with same name/year when publisher is NULL (NULLs are distinct in SQL).
        # This is acceptable for orphan lists during data import.
        unique_together = ["publisher", "name", "year"]
        indexes = [
            models.Index(fields=["type", "year"]),
        ]
        verbose_name = "Book List"
        verbose_name_plural = "Book Lists"


class BookListMembership(ListMembershipBase):
    """
    A book's appearance in a list.

    Inherits from ListMembershipBase which provides:
    - rank field

    References books.BookList for complete independence from games app.
    """

    list = models.ForeignKey(
        "BookList",
        on_delete=models.CASCADE,
        help_text="The list this book appears on",
    )
    book = models.ForeignKey(
        "Book",
        on_delete=models.CASCADE,
        related_name="lists",
        help_text="The book appearing in the list",
    )

    class Meta:
        db_table = "books_booklistmembership"
        indexes = [
            models.Index(fields=["list", "rank"]),
            models.Index(fields=["book", "list"]),
        ]
        unique_together = [("list", "book")]
        verbose_name = "Book List Membership"
        verbose_name_plural = "Book List Memberships"

    def __str__(self) -> str:
        return f"{self.list} - {self.book} - {self.rank}"


class ReadBook(UserTrackingBase):
    """
    Tracks books a user has marked as read.

    Uses hybrid FK + goodreads_id approach:
    - FK to Book for fast queries and joins
    - goodreads_id stored for reconnection after book re-imports
    """

    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="read_by",
    )
    goodreads_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Goodreads book ID for reconnection after reimport",
    )

    class Meta:
        db_table = "books_readbook"
        unique_together = [("user", "goodreads_id")]
        indexes = [models.Index(fields=["user", "book"])]

    def __str__(self):
        book_name = self.book.name if self.book else f"Goodreads:{self.goodreads_id}"
        return f"{self.user.username} read {book_name}"


class WantToReadBook(UserTrackingBase):
    """
    Tracks books a user wants to read (reading list/backlog).

    Uses hybrid FK + goodreads_id approach:
    - FK to Book for fast queries and joins
    - goodreads_id stored for reconnection after book re-imports

    Mutually exclusive with ReadBook - a book cannot be both
    "want to read" and "read" simultaneously.
    """

    book = models.ForeignKey(
        "Book",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="want_to_read_by",
    )
    goodreads_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Goodreads book ID for reconnection after reimport",
    )

    class Meta:
        db_table = "books_wanttoreadbook"
        unique_together = [("user", "goodreads_id")]
        indexes = [models.Index(fields=["user", "book"])]
        verbose_name = "Want to Read Book"
        verbose_name_plural = "Want to Read Books"

    def __str__(self):
        book_name = self.book.name if self.book else f"Goodreads:{self.goodreads_id}"
        return f"{self.user.username} wants to read {book_name}"
