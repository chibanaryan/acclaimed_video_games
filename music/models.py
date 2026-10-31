"""
Music models for the multi-media platform.

Albums are the media item; Artist plays the role Developer plays for games
and Author plays for books. Everything shared lives in ``core.models``, so
this module only adds what is specific to recorded music.
"""

import re
from functools import cached_property
from typing import Any, List, Optional

from django.db import models
from django.db.models import Count, Exists, OuterRef
from django.utils.text import slugify

from core.models import (
    ExternalDataBase,
    ListBase,
    ListMembershipBase,
    MediaItemBase,
    PublicationBase,
    SavedFilterSetBase,
    UserTrackingBase,
)
from core.sites import MUSIC, canonical_url, site_reverse
from music import config


class Artist(models.Model):
    """
    A recording artist: a band, a solo performer or an alias.

    Every artist comes from the release's ``ArtistInfo.txt`` under the data
    provider's own permanent index, ``source_id``, which is what an import
    upserts on - so an artist keeps its pk across imports. Its slug follows
    its current name, disambiguated by its Wikipedia title (see
    ``music.services.artist_slugs``), so a slug - and a ``?artists=`` link,
    which takes slugs - lasts only as long as the name.

    An artist can be credited under several names, ``name_variants``:
    Prince is also "Prince and the Revolution", Frank Zappa "The Mothers of
    Invention". A credit names the artist and the
    variant (``AlbumCredit.variant``), so every album credited under any of
    an artist's names is theirs, and the credit line still reads as printed.

    Unlike ``CreatorBase`` creators, every artist has a slug and a page.
    """

    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(
        max_length=210,
        null=True,
        blank=True,
        db_index=True,
        help_text="From the current name; every import rebuilds it",
    )
    source_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="The data provider's permanent artist index (ArtistInfo.txt)",
    )
    musicbrainz_id = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        db_index=True,
        help_text="MusicBrainz artist MBID",
    )
    wikidata_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Wikidata entity ID (e.g., 'Q1299')",
    )
    all_wikidata_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="Every Wikidata ID for this artist; the first is primary",
    )
    wikipedia_title = models.CharField(
        max_length=300,
        blank=True,
        help_text=(
            "English Wikipedia title of the primary Wikidata ID, from the "
            "Wikidata pass; tells same-named artists' slugs apart"
        ),
    )
    name_variants = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Every name the release credits this artist under, in file order; "
            "the first is the name. Some are unused by the ranked albums"
        ),
    )

    class Meta:
        db_table = "music_artist"
        ordering = ["name"]
        verbose_name = "Artist"
        verbose_name_plural = "Artists"
        indexes = [
            models.Index(fields=["musicbrainz_id"]),
            models.Index(fields=["wikidata_id"]),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return site_reverse(MUSIC, "music:artist-detail", kwargs={"slug": self.slug})


class MusicGenre(models.Model):
    """
    A hierarchical music genre with a denormalized path.

    Mirrors ``books.models.BookGenre``: a parent FK plus a cached ``level``
    and ``path`` so a filter UI can render the tree without walking it. Rows
    are written by ``music.services.genre_rebuild`` from the stored metadata;
    the supplied ranking files carry no genre data, so this starts empty.
    """

    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(max_length=110, unique=True, null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent genre in the hierarchy",
    )
    level = models.PositiveSmallIntegerField(
        default=0, help_text="Depth in the hierarchy (0 = root)"
    )
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="Sort order within the same level"
    )
    path = models.CharField(
        max_length=300,
        blank=True,
        db_index=True,
        help_text="Denormalized ancestry, e.g. 'Rock > Punk Rock > Post-Punk'",
    )
    description = models.TextField(blank=True)
    icon_name = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "music_musicgenre"
        ordering = ["level", "display_order", "name"]
        verbose_name = "Music Genre"
        verbose_name_plural = "Music Genres"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["parent", "level"]),
            models.Index(fields=["level", "display_order"]),
        ]

    def __str__(self) -> str:
        return self.path or self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Populate the slug, then recompute level and path from the parent."""
        if not self.slug:
            self.slug = slugify(self.name)
        if self.parent:
            self.level = self.parent.level + 1
            self.path = f"{self.parent.path} > {self.name}"
        else:
            self.level = 0
            self.path = self.name
        super().save(*args, **kwargs)

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @property
    def is_leaf(self) -> bool:
        return not self.children.exists()

    def get_descendants(self, include_self: bool = False) -> List["MusicGenre"]:
        """Return every genre below this one, depth first."""
        descendants = []
        if include_self:
            descendants.append(self)
        for child in self.children.all():
            descendants.append(child)
            descendants.extend(child.get_descendants(include_self=False))
        return descendants

    def get_descendant_ids(self, include_self: bool = False) -> List[int]:
        """Return the ids of every genre below this one (for filtering)."""
        ids = []
        if include_self:
            ids.append(self.id)
        for child in self.children.all():
            ids.append(child.id)
            ids.extend(child.get_descendant_ids(include_self=False))
        return ids


def credits_prefetch() -> models.Prefetch:
    """The credits in their file order, each with its artist joined.

    What a row's credit line reads through ``Album.credited_artists``: one
    query for every album's credits, where the string path
    ``credits__artist`` would take two. A function so that ``AlbumCredit``,
    defined below, is looked up when it is called.
    """
    return models.Prefetch(
        "credits", queryset=AlbumCredit.objects.select_related("artist")
    )


class AlbumQuerySet(models.QuerySet):
    """Chainable query helpers that keep album list views off the N+1 path."""

    def with_relations(self) -> "AlbumQuerySet":
        """Prefetch everything an album row renders.

        ``primary_musicbrainz_album_data`` is joined because every row asks
        it for the cover URL; without it a hundred-row page runs a hundred
        extra queries.
        """
        return self.select_related("primary_musicbrainz_album_data").prefetch_related(
            credits_prefetch(), "genres"
        )

    def with_list_count(self) -> "AlbumQuerySet":
        """Annotate how many source lists each album appears on."""
        return self.annotate(list_count=Count("lists", distinct=True))

    def with_listen_status(self, user) -> "AlbumQuerySet":
        """Annotate have / heard / want-to-listen status for ``user``.

        The three are exclusive, so each annotation names exactly one state:
        an owned album is ``is_owned_by_user`` and not ``is_listened_by_user``,
        though both are ``ListenedAlbum`` rows.

        A no-op for an anonymous user, so callers that filter on the
        annotations must guard the same way rather than assume they exist.
        """
        if not user or not user.is_authenticated:
            return self

        return self.annotate(
            is_owned_by_user=Exists(
                ListenedAlbum.objects.filter(
                    user=user, album=OuterRef("pk"), owned=True
                )
            ),
            is_listened_by_user=Exists(
                ListenedAlbum.objects.filter(
                    user=user, album=OuterRef("pk"), owned=False
                )
            ),
            is_want_to_listen_by_user=Exists(
                WantToListenAlbum.objects.filter(user=user, album=OuterRef("pk"))
            ),
        )


def _is_reserved_slug(slug: str) -> bool:
    """Whether ``slug`` would be shadowed by a fixed route under /music/."""
    return slug in config.RESERVED_ALBUM_SLUGS or bool(
        re.match(config.RESERVED_ALBUM_SLUG_PATTERN, slug)
    )


class Album(MediaItemBase):
    """
    A studio album, ranked by aggregating published critics' lists.

    ``rank`` comes from the import file, as it does for games; ``year_rank``
    and ``decade_rank`` are derived from it by
    ``core.services.ranking.update_year_decade_ranks``.
    """

    objects = AlbumQuerySet.as_manager()

    year_released = models.PositiveSmallIntegerField(
        null=True, blank=True, db_index=True
    )
    release_date = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "First release date, to order albums within their year. Derived "
            "from the fetched metadata by music.services.release_dates; the "
            "year itself stays year_released, as published."
        ),
    )
    release_date_precision = models.CharField(
        max_length=5,
        blank=True,
        help_text="'day' or 'month'; blank shows only the month, the safe reading",
    )
    artist_credit = models.CharField(
        max_length=300,
        blank=True,
        help_text=(
            "The credited names as one line, e.g. 'Paul McCartney and Wings', "
            "'Jimmy Cliff & Various Artists' or 'Various Artists'. Derived on "
            "import from the credits; kept as text for search, slugs, meta tags "
            "and the CSV export."
        ),
    )
    various_artists = models.BooleanField(
        default=False,
        help_text=(
            "The credit ends in 'Various Artists': a compilation, or a "
            "soundtrack credited to an artist and others"
        ),
    )
    artists = models.ManyToManyField(
        Artist, blank=True, through="AlbumCredit", related_name="albums"
    )
    genres = models.ManyToManyField(MusicGenre, blank=True, related_name="albums")
    musicbrainz_release_group_id = models.CharField(
        max_length=36,
        null=True,
        blank=True,
        db_index=True,
        help_text="MusicBrainz release-group MBID (Wikidata P436)",
    )
    discogs_master_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Discogs master release ID (Wikidata P1954)",
    )
    cover_image_url = models.URLField(null=True, blank=True)
    all_wikidata_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="Every Wikidata ID for this album; the first is primary",
    )

    # Fast-path pointers to the primary external-metadata record of each
    # source, so rendering a row never has to filter on is_primary.
    primary_wikipedia_album_data = models.OneToOneField(
        "WikipediaAlbumData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_album",
        help_text="Primary Wikipedia/Wikidata record for display",
    )
    primary_discogs_album_data = models.OneToOneField(
        "DiscogsAlbumData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_album",
        help_text="Primary Discogs record for display",
    )
    primary_musicbrainz_album_data = models.OneToOneField(
        "MusicBrainzAlbumData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_album",
        help_text="Primary MusicBrainz record for display",
    )

    class Meta:
        db_table = "music_album"
        ordering = ["rank"]
        verbose_name = "Album"
        verbose_name_plural = "Albums"
        indexes = [
            models.Index(fields=["year_released", "rank"]),
            models.Index(fields=["musicbrainz_release_group_id"]),
            models.Index(fields=["discogs_master_id"]),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Generate a unique slug, then defer to MediaItemBase for the rest."""
        if not self.slug:
            self.slug = self._build_unique_slug()
        super().save(*args, **kwargs)

    def _build_unique_slug(self) -> str:
        """Slugify the title, disambiguating with the artist then a counter.

        Album titles collide far more than game titles do - several acts have
        a record called '1999' - so fall back to the credit before resorting
        to a numeric tail.
        """
        base = slugify(self.name) or "album"
        candidates = [base]
        if self.artist_credit:
            with_artist = slugify(f"{self.name} {self.artist_credit}")
            if with_artist and with_artist != base:
                candidates.append(with_artist)

        taken = Album.objects.exclude(pk=self.pk) if self.pk else Album.objects.all()
        for candidate in candidates:
            if _is_reserved_slug(candidate):
                continue
            if not taken.filter(slug=candidate).exists():
                return candidate

        suffix = 2
        while taken.filter(slug=f"{base}-{suffix}").exists():
            suffix += 1
        return f"{base}-{suffix}"

    def get_absolute_url(self) -> str:
        return site_reverse(MUSIC, "music:album-detail", kwargs={"slug": self.slug})

    @property
    def wikidata_qids(self) -> List[str]:
        """Every Wikidata ID for this album, primary first, each once.

        Two albums in the release carry two QIDs - the UK and US editions of
        'Let It Bleed' and 'Aftermath' - so the extras matter: the importer
        matches a release row on any of them, and one of them is where the
        MusicBrainz and Discogs ids actually live.
        """
        qids = []
        for qid in [self.wikidata_id, *(self.all_wikidata_ids or [])]:
            if qid and qid not in qids:
                qids.append(qid)
        return qids

    @property
    def discogs_master_url(self) -> Optional[str]:
        """The Discogs master page, which its API terms want credited."""
        if not self.discogs_master_id:
            return None
        return f"https://www.discogs.com/master/{self.discogs_master_id}"

    @cached_property
    def decade(self) -> Optional[int]:
        """The release decade, e.g. 1967 -> 1960."""
        if self.year_released is None:
            return None
        return (self.year_released // 10) * 10

    @cached_property
    def year(self) -> Optional[int]:
        """Alias for ``year_released``.

        ``core/includes/_base_media_row.html`` renders ``item.year``, so a
        media item has to expose the release year under that name to use the
        shared row template.
        """
        return self.year_released

    @cached_property
    def thumbnail(self) -> Optional[str]:
        """Row-sized cover art (250px), falling back to the stored URL.

        Rows render at 90px, so the 250px variant covers 2x displays. The
        Cover Art Archive serves a size by URL, so the ids on the MusicBrainz
        record are enough to ask for one.
        """
        return self._cover_art_url(250) or self.cover_image_url

    @cached_property
    def image(self) -> Optional[str]:
        """Detail-page cover art (500px), falling back to the stored URL."""
        return self._cover_art_url(500) or self.cover_image_url

    @cached_property
    def image_og(self) -> Optional[str]:
        """``image`` as an absolute URL, for Open Graph and JSON-LD.

        A stored cover is a path on this site, which scrapers and search
        engines cannot fetch on its own.
        """
        image = self.image
        if image and image.startswith("/"):
            return canonical_url(MUSIC, image)
        return image

    def _cover_art_url(self, size: int) -> Optional[str]:
        """The best URL for cover art at ``size`` px, or None.

        Prefers our own stored copy. The Cover Art Archive redirects to
        archive.org, which returns an intermittent 500 on perfectly valid
        images - measured at roughly one request in ten, with some items
        broken outright. On a page showing a hundred covers that guarantees
        visible breakage on every load, so the bytes are stored locally and
        served from here. The remote URL stays as the fallback.
        """
        data = self.primary_musicbrainz_album_data
        if data is None:
            return None
        if data.cover_art_stored:
            return data.local_cover_art_url(size)
        return data.cover_art_url(size)

    @property
    def credited_artists(self) -> List[Artist]:
        """The credited artists in the order the release lists them.

        ``self.artists.all()`` cannot give that order - an M2M is ordered by
        ``Artist.Meta.ordering`` - so this reads the through rows, which
        ``with_relations()`` prefetches with their artists.
        """
        return [credit.artist for credit in self.credits.all()]


class AlbumCredit(models.Model):
    """An album's credited artist, in the order ``WebRankings.txt`` gives.

    ``variant`` is the index into the artist's ``name_variants`` the release
    credits, and ``credited_name`` that name as of the import: Purple Rain is
    credited to Prince as "Prince and the Revolution". Stored, as
    ``Album.artist_credit`` is, so the credit line and a search by the name
    need no lookup into the artist's list.
    """

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="credits")
    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, related_name="album_credits"
    )
    position = models.PositiveSmallIntegerField(default=0)
    variant = models.PositiveSmallIntegerField(
        default=0, help_text="Index into the artist's name variants; 0 is the name"
    )
    credited_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="The name the album is credited under; blank is the artist's own",
    )

    class Meta:
        db_table = "music_albumcredit"
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["album", "artist"], name="unique_album_credit"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.album_id} #{self.position}: {self.artist_id}"

    @property
    def name(self) -> str:
        """The name to print: the credited one, else the artist's own.

        A credit written by ``album.artists.set()`` or the admin has none.
        """
        return self.credited_name or self.artist.name

    @property
    def uses_variant(self) -> bool:
        """Whether the album credits the artist under another of their names."""
        return self.name != self.artist.name


