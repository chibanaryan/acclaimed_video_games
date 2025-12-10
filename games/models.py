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


class Company(models.Model):
    """
    A parent company that owns game development studios.

    In IGDB's data model, this corresponds to a "company" record that appears
    as the "parent" field of other companies. Examples: Nintendo (parent of
    Nintendo EAD, Nintendo EPD), Activision Blizzard (parent of Activision,
    Blizzard Entertainment).

    Note: Some companies both own studios AND develop games directly. In that
    case, the company will have a Studio record with the same name (e.g., both
    a Company "Valve" and a Studio "Valve").

    This model is primarily used for:
    - Organizing studios hierarchically on developer detail pages
    - Tracking corporate ownership relationships
    - Providing company-level slugs for URL routing (/developers/<slug>/)

    Games are linked to Studio records, not Company records directly.
    """

    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=100, null=True, blank=True, db_index=True)
    igdb_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="IGDB company ID (from companies endpoint)",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Companies"

    def __str__(self) -> str:
        return self.name

    @property
    def subsidiary_studios(self) -> models.QuerySet:
        """Returns only subsidiary studios (excludes self-named studio)."""
        return self.studios.exclude(name=self.name)


class Studio(models.Model):
    """
    A game development studio that creates games.

    In IGDB's data model, this corresponds to a "company" record that appears
    in a game's "involved_companies" list with developer=True. Studios can be:

    1. **Independent**: No parent company (company=None)
       Examples: Independent studios, self-published developers

    2. **Subsidiary**: Owned by a parent company (company=Company)
       Examples: Nintendo EAD (company=Nintendo), Respawn (company=EA)

    3. **Primary studio**: Same name as parent (company=Company, name=company.name)
       Examples: Valve (both company and studio), FromSoftware

    Games are linked to Studios via the Game.studios M2M field. This allows
    proper attribution when a parent company develops games directly (e.g.,
    Activision games show on the Activision company page).

    Note: User-facing pages refer to these as "developers" for familiarity,
    but internally they represent the actual development studios.
    """

    company = models.ForeignKey(
        "Company",
        on_delete=models.CASCADE,
        related_name="studios",
        null=True,
        blank=True,
        help_text=(
            "Parent company that owns this studio " "(optional for independent studios)"
        ),
    )
    name = models.CharField(max_length=100, unique=True)
    igdb_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="IGDB company ID (from companies endpoint)",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Studios"

    def __str__(self) -> str:
        if self.company and self.name != self.company.name:
            return f"{self.name} ({self.company})"
        else:
            return self.name

    @property
    def is_primary_studio(self) -> bool:
        """True if this studio has the same name as its parent company."""
        return self.company is not None and self.name == self.company.name

    @property
    def is_independent(self) -> bool:
        """True if this studio has no parent company."""
        return self.company is None

    @property
    def root_company(self):
        """
        Returns the root (topmost) company in the ownership hierarchy.

        For nested studios like BioWare Edmonton → BioWare → EA,
        this returns the ultimate parent (EA).
        """
        if not self.company:
            return None

        current = self.company
        visited = {current.id}  # Prevent infinite loops

        # Traverse up the hierarchy
        while True:
            # Check if this company also exists as a studio with a parent
            matching_studio = (
                Studio.objects.filter(name=current.name, company__isnull=False)
                .select_related("company")
                .first()
            )

            if matching_studio and matching_studio.company_id not in visited:
                visited.add(matching_studio.company_id)
                current = matching_studio.company
            else:
                break

        return current


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


class IGDBGameData(models.Model):
    """
    Supplemental IGDB game data.
    Multiple records per game supported (e.g., Pokémon Red/Blue/Yellow).
    One record marked as primary for default display.
    """

    game = models.ForeignKey(
        "Game", on_delete=models.CASCADE, related_name="igdb_game_data_set"
    )
    igdb_id = models.IntegerField(
        db_index=True, help_text="IGDB game ID for this specific version/entry"
    )
    artwork_id = models.CharField(
        max_length=100, db_index=True, help_text="IGDB cover art hash (e.g., 'co1234')"
    )
    url = models.URLField(help_text="IGDB game detail page URL")
    description = models.TextField(null=True, blank=True)
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
                condition=models.Q(is_primary=True),
                name="unique_primary_igdb_per_game",
            )
        ]

    def __str__(self) -> str:
        return f"IGDB data for {self.game.name} (ID: {self.igdb_id})"

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


