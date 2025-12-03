import logging
from functools import cached_property
from typing import Any, Dict, Optional

import markdown
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models
from django.utils.text import Truncator, slugify
from unidecode import unidecode

from . import constants, igdb

logger = logging.getLogger(__name__)


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

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Developer(models.Model):
    """
    A company or organization that produces video games
    """

    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=100, null=True, blank=True, db_index=True)
    igdb_id = models.IntegerField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def other_aliases(self) -> models.QuerySet:
        return self.aliases.exclude(name=self.name)


class DeveloperAlias(models.Model):
    """
    A different name that a developer may use
    """

    developer = models.ForeignKey(
        "Developer", on_delete=models.CASCADE, related_name="aliases"
    )
    name = models.CharField(max_length=100, unique=True)
    igdb_id = models.IntegerField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Developer aliases"

    def __str__(self) -> str:
        if self.name != self.developer.name:
            return f"{self.name} ({self.developer})"
        else:
            return self.name


class Genre(models.Model):
    """A video game genre"""

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return self.name


class GameQuerySet(models.QuerySet):
    """Custom QuerySet for Game model with common prefetch patterns."""

    def with_relations(self):
        """Prefetch common relations for game lists and search results."""
        return self.prefetch_related(
            "developers",
            "developers__developer",
            "platforms",
            "genres",
        )


