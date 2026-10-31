"""
Music views for the multi-media platform.

Every view is public but the import page, which is behind
``core.mixins.StaffOnlyMixin``.

The album list is server-rendered with HTMX filtering and progressively
enhanced by music/static/music/js/, so every variable these templates read is
set here and the page works with or without that bundle.

Presentation is deliberately shared with the games rankings page rather than
reimplemented: the results-header controls, the row and grid card styling and
the filter sidebar components all come from core/, so the two sections look
like one site.
"""

from collections import defaultdict
import csv
import math
import re
from contextlib import ExitStack
from io import TextIOWrapper
from pathlib import Path

from django.conf import settings
from django.db.models import Count, F, Max, Prefetch, Q
from django.db.models.expressions import OrderBy
from django.db.models.functions import Lower
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.http import urlencode
from django.utils.text import slugify
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from core import constants as core_constants
from core.cache_helpers import (
    batched_cache_reads,
    cache_get,
    get_year_bounds,
)
from core.mixins import HTMXPartialMixin, RobustPaginationMixin, StaffOnlyMixin
from core.models import User
from core import sites
from core.services import genre_tree, seo
from core.services.query_params import parse_id_list, parse_int
from music import config, models
from music.forms import MusicImportForm
from music.services import caching, import_handler, landing_pages
from music.services.credits import (
    album_ids_by_artist,
    artists_matching,
    split_by_credit,
    variant_names_by_artist,
    variant_names_of,
)
from core.services import ranking, titles
from games.models import SiteMetadata
from music.templatetags import music_filters
from music.services.data_version import compute_album_data_version
from music.services.listening_stats import total_album_count

# The checked-in release files, offered as the import default so the page is
# usable without hunting for them.
BUNDLED_RELEASE_DIR = (
    Path(settings.BASE_DIR) / "acclaimedgames" / "test_input_files" / "music"
)
BUNDLED_FILES = {
    "artists_file": "ArtistInfo.txt",
    "lists_file": "ListData.txt",
    "albums_file": "WebRankings.txt",
    "positions_file": "ListPositions.txt",
}

# Sorts are declared in their natural ascending form and the direction flips
# only the primary key, so a tiebreaker keeps pointing the same way: albums
# by year descending is newest-first then best-ranked, not newest-first then
# worst-ranked. Declaring a field pre-negated here would make `dir=desc`
# double-negate it.
#
# A primary key may be a tuple of fields that all follow the direction. The
# year sort's is the year and then the release date within it, so "newest
# first" means newest within the year too. The year leads because it is the
# published one every filter and row shows; an album without a date sits at
# the end of its year either way. `AlbumFilterEngine.sort` mirrors this.
RELEASE_ORDER = ("year_released", F("release_date").asc(nulls_last=True))

ALBUM_SORTS = {
    "rank": ("rank",),
    "name": (Lower("name"),),
    "year": (RELEASE_ORDER, "rank"),
    "lists": ("list_count", "rank"),
}

# Which way a sort runs when the URL names no direction. The controls pick
# the same way - a name or a rank reads best-first, a count reads biggest
# first - so a hand-typed ?sort=rank and a click on "Top Rank" agree.
ASCENDING_SORTS = frozenset({"name", "alpha", "order", "rank"})


def default_direction(sort):
    """The direction a sort runs in when the URL does not say."""
    return "asc" if sort in ASCENDING_SORTS else "desc"


# Sort keys for the artist list, which sorts in Python: its counts and best
# ranks come from one read of the credit table rather than a join. Each is
# the primary key only; ties always fall back to the name, ascending.
ARTIST_SORTS = {
    "albums": lambda artist: artist.albums_count,
    # An artist's best album, as the developer list's "Top Rank" sorts by a
    # developer's best game. A lower rank is better, so this one reads
    # "ascending" in the natural sense the other sorts are declared in.
    "rank": lambda artist: artist.best_rank,
    "name": lambda artist: artist.name.lower(),
}


# An artist page's albums. Both read ascending first - best first, oldest
# first - so unlike default_direction() a year here starts at the debut.
ARTIST_ALBUM_SORTS = {
    "rank": ("rank",),
    "year": (RELEASE_ORDER, "rank"),
}


_SLUG_TOKEN = re.compile(r"^[-\w]+$")


def parse_artist_param(raw):
    """``?artists=``'s artist slugs, in the order given, each once.

    Slugs only: the pks were handed out in the order the provider entered
    the artists, and accepting them here would let anyone read that order
    back off the page, one ``?artists=N`` at a time. Nothing public linked
    to the pks before the switch. A slug that names nobody filters to
    nothing, honestly, rather than being dropped into an unfiltered page.
    """
    tokens = (part.strip().lower() for part in (raw or "").split(","))
    return list(dict.fromkeys(token for token in tokens if _SLUG_TOKEN.match(token)))


def _artist_names(raw, artists):
    """``?artists=``'s artists by name, joined: "Prince & Nico"; else ""."""
    if not artists:
        return ""
    names = {artist["slug"]: artist["name"] for artist in artists}
    chosen = [names[slug] for slug in parse_artist_param(raw) if slug in names]
    return titles.join_names(chosen) if chosen else ""


def _filter_title(params, min_year=None, max_year=None, genres=None, artists=None):
    """A natural page title describing the current filter state.

    Composed the way ``games.views._build_filter_title`` composes its own:
    the selected genres fold into the noun phrase, the year range becomes an
    "of ..." suffix, and an artist reads as "by ...". It used to know only
    about the search box and the year range, so filtering by genre left the
    heading saying "Most Acclaimed Albums" and nothing else.

    Deliberately avoids "best"/"top" phrasing, matching the games pages.
    """
    query = params.get("q")
    if query:
        return f"Albums matching \u201c{query}\u201d"

    genre_label = ""
    selected_genres = parse_id_list(params.get("genres"))
    if selected_genres and genres:
        names = {genre["id"]: genre["name"] for genre in genres}
        chosen = [names[genre_id] for genre_id in selected_genres if genre_id in names]
        if chosen:
            genre_label = f" {titles.join_names(chosen)}"

    artist_names = _artist_names(params.get("artists"), artists)
    artist_label = f" by {artist_names}" if artist_names else ""

    start = parse_int(params.get("start"))
    end = parse_int(params.get("end"))
    if min_year is not None and max_year is not None:
        window = titles.build_time_window(
            start if start is not None else min_year,
            end if end is not None else max_year,
            min_year,
            max_year,
        )
    elif start is not None and end is not None:
        window = titles.build_time_window(start, end, start, end)
    else:
        window = ""

    time_suffix = f" of {window}" if window else ""

    # Games appends ": Played" by hand and so handles only one value, which
    # is a latent bug there since the parameter is multi-select. Join them.
    statuses = _parse_status_list(params.get("listened"), config.LISTEN_FILTER_VALUES)
    status_suffix = ""
    if statuses:
        chosen = [
            option["title"]
            for option in config.LISTEN_STATUS_OPTIONS
            if option["value"] in statuses
        ]
        status_suffix = f": {titles.join_names(chosen)}"

    title = (
        f"Most Acclaimed{genre_label} Albums{artist_label}"
        f"{time_suffix}{status_suffix}"
    )
    return " ".join(title.split())


