"""
Configuration constants for the Music application.

Centralizes cache timeouts, pagination defaults, and other settings.
Mirrors the structure of games/config.py and books/config.py.
"""

from django.conf import settings

# =============================================================================
# Cache Timeouts (in seconds)
# =============================================================================

CACHE_TIMEOUT_5_MINUTES = 60 * 5  # 300 seconds
CACHE_TIMEOUT_1_HOUR = 60 * 60  # 3600 seconds
CACHE_TIMEOUT_24_HOURS = 60 * 60 * 24  # 86400 seconds
CACHE_TIMEOUT_DEFAULT = CACHE_TIMEOUT_24_HOURS

# Cache version - bump this to invalidate all caches after schema/data changes
CACHE_VERSION = "v1"

# =============================================================================
# Pagination Defaults
# =============================================================================

DEFAULT_PAGE_SIZE = 100
SEARCH_PAGE_SIZE = 100

# =============================================================================
# Year Defaults
# =============================================================================

DEFAULT_MIN_YEAR = 1950  # The supplied rankings start at 1955

# =============================================================================
# Cache Keys
# =============================================================================

# Whether music pages carry a "Beta" badge and notice
MUSIC_BETA = True

# Every key carries CACHE_VERSION, so one bump invalidates the whole set, and
# every *global* key appears in CACHE_KEYS, which
# `music.services.caching.invalidate_music_caches` iterates - a new cached option cannot
# be added without being invalidated too. Per-user values cannot be
# enumerated that way; they live in PER_USER_CACHE_KEY_TEMPLATES below.
CACHE_KEY_YEAR_STATS = f"{CACHE_VERSION}:album_year_stats"
CACHE_KEY_ARTIST_OPTIONS = f"{CACHE_VERSION}:music_artist_options"
CACHE_KEY_GENRE_OPTIONS = f"{CACHE_VERSION}:music_genre_options"
CACHE_KEY_HERO_STATS = f"{CACHE_VERSION}:music_hero_stats"
CACHE_KEY_TOTAL_ALBUM_COUNT = f"{CACHE_VERSION}:total_album_count"
CACHE_KEY_LANDING_GENRES = f"{CACHE_VERSION}:music_landing_genres"
CACHE_KEY_LANDING_DECADES = f"{CACHE_VERSION}:music_landing_decades"
CACHE_KEY_YEAR_BASELINE = f"{CACHE_VERSION}:music_year_baseline"
CACHE_KEY_LISTENER_COUNTS = f"{CACHE_VERSION}:listener_counts"

# Not a cached value but the stamp every invalidation moves, so it stays out
# of CACHE_KEYS: `music.services.caching.cached` compares it around a read.
CACHE_KEY_GENERATION = f"{CACHE_VERSION}:cache_generation"

CACHE_KEYS = (
    CACHE_KEY_YEAR_STATS,
    CACHE_KEY_ARTIST_OPTIONS,
    CACHE_KEY_GENRE_OPTIONS,
    CACHE_KEY_HERO_STATS,
    CACHE_KEY_TOTAL_ALBUM_COUNT,
    CACHE_KEY_LANDING_GENRES,
    CACHE_KEY_LANDING_DECADES,
    CACHE_KEY_YEAR_BASELINE,
    CACHE_KEY_LISTENER_COUNTS,
)

# Album detail is the catch-all `/<slug>/` at the root of the music host, so
# every fixed first segment there would shadow an album that slugified to it:
# music/urls.py's own, and the routes every site shares
# (acclaimedgames/urls_common.py, urls_music.py). `/1970s/` is a decade
# landing page. `Album._build_unique_slug` treats these as taken;
# `test_every_static_route_segment_is_reserved` keeps the set in step with
# the URLconf.
RESERVED_ALBUM_SLUGS = frozenset(
    {
        # music/urls.py
        "artists",
        "browse",
        "cover",
        "download",
        "genres",
        "import",
        "lists",
        "search",
        # Shared with every site, and the music API's mount point
        "accounts",
        "admin",
        "api",
        "auth",
        "contact",
        "healthz",
        "page",
        "static",
        "unsubscribe",
        "test-404",
        "__debug__",
    }
)
RESERVED_ALBUM_SLUG_PATTERN = r"^\d{3}0s$"

# Per-user tracking id sets. These are *templates*, not keys: there is one key
# per user, so they cannot go in CACHE_KEYS and an import cannot blanket
# invalidate them. `music.services.caching` drops them at the only three
# moments they can go stale - a toggle, an import, and `mark_albums_listened`.
# A new per-user cached value belongs in this tuple for the same reason a new
# global one belongs in CACHE_KEYS.
CACHE_KEY_LISTENED_ALBUMS = f"{CACHE_VERSION}:listened_albums_{{user_id}}"
CACHE_KEY_WANT_TO_LISTEN_ALBUMS = f"{CACHE_VERSION}:want_to_listen_albums_{{user_id}}"
CACHE_KEY_OWNED_ALBUMS = f"{CACHE_VERSION}:owned_albums_{{user_id}}"

