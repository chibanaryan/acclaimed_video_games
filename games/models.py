import logging
import secrets
from functools import cached_property
from typing import Any, Dict, Optional

import markdown
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import Truncator, slugify
from unidecode import unidecode

from . import constants, igdb

logger = logging.getLogger(__name__)


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


class PlayedGame(models.Model):
    """
    Tracks games a user has marked as played.

    Uses hybrid FK + igdb_id approach:
    - FK to Game for fast queries and joins
    - igdb_id stored for reconnection after game re-imports
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="played_games",
    )
    game = models.ForeignKey(
        "Game",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="played_by",
    )
    igdb_id = models.IntegerField(db_index=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "igdb_id")]
        indexes = [models.Index(fields=["user", "game"])]

    def __str__(self):
        game_name = self.game.name if self.game else f"IGDB:{self.igdb_id}"
        return f"{self.user.username} played {game_name}"


class WantToPlayGame(models.Model):
    """
    Tracks games a user wants to play (backlog/wishlist).

    Uses hybrid FK + igdb_id approach:
    - FK to Game for fast queries and joins
    - igdb_id stored for reconnection after game re-imports

    Mutually exclusive with PlayedGame - a game cannot be both
    "want to play" and "played" simultaneously.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="want_to_play_games",
    )
    game = models.ForeignKey(
        "Game",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="want_to_play_by",
    )
    igdb_id = models.IntegerField(db_index=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "igdb_id")]
        indexes = [models.Index(fields=["user", "game"])]
        verbose_name = "Want to Play Game"
        verbose_name_plural = "Want to Play Games"

    def __str__(self):
        game_name = self.game.name if self.game else f"IGDB:{self.igdb_id}"
        return f"{self.user.username} wants to play {game_name}"


class SavedFilterSet(models.Model):
    """
    Saved filter configuration for quick access.

    Stores filter state as JSON, allowing users to save and
    quickly restore complex filter combinations.
    Maximum 10 saved filters per user (enforced in API).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_filter_sets",
    )
    name = models.CharField(
        max_length=255, help_text="User-defined or auto-generated filter name"
    )
    filters = models.JSONField(
        help_text="Filter configuration: q, start, end, genres, platforms, etc."
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-modified"]
        indexes = [
            models.Index(fields=["user", "-modified"]),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.name}"


class Snippet(models.Model):
    """A reusable piece of text"""

    slug = models.SlugField(unique=True)
    text = models.TextField()

    def __str__(self) -> str:
        return self.slug

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the snippet, ensuring slug is properly slugified."""
        slugified_slug = slugify(self.slug)
        if self.slug != slugified_slug:
            self.slug = slugified_slug
        super().save(*args, **kwargs)


class SiteMetadata(models.Model):
    """Site-wide metadata stored as a singleton"""

    key = models.CharField(max_length=50, unique=True, default="default")
    last_full_update = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Site Metadata"
        verbose_name_plural = "Site Metadata"

    def __str__(self) -> str:
        return f"Site Metadata ({self.key})"

    @classmethod
    def get_instance(cls) -> "SiteMetadata":
        """Get or create the singleton instance."""
        instance, _ = cls.objects.get_or_create(key="default")
        return instance