def _tracked_album_ids(user, cache_key, queryset):
    """A user's tracked album ids from ``queryset``, cached briefly.

    Album ids rather than Wikidata ids because these sets are joined against
    the client-side payload, which carries the album pk. Rows orphaned when
    a release dropped their album are left out until the reconnection pass
    re-adopts them - without the FK there is no id to join on.
    """
    return caching.cached(
        cache_key.format(user_id=user.id),
        lambda: list(
            queryset.filter(user=user, album__isnull=False).values_list(
                "album_id", flat=True
            )
        ),
        config.CACHE_TIMEOUT_TRACKING,
    )


def _get_listened_album_ids(user):
    """The album ids this user has heard but does not own."""
    return _tracked_album_ids(
        user,
        config.CACHE_KEY_LISTENED_ALBUMS,
        models.ListenedAlbum.objects.filter(owned=False),
    )


def _get_owned_album_ids(user):
    """The album ids this user has a copy of."""
    return _tracked_album_ids(
        user,
        config.CACHE_KEY_OWNED_ALBUMS,
        models.ListenedAlbum.objects.filter(owned=True),
    )


def _get_want_to_listen_album_ids(user):
    """The album ids this user wants to listen to."""
    return _tracked_album_ids(
        user,
        config.CACHE_KEY_WANT_TO_LISTEN_ALBUMS,
        models.WantToListenAlbum.objects.all(),
    )


def _get_year_bounds():
    """Return the cached global min/max release years."""
    return get_year_bounds(
        model_class=models.Album,
        year_field="year_released",
        cache_key=config.CACHE_KEY_YEAR_STATS,
        cache_timeout=config.CACHE_TIMEOUT_24_HOURS,
        default_min=config.DEFAULT_MIN_YEAR,
        generation_key=config.CACHE_KEY_GENERATION,
    )


def _parse_status_list(raw, allowed):
    """Parse a comma-separated status parameter, dropping unknown values.

    Multi-select, as games' ``played`` is: ``listened=want,no`` asks for the
    backlog and the untracked together. An unrecognised value is ignored
    rather than failing, so a hand-edited URL narrows nothing instead of
    erroring.
    """
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip() in allowed]


def _apply_listen_filter(queryset, user, listened_param):
    """Filter by listen status.

    Requires ``with_listen_status(user)`` to have annotated the queryset.
    Both guards matter: the annotations do not exist for an anonymous user,
    so filtering on them would raise.
    """
    statuses = _parse_status_list(listened_param, config.LISTEN_FILTER_VALUES)
    if not statuses or not user or not user.is_authenticated:
        return queryset

    q_filter = Q()
    for status in statuses:
        if status == "own":
            q_filter |= Q(is_owned_by_user=True)
        elif status == "yes":
            q_filter |= Q(is_listened_by_user=True)
        elif status == "want":
            q_filter |= Q(is_want_to_listen_by_user=True)
        else:  # "no" - in none of the three states
            q_filter |= Q(
                is_owned_by_user=False,
                is_listened_by_user=False,
                is_want_to_listen_by_user=False,
            )
    return queryset.filter(q_filter)


def _apply_sort(queryset, sorts, sort, direction, default):
    """Order a queryset by one of ``sorts``, flipping the primary key."""
    primary, *rest = sorts.get(sort) or sorts[default]
    primary = primary if isinstance(primary, tuple) else (primary,)
    if direction == "desc":
        primary = tuple(_reverse_order(field) for field in primary)
    return queryset.order_by(*primary, *rest)


def _reverse_order(field):
    """Invert a single order_by term, string or expression.

    An explicit ``OrderBy`` keeps its null placement, so an undated album
    stays last whichever way the dates run.
    """
    if isinstance(field, str):
        return field[1:] if field.startswith("-") else f"-{field}"
    if isinstance(field, OrderBy):
        return OrderBy(
            field.expression,
            descending=not field.descending,
            nulls_first=field.nulls_first,
            nulls_last=field.nulls_last,
        )
    return field.desc()


def apply_album_filters(queryset, params, skip=(), user=None, descendants=None):
    """Apply the rankings page's filters to ``queryset``.

    ``skip`` leaves a dimension out, which is how the facet counts beside the
    year cells and the genre rows are worked out: the count under "1975" is
    how many albums that year has under the *other* filters, not how many are
    showing right now. The dimensions are ``q``, ``year``, ``artists``,
    ``genres`` and ``listened``.

    ``user`` is only needed for the ``listened`` dimension, and is last with
    a default so the three-positional call shape stays valid.

    ``descendants`` is an already-built genre descendant map, passed in by a
    caller that filters more than once per request so the table is walked
    once rather than per call. Left out, the genre dimension builds its own.
    """
    q = params.get("q")
    if q and "q" not in skip:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(name_normalized__icontains=q)
            | Q(artist_credit__icontains=q)
        )

    if "year" not in skip:
        start = parse_int(params.get("start"))
        if start is not None:
            queryset = queryset.filter(year_released__gte=start)
        end = parse_int(params.get("end"))
        if end is not None:
            queryset = queryset.filter(year_released__lte=end)

    if "artists" not in skip:
        artist_slugs = parse_artist_param(params.get("artists"))
        if artist_slugs:
            # Prince's credits as Prince and the Revolution are Prince's
            # credits, so a plain join finds every name's records.
            queryset = queryset.filter(artists__slug__in=artist_slugs).distinct()

    if "genres" not in skip:
        genre_ids = parse_id_list(params.get("genres"))
        if genre_ids:
            queryset = queryset.filter(
                genres__id__in=expand_genre_ids(genre_ids, descendants)
            ).distinct()

    if "listened" not in skip:
        queryset = _apply_listen_filter(queryset, user, params.get("listened"))

    return queryset


def _genre_descendant_map():
    """``{genre_id: [descendant ids]}`` for the whole taxonomy, in one query.

    Walking the tree through the ORM instead is what made this page cost 418
    identical ``music_musicgenre`` selects: ``prefetch_related("children")``
    populates the rows it fetched, but recursing into a *child* instance's
    own ``children`` is unprefetched, so it is a query per node visited.
    """
    return genre_tree.fetch_descendants_by_id(models.MusicGenre.objects.all())


def expand_genre_ids(genre_ids, descendants=None):
    """Add every descendant of the selected genres.

    Selecting "Rock" means rock, including the styles filed under it -
    which is what ``games.services.query_filters.apply_genre_filter`` does,
    and what the count beside the row says. Matching the ids literally made
    a root match only the albums tagged with the bare root name, so picking
    Rock dropped almost everything the reader would call rock.

    An id that is not a genre at all stays in the result, as it did when this
    read the table directly: the seed is the selection itself, so an unknown
    id simply matches no album rather than being silently dropped.
    """
    if descendants is None:
        descendants = _genre_descendant_map()
    expanded = set(genre_ids)
    for genre_id in genre_ids:
        expanded.update(descendants.get(genre_id, ()))
    return sorted(expanded)


def _year_counts(queryset, min_year, max_year):
    """Albums per release year, for the year heatmap.

    Every year in the corpus-wide range is present, zeros included, as
    `games.views.HomePageView` builds its own. The grid takes its decade
    structure from this array rather than from `min_year`/`max_year`, so
    returning only the years the current filter happens to cover shrank the
    grid itself: loading `/music/?genres=<something narrow>` left most of
    the timeline with no cells to click, and no way back to it.

    `distinct=True` because the genre and artist filters join through M2M
    tables, so an album matching two genres in the selected subtree would
    otherwise be counted once per match.

    `order_by()` because those filters also call `.distinct()`, and a
    DISTINCT query must select its ordering columns - so `Album`'s default
    `rank` ordering went into the GROUP BY, every album became its own
    group, and under any genre or artist filter every year cell said 1.
    """
    counts = {
        row["year_released"]: row["count"]
        for row in queryset.exclude(year_released__isnull=True)
        .order_by()
        .values("year_released")
        .annotate(count=Count("id", distinct=True))
    }
    return [
        {"year": year, "count": counts.get(year, 0)}
        for year in range(min_year, max_year + 1)
    ]