class MusicPublication(PublicationBase):
    """
    A magazine, site or broadcaster that publishes album rankings.

    Carries ``reputation_score`` like ``games.Publication`` does: the music
    lists come from Rolling Stone, Pitchfork, NME and the like, and the same
    editorial-weighting debate applies. The score is staff-edited and does
    not affect ordering.
    """

    reputation_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Editorial reputation score, staff-edited. Display only.",
    )

    class Meta:
        db_table = "music_musicpublication"
        ordering = ["name"]
        verbose_name = "Music Publication"
        verbose_name_plural = "Music Publications"


class MusicList(ListBase):
    """A published album ranking, e.g. 'The 500 Greatest Albums of All Time'."""

    publisher = models.ForeignKey(
        "MusicPublication",
        null=True,
        blank=True,
        related_name="lists",
        on_delete=models.CASCADE,
    )

    class Meta:
        db_table = "music_musiclist"
        ordering = ["order", "type", "publisher", "year", "name"]
        unique_together = ["publisher", "name", "year"]
        indexes = [models.Index(fields=["type", "year"])]
        verbose_name = "Music List"
        verbose_name_plural = "Music Lists"


class AlbumListMembership(ListMembershipBase):
    """One album's position on one list.

    Unranked lists (a '1001 albums' book, an alphabetical hundred) record
    every member at rank 1, matching the convention the games data uses.
    """

    list = models.ForeignKey(
        "MusicList",
        on_delete=models.CASCADE,
        help_text="The list this album appears on",
    )
    album = models.ForeignKey(
        "Album",
        on_delete=models.CASCADE,
        related_name="lists",
        help_text="The album appearing in the list",
    )

    class Meta:
        db_table = "music_albumlistmembership"
        indexes = [
            models.Index(fields=["list", "rank"]),
            models.Index(fields=["album", "list"]),
        ]
        unique_together = [("list", "album")]
        verbose_name = "Album List Membership"
        verbose_name_plural = "Album List Memberships"

    def __str__(self) -> str:
        return f"{self.list} - {self.album} - {self.rank}"


