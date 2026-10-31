"""
Music API views.

Public and almost all read-only. ``all/`` is the bulk endpoint feeding the
client-side filtering bundle; there is deliberately no ``version/`` endpoint
beside it, because the album rankings page renders the same data version into
the page itself, so the client can tell a stale copy from a current one
without a second request.

``saved-filters/`` is the exception and the only endpoint here that writes.
It is why there are two mixins below rather than one: CSRF enforcement
now applies to this module, where before no unsafe method existed to trigger
it.
"""

from django.db.models import Count, Max, Min, Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView, Response
from unidecode import unidecode

from core import constants as core_constants
from core.services import genre_tree
from core.services import search_ranking
from core.services.query_params import parse_limit

from .. import config, models
from ..services.credits import (
    album_ids_by_artist,
    artist_summary,
    artists_matching,
    split_by_credit,
    variant_names_by_artist,
    variant_names_of,
)
from ..services.data_version import compute_album_data_version
from . import serializers


class MusicReadAPIMixin:
    """The read-only endpoints, as public as games' API.

    A read needs no permission and never looks at ``request.user``.
    ``SessionAuthentication`` is here for the throttle:
    ``DEFAULT_AUTHENTICATION_CLASSES`` is empty project-wide, so without it
    a DRF view sees every request as anonymous, and ``AnonRateThrottle``'s
    60/minute would apply to signed-in readers too. The saved-filter views
    use :class:`MusicWriteAPIMixin`, which inherits it and cannot see a
    login without it.
    """

    authentication_classes = [SessionAuthentication]


class MusicWriteAPIMixin(MusicReadAPIMixin):
    """The endpoints that write, which want a login.

    Separate from :class:`MusicReadAPIMixin` in name on purpose:
    ``SessionAuthentication`` enforces CSRF on unsafe methods, so every
    caller of a view using this mixin has to send ``X-CSRFToken``, and a
    reader can tell which endpoints that applies to without reading the
    methods.

    A signed-out caller gets ``IsAuthenticated``'s 403, as games' saved
    filters answer.
    """

    permission_classes = [IsAuthenticated]


# Note on caching: these endpoints are uncached, and nothing has measured
# whether they should be. `all/` is the one to look at first: games caches its
# equivalent for an hour.


class AlbumAllDataView(MusicReadAPIMixin, APIView):
    """
    Every album in one payload, for client-side filtering.

    The whole corpus is 1000 albums, which is about 270 KB of JSON and 95 KB
    over the wire, so the client fetches it once and filters in the browser
    instead of making an HTMX round trip per filter change. Field names are
    single letters for the same reason they are in the games and books
    equivalents: at this row count the key names are a real share of the
    payload.

    Artists and genres are sent as lookup tables rather than repeated inline,
    since the renderer has to reproduce the ``artist_links`` template tag and
    the genre filter has to resolve a root genre to its styles. An album
    credited under another of an artist's names carries those names in
    ``"cv"``, beside its ``"ar"`` slugs; the few that need it are cheaper than
    a name per credit on every album.
    """

    def get(self, request):
        albums = (
            models.Album.objects.select_related("primary_musicbrainz_album_data")
            .prefetch_related(models.credits_prefetch(), "genres")
            .with_list_count()
            .order_by("rank")
        )

        # The alphabetical sort ships as a precomputed position rather than
        # being recomputed in the browser. `Lower(name)` orders under the
        # database's collation, and no JavaScript comparator reproduces that
        # for every title: `localeCompare` files "Agaetis byrjun" next to the
        # A's while SQLite sorts it past Z, and punctuation is weighted
        # differently again. Sending the server's own ordering makes the two
        # agree exactly, whatever the collation - and keeps local SQLite
        # behaving like production Postgres.
        name_order = {
            album_id: position
            for position, album_id in enumerate(
                models.Album.objects.order_by(Lower("name")).values_list(
                    "id", flat=True
                )
            )
        }

        albums_data = []
        artists = {}

        for album in albums:
            artist_slugs, credited_names = [], []
            # In credit order, which the renderer's credit line follows.
            for credit in album.credits.all():
                artist = credit.artist
                # By slug, not pk: the pks were handed out in the order the
                # provider entered the artists, which the payload must not show.
                artist_slugs.append(artist.slug)
                credited_names.append(credit.name)
                if artist.slug not in artists:
                    artists[artist.slug] = {"n": artist.name}

            entry = {
                "id": album.id,
                "n": album.name,
                # The server's text search is `name OR name_normalized OR
                # artist_credit`, all three case-insensitive and none of
                # them accent-folded. `name_normalized` is `unidecode(name)`
                # and is stored only when it differs, so it is sent as it
                # is: reimplementing unidecode in the browser would be a
                # second, drifting copy of the rule.
                "nn": album.name_normalized or "",
                "s": album.slug,
                "r": album.rank,
                "y": album.year_released,
                # The release date orders a year's albums. ISO, so the
                # client compares it as a string; null when undated.
                "rd": album.release_date and album.release_date.isoformat(),
                "c": album.artist_credit,  # credit line, names joined
                "t": album.thumbnail,  # 250px cover, local copy preferred
                "ar": artist_slugs,
                "g": [genre.id for genre in album.genres.all()],
                "lc": album.list_count,
                "ni": name_order[album.id],  # alphabetical position
            }
            if credited_names != [artists[slug]["n"] for slug in artist_slugs]:
                entry["cv"] = credited_names  # credited as another name
            if album.various_artists:
                entry["va"] = 1  # the credit ends in "Various Artists"
            albums_data.append(entry)

        # One fetch for the table, one in-memory walk for the descendants.
        # Recursing through `children` instead cost a query per genre, and
        # `values()` keeps the manager's ordering, so "d" comes out exactly
        # as it did - depth first, excluding the genre itself.
        genre_rows = list(
            models.MusicGenre.objects.values("id", "name", "slug", "parent_id", "level")
        )
        descendants = genre_tree.descendants_by_id(
            (row["id"], row["parent_id"]) for row in genre_rows
        )
        genres_data = [
            {
                "id": row["id"],
                "n": row["name"],
                "s": row["slug"],
                "p": row["parent_id"],
                "l": row["level"],
                "d": descendants.get(row["id"], []),
            }
            for row in genre_rows
        ]

        return Response(
            {
                "version": compute_album_data_version(),
                "albums": albums_data,
                "artists": artists,
                "genres": genres_data,
            }
        )