def _genre_counts(queryset, descendants=None):
    """Albums per genre, counting each genre's whole subtree.

    The number beside a row has to be what selecting that row gives, and
    selecting a root includes its styles. Summing a root and its children
    in the browser (which is what the tree used to do) counts an album
    tagged both "Classical" and "Modern Classical" twice - the page said
    Classical had 2 albums when it had one.

    ``descendants`` is the shared genre map; the key order it iterates in is
    the manager's own, so the counts dict comes out ordered as it always was.
    """
    if descendants is None:
        descendants = _genre_descendant_map()
    pairs = list(queryset.exclude(genres__isnull=True).values_list("id", "genres__id"))
    albums_by_genre = defaultdict(set)
    for album_id, genre_id in pairs:
        albums_by_genre[genre_id].add(album_id)

    counts = {}
    for genre_id, descendant_ids in descendants.items():
        albums = set()
        for subtree_id in (genre_id, *descendant_ids):
            albums |= albums_by_genre.get(subtree_id, set())
        if albums:
            counts[str(genre_id)] = len(albums)
    return counts


def _cached_artist_options():
    """Return the artist filter options: every artist with at least one album."""

    def load():
        album_ids = album_ids_by_artist()
        return [
            {**option, "albums_count": len(album_ids[option["id"]])}
            for option in models.Artist.objects.filter(id__in=list(album_ids))
            .order_by(Lower("name"))
            .values("id", "name", "slug")
        ]

    return caching.cached(
        config.CACHE_KEY_ARTIST_OPTIONS, load, config.CACHE_TIMEOUT_24_HOURS
    )


def _cached_genre_options():
    """Return the genre filter options.

    Empty until the metadata pass populates ``MusicGenre``; the template
    hides the genre filter when there is nothing to show. ``albums_count`` is
    selected explicitly - annotating without naming it in ``values()`` leaves
    the template rendering a blank count.
    """
    return caching.cached(
        config.CACHE_KEY_GENRE_OPTIONS,
        lambda: list(
            models.MusicGenre.objects.annotate(albums_count=Count("albums"))
            .filter(albums_count__gt=0)
            .order_by("level", "display_order", "name")
            .values("id", "name", "slug", "level", "parent_id", "path", "albums_count")
        ),
        config.CACHE_TIMEOUT_24_HOURS,
    )


def genre_tree_options(descendants=None):
    """The genre options shaped for ``core/includes/_genre_filter.html``.

    The shared tree reads ``level``, ``parent_id`` and a count; it prefers
    ``filtered_count`` when one has been pushed in, and falls back to
    ``item_count`` - the equivalent of games' ``game_count``.
    """
    subtree_counts = _genre_counts(models.Album.objects.all(), descendants)
    return [
        {
            "id": option["id"],
            "name": option["name"],
            "slug": option["slug"],
            "level": option["level"],
            "parent_id": option["parent_id"],
            # The subtree count, for the same reason _genre_counts uses one.
            "item_count": subtree_counts.get(str(option["id"]), 0),
        }
        for option in _cached_genre_options()
    ]


def group_genre_options(options):
    """Group flat genre options under their root, for <optgroup>.

    The taxonomy is two levels - a root genre and the vocabulary's leaves
    beneath it - which is more than a flat list of names can present
    usefully. Roots keep the order ``genre_normalizer.GENRE_HIERARCHY`` sets,
    which the query's ``display_order`` already reflects.

    A root is offered as a selectable option of its own as well as a group
    label, because filtering on "all of Rock" is the most useful thing a
    reader can ask for.
    """
    by_id = {option["id"]: option for option in options}
    groups = []
    group_index = {}

    for option in options:
        root = option
        # Walk up to the root; the tree is two deep, so this is one step.
        while root.get("parent_id") and root["parent_id"] in by_id:
            root = by_id[root["parent_id"]]

        if root["id"] not in group_index:
            group_index[root["id"]] = {"root": root, "options": []}
            groups.append(group_index[root["id"]])
        group_index[root["id"]]["options"].append(option)

    for group in groups:
        group["options"].sort(key=lambda item: (item["level"], item["name"]))

    return groups


def _cached_year_baseline(min_year, max_year):
    """Every album per release year: the year heatmap's colour scale.

    Stored with the bounds it spans and rebuilt when they move: the bounds
    are cached apart (`_get_year_bounds`), and a baseline missing a decade
    they include would leave that decade with no cells to click.
    """
    cached = cache_get(config.CACHE_KEY_YEAR_BASELINE)
    if cached is not None and cached["bounds"] == [min_year, max_year]:
        return cached["counts"]
    generation = caching.current_generation()
    counts = _year_counts(models.Album.objects.all(), min_year, max_year)
    caching.set_if_current(
        config.CACHE_KEY_YEAR_BASELINE,
        {"bounds": [min_year, max_year], "counts": counts},
        config.CACHE_TIMEOUT_24_HOURS,
        generation,
    )
    return counts


def _cached_hero_stats():
    """Return the counts shown in the page heading."""
    return caching.cached(
        config.CACHE_KEY_HERO_STATS,
        lambda: {
            "album_count": models.Album.objects.count(),
            "artist_count": len(album_ids_by_artist()),
            "list_count": models.MusicList.objects.count(),
            "publication_count": models.MusicPublication.objects.count(),
        },
        config.CACHE_TIMEOUT_24_HOURS,
    )


def group_list_appearances(memberships):
    """Group an album's list appearances by list type, most important first.

    Labels come from ``core.constants`` so they match the codes actually
    stored on the list, and the group order follows
    ``LIST_TYPE_IMPORTANCE_ORDER`` rather than a hand-kept list of strings.
    """
    grouped = defaultdict(list)
    for membership in memberships:
        source = membership.list
        grouped[source.type].append(
            {
                "id": source.id,
                "name": source.name,
                "publication": source.publisher.name if source.publisher else "",
                "publisher": source.publisher,
                "type": source.type,
                "type_name": core_constants.get_list_type_label(source.type),
                "url": source.url,
                "year": source.year,
                "rank": membership.rank,
            }
        )

    return [
        (core_constants.get_list_type_label(code), grouped[code])
        for code in core_constants.LIST_TYPE_IMPORTANCE_ORDER
        if code in grouped
    ]


