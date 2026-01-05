"""
Abstract base models for the multi-media platform.

These models provide shared functionality for games, books, and future media types.
Each abstract model captures common patterns that can be extended by concrete models.
"""

from functools import cached_property

from django.conf import settings
from django.db import models
from unidecode import unidecode


class MediaItemBase(models.Model):
    """
    Abstract base model for media items (games, books, etc.).

    Provides common fields for ranking, identification, and timestamps.
    Concrete models should add:
    - Media-specific fields (year_of_release, year_published, etc.)
    - Media-specific relationships (developers, authors, etc.)
    - Media-specific external data FKs
    """

    name = models.CharField(max_length=200, db_index=True)
    name_normalized = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_index=True,
        help_text="ASCII-only version of name for search matching",
    )
    slug = models.SlugField(
        max_length=210,
        null=True,
        blank=True,
        db_index=True,
        help_text="URL-friendly identifier",
    )
    description = models.TextField(null=True, blank=True)
    rank = models.IntegerField(db_index=True)
    year_rank = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Rank within release year",
    )
    decade_rank = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Rank within release decade",
    )
    wikidata_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Wikidata entity ID (e.g., 'Q12345')",
    )
    created = models.DateTimeField(auto_now_add=True, db_index=True, null=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ["rank"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Save the media item, calculating normalized name."""
        # Save the normalized version of the name for search
        normalized = unidecode(self.name)
        if self.name != normalized:
            self.name_normalized = normalized
        super().save(*args, **kwargs)

    @cached_property
    def decade(self):
        """Get the decade of release. Override in concrete class."""
        raise NotImplementedError("Subclasses must implement decade property")


class CreatorBase(models.Model):
    """
    Abstract base model for creators (developers, authors, publishers, etc.).

    Supports hierarchical relationships via self-referential parent FK.
    Root creators have slugs for URLs; subsidiaries are accessed via parent.

    Concrete models should add:
    - External ID fields (igdb_id, goodreads_id, etc.)
    - External URL fields
    """

    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(
        max_length=210,
        null=True,
        blank=True,
        db_index=True,
        help_text="URL-friendly identifier (only for root creators)",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subsidiaries",
        help_text="Parent creator in the ownership hierarchy",
    )

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        if self.parent:
            return f"{self.name} ({self.parent.name})"
        return self.name

    @property
    def is_root(self) -> bool:
        """True if this is a root creator (no parent)."""
        return self.parent is None

    @property
    def is_subsidiary(self) -> bool:
        """True if this creator has a parent."""
        return self.parent is not None

    @cached_property
    def root_creator(self):
        """
        Returns the root (topmost) creator in the ownership hierarchy.

        Cached on the instance to avoid repeated DB queries.
        """
        if not self.parent:
            return self

        current = self
        visited = {current.id}  # Prevent infinite loops

        while current.parent:
            if current.parent_id in visited:
                break
            visited.add(current.parent_id)
            current = current.parent

        return current

    @property
    def display_root_creator(self):
        """
        Template-friendly accessor for root creator.

        Uses prefetched root if available (set by views using cached hierarchy),
        otherwise falls back to the cached_property root_creator.
        """
        if hasattr(self, "_prefetched_root"):
            return self._prefetched_root
        return self.root_creator

    def get_all_subsidiaries(self, include_self: bool = False) -> list:
        """Get all subsidiary creators recursively."""
        descendants = []
        if include_self:
            descendants.append(self)

        for sub in self.subsidiaries.all():
            descendants.append(sub)
            descendants.extend(sub.get_all_subsidiaries(include_self=False))

        return descendants

    def get_all_subsidiary_ids(self, include_self: bool = False) -> list:
        """Get IDs of all subsidiary creators (optimized for filtering)."""
        ids = []
        if include_self:
            ids.append(self.id)

        for sub in self.subsidiaries.all():
            ids.append(sub.id)
            ids.extend(sub.get_all_subsidiary_ids(include_self=False))

        return ids

    def save(self, *args, **kwargs):
        """Save the creator, clearing slug if it has a parent."""
        # Only root creators should have slugs
        if self.parent_id is not None:
            self.slug = ""
        super().save(*args, **kwargs)


class ExternalDataBase(models.Model):
    """
    Abstract base model for external metadata records.

    Provides common fields for tracking data from external sources
    (IGDB, Wikipedia, HLTB, GoodReads, etc.).

    Multiple records per media item supported (e.g., regional editions).
    One record marked as primary for default display.

    Concrete models should add:
    - FK to the specific media item (game, book, etc.)
    - External source-specific ID fields
    - Source-specific data fields
    """

    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Primary record for display (only one per media item)",
    )
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.__class__.__name__} (primary={self.is_primary})"


class UserTrackingBase(models.Model):
    """
    Abstract base model for user tracking records (played games, read books, etc.).

    Uses hybrid FK + external ID approach:
    - FK to media item for fast queries and joins
    - External ID stored for reconnection after re-imports

    Concrete models should add:
    - FK to the specific media item (game, book, etc.)
    - External ID field for the media item
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.user.username} tracked {self.__class__.__name__}"