#: The unified search's groups, in the order a tie between them falls.
SEARCH_GROUPS = ("artists", "albums")


class MusicUnifiedSearchView(MusicReadAPIMixin, APIView):
    """Albums and artists in one response, for the sidebar search box.

    The games equivalent (``games.api.views.UnifiedSearchView``) feeds the
    same search box in the same chrome; music had no endpoint at all, which
    is why the sidebar's search input was gated on ``media_type == 'games'``
    and the section had no search anywhere.

    ``order`` names the groups in the order the dropdown shows them: the one
    holding the better match (``core.services.search_ranking``) leads, and
    on a tie the artist, since "The Beatles" names the band and the White
    Album equally well and is after the band. Artists are ordered best match
    first, then by album count; albums by rank, but for an exact title.
    """

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        album_limit = parse_limit(request.query_params.get("album_limit"), 5)
        artist_limit = parse_limit(request.query_params.get("artist_limit"), 3)

        if len(q) < 2:
            return Response({"albums": [], "artists": [], "order": list(SEARCH_GROUPS)})

        # Ranked, with an exact title first, in one bounded query; thumbnail
        # reads the MusicBrainz row, so it is joined, as /api/music/all/ does.
        albums = list(
            search_ranking.exact_first(
                models.Album.objects.filter(
                    Q(name__icontains=q)
                    | Q(name_normalized__icontains=q)
                    | Q(artist_credit__icontains=q)
                ),
                "rank",
                name=q,
                name_normalized=unidecode(q),
            ).select_related("primary_musicbrainz_album_data")[:album_limit]
        )

        # Already most albums first; a stable sort puts the best match above that.
        artists = _artists_with_albums(artists_matching(q), with_variant_names=True)
        artist_scores = {
            artist.id: search_ranking.quality_or(
                q, [artist.name, *artist.variant_names], search_ranking.SUBSTRING
            )
            for artist in artists
        }
        artists.sort(key=lambda artist: artist_scores[artist.id])
        artists = artists[:artist_limit]

        order = search_ranking.group_order(
            {
                "albums": min(
                    (
                        search_ranking.quality_or(
                            q,
                            (album.name, album.name_normalized),
                            search_ranking.INDIRECT,
                        )
                        for album in albums
                    ),
                    default=None,
                ),
                "artists": artist_scores[artists[0].id] if artists else None,
            },
            SEARCH_GROUPS,
        )

        return Response(
            {
                "albums": [
                    {
                        "id": album.id,
                        "name": album.name,
                        "slug": album.slug,
                        "rank": album.rank,
                        "year_released": album.year_released,
                        "artist_credit": album.artist_credit,
                        "thumbnail": album.thumbnail or "",
                    }
                    for album in albums
                ],
                "artists": [
                    {
                        "name": artist.name,
                        "slug": artist.slug,
                        "albums_count": artist.albums_count,
                        "summary": artist_summary(artist.albums_count),
                    }
                    for artist in artists
                ],
                "order": order,
            }
        )