class AlbumHomePageView(RobustPaginationMixin, ListView):
    """
    The album rankings page, with search, filtering and HTMX updates.

    Supports text search across title and published credit, a release-year
    range, artist and genre filters, and four sorts in either direction.
    """

    model = models.Album
    template_name = "music/home.html"
    context_object_name = "albums"
    paginate_by = config.DEFAULT_PAGE_SIZE
    paginate_orphans = 0

    def _is_partial_request(self):
        """Whether this request wants a fragment rather than the whole page."""
        return bool(
            self.request.headers.get("HX-Request")
            or self.request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or self.request.GET.get("partial") == "true"
        )

    def _is_full_page(self):
        """Neither a swap nor a Load More page: only this draws the year grid."""
        return (
            not self._is_partial_request() and self.request.GET.get("append") != "true"
        )

    @cached_property
    def _descendants(self):
        """The genre descendant map, built once for the whole request.

        ``get_queryset`` runs before ``get_context_data`` under ``ListView``
        and both filter, so this cannot be a local in either one: the three
        consumers between them would each walk the table.
        """
        return _genre_descendant_map()

    def get(self, request, *args, **kwargs):
        # Every cached value the page reads, in one shared-cache round trip.
        with batched_cache_reads(self._prefetch_cache_keys()):
            return self.render_rankings(request, *args, **kwargs)

    def render_rankings(self, request, *args, **kwargs):
        """The page itself, inside the batch; landing pages add their filters."""
        return super().get(request, *args, **kwargs)

    def _prefetch_cache_keys(self):
        """Every shared-cache key the page reads before it renders."""
        keys = [
            config.CACHE_KEY_GENERATION,
            config.CACHE_KEY_YEAR_STATS,
            config.CACHE_KEY_ARTIST_OPTIONS,
            config.CACHE_KEY_GENRE_OPTIONS,
            config.CACHE_KEY_HERO_STATS,
        ]
        if self._is_full_page():
            keys.append(config.CACHE_KEY_YEAR_BASELINE)
        if self.request.user.is_authenticated:
            keys += [
                template.format(user_id=self.request.user.id)
                for template in config.PER_USER_CACHE_KEY_TEMPLATES
            ]
        return keys

    def get_template_names(self):
        """Serve the right fragment for HTMX, the full page otherwise."""
        if self.request.GET.get("append") == "true":
            return ["music/includes/_album_list_append.html"]

        is_htmx = self._is_partial_request()
        if is_htmx:
            if self.request.headers.get("HX-Target") == "album-results-container":
                return ["music/includes/_album_list_results.html"]
            return ["music/includes/_album_list_content.html"]
        return super().get_template_names()

    def get_queryset(self):
        qs = apply_album_filters(
            models.Album.objects.with_relations()
            .with_list_count()
            .with_listen_status(self.request.user),
            self.request.GET,
            user=self.request.user,
            descendants=self._descendants,
        )
        return _apply_sort(
            qs,
            ALBUM_SORTS,
            self.request.GET.get("sort", "rank"),
            self.request.GET.get("dir", "asc"),
            default="rank",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        min_year, max_year = _get_year_bounds()
        context["min_year"] = min_year
        context["max_year"] = max_year
        # The artist filter is not in the sidebar: two thirds of artists have
        # a single album, so a 337-entry dropdown was mostly one-row filters,
        # and the search box already matches the published credit. The
        # parameter still works for deep links, and a row's credit links to
        # the artist's own page.
        context["artists"] = _cached_artist_options()
        genres = _cached_genre_options()
        context["genres"] = genres
        context["genre_groups"] = group_genre_options(genres)
        context["genre_tree"] = genre_tree_options(self._descendants)
        context["genre_category_icons"] = music_filters.MUSIC_GENRE_CATEGORY_ICONS
        context["default_genre_icon"] = music_filters.DEFAULT_GENRE_ICON
        context.update(_cached_hero_stats())

        # Facet counts for the shared year grid and genre tree. Each is
        # counted with its own dimension left out, so a year cell says how
        # many albums that year would give under the other filters.
        # `listened` is deliberately not skipped in either pass: a year
        # cell should count what the status filter leaves, the way games'
        # client-side facet pass gates its year counts on passesPlayed.
        base = models.Album.objects.with_listen_status(self.request.user)
        context["year_counts"] = _year_counts(
            apply_album_filters(
                base,
                self.request.GET,
                skip=("year",),
                user=self.request.user,
                descendants=self._descendants,
            ),
            min_year,
            max_year,
        )
        # The grid's colour scale is the whole corpus, as games' is. Scaled
        # to the counts of a page loaded filtered (`?listened=no`), clearing
        # the filter asked for opacities over 100%, and only the filtered
        # years stayed coloured. Sent only when it differs from the counts
        # above, which the grid falls back to, and only with the grid: an
        # HTMX swap or a Load More page renders none.
        if self._is_full_page():
            baseline = _cached_year_baseline(min_year, max_year)
            if baseline != context["year_counts"]:
                context["year_baseline_counts"] = baseline
        context["genre_counts"] = _genre_counts(
            apply_album_filters(
                base,
                self.request.GET,
                skip=("genres",),
                user=self.request.user,
                descendants=self._descendants,
            ),
            self._descendants,
        )

        # Where the filtered albums sit across the whole ranking, binned
        # against the global maximum so the shape is comparable between
        # filters - the chart the games rankings page shows beside its own
        # heading.
        max_rank = models.Album.objects.aggregate(top=Max("rank"))["top"] or 0
        context["max_rank"] = max_rank
        context["rank_distribution"] = ranking.rank_distribution(
            self.get_queryset()
            .filter(rank__gte=1, rank__lte=max_rank)
            .order_by()
            .values_list("rank", flat=True),
            max_rank,
            config.RANK_DISTRIBUTION_BIN_COUNT,
        )
        context["rank_distribution_bin_count"] = config.RANK_DISTRIBUTION_BIN_COUNT

        page_obj = context.get("page_obj")
        total_count = page_obj.paginator.count if page_obj else 0
        loaded_count = page_obj.end_index() if page_obj and total_count else 0
        context["total_count"] = total_count
        context["loaded_count"] = loaded_count
        context["remaining_count"] = total_count - loaded_count
        context["has_more"] = bool(page_obj and page_obj.has_next())
        context["next_page"] = (
            page_obj.next_page_number() if context["has_more"] else None
        )

        # Echo the filter state back so the controls stay in sync after a swap.
        context["current_q"] = self.request.GET.get("q", "")
        context["current_start"] = self.request.GET.get("start", "")
        context["current_end"] = self.request.GET.get("end", "")
        # Carried by the form, so the filter survives the next change.
        context["current_artists"] = ",".join(
            parse_artist_param(self.request.GET.get("artists"))
        )
        context["current_genres"] = self.request.GET.get("genres", "")
        context["current_listened"] = self.request.GET.get("listened", "")
        context["listen_status_options"] = config.LISTEN_STATUS_OPTIONS
        # The saved-filter cap, for the sidebar's and the sheet's limit
        # labels. Rendered rather than hard-coded in either, so the two
        # cannot come to state different ceilings.
        context["max_saved_filters"] = config.MAX_SAVED_FILTERS
        context["current_sort"] = self.request.GET.get("sort", "rank")
        context["current_dir"] = self.request.GET.get("dir", "asc")
        # The artists as parsed, so a value that names nothing a slug could
        # does not leave a page "filtered" that the client calls all-time.
        context["is_filtered"] = bool(context["current_artists"]) or any(
            self.request.GET.get(param)
            for param in ("q", "start", "end", "genres", "listened")
        )
        context["filter_title"] = _filter_title(
            self.request.GET,
            min_year=min_year,
            max_year=max_year,
            genres=genres,
            artists=context["artists"],
        )
        # What the heading says of them, for the client to keep saying it
        # once it composes the heading itself.
        context["current_artist_label"] = _artist_names(
            self.request.GET.get("artists"), context["artists"]
        )

        # The state the shared Alpine filter component starts from. Years
        # default to the full range, which is how the grid spells "no year
        # filter"; the view spells it as absent parameters.
        context["filters"] = {
            "q": context["current_q"],
            "start": parse_int(self.request.GET.get("start")) or min_year,
            "end": parse_int(self.request.GET.get("end")) or max_year,
            "genres": [
                str(genre_id)
                for genre_id in parse_id_list(self.request.GET.get("genres"))
            ],
            "listened": _parse_status_list(
                self.request.GET.get("listened"), config.LISTEN_FILTER_VALUES
            ),
            "sort": context["current_sort"],
            "sortDirection": context["current_dir"],
        }
        context["show_rank"] = "filtered" if context["is_filtered"] else "alltime"
        context["highlight"] = parse_int(self.request.GET.get("highlight"))
        context["query_string"] = self._filter_query_string()

        # Client-side filtering. The bundle and the <template> elements it
        # clones are both gated on this flag, and the version lets a client
        # holding a copy of the bulk payload tell whether it is still current
        # without asking - which is why there is no `version/` endpoint.
        context["enable_client_filtering"] = True
        context["album_data_version"] = compute_album_data_version()

        # Tracking state is rendered into the page per request, never into
        # the bulk payload: that payload is held in sessionStorage keyed only
        # on album_data_version, so two users sharing a browser session share
        # it. Games does the same for the same reason.
        if self.request.user.is_authenticated:
            context["listened_album_ids"] = _get_listened_album_ids(self.request.user)
            context["owned_album_ids"] = _get_owned_album_ids(self.request.user)
            context["want_to_listen_album_ids"] = _get_want_to_listen_album_ids(
                self.request.user
            )

        # Sorts for the shared results-header controls
        # (core/includes/_media_list_controls.html), the same partial the
        # games rankings page renders.
        context["sort_options"] = config.SORT_OPTIONS
        context["quick_mark_options"] = config.QUICK_MARK_OPTIONS
        # Out-of-band updates belong in a swap response, not in a full page.
        context["is_partial_response"] = self._is_partial_request()
        context["last_update"] = SiteMetadata.get_instance(
            config.SITE_METADATA_KEY
        ).last_full_update

        return context

    def _filter_query_string(self):
        """The current filter params, minus page, for load-more links."""
        params = self.request.GET.copy()
        params.pop("page", None)
        params.pop("append", None)
        return params.urlencode()


class MusicLandingPageView(AlbumHomePageView):
    """The album rankings page at a crawlable, self-canonical URL.

    The genre or decade in the path becomes the equivalent filter params,
    injected into ``request.GET`` before the rankings machinery runs, so the
    filter UI, Load More and client-side filtering all work unchanged - as
    ``games.views.SeoRankingPageView`` does. A param the request names
    itself wins over the path's.

    The injection happens in ``render_rankings()``, not ``setup()`` as games
    does it, so that ``get()``'s ``batched_cache_reads`` covers it.
    """

    def get_page_seo(self):
        """Return ``{"params", "meta_description"}`` for this URL, or 404."""
        raise NotImplementedError

    def _prefetch_cache_keys(self):
        # Each subclass names the landing list `get_page_seo` resolves the
        # path against; none is an AttributeError, not a silent extra read
        return [*super()._prefetch_cache_keys(), self.landing_cache_key]

    def render_rankings(self, request, *args, **kwargs):
        self.seo = self.get_page_seo()
        params = request.GET.copy()
        for key, value in self.seo["params"].items():
            if key not in params:
                params[key] = value
        request.GET = params
        return super().render_rankings(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # The natural filter title doubles as the page title, so the landing
        # page and the same filters chosen by hand read identically.
        context["seo_title"] = context["filter_title"]
        context["seo_meta_description"] = self.seo["meta_description"]
        context["itemlist_json"] = seo.itemlist_json(
            context["filter_title"],
            (
                (album.name, album.get_absolute_url())
                for album in list(context["albums"])[: landing_pages.TOP_N]
            ),
            sites.MUSIC,
        )
        # The client pushes every filter change to /music/?..., so history
        # entries that land back on this path carry no query string; these
        # say what that bare path means.
        context["landing_path"] = self.request.path
        context["landing_search"] = urlencode(self.seo["params"])
        return context


class GenreLandingView(MusicLandingPageView):
    """A root genre's rankings at /music/genres/<slug>/."""

    landing_cache_key = config.CACHE_KEY_LANDING_GENRES

    def get_page_seo(self):
        entry = landing_pages.resolve_genre_slug(self.kwargs["slug"])
        if entry is None:
            raise Http404("No landing page for this genre")
        list_count = _cached_hero_stats()["list_count"]
        return {
            "params": {"genres": str(entry["id"])},
            "meta_description": (
                f"The most critically acclaimed {entry['name']} albums of all "
                f"time, ranked by aggregating {list_count} critic lists. "
                f"Explore {entry['album_count']} acclaimed albums."
            ),
        }


class DecadeLandingView(MusicLandingPageView):
    """A decade's rankings at /music/<decade>s/."""

    landing_cache_key = config.CACHE_KEY_LANDING_DECADES

    def get_page_seo(self):
        decade = int(self.kwargs["decade"])
        if decade not in landing_pages.get_landing_decades():
            raise Http404("No landing page for this decade")
        list_count = _cached_hero_stats()["list_count"]
        return {
            "params": {"start": str(decade), "end": str(decade + 9)},
            "meta_description": (
                f"The most critically acclaimed albums of the {decade}s, "
                f"ranked by critic consensus across {list_count} published "
                f"lists."
            ),
        }


class MusicBrowseIndexView(TemplateView):
    """Index of every music landing page, reached from the sitemap only."""

    template_name = "music/landing/browse.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["genre_pages"] = [
            {
                "label": f"{genre['name']} Albums",
                "url": reverse("music:by-genre", kwargs={"slug": genre["slug"]}),
            }
            for genre in landing_pages.get_landing_genres()
        ]
        context["decade_pages"] = [
            {
                "label": f"Albums of the {decade}s",
                "url": reverse("music:by-decade", kwargs={"decade": decade}),
            }
            for decade in landing_pages.get_landing_decades()
        ]
        context.update(_cached_hero_stats())
        return context


class AlbumDownloadView(View):
    """The current filter state as a CSV, as the games sidebar offers.

    Same filters as the rankings page, so the file is exactly what the
    reader is looking at - the filename is the heading, slugified, which is
    how ``games.views.download_games_csv`` names its own.
    """

    def get(self, request, *args, **kwargs):
        min_year, max_year = _get_year_bounds()
        albums = _apply_sort(
            apply_album_filters(
                models.Album.objects.with_relations()
                .with_list_count()
                .with_listen_status(request.user),
                request.GET,
                user=request.user,
            ),
            ALBUM_SORTS,
            request.GET.get("sort", "rank"),
            request.GET.get("dir", "asc"),
            default="rank",
        )

        title = _filter_title(
            request.GET,
            min_year=min_year,
            max_year=max_year,
            genres=_cached_genre_options(),
            artists=_cached_artist_options(),
        )
        filename = f"{slugify(title) or 'acclaimed-albums'}.csv"

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Filtered Rank",
                "Global Rank",
                "Name",
                "Year",
                "Artist",
                "Genres",
                "Lists",
            ]
        )
        for index, album in enumerate(albums, start=1):
            writer.writerow(
                [
                    index,
                    album.rank,
                    album.name,
                    album.year_released or "",
                    album.artist_credit,
                    ", ".join(genre.name for genre in album.genres.all()),
                    album.list_count,
                ]
            )
        return response