class ListenedAlbum(UserTrackingBase):
    """Tracks albums a user has marked as listened to.

    Hybrid FK + external id, as ``books.models.ReadBook`` is: the FK is what
    queries join on, and ``wikidata_id`` is what survives an import. An
    import keeps the albums it can match, rows and all, but deletes one the
    release drops; the row then waits on its external id, and
    ``music.services.user_tracking_service`` re-adopts it if the album comes
    back.

    ``owned`` is the "Have" state: an album the user owns a copy of. It is a
    flag on this row rather than a table of its own because owning implies
    having heard, and because the row then inherits the reconnection pass,
    the bulk command and the toggle's atomic write unchanged. The page's
    "Heard" state is therefore a row with ``owned=False``.
    """

    album = models.ForeignKey(
        "Album",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="listened_by",
    )
    wikidata_id = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Wikidata QID, for reconnection after an album reimport",
    )
    owned = models.BooleanField(
        default=False,
        help_text="The user has a copy of this album (shown as 'Have')",
    )

    class Meta:
        db_table = "music_listenedalbum"
        unique_together = [("user", "wikidata_id")]
        indexes = [models.Index(fields=["user", "album"])]
        verbose_name = "Listened Album"
        verbose_name_plural = "Listened Albums"

    def __str__(self) -> str:
        label = self.album.name if self.album else f"Wikidata:{self.wikidata_id}"
        verb = "has" if self.owned else "listened to"
        return f"{self.user.username} {verb} {label}"