PER_USER_CACHE_KEY_TEMPLATES = (
    CACHE_KEY_LISTENED_ALBUMS,
    CACHE_KEY_OWNED_ALBUMS,
    CACHE_KEY_WANT_TO_LISTEN_ALBUMS,
)

CACHE_TIMEOUT_TRACKING = CACHE_TIMEOUT_5_MINUTES

# =============================================================================
# Listen Status
# =============================================================================

# The Listen Status control's options, in the order the sidebar shows them.
#
# Two vocabularies, as games has: `value` is the filter's (`?listened=yes`),
# `status` is the toggle's (`?status=listened`, and what the button writes
# into data-status). `?listened=yes` reads correctly in a URL and
# data-status="listened" reads correctly on an element, so neither spelling
# is forced to serve both. This table is the only place the two are mapped
# server-side; `core/static/core/js/media-tracking.js` holds the client's.
#
# The states are exclusive: Have, Heard, Want or Untracked. "Heard" kept the
# `listened` / `yes` spelling it had when it was labelled "Listened", so old
# links, saved filters and `mark_albums_listened` still mean the same thing.
# Every option carries the mark its button shows, in its colours, as games'
# GAME_STATUS_OPTIONS do: Untracked dimmed by opacity (so it stays visible on
# a selected option), Want in the warning colour.
# "Have" is a ListenedAlbum row with owned=True. Have and Heard show an
# illustration (`image`, a static path) where the others show a glyph: a gold
# record, and for Have that record sliding out of its sleeve - the record
# family again, told apart from Heard by its shape and not only its colour.
LISTEN_STATUS_OPTIONS = (
    {
        "value": "no",
        "status": "none",
        "label": "Untracked",
        "title": "Untracked",
        "icon": "mdi-record-circle-outline",
        "icon_class": "opacity-60",
    },
    {
        "value": "want",
        "status": "want",
        "label": "Want",
        "title": "Want to Listen",
        "icon": "mdi-record-plus",
        "icon_class": "text-warning",
    },
    {
        "value": "yes",
        "status": "listened",
        "label": "Heard",
        "title": "Heard",
        "image": "music/images/gold-record.svg",
    },
    {
        "value": "own",
        "status": "own",
        "label": "Have",
        "title": "Owned",
        "image": "music/images/record-sleeve.svg",
    },
)

# The quick-mark picker's choices (core/includes/_quick_mark_picker.html),
# most-collected first. `status` is the toggle's vocabulary; "Clear" sets
# none, which a reader tidying up a run of mis-marks wants as much as a mark.
QUICK_MARK_OPTIONS = (
    {
        "status": "own",
        "label": "Have",
        "image": "music/images/record-sleeve.svg",
    },
    {
        "status": "listened",
        "label": "Heard",
        "image": "music/images/gold-record.svg",
    },
    {
        "status": "want",
        "label": "Want",
        "icon": "mdi-record-plus",
        "icon_class": "text-warning",
    },
    {
        "status": "none",
        "label": "Clear",
        "icon": "mdi-record-circle-outline",
        "icon_class": "text-base-content/50",
    },
)

LISTEN_FILTER_VALUES = tuple(option["value"] for option in LISTEN_STATUS_OPTIONS)
LISTEN_TOGGLE_STATUSES = tuple(option["status"] for option in LISTEN_STATUS_OPTIONS)

# =============================================================================
# Import Settings
# =============================================================================

IMPORT_BATCH_SIZE = 1000

# =============================================================================
# Metadata Pipeline
# =============================================================================

# API endpoints
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
DISCOGS_API_URL = "https://api.discogs.com"
MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2"
COVER_ART_ARCHIVE_URL = "https://coverartarchive.org"

# User agent. MusicBrainz rejects requests without one carrying a contact
# address, and Discogs rejects requests without a descriptive one.
MUSIC_USER_AGENT = (
    "AcclaimedGamesBot/1.0 "
    f"({settings.CANONICAL_ORIGIN}/; contact@acclaimedvideogames.com)"
)

# Rate limiting.
# - MusicBrainz publishes a hard average of 1 request/second per IP and
#   answers 503 past it, so leave headroom.
# - The Cover Art Archive documents no rate limiting at all; be polite anyway.
# - Discogs reported X-Discogs-Ratelimit: 25 (per minute) unauthenticated. A
#   token raises that, by an amount the docs would not serve, so the client
#   paces itself from the response headers and treats this as the floor.
MUSICBRAINZ_REQUEST_DELAY = 1.1
COVER_ART_REQUEST_DELAY = 0.2
DISCOGS_REQUEST_DELAY = 2.5