class ToggleListenedAlbumView(LoginRequiredMixin, View):
    """Set an album's listen status, answering with the re-rendered button.

    ``?status=none|want|listened|own`` sets a status directly. ``own`` and
    ``listened`` are the same ``ListenedAlbum`` row with ``owned`` set or
    cleared, so moving between Have and Heard keeps the row's ``created``.
    Games also carries a legacy cycle for a bare POST; the dropdown here only
    ever sets a status outright, so a cycle would be a second code path
    nothing reaches.

    A signed-out visitor gets ``LoginRequiredMixin``'s redirect, as games'
    toggle does.

    Two things games and books both get wrong here are fixed. The delete and
    the write run in one transaction, so a failure between them cannot leave
    a user who was tracking the album tracking nothing. And the write is an
    ``update_or_create`` keyed on the ``unique_together``, so a double-click
    cannot race into an IntegrityError - and a row orphaned by a reimport is
    re-adopted on the spot rather than waiting for the next import's pass.
    """

    def post(self, request, album_id):
        album = get_object_or_404(models.Album, pk=album_id)
        target = request.GET.get("status")
        if not album.wikidata_id or target not in config.LISTEN_TOGGLE_STATUSES:
            return HttpResponseBadRequest("Unknown status")

        key = {"user": request.user, "wikidata_id": album.wikidata_id}
        with transaction.atomic():
            # One user's toggles run one at a time, as games' do: otherwise
            # a Heard and a Want sent together each delete the other table
            # before the other's insert is visible, and both rows survive.
            User.objects.select_for_update().filter(pk=request.user.pk).first()
            if target in ("listened", "own"):
                models.WantToListenAlbum.objects.filter(**key).delete()
                models.ListenedAlbum.objects.update_or_create(
                    **key, defaults={"album": album, "owned": target == "own"}
                )
            elif target == "want":
                models.ListenedAlbum.objects.filter(**key).delete()
                models.WantToListenAlbum.objects.update_or_create(
                    **key, defaults={"album": album}
                )
            else:
                models.ListenedAlbum.objects.filter(**key).delete()
                models.WantToListenAlbum.objects.filter(**key).delete()

        caching.invalidate_listen_caches([request.user.id])

        response = render(
            request,
            "music/includes/_listen_button.html",
            {
                "album": album,
                "is_owned": target == "own",
                "is_tracked": target == "listened",
                "is_wanted": target == "want",
                "size": request.GET.get("size"),
                "just_toggled": True,
            },
        )
        # A button swap is not navigation.
        response["HX-Push-Url"] = "false"
        return response