class WantToListenAlbum(UserTrackingBase):
    """Tracks albums a user wants to listen to.

    Mutually exclusive with :class:`ListenedAlbum`. The exclusivity is
    enforced by the toggle view rather than by a constraint, as games and
    books also do - the two are separate tables, so no single constraint
    spans them.
    """

    album = models.ForeignKey(
        "Album",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="want_to_listen_by",
    )
    wikidata_id = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Wikidata QID, for reconnection after an album reimport",
    )

    class Meta:
        db_table = "music_wanttolistenalbum"
        unique_together = [("user", "wikidata_id")]
        indexes = [models.Index(fields=["user", "album"])]
        verbose_name = "Want to Listen Album"
        verbose_name_plural = "Want to Listen Albums"

    def __str__(self) -> str:
        label = self.album.name if self.album else f"Wikidata:{self.wikidata_id}"
        return f"{self.user.username} wants to listen to {label}"


class SavedAlbumFilterSet(SavedFilterSetBase):
    """A named album filter combination, saved by one reader.

    Adds nothing to :class:`core.models.SavedFilterSetBase`: the point of a
    concrete model is a table of music's own, so the games and music
    sections neither share rows nor constrain each other's migrations.

    Unlike :class:`ListenedAlbum` this carries no external id and needs no
    reconnection pass after an import. A saved filter references genres by
    id, and an import replaces albums, not genres.
    """

    class Meta(SavedFilterSetBase.Meta):
        db_table = "music_savedalbumfilterset"
        verbose_name = "Saved Album Filter"
        verbose_name_plural = "Saved Album Filters"


