# AGENTS.md

This file provides guidance to Claude Code and Codex when working with code in this repository.

`CLAUDE.md` is a symlink to this file: edit this one, and keep the link. Claude Code would load this file without it, but `/code-review`'s conventions check reads only `CLAUDE.md` files (checked 2026-10-31, Claude Code 2.1.309), so deleting the link stops the review checking the rules below.

## Project Overview

Acclaimed Media ranks the most critically acclaimed video games and albums by aggregating critics' lists. One Django app serves three hosts: a landing page at `acclaimedmedia.org`, the game rankings at `games.acclaimedmedia.org` and the album rankings at `music.acclaimedmedia.org` (see "Domain"). The application uses Django with server-side rendering, HTMX for dynamic interactions, and Alpine.js for client-side reactivity. It integrates with the IGDB (Internet Game Database) API.

## Available Skills

Use these skills for common workflows:
- `/commit` - Commit and push to git (builds CSS, minifies JS, runs `/code-review`, pushes to main)
- `/deploy` - Deploy to Heroku production (all commit steps, review included, then waits for CI, backs up the database if migrations ship, pushes to Heroku and checks `/healthz/`)
- `/minify` - Minify JavaScript files and regenerate bundles
- `/igdb` - Import IGDB game data
- `/wikipedia` - Fetch Wikipedia metadata and genres
- `/refresh-metadata` - Weekly metadata refresh (IGDB + Wikipedia)
- `/test` - Run tests with coverage
- `/icons` - Add Material Design Icons to the site (including subset font rebuilds)
- `/openlibrary` - Fetch book metadata from Open Library API
- `/music-metadata` - Fetch album metadata (Wikidata, Discogs, MusicBrainz, cover art)
- `/upgrade-deps` - Monthly upkeep: Dependabot PRs, package bumps, audits, performance and end-of-life checks

Import the music ranking release with `python manage.py import_music_data`,
then populate its metadata with `/music-metadata`
(`python manage.py fetch_album_metadata`).

### Review before merging

Every ticket's changes get a `/code-review` pass (at `high`) before they
reach `main`. Pushing to `main` is the merge here: there is no branch
protection, and the only PRs are Dependabot's, so the review is a workflow
rule rather than a GitHub one. `/commit` and `/deploy` run it as their step
5. A hand-run `git push origin main` or merge is covered by the same rule,
and so is merging a Dependabot PR with `gh pr merge`. Fix every finding or
say in chat why it is waived, and review again after any fix, for as many
rounds as it takes; skip the review only when the user says to,
or the diff touches no code or templates (a Dependabot PR that changes
only lock files touches none). Codex has no `/code-review`: a Codex
session asks the user before pushing to `main` or merging a PR.

## Development Commands

### Backend (Django)

**Activate virtual environment:**

On macOS/Linux:
```bash
source venv/bin/activate
```

On Windows (Git Bash/PowerShell):
```bash
source venv/Scripts/activate
```

**Run development server:**
```bash
DEBUG=True python3 manage.py runserver
```

**Note:** Always include `DEBUG=True` when running the development server locally to enable template reloading, detailed error pages, and the Django Debug Toolbar.

Open `http://games.localhost:8000/` for the games site, `http://music.localhost:8000/` for music and `http://localhost:8000/` for the landing page (see "Domain"). `127.0.0.1:8000` serves the games site.

**Database migrations:**
```bash
python3 manage.py migrate
python3 manage.py makemigrations
```

**Create superuser:**
```bash
python3 manage.py createsuperuser
```

**Sync production database to local SQLite:**
```bash
python3 manage.py sync_from_prod
```
Downloads the games and music data from production Heroku and loads it into
local SQLite: two `dumpdata` runs, the music one with the cover art bytes
(~100 MB, a few minutes). Per-user rows are not synced and local ones are
deleted: played/want-to-play, heard/have/want-to-listen, saved filters. Auth
users are excluded too, so local accounts survive; on a fresh database,
create a superuser with `python3 manage.py createsuperuser`. Clearing and
loading run in one transaction, so a failed load leaves the local data as it
was.

**Collect static files (before deployment):**
```bash
python3 manage.py collectstatic
```

### Heroku Commands

**Important:** When running commands on Heroku, use `--` after `run` to separate Heroku flags from the command:

```bash
# Run Django shell with a command
heroku run -- python manage.py shell -c "from games.models import Game; print(Game.objects.count())"

# Run a management command
heroku run -- python manage.py migrate

# Open interactive shell
heroku run -- python manage.py shell
```

## Architecture

### Backend Structure