class Game(models.Model):
    """
    A video game
    """

    name = models.CharField(max_length=100, db_index=True)
    name_normalized = models.CharField(
        max_length=100, null=True, blank=True, db_index=True
    )
    slug = models.SlugField(max_length=100, null=True, blank=True, db_index=True)
    genres = models.ManyToManyField("Genre", blank=True)
    description = models.TextField(null=True, blank=True)
    rank = models.IntegerField(db_index=True)
    year_of_release = models.PositiveSmallIntegerField(
        null=True, blank=True, db_index=True
    )
    developers = models.ManyToManyField(
        "DeveloperAlias", blank=True, related_name="games"
    )
    platforms = models.ManyToManyField("Platform", blank=True, related_name="games")
    created = models.DateTimeField(
        auto_now_add=True, db_index=True, null=True, blank=True
    )
    modified = models.DateTimeField(auto_now=True, db_index=True)
    igdb_id = models.IntegerField(null=True, blank=True, db_index=True)
    igdb_artwork_id = models.CharField(max_length=100, null=True, blank=True)
    igdb_url = models.URLField(null=True, blank=True)
    year_rank = models.IntegerField(null=True, blank=True, db_index=True)
    decade_rank = models.IntegerField(null=True, blank=True, db_index=True)
    # Wikipedia genre data (separate from IGDB genres)
    # primary_genre is the first genre in the ordered list (for sorting)
    # all_genres is pipe-separated for display/filtering
    wikipedia_primary_genre = models.CharField(max_length=200, null=True, blank=True)
    wikipedia_all_genres = models.TextField(null=True, blank=True)
    wikidata_id = models.CharField(max_length=20, null=True, blank=True)  # deprecated

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
        Save the game, calculating normalized name.
        """
        # Save the normalized version of the name
        normalized = unidecode(self.name)
        if self.name != normalized:
            self.name_normalized = normalized

        super().save(*args, **kwargs)

    def get_igdb_data(
        self, cache_results: bool = True, api_client=None, data: dict = None
    ) -> None:
        """
        Fetch and populate game data from IGDB API.

        Args:
            cache_results: Whether to cache the API results
            api_client: Optional API client for dependency injection
            data: Optional pre-fetched game data from IGDB API.
                  If provided, skips API call and uses this data directly.

        Returns:
            None. Updates the model instance fields in-place.
        """
        if not self.igdb_id:
            return

        # Use pre-fetched data if provided, otherwise fetch from API
        if data is None:
            # Allow dependency injection for tests while preventing reuse of a global
            # API client that can accumulate cached responses across requests.
            api_client = api_client or igdb.get_api()

            if not api_client:
                logger.warning("IGDB API unavailable; skipping update for %s", self)
                return

            data = api_client.get_game_info_by_id(self.igdb_id, cache_results)
        self.slug = slugify(data.get("slug"))
        self.igdb_url = data.get("url")
        self.igdb_artwork_id = data.get("cover")
        self.description = "\n\n".join(
            [x for x in [data.get("storyline"), data.get("summary")] if x]
        )

        developer_aliases = []
        for d in data["developers"]:

            # This developer is a parent
            if not d.get("parent"):
                developer, created = Developer.objects.update_or_create(
                    name=d["name"],
                    defaults={
                        "slug": d["slug"],
                        "igdb_id": d["id"],
                    },
                )

            # This developer has a parent
            else:
                parent_obj = d.get("parent")
                if parent_obj:
                    developer, created = Developer.objects.update_or_create(
                        name=parent_obj["name"],
                        defaults={
                            "slug": parent_obj["slug"],
                            "igdb_id": parent_obj["id"],
                        },
                    )

                    # Ensure parent has an alias too (prevents orphaned developers)
                    try:
                        DeveloperAlias.objects.update_or_create(
                            developer=developer,
                            name=parent_obj["name"],
                            defaults={
                                "igdb_id": parent_obj["id"],
                            },
                        )
                    except IntegrityError:
                        # Parent alias already exists linked to another developer
                        pass

            try:
                developer_alias, created = DeveloperAlias.objects.update_or_create(
                    developer=developer,
                    name=d["name"],
                    defaults={
                        "igdb_id": d["id"],
                    },
                )
            except IntegrityError:
                developer_alias = DeveloperAlias.objects.get(name=d["name"])

            developer_aliases.append(developer_alias)

        self.developers.set(developer_aliases)

        genres = []
        for genre_name in data.get("genres"):
            genre, created = Genre.objects.get_or_create(name=genre_name)
            genres.append(genre)
        self.genres.set(genres)

    @cached_property
    def thumbnail(self) -> Optional[str]:
        """Get the thumbnail URL for the game's cover art (90x128) (cached)."""
        if self.igdb_artwork_id:
            return (
                "https://images.igdb.com/igdb/image/upload/t_cover_small/"
                f"{self.igdb_artwork_id}"
            )
        return None

    @cached_property
    def thumbnail_2x(self) -> Optional[str]:
        """Get the 2x thumbnail URL for retina displays (180x256) (cached)."""
        if self.igdb_artwork_id:
            return (
                "https://images.igdb.com/igdb/image/upload/t_cover_small_2x/"
                f"{self.igdb_artwork_id}"
            )
        return None

    @cached_property
    def image(self) -> Optional[str]:
        """Get the full-size image URL for the game's cover art (264x352) (cached)."""
        if self.igdb_artwork_id:
            return (
                "https://images.igdb.com/igdb/image/upload/t_cover_big/"
                f"{self.igdb_artwork_id}"
            )
        return None

    @cached_property
    def image_2x(self) -> Optional[str]:
        """Get the 2x retina URL for the game's cover art (528x704) (cached)."""
        if self.igdb_artwork_id:
            return (
                "https://images.igdb.com/igdb/image/upload/t_cover_big_2x/"
                f"{self.igdb_artwork_id}"
            )
        return None

    @cached_property
    def homepage_thumb_small(self) -> Optional[str]:
        """Get smallest homepage thumbnail - t_cover_small (90x128) for mobile."""
        if self.igdb_artwork_id:
            return (
                "https://images.igdb.com/igdb/image/upload/t_cover_small/"
                f"{self.igdb_artwork_id}"
            )
        return None

    @cached_property
    def homepage_thumb(self) -> Optional[str]:
        """Get homepage thumbnail - t_cover_small_2x (180x256) avoids upscaling blur."""
        if self.igdb_artwork_id:
            return (
                "https://images.igdb.com/igdb/image/upload/t_cover_small_2x/"
                f"{self.igdb_artwork_id}"
            )
        return None

    @cached_property
    def homepage_thumb_2x(self) -> Optional[str]:
        """Get homepage 2x thumbnail - t_cover_big (264x352) for retina quality."""
        if self.igdb_artwork_id:
            return (
                "https://images.igdb.com/igdb/image/upload/t_cover_big/"
                f"{self.igdb_artwork_id}"
            )
        return None

    @cached_property
    def decade(self) -> Optional[int]:
        """Get the decade the game was released (cached)."""
        if self.year_of_release:
            from . import utils

            return utils.year_to_decade(self.year_of_release)
        return None

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
    active = models.BooleanField(default=True, db_index=True)
    author = models.ForeignKey(
        get_user_model(),
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