class WikipediaAlbumData(ExternalDataBase):
    """
    Supplemental Wikidata/Wikipedia album data.

    Named for consistency with ``WikipediaGameData`` and ``WikipediaBookData``
    even though Wikidata supplies most of it: the enwiki sitelink is what ties
    an album to an article, and everything else rides on the same request.

    Metadata persists when albums are deleted (SET_NULL).
    ``music.services.import_handler.import_albums`` keeps every album it can
    match by Wikidata id, but deletes one the release drops, and without
    SET_NULL its fetched data would go with it rather than wait to be
    re-adopted if it comes back.
    """

    album = models.ForeignKey(
        "Album",
        on_delete=models.SET_NULL,
        related_name="wikipedia_album_data_set",
        null=True,
        blank=True,
    )
    wikidata_id = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,
        help_text="Wikidata entity ID (e.g., 'Q212863')",
    )
    page_title = models.CharField(
        max_length=300, blank=True, db_index=True, help_text="Wikipedia page title"
    )
    release_date = models.DateField(
        null=True, blank=True, help_text="Full release date from Wikidata P577"
    )
    release_date_precision = models.CharField(
        max_length=5,
        blank=True,
        help_text="'day' or 'month' (stored as the 1st); blank if not yet known",
    )
    record_label = models.CharField(
        max_length=300, null=True, blank=True, help_text="Record label (P264)"
    )
    spotify_album_id = models.CharField(
        max_length=50, null=True, blank=True, help_text="Spotify album ID (P2205)"
    )
    primary_genre = models.CharField(max_length=200, null=True, blank=True)
    all_genres = models.TextField(
        null=True,
        blank=True,
        help_text="Comma-separated genre labels from P136, before normalization",
    )

    class Meta:
        db_table = "music_wikipediaalbumdata"
        verbose_name = "Wikipedia Album Data"
        verbose_name_plural = "Wikipedia Album Data"
        indexes = [
            models.Index(fields=["album", "is_primary"]),
            models.Index(fields=["wikidata_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["album"],
                condition=models.Q(is_primary=True) & models.Q(album__isnull=False),
                name="unique_primary_wikipedia_per_album",
            )
        ]

    def __str__(self) -> str:
        if self.album:
            return f"Wikipedia data for {self.album.name}"
        return f"Orphaned Wikipedia data (Wikidata: {self.wikidata_id or 'unknown'})"

    @property
    def wikipedia_url(self) -> Optional[str]:
        """The article URL, or None when no page title was resolved."""
        if self.page_title:
            return f"https://en.wikipedia.org/wiki/{self.page_title.replace(' ', '_')}"
        return None

    @classmethod
    def collapse_duplicates(cls, album, wikidata_id):
        """Reduce (album, wikidata_id) to one row and return it, or None.

        Two albums in the supplied ranking carry two Wikidata IDs each - the
        UK and US editions of 'Let It Bleed' and 'Aftermath' - and alternate
        IDs can resolve to the same article, so nothing stops a second row
        appearing for the same pair. Left alone it becomes a
        ``MultipleObjectsReturned`` that fails that album on every refresh
        from then on, which is the bug ``WikipediaGameData.upsert_for_game``
        exists to prevent on the games side.
        """
        matches = list(
            cls.objects.filter(album=album, wikidata_id=wikidata_id).order_by("id")
        )
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]

        keep = next((match for match in matches if match.is_primary), matches[0])
        extra_pks = [match.pk for match in matches if match.pk != keep.pk]

        # Repoint the album before deleting, so the primary record survives.
        if album.primary_wikipedia_album_data_id in extra_pks:
            album.primary_wikipedia_album_data = keep
            album.save(update_fields=["primary_wikipedia_album_data"])

        cls.objects.filter(pk__in=extra_pks).delete()
        return keep


