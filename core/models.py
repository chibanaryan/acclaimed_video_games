"""
Abstract base models for the multi-media platform.

These models provide shared functionality for games, books, and future media types.
Each abstract model captures common patterns that can be extended by concrete models.
"""

import secrets
from functools import cached_property
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify
from unidecode import unidecode


class User(AbstractUser):
    """
    Custom user model consolidating UserProfile and Subscriber functionality.

    This model extends Django's AbstractUser to include:
    - Newsletter subscription fields (email_subscribed, unsubscribe_token, etc.)

    Email verification is handled by allauth's EmailAddress model.
    Check EmailAddress.verified to determine if a user's email is verified.

    Users can be:
    - Full accounts: Have a usable password, can log in
    - Subscriber-only: Created from newsletter signup with unusable password,
      can claim account later via password reset
    """

    # Newsletter subscription fields
    email_subscribed = models.BooleanField(default=False)
    unsubscribe_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, db_index=True
    )
    date_subscribed = models.DateTimeField(null=True, blank=True)

    class Meta:
        swappable = "AUTH_USER_MODEL"
        db_table = "games_user"  # Preserve existing table name

    @property
    def name(self) -> str:
        """Return username or email prefix for display purposes."""
        if self.username:
            return self.username
        if self.email:
            return self.email.split("@")[0]
        return "User"

    @property
    def email_verified(self) -> bool:
        """Check if user's email is verified via allauth EmailAddress."""
        from allauth.account.models import EmailAddress

        return EmailAddress.objects.filter(
            user=self, email__iexact=self.email, verified=True
        ).exists()

    def generate_unsubscribe_token(self) -> None:
        """Generate unsubscribe token for newsletter."""
        if not self.unsubscribe_token:
            self.unsubscribe_token = secrets.token_urlsafe(32)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Generate unsubscribe token if subscribing for first time."""
        if self.email_subscribed and not self.unsubscribe_token:
            self.generate_unsubscribe_token()
        super().save(*args, **kwargs)


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


class PublicationBase(models.Model):
    """
    Abstract base model for publications (magazines, websites, etc.) that publish lists.

    Publications aggregate lists from a single source like IGN, GameSpot, NYT, etc.
    Each media app has its own concrete Publication model for independence.

    Concrete models may add:
    - Media-specific external ID fields
    - Additional metadata fields (e.g., website URL, description)
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, db_index=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the publication, ensuring slug is populated."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ListBase(models.Model):
    """
    Abstract base model for ranking lists.

    Lists represent collections of ranked media items from a publication.
    Each list has a type (all-time, decade, end-of-year, misc) and year.

    Concrete models must add:
    - publisher: ForeignKey to the concrete Publication model
    - Any media-specific fields

    Note: The 'publisher' FK is not defined here because abstract models
    cannot reference other abstract models. Each concrete class must define
    its own publisher FK pointing to its concrete Publication model.
    """

    # Import at class level because choices/default are evaluated at class definition time
    from core import constants as core_constants

    name = models.CharField(max_length=100)
    url = models.URLField(null=True, blank=True)
    year = models.PositiveSmallIntegerField(db_index=True)
    type = models.CharField(
        max_length=1,
        choices=core_constants.LIST_TYPES,
        default=core_constants.LIST_EOY,
        db_index=True,
    )
    order = models.PositiveIntegerField(unique=True, null=True)

    class Meta:
        abstract = True
        ordering = ["order", "type", "year", "name"]

    def __str__(self) -> str:
        return self.name

    def get_type_label(self) -> str:
        """Get human-readable label for this list's type."""
        from core import constants as core_constants

        return core_constants.get_list_type_label(self.type)


class ListMembershipBase(models.Model):
    """
    Abstract base model for list membership (item position in a list).

    Tracks which media items appear in which lists and their rank.

    Concrete models must add:
    - list: ForeignKey to the concrete List model
    - Media item FK (game, book, etc.)
    """

    rank = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Position in the list (lower is better)",
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"Rank {self.rank}"