class AlbumListView(MusicReadAPIMixin, ListAPIView):
    """
    List albums with filtering and search.

    Query params: ``q`` (title or credit), ``artist`` (slug), ``genres``
    (comma-separated ids), ``start``/``end`` (release-year range).
    """

    serializer_class = serializers.AlbumSummarySerializer

    def get_queryset(self):
        qs = models.Album.objects.with_relations().with_list_count()
        params = self.request.query_params

        q = params.get("q")
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(artist_credit__icontains=q)

        artist = params.get("artist")
        if artist:
            # Every album credited to them, under whichever of their names.
            qs = qs.filter(artists__slug=artist)

        genres = params.get("genres")
        if genres:
            genre_ids = [x.strip() for x in genres.split(",") if x.strip().isdigit()]
            if genre_ids:
                qs = qs.filter(genres__id__in=genre_ids)

        for param, lookup in (("start", "gte"), ("end", "lte")):
            value = params.get(param)
            if value and value.isdigit():
                qs = qs.filter(**{f"year_released__{lookup}": int(value)})

        return qs.distinct().order_by("rank")


class AlbumDetailView(MusicReadAPIMixin, RetrieveAPIView):
    """One album with its list appearances."""

    serializer_class = serializers.AlbumDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return models.Album.objects.with_relations().with_list_count()


class AlbumSearchAPIView(MusicReadAPIMixin, ListAPIView):
    """Album search, capped at 20 results."""

    serializer_class = serializers.AlbumSummarySerializer
    pagination_class = None

    def get_queryset(self):
        q = self.request.query_params.get("q")
        if not q:
            return models.Album.objects.none()
        qs = models.Album.objects.with_relations()
        return (
            (qs.filter(name__icontains=q) | qs.filter(artist_credit__icontains=q))
            .distinct()
            .order_by("rank")[:20]
        )


def _artists_with_albums(queryset, with_variant_names=False):
    """``queryset``'s artists with a ranked album, most albums first.

    A list with ``albums_count`` set on each artist, and ``variant_names``
    too when asked for: the unified search shows none, but scores a match on
    a credited name ("Revolution" finds Prince) by them.
    """
    album_ids = album_ids_by_artist()
    artists = list(queryset.filter(id__in=list(album_ids)))
    variant_names = (
        variant_names_by_artist([artist.id for artist in artists])
        if with_variant_names
        else {}
    )
    for artist in artists:
        artist.albums_count = len(album_ids[artist.id])
        artist.variant_names = variant_names.get(artist.id, [])
    artists.sort(key=lambda artist: (-artist.albums_count, artist.name.lower()))
    return artists


class ArtistListView(MusicReadAPIMixin, ListAPIView):
    """Artists with at least one ranked album."""

    serializer_class = serializers.ArtistSerializer

    def get_queryset(self):
        q = self.request.query_params.get("q")
        qs = artists_matching(q) if q else models.Artist.objects.all()
        return _artists_with_albums(qs, with_variant_names=True)


class ArtistDetailView(MusicReadAPIMixin, RetrieveAPIView):
    """One artist with every ranked album credited to them."""

    serializer_class = serializers.ArtistDetailSerializer
    lookup_field = "slug"
    queryset = models.Artist.objects.all()

    def get_object(self):
        artist = super().get_object()
        albums = list(
            models.Album.objects.with_relations()
            .with_list_count()
            .filter(artists=artist)
            .order_by("rank")
        )
        artist.own_albums, artist.joint_albums = split_by_credit(albums, artist.id)
        artist.albums_count = len(albums)
        artist.variant_names = variant_names_of(artist.id)
        return artist


class MusicListListView(MusicReadAPIMixin, ListAPIView):
    """The published source lists."""

    serializer_class = serializers.MusicListSerializer

    def get_queryset(self):
        qs = models.MusicList.objects.select_related("publisher").order_by("order")
        list_type = self.request.query_params.get("type")
        if list_type in dict(core_constants.LIST_TYPES):
            qs = qs.filter(type=list_type)
        return qs


class MusicGenreListView(MusicReadAPIMixin, ListAPIView):
    """Every music genre, flat, ordered for tree reassembly."""

    serializer_class = serializers.MusicGenreSerializer
    pagination_class = None

    def get_queryset(self):
        return models.MusicGenre.objects.select_related("parent").order_by(
            "level", "display_order", "name"
        )