class DiscogsAlbumData(ExternalDataBase):
    """
    Discogs master-release data: the genre source of record.

    ``genres`` and ``styles`` are stored verbatim rather than only as
    normalized ``MusicGenre`` links, for two reasons: the style-to-root
    mapping can be re-derived without re-fetching 500 masters, and the
    provenance is kept should attribution ever be required.
    """

    album = models.ForeignKey(
        "Album",
        on_delete=models.SET_NULL,
        related_name="discogs_album_data_set",
        null=True,
        blank=True,
    )
    master_id = models.PositiveIntegerField(
        db_index=True, help_text="Discogs master release ID (Wikidata P1954)"
    )
    title = models.CharField(max_length=300, blank=True)
    main_release_year = models.PositiveSmallIntegerField(null=True, blank=True)
    genres = models.JSONField(
        default=list,
        blank=True,
        help_text="Discogs top-level genres, verbatim (e.g. ['Rock', 'Pop'])",
    )
    styles = models.JSONField(
        default=list,
        blank=True,
        help_text="Discogs styles, verbatim (e.g. ['Art Rock', 'Psychedelic Rock'])",
    )

    class Meta:
        db_table = "music_discogsalbumdata"
        verbose_name = "Discogs Album Data"
        verbose_name_plural = "Discogs Album Data"
        indexes = [
            models.Index(fields=["album", "is_primary"]),
            models.Index(fields=["master_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["album"],
                condition=models.Q(is_primary=True) & models.Q(album__isnull=False),
                name="unique_primary_discogs_per_album",
            )
        ]

    def __str__(self) -> str:
        if self.album:
            return f"Discogs data for {self.album.name}"
        return f"Orphaned Discogs data (master: {self.master_id})"

    @property
    def discogs_url(self) -> str:
        return f"https://www.discogs.com/master/{self.master_id}"


class MusicBrainzAlbumData(ExternalDataBase):
    """
    MusicBrainz release-group data, plus the Cover Art Archive provenance.

    The cover art lives here because it is keyed by MusicBrainz identifiers:
    the Cover Art Archive is indexed by release MBID, and only the release
    MBID and image id are stored, since a size is requested by URL. That is
    the same trade ``IGDBGameData.artwork_id`` makes.
    """

    album = models.ForeignKey(
        "Album",
        on_delete=models.SET_NULL,
        related_name="musicbrainz_album_data_set",
        null=True,
        blank=True,
    )
    release_group_mbid = models.CharField(
        max_length=36, db_index=True, help_text="MusicBrainz release-group MBID"
    )
    title = models.CharField(max_length=300, blank=True)
    primary_type = models.CharField(
        max_length=50, blank=True, help_text="Album, Single, EP, Broadcast, Other"
    )
    secondary_types = models.JSONField(
        default=list, blank=True, help_text="Live, Compilation, Soundtrack, ..."
    )
    first_release_date = models.CharField(
        max_length=10,
        blank=True,
        help_text="Partial dates are valid here: '1966', '1966-05', '1966-05-16'",
    )
    rating = models.FloatField(null=True, blank=True)
    rating_votes = models.PositiveIntegerField(null=True, blank=True)
    all_genres = models.TextField(
        null=True,
        blank=True,
        help_text="Comma-separated MusicBrainz genre names, vote-ordered",
    )
    cover_art_release_mbid = models.CharField(
        max_length=36,
        blank=True,
        help_text="Release MBID the Cover Art Archive front image belongs to",
    )
    cover_art_image_id = models.CharField(
        max_length=30, blank=True, help_text="Cover Art Archive image id"
    )
    cover_art_stored = models.BooleanField(
        default=False,
        db_index=True,
        help_text="The image bytes are in AlbumCover, so serve them locally",
    )

    class Meta:
        db_table = "music_musicbrainzalbumdata"
        verbose_name = "MusicBrainz Album Data"
        verbose_name_plural = "MusicBrainz Album Data"
        indexes = [
            models.Index(fields=["album", "is_primary"]),
            models.Index(fields=["release_group_mbid"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["album"],
                condition=models.Q(is_primary=True) & models.Q(album__isnull=False),
                name="unique_primary_musicbrainz_per_album",
            )
        ]

    def __str__(self) -> str:
        if self.album:
            return f"MusicBrainz data for {self.album.name}"
        return f"Orphaned MusicBrainz data ({self.release_group_mbid})"

    @property
    def release_group_url(self) -> str:
        return f"https://musicbrainz.org/release-group/{self.release_group_mbid}"

    def local_cover_art_url(self, size: int) -> Optional[str]:
        """The URL of our own stored copy of the cover.

        Keyed by the Cover Art Archive's own identifiers, which never change
        for a given image, so the response can be cached immutably.
        """
        if not (self.cover_art_release_mbid and self.cover_art_image_id):
            return None
        return site_reverse(
            MUSIC,
            "music:cover",
            kwargs={
                "release_mbid": self.cover_art_release_mbid,
                "image_id": self.cover_art_image_id,
                "size": size,
            },
        )

    def cover_art_url(self, size: Optional[int] = None) -> Optional[str]:
        """The Cover Art Archive URL for the front cover, or None.

        Passing a size returns that thumbnail; passing none returns the full
        image. The request has to go through coverartarchive.org, which
        answers with a 307 to archive.org, so this is the URL to hotlink and
        not the one it redirects to.
        """
        if not (self.cover_art_release_mbid and self.cover_art_image_id):
            return None
        base = (
            f"{config.COVER_ART_ARCHIVE_URL}/release/"
            f"{self.cover_art_release_mbid}/{self.cover_art_image_id}"
        )
        if size is None:
            return f"{base}.jpg"
        return f"{base}-{size}.jpg"


class AlbumCover(models.Model):
    """Our own copy of an album's cover art.

    The Cover Art Archive is the right *source* for album art, but it is the
    wrong thing to hotlink: it answers with a 307 to archive.org, which
    returns an intermittent 500 on images that are perfectly present a moment
    later, and a handful of items are broken outright. A list page showing a
    hundred covers therefore shows several broken ones on every load.

    So the bytes are fetched once and served from here. Rows are keyed by the
    archive's own release MBID, image id and size rather than by album, which
    means they survive an album's deletion and are re-adopted without
    re-downloading if it comes back.
    """

    #: The sizes stored: one for rows, one for the detail page.
    ROW_SIZE = 250
    DETAIL_SIZE = 500
    SIZES = (ROW_SIZE, DETAIL_SIZE)

    album = models.ForeignKey(
        "Album",
        on_delete=models.SET_NULL,
        related_name="covers",
        null=True,
        blank=True,
    )
    release_mbid = models.CharField(max_length=36, db_index=True)
    image_id = models.CharField(max_length=30, db_index=True)
    size = models.PositiveSmallIntegerField()
    data = models.BinaryField()
    content_type = models.CharField(max_length=40, default="image/jpeg")
    byte_size = models.PositiveIntegerField(default=0)
    source_url = models.URLField(blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "music_albumcover"
        verbose_name = "Album Cover"
        verbose_name_plural = "Album Covers"
        indexes = [
            models.Index(fields=["release_mbid", "image_id", "size"]),
            models.Index(fields=["album"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["release_mbid", "image_id", "size"],
                name="unique_cover_per_image_and_size",
            )
        ]

    def __str__(self) -> str:
        return f"Cover {self.image_id} @ {self.size}px ({self.byte_size} bytes)"