- **acclaimedgames/** - Django project settings and main URL configuration
- **core/** - Shared infrastructure for multi-media support:
  - **sites.py**, **middleware.py** - The three sites by host, and the middleware that routes to their URLconfs (`acclaimedgames/urls_root.py`, `urls_games.py`, `urls_music.py`, with the shared routes in `urls_common.py`)
  - **views.py** - The landing page, the apex's redirects to the two sites, `healthz`
  - **models.py** - User model, abstract base classes (MediaItemBase, CreatorBase, ExternalDataBase, UserTrackingBase)
  - **mixins.py** - Shared view mixins (RobustPaginationMixin, HTMXPartialMixin)
  - **templatetags/core_filters.py** - Shared template filters
  - **templates/core/** - Shared templates (_pagination.html, _base_media_row.html)
  - **static/core/js/** - Base JavaScript renderer classes
- **games/** - Main Django app containing:
  - **models.py** - Core data models (Game, Developer, Platform, List, etc.)
  - **api/** - REST API with views, serializers, and URL routing
  - **views/** - The views, one module per page family: `rankings` (home and
    the SEO landing pages), `game_pages` (detail and the played toggle),
    `developers`, `lists`, `download` (CSV), `content` (contact, flat pages,
    blog, 404, robots.txt), `imports` (staff), `auth` (the sign-in modal),
    plus `filter_titles` and `_helpers`. `__init__` re-exports every name,
    so `games.views.X` still resolves; patch a name where it is read
    (`games.views.rankings._get_year_bounds`). Split from one 4,000-line
    module on 2026-10-26
  - **middleware.py** - HTMXPushURLMiddleware for HTMX history support
  - **templatetags/** - Custom template filters (game_filters.py)
  - **management/commands/** - Custom Django commands (e.g., `get_igdb.py`)
  - **tests/** - Comprehensive test suite (API, models, IGDB, imports, views, admin, utils)
  - **templates/** - Server-side templates with HTMX and Alpine.js
  - **static/** - Static files served by Django
- **books/** - Books app for book rankings (feature-flagged with `BOOKS_ENABLED`):
  - **models.py** - Book, Author, BookGenre, BookSeries, ReadBook, WantToReadBook, etc.
  - **api/** - REST API with views, serializers, and URL routing
  - **views.py** - Book-related views (BookHomePageView, BookDetailView, AuthorListView, etc.)
  - **openlibrary.py** - Open Library API client for book metadata
  - **hardcover.py** - Hardcover GraphQL API client (optional)
  - **book_metadata.py** - Unified metadata service combining multiple sources
  - **templatetags/book_filters.py** - Book-specific template filters
  - **management/commands/** - Book metadata commands (fetch_book_metadata.py)
  - **templates/books/** - Book templates
  - **static/books/js/** - Book list renderer and client-side filtering

- **music/** - Music app for album rankings:
  - **models.py** - Album, Artist, MusicGenre, MusicPublication, MusicList, AlbumListMembership
  - **api/** - REST API with views, serializers, and URL routing (read-only but for saved filters, deliberately uncached)
  - **views.py** - Album/artist/source-list views and the SEO landing pages (the import page behind `core.mixins.StaffOnlyMixin`)
  - **sitemaps.py** - The music sitemap sections
  - **services/landing_pages.py** - Which genre and decade landing pages exist
  - **services/import_handler.py** - Imports the four-TSV album ranking release
  - **services/credits.py** - The credit line, and which albums are whose (from `AlbumCredit`)
  - **templatetags/music_filters.py** - Music-specific template filters
  - **management/commands/import_music_data.py** - Loads the ranking release files
  - **templates/music/** - Music templates; album rows extend `core/includes/_base_media_row.html`

**Installed Apps:**
- `django.contrib.admin` - Admin interface
- `django.contrib.auth` - Authentication
- `django.contrib.contenttypes` - Content type framework
- `django.contrib.sessions` - Session management
- `django.contrib.messages` - Messaging framework
- `django.contrib.staticfiles` - Static file management
- `django.contrib.flatpages` - Flat pages framework for CMS content
- `django.contrib.sites` - Sites framework (used for multi-site support)
- `django.contrib.postgres` - PostgreSQL-specific features
- `rest_framework` - Django REST Framework
- `corsheaders` - CORS support
- `tailwind` - django-tailwind integration
- `theme` - Tailwind CSS theme app with DaisyUI
- `core` - Shared infrastructure (User model, abstract bases, mixins)
- `games` - Main game aggregation app with HTMX and Alpine.js
- `books` - Book rankings app (behind `BOOKS_ENABLED` feature flag)
- `music` - Album rankings app

**Middleware:**
- `django.middleware.security.SecurityMiddleware` - Security headers
- `core.middleware.SiteHostMiddleware` - Picks the site (landing, games,
  music) and its URLconf from the host; see "Domain"
- `whitenoise.middleware.WhiteNoiseMiddleware` - Static file serving in production
- `games.middleware.UncompressedUptimeCheckMiddleware` - Answers a `GET`/`HEAD`
  of `/` from `SentryUptimeBot` that refuses gzip with a 2-byte 200, before
  rate limiting and sessions. Two SentryUptimeBot checks hit `/` every
  minute: ours (at :17, sending gzip) and one at :39 that sends no
  `Accept-Encoding` and pulled the whole ~667 KB page. Sentry Support
  confirmed on 2026-10-26 that the :39 check is not in our organization and
  is tracing it, so each :39 check temporarily logs its `sentry-trace` to
  `games.middleware.uptime`; remove that once they name the source. The
  2-byte answer proves only that a dyno is up - our gzip monitor, which
  still gets the real page, is the one that catches a broken render, so do
  not delete it
- `games.middleware.RateLimitMiddleware` - Per-IP rate limiting (see "Caching")
- `games.middleware.EventStreamAwareGZipMiddleware` - gzip for any client that
  accepts it, except `text/event-stream`, which zlib would buffer
- `django.contrib.sessions.middleware.SessionMiddleware` - Session management
- `corsheaders.middleware.CorsMiddleware` - CORS headers
- `django.middleware.common.CommonMiddleware` - Common utilities
- `django.middleware.csrf.CsrfViewMiddleware` - CSRF protection
- `django.contrib.auth.middleware.AuthenticationMiddleware` - Authentication
- `allauth.account.middleware.AccountMiddleware` - django-allauth's account state
- `django.contrib.messages.middleware.MessageMiddleware` - Messages
- `django.middleware.clickjacking.XFrameOptionsMiddleware` - Click-jacking protection
- `django.contrib.flatpages.middleware.FlatpageFallbackMiddleware` - Flat pages routing
- `games.middleware.HTMXPushURLMiddleware` - HTMX history/URL push support

### Data Models

Core Django models include:

- **Game** - Video games with ranking, IGDB integration, genres, platforms, and developers
- **Developer** - Game development entities with hierarchical parent-child relationships
  - Uses self-referential `parent` FK for ownership hierarchy
  - Root developers (parent=None) have slugs for URL routing (e.g., Nintendo, Valve)
  - Subsidiary developers (parent=Developer) are child entities (e.g., Nintendo EAD, Respawn)
  - Games link to developers via `Game.developers` M2M field
  - In IGDB's data model, all are "company" records - we add hierarchy on import
- **Platform** - Gaming platforms (PC, PS5, etc.)
- **Genre** - Game genres
- **Publication** - Magazines/websites that publish game lists
- **List/ListMembership** - Published rankings and game positions within them
- **Post** - Blog-style news posts with markdown support
- **Snippet** - Reusable text snippets

Books-specific models (behind `BOOKS_ENABLED` feature flag):

- **Book** - Book items with ranking, author, genre, and metadata integration
- **Author** - Book authors with hierarchical parent-child relationships (similar to Developer)
- **BookGenre** - Hierarchical book genres with path denormalization
- **BookSeries** - Book series with position tracking
- **BookListMembership** - Book positions within lists
- **ReadBook/WantToReadBook** - User tracking for books (like PlayedGame/WantToPlayGame)
- **WikipediaBookData** - Wikipedia metadata for books

Music-specific models:

- **Album** - Albums with ranking, a derived credit line, credited artists, genres, and Wikidata/MusicBrainz ids
- **Artist** - Every act in `ArtistInfo.txt`, keyed on the provider's permanent
  `source_id`, with `name_variants` (every name it is credited under, the first
  its own) and `all_wikidata_ids`. Every artist has a slug and a page; there is
  no parent FK and, since `0009`, no relation table
- **AlbumCredit** - the through table of `Album.artists`: the credit order, the
  `variant` the release names and its `credited_name` (Purple Rain: Prince, as
  "Prince and the Revolution"). Read `album.credits.all()` or
  `album.credited_artists`, not `album.artists.all()`, which is alphabetical
- **MusicGenre** - Hierarchical music genres with path denormalization
- **MusicPublication/MusicList/AlbumListMembership** - Album rankings and positions within them
- **WikipediaAlbumData/DiscogsAlbumData/MusicBrainzAlbumData** - fetched metadata on
  `ExternalDataBase`, each with the `primary_…` OneToOne fast-path and the
  `unique_primary_…_per_album` partial constraint. An import keeps every album it
  matches, so its rows stay attached. All use `on_delete=SET_NULL`, so the rows of
  an album a release drops survive it, and every metadata pass re-adopts them by
  external ID if the album comes back
- **AlbumCover** - the cover-art bytes at two sizes, keyed by the Cover Art Archive's
  own release MBID, image id and size rather than by album, so they also outlive
  their album's deletion
- **ListenedAlbum / WantToListenAlbum** - per-user tracking on
  `core.models.UserTrackingBase`, as books' pair is and games' predates. Each
  keeps a nullable `album` FK **and** the album's `wikidata_id`, because an
  import deletes the albums a release drops: the rows survive on `SET_NULL` and
  `music.services.user_tracking_service` re-adopts them by that id if the
  album comes back.
  Mutual exclusivity is enforced by the toggle view, not by a constraint -
  they are separate tables, so no one constraint spans them. "Have" (an album
  the user owns) is a `ListenedAlbum` row with `owned=True`, not a third
  table, so it inherits the reconnection pass and the bulk command unchanged

### API Architecture

Django REST Framework powers the API at `/api/` with endpoints:
- `/api/games/` - List and search games
- `/api/games/search/` - Game search for navbar
- `/api/games/<slug>/` - Game details with lists appearances
- `/api/developers/` - List of all developers with games
- `/api/developers/<slug>/` - Developer details by slug
- `/api/developers/by-id/<igdb_id>/` - Developer details by IGDB ID
- `/api/lists/` - Source lists
- `/api/platforms/` - Gaming platforms
- `/api/genres/` - Game genres (also available at `/api/wikipedia-genres/` for backwards compatibility)
- `/api/meta/` - Metadata about the database
- `/api/unified-search/` - Unified search for games, developers, and series

Books API endpoints (behind `BOOKS_ENABLED` feature flag):
- `/api/books/` - List and search books
- `/api/books/search/` - Book search
- `/api/books/<slug>/` - Book details with lists appearances
- `/api/books/all/` - Bulk endpoint with gzip compression
- `/api/books/authors/` - List authors
- `/api/books/authors/<slug>/` - Author details with book list
- `/api/books/unified-search/` - Unified book search

Music API endpoints, on `music.acclaimedmedia.org` (at `/api/` on the
apex until 2026-10-30, which now redirects):
- `/api/` - List and filter albums
- `/api/<slug>/` - Album details with list appearances
- `/api/search/` - Album search
- `/api/artists/` and `/api/artists/<slug>/` - Artists
- `/api/lists/` - Source lists
- `/api/genres/` - Music genres
- `/api/meta/` - Counts and year/decade distributions
- `/api/all/` - Every album in one payload, for client-side filtering
- `/api/unified-search/` - Albums and artists together, for the sidebar
  and mobile search boxes. `order` puts the group with the better match on
  top - exact name, then a word starting with the query, then a substring,
  and last an album found only through its credit line - with artists
  winning a tie (`core/services/search_ranking.py`, which games'
  `/api/unified-search/` uses too). Artists are ordered by
  match, then album count; albums by rank, except an exact title, which
  comes first (by match alone, "Beatles" put Meet the Beatles! at #820 above
  Abbey Road at #4). Albums always came first until 2026-10-29, and an album
  matches on its credit, so "Beatles" filled the five album rows and the
  band sat below the dropdown's fold
- `/api/saved-filters/` and `/api/saved-filters/<pk>/` - a
  reader's saved filter combinations. The only endpoints in `music/api/`
  that **write**, so the only ones CSRF applies to

**Note:** these endpoints carry no `cache_page` decorator, and nothing has
measured whether they should. `/api/all/` is the one to look at first.

**Note:** every view in `music/api/` names `SessionAuthentication` (through
`MusicReadAPIMixin` or `MusicWriteAPIMixin`), as books' `StaffReadAPIMixin` does.
`REST_FRAMEWORK`'s `DEFAULT_AUTHENTICATION_CLASSES` is empty project-wide, so a
view that names no authenticator sees a signed-in user as anonymous. On music's
reads that matters to the throttle: `AnonRateThrottle` skips an authenticated
request, so dropping it would put signed-in readers under the 60/minute limit.
On books, whose views declare `permission_classes = [IsStaffOrHide]`, it 404s
staff. The books API shipped that way until 2026-10-17 - its whole read API
was unreachable from a browser - and the tests missed it because
`APIClient.force_authenticate` bypasses authentication entirely. Test API
access with a real session login.

### Shared ranking-page components

The games and album rankings pages render the same chrome from `core/`. They
had each grown their own, and the album page's was visibly poorer for it - a
row of decade chips instead of the year heatmap, a flat `<select>` where a
root genre and one of its styles looked identical, no view toggle, no
jump-to-rank, and row styling that had copied the games hover rules without
the hover.

| Shared piece | What it is |
|---|---|
| `core/includes/_media_list_controls.html` | sort dropdown, direction flip, list/grid toggle, jump-to-rank |
| `core/includes/_year_grid.html` | the year heatmap, with drag and shift+click ranges |
| `core/includes/_genre_filter.html` | the hierarchical genre tree |
| `core/includes/_mobile_filter_time.html`, `_mobile_filter_genres.html` | their bottom-sheet equivalents |
| `core/includes/_entity_sort_controls.html` | the sort control for entity lists (artists, source lists, developers) |
| `core/includes/_publication_group.html` | a publication's lists, collapsible, on a source-lists page |
| `core/includes/_list_type_group.html` | one group of list appearances on a detail page |
| `core/includes/_rank_distribution.html` | where the filtered items sit across the ranking |
| `core/includes/_search_box.html` | the standard search input, with its clear button |
| `core/includes/_tracking_button.html` | the three-state tracking dropdown, and `_tracking_button_template.html`, its clone twin |
| `core/includes/_status_filter.html`, `_mobile_filter_status.html` | the tracking status filter, games and music alike since 2026-10-29: each option shows its button's mark in its colours (`GAME_STATUS_OPTIONS`, `LISTEN_STATUS_OPTIONS`) |
| `core/includes/_saved_filters_dropdown.html`, `_saved_filter_modals.html`, `_mobile_saved_filters.html` | saved filter combinations, in the sidebar and the sheet |
| `core/services/titles.py` | the heading's wording: `join_names`, `build_time_window` |
| `core/services/ranking.py` | `rank_distribution`, the chart's binning |
| `core/js/filter-subcomponents.js` | `yearGridComponent`, `genreFilterComponent` and their mobile forms |
| `core/js/media-list-controls.js` | `mediaListControls`, `entityListControls` |
| `core/js/media-search.js` | `createMediaSearchData`, for a section's search box |
| `core/js/media-tracking.js` | `MediaTracking`, which keeps the tracking id Sets current after a button swap |
| `core/includes/_quick_mark_picker.html`, `core/js/quick-mark.js` | quick-mark mode: one click applies a picked status (see "Album tracking") |
| `core/js/media-list-controls.js` | also the saved-filter state and methods, inert without a `savedFiltersUrl` |

The templates are the contract. Each binds to an Alpine component exposing
`filters`, `genres`, `initialized`, `debouncedFilterUpdate()`,
`handleFilterChange()`, `updateSort()`, `toggleSortDirection()`, `viewMode`
and `setViewMode()`. Games satisfies it with `filterComponent`, which also
owns platforms, series, playtime and saved filters; music satisfies it with
`mediaListControls`, which writes the state into its HTMX form and announces
a `change`. **Add a control to the shared template, not to one page.**

Row and card styling is shared the same way but through CSS selector lists -
`.game-row, .media-row { ... }` - because each section's JavaScript queries
its own class names. One rule block, both families; a fourth copy of the
`.game-row` rules is what left album rows without a hover state.

A selected year range reads as one shape, and fades as one, because each tile
carries four generated boxes in the primary colour: its fill over the heatmap
colour, the gaps to its right and below, and the corner between them
(`::before` and `::after` on the tile and on its label). All four fade
`opacity`, which runs off the main thread in every browser. A filter change's
list render blocks that thread, so a fade on it waits: with box-shadow gaps, and
again with `background-color` on the boxes, Clear finished the tiles at ~220 ms
and started the gaps at ~550-640 ms (4x CPU). Text colour changes at once for
the same reason. Square corners are the fill's, and the tile under it stays
round: a corner squares up at once and rounds off only when the fade is over,
since rounding it while the fill and gaps were solid opened a star at every
join. The gaps take 100 ms of the fill's 150, leaving first and arriving last.
In exact step they still looked as if they lingered: at 127 ms of a Clear the
tile was `147,139,79`, already tan, and the gap `169,192,186`, still green,
because the primary colour stays itself over the page background and turns
muddy over the heatmap. 80 ms overshoots, and the range falls apart before it
fades. Each gap has one owner because two half-opaque fills stack, and that is
why `yearExists` counts the zero-count years `buildDecades` fills in. The gap
boxes reach a pixel past the gap, and a fill a pixel past its tile on each side
it shares, once it has arrived: meeting exactly left a hairline at every join at
any fractional display scale (browser zoom 110%, Windows at 125%), and 1x and 2x
hide that. A range is
`.is-in-range`, not the shared `.is-selected`, whose ring and tint only source
order would keep off. Measure all this from real frames after a real click, and
look at them: freezing a transition takes the threads out of the picture, and a
matching percentage is not a matching colour. Pinned by
`core/tests/test_static_bundles.py::YearGridGapsFadeWithTheirTilesTests`.

Facet counts (the number beside a year cell or a genre row) are counted with
their own dimension left out, so an option never leads to an empty page:
`apply_album_filters(..., skip=("year",))` server-side and
`AlbumFilterEngine.facets()` in the browser. Both publish the same
`year-counts-update` / `genre-counts-update` events the subcomponents listen
for, so neither side knows which did the counting.

### Music client-side filtering

The album rankings page filters in the browser. `/api/all/` on the music host
(`music-api:album-all-data`) returns the whole corpus
(1000 albums, ~270 KB of JSON, 95 KB gzipped), the bundle holds it in
`sessionStorage` keyed by the data version the page renders into itself, and
`music/static/music/js/` filters, sorts and renders locally. There is no
IndexedDB layer and no `version/` endpoint: at this size neither pays for
itself.

It is progressive enhancement. The page is server-rendered and its HTMX sidebar
filters server-side on its own; the bundle suppresses those requests only once
it has data and a renderer, so a failed or slow bundle leaves a working page.
Load More, jump-to-rank and the list/grid toggle all work either way: the
engine seeds itself from what the server rendered (`attach()` and
`_syncRendererWithPage()`) rather than re-rendering the page on load.

Two payload fields exist to keep the client and the server agreeing exactly:

- `nn` is `name_normalized`, the `unidecode(name)` column the server's `q`
  searches alongside `name` and `artist_credit`. Sent rather than recomputed,
  because reimplementing unidecode in the browser would be a second copy of the
  rule that drifts.
- `ni` is the album's position in the server's own `Lower(name)` ordering. No
  JavaScript comparator reproduces a database collation: `localeCompare` files
  "Ágætis byrjun" next to the A's while SQLite sorts it past Z, and punctuation
  is weighted differently again. The client sorts alphabetically by this
  integer, which also stops local SQLite disagreeing with production Postgres.

The "Release Date" sort (`?sort=year`, kept for old links and saved filters)
is `year_released`, then `release_date` within the year (undated last in both
directions), then rank - `RELEASE_ORDER` in `music/views.py`,
`_compareReleaseDates` on the client, which reads the payload's `rd`. The
year leads because it is the published one every filter and row shows.
`Album.release_date` is derived from Wikidata P577, else MusicBrainz's first
release, by `music.services.release_dates.refresh_release_dates` at the end of
any `fetch_album_metadata` run with a Wikidata or MusicBrainz pass. An album
an import adds has none until that run, as it has no genres; a kept album
keeps both.

`release_date_precision` ("day", "month", or blank) matters because a
month-precise date is stored as the 1st: the artist page's rows show
"May 16, 1966" only for "day", else "May 1966" (`release_date_label`, passed
to the row as `year_text`). Blank reads as a month - it is what a Wikidata row
fetched before the precision was stored carries until its next pass.

The genre filter expands a selected genre to its descendants on both sides,
as `games.services.query_filters.apply_genre_filter` does: picking "Rock"
means rock, including the Discogs styles filed under it. `expand_genre_ids`
does it server-side and `AlbumFilterEngine._expandGenres` in the browser,
from the descendant ids the payload already carries.

The count beside a genre is a **distinct** count across that genre's whole
subtree, so it is exactly what selecting the row gives. Summing a root and
its children instead - which is what the shared tree does when a section does
not supply subtree counts - double-counts an album tagged both "Classical"
and "Modern Classical", and the sidebar claimed Classical had two albums when
it had one. Music passes `genre_counts_include_descendants` to turn the
summing off.

The parity check is automated, for music and games alike:
`core/tests/test_filter_parity.py` renders a spread of filter and sort
combinations on the server, runs the real engine files under Node on the same
data (`core/tests/js/filter_parity.js`), and requires the same order. Unit
tests cannot catch a divergence here, because both sides can be
self-consistently wrong. On its first run it found games' name sort comparing
with `localeCompare` against the database's collation. Games now send `ni` as
music does, and the server sorts by `Lower(name)`. The test skips where Node
is missing; CI's runners have it. Add a query there when adding a filter or
a sort.

### Album tracking

`ListenedAlbum` / `WantToListenAlbum` mirror games' `PlayedGame` /
`WantToPlayGame`, with four deliberate differences:

- **The button is one shared partial.** Games and books each carry their own
  near-identical copy; `core/includes/_tracking_button.html` takes the verbs,
  icons and route as parameters and `music/includes/_listen_button.html` is a
  thin wrapper supplying music's. It resolves the route **positionally**
  (`{% url toggle_url_name item.id %}`) because `{% url %}` cannot take a
  dynamic kwarg name - so a section's toggle route must take the item's pk as
  its one positional argument. Games and books are unchanged and can migrate.
- **No inline sync script.** Both other sections ship a `<script>` *inside*
  every swapped partial, which mutates the global Sets and then deletes its
  own earlier copies so they do not pile up. `core/js/media-tracking.js` is
  one delegated listener instead, and a page registers what its scope means.
- **The toggle is atomic.** The delete and the write run in one transaction
  and the write is an `update_or_create` keyed on the `unique_together`, so a
  double-click cannot race into an `IntegrityError` - and a row orphaned when
  a release dropped its album is re-adopted on the spot. The cache is dropped
  after the block commits, so a rolled-back write cannot clear it.
- **Nothing per-user goes in `/api/all/`.** That payload is held in
  `sessionStorage` keyed only on its version, so two people sharing a browser
  session share it. The client joins on the album pk, which the payload
  already carries, and the page renders `window.listenedAlbumIds` /
  `window.wantToListenAlbumIds` per request - so there is no new payload key
  and no `SCHEMA_VERSION` bump.

Two traps worth knowing, both of which only appear in a real browser and are
now pinned by `core/tests/test_media_tracking.py` and the source tests in
`music/tests/test_tracking.py`:

- **`htmx:afterSwap` is too early to read the new state.** With
  `hx-swap="outerHTML"` the swap *replaces* the target, so `detail.target` is
  by then the detached old element, still carrying its pre-swap
  `data-status`. `media-tracking.js` listens on `htmx:afterRequest` and takes
  the new status from the request's own `?status=`.
- **The client-side filter suppressor must only cancel GETs.**
  `album-client-filtering.js` cancels HTMX requests once the engine can answer
  them locally, with listeners on the form and on
  `#album-results-container`. Every row sits inside that container, so a
  row's toggle POST bubbles through the same listener - and cancelling it made
  the button do nothing at all, but only once the bundle had loaded, which is
  why it looked intermittent.

Two filter vocabularies, as games has: `?listened=own|yes|want|no`
(multi-select, comma-joined) for filtering, and `?status=own|listened|want|none`
for the toggle. `?listened=yes` reads correctly in a URL and
`data-status="listened"` reads correctly on an element;
`music/config.py:LISTEN_STATUS_OPTIONS` maps the two server-side and the scope
registry in `media-tracking.js` does client-side.

**Four exclusive states: Have, Heard, Want, Untracked.** Have was added
(2026-10-19) for readers who track what they own rather than what they have
heard, and "Listened" was relabelled "Heard" at the same time. The internal
spelling kept `listened` / `yes`, so old links, saved filters and
`mark_albums_listened` still mean "heard". Each state is exactly one thing
everywhere: `is_owned_by_user` and `is_listened_by_user` annotate
`owned=True` and `owned=False` rows respectively, `?listened=yes` leaves owned
albums out, and the page renders three disjoint Sets (`ownedAlbumIds`,
`listenedAlbumIds`, `wantToListenAlbumIds`), which `media-tracking.js` keeps
current through a status-to-Set map. The reconnection merge keeps `owned` if
any merged row had it. Have and Heard are illustrations, as games' Played is
its Mario Star: a gold record for Heard, and for Have that record sliding out
of its sleeve, so they differ by shape and not only colour
(`music/static/music/images/`). The shared button, its clone twin, the status
filter and the quick-mark picker take a static `image` in place of an icon
class. Untracked is `mdi-record-circle-outline`, and Want that empty record
with a plus, as games' Want is `mdi-star-plus-outline`: MDI has no record
with a plus, so `mdi-record-plus` is an SVG mask in `styles.css`, filled
with the text colour.

**Quick-mark mode.** A "Mark" button opens a menu of Have, Heard, Want,
Clear and Off (games: Played, Want to Play, Clear, Off). With a mode picked,
one click on a tracking button applies that status, and a click on an item
already in it clears it. The button shows the mode's icon and is tinted while
one is on. It is `core/includes/_quick_mark_picker.html` and
`core/js/quick-mark.js`, which both rankings pages push onto
`window.alpineScripts`. On desktop `_media_list_controls.html` includes it
when the page passes `quick_mark_scope` and `quick_mark_options`, on the
right beside jump-to-rank. That row is a three-column grid
(`minmax(max-content,1fr) minmax(0,1fr) minmax(max-content,1fr)`), so the
count sits at the true centre. Below xl, words give way to icons (Asc, the
Mark label), and a container query hides the count once the middle column is
too narrow for it, rather than truncating it to a stray letter. On mobile
it sits beside the Filters button, because the controls row is already full
at 360px. It was first a strip of five buttons in the results header, which
crowded that row. Four things it depends on:

- The mode is per scope in `localStorage` (`quickMark:<scope>`) and acts only
  while a picker for that scope is on the page, so detail pages keep the menu.
- Its click listener **captures**, for the same reason the played menu's
  does: the button's Alpine handler would open the menu and the wrapper stops
  propagation in the bubble phase.
- It ignores `event.detail >= 2`: the second click of a double-click would
  otherwise undo the first.
- It posts with the wrapper as source and target, to the wrapper's
  `data-toggle-url` (games: the played menu's `data-url`), so the swap goes
  through the same path as a menu choice. Games' `played-menu.js` asks
  `QuickMark.active('game')` before opening its shared menu.

Per-user cache keys cannot live in `CACHE_KEYS`, which is a flat tuple an
import iterates. They are templates in `PER_USER_CACHE_KEY_TEMPLATES`, dropped
by `caching.invalidate_listen_caches(user_ids)` on a toggle and from the bulk
command below, and `invalidate_release_caches(user_ids)` on an import, the only
three moments they can go stale.

**The Account modal shows a reader's albums** beside their games, the current
site's block first, on any host (`music.services.listening_stats`). Its rank
counts Have and Heard together, and so
says "tracked" rather than "heard", which would be false of a reader who only
marks what they own. The rank logic is `core.services.percentile`, shared with
games: a percentage compares a reader with everyone else, "top 1%" counts those
level with or ahead of them, so a tie cannot claim it, and a leader or someone
near the bottom gets a position instead, "tied for" when it is shared, since
"more than 95%" undersells the first and "more than 0%" says nothing to the
second. `CACHE_KEY_LISTENER_COUNTS` is one global key, in `CACHE_KEYS` for
an import, and `invalidate_listen_caches` drops it too, for a toggle or the bulk
command. An admin edit or a deleted user waits out its
one-hour TTL; games' signals cover those, and music has none yet.

**Marking a collection in bulk**, for importing listens matched elsewhere
(a RateYourMusic export, say) without several hundred web requests:

```bash
python manage.py mark_albums_listened --user <name> --ids Q212863,Q19003
python manage.py mark_albums_listened --user <name> --ids-file ids.txt --dry-run
```

The matching stays outside the command. Deciding that an export's
"E·MO·TION" is our "Emotion" is a judgement call for whoever is looking at
both lists; the command takes the Wikidata ids that judgement produced and
does only the database half, with the toggle's own semantics - one
transaction, `update_or_create` on the `unique_together`, any
want-to-listen row for the same album cleared, and the per-user caches
dropped on commit. An id already marked is left alone, so a mark the user
made themselves keeps its `created` timestamp, and ids are matched against
every id an album carries rather than just the primary one.

**The User admin shows all five tracking counts** (played, want to play,
have, heard, want to listen) with a read-only capped list of each. Have and
Heard are both `ListenedAlbum` counts, split on `owned`, and the
`ListenedAlbum` changelist filters on it, since Have has no table to find
in the admin sidebar. The counts
are correlated subqueries, not `Count("relation", distinct=True)`: four
multi-valued joins on one queryset multiply, and a user with 822 listened
albums and 178 want-to-listen rows produced 146k intermediate rows before
`distinct` collapsed them again.

### Saved filters

A reader who has built up a genre + decade + listen-status combination keeps
it by name. Games has had this since `SavedFilterSet`; music's was built as
**shared `core/` components with music wired to them**, the way album
tracking was - games is untouched and can migrate by swapping three
includes.

| Piece | Where |
|---|---|
| `core.models.SavedFilterSetBase` | abstract: user, name, `filters` JSON, created/modified, `-modified` ordering |
| `music.models.SavedAlbumFilterSet` | the concrete table; adds nothing |
| `core/includes/_saved_filters_dropdown.html` | the sidebar "Saved" menu |
| `core/includes/_saved_filter_modals.html` | save / rename / delete, one copy per page |
| `core/includes/_mobile_saved_filters.html` | the bottom sheet's collapsible equivalent |
| `core/js/media-list-controls.js` | the state and the eight methods, named as games' are |
| `/api/saved-filters/` (music host) | list, create, rename, delete |

The partials bind to a **method contract**, not to a page:
`loadSavedFilters`, `applySavedFilter`, `saveCurrentFilters`,
`submitSaveFilter`, `renameSavedFilter`, `submitRenameFilter`,
`deleteSavedFilter`, `confirmDeleteFilter`, plus `hasActiveFilters` and
`savedFilters*`. Both `mediaListControls` and games' `filterComponent`
expose exactly those names, which is what makes the migration a template
change. The whole feature is inert unless the page passes a
`savedFiltersUrl`, so a section that has not opted in renders no button.

Four things worth knowing before changing any of it:

- **Applying a saved filter must not announce `year-reset` or
  `genres-reset`.** Those events do not mean "refresh yourselves":
  `core/includes/_mobile_filter_time.html` answers `year-reset` by assigning
  the full year range and `_mobile_filter_genres.html` answers
  `genres-reset` by assigning `[]`, and **the mobile sheet shares the
  rankings page's Alpine state at every width, desktop included**. So
  dispatching them after restoring a combination wiped it: the sort and its
  direction survived while the genre and the years were silently dropped,
  and the heading went on naming the unfiltered page. The grid and the tree
  derive their selected state from `filters` reactively and need no
  telling. Pinned by
  `core/tests/test_static_bundles.py::ApplyingASavedFilterMustNotAnnounceAResetTests`.
- **`applyingSavedFilter` was a hook with nothing on the other end.**
  `core/includes/_year_grid.html` has always passed `isApplyingSavedFilter`
  behind a `typeof` guard, so a component without the flag silently got
  `false` and the grid treated a programmatic range as a hover preview.
  Defining it on `mediaListControls` lit the hook up with no template
  change - and the guard is why its absence could never throw.
- **This is music's first *write* endpoint**, so CSRF applies to
  `music/api/` for the first time; `MusicWriteAPIMixin` sits beside
  `MusicReadAPIMixin` to say which views that covers. A signed-out caller
  gets games' 403. The ordinary Django test client does not enforce CSRF, so
  `music/tests/test_saved_filters.py` uses
  `Client(enforce_csrf_checks=True)` for the real answer.
- **Deliberately uncached**, and `music/config.py` says so where a reader
  would otherwise expect a `CACHE_KEYS` entry: the rows are per-user, read
  once when the dropdown first opens, and written by the person about to
  re-read them.

`SavedAlbumFilterSet` needs no reconnection pass after an import, unlike the
tracking models - a saved filter references genres by id, and an import
replaces albums, not genres.

**Games' `applySavedFilter` never restored `sortDirection`**, though
`submitSaveFilter` had always stored it, so applying a saved "Year, newest
first" quietly came back ascending. Fixed on both sides, and pinned in
source and minified form, because the page loads only the minified copy.

### Template Architecture

The application uses Django templates with server-side rendering:
- **Production**: Uses Django's cached template loader for optimal performance
- **Development**: Uses non-cached loaders for hot-reloading during development
- Templates configured in `settings.py` based on `DEBUG` mode
- Game templates are in `games/templates/`
- Book templates are in `books/templates/` (feature-flagged)
- Shared templates are in `core/templates/`

## Application Structure (Django + HTMX + Alpine.js)

The application uses Django templates with HTMX for dynamic interactions and Alpine.js for client-side reactivity.

### Views and Templates

- **games/** - Main Django app containing:
  - **views/** - Views for all routes, one module per page family
  - URL routing is `acclaimedgames/urls_games.py`, with the shared routes in `urls_common.py`
  - **templates/** - Django templates organized by feature:
    - **base.html** - Main template layout with navigation
    - **games/** - Game list, detail, and search templates
    - **developers/** - Developer list and detail templates
    - **lists/** - Lists and results templates
    - **posts/** - Post/news templates
    - **pages/** - Static page templates
  - **templatetags/** - Custom template filters (game_filters.py)
  - **middleware.py** - HTMXPushURLMiddleware for HTMX history support

### Application Features

**Styling:**
- Uses Tailwind CSS v4 with DaisyUI v5 component library
- Light theme (lofi) as default with forest dark theme available via theme switcher
- Responsive design using Tailwind's mobile-first breakpoints (md:, lg:, etc.)
- Custom components defined in `theme/static_src/src/styles.css` using Tailwind's `@layer components`

**Template Filters:**
- `from_now` - Converts datetime to relative time (e.g., "2 hours ago")
- Custom utilities for formatting and string manipulation

**Routes:**
- `/` - Home page (games)
- `/games/` - Game list with filtering and search
- `/games/<slug>/` - Game detail view
- `/games/search/` - Game search endpoint (HTMX)
- `/developers/` - Developer list with game counts and hierarchy
- `/developers/<slug>/` - Developer detail view with subsidiary hierarchy and games
- `/lists/` - Published rankings list (with media_type filter)
- `/posts/` - News and blog posts
- `/page/<slug>/` - Static pages

Book routes (behind `BOOKS_ENABLED` feature flag):
- `/books/` - Book list with filtering and search
- `/book/<slug>/` - Book detail view
- `/authors/` - Author list with book counts
- `/authors/<slug>/` - Author detail view with books

Music routes, on `music.acclaimedmedia.org` (they were under `/music/` at
the apex until 2026-10-30):
- `/` - Album rankings with HTMX search, year/artist/genre filters and sorting
- `/<slug>/` - Album detail with list appearances grouped by list type
- `/artists/` - Artist list with album counts
- `/artists/<slug>/` - Artist detail with ranked albums
- `/lists/` - The published source lists behind the rankings
- `/import/` - Staff import for the three release files. Linked from nowhere,
  staff included: staff type the URL
- `/<album_id>/toggle-listened/` - POST, `?status=none|want|listened|own`,
  answering with the re-rendered button for HTMX to swap
- `/cover/<release_mbid>/<image_id>-<size>.jpg` - Cover art served from our own
  store, cached a year and immutable
- `/genres/<slug>/` - A root genre's rankings (SEO landing page)
- `/<decade>s/` - A decade's rankings (SEO landing page)
- `/browse/` - Index of the landing pages
- `/api/...` - the music API (`music-api:`), listed under "API Architecture"

Album detail is the catch-all `/<slug>/`, so every fixed first segment on the
music host - music's own routes and the shared ones (`accounts`, `admin`,
`api`, `page`, ...) - is in `music.config.RESERVED_ALBUM_SLUGS` (and a decade
shape in `RESERVED_ALBUM_SLUG_PATTERN`), which `Album._build_unique_slug`
treats as taken. A test walks `urls_music` and fails if a route is added
without reserving its segment.

**Music landing pages** are games' `/games/<genre>/` and `/games/<decade>s/`
for albums: `MusicLandingPageView` subclasses `AlbumHomePageView` and injects
the path's filters into `request.GET` - in `render_rankings()`, not `setup()`
as games does, so the cache batch covers the injection.
Root genres with a directly tagged album and at least `MIN_GENRE_ALBUMS`
across their subtree qualify, and decades with `MIN_DECADE_ALBUMS`; the
lists are cached under `CACHE_KEYS`. They are self-canonical, carry an
ItemList (`core.services.seo`), and are discovered through the sitemap
only - no nav, badge or footer link, as for games. No year pages: album
slugs such as `1999` already own those paths. The client pushes every
filter change onto `window.albumRankingsUrl` (`/?...` on the music host)
rather than the current path, and both popstate readers read a landing
page's bare path as `window.albumLandingSearch` - otherwise clearing the
genre on `/genres/rock/` pushed the rock URL back. The album renderer builds
every link from `window.albumRankingsUrl` too (`_musicPath`), so no script
spells a music path.

**Navigation:** the sidebar, top to bottom, is the site menu
(`core/includes/_site_menu.html`: "Acclaimed Media" over the current site's
name, opening in place to Games, Music and All sites, absolute links through
`{% site_url %}`; a `<details>`, so it needs no Alpine, and `base.html`
closes it on an outside click or Escape), the site's own links (`core/includes/_sidebar_nav.html`:
Rankings, Developers, Source Lists and Blog for games; Albums, Artists and
Source Lists for music), its search, and the shared bottom block - account,
Donate, About / FAQ, Contact, theme, socials. `media_type` comes from the
host (`games.context_processors.media_type`), so a shared page such as About
keeps the sidebar of the site it was opened on. Staff pages - both import
pages - are linked from nowhere. The games mobile bar has a Music icon and
music's a Games icon.

**Access:** music is public. Reads are open to everyone; the listen toggle
answers a signed-out visitor with games' login redirect and the saved-filter
API with games' 403; `/import/` is staff-only, behind
`core.mixins.StaffOnlyMixin`.

- Books still uses `core.mixins.StaffOnlyMixin` / `core.permissions.IsStaffOrHide`.
- Music is a beta, and says so everywhere while `music.config.MUSIC_BETA` is
  on: a notice with a feedback link at the top of every page on the music host
  (`music/includes/_beta_notice.html`, from `base.html`), and a "Beta" badge
  (`music/includes/_beta_badge.html`) on every music heading and on every
  way in - the site menu (on music, beside the site's own name), the games
  mobile bar's Music icon, and the landing page's Music card, which also
  says it in words. Turning `MUSIC_BETA` off removes them all.
- Artist slugs have no redirects, by decision (2026-10-30): every import
  rebuilds them from the current names (see "Music Data Import"), so a renamed
  act's old links 404 until an `ArtistSlugHistory` is built.

**HTMX Integration:**
- Dynamic filtering without full page reloads
- Pagination for lists with smooth navigation
- Real-time search results
- Smooth form submissions

**Alpine.js Interactivity:**
- Client-side state management for UI components
- Dropdown menus, modals, and toggles
- Form validation and user interactions

### Middleware

**HTMXPushURLMiddleware**: Provides HTMX support for browser history:
- Pushes URLs to browser history when HTMX requests complete
- Maintains browser back/forward functionality with HTMX
- Uses `HX-Push-Url` header for selective history updates

### Google Analytics Integration

The site uses Google Analytics 4 (GA4) with custom HTMX tracking for comprehensive page view analytics:

**Implementation Location:** `games/templates/base.html`

**Standard Page Views:**
- gtag.js loads on every page via base template
- Tracks initial page loads and full navigation
- Property ID: `G-0591405Q89`

**HTMX Navigation Tracking:**
- Custom event listener on `htmx:afterSwap` tracks partial page updates as page views
- Includes full URL path with query parameters for granular tracking
- Captures filter changes, pagination, and search navigation
- Provides more detailed tracking than typical SPAs (tracks query parameter changes as distinct page views)

**Code Example:**
```javascript
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Track HTMX navigation as page views
    if (window.gtag) {
        gtag('config', 'G-0591405Q89', {
            page_path: window.location.pathname + window.location.search
        });
    }
});
```

**Advantages over SPA Tracking:**
- Automatically tracks all filter state changes (e.g., `/games/search/?q=zelda` vs `/games/search/?q=mario`)
- No custom router configuration required
- Simpler implementation with more granular insights

### Development Notes

- Template reloading works in development via Django's non-cached template loaders
- In production, template caching is enabled for performance

### Home Page Client/Server Rendering Consistency

The home page game rankings use a **dual-rendering architecture** that requires careful coordination:

**How It Works:**
1. **Server-side rendering**: Django templates render game rows with actual data on initial page load
2. **Client-side rendering**: JavaScript clones `<template>` elements and fills them with data for filtered/paginated results
3. **Single source of truth**: The same Django templates (`_game_row_desktop.html`, `_game_row_mobile.html`) serve both purposes
4. **Grid cards are client-only**: `_game_card_grid.html` is rendered solely into `#grid-card-template`; the server sends rows and the bundle builds the grid (see "Rankings page weight" under "Production memory budget")

**Template Structure:**
- When `game` context is provided → server renders with data
- When `game` is absent (inside `<template>` tags) → renders empty structure with `data-slot` attributes for JS

**Files That Must Stay In Sync:**

| Server-Side (Python/Django) | Client-Side (JavaScript) |
|----------------------------|--------------------------|
| `games/templates/games/includes/_game_row_desktop.html` | `games/static/games/js/game-list-renderer.js` |
| `games/templates/games/includes/_game_row_mobile.html` | (fallback string methods: `_renderDesktopRowString`, `_renderMobileRowString`) |
| `games/templatetags/game_filters.py` | `_platformFamilies`, `_familyInfo` objects |
| `music/templates/music/includes/_album_row.html` | `music/static/music/js/album-list-renderer.js` |
| `music/templates/music/includes/_album_card_grid.html` | `AlbumListRenderer._renderGridCard` |
| `games/templates/games/includes/_game_card_grid.html` | `GameListRenderer._renderGridCard` |
| `core/templates/core/includes/_base_media_row.html` | `core/static/core/js/base-renderer.js` |
| `core/templates/core/includes/_tracking_button_template.html` | `AlbumListRenderer._renderTrackingButtonDOM` / `TRACKING_SLOTS` |

Music renders one partial for both halves: `_base_media_row.html` takes a
`row_variant` of `'desktop'` or `'mobile'` so `music/home.html` can put each
half in its own `<template>`, which is what `BaseMediaListRenderer`
`_initTemplates` expects. The renderer declares the slots it fills in
`AlbumListRenderer.SLOTS`, and `music/tests/test_visual_regression.py` checks
the template still emits every one of them - **including when the row is
rendered with no album**, which is how a `<template>` is rendered. A slot
placed inside `{% if item.something %}` disappears from the clone and the
renderer silently has nowhere to write.

**When Modifying Game Rows:**
1. Update the Django template for server-rendered output
2. Update the JavaScript renderer's DOM-cloning logic (uses `data-slot` attributes)
3. Update the JavaScript fallback string-rendering methods to match
4. Ensure `PLATFORM_FAMILIES` and `FAMILY_INFO` constants match between Python and JS

**Key Data Slots:** `rank`, `global-rank`, `thumbnail`, `name`, `year`, `title-link`, `thumb-link`, `year-link`, `meta-row`, `platforms`, `genres`, `list-count`, `primary-developer`, `played-button`

**Testing:** After changes, verify both:
- Fresh page load (server-rendered)
- Filtered results (client-rendered via JS template cloning)

## IGDB Integration

The `games/igdb.py` module handles IGDB API integration with multiple optimization strategies:

### Features

**Field Expansion**: Reduces API calls by 3-5x by expanding cover and genre data in the main game query instead of making separate requests.

**Concurrent Requests**: Process multiple games simultaneously (up to 8 concurrent requests) for 4-8x speedup.

**Multi-Query Batching**: Fetch multiple games per API request (10-50 for free tier, up to 500 for Pro tier) for additional 3-5x speedup.

**Pro Tier Support**: Access IGDB Pro tier with 750x faster rate limits (3,000 req/sec vs 4 req/sec).

**Thread-Safe**: All caching and rate limiting is thread-safe for concurrent processing.

IGDB provides cover art, descriptions, developer information, and genres.

For detailed command usage, run `/igdb`.

## HowLongToBeat playtimes

Rows, cards, the playtime sort and filter show HLTB's **Main Story** average,
or **100%** with the toggle; Main + Extras appears only on the detail page and
in the CSV.

**Open-ended games show no playtime.** For League of Legends, World of
Warcraft or Rocket League, HLTB's averages are time invested, not time to
beat. They put a 1162-hour MOBA at the top of "longest" and a five-hour
car-football game under "short". `HLTBGameData.is_open_ended` is derived in
`save()`: the staff call in `open_ended_override`, else HLTB's own
`game_type` (`multi`/`endless`/`sports`, read from the raw search row by
`fetch_hltb_data.entry_profile`). `games/services/playtime.py` is the one
place that applies it: the sort, the filters and their counts,
`/api/games/all/` (null `pt`/`ptc`), the `hltb_hours` tag, the `shown_hltb`
filter on the row `{% with %}`, the backlog total and the CSV. The detail
page keeps the numbers under a "No finish line" line.

**The calls are made in the admin**, on the HLTB record: the override's help
text states the test (does the game have an ending that HLTB's Main time
measures?), and the HLTB changelist has bulk "Mark open-ended / Mark
finishable / Clear the call" actions; the Game changelist shows the result
as a read-only "Open-ended" column, with a filter for games HLTB has not
matched (which cannot carry a call yet). A call reaches visitors within the
hour: cached pages expire in 5 minutes, `/api/games/all/` in an hour. If
IGDB re-keys a game, the fetch gives its new HLTB row the old row's call.
HLTB files most sandbox, sports and
arcade games as ordinary "game"s and some co-op story games as "multi", so
about 190 calls were made by hand; migration `0120` moved them there from a
list in code (`games/open_ended.py`, deleted). The call lives on the HLTB
record, not on `Game`, because a games import recreates every `Game` while
HLTB rows survive it and every refresh. A game with no HLTB row yet cannot
be marked until HLTB matches it. `comp_lvl_combine` is stored but not used:
production's first full refresh showed it marks any game with a co-op or
versus mode (Sam & Max, Gunstar Heroes), and it was hiding story games.
Never `.update()` the override or `game_type` without re-saving, which
re-derives the flag.

The weekly `refresh_all_metadata` refetches every game and so fills in the
flags. HLTB answers a burst with 429s; a failed lookup leaves the row as it
was. The `/api/games/all/` version hash fingerprints the playtimes it serves
(summed hours, and the ids of open-ended games). An HLTB save leaves
`Game.modified` alone, and the weekly refresh saves every row whether or not
anything changed, so `updated_at` would make every visitor re-download the
data each week.

## Forum (removed)

The community forum (django-machina) was removed on 2026-10-17; a hosted
provider will cover that need instead. Migration `0115_drop_machina_tables`
dropped its 14 tables, content types, permissions, the "Forum Moderators"
group and machina's `django_migrations` rows, so nothing of it remains in the
schema. `Publication.reputation_score` survives as staff-edited editorial
metadata, now display-only.

## Music Data Import

The album rankings come from four TSV files, three of them the same shape the
games importer takes (`acclaimedgames/test_input_files/music/` holds the current
release):

| File | Columns |
|---|---|
| `ArtistInfo.txt` | id, wikidata_ids, name, then any further name variants |
| `ListData.txt` | publisher, year, type, name, url |
| `WebRankings.txt` | rank, name, credits, year, wikidata_ids |
| `ListPositions.txt` | tab-separated `listIndex:position` pairs, one row per album in rank order |

```bash
python manage.py import_music_data            # uses the checked-in release files
python manage.py import_music_data --dry-run  # list types, name variants, artists removed, albums kept/added/removed
python manage.py import_music_data --artists ... --lists ... --albums ... --positions ...
```

The import runs in one transaction, artists first. Lists, list positions and
credits are replaced; artists and albums are updated in place. Four details
differ from the games files:

- **The list type is validated.** Column 3 is All Time, Decade, EOY or Misc,
  as in the games file, but an unknown word fails the import with its row
  number where games stores whatever letter it starts with
  (`parse_lists_file`). Until the 2026-10-29 release the file had no type
  column and the types were guessed from the titles, which filed "The
  AllMusic Decade in Review" as all-time; a file in that layout now fails
  with a message saying so.
- **Artists are the provider's, by id.** `ArtistInfo.txt` lists every act
  under a permanent index (sparse), then its Wikidata ids (comma-separated,
  optional, read with or without the `Q`), then its names. `WebRankings.txt`
  column 3 is `artist,variant` pairs separated by `;`, in credit order, and
  `VA` last for various artists - see "Artist name variants" below.
  `Album.artist_credit` is derived from the credited names as "A", "A & B",
  "A, B & C", with "Various Artists" as a last name (`credits.credit_text`).
  Either file in its pre-2026-10-28 layout fails with a message saying so.
- **Artists are upserted, not replaced.** Matched on `source_id`; a row that
  predates the ids is adopted by Wikidata id, exact name, then normalized name,
  so pks survive. **Slugs are not kept**: they follow the current names
  (`music.services.artist_slugs`), rebuilt by every import and again after
  every Wikidata pass, and the admin cannot edit them. Same-named acts are
  told apart the way Wikipedia does it: the one whose English Wikipedia
  title (`Artist.wikipedia_title`, from the enwiki sitelink) is the bare
  name keeps the plain slug, the others take their titles
  ("nirvana-british-band"); with no bare-name title the lowest provider id
  keeps the plain slug, and only an act with no usable title is numbered. Names go through unidecode ("royksopp"). Nothing
  redirects a replaced slug (see "Access"). `--dry-run` lists the slugs that
  would change. An artist the file does not list is deleted,
  with its page.
- **A provider id is permanent.** The import trusts that: a row updates
  whichever artist holds its id. One that shares no Wikidata id and no
  normalised name with what is stored is reported - "may have been reused"
  in the import message, `!` in `--dry-run` - but still imported, since a
  rename can do that too.
- **Albums are upserted, not replaced.** `match_albums` pairs each row with
  the stored album carrying any of its Wikidata ids (`Album.wikidata_qids`,
  the primary and every id in `all_wikidata_ids`), primary id first; an album
  is claimed by one row at most, so a split row gets a new album. A matched
  album has its rank, name, year, ids and credits rewritten and keeps its pk
  and slug - and so its metadata pointers, genres, release date, covers and
  tracking rows. Albums the file drops are deleted (before any are created,
  so a new album can take a dropped one's slug), and a row with no QID is
  always new. The message, `--dry-run` and the staff import page all report
  "N kept, N added, N removed". Until 2026-10-23 every import deleted every
  album, and the next metadata run spent ~22 minutes re-fetching MusicBrainz
  for all of them.

Unranked lists record every member at rank 1, matching the games convention.

**An import re-adopts tracking rows.** A kept album keeps its
`ListenedAlbum` / `WantToListenAlbum` rows outright. An album the release
drops is deleted and its rows wait on `SET_NULL`, so `import_albums` still
runs `music.services.user_tracking_service.reconnect_tracking_records` as the
safety net: when the album comes back it reconnects them by Wikidata id -
normalising a secondary id to the primary and merging two rows that now
point at one album, earliest kept. A row that is already right is skipped,
so its user's caches are not dropped for nothing; the users whose rows a
removal orphaned have theirs dropped instead, since their cached sets name
the deleted pks. `import_batch` drops them with the section's keys, in one
call, once it has committed: dropped inside the transaction, a page load
before it commits would refill them from the old rows. The pass is behind a
one-query existence check, so an untracked database pays nothing.

**An import does not fetch metadata.** A kept album needs none - its rows,
genres and covers never left it - so after a release that mostly repeats the
last, `fetch_album_metadata --with-musicbrainz` skips nearly everything and
finishes in seconds. An added album renders with placeholder artwork and no
genres until that run. An album returning from an earlier release has its
old rows waiting as orphans, and every pass adopts them by external id before
fetching: Wikidata and Discogs by their ids, and covers and MusicBrainz by
`release_group_mbid` through `_musicbrainz_record`, which adopts the *whole*
row - title, dates, genres and cover ids - rather than making an empty one
and letting the cover pass copy only the cover ids across. The games import page
has the same split (its "Metadata Operations" panel, with its own buttons);
music's import page shows what is missing and the command to run. The weekly
scheduled fetch (below) closes the gap by the next Sunday if nobody does.

**A cache error does not fail a committed import.** The release is live by the
time `import_batch` drops the caches, and staff told it failed would re-run
it, so `invalidate_release_caches` logs the error and returns `False`, and
the import returns a warning: an amber alert on the staff page, `style.WARNING`
from the command. The fix it names is `python manage.py clear_music_caches`,
which does only that, readers' sets included, and exits non-zero if it fails
too. `fetch_album_metadata`
and `rebuild_album_genres` get the same protection from
`invalidate_music_caches`, and print the same warning, so a cache error no
longer stops the weekly job before its dates and slugs. If the database connection
itself has died, the staff page's own queries after the import can still fail;
the release stands.

The import stamps `SiteMetadata` under the `music` key, which the rankings
heading reads as "Updated: ...". `SiteMetadata` is keyed per section, so
games and music carry their own dates.

### Artist name variants

Since the 2026-10-28 release an artist carries every name it is credited
under, and a credit names the artist *and* the name: `8,1` is artist 8,
Prince, under name 1, "Prince and the Revolution". Most credits are `,0`,
the artist's own name. This replaced the relation tags of 2026-10-23
(alias/project/collaboration/featuring/backed-by, `ArtistRelation` and an
`ArtistGraph` roll-up), in which Prince and the Revolution was an artist of
its own tagged as a project of Prince; those acts were deleted by the
import, and their pages 404 (music was still the staff beta).

- **An album belongs to exactly the artists it credits**, under whatever
  name, so there is no walk and no expansion: `?artists=` is a plain join on
  both sides, an artist's page and counts come from one read of
  `AlbumCredit` (`credits.album_ids_by_artist`), and "More by" is the credited
  artists. Nobody "appears on" anything any more.
- **The credit line shows the credited name and links to the artist**:
  "Prince and the Revolution" goes to `/artists/prince/`, titled
  "Prince". `artist_links` server-side, `_artistCreditHtml` client-side, from
  the `"cv"` names `/api/all/` sends for the albums that need them.
  Album detail adds an "Artist:" row naming the artist when the credit uses
  another name.
- **`VA` is the last credit**, alone on a compilation and after the named
  artists on a soundtrack ("Jimmy Cliff & Various Artists"). It sets
  `Album.various_artists` (`"va"` in the payload) and is rendered unlinked.
- **Some variants are unused**: kept for albums outside the ranking, or left
  over from the tag system ("The Velvet Underground & Nico" - that album is
  credited to each artist separately). "Also credited as", on the artist
  page and row, and the artist search therefore read the names credits
  actually use (`AlbumCredit.credited_name`, `credits.variant_names_by_artist`),
  not `Artist.name_variants`.
- The release's Wikidata ids describe the artist, not its names, so there is
  not one per name. The first is `Artist.wikidata_id`, which the Wikidata
  pass reads for the MusicBrainz id.
- **Albums credited with other artists are listed apart**, under "With
  other artists" on the artist page and `with_other_artists` in the API
  (`credits.split_by_credit`): Getz/Gilberto on Stan Getz's. A `VA` tail
  names nobody else. They still count, in the total and the chart.
- **No artist pk is public.** The pks were handed out in the provider's
  entry order, which he does not want visible. `?artists=` takes slugs
  only - a pk would let anyone read the order back one link at a time - and
  a hidden form field carries it through later filter changes;
  `/api/all/` keys its artists table by slug and lists slugs in
  `"ar"`; no artist serializer has an `id`. A slug rebuild touches its
  albums' `modified`, so the payload version moves with it.
- The provider mentions a members list per artist for a future "See also";
  no file carries it yet.

The credit line's separators are `credit_separator` on both sides;
`core/tests/test_filter_parity.py` renders every album's line through both
and requires them equal.

The Wikidata pass no longer touches album credits. It reads each artist's
MusicBrainz id (P434) and English Wikipedia title off the artist's own QID
and stores only those.

## Music Metadata Pipeline

Run `/music-metadata` (`python manage.py fetch_album_metadata`) after an import.
Every album carries a Wikidata QID, which supplies the Discogs and MusicBrainz
identifiers the other sources are keyed by, so nothing is matched on title.

Four passes, selectable, because their costs differ by two orders of magnitude:
Wikidata is ~25 batched requests (seconds), cover art ~1000 downloads (~18 min),
Discogs ~500 requests at 25/min anonymous (~23 min), and MusicBrainz ~500 at its
hard 1 req/sec cap (~9 min, opt-in via `--musicbrainz` alone or
`--with-musicbrainz` alongside the rest). Set `DISCOGS_TOKEN` to raise the
Discogs limit (production has one); the client paces itself from the response
headers either way.

**It runs weekly on Heroku Scheduler**, as games' `refresh_all_metadata` does:
a daily job, `python manage.py fetch_album_metadata --weekly --with-musicbrainz
--refresh-stale 125`, where `--weekly` exits at once on any day but Sunday
(UTC) - the add-on has no weekly frequency. It is deliberately not `--force`:
every pass but Wikidata skips records that already landed, so a routine run
costs Wikidata's ~25 requests plus whatever an import left missing, then the
genre rebuild and the cache invalidation - about a minute, nearly all of it
Wikidata's network time. A full re-fetch stays a manual `heroku run:detached`.

`--refresh-stale 125` is the one deliberate re-fetch: the MusicBrainz pass
also re-reads the 125 albums whose rows have the oldest `updated_at`, ~2
minutes at 1 req/sec, so the corpus cycles every eight weeks. Since imports
keep albums in place a MusicBrainz row would otherwise be fetched once and
never again, while its genre tags keep gathering votes; before 2026-10-23 the
orphan bug re-fetched everything after every import, which hid that. Covers
and Discogs are not refreshed: covers do not change, and the Discogs reading
below rests on what we display, not on freshness. Wikidata already re-reads
everything every run.

Decisions worth knowing before changing any of it:

- **A style's root is corrected in place.** `get_or_create_genre` used to
  return an existing genre row untouched, so a style first created under the
  wrong root kept it forever: "Alternative Rock" sat under Electronic for 68
  albums long after the resolution order was fixed, because the fix could not
  reach a row that already existed. It now re-parents a row whose root has
  changed, `level` and `path` with it.
- **Genres are our own vocabulary, voted on by three sources.**
  `music/services/genre_normalizer.py` names every genre the filter offers -
  16 roots and about 125 leaves - and classifies each source label as a leaf,
  an alias of one ("Glam" -> Glam Rock, "thrash metal" -> Thrash Metal), a
  root ("hip-hop", "rock music"), or a label dropped on purpose ("Vocal",
  "Classic Rock"). An unclassified label creates nothing. When every Discogs
  style became a row of its own the tree had 207 leaves, 73 of them holding a
  single album, and an unmapped style took its root from the album's own
  Discogs genres, which filed Bubblegum under Electronic and Son under Jazz.
  Discogs styles are the **base** and are kept whole. Wikidata P136 and
  MusicBrainz genres can only **add**: a leaf another source also names, a
  root two sources support, or a leaf for an agreed root with nothing under
  it. A stricter "two sources must agree" rule was tried and dropped real
  genres, because Wikidata names a single genre for over half the albums
  (*Purple Rain* lost Funk). Leaves held by fewer than `MIN_LEAF_ALBUMS` (3)
  albums are pruned, and their albums keep the root. Wikidata alone is no
  better a source: it has *more* distinct labels than Discogs (272 against
  222), and its P279 graph classified only 159 of 207 genre entities, put
  thrash metal under Rock, and left ska, dub and ambient unreachable.
- **Classifying a label is not free, even when the label is rare.** Discogs'
  top-level genres count as a vote, and they are coarse: "Rock" supports
  Punk and Metal, "Folk, World, & Country" supports World. So one
  MusicBrainz tag read as a World or Punk leaf can tag an album on its own
  ("tejano" as Latin put Marty Robbins under World). Read the per-album diff
  from `rebuild_album_genres --dry-run --report`, not just the counts.
- **The tree stays two levels and single-parent; hybrids tag extra roots.**
  `HYBRID_ROOTS` gives Folk Rock, Country Rock, Synth-pop and a few others a
  second root on the *album*, not a second parent on the genre, so *Harvest*
  is under Rock, Folk and Country, while the shared tree, `genre_tree.py` and
  the client payload keep assuming one parent.
- **Genres are rebuilt offline, corpus-wide.** The passes only store what
  they fetch. `python manage.py rebuild_album_genres` (run automatically at
  the end of `fetch_album_metadata`) derives every album's genres from the
  stored rows in seconds, with no network. `--dry-run --report` shows the
  diff, the pruned leaves and any unclassified label - a new release's new
  labels show up there and fail `RealVocabularyTests`. The rebuild renames
  an alias's row in place, so its id survives, and remaps
  `SavedAlbumFilterSet` genre ids that point at deleted rows.
- **Cover art is downloaded, not hotlinked.** The Cover Art Archive redirects to
  archive.org, which 500s on roughly one request in ten and has a few items
  broken outright, so a hundred-cover page broke visibly on every load. The bytes
  live in `AlbumCover` and `music.views.AlbumCoverView` serves them. Downloading
  doubles as verification, and there are three fallbacks: the release group's own
  art, then any release in the group (earliest first), then a MusicBrainz search
  by title and artist for albums whose Wikidata entity has no P436.
- **A `front` flag is not a sleeve.** The archive tags each image with types,
  and a front can also be `Obi`, `Sticker` or `Spine` (a Japanese pressing,
  shrink-wrap, a cassette J-card) or `Back`/`Medium` (a photo of the whole
  package - "It Takes a Nation of Millions" showed its jewel case and disc).
  `musicbrainz.cover_quality` ranks them; anything short of a clean scan sends
  the pass on through the releases for one, and keeps the best it found
  rather than none. A cassette's J-card is tagged a plain `Front`, so the
  release walk also puts cassette releases last (`inc=media` on the browse).
  An audit of 1000 covers found 27 non-plain fronts, 18 of them harmless
  `Booklet`/`Track` scans. Re-pick an album with
  `--covers-only --force --slug <slug>`, since a stored cover is otherwise skipped.

`Album.cover_image_url` keeps the remote URL for the API, and as the fallback;
`Album.thumbnail` and `Album.image` are what the pages render and prefer the local
copy. `Album.image_og` is `image` made absolute on `CANONICAL_ORIGIN`, for
Open Graph and the JSON-LD.

### Discogs API terms

Discogs' [API Terms of Use](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use)
(last updated 2025-05-27; their site 403s automated fetches, so read it in a
browser) ask for two notices, both rendered and both pinned by
`music/tests/test_discogs_attribution.py`:

- **The non-affiliation notice, verbatim and prominently**: "This application
  uses Discogs’ API but is not affiliated with, sponsored or endorsed by
  Discogs. ‘Discogs’ is a trademark of Zink Media, LLC." `base.html` renders
  `music/includes/_discogs_notice.html` at the foot of every music page.
- **"Data provided by Discogs" directly beside the data**, linking to the
  discogs.com page that holds it, never `rel="nofollow"`.
  `core/includes/_data_credit.html` is the one markup for it. Album detail
  puts it under the genre badges, linked to `Album.discogs_master_url`. The
  list pages put one "Genres use data provided by Discogs" line beside the
  genre filter (the shared `_genre_filter.html` / `_mobile_filter_genres.html`
  take `data_credit_text` / `data_credit_url`, so games shows none) and
  above an artist's albums. Rows and cards carry no per-row credit, which
  would add ~100 links of HTML to every page.

We use no **Restricted Data** (user, marketplace and image data): covers come
from the Cover Art Archive, and genres and styles are not in the restricted
list, so the ban on commercial use of Restricted Data does not bite. The terms
also say content may not be displayed "more than six (6) hours older" than
discogs.com, nor stored "longer than is necessary". Our reading: what the site
displays is its own genre vocabulary, derived by `rebuild_album_genres` from
three voting sources, not Discogs content verbatim; the verbatim
`DiscogsAlbumData` rows are kept as provenance and to rebuild offline. The
weekly Heroku Scheduler job does **not** refresh them: without `--force` the
Discogs pass skips albums that already have a row, so each master is fetched
once and re-fetched only by a manual
`fetch_album_metadata --discogs-only --force`. The reading therefore rests on
what we display, not on how fresh the stored copy is. Revisit this if Discogs
content is ever shown as-is.

## Music and games query budgets

`/music/` cost 443 queries and `/music/artists/` 305, measured against the
1000-album corpus. Both were one-shape N+1s, and both are now pinned by
`music/tests/test_views.py::MusicQueryBudgetTests`:

| page | before | after |
|---|---|---|
| `/music/` | 443 | 26 |
| `/music/?genres=<root>` | 439 | 16 |
| `/music/artists/` | 305 | 6 |
| `/api/music/all/` | 1218 | 10 |

- **`core/services/genre_tree.py` answers the hierarchy in one query.**
  `descendants_by_id(pairs)` maps every genre id to the ids below it from a
  single `(id, parent_id)` fetch. `MusicGenre.get_descendant_ids` still
  exists for one-off use, but nothing on a hot path calls it:
  `prefetch_related("children")` populates only the rows it fetched, so
  recursing into a child instance's own `children` is a query per node.
  The map is returned in **arrival** order, not the post-order the walk
  resolves nodes in, because callers iterate it to build the counts dict
  the page serializes - and that dict's order has to stay the manager's.
  It carries a cycle guard.
- **Deliberately uncached, in both sections.** Music's needs the whole
  table, where ~200 round trips to the shared cache lose to one SELECT of
  200 two-column rows. Games used to cache descendant ids per genre with
  signal invalidation, and that cache went stale: the filter's key
  (`genre_descendants:<id>`) was not one the signal deleted (`:<id>:True` /
  `:False`), so a re-parented genre filtered by its old tree for 24 hours.
  In production the shared cache is itself a Postgres table, so a hit costs
  a query anyway. `games.services.query_filters.genre_descendant_map()` is
  now one uncached SELECT of ~60 rows, and the signal is gone.
- **`ArtistListView` prefetches `albums` with the MusicBrainz row joined.**
  Needed because both row halves read `artist.albums.first` - the mobile
  card block runs it a second time, which is why it was 200 album selects
  for 100 rows. `{% with best=artist.albums.first %}` does resolve off the
  prefetch cache (measured), so no template change was needed.
- **`/api/music/all/` had the worst N+1 on the site and nothing recorded
  it**: the album loop reads `album.thumbnail` while the queryset prefetched
  only `artists` and `genres`, so 1000 albums each lazy-loaded their
  MusicBrainz row.
- **Add a filter dimension here and the facet passes multiply.** Build the
  map once per request - `AlbumHomePageView._descendants` and games'
  `HomePageView._genre_descendants` - and pass it in; every consumer
  (`apply_genre_filter` included) takes an optional `descendants=` and
  builds its own only when called standalone.
- **Games' `/` is pinned by
  `games/tests/test_main_views.py::GamesHomeGenreQueryBudgetTests`.** On a
  cold cache it cost 109 queries, 75 of them `games_wikipediagenre`:
  `get_landing_genres` filters once per root genre, and every filter walked
  `children` a query per node. Now 38, and `/?genres=<root>` 109 -> 39.
  `/api/games/all/` uses `descendants_by_id` too, in place of its own copy
  of the walk.
- **The rest are pinned by growth, not by count**
  (`games/tests/test_query_budgets.py`). Each test renders a page, adds more
  of what it lists, and requires the same query count, so an N+1 fails it
  while an unrelated added query does not. It covers game detail,
  `/developers/` in every sort, `/api/unified-search/`, `/api/games/all/`,
  a decade landing page and `/music/lists/`. Game detail was the one that
  grew: it prefetched one level of each developer's parents, and
  `display_root_developer` queried the rest a level at a time. It now uses
  `with_relations()`, which joins four.

**The games filters are one function**, `games.services.game_filters.
apply_game_filters(qs, params, skip=...)`. It is used by the list, the year,
genre and platform counts (each skipping its own dimension), the CSV download
and the landing pages, as `apply_album_filters` is for albums. The five copies
it replaced had drifted:
- The counts and the CSV searched `name` only, so "pokemon" listed the
  Pokémon games while the counts and the download left them out.
- The counts ignored series and playtime, which the client engine's counts
  always applied, so the server's first render and the client disagreed.
- The CSV ignored the sort.

Facet cache keys hash every filter parameter except the skipped dimension's
(`facet_params`).

## The rankings heading and the tab title

Both sections compose a heading from the filter state and reuse it as the
document title. Two traps, both of which have bitten:

- **A genre clicked in a row does not go through the filter component.**
  `album-client-filtering.js` answers `add-genre` by writing the hidden
  select and re-rendering from the engine. `filters` lives on
  `mediaListControls`, and the heading and the sidebar genre tree are both
  built from it, so the row handler announces `genres-selected` and the
  component listens. Without that the list filtered while the heading went
  on naming the unfiltered page, and a reload "fixed" it because the server
  composes the heading from the URL. Games has no such bug: it routes
  `add-genre` through `component.addGenre`.
  `core/tests/test_static_bundles.py` pins the event name from both ends,
  minified copies included.
- **The document title is not free on either path.** `games/home.html` used
  `seo_title`, which only the SEO landing views set, so the tab title never
  moved. It now falls back to `filter_title`, as music's always did. Nothing
  set `document.title` during client-side filtering in either section;
  `base.html` publishes one `window.documentTitleSuffix` and both filter
  components rebuild `heading + suffix`.

There are no `?v=N` cache-busters to bump. Production's manifest storage
hashes every static name, so changed JS is a new URL, and development
serves static files with `WHITENOISE_MAX_AGE = 0`. Until 2026-10-26, 22
hand-maintained literals did nothing in production; in development the
one-year max-age was what made them necessary.
`core/tests/test_static_assets.py` keeps them from coming back.

## Domain

Three sites, one app, since 2026-10-30:

| Host | Site | URLconf |
|---|---|---|
| `acclaimedmedia.org` | the landing page: one card per site | `acclaimedgames/urls_root.py` |
| `games.acclaimedmedia.org` | the game rankings, at the paths the apex had | `acclaimedgames/urls_games.py` (also `ROOT_URLCONF`) |
| `music.acclaimedmedia.org` | the album rankings, at the root of the host | `acclaimedgames/urls_music.py` |

There is one name for all of it, **Acclaimed Media**: every title suffix,
`og:site_name`, the JSON-LD, the emails and `Site.name` (migration `0123`).
Neither site names itself. The favicons are still the old Acclaimed Video
Games artwork until a new one is drawn, and a page without artwork of its
own has no `og:image`: the old default was removed. Mail still goes to
and from `contact@acclaimedvideogames.com`, the address Titan and Brevo have
verified.

**`core/sites.py` is the routing.** `core.middleware.SiteHostMiddleware`
reads the host, records `request.site_key` (`"root"`, `"games"`, `"music"`)
and sets `request.urlconf`, which Django uses to resolve the path and as the
default for every `reverse()` and `{% url %}` during the request. So a link
within a site is a plain `{% url %}`; a link to *another* site needs that
site's URLconf and origin, which is `{% site_url 'music' 'music:home' %}`
(`core_filters`) or `sites.site_url()`. A model or a command that builds a
URL whatever the request is uses `sites.site_reverse()` (music's
`get_absolute_url` and cover URLs do). Any other host - the test client's
`testserver`, `127.0.0.1` - gets `ROOT_URLCONF`, the games site's.

- **Origins.** `settings.SITE_ORIGINS` holds the three public origins, used
  for canonical links, the sitemap `<loc>`s and structured data
  (`{{ canonical_origin }}` follows the host; `sites.canonical_url()`).
  `CANONICAL_ORIGIN` is the apex's, for emails and the fetchers'
  User-Agent. A cross-site *link* (`site_origin()`) keeps the request's
  scheme and port, so `games.localhost:8000` links to `music.localhost:8000`.
- **The shared routes** - sign-in, `accounts/`, the contact form,
  `/page/<slug>/` (About, Donate, Privacy, Legal), unsubscribe, admin,
  `healthz/`, `robots.txt`, `sitemap.xml` - are in every URLconf
  (`urls_common.py`), so a visitor uses them without leaving their site.
  The shared pages are one copy: their canonical link and sitemap entry are
  the apex's. At the apex they render without a sidebar.
- **The old apex paths redirect.** Everything the apex served before is in
  links and search indexes, so `urls_root`'s catch-all
  (`core.views.redirect_to_site`) sends `/music/<rest>` to
  `music.…/<rest>`, `/api/music/<rest>` to `music.…/api/<rest>`, and every
  other path to the same path on `games.`, query string kept. `/` with a
  query is an old filter link, since the rankings lived there, and goes to
  `games.` too, if it carries one of the rankings' own parameters
(`OLD_FILTER_PARAMS`); anything else, such as a tracking tag, stays on the
landing page and shares its cache.
- **Each site has its own `robots.txt` and `sitemap.xml`**
  (`core.sitemaps.for_site` puts each `<loc>` on the site's origin; the
  `Site` row's domain stays the apex).
- **One sign-in for all three.** In production the session and CSRF cookies
  are set on `.acclaimedmedia.org`, and both were renamed (`am_sessionid`,
  `am_csrftoken`) with the move, since a host-only cookie of the old name
  left on the apex would otherwise be sent beside the new one. Everyone was
  signed out once. JavaScript that reads the CSRF cookie reads
  `am_csrftoken`. The theme choice is in `localStorage`, which is per
  origin, so `_theme_script.html` also keeps it in a domain-wide `theme`
  cookie.
- **Development** uses the same names under localhost: `localhost:8000`,
  `games.localhost:8000`, `music.localhost:8000` (Chrome resolves
  `*.localhost` itself; `ALLOWED_HOSTS` takes `.localhost` under `DEBUG`).
  The cookies are host-only there, so signing in on one does not sign you
  in on the others.

DNS is in Cloudflare (James's account; both zones), and the app on Heroku
has three custom domains, each with Heroku's ACM certificate:

- **`acclaimedmedia.org`, `games.` and `music.` are DNS-only** (grey cloud),
  CNAMEs to their Heroku DNS targets. They must not be proxied:
  `get_client_ip` takes the last `X-Forwarded-For` entry, Heroku's router's,
  and behind Cloudflare that would be a Cloudflare address, so every visitor
  would share a rate-limit bucket.
- **Every other host is a 301 at Cloudflare's edge**: `www.acclaimedmedia.org`
  to the apex, and `acclaimedvideogames.com` and `www.acclaimedvideogames.com`
  to `games.acclaimedmedia.org`, path and query string kept. They are
  proxied records with a placeholder address (`192.0.2.1`) and a dynamic
  redirect rule in their zone, and never reach a dyno.
- Keep the old domain registered, and leave its MX, SPF, DKIM and DMARC
  records alone: the contact address still lives there.
- Sentry's uptime monitor should fetch `https://games.acclaimedmedia.org/`:
  the apex is now a light page that does not exercise the rankings render.

## Caching

Three aliases, defined by `core/cache_config.py` (which `settings.py` calls):

- **`default` is shared across processes.** In production it is Django's
  `DatabaseCache` on the existing Postgres (`CACHE_URL=dbcache://cache_table`),
  so the gunicorn workers and any one-off dyno see the same entries. That
  is what makes `music.services.caching` mean anything: under
  `LocMemCache` each process had its own copy and an invalidation reached
  exactly one of them, so a metadata refresh left stale filter options behind
  for up to their 24-hour TTL. Local dev stays on LocMem; `createcachetable
  cache_table` runs in the Heroku release phase and is idempotent.
  The table outlives a deploy, so the games API's page caches
  (`games.api.views.cache_page`) are keyed on `HEROKU_RELEASE_VERSION`, from
  the app's `runtime-dyno-metadata` lab (enabled 2026-10-26). Before that,
  new code was served old code's output, such as the payload version for up
  to an hour after a `SCHEMA_VERSION` bump. The rest of the alias is not
  prefixed. A whole-alias prefix reset allauth's and the contact form's
  rate-limit counters on every release, and aimed a long job's
  invalidation at the release it started under. The hand-built caches carry
  their own version constants. The same lab gives Sentry
  `HEROKU_SLUG_COMMIT`, which it reads as the release.
- **`local` is per-process, and must stay that way.** It holds the whole
  rendered pages of `core.mixins.AnonymousResponseCacheMixin`. They are large
  and need no cross-process agreement: on the shared backend a crawler would
  push every page's HTML into Postgres and cull the small shared entries
  straight back out. The bodies are stored **deflated** - the rankings page is
  ~1.4 MB of HTML and there are ~50 cacheable URLs between the home page and
  the SEO landing pages, which uncompressed is 60-70 MB in every worker.
  A cached page's **CSRF token cannot be cached with it**. It is masked from
  the secret in one visitor's cookie, so replaying it hands the next visitor a
  token their own cookie will not match - and a cache hit renders no template,
  so nothing calls `get_token` and no cookie is set at all. `base.html`'s
  contact form therefore 403'd for anyone whose first page was a cached one.
  The mixin swaps the token for a NUL-delimited sentinel on the way in and
  mints a fresh one per request on the way out, so the page stays cacheable
  and the secret stays per-visitor. The CSP nonce, the second per-request
  token, gets the same treatment (`_stash_csp_nonce` / `_restore_csp_nonce`):
  the header carries a fresh nonce on every response, so a replayed one
  would put every inline script outside the policy. A third token would
  need a third pair.
- **`ratelimit` is per-process too**, and holds the per-IP counters in
  `games.middleware`. It was carved out of `local` on 2026-10-18: page bodies
  and counters were culling each other out of one 500-entry LocMem, so a crawl
  wide enough to matter evicted the counters meant to stop it. DRF's
  anonymous throttle (`core.throttling.ClientIPAnonRateThrottle`) counts
  there too; on DRF's default it wrote to Postgres on every API hit. Under
  test the alias is a DummyCache, so no counter is ever kept. Django's
  runner does not clear caches between tests, and a test process making 120
  requests in a minute failed unrelated tests with 429s. The tests of the
  limits override `CACHES` with a real backend.

**Every per-IP limit keys on `core.services.client_ip.get_client_ip`**: the
middleware, the contact form guard, DRF's throttle and allauth's limits,
through `ModalAccountAdapter.get_client_ip`. It takes the *last*
`X-Forwarded-For` entry, the one Heroku's router appends. The client writes
everything to its left, so the first entry, which the code read until
2026-10-26, let anyone take a fresh bucket per request or get another
address blocked. allauth's own default was `REMOTE_ADDR`, the router's, so
every visitor shared one bucket. This assumes nothing proxies in front of
the router; a CDN would move the client one entry left. The auth modal
views call allauth's forms directly, so they apply the `signup`,
`reset_password` and `confirm_email` limits themselves, as allauth's views
would.

`MAX_ENTRIES` is set explicitly for all three, since Django's default of 300
culls a third of the cache on almost every write.

**There is deliberately no site-wide `UpdateCacheMiddleware` /
`FetchFromCacheMiddleware`.** Every page varies on `Cookie` - the auth-aware
chrome and the CSRF token see to that - so Django keyed a separate copy of
every page on every visitor's cookie header, while storing nothing at all for
a first-time visitor who has none (it skips the write when the response sets
cookies and the request carried none). Three workers' worth of per-visitor
HTML, at 1.4 MB each for any client that did not send `Accept-Encoding: gzip`,
was most of why the dyno sat over its 512 MB quota. See "Production memory
budget" below.

**Music has no whole-page cache.** Every cached rankings page spends from the
512 MB budget below, so measure before adding `AnonymousResponseCacheMixin`.

Music's cache keys all live in `music/config.py` as `CACHE_KEYS`, which
`caching.invalidate_music_caches()` iterates - add a cached value there or it
will not be invalidated. Every key carries `CACHE_VERSION`, so bumping that
string invalidates the whole set.

**Every music cache write goes through `caching.cached` or `set_if_current`,**
wrappers on `core.cache_helpers`. A read that queried just before a commit
would otherwise save the old rows just after the commit's delete, and they
would stay for the key's whole TTL, 24 hours for the filter options. Every drop
first writes a new `CACHE_KEY_GENERATION`, and a read skips its save if that
moved while it was querying. One generation covers the section, so a toggle
costs a concurrent miss its save and nothing more. A hit costs nothing extra; a miss costs one
more read, since `AlbumHomePageView` batches the generation with its keys. A
tiny window remains between the check and the write. Versioned keys
would close it, at a cache read on every unbatched page and a rewrite of the
music cache tests. `music/tests/test_caching.py` fails if a module writes the
cache around the guard.

**Games' invalidated caches use the same guard, a family at a time**
(`games/cache.py`): hero stats, the played and want-to-play id sets and played
counts, and the developer hierarchy and detail. A generation row is written on
every drop, so there is one per family, not per key, which could outgrow the
cache table's budget, and not one for the section, which would have the weekly
refresh cancel every family's saves. A developer save that changes nothing, which
is most of what the IGDB refresh does, drops nothing. They drop through
`core.cache_helpers.drop_on_commit`, not `cache.delete`: `post_save` fires
inside an import's transaction, and a page load before the commit used to put
the old counts back for a day with nothing left to drop them. Keys collect per
thread and flush together at the commit, so an import costs one drop per family
rather than thousands. Hero stats drop when a game, list or publication is created or
deleted, not on every save, which is what the weekly refresh does. Games' facet,
landing and count caches are not converted: nothing invalidates them by event,
so they have no race. Books' are not either, being staff-only in production. A
test of what a signal invalidates takes
`core.tests.utils.CommitHooksRunNowMixin`, since a `TestCase` never commits.

Music's `/cover/` is exempt from rate limiting on the music host
(`SITE_RATE_LIMIT_EXEMPT_PREFIXES`): it is a static asset in all but the URL,
and one rankings page requests up to a hundred of them against a 120/minute
budget.

**A whole-page cache key carries the host.** `AnonymousResponseCacheMixin`
puts `request.get_host()` in front of the view's own key, because a page
links to the other sites by absolute URL built from the host it was
rendered for. The landing page is cached the same way.

## Content Security Policy

`SECURE_CSP_REPORT_ONLY` in settings, with Django's own
`ContentSecurityPolicyMiddleware` and `{{ csp_nonce }}`, since 2026-10-26.
It reports and blocks nothing; enforcing it means moving the dict to
`SECURE_CSP` once Sentry's CSP reports are quiet. What it rests on:
- Every inline `<script>` carries `nonce="{{ csp_nonce }}"`. Scripts an
  htmx swap brings in get the page's nonce through the `htmx-config` meta
  tag's `inlineScriptNonce`. Cached pages are given the request's nonce, as
  above.
- There are no inline event handlers, which a nonce forbids. Mobile row
  cards navigate through `[data-href]`, dialogs close through
  `[data-close-dialog]`, and the import page's confirms through
  `[data-confirm]`, each with one delegated listener. The one exception is
  `onclick="event.stopPropagation()"` on the tracking buttons, on rows that
  carry no Alpine on purpose; `'unsafe-hashes'` with its hash
  (`core.csp.handler_hash`) allows exactly that text.
- `'unsafe-eval'`, because Alpine evaluates expressions with `new Function`.
  Dropping it needs Alpine's CSP build.
- `style-src` has `'unsafe-inline'` and no nonce: a nonce would disable it,
  and `style=""` attributes are everywhere.
- Reports go to Sentry's security endpoint, built from the DSN
  (`core.csp.sentry_report_uri`). Under test and on a developer's machine
  there is none (`SENTRY_ENABLED`).
- A `meta-webindexer` report naming an `acclaimedvideogames.com` host does
  not count against "quiet". Meta's crawler re-renders pages it stored before
  the domain move (from 2026-10-30): their assets 301 to
  `acclaimedmedia.org`, which the stored page's `'self'` does not cover, and
  the report names the old URL. The policy is stored with the page, so no
  change to ours reaches it. No template or asset references the old host,
  though some posts link to it. A real browser's report still counts.
- A FlatPage body cannot carry a nonce, so it cannot hold an inline script,
  and a third-party widget in one means widening the policy for the whole
  site. The Donate page's Ko-fi button was Ko-fi's script until 2026-10-30
  and is now a plain link. Its PayPal buttons are forms, hence
  `form-action https://www.paypal.com/donate`.

`core/tests/test_csp.py` pins the nonces and the handler rule. When adding
an inline script, give it the nonce; when adding a click behaviour, use a
data attribute and a delegated listener, not `onclick`.

## Production memory budget

The web dyno is a Basic one: **512 MB for every gunicorn worker together**.
Measured on 2026-10-18 (Python 3.11, Django 5.2; re-measure after the
2026-10-25 move to 3.14 and 6.1 reaches the dyno), one worker boots at ~110 MB (79 MB of imports, ~30 MB
of it `sentry_sdk`) and plateaus at **~200 MB** once it has rendered a page or
two - flat from ~50 renders out to 1000, so there is no leak to hunt. The
rankings page was 1.4 MB of HTML then, and the ~45 MB a worker never returns
after its first render is allocator arenas, not live data. It is now 690 KB
anonymous and 833 KB logged in (see "Rankings page weight" below).

That arithmetic sets the shape of the `Procfile`:

- **`--workers 2`.** 2 x 200 MB leaves ~110 MB of headroom; three workers
  needed ~570 MB and the dyno had been swapping and firing R14 all day.
- **`--worker-class gthread --threads 2`** for concurrency without a third
  heap: threads share their worker's imports and caches, so a second thread
  costs only what its in-flight render allocates, where a third process cost
  another ~200 MB. Four requests run at once instead of two, and a long SSE
  import stream now holds one thread rather than a whole worker. Raise
  `--threads` only against `memory.rss.bytes.max` measured on the dyno.
  The request path was audited for shared state before the switch: the
  per-process caches are `LocMemCache` (locked), the IGDB client and every
  `requests.Session` are per instance, and `RateLimitMiddleware._incr` now
  `add`s before it `incr`s so two threads meeting a new key both count.
- **Database connections are per thread.** `CONN_MAX_AGE` is left at 0, so
  each request opens and closes its own, and the web dyno holds at most
  workers x threads (4) at once, plus an import's: its background thread
  and the IGDB importer's pool of 8. `import_handler._start_import_thread`
  closes the background thread's connection when it finishes; left alone it
  lingered until the cyclic garbage collector reached the thread's wrapper.
- **No `--preload`.** Measured with a fork test: a child touched ~160 MB of
  the parent's pages within 20 requests, because CPython refcounts dirty the
  page holding every object they read. Copy-on-write saved nothing (593 MB
  preloaded vs 585 MB not).
- **`--timeout 600` stays.** The games importer streams progress over SSE and
  a shorter timeout kills that mid-import.
- `--max-requests 500` is a guard against slow growth, not a memory lever: a
  recycled worker is back at the plateau within ~15 page renders.

**Template indentation is stripped at load.** `core/template_loaders.py`
wraps both loaders, in dev and prod alike, and removes the leading whitespace
of every `.html` source line, which was 36% of the rankings page. Each newline
survives, so rendering is unchanged, except inside `<pre>`/`<textarea>`, which
are left as written. **Do not add markup whose meaning depends on
indentation** - `white-space: pre` in CSS, or indented text in a `<code>`
block - without exempting it there.

**Rankings page weight.** What was cut, and what holds it down:

- **The server renders no grid cards.** The 100 hidden
  `_game_card_grid.html` cards were ~160 KB. Grid mode now shows the list
  rows until the client-side filtering bundle builds a grid from
  `#grid-card-template`: `styles.css` hides the rows only
  `:has(.game-grid)`, `home.html` fetches the bundle at once when
  `gameViewMode` is `grid`, and `filterComponent` renders the grid as soon
  as the bundle is ready (`_needsClientGrid`), without touching the URL.
  Anything that pages a grid (`renderer.loadMore`, `renderer.showRange`)
  builds the whole window when no grid exists yet, because the rows above
  are not cards.
- **Jump to rank renders a window, not everything above the target.**
  `BaseMediaListRenderer` tracks `windowStart`/`windowEnd`, and `planJump`
  either scrolls (the target is already rendered), extends the window (the
  target is within a page of it), or replaces it with `JUMP_RADIUS` (50) rows
  either side of the target. `core/includes/_load_previous.html`, above each
  rankings list, gets a Load Previous button whenever rows are left out
  above. Positions are absolute, so anything that finds "the Nth row" on the
  page has to subtract `windowStart`. Focusing the games jump box also starts
  the engine: before, it only loaded the bundle, so every jump took the
  server path, which fetches each page down to the target.
- **Platform and genre spans carry `data-add-platforms` / `data-add-genre`,
  not inline onclicks** (~54 KB). One delegated listener in `base.html`
  re-announces the `add-platforms` / `add-genre` events every filter
  component already answers. Album rows use it too, with `data-item` for the
  highlight.
- **One game status menu per page, not one per button** (~250 KB logged
  in). Each game renders two buttons, one per row half, and each used to
  carry an Alpine component and three `hx-post` items. A button is now only
  its trigger; `games/includes/_played_menu.html` and `played-menu.js` open
  the shared menu beside it and post with `htmx.ajax`, the wrapper as source
  so the body's CSRF header is inherited. The wrapper's
  `onclick="event.stopPropagation()"` keeps the mobile row from navigating,
  so the menu's click listener runs in the **capture** phase.
- **Alpine skips the filter UI the visitor cannot see** (2026-10-25). At
  Lighthouse's 4x mobile throttle, Alpine's init on `/` was one ~920 ms task,
  and nearly all of it went to two invisible things: the `display:none`
  desktop sidebar (~530 ms) and the never-opened mobile sheet (~340 ms). The
  100 rows cost nothing, because they carry no directives. The sheet's contents
  now sit in `<template x-if="hasOpenedBefore">`. The sidebar
  (`#desktop-filter-sidebar` in `_advanced_filters.html`) is `x-ignore`d
  by an inline script on a narrow first load, then `Alpine.initTree`d if
  the window widens past 962px. Both lean on `mobile-filter-opened`, which
  makes `filterComponent` re-send the facet counts that the late components
  missed. Alpine init dropped to ~90 ms. The sidebar div must carry no
  directives of its own, since `initTree` would run them a second time.
  The album page does the same (`#album-filter-sidebar`, music's sheet):
  the script is the shared `core/includes/_defer_hidden_sidebar.html`, and
  `mediaListControls.refreshFacetCounts()` answers `mobile-filter-opened`
  through the engine's `republishFacets()` once it is ready. Its form keeps
  working while ignored, because `commit()` writes the fields itself. At 4x,
  `/music/` went from ~360 ms of Alpine init to ~75 ms on a phone.

**Filter-change speed** (2026-10-26). A decade click took ~290 ms to
reach the list on a fast machine and ~710 ms at a 4x CPU slowdown, and
almost none of that was filtering. Now it is ~60 ms and ~250 ms, with
every click's INP under 200 ms even at 4x. Four things mattered:

- **The trailing debounce** (150 ms in games, 250 ms in music's
  `mediaListControls`) made every single click wait.
  `_debouncedFilter` is now `debounceLeading` (`utils-base.js`): the first
  change applies at once and a burst still collapses into one trailing
  update. It runs through `afterNextPaint`, because doing the update in
  the click's own task held back the paint INP measures, at 300-400 ms on a
  slow CPU. It leads only once the client engine is ready
  (`clientFilterReady`, music's `clientEngine` setting): before that each
  update is a server render, and a leading fetch could land after a newer
  client render. A burst's trailing run replaces the history entry the
  leading one pushed (music: `form.dataset.historyReplace`), and is skipped
  when it would render the same filters again.
- **Sidebar bindings scanned the page's reactive arrays.** Every
  platform, genre and series row called `find()`/`filter()` over
  `platforms`/`genres`/`seriesList`. Each scan read, and subscribed to,
  every item through Alpine's proxy, and a year change re-evaluates every
  row, so one change cost ~90 ms of Alpine effects. The components now
  build index maps once (`indexBy`, `buildGenreIndex`) and read
  `list[i]`, which tracks only that item. The structure of these lists is
  fixed for the page's life; only `filtered_count` changes.
- **The desktop series getter sorted `seriesList` in place**, writing
  every index of the reactive array on each read. It sorts a copy.
- **The chart animation is frame-capped** (`MAX_FRAME_STEP_MS` in
  `rank-distribution.js`), so a busy main thread pauses the morph rather
  than skipping to its end.

Measure with real clicks, at 1x and 4x, through the Event Timing API
(`interactionId` entries) plus a MutationObserver on
`#game-list-container`. Puppeteer's `mouse.click` hits nothing off-screen,
so scroll a sidebar control into view first.

Anything that grows the rendered page, the boot imports, or a per-process
cache is spending from that 512 MB twice over. `heroku ps`, and the
metrics API (`api.metrics.heroku.com/apps/<id>/formation/web/metrics/memory
?start_time=..&end_time=..&step=1h&process_type=web`, with
`memory.rss.bytes.max` and `memory.swap.bytes.max`), are how to check it.

## Configuration

### Environment Variables

Environment variables are managed via django-environ (`.env` file):
- `DEBUG` - Enable Django debug mode
- `SECRET_KEY` - Django secret key
- `IGDB_CLIENT_ID` - IGDB API client ID
- `IGDB_CLIENT_SECRET` - IGDB API client secret
- `IGDB_USE_PRO_TIER` - Enable IGDB Pro tier (default: False)
- `WIKIDATA_ACCESS_TOKEN` - For faster Wikipedia processing (2.5x speedup)
- `BOOKS_ENABLED` - Enable books feature (default: False, enabled in DEBUG/TEST modes)
- `HARDCOVER_API_TOKEN` - Optional Hardcover API token for additional book metadata
- `DISCOGS_TOKEN` - Optional Discogs personal access token; raises the music
  metadata rate limit above the 25 requests/minute anonymous tier
- `CACHE_URL` - Cache backend URL. Production uses `dbcache://cache_table`;
  local dev falls back to LocMem whatever this says, and tests set
  `locmemcache://`. See the Caching section
- `SENTRY_ENVIRONMENT` - Sentry's environment tag. Defaults to `production`
  when `DYNO` is set (any Heroku dyno) and `development` everywhere else.
  `development` sends nothing, neither errors nor CSP reports, even with
  `SENTRY_DSN` in the local `.env`; set any other value to opt a machine in.
  `manage.py shell` never reports, on a dyno either: whoever ran it reads the
  traceback, and each typo in a one-off query filed an issue and an alert.
  That includes `heroku run:detached`, so unwatched work belongs in a command

### Configuration Files

- **`.python-version`** - Specifies Python 3.14 for Heroku deployment; the local venv tracks production's patch release (see "Dependencies")
- **`.pre-commit-config.yaml`** - Pre-commit hook configuration for code quality enforcement (Black, Flake8, tests)
- **`.coveragerc`** - Coverage configuration. It omits migrations, the tests, every management command and both `import_handler.py` modules, so the 100% gate does not cover the scheduled jobs or the import pipelines
- **`.flake8`** - Flake8 linter configuration (max line length 88, excludes venv)
- **`scripts/run_tests.sh`** - The same suites under Django's own test runner; see below

**Two test runners, on purpose.** `pytest` is the gate: the pre-commit hook
runs it on every commit and `pytest.ini` fails the commit under 100%
coverage. `conftest.py` also clears every cache alias between tests, which
hides a test that leaks cache or process state into the next one.
`scripts/run_tests.sh` runs the same four suites under `manage.py test`,
where conftest does not apply, so such a leak fails there. On 2026-10-17 it
found 181 failures and 55 errors that a fully green pytest run had missed,
after the cache was split into aliases. It would nearly double a commit's
test time (~45 s on top of pytest's ~60 s), so it is a manual-stage hook. Run
it when a change touches caching, sessions or any other process-wide state:

```bash
venv/bin/pre-commit run django-tests --hook-stage manual
```

It used to run on every commit from a hand-placed
`.git/hooks/pre-commit.legacy`, until a `pre-commit install` silently replaced
it. Keep hooks in `.pre-commit-config.yaml`, never in `.git/hooks`, which
`pre-commit install` owns and every worktree shares. `tblib` is in
`requirements-dev.txt` so that a failure under `--parallel` reports its traceback
instead of crashing the runner on an unpicklable one.

**Tests cannot reach the network under pytest.** `conftest.py` refuses
every DNS lookup and connection that leaves the machine (loopback stays
open for the Postgres runs), and fails the test even when the client code
swallowed the error. The tests also run without outside credentials:
settings blanks the IGDB, Wikidata and Discogs ones under test, as CI has
none. When the guard was added on 2026-10-26 it caught four tests calling
IGDB and HowLongToBeat for real. Locally they were also fetching a live
Twitch token with the `.env` credentials. Patch the client where the code
under test reads it. The Django runner has no conftest and so no guard.

**Tests pick a site the way a request does.** The test client's
`testserver` host gets `ROOT_URLCONF`, the games site, so games tests need
nothing. A module of music tests imports the module fixtures
(`from music.tests.site import setUpModule, tearDownModule`), which put the
music URLconf in place for the whole module under both runners; a music
class in a mostly-games module takes `@music_site` instead. A test that
crosses sites names the real host: `core.tests.utils.get_on_site(client,
sites.GAMES, "home")`, over HTTPS, so its links are the production ones.

## Database

- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL on Heroku
- The `rank` field on Game determines primary ordering (lower is better)
- `year_rank` and `decade_rank` are derived from `rank` by
  `core.services.ranking.update_year_decade_ranks()`, which runs during import -
  **not** automatically on save

## Dependencies

Python packages are pinned with pip-tools. Edit the `.in` files and never the
`.txt` files, which are compiled from them:

| File | What it is |
|---|---|
| `requirements.in` | What production imports, loosely constrained |
| `requirements.txt` | Its compiled, fully pinned lock - what Heroku installs |
| `requirements-dev.in` | Tests, hooks, `pip-audit`, the debug toolbar, `runserver_plus` |
| `requirements-dev.txt` | Its lock, constrained to `requirements.txt`'s pins |

```bash
pip install -r requirements.txt -r requirements-dev.txt   # local development and tests
pip-compile requirements.in && pip-compile requirements-dev.in   # after editing an .in
pip-compile --upgrade-package django requirements.in && pip-compile requirements-dev.in
```

Always recompile the dev lock after the production one: it repeats every
production pin, and CI installs both locks together so that a dev lock left
on an old pin fails the install rather than testing a version Heroku never
runs.

Each lock's header records the exact `pip-compile` command, flags included;
Dependabot reruns it. Until 2026-10-25 only `psycopg2-binary` was pinned, so
every Heroku build installed whatever was newest that day, test tools
included.

Tailwind CSS and DaisyUI are npm packages in `theme/static_src/`, pinned by
its `package-lock.json`. `node_modules` there and `venv` at the root are
symlinks into the main checkout in every worktree (`scripts/setup_worktree.sh`),
so `npm install` or `pip install` in a worktree changes every checkout's copy.
Replace the symlink with a real install before changing either on a branch.

The shared venv lives in the main checkout and is built on Homebrew's
`python@3.14`, kept on the patch release production runs (check with
`heroku run -a acclaimedgames -- python --version`, which starts a
one-off dyno). Its interpreter is a symlink into
Homebrew's `opt/` directory, so `brew upgrade python@3.14` moves every
worktree's venv to the new patch with no rebuild; a patch release keeps the
ABI, so the installed packages carry on working. Rebuild only for a new
minor version, from the main checkout, once `.python-version` is bumped
and the locks are recompiled under it:

```bash
V="$(cat .python-version)"; PY="$(brew --prefix python@$V)/bin/python$V"
test -x "$PY" && rm -rf venv && "$PY" -m venv venv \
  && venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
```

`test -x` comes first because `brew --prefix` prints a path even for a
formula that is not installed, and every worktree's `venv` symlink points
at this one: deleting it before the new interpreter is known to exist
leaves all of them without a venv.

Use Homebrew's Python, not a python.org installer. python.org's macOS
framework builds ship no CA bundle, and their "Install Certificates" step
cannot write one without root, so aiohttp (the HLTB fetch) fails every
certificate check unless a `sitecustomize.py` points `SSL_CERT_FILE` at
certifi - which is what the venv carried until 2026-10-25.

### Keeping dependencies current

Four layers, from automatic to manual:

- **GitHub security features** (enabled 2026-10-25): Dependabot alerts,
  Dependabot security updates (a PR as soon as an advisory lands), secret
  scanning, and push protection, which refuses a push containing a
  recognised credential.
- **Dependabot version updates** (`.github/dependabot.yml`): every Monday,
  one grouped PR of minor and patch bumps per ecosystem (pip, npm), and
  majors one PR each. Django's feature releases get their own PR too, since
  they can remove deprecated APIs. GitHub Actions monthly. Nothing
  is held back: until 2026-10-25 `requirements.in` capped Django below 6.0,
  and the site ran 5.2 on Python 3.11, which no Django 6 release supports.
- **CI** (`.github/workflows/ci.yml`) on every push to `main`, every PR, and
  every Monday:

  | Job | Checks |
  |---|---|
  | `lint` | black, flake8 over every file |
  | `pytest` | the suites with the 100% coverage gate |
  | `django-tests` | `scripts/run_tests.sh`, the runner without conftest, on Postgres 18 (production's version) |
  | `audit` | `pip-audit` on both locks, `npm audit --audit-level=high` |
  | `css` | rebuilds the CSS and fails if it differs from the committed file |
  | `js` | `scripts/minify_js.sh --check`: the same for the minified JS and bundles |
  | `browser` | `scripts/browser_smoke.js`: Chrome over the main pages, failing on a JS, Alpine or CSP error |

  `css` exists because Heroku runs only the Python buildpack, so the
  committed `theme/static/css/dist/styles.css` is what ships. An npm bump
  that changes the build fails there until someone rebuilds and looks at it.
  Tailwind 4.1 -> 4.3 was such a bump: it grew the file from 208 KB to
  253 KB (32 KB to 36 KB gzipped), and moved nothing on screen but the music
  Filters header's buttons, by ~3px.
- **`/upgrade-deps`**, monthly: merge the Dependabot queue, take the majors,
  audit, check page weight, memory and slow transactions, and check the
  runtime end-of-life calendar (Python 3.14 ends October 2030; Django 6.1,
  not an LTS, gets security fixes until December 2027, so 6.2 by then).

A Dependabot PR is a merge to `main` like any other. A dependency-only diff
touches no code or templates, so the `/code-review` gate's skip applies, but
it merges only with CI green, and a major only after reading its changelog.

**`@tailwindcss/typography` pins `postcss-selector-parser` exactly** (at
6.0.10 in 0.5.20), below the 6.1.5 fix for GHSA-rj75-hqrm-r3gf. An
`overrides` entry in `theme/static_src/package.json` holds it at the patched
6.1.5 instead; drop it once the plugin's pin moves past that. Nothing is
waived any more: CI's `npm audit` fails on any severity, as `pip-audit` does.

**What the first Postgres run found** (2026-10-25), none of which SQLite
could show:

- **Two migrations had only ever run incrementally.** `0055` and `0061`
  failed on a fresh database: `0044`'s rename left the old index names
  behind, and `0061` probed for `auth_user` with a SELECT whose failure
  aborts a Postgres transaction. Both now branch on the vendor; production
  applied them long ago, so only new databases see the change.
- **Import threads escape the test transaction.** `_start_import_thread`
  runs an import on its own connection. Under in-memory SQLite Django hands
  every thread the test's connection, so it never mattered; on Postgres the
  thread's writes commit for real and leak into every later test on that
  worker, and one touching a row the test holds deadlocks. Tests that reach
  a thread run it inline (`InlineImportThreadMixin` in
  `games/tests/test_imports.py`).
- **Five import tests had been passing by accident.** Their mocks patched
  `games.utils.*`, which the code stopped reading when it moved to
  `games.services.import_handler`; they passed because the threaded import
  failed with SQLite's "database table is locked", which they took for the
  error they expected. Underneath was a real bug: the streaming batch import
  (`import_batch_with_progress`, the staff import page) passed `"GAMES"`
  where `_validate_prerequisites` compares `constants.TYPE_GAME`, so it
  never validated prerequisites at all.
- **A test assumed a primary key of 1.** Postgres sequences do not rewind
  when a test's transaction rolls back; use the object's `id`.

Set `TEST_DATABASE_URL` to run the suites on Postgres locally; tests
otherwise always use in-memory SQLite. Patch the module that *reads* a name,
not one that re-exports it.

## Static Files

- Django collectstatic copies static files from apps to `staticfiles/`
- WhiteNoise serves static files in production
- Static files are located in:
  - `games/static/` - Game app static files (icons, fonts, images)
  - `theme/static/` - Tailwind CSS compiled output
  - `games/templates/` - Template files

### CSS Workflow (Tailwind CSS)

The site uses django-tailwind with Tailwind CSS v4 and DaisyUI v5 for styling.

**Development:**
```bash
# Start Tailwind CSS watcher (rebuilds CSS on file changes)
python manage.py tailwind start

# Run Django dev server (in separate terminal)
python manage.py runserver
```

**Production Build:**
```bash
# Build minified CSS for production
python manage.py tailwind build

# Collect static files
python manage.py collectstatic --noinput
```

**File Locations:**
- `theme/static_src/src/styles.css` - Main Tailwind CSS source file with custom components
- `theme/static/css/dist/styles.css` - Compiled CSS output (auto-generated)
- `games/static/games/css/mdi-subset.css` - Material Design Icons (self-hosted subset)
- `games/static/games/fonts/materialdesignicons-webfont.woff2` - Generated MDI subset font

**Adding Custom Styles:**
Edit `theme/static_src/src/styles.css` and use Tailwind's `@layer` directive:
```css
@layer components {
  .my-component {
    @apply flex items-center gap-2;
  }
}
```

**DaisyUI Components:**
Common components used: `btn`, `card`, `table`, `alert`, `badge`, `input`, `select`, `checkbox`, `dropdown`, `modal`, `link`

**Theme Configuration:**
Themes are defined in `theme/static_src/src/styles.css` using DaisyUI's `@plugin` directive:
```css
@plugin "daisyui" {
  themes: ["lofi", "forest"];
}
```
The theme switcher in the navigation allows users to change themes, with the selection persisted in localStorage.

### MDI Subset Workflow

Material Design Icons are shipped as a local WOFF2 subset to reduce transfer size.

**Rebuild command:**
```bash
./scripts/build_mdi_subset.sh
```

**Dependencies:**
- `pyftsubset` (from `fonttools`)
- `brotli`
- `zopfli`

Install once if missing:
```bash
pip install fonttools brotli zopfli
```

The script scans icon codepoints from `games/templates/base.html` and `games/static/games/css/mdi-subset.css`, then rewrites `games/static/games/fonts/materialdesignicons-webfont.woff2` in place.

### JavaScript Workflow

JavaScript files in `games/static/games/js/` follow a specific workflow:

**Source and Minified Files:**
- Source files (e.g., `game-list-renderer.js`) contain the readable code
- Minified files (e.g., `game-list-renderer.min.js`) are generated from source files
- **Always edit the source `.js` file, never the `.min.js` file directly**

**Bundle Files:** three, each built by `scripts/minify_js.sh` from minified
sources in dependency order, and each starting with
`core/static/core/js/base-renderer.min.js` - a bundle whose renderer extends
`BaseMediaListRenderer` without it throws a `ReferenceError` as it loads, so
nothing declared after that point registers either:

- `games/static/games/js/client-side-filtering.bundle.min.js` - `base-renderer`, `game-cache`, `client-filter`, `game-list-renderer`, `client-filtering`
- `books/static/books/js/book-client-side-filtering.bundle.min.js` - `base-renderer`, `book-cache`, `book-client-filter`, `book-list-renderer`, `book-client-filtering`
- `music/static/music/js/music-client-side-filtering.bundle.min.js` - `base-renderer`, `album-filter`, `album-list-renderer`, `album-client-filtering`

`core/static/core/js/` also holds three files loaded on their own rather than
bundled, because they have to run before Alpine initialises:
`filter-subcomponents.min.js`, `media-list-controls.min.js` and
`media-search.min.js`. Pages push them onto `window.alpineScripts` in
`{% block pre_alpine %}`.

`core/tests/test_static_bundles.py` asserts that every bundle a template
references exists and that each defines the base classes its members extend.
Both of those failed silently in the books bundle until 2026-10-17.

**After Editing JavaScript:**
Run `/minify` or `./scripts/minify_js.sh`

The minify skill/script:
1. Minifies every source `.js` file with terser pinned at 5.51.2, replacing any `.min.js` whose content differs (`--check` reports instead, and CI's `js` job runs it)
2. Regenerates the bundle if any of its source files changed
3. Stages updated files for git

**Important:** When modifying client-side game rendering (e.g., `game-list-renderer.js`), changes must be reflected in both:
- The Django template (server-side rendering)
- The JavaScript file (client-side rendering on home page)

## Design Guidelines

### Quantitative Display Ruleset

When making any changes that affect **visual displays of quantitative information** (charts, graphs, tables with numbers, rankings, statistics, data visualizations), read and follow the principles in:

**`acclaimedgames/rulesets/Unified Quantitative Display Ruleset.md`**

This ruleset applies to:
- Game ranking displays and tables
- Statistics and metrics (play counts, list appearances, scores)
- Charts or graphs showing trends, distributions, or comparisons
- Any numerical data presentation to users

Key principles to prioritize:
- **Graphical integrity**: Represent quantities proportionally; what is shown must match the data
- **Data-ink ratio**: Maximize data-bearing elements, minimize decorative non-data elements
- **Comparison support**: Design to encourage meaningful comparisons
- **Context**: Always provide units, time frames, and context needed for interpretation
- **Avoid chartjunk**: No fake 3D, unnecessary decoration, or design that doesn't serve the data