class AlbumDetailView(DetailView):
    """One album, with every list it appears on grouped by list type."""

    model = models.Album
    template_name = "music/album_detail.html"
    context_object_name = "album"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return models.Album.objects.prefetch_related(
            # The credit line, and the properties row naming the artists
            # behind a credited name.
            models.credits_prefetch(),
            "genres",
            Prefetch(
                "lists",
                queryset=models.AlbumListMembership.objects.select_related(
                    "list__publisher"
                ).order_by(
                    "-list__year",
                    "list__publisher__name",
                    "list__name",
                    "rank",
                ),
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        album = context["album"]
        context["grouped_lists"] = group_list_appearances(album.lists.all())
        context["list_appearance_count"] = len(album.lists.all())

        context["total_album_count"] = total_album_count()

        # "N of M" beside the decade and year ranks, as the game detail page
        # shows beside its own. Without them a rank reads as a bare number.
        if album.decade is not None:
            context["decade_album_count"] = models.Album.objects.filter(
                year_released__gte=album.decade, year_released__lte=album.decade + 9
            ).count()
        if album.year_released is not None:
            context["year_album_count"] = models.Album.objects.filter(
                year_released=album.year_released
            ).count()

        if self.request.user.is_authenticated:
            owned = (
                models.ListenedAlbum.objects.filter(user=self.request.user, album=album)
                .values_list("owned", flat=True)
                .first()
            )
            context["is_owned"] = owned is True
            context["is_listened"] = owned is False
            context["is_want_to_listen"] = models.WantToListenAlbum.objects.filter(
                user=self.request.user, album=album
            ).exists()

        credits = album.credits.all()
        # Purple Rain is credited as "Prince and the Revolution"; the
        # properties table then names the artist the link leads to, Prince.
        context["credits_use_variants"] = any(credit.uses_variant for credit in credits)
        credited = [credit.artist for credit in credits]
        if credited:
            # "More by" names the credited artists by their own names and
            # lists everything credited to them, under any name.
            context["more_by_artists"] = credited
            context["related_albums"] = (
                models.Album.objects.filter(artists__in=credited)
                .exclude(id=album.id)
                .distinct()
                .with_relations()
                .with_listen_status(self.request.user)
                .order_by("rank")[:10]
            )

        return context


class ArtistListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    """Artists that have at least one ranked album, with search and sorting."""

    model = models.Artist
    template_name = "music/artists/artist_list.html"
    context_object_name = "artists"
    paginate_by = config.DEFAULT_PAGE_SIZE
    paginate_orphans = 0
    htmx_partial_template = "music/artists/includes/_artist_list_results.html"

    def get_template_names(self):
        if self.request.GET.get("append") == "true":
            return ["music/artists/includes/_artist_list_append.html"]
        return super().get_template_names()

    def get_queryset(self):
        """Every artist with a ranked album, sorted in Python.

        About six hundred artists; one read of the credit table gives every
        count and best rank, which costs less than the joins a SQL sort
        would need. A search matches every name an album credits the artist
        under too, so "Revolution" finds Prince, and each row shows those
        names.
        """
        album_ids = album_ids_by_artist()
        album_ranks = dict(models.Album.objects.values_list("id", "rank"))
        variant_names = variant_names_by_artist()

        q = self.request.GET.get("q")
        qs = (artists_matching(q) if q else models.Artist.objects).filter(
            id__in=list(album_ids)
        )

        artists = []
        best_album_ids = {}
        for artist in qs:
            ids = album_ids[artist.id]
            artist.albums_count = len(ids)
            artist.variant_names = variant_names.get(artist.id, [])
            best_album_ids[artist.id] = min(ids, key=album_ranks.__getitem__)
            artist.best_rank = album_ranks[best_album_ids[artist.id]]
            artists.append(artist)

        # Both row halves show the top album and the desktop one its cover,
        # which goes through `primary_musicbrainz_album_data`: one query for
        # every artist's, rather than three per artist.
        top_albums = models.Album.objects.select_related(
            "primary_musicbrainz_album_data"
        ).in_bulk(set(best_album_ids.values()))
        for artist in artists:
            artist.top_album = top_albums[best_album_ids[artist.id]]

        sort = self.request.GET.get("sort", "albums")
        if sort not in ARTIST_SORTS:
            sort = "albums"
        direction = self.request.GET.get("dir") or default_direction(sort)
        # Two stable passes: the name tiebreaker first, then the primary key
        # in the requested direction, which leaves ties in name order.
        artists.sort(key=ARTIST_SORTS["name"])
        if sort != "name" or direction == "desc":
            artists.sort(key=ARTIST_SORTS[sort], reverse=direction == "desc")
        return artists

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_q"] = self.request.GET.get("q", "")
        context["current_sort"] = self.request.GET.get("sort", "albums")
        context["current_dir"] = self.request.GET.get("dir") or default_direction(
            context["current_sort"]
        )
        context["sort_options"] = config.ARTIST_SORT_OPTIONS

        page_obj = context.get("page_obj")
        total_count = page_obj.paginator.count if page_obj else 0
        context["total_count"] = total_count
        context["loaded_count"] = (
            page_obj.end_index() if page_obj and total_count else 0
        )
        context["has_more"] = bool(page_obj and page_obj.has_next())
        context["next_page"] = (
            page_obj.next_page_number() if context["has_more"] else None
        )
        return context


class ArtistDetailView(HTMXPartialMixin, DetailView):
    """One artist, with their ranked albums and any subsidiary acts."""

    model = models.Artist
    template_name = "music/artists/artist_detail.html"
    htmx_partial_template = "music/artists/includes/_artist_album_results.html"
    context_object_name = "artist"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        sort = self.request.GET.get("sort")
        self.album_sort = sort if sort in ARTIST_ALBUM_SORTS else "rank"
        self.album_dir = "desc" if self.request.GET.get("dir") == "desc" else "asc"
        return models.Artist.objects.all()

    def _albums(self, album_ids, sort="rank", direction="asc"):
        return list(
            _apply_sort(
                models.Album.objects.filter(id__in=album_ids)
                .with_relations()
                .with_list_count()
                .with_listen_status(self.request.user),
                ARTIST_ALBUM_SORTS,
                sort,
                direction,
                default="rank",
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        artist = context["artist"]
        # Every album credited to them, under whichever of their names.
        albums = self._albums(
            artist.album_credits.values("album_id"), self.album_sort, self.album_dir
        )
        # Solo and joint credits apart, as the provider asked; both count,
        # and the chart covers both.
        context["artist_albums"], context["joint_albums"] = split_by_credit(
            albums, artist.id
        )
        context["albums_count"] = len(albums)
        context["also_credited_as"] = variant_names_of(artist.id)
        # The best album whatever order the rows are in.
        context["best_album"] = min(albums, key=lambda a: a.rank, default=None)
        context["current_sort"] = self.album_sort
        context["current_dir"] = self.album_dir
        context["sort_options"] = config.ARTIST_ALBUM_SORT_OPTIONS
        context["show_album_sort"] = len(albums) >= config.ARTIST_ALBUM_SORT_MIN_ALBUMS

        # Where this artist's albums sit across the whole ranking, the chart
        # the developer detail page shows for a developer's games.
        max_rank = models.Album.objects.aggregate(top=Max("rank"))["top"] or 0
        context["max_rank"] = max_rank
        context["rank_distribution"] = ranking.rank_distribution(
            [album.rank for album in albums],
            max_rank,
            config.RANK_DISTRIBUTION_BIN_COUNT,
        )
        context["rank_distribution_bin_count"] = config.RANK_DISTRIBUTION_BIN_COUNT
        return context


class AlbumSearchView(ListView):
    """HTMX search results for the album search box."""

    model = models.Album
    template_name = "music/includes/_album_search_results.html"
    context_object_name = "albums"
    paginate_by = 20

    def get_queryset(self):
        q = self.request.GET.get("q")
        if not q:
            return models.Album.objects.none()
        return (
            models.Album.objects.with_relations()
            .filter(
                Q(name__icontains=q)
                | Q(name_normalized__icontains=q)
                | Q(artist_credit__icontains=q)
            )
            .order_by("rank")[:20]
        )


def group_lists_by_publication(music_lists):
    """Group source lists under their publication, with per-type counts.

    The shape ``core/includes/_publication_group.html`` renders, which is how
    the games source-lists page presents the same data. A publication with a
    dozen lists reads as one row that opens, not as a dozen loose cards.
    """
    groups = []
    index = {}
    type_fields = {
        core_constants.LIST_ALLTIME: "alltime_count",
        core_constants.LIST_DECADE: "decade_count",
        core_constants.LIST_MISC: "misc_count",
        core_constants.LIST_EOY: "eoy_count",
    }

    for source in music_lists:
        key = source.publisher_id
        if key not in index:
            index[key] = {
                "publication": source.publisher,
                "lists": [],
                "alltime_count": 0,
                "decade_count": 0,
                "misc_count": 0,
                "eoy_count": 0,
                "total_count": 0,
            }
            groups.append(index[key])
        group = index[key]
        group["lists"].append(source)
        group["total_count"] += 1
        field = type_fields.get(source.type)
        if field:
            group[field] += 1

    return groups


# How much a list type is worth when ordering publications by importance,
# matching games' weighting: an all-time list says more about a publication
# than a year-end one.
PUBLICATION_IMPORTANCE_WEIGHTS = {
    core_constants.LIST_ALLTIME: 1000,
    core_constants.LIST_DECADE: 100,
    core_constants.LIST_MISC: 10,
    core_constants.LIST_EOY: 1,
}


def _publication_importance(group):
    """A publication's weight, for the default ordering."""
    return (
        group["alltime_count"]
        * PUBLICATION_IMPORTANCE_WEIGHTS[core_constants.LIST_ALLTIME]
        + group["decade_count"]
        * PUBLICATION_IMPORTANCE_WEIGHTS[core_constants.LIST_DECADE]
        + group["misc_count"] * PUBLICATION_IMPORTANCE_WEIGHTS[core_constants.LIST_MISC]
        + group["eoy_count"] * PUBLICATION_IMPORTANCE_WEIGHTS[core_constants.LIST_EOY]
    )


class MusicListListView(HTMXPartialMixin, ListView):
    """The source lists behind the album rankings, grouped by publication."""

    model = models.MusicList
    template_name = "music/lists/list_list.html"
    context_object_name = "music_lists"
    htmx_partial_template = "music/lists/includes/_list_list_results.html"

    def get_queryset(self):
        qs = (
            models.MusicList.objects.select_related("publisher")
            .annotate(album_count=Count("albumlistmembership"))
            .order_by("order")
        )

        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(publisher__name__icontains=q))

        list_type = self.request.GET.get("type")
        if list_type in dict(core_constants.LIST_TYPES):
            qs = qs.filter(type=list_type)

        year = parse_int(self.request.GET.get("year"))
        if year is not None:
            qs = qs.filter(year=year)

        # Within a publication, the lists that say the most come first, as
        # they do in the games groups. The page's sort orders publications,
        # not lists, so it is applied to the groups in get_context_data.
        return qs.order_by("type", "-year", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_q"] = self.request.GET.get("q", "")
        context["current_type"] = self.request.GET.get("type", "")
        sort = self.request.GET.get("sort", "importance")
        if sort not in {option["value"] for option in config.MUSIC_LIST_SORT_OPTIONS}:
            sort = "importance"
        context["current_sort"] = sort
        context["current_dir"] = self.request.GET.get("dir") or default_direction(sort)
        context["sort_options"] = config.MUSIC_LIST_SORT_OPTIONS
        context["current_year"] = self.request.GET.get("year", "")

        music_lists = list(context["music_lists"])
        context["total_count"] = len(music_lists)

        groups = group_lists_by_publication(music_lists)
        descending = context["current_dir"] == "desc"

        def publication_name(group):
            return group["publication"].name.lower() if group["publication"] else ""

        if sort == "alpha":
            groups.sort(key=publication_name, reverse=descending)
        else:
            # The default, as on the games page: publications whose lists
            # carry the most weight first, ties broken by name.
            groups.sort(key=publication_name)
            groups.sort(key=_publication_importance, reverse=descending)
        context["publication_groups"] = groups
        context["publication_count"] = len(groups)

        # Facet counts: each filter counted with its own dimension left out,
        # so an option never leads to an empty page.
        by_type = models.MusicList.objects.all()
        if context["current_year"]:
            year = parse_int(context["current_year"])
            if year is not None:
                by_type = by_type.filter(year=year)
        context["list_types"] = [
            {
                "code": code,
                "label": core_constants.get_list_type_label(code),
                "count": by_type.filter(type=code).count(),
            }
            for code in core_constants.LIST_TYPE_IMPORTANCE_ORDER
        ]

        by_year = models.MusicList.objects.all()
        if context["current_type"]:
            by_year = by_year.filter(type=context["current_type"])
        context["list_years"] = list(
            by_year.values("year").annotate(count=Count("id")).order_by("-year")
        )
        return context


class AlbumCoverView(View):
    """Serve our own stored copy of an album cover.

    The Cover Art Archive is the source of this art, but hotlinking it means
    every page view depends on archive.org, which 500s intermittently; a
    list page showing a hundred covers then shows several broken images on
    every load. Storing the bytes and serving them from here removes that
    dependency, and also the 307 redirect each remote image costs.

    The URL carries the archive's release MBID, image id and size, all of
    which are immutable for a given image, so the response is cached for a
    year. Staff-gated like every other music route.
    """

    # A year, which is the maximum worth asking for, marked immutable so a
    # revalidation request is never made.
    CACHE_CONTROL = "public, max-age=31536000, immutable"

    def get(self, request, release_mbid, image_id, size):
        cover = models.AlbumCover.objects.filter(
            release_mbid=release_mbid, image_id=image_id, size=size
        ).first()
        if cover is None:
            raise Http404("No such cover")

        # `bytes(cover.data)` here would hold a second full copy of the
        # image: psycopg2 hands back a memoryview and Django's content
        # setter converts it once already. The covers run to 228 KB and a
        # rankings page asks for a hundred of them.
        response = HttpResponse(cover.data, content_type=cover.content_type)
        response["Cache-Control"] = self.CACHE_CONTROL
        response["Content-Length"] = str(len(response.content))
        return response


class MusicImportView(StaffOnlyMixin, View):
    """Import the album rankings from uploaded files or the bundled release.

    Staff-gated like every other music view, as ``games.views.ImportView``
    now is too - it was login-gated until 2026-10-17, which let any verified
    account replace the game rankings.

    The import runs inline rather than over SSE: 500 albums land in well
    under a second, so the streaming progress machinery the games importer
    needs would be scaffolding without a purpose.
    """

    template_name = "music/import.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            self._context(MusicImportForm()),
        )

    def post(self, request):
        form = MusicImportForm(request.POST, request.FILES)
        summary = None
        error = None

        if form.is_valid():
            try:
                message, warnings = self._run_import(form.cleaned_data)
            except Exception as exc:  # noqa: BLE001 - surfaced to the page
                # The importer runs in one transaction, so a failure leaves
                # the previous rankings in place; report it and carry on.
                error = str(exc)
            else:
                # Outside the try: the release is live by now, so a failure
                # here must not reach the message above.
                summary = {
                    "message": message,
                    "warnings": warnings,
                    "counts": _music_counts(),
                }

        return render(
            request,
            self.template_name,
            self._context(form, summary=summary, error=error),
        )

    def _run_import(self, data):
        """Run the batch import, from uploads or the bundled files."""
        if data.get("seed_bundled_data"):
            missing = [
                name
                for name in BUNDLED_FILES.values()
                if not (BUNDLED_RELEASE_DIR / name).is_file()
            ]
            if missing:
                raise FileNotFoundError(
                    "Bundled release files are missing: " + ", ".join(missing)
                )
            with ExitStack() as stack:
                # Keyed by field name, which is also import_batch's keyword.
                # The positions file is read by line, not by csv, so it is
                # opened without newline="".
                files = {
                    field: stack.enter_context(
                        (BUNDLED_RELEASE_DIR / name).open(
                            encoding="utf-8-sig",
                            newline=None if field == "positions_file" else "",
                        )
                    )
                    for field, name in BUNDLED_FILES.items()
                }
                return import_handler.import_batch(**files)
        else:
            wrappers = {
                field: TextIOWrapper(data[field], encoding="utf-8-sig", newline="")
                for field in MusicImportForm.FILE_FIELDS
            }
            try:
                return import_handler.import_batch(**wrappers)
            finally:
                for wrapper in wrappers.values():
                    wrapper.detach()

    def _context(self, form, summary=None, error=None):
        return {
            "form": form,
            "summary": summary,
            "error": error,
            "counts": _music_counts(),
            "metadata": _metadata_gaps(),
            "bundled_files": [
                {"label": MusicImportForm().fields[field].label, "name": name}
                for field, name in BUNDLED_FILES.items()
            ],
            "bundled_dir": _bundled_dir_label(),
            "bundled_available": all(
                (BUNDLED_RELEASE_DIR / name).is_file()
                for name in BUNDLED_FILES.values()
            ),
        }


def _bundled_dir_label():
    """The bundled release directory, shown relative to the project root.

    Falls back to the absolute path when the directory sits outside the
    project, which only happens when it has been pointed elsewhere.
    """
    try:
        return str(BUNDLED_RELEASE_DIR.relative_to(settings.BASE_DIR))
    except ValueError:
        return str(BUNDLED_RELEASE_DIR)


def _music_counts():
    """Current row counts, shown before and after an import."""
    return {
        "albums": models.Album.objects.count(),
        "artists": models.Artist.objects.count(),
        "album_credits": models.AlbumCredit.objects.count(),
        "lists": models.MusicList.objects.count(),
        "publications": models.MusicPublication.objects.count(),
        "memberships": models.AlbumListMembership.objects.count(),
    }


def _metadata_gaps():
    """How many albums each metadata pass still has work for.

    An import keeps every album it matches by Wikidata id, metadata and all,
    but one it adds has no external data until the metadata pass next runs
    (which is also when a returning album's old rows are re-adopted by
    external id). Until then it renders without cover art or genres. The
    games import page carries the same idea as its "Metadata Operations"
    panel.
    """
    total = models.Album.objects.count()
    missing_wikidata = models.Album.objects.filter(
        primary_wikipedia_album_data__isnull=True
    ).count()
    missing_genres = models.Album.objects.filter(genres__isnull=True).count()
    missing_covers = models.Album.objects.exclude(
        primary_musicbrainz_album_data__cover_art_stored=True
    ).count()

    return {
        "total": total,
        "missing_wikidata": missing_wikidata,
        "missing_genres": missing_genres,
        "missing_covers": missing_covers,
        "complete": total > 0
        and not (missing_wikidata or missing_genres or missing_covers),
        # Discogs' anonymous tier is the floor on a refresh: 25 requests a
        # minute, one per album, so this is the number that matters.
        "estimated_minutes": (
            math.ceil(
                max(missing_genres, missing_covers, missing_wikidata)
                / config.DISCOGS_ANONYMOUS_REQUESTS_PER_MINUTE
            )
            if total
            else 0
        ),
    }