class Platform(models.Model):
    """
    The platform a game available for
    """

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100, unique=True)
    year_start = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Year platform became active",
    )
    year_end = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Year platform discontinued (null = still active)",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Developer(models.Model):
    """
    A game development entity with optional parent hierarchy.

    In IGDB's data model, all developers are "company" records. This model
    represents both parent developers and subsidiary development teams using a
    self-referential parent FK.

    Structure:
    - Root developers (parent=None): Top-level entities with slugs for URLs
      Examples: Nintendo, Valve, FromSoftware
    - Subsidiary developers (parent=Developer): Child entities without slugs
      Examples: Nintendo EAD (parent=Nintendo), Respawn (parent=EA)

    Games are linked directly to Developer records via Game.developers M2M.
    The parent FK enables hierarchical organization on developer detail pages.
    """

    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=100, null=True, blank=True, db_index=True)
    igdb_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="IGDB developer ID (from companies endpoint)",
    )
    igdb_url = models.URLField(
        null=True,
        blank=True,
        help_text="IGDB company detail page URL",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subsidiaries",
        help_text="Parent developer in the ownership hierarchy",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Developers"

    def __str__(self) -> str:
        if self.parent:
            return f"{self.name} ({self.parent.name})"
        return self.name

    @property
    def is_root(self) -> bool:
        """True if this is a root developer (no parent)."""
        return self.parent is None

    @property
    def is_subsidiary(self) -> bool:
        """True if this developer has a parent."""
        return self.parent is not None

    @cached_property
    def root_developer(self) -> "Developer":
        """
        Returns the root (topmost) developer in the ownership hierarchy.

        For nested developers like BioWare Edmonton → BioWare → EA,
        this returns the ultimate parent (EA).

        Cached on the instance to avoid repeated DB queries when accessed
        multiple times on the same instance.
        """
        if not self.parent:
            return self

        current = self
        visited = {current.id}  # Prevent infinite loops

        while current.parent:
            if current.parent_id in visited:
                break  # Prevent infinite loops
            visited.add(current.parent_id)
            current = current.parent

        return current

    @property
    def display_root_developer(self) -> "Developer":
        """
        Template-friendly accessor for root developer.

        Uses prefetched root if available (set by views using cached hierarchy),
        otherwise falls back to the cached_property root_developer.
        """
        if hasattr(self, "_prefetched_root"):
            return self._prefetched_root
        return self.root_developer

    def get_all_subsidiaries(self, include_self: bool = False) -> list:
        """
        Get all subsidiary developers recursively.

        Args:
            include_self: If True, include this developer in results

        Returns:
            List of Developer objects (all descendants)
        """
        descendants = []
        if include_self:
            descendants.append(self)

        for sub in self.subsidiaries.all():
            descendants.append(sub)
            descendants.extend(sub.get_all_subsidiaries(include_self=False))

        return descendants

    def get_all_subsidiary_ids(self, include_self: bool = False) -> list:
        """
        Get IDs of all subsidiary developers (optimized for filtering).

        Args:
            include_self: If True, include this developer's ID

        Returns:
            List of developer IDs
        """
        ids = []
        if include_self:
            ids.append(self.id)

        for sub in self.subsidiaries.all():
            ids.append(sub.id)
            ids.extend(sub.get_all_subsidiary_ids(include_self=False))

        return ids

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the developer, clearing slug if it has a parent."""
        # Only root developers should have slugs - child developers are accessed
        # via their root parent's URL with hash anchors
        if self.parent_id is not None:
            self.slug = ""
        super().save(*args, **kwargs)


class IGDBGenre(models.Model):
    """A video game genre from IGDB"""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "games_igdbgenre"
        ordering = ["name"]
        verbose_name = "IGDB Genre"
        verbose_name_plural = "IGDB Genres"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return self.name


class WikipediaGenre(models.Model):
    """
    A video game genre from Wikipedia with hierarchical structure.

    Supports multi-level hierarchy with parent-child relationships:
    - Level 0: Root categories (e.g., "Action", "Adventure")
    - Level 1+: Child genres (e.g., "First-Person Shooter" under "Action")

    The hierarchy enables:
    - Tree-based filtering in UI
    - Multi-level selection (select parent = select all children)
    - Organized genre navigation
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(
        max_length=110,
        unique=True,
        null=True,  # Allow null initially for migration
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
        help_text="Full hierarchy path (e.g., 'Action > Shooter > FPS')",
    )

    # Optional metadata
    description = models.TextField(
        blank=True,
        help_text="Optional description of the genre",
    )
    icon_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon identifier for UI (e.g., 'genre-action')",
    )

    class Meta:
        ordering = ["level", "display_order", "name"]
        verbose_name = "Wikipedia Genre"
        verbose_name_plural = "Wikipedia Genres"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["parent", "level"]),
            models.Index(fields=["level", "display_order"]),
        ]

    def __str__(self) -> str:
        return self.path if self.path else self.name

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

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
        """
        Get all descendant genres recursively.

        Args:
            include_self: If True, include this genre in results

        Returns:
            List of WikipediaGenre objects (descendants)
        """
        descendants = []
        if include_self:
            descendants.append(self)

        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants(include_self=False))

        return descendants

    def get_descendant_ids(self, include_self=False):
        """
        Get IDs of all descendant genres (optimized for filtering).

        Args:
            include_self: If True, include this genre's ID

        Returns:
            List of genre IDs
        """
        ids = []
        if include_self:
            ids.append(self.id)

        for child in self.children.all():
            ids.append(child.id)
            ids.extend(child.get_descendant_ids(include_self=False))

        return ids

    def get_ancestors(self, include_self=False):
        """
        Get all ancestor genres up to root.

        Args:
            include_self: If True, include this genre in results

        Returns:
            List of WikipediaGenre objects (ancestors, root first)
        """
        ancestors = []
        current = self.parent

        while current:
            ancestors.insert(0, current)
            current = current.parent

        if include_self:
            ancestors.append(self)

        return ancestors

    @property
    def is_root(self):
        """Check if this is a root category (no parent)."""
        return self.parent is None

    @property
    def is_leaf(self):
        """Check if this is a leaf genre (no children)."""
        return not self.children.exists()