# The same figure as a rate, for estimating how long a refresh will take.
DISCOGS_ANONYMOUS_REQUESTS_PER_MINUTE = 25

# Wikidata lets wbgetentities take 50 entity ids per request for ordinary
# clients, which turns 500 albums into 10 round trips.
WIKIDATA_BATCH_SIZE = 50

# Wikidata properties read off an album entity.
WIKIDATA_PERFORMER_PROPERTY = "P175"
WIKIDATA_GENRE_PROPERTY = "P136"
WIKIDATA_RELEASE_DATE_PROPERTY = "P577"
WIKIDATA_LABEL_PROPERTY = "P264"
WIKIDATA_MUSICBRAINZ_RELEASE_GROUP_PROPERTY = "P436"
WIKIDATA_DISCOGS_MASTER_PROPERTY = "P1954"
WIKIDATA_SPOTIFY_PROPERTY = "P2205"

# Read off an artist entity, so Artist.musicbrainz_id needs no MusicBrainz call.
WIKIDATA_ARTIST_MUSICBRAINZ_PROPERTY = "P434"

# Cover Art Archive thumbnail sizes. 250 covers the 90px rows at 2x, 500 the
# 300px detail image.
COVER_ART_THUMBNAIL_SIZES = (250, 500, 1200)

# How many bins the rank distribution chart draws, matching games so the
# two charts read at the same resolution.
RANK_DISTRIBUTION_BIN_COUNT = 10

# The SiteMetadata row this section stamps on import, which the rankings
# heading reads as "Updated: ...".
SITE_METADATA_KEY = "music"

# =============================================================================
# Artist credits
# =============================================================================

# The credit for "VA" in WebRankings.txt: the whole line of a compilation, the
# tail of a soundtrack credited to an artist and others ("Jimmy Cliff &
# Various Artists"). Not linked, because there is no artist page behind it.
# The token is how the file spells it, always the last credit.
VARIOUS_ARTISTS = "Various Artists"
VARIOUS_ARTISTS_TOKEN = "VA"

# =============================================================================
# Ranking list controls
# =============================================================================

# The sorts offered on the album rankings page. Keys match ALBUM_SORTS in
# music/views.py and the comparators in album-filter.js; the labels and their
# order are rendered by core/includes/_media_list_controls.html, the same
# partial the games rankings page uses.
SORT_OPTIONS = (
    {"value": "rank", "label": "Rank"},
    {"value": "year", "label": "Release Date"},
    {"value": "name", "label": "A-Z"},
)

# The artist and source-list pages, rendered by
# core/includes/_entity_sort_controls.html - the control the games developer
# list uses. Keys match ARTIST_SORTS and MUSIC_LIST_SORTS in music/views.py.
ARTIST_SORT_OPTIONS = (
    {"value": "albums", "label": "# Albums"},
    {"value": "rank", "label": "Top Rank"},
    {"value": "name", "label": "Name (A-Z)"},
)

# An artist's own albums, by acclaim or as a career in release order. Keys
# match ARTIST_ALBUM_SORTS in music/views.py. The control appears only from
# ARTIST_ALBUM_SORT_MIN_ALBUMS up: with one or two albums the order is moot.
ARTIST_ALBUM_SORT_OPTIONS = (
    {"value": "rank", "label": "Rank"},
    {"value": "year", "label": "Release Date"},
)
ARTIST_ALBUM_SORT_MIN_ALBUMS = 3

# The source-lists page sorts publications, not loose lists, now that it
# groups by publication - so it offers what the games page offers in the
# same mode: by how much a publication contributes, or by name.
MUSIC_LIST_SORT_OPTIONS = (
    {"value": "importance", "label": "# Lists"},
    {"value": "alpha", "label": "Alphabetical"},
)

# =============================================================================
# Saved filters
# =============================================================================

# How many filter combinations one reader may keep, and how long a name may
# be. Both live here rather than in the view because games hard-codes its
# ceiling in the view *and* in both of its templates, which is how its
# sidebar and its mobile sheet came to state the limit in two places.
MAX_SAVED_FILTERS = 10
SAVED_FILTER_NAME_MAX_LENGTH = 255

# Saved filters are deliberately **uncached**. Every other note in this file
# says a new value has to be registered for invalidation, so the absence
# needs stating: these rows are per-user, read once when the dropdown is
# first opened, and written by the reader who is about to re-read them - so a
# cache would be invalidated on nearly every read and would have to be
# dropped on every write. Nothing here joins CACHE_KEYS or
# PER_USER_CACHE_KEY_TEMPLATES.