class MusicMetaView(MusicReadAPIMixin, APIView):
    """Counts and year distributions for the music database."""

    def get(self, request, *args, **kwargs):
        music_lists = models.MusicList.objects.all()
        bounds = models.Album.objects.aggregate(
            min_year=Min("year_released"), max_year=Max("year_released")
        )

        year_counts = list(
            models.Album.objects.exclude(year_released__isnull=True)
            .values("year_released")
            .annotate(count=Count("id"))
            .order_by("year_released")
        )
        decade_counts = {}
        for entry in year_counts:
            decade = (entry["year_released"] // 10) * 10
            decade_counts[decade] = decade_counts.get(decade, 0) + entry["count"]

        return Response(
            {
                "albums": {
                    "total_count": models.Album.objects.count(),
                    "min_year": bounds["min_year"],
                    "max_year": bounds["max_year"],
                    "years": year_counts,
                    "decades": [
                        {"decade": f"{decade}-{str(decade + 9)[-2:]}", "count": count}
                        for decade, count in sorted(decade_counts.items())
                    ],
                },
                "artists": {"total_count": len(album_ids_by_artist())},
                "lists": {
                    "total_count": music_lists.count(),
                    "by_type": [
                        {
                            "type": code,
                            "label": core_constants.get_list_type_label(code),
                            "count": music_lists.filter(type=code).count(),
                        }
                        for code in core_constants.LIST_TYPE_IMPORTANCE_ORDER
                    ],
                    "years": list(
                        music_lists.values("year")
                        .annotate(count=Count("id"))
                        .order_by("year")
                    ),
                },
                "publications": {
                    "total_count": models.MusicPublication.objects.count()
                },
            }
        )


def _saved_filter_payload(filter_set):
    """One saved filter, in the shape the sidebar's dropdown reads."""
    return {
        "id": filter_set.id,
        "name": filter_set.name,
        "filters": filter_set.filters,
        "modified": filter_set.modified.isoformat(),
    }


def _validate_saved_filter_name(name, user, exclude_pk=None):
    """The name rules, or an error string if the name breaks one.

    Shared by create and rename so the two cannot disagree about the
    ceiling or about what counts as a duplicate - games enforces the same
    three rules twice over, once per method.
    """
    if not name:
        return "Filter name is required."
    if len(name) > config.SAVED_FILTER_NAME_MAX_LENGTH:
        return (
            f"Filter name must be {config.SAVED_FILTER_NAME_MAX_LENGTH} "
            "characters or less."
        )
    duplicates = models.SavedAlbumFilterSet.objects.filter(user=user, name=name)
    if exclude_pk is not None:
        duplicates = duplicates.exclude(pk=exclude_pk)
    if duplicates.exists():
        return "A filter with this name already exists."
    return None


class SavedAlbumFilterSetListCreateView(MusicWriteAPIMixin, APIView):
    """List this reader's saved album filters, or save the current one.

    The cap is ``config.MAX_SAVED_FILTERS`` and is enforced here rather than
    by a constraint, as games' is: it is a courtesy to keep the dropdown
    readable, not an invariant.
    """

    def get(self, request):
        filter_sets = models.SavedAlbumFilterSet.objects.filter(
            user=request.user
        ).order_by("-modified")[: config.MAX_SAVED_FILTERS]
        data = [_saved_filter_payload(entry) for entry in filter_sets]
        return Response({"filter_sets": data, "count": len(data)})

    def post(self, request):
        current_count = models.SavedAlbumFilterSet.objects.filter(
            user=request.user
        ).count()
        if current_count >= config.MAX_SAVED_FILTERS:
            return Response(
                {
                    "error": f"Maximum of {config.MAX_SAVED_FILTERS} saved "
                    "filters allowed. Delete one to save a new filter."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = str(request.data.get("name", "")).strip()
        error = _validate_saved_filter_name(name, request.user)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        filter_set = models.SavedAlbumFilterSet.objects.create(
            user=request.user,
            name=name,
            filters=request.data.get("filters", {}),
        )
        return Response(
            _saved_filter_payload(filter_set), status=status.HTTP_201_CREATED
        )


class SavedAlbumFilterSetDetailView(MusicWriteAPIMixin, APIView):
    """Rename or delete one saved album filter.

    Both methods go through an owner-scoped lookup, so another reader's id
    is a 404 rather than a 403.
    """

    def get_object(self, pk, user):
        return get_object_or_404(models.SavedAlbumFilterSet, pk=pk, user=user)

    def patch(self, request, pk):
        filter_set = self.get_object(pk, request.user)
        name = str(request.data.get("name", "")).strip()
        error = _validate_saved_filter_name(name, request.user, exclude_pk=pk)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        filter_set.name = name
        # `modified` is auto_now, so it has to be named for the update to
        # bump it - and the ordering the dropdown relies on is by `modified`.
        filter_set.save(update_fields=["name", "modified"])
        return Response({"id": filter_set.id, "name": filter_set.name})

    def delete(self, request, pk):
        self.get_object(pk, request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