class WikipediaGameData(models.Model):
    """
    Supplemental Wikipedia/Wikidata game data.
    Multiple records per game supported (e.g., different language editions).
    One record marked as primary for default display.
    """

    game = models.ForeignKey(
        "Game", on_delete=models.CASCADE, related_name="wikipedia_game_data_set"
    )
    wikidata_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Wikidata entity ID (e.g., 'Q12345')",
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
                condition=models.Q(is_primary=True),
                name="unique_primary_wikipedia_per_game",
            )
        ]

    def __str__(self) -> str:
        return f"Wikipedia data for {self.game.name}"

    @property
    def wikipedia_url(self) -> Optional[str]:
        """Generate Wikipedia article URL from page title."""
        if self.page_title:
            return f"https://en.wikipedia.org/wiki/{self.page_title.replace(' ', '_')}"
        return None


class GameQuerySet(models.QuerySet):
    """Custom QuerySet for Game model with common prefetch patterns."""

    def with_relations(self):
        """Prefetch common relations for game lists and search results."""
        return self.prefetch_related(
            "studios",
            "studios__company",
            "platforms",
            "genres",
        ).select_related(
            "primary_igdb_game_data",
            "primary_wikipedia_game_data",
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
    studios = models.ManyToManyField(
        "Studio",
        blank=True,
        related_name="games",
        help_text=(
            "Game development studios that created this game "
            "(from IGDB involved_companies)"
        ),
    )
    platforms = models.ManyToManyField("Platform", blank=True, related_name="games")
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

    # DEPRECATED FIELDS - Will be removed in future release
    igdb_artwork_id = models.CharField(max_length=100, null=True, blank=True)
    igdb_url = models.URLField(null=True, blank=True)
    year_rank = models.IntegerField(null=True, blank=True, db_index=True)
    decade_rank = models.IntegerField(null=True, blank=True, db_index=True)
    # DEPRECATED FIELDS - Wikipedia data moved to WikipediaData model
    wikipedia_primary_genre = models.CharField(max_length=200, null=True, blank=True)
    wikipedia_all_genres = models.TextField(null=True, blank=True)
    wikidata_id = models.CharField(max_length=20, null=True, blank=True)
    wikipedia_page_title = models.CharField(
        max_length=300,
        null=True,
        blank=True,
        db_index=True,
        help_text="Wikipedia page title (e.g., 'Zelda: Breath of the Wild')",
    )
    wikipedia_lookup_source = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Lookup method: wikidata, opensearch_year, etc.",
    )

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

        # Call parent save first to ensure we have a primary key
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Create empty IGDB and Wikipedia game data records if they don't exist
        # This ensures every game has at least one record in each table
        if is_new:
            # Create empty IGDB game data if we have an igdb_id and no existing record
            if self.igdb_id and not IGDBGameData.objects.filter(game=self).exists():
                # Copy deprecated fields if they exist for backward compatibility
                igdb_data = IGDBGameData.objects.create(
                    game=self,
                    igdb_id=self.igdb_id,
                    artwork_id=self.igdb_artwork_id or "",
                    url=self.igdb_url or "",
                    description=self.description or "",
                    is_primary=True,
                )
                self.primary_igdb_game_data = igdb_data
                # Save again to update the FK relationship
                super().save(update_fields=["primary_igdb_game_data"])

            # Create empty Wikipedia game data only if no existing record
            if not WikipediaGameData.objects.filter(game=self).exists():
                # Copy deprecated fields if they exist for backward compatibility
                wiki_data = WikipediaGameData.objects.create(
                    game=self,
                    page_title=self.wikipedia_page_title or "",
                    primary_genre=self.wikipedia_primary_genre or "",
                    all_genres=self.wikipedia_all_genres or "",
                    lookup_source=self.wikipedia_lookup_source or "",
                    is_primary=True,
                )
                self.primary_wikipedia_game_data = wiki_data
                # Save again to update the FK relationship
                super().save(update_fields=["primary_wikipedia_game_data"])

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
                self.slug = slugify(game_data.get("slug"))
                # Unset is_primary to avoid UNIQUE constraint violation
                IGDBGameData.objects.filter(game=self, is_primary=True).update(
                    is_primary=False
                )

            # Create or update IGDBGameData
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
                    "is_primary": (idx == 0),  # First record is primary
                },
            )

            # Set as primary on game
            if idx == 0:
                self.primary_igdb_game_data = igdb_game_data

                # Update deprecated fields for backward compatibility
                self.igdb_url = game_data.get("url")
                self.igdb_artwork_id = game_data.get("cover")
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

        # Update studios and genres only from first record
        if ids_to_fetch and (data is not None or api_client):
            # Get first record data for studios/genres
            if data is not None:
                first_data = data
            else:
                first_data = api_client.get_game_info_by_id(
                    ids_to_fetch[0], cache_results
                )

            studios = []
            for d in first_data["studios"]:
                # This company is independent (no parent)
                if not d.get("parent"):
                    company, created = Company.objects.update_or_create(
                        name=d["name"],
                        defaults={
                            "slug": d["slug"],
                            "igdb_id": d["id"],
                        },
                    )

                # This studio has a parent company
                else:
                    parent_obj = d.get("parent")
                    if parent_obj:
                        company, created = Company.objects.update_or_create(
                            name=parent_obj["name"],
                            defaults={
                                "slug": parent_obj["slug"],
                                "igdb_id": parent_obj["id"],
                            },
                        )

                try:
                    studio, created = Studio.objects.update_or_create(
                        name=d["name"],
                        defaults={
                            "igdb_id": d["id"],
                            "company": company,
                        },
                    )
                except IntegrityError:
                    studio = Studio.objects.get(name=d["name"])

                studios.append(studio)

            self.studios.set(studios)

            genres = []
            for genre_name in first_data.get("genres"):
                genre, created = Genre.objects.get_or_create(name=genre_name)
                genres.append(genre)
            self.genres.set(genres)

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

            # Create or update WikipediaGameData record
            wiki_game_data, created = WikipediaGameData.objects.update_or_create(
                game=self,
                page_title=page_title,
                defaults={
                    "wikidata_id": wikidata_id_extracted,
                    "primary_genre": result.primary_genre,
                    "all_genres": result.all_genres_str,
                    "lookup_source": result.source_url,
                    "is_primary": idx == 0,  # First entry becomes primary
                },
            )

            # Set primary relationship for first entry
            if idx == 0:
                self.primary_wikipedia_game_data = wiki_game_data
                # Update deprecated fields for backward compatibility
                self.wikipedia_primary_genre = result.primary_genre
                self.wikipedia_all_genres = result.all_genres_str
                self.save(
                    update_fields=[
                        "primary_wikipedia_game_data",
                        "wikipedia_primary_genre",
                        "wikipedia_all_genres",
                    ]
                )

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
        help_text=(
            "⚠️ Checking this box will publish the post and "
            "send email notifications to all subscribers."
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


class Subscriber(models.Model):
    """
    Newsletter subscriber for post notifications with double opt-in.
    """

    email = models.EmailField(unique=True, db_index=True)
    date_subscribed = models.DateTimeField(auto_now_add=True)
    is_confirmed = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    confirmation_token = models.CharField(max_length=64, unique=True, db_index=True)
    unsubscribe_token = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        ordering = ["-date_subscribed"]
        indexes = [
            models.Index(fields=["is_confirmed", "is_active"]),
        ]

    def __str__(self) -> str:
        status = "confirmed" if self.is_confirmed else "pending"
        active_status = "" if self.is_active else " (unsubscribed)"
        return f"{self.email} ({status}){active_status}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Generate tokens on first save if not already set."""
        if not self.confirmation_token:
            import secrets

            self.confirmation_token = secrets.token_urlsafe(32)
        if not self.unsubscribe_token:
            import secrets

            self.unsubscribe_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