class WikipediaCountry(models.Model):
    """
    A country of origin for video games from Wikidata P495.
    Simple model for filtering games by country of development.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, db_index=True)
    wikidata_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Wikidata Q-ID (e.g., 'Q17' for Japan)",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Wikipedia Country"
        verbose_name_plural = "Wikipedia Countries"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class WikipediaGameMode(models.Model):
    """
    A game mode from Wikidata P404 (single-player, multiplayer, etc.).
    Simple model for filtering games by game mode.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, db_index=True)
    wikidata_id = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        help_text="Wikidata Q-ID (e.g., 'Q208850' for Single-player)",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Wikipedia Game Mode"
        verbose_name_plural = "Wikipedia Game Modes"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Series(models.Model):
    """
    A video game series from IGDB (called 'Collection' in IGDB API).
    Examples: 'Mario Kart', 'Paper Mario', 'Final Fantasy VII'

    Games can belong to multiple series (e.g., 'Super Smash Bros Ultimate'
    belongs to 'Super Smash Bros', 'Mario', 'Zelda', etc.).
    """

    name = models.CharField(max_length=200, unique=True, db_index=True)
    slug = models.SlugField(max_length=210, unique=True, db_index=True)
    igdb_id = models.IntegerField(unique=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Series"

    def __str__(self):
        return self.name


class IGDBGameData(models.Model):
    """
    Supplemental IGDB game data.
    Multiple records per game supported (e.g., Pokémon Red/Blue/Yellow).
    One record marked as primary for default display.

    Metadata persists when games are deleted (SET_NULL) to allow reconnection
    when games are re-imported.
    """

    game = models.ForeignKey(
        "Game",
        on_delete=models.SET_NULL,
        related_name="igdb_game_data_set",
        null=True,
        blank=True,
    )
    igdb_id = models.IntegerField(
        db_index=True, help_text="IGDB game ID for this specific version/entry"
    )
    artwork_id = models.CharField(
        max_length=100, db_index=True, help_text="IGDB cover art hash (e.g., 'co1234')"
    )
    url = models.URLField(help_text="IGDB game detail page URL")
    description = models.TextField(null=True, blank=True)
    youtube_video_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="YouTube video ID from IGDB (first video)",
    )
    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Primary IGDB record for display (only one per game)",
    )
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "games_igdbgamedata"
        verbose_name = "IGDB Game Data"
        verbose_name_plural = "IGDB Game Data"
        indexes = [
            models.Index(fields=["game", "is_primary"]),
            models.Index(fields=["igdb_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["game"],
                condition=models.Q(is_primary=True) & models.Q(game__isnull=False),
                name="unique_primary_igdb_per_game",
            )
        ]

    def __str__(self) -> str:
        if self.game:
            return f"IGDB data for {self.game.name} (ID: {self.igdb_id})"
        return f"Orphaned IGDB data (ID: {self.igdb_id})"

    @cached_property
    def thumbnail(self) -> Optional[str]:
        """Get thumbnail URL (90x128) for cover art."""
        if self.artwork_id:
            base = "https://images.igdb.com/igdb/image/upload"
            return f"{base}/t_cover_small/{self.artwork_id}"
        return None

    @cached_property
    def thumbnail_2x(self) -> Optional[str]:
        """Get 2x thumbnail URL (180x256) for retina displays."""
        if self.artwork_id:
            base = "https://images.igdb.com/igdb/image/upload"
            return f"{base}/t_cover_small_2x/{self.artwork_id}"
        return None

    @cached_property
    def image(self) -> Optional[str]:
        """Get full-size image URL (264x352) for cover art."""
        if self.artwork_id:
            base = "https://images.igdb.com/igdb/image/upload"
            return f"{base}/t_cover_big/{self.artwork_id}"
        return None

    @cached_property
    def image_2x(self) -> Optional[str]:
        """Get 2x retina URL (528x704) for cover art."""
        if self.artwork_id:
            base = "https://images.igdb.com/igdb/image/upload"
            return f"{base}/t_cover_big_2x/{self.artwork_id}"
        return None

    @cached_property
    def homepage_thumb_small(self) -> Optional[str]:
        """Get smallest homepage thumbnail - t_cover_small (90x128)."""
        if self.artwork_id:
            base = "https://images.igdb.com/igdb/image/upload"
            return f"{base}/t_cover_small/{self.artwork_id}"
        return None

    @cached_property
    def homepage_thumb(self) -> Optional[str]:
        """Get homepage thumbnail - t_cover_small_2x (180x256)."""
        if self.artwork_id:
            base = "https://images.igdb.com/igdb/image/upload"
            return f"{base}/t_cover_small_2x/{self.artwork_id}"
        return None

    @cached_property
    def homepage_thumb_2x(self) -> Optional[str]:
        """Get homepage 2x thumbnail - t_cover_big (264x352)."""
        if self.artwork_id:
            base = "https://images.igdb.com/igdb/image/upload"
            return f"{base}/t_cover_big/{self.artwork_id}"
        return None

    @cached_property
    def thumbnail_square(self) -> Optional[str]:
        """Get square thumbnail for mobile cards - t_thumb (90x90)."""
        if self.artwork_id:
            base = "https://images.igdb.com/igdb/image/upload"
            return f"{base}/t_thumb/{self.artwork_id}"
        return None

    @property
    def youtube_url(self) -> Optional[str]:
        """Get full YouTube URL from video ID."""
        if self.youtube_video_id:
            return f"https://www.youtube.com/watch?v={self.youtube_video_id}"
        return None


class WikipediaGameData(models.Model):
    """
    Supplemental Wikipedia/Wikidata game data.
    Multiple records per game supported (e.g., different language editions).
    One record marked as primary for default display.

    Metadata persists when games are deleted (SET_NULL) to allow reconnection
    when games are re-imported.
    """

    game = models.ForeignKey(
        "Game",
        on_delete=models.SET_NULL,
        related_name="wikipedia_game_data_set",
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
    hltb_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="HowLongToBeat ID from Wikidata property P2816",
    )
    steam_app_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Steam AppID from Wikidata property P1733",
    )
    wikiquote_page_title = models.CharField(
        max_length=300,
        null=True,
        blank=True,
        help_text="Wikiquote page title from enwikiquote sitelink",
    )
    page_title = models.CharField(
        max_length=300, db_index=True, help_text="Wikipedia page title"
    )
    primary_genre = models.CharField(max_length=200, null=True, blank=True)
    all_genres = models.TextField(null=True, blank=True)
    lookup_source = models.CharField(max_length=50, null=True, blank=True)
    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Primary Wikipedia record for display (only one per game)",
    )
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "games_wikipediagamedata"
        verbose_name = "Wikipedia Game Data"
        verbose_name_plural = "Wikipedia Game Data"
        indexes = [
            models.Index(fields=["game", "is_primary"]),
            models.Index(fields=["wikidata_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["game"],
                condition=models.Q(is_primary=True) & models.Q(game__isnull=False),
                name="unique_primary_wikipedia_per_game",
            )
        ]

    def __str__(self) -> str:
        if self.game:
            return f"Wikipedia data for {self.game.name}"
        return f"Orphaned Wikipedia data (Wikidata: {self.wikidata_id or 'unknown'})"

    @property
    def wikipedia_url(self) -> Optional[str]:
        """Generate Wikipedia article URL from page title."""
        if self.page_title:
            return f"https://en.wikipedia.org/wiki/{self.page_title.replace(' ', '_')}"
        return None

    @property
    def wikiquote_url(self) -> Optional[str]:
        """Generate Wikiquote article URL from page title."""
        if self.wikiquote_page_title:
            title = self.wikiquote_page_title.replace(" ", "_")
            return f"https://en.wikiquote.org/wiki/{title}"
        return None


class HLTBGameData(models.Model):
    """
    Supplemental HowLongToBeat playtime data.
    Stores completion time estimates from howlongtobeat.com.

    Metadata persists when games are deleted (SET_NULL) to allow reconnection
    when games are re-imported (using igdb_id for matching).
    """

    game = models.ForeignKey(
        "Game",
        on_delete=models.SET_NULL,
        related_name="hltb_game_data_set",
        null=True,
        blank=True,
    )
    igdb_id = models.IntegerField(
        db_index=True,
        help_text="IGDB game ID for reconnection after reimport",
    )
    hltb_id = models.CharField(
        max_length=20,
        db_index=True,
        help_text="HowLongToBeat internal game ID",
    )
    hltb_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Game name as listed on HowLongToBeat",
    )
    fetch_method = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="How the game was matched (wikidata, name_search)",
    )
    similarity = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Name similarity score (0.00-1.00)",
    )
    fetch_error = models.TextField(
        blank=True,
        default="",
        help_text="Error message if fetch failed",
    )
    main_story_hours = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Hours to complete main story",
    )
    main_extra_hours = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Hours to complete main story + extras",
    )
    completionist_hours = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Hours for 100% completion",
    )
    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Primary HLTB record for display (only one per game)",
    )
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "games_hltbgamedata"
        verbose_name = "HLTB Game Data"
        verbose_name_plural = "HLTB Game Data"
        indexes = [
            models.Index(fields=["game", "is_primary"]),
            models.Index(fields=["igdb_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["game"],
                condition=models.Q(is_primary=True) & models.Q(game__isnull=False),
                name="unique_primary_hltb_per_game",
            )
        ]

    def __str__(self) -> str:
        if self.game:
            return f"HLTB data for {self.game.name} ({self.main_story_hours}h)"
        return f"Orphaned HLTB data (IGDB: {self.igdb_id})"

    @property
    def hltb_url(self) -> Optional[str]:
        """Generate HowLongToBeat game URL."""
        if self.hltb_id:
            return f"https://howlongtobeat.com/game/{self.hltb_id}"
        return None


class ProtonDBGameData(models.Model):
    """
    ProtonDB Steam Deck/Linux compatibility data.
    Stores compatibility tier ratings from protondb.com.

    Metadata persists when games are deleted (SET_NULL) to allow reconnection
    when games are re-imported (using igdb_id for matching).
    """

    TIER_CHOICES = [
        ("native", "Native"),
        ("platinum", "Platinum"),
        ("gold", "Gold"),
        ("silver", "Silver"),
        ("bronze", "Bronze"),
        ("borked", "Borked"),
        ("pending", "Pending"),
    ]

    game = models.ForeignKey(
        "Game",
        on_delete=models.SET_NULL,
        related_name="protondb_game_data_set",
        null=True,
        blank=True,
    )
    igdb_id = models.IntegerField(
        db_index=True,
        help_text="IGDB game ID for reconnection after reimport",
    )
    steam_app_id = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Steam AppID used to fetch ProtonDB data",
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        help_text="ProtonDB compatibility tier",
    )
    trending_tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        null=True,
        blank=True,
        help_text="Trending compatibility tier based on recent reports",
    )
    report_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of user reports on ProtonDB",
    )
    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Primary ProtonDB record for display (only one per game)",
    )
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "games_protondbgamedata"
        verbose_name = "ProtonDB Game Data"
        verbose_name_plural = "ProtonDB Game Data"
        indexes = [
            models.Index(fields=["game", "is_primary"]),
            models.Index(fields=["igdb_id"]),
            models.Index(fields=["steam_app_id"]),
            models.Index(fields=["tier"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["game"],
                condition=models.Q(is_primary=True) & models.Q(game__isnull=False),
                name="unique_primary_protondb_per_game",
            )
        ]

    def __str__(self) -> str:
        if self.game:
            return f"ProtonDB data for {self.game.name} ({self.tier})"
        return f"Orphaned ProtonDB data (IGDB: {self.igdb_id})"

    @property
    def protondb_url(self) -> Optional[str]:
        """Generate ProtonDB game URL."""
        if self.steam_app_id:
            return f"https://www.protondb.com/app/{self.steam_app_id}"
        return None

    @property
    def is_steam_deck_compatible(self) -> bool:
        """Returns True if the game is playable on Steam Deck."""
        return self.tier in ("native", "platinum", "gold")


class GameQuerySet(models.QuerySet):
    """Custom QuerySet for Game model with common prefetch patterns."""

    def with_relations(self):
        """Prefetch common relations for game lists and search results."""
        return self.prefetch_related(
            "developers",
            "developers__parent",
            "platforms",
            "genres",
            "series",
        ).select_related(
            "primary_igdb_game_data",
            "primary_wikipedia_game_data",
            "primary_hltb_game_data",
            "primary_protondb_game_data",
        )

    def with_played_status(self, user):
        """Annotate games with played and want-to-play status for the given user."""
        if not user or not user.is_authenticated:
            return self
        from django.db.models import Exists, OuterRef

        return self.annotate(
            is_played_by_user=Exists(
                PlayedGame.objects.filter(user=user, game=OuterRef("pk"))
            ),
            is_want_to_play_by_user=Exists(
                WantToPlayGame.objects.filter(user=user, game=OuterRef("pk"))
            ),
        )

    def with_list_count(self):
        """Annotate games with count of list appearances."""
        from django.db.models import Count

        return self.annotate(list_count=Count("lists", distinct=True))


class Game(models.Model):
    """
    A video game
    """

    name = models.CharField(max_length=100, db_index=True)
    name_normalized = models.CharField(
        max_length=100, null=True, blank=True, db_index=True
    )
    slug = models.SlugField(max_length=100, null=True, blank=True, db_index=True)
    genres = models.ManyToManyField("IGDBGenre", blank=True)
    wikipedia_genres = models.ManyToManyField(
        "WikipediaGenre",
        blank=True,
        related_name="games_with_wikipedia_genre",
    )
    wikipedia_countries = models.ManyToManyField(
        "WikipediaCountry",
        blank=True,
        related_name="games",
        help_text="Countries of origin from Wikidata P495",
    )
    wikipedia_game_modes = models.ManyToManyField(
        "WikipediaGameMode",
        blank=True,
        related_name="games",
        help_text="Game modes from Wikidata P404",
    )
    description = models.TextField(null=True, blank=True)
    rank = models.IntegerField(db_index=True)
    year_of_release = models.PositiveSmallIntegerField(
        null=True, blank=True, db_index=True
    )
    developers = models.ManyToManyField(
        "Developer",
        blank=True,
        related_name="developed_games",
        help_text="Game developers (from IGDB involved_companies)",
    )
    platforms = models.ManyToManyField("Platform", blank=True, related_name="games")
    series = models.ManyToManyField(
        "Series",
        blank=True,
        related_name="games",
        help_text="Game series from IGDB (e.g., 'Mario Kart', 'Final Fantasy VII')",
    )
    created = models.DateTimeField(
        auto_now_add=True, db_index=True, null=True, blank=True
    )
    modified = models.DateTimeField(auto_now=True, db_index=True)
    igdb_id = models.IntegerField(null=True, blank=True, db_index=True)

    # Fast access to primary records (OneToOne for performance)
    primary_igdb_game_data = models.OneToOneField(
        "IGDBGameData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_game",
        help_text="Primary IGDB game data for display",
    )
    primary_wikipedia_game_data = models.OneToOneField(
        "WikipediaGameData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_game",
        help_text="Primary Wikipedia game data for display",
    )
    primary_hltb_game_data = models.OneToOneField(
        "HLTBGameData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_game",
        help_text="Primary HLTB game data for playtime display",
    )
    primary_protondb_game_data = models.OneToOneField(
        "ProtonDBGameData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_game",
        help_text="Primary ProtonDB data for Steam Deck compatibility display",
    )

    # Wikidata ID for linking to Wikipedia/Wikidata
    wikidata_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Wikidata entity ID (e.g., 'Q12345')",
    )

    # Calculated ranking fields
    year_rank = models.IntegerField(null=True, blank=True, db_index=True)
    decade_rank = models.IntegerField(null=True, blank=True, db_index=True)

    objects = GameQuerySet.as_manager()

    class Meta:
        ordering = ["rank"]
        indexes = [
            models.Index(fields=["year_of_release", "rank"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Save the game, calculating normalized name and ensuring data records exist.
        """
        # Save the normalized version of the name
        normalized = unidecode(self.name)
        if self.name != normalized:
            self.name_normalized = normalized

        # Call parent save
        super().save(*args, **kwargs)

    def get_igdb_data(
        self,
        igdb_ids=None,
        cache_results: bool = True,
        api_client=None,
        data: dict = None,
    ) -> None:
        """
        Fetch and populate game data from IGDB API.

        Args:
            igdb_ids: String of comma-separated IGDB IDs (e.g., "1234,5678")
                      or single int. Defaults to self.igdb_id.
            cache_results: Whether to cache the API results
            api_client: Optional API client for dependency injection
            data: Optional pre-fetched game data from IGDB API.
                  If provided, skips API call and uses this data directly.
                  Only used when igdb_ids is None or single ID.

        Returns:
            None. Creates IGDBData records for each ID. First ID becomes primary.
        """
        # Parse IGDB IDs
        if data is not None:
            # Legacy mode: using pre-fetched data for single ID
            ids_to_fetch = [self.igdb_id] if self.igdb_id else []
        elif igdb_ids is None:
            if not self.igdb_id:
                return
            ids_to_fetch = [self.igdb_id]
        elif isinstance(igdb_ids, str):
            ids_to_fetch = [int(x.strip()) for x in igdb_ids.split(",") if x.strip()]
        else:
            ids_to_fetch = [int(igdb_ids)]

        if not ids_to_fetch:
            return

        # Update primary igdb_id reference
        if not self.igdb_id:
            self.igdb_id = ids_to_fetch[0]

        api_client = api_client or igdb.get_api()

        if not api_client and data is None:
            logger.warning("IGDB API unavailable; skipping update for %s", self)
            return

        # Fetch and create records for each ID
        for idx, igdb_id_to_fetch in enumerate(ids_to_fetch):
            # Use pre-fetched data for legacy single-ID mode
            if data is not None and idx == 0:
                game_data = data
            else:
                game_data = api_client.get_game_info_by_id(
                    igdb_id_to_fetch, cache_results
                )

            if not game_data:
                continue

            # Update slug from first record
            if idx == 0:
                # Generate slug from IGDB or game name
                igdb_slug = game_data.get("slug")
                if igdb_slug:
                    # IGDB provides a slug - use it (whether we have one or not)
                    self.slug = slugify(igdb_slug)
                elif not self.slug:
                    # No slug yet and IGDB doesn't provide one - generate from game name
                    self.slug = slugify(self.name)
                # else: Keep existing slug if IGDB doesn't provide one

                # Unset is_primary to avoid UNIQUE constraint violation
                IGDBGameData.objects.filter(game=self, is_primary=True).update(
                    is_primary=False
                )

            # First, check for orphaned record with same igdb_id
            orphaned_record = IGDBGameData.objects.filter(
                igdb_id=igdb_id_to_fetch,
                game__isnull=True,
                is_primary=True,
            ).first()

            if orphaned_record:
                # Reconnect orphaned record
                # (is_primary already unset above at line 573-575)
                orphaned_record.game = self
                orphaned_record.artwork_id = game_data.get("cover", "")
                orphaned_record.url = game_data.get("url", "")
                orphaned_record.description = "\n\n".join(
                    [
                        x
                        for x in [
                            game_data.get("storyline"),
                            game_data.get("summary"),
                        ]
                        if x
                    ]
                )
                orphaned_record.youtube_video_id = game_data.get("youtube_video_id")
                orphaned_record.is_primary = idx == 0  # First record is primary
                orphaned_record.save(
                    update_fields=[
                        "game",
                        "artwork_id",
                        "url",
                        "description",
                        "youtube_video_id",
                        "is_primary",
                    ]
                )
                igdb_game_data = orphaned_record
                created = False
            else:
                # No orphaned record found, create or update
                igdb_game_data, created = IGDBGameData.objects.update_or_create(
                    game=self,
                    igdb_id=igdb_id_to_fetch,
                    defaults={
                        "artwork_id": game_data.get("cover", ""),
                        "url": game_data.get("url", ""),
                        "description": "\n\n".join(
                            [
                                x
                                for x in [
                                    game_data.get("storyline"),
                                    game_data.get("summary"),
                                ]
                                if x
                            ]
                        ),
                        "youtube_video_id": game_data.get("youtube_video_id"),
                        "is_primary": (idx == 0),  # First record is primary
                    },
                )

            # Set as primary on game
            if idx == 0:
                self.primary_igdb_game_data = igdb_game_data

                # Update description field
                self.description = "\n\n".join(
                    [
                        x
                        for x in [
                            game_data.get("storyline"),
                            game_data.get("summary"),
                        ]
                        if x
                    ]
                )

        # Update developers and IGDB genres only from first record
        if ids_to_fetch and (data is not None or api_client):
            # Get first record data for developers/IGDB genres
            if data is not None:
                first_data = data
            else:
                first_data = api_client.get_game_info_by_id(
                    ids_to_fetch[0], cache_results
                )

            devs = []
            for d in first_data.get("developers", []):
                dev = self._get_or_create_developer_with_parents(d)
                devs.append(dev)

            self.developers.set(devs)

            genres = []
            for genre_name in first_data.get("genres", []):
                genre, created = IGDBGenre.objects.get_or_create(name=genre_name)
                genres.append(genre)
            self.genres.set(genres)

            # Update series from IGDB collections
            series_list = []
            for s in first_data.get("series", []):
                series_obj, _ = Series.objects.get_or_create(
                    igdb_id=s["id"],
                    defaults={
                        "name": s["name"],
                        "slug": s.get("slug") or slugify(s["name"]),
                    },
                )
                series_list.append(series_obj)
            self.series.set(series_list)

        # Save only specific fields to avoid updating modified timestamp
        self.save(update_fields=["slug", "primary_igdb_game_data", "description"])

    @staticmethod
    def _get_or_create_developer_with_parents(dev_data: dict) -> "Developer":
        """
        Recursively create developer and all parents up to root.

        Args:
            dev_data: Dict with id, name, slug, parent (dict or None)

        Returns:
            Developer instance
        """
        parent = None
        parent_data = dev_data.get("parent")

        if parent_data and isinstance(parent_data, dict):
            # Recursively create parent first
            parent = Game._get_or_create_developer_with_parents(parent_data)

        # Determine if this is a root developer
        is_root = parent is None

        # Build IGDB URL from slug if available
        igdb_slug = dev_data.get("slug")
        igdb_url = f"https://www.igdb.com/companies/{igdb_slug}" if igdb_slug else None

        # update_or_create prevents duplicates - matches on igdb_id
        developer, _ = Developer.objects.update_or_create(
            igdb_id=dev_data["id"],  # Lookup key - ensures no duplicates
            defaults={
                "name": dev_data["name"],
                "parent": parent,
                # Only root developers get slugs
                "slug": igdb_slug if is_root else None,
                "igdb_url": igdb_url,
            },
        )
        return developer

    def _update_relationships_from_data(self, game_data: dict) -> None:
        """
        Update Developer/IGDB Genre relationships from IGDB game data dict.

        Helper method that updates M2M relationships from pre-fetched data.
        Does not modify IGDBGameData records.

        Args:
            game_data: Dict from IGDB API with developers and IGDB genres keys
        """
        # Update developers
        devs = []
        for d in game_data.get("developers", []):
            dev = self._get_or_create_developer_with_parents(d)
            devs.append(dev)

        self.developers.set(devs)

        # Update IGDB genres
        genres = []
        for genre_name in game_data.get("genres", []):
            genre, created = IGDBGenre.objects.get_or_create(name=genre_name)
            genres.append(genre)
        self.genres.set(genres)

        # Update series from IGDB collections
        series_list = []
        for s in game_data.get("series", []):
            series_obj, _ = Series.objects.get_or_create(
                igdb_id=s["id"],
                defaults={
                    "name": s["name"],
                    "slug": s.get("slug") or slugify(s["name"]),
                },
            )
            series_list.append(series_obj)
        self.series.set(series_list)

    def update_igdb_relationships(self, api_client=None) -> bool:
        """
        Update Company/Studio/IGDB Genre relationships from IGDB API without
        modifying IGDBGameData records.

        Used when games are re-imported after deletion - the IGDBGameData
        is preserved as orphaned records, but M2M relationships need to be
        recreated.

        Args:
            api_client: Optional API client for dependency injection

        Returns:
            True if successful, False otherwise
        """
        if not self.igdb_id:
            return False

        api_client = api_client or igdb.get_api()
        if not api_client:
            logger.warning("IGDB API unavailable; skipping update for %s", self)
            return False

        # Fetch game data from API
        game_data = api_client.get_game_info_by_id(self.igdb_id, cache_results=True)
        if not game_data:
            return False

        # Update relationships from fetched data
        self._update_relationships_from_data(game_data)
        return True

    def get_wikipedia_data(self, page_titles=None, wikidata_ids=None, year=None):
        """
        Fetch and save Wikipedia/Wikidata data for this game.

        Supports multiple page titles or Wikidata IDs (comma-separated):
        - First entry becomes primary (is_primary=True)
        - Additional entries stored as alternate records
        - Each record stores genre data from its Wikipedia page

        Args:
            page_titles: Comma-separated page titles
                (e.g., "Pokémon Red and Blue,Pokémon Red")
            wikidata_ids: Comma-separated Wikidata IDs
                (e.g., "Q12345,Q67890") - not implemented
            year: Optional year for disambiguation

        Usage:
            # Single page title
            game.get_wikipedia_data(page_titles="The Legend of Zelda")

            # Multiple page titles (first becomes primary)
            game.get_wikipedia_data(
                page_titles="Pokémon Red and Blue,Pokémon Red,Pokémon Blue"
            )

            # Use game name if no titles provided
            game.get_wikipedia_data()
        """
        from games.services.wiki_genre_service import WikiGenreService

        # Parse page titles - comma-separated string
        if page_titles is None:
            if not self.name:  # pragma: no cover
                return  # pragma: no cover
            titles_to_fetch = [self.name]
        elif isinstance(page_titles, str):
            titles_to_fetch = [t.strip() for t in page_titles.split(",") if t.strip()]
        else:
            titles_to_fetch = [str(page_titles)]

        # TODO: Add Wikidata ID support if wikidata_ids is provided
        # This would require querying Wikidata API to resolve IDs to page titles
        if wikidata_ids:  # pragma: no cover
            logger.warning(
                "Wikidata ID support not yet implemented"
            )  # pragma: no cover

        # Initialize service
        service = WikiGenreService()

        # Fetch and create records for each page title
        for idx, page_title in enumerate(titles_to_fetch):
            # Fetch genre data from Wikipedia
            result = service.get_genre(page_title, year=year or self.year_of_release)

            # Skip failed lookups
            if result.source.value == "Failed":  # pragma: no cover
                logger.warning(  # pragma: no cover
                    "Failed to fetch Wikipedia data for %s: %s",
                    page_title,
                    result.error_message,
                )
                continue  # pragma: no cover

            # Extract Wikidata ID from URL if available
            wikidata_id_extracted = None
            if result.source_url:
                # Wikipedia URLs might link to Wikidata - for now just store None
                # TODO: Add Wikidata ID extraction from Wikipedia page
                pass

            # For the first entry (primary), unset is_primary on any existing records
            # to avoid UNIQUE constraint violation
            if idx == 0:
                WikipediaGameData.objects.filter(game=self, is_primary=True).update(
                    is_primary=False
                )

            # Capitalize first letter if lowercase, preserve rest
            def capitalize_first(name):
                return (
                    name[0].upper() + name[1:] if name and name[0].islower() else name
                )

            # Capitalize genre names before storing
            capitalized_primary = (
                capitalize_first(result.primary_genre) if result.primary_genre else None
            )
            capitalized_all = (
                [capitalize_first(g) for g in result.all_genres]
                if result.all_genres
                else []
            )
            capitalized_all_str = ", ".join(capitalized_all) if capitalized_all else ""

            # Create or update WikipediaGameData record
            wiki_game_data, created = WikipediaGameData.objects.update_or_create(
                game=self,
                page_title=page_title,
                defaults={
                    "wikidata_id": wikidata_id_extracted,
                    "primary_genre": capitalized_primary,
                    "all_genres": capitalized_all_str,
                    "lookup_source": result.source_url,
                    "is_primary": idx == 0,  # First entry becomes primary
                },
            )

            # Set primary relationship for first entry
            if idx == 0:
                self.primary_wikipedia_game_data = wiki_game_data
                self.save(update_fields=["primary_wikipedia_game_data"])

                # Create WikipediaGenre objects and link to game (only for primary)
                # Use normalization to map scraped genres to canonical names
                if capitalized_all:
                    from games.services.genre_normalizer import (
                        get_or_create_genre,
                        normalize_genre,
                    )

                    wikipedia_genres = []
                    seen_genres = set()  # Track seen genres to avoid duplicates

                    for genre_name in capitalized_all:
                        # Normalize the genre name to canonical form
                        normalized_name = normalize_genre(genre_name)

                        # Skip None (invalid genres) and duplicates
                        if normalized_name is None:
                            continue
                        if normalized_name in seen_genres:
                            continue
                        seen_genres.add(normalized_name)

                        # Get or create the normalized genre with hierarchy
                        genre = get_or_create_genre(normalized_name)
                        wikipedia_genres.append(genre)

                    self.wikipedia_genres.set(wikipedia_genres)

            action = "Created" if created else "Updated"
            logger.info(
                "%s WikipediaGameData for %s (page: %s, primary: %s)",
                action,
                self.name,
                page_title,
                idx == 0,
            )

    # Delegation properties for IGDB image URLs (backward compatibility)
    @cached_property
    def thumbnail(self) -> Optional[str]:
        """Get thumbnail URL (90x128) from primary IGDB data."""
        if self.primary_igdb_game_data:
            return self.primary_igdb_game_data.thumbnail
        return None

    @cached_property
    def thumbnail_2x(self) -> Optional[str]:
        """Get 2x thumbnail URL (180x256) from primary IGDB data."""
        if self.primary_igdb_game_data:
            return self.primary_igdb_game_data.thumbnail_2x
        return None

    @cached_property
    def image(self) -> Optional[str]:
        """Get full-size image URL (264x352) from primary IGDB data."""
        if self.primary_igdb_game_data:
            return self.primary_igdb_game_data.image
        return None

    @cached_property
    def image_2x(self) -> Optional[str]:
        """Get 2x retina URL (528x704) from primary IGDB data."""
        if self.primary_igdb_game_data:
            return self.primary_igdb_game_data.image_2x
        return None

    @cached_property
    def homepage_thumb_small(self) -> Optional[str]:
        """Get smallest homepage thumbnail (90x128) from primary IGDB data."""
        if self.primary_igdb_game_data:
            return self.primary_igdb_game_data.homepage_thumb_small
        return None

    @cached_property
    def homepage_thumb(self) -> Optional[str]:
        """Get homepage thumbnail (180x256) from primary IGDB data."""
        if self.primary_igdb_game_data:
            return self.primary_igdb_game_data.homepage_thumb
        return None

    @cached_property
    def homepage_thumb_2x(self) -> Optional[str]:
        """Get homepage 2x thumbnail (264x352) from primary IGDB data."""
        if self.primary_igdb_game_data:
            return self.primary_igdb_game_data.homepage_thumb_2x
        return None

    @cached_property
    def thumbnail_square(self) -> Optional[str]:
        """Get square thumbnail (90x90) from primary IGDB data."""
        if self.primary_igdb_game_data:
            return self.primary_igdb_game_data.thumbnail_square
        return None

    @cached_property
    def decade(self) -> Optional[int]:
        """Get the decade the game was released (cached)."""
        if self.year_of_release:
            from . import utils

            return utils.year_to_decade(self.year_of_release)
        return None

    def get_display_developers(self, max_count: int = None) -> list:
        """
        Get developers for display, filtering out redundant ancestors.

        When a game credits both a parent company and its subsidiary
        (e.g., Nintendo and Nintendo R&D1), this returns only the most
        specific developer (the subsidiary).

        Args:
            max_count: Maximum number of developers to return (None = no limit)

        Returns:
            List of Developer objects, filtered and optionally limited
        """
        developers = list(self.developers.all())

        if len(developers) <= 1:
            return developers

        # Build set of all ancestor IDs across all developers
        ancestor_ids = set()
        for dev in developers:
            # Walk up the parent chain and collect ancestor IDs
            current = dev.parent
            visited = set()
            while current and current.id not in visited:
                ancestor_ids.add(current.id)
                visited.add(current.id)
                current = current.parent

        # Filter out any developer that is an ancestor of another
        filtered = [dev for dev in developers if dev.id not in ancestor_ids]

        if max_count is not None:
            return filtered[:max_count]
        return filtered

    @property
    def lists_grouped_by_type(self) -> Dict[str, list]:
        """Get lists grouped by type label.

        Returns:
            Dictionary mapping type labels to lists of membership data
        """
        from collections import defaultdict
        from . import constants

        grouped = defaultdict(list)
        # Use .all() to leverage prefetch_related from views when available
        # GameDetailView prefetches with select_related("list__publisher")
        for membership in self.lists.all():
            list_type = membership.list.type
            label = constants.get_list_type_label(list_type)
            grouped[label].append(
                {
                    "id": membership.list.id,
                    "name": membership.list.name,
                    "publication": (
                        membership.list.publisher.name
                        if membership.list.publisher
                        else ""
                    ),
                    "type": list_type,
                    "type_name": label,
                    "url": membership.list.url,
                    "year": membership.list.year,
                    "rank": membership.rank,
                }
            )

        # Sort by predefined order
        sorting_arr = ["All time", "Decade", "Miscellaneous", "End of year"]
        result = {}
        for key in sorting_arr:
            if key in grouped:
                result[key] = grouped[key]
        return result


class GameQuote(models.Model):
    """
    A memorable quote from or about a game.
    Can be from the game itself or from reviews/critics.
    """

    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="quotes")
    text = models.TextField(help_text="The quote text")
    attribution = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Source of quote (e.g., 'IGN Review', 'Game dialogue')",
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Featured quotes are prioritized for Game of the Day",
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-created"]
        indexes = [
            models.Index(fields=["game", "-is_featured"]),
        ]

    def __str__(self) -> str:
        from django.utils.text import Truncator

        return f"{self.game.name}: {Truncator(self.text).words(10)}"


class Publication(models.Model):
    """
    A magazine, website etc that publishes lists
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100)

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the publication, ensuring slug is populated."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class List(models.Model):
    """
    A list published by a critic or publication
    """

    publisher = models.ForeignKey(
        "Publication",
        null=True,
        blank=True,
        related_name="lists",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    url = models.URLField(null=True, blank=True)
    year = models.PositiveSmallIntegerField(db_index=True)
    type = models.CharField(
        max_length=1,
        choices=constants.LIST_TYPES,
        default=constants.LIST_EOY,
        db_index=True,
    )
    order = models.PositiveIntegerField(unique=True, null=True)

    class Meta:
        ordering = ["order", "type", "publisher", "year", "name"]
        unique_together = ["publisher", "name", "year"]
        indexes = [
            models.Index(fields=["type", "year"]),
        ]

    def __str__(self) -> str:
        return self.name


class ListMembership(models.Model):
    """
    A game's appearance in a list
    """

    list = models.ForeignKey("List", on_delete=models.CASCADE)
    game = models.ForeignKey("Game", on_delete=models.CASCADE, related_name="lists")
    rank = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["list", "rank"]),
            models.Index(fields=["game", "list"]),
        ]

    def __str__(self) -> str:
        return f"{self.list} - {self.game} - {self.rank}"


class Post(models.Model):
    """
    A blog-style news post
    """

    title = models.CharField(max_length=100, null=True, blank=True)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether the post is published and visible on the site.",
    )
    send_notification = models.BooleanField(
        default=False,
        help_text=(
            "Check to send email notification to subscribers when publishing. "
            "Only sends if notification hasn't been sent yet."
        ),
    )
    notification_sent = models.BooleanField(
        default=False,
        help_text=(
            "Tracks whether email notification has been sent "
            "for this post (sent only once)."
        ),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )

    class Meta:
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["active", "-date"]),
        ]

    def __str__(self) -> str:
        return self.title or Truncator(self.text).words(10)

    @cached_property
    def text_rendered(self) -> str:
        """Render the markdown text as HTML (cached)."""
        return markdown.markdown(self.text)


class Article(models.Model):
    """
    Long-form blog article with markdown content and SEO-friendly URLs.
    Separate from Post (news updates) for distinct content types.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    excerpt = models.TextField(
        max_length=500,
        blank=True,
        help_text=(
            "Summary shown on the blog list page, in search engine results, "
            "and when shared on social media. Keep under 160 characters for best SEO."
        ),
    )
    content = models.TextField(
        help_text=(
            "Article body in Markdown. "
            "Images can be embedded using ![alt](url) syntax."
        )
    )
    featured_image = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL for the main article image (e.g., from Cloudinary).",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Set automatically when status changes to published.",
    )

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        # Auto-set published_at when first published
        if self.status == self.Status.PUBLISHED and not self.published_at:
            from django.utils import timezone

            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @cached_property
    def content_rendered(self) -> str:
        """Render the markdown content as HTML (cached)."""
        return markdown.markdown(
            self.content, extensions=["fenced_code", "tables", "toc"]
        )

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("article-detail", kwargs={"slug": self.slug})
