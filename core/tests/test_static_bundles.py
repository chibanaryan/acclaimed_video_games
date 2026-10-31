"""Tests for the client-side filtering bundles.

Two failures shipped in the books bundle and went unnoticed because nothing
tested either: the template referenced a filename the build script does not
write, and the bundle omitted the base class its renderer extends - which
throws a ReferenceError as the bundle loads, so nothing declared after that
point registers either. Both are checked here for every app at once, because
both are mistakes a reader cannot see.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

TEMPLATE_DIRS = ["games", "books", "music", "core"]

# `{% static 'app/js/x.bundle.min.js' %}`, either quote style.
BUNDLE_REFERENCE = re.compile(
    r"""{%\s*static\s*['"]([^'"]+\.bundle\.min\.js)['"]\s*%}"""
)
CLASS_DECLARATION = re.compile(r"class\s+(\w+)(?:\s+extends\s+(\w+))?")


def _referenced_bundles():
    """Every bundle path referenced from a template, with its template."""
    found = []
    for app in TEMPLATE_DIRS:
        root = Path(settings.BASE_DIR) / app / "templates"
        if not root.exists():
            continue
        for template in root.rglob("*.html"):
            for match in BUNDLE_REFERENCE.finditer(template.read_text()):
                found.append((template, match.group(1)))
    return found


class ReferencedBundlesExistTests(SimpleTestCase):
    """A bundle a template asks for has to be a file that exists.

    Under production's manifest static storage, a `{% static %}` name missing
    from the manifest raises while rendering rather than 404ing, so a typo
    here takes the page down rather than degrading it.
    """

    def test_some_bundles_are_referenced(self):
        # Guards the regex: an empty sweep would make the test below vacuous.
        self.assertTrue(_referenced_bundles())

    def test_every_referenced_bundle_is_findable(self):
        for template, path in _referenced_bundles():
            with self.subTest(template=template.name, path=path):
                self.assertIsNotNone(
                    finders.find(path),
                    f"{template} references {path}, which no app serves. "
                    f"The name must match the bundle scripts/minify_js.sh "
                    f"writes.",
                )


class BundleContentsTests(SimpleTestCase):
    """A bundle must carry the base classes its own members extend."""

    def test_base_classes_are_declared_before_their_subclasses(self):
        bundles = {path for _, path in _referenced_bundles()}
        self.assertTrue(bundles)

        for path in sorted(bundles):
            with self.subTest(bundle=path):
                source = Path(finders.find(path)).read_text()
                positions = {}
                extends = []
                for match in CLASS_DECLARATION.finditer(source):
                    name, base = match.group(1), match.group(2)
                    positions.setdefault(name, match.start())
                    if base:
                        extends.append((name, base, match.start()))

                for name, base, at in extends:
                    self.assertIn(
                        base,
                        positions,
                        f"{path} declares `class {name} extends {base}` but "
                        f"never defines {base}: the bundle throws a "
                        f"ReferenceError on load. Add its file to this "
                        f"bundle's sources in scripts/minify_js.sh.",
                    )
                    self.assertLess(
                        positions[base],
                        at,
                        f"{path} defines {base} after {name} extends it; "
                        f"reorder the bundle sources so the base class "
                        f"comes first.",
                    )


class RowGenreClickReachesTheHeadingTests(SimpleTestCase):
    """A genre clicked in an album row has to reach the Alpine controls.

    `album-client-filtering.js` answers `add-genre` by writing the hidden
    `genres` select and re-rendering from the engine, which filters the list
    and pushes the URL. But `filters` lives on `mediaListControls`, and both
    the heading and the sidebar's genre tree are built from it - so setting
    the select alone filtered the list while the heading went on naming the
    unfiltered page. Reloading appeared to fix it, because the server then
    composed the heading from the URL.

    The two halves are in different files and neither reads the other, so
    this checks the event name still joins them up. A rename on one side
    only would leave the list filtering with a stale heading again, and
    nothing else in the suite would notice.
    """

    EVENT = "genres-selected"

    def _source(self, relative_path):
        path = Path(settings.BASE_DIR) / relative_path
        self.assertTrue(path.exists(), f"missing {relative_path}")
        return path.read_text()

    def test_the_row_handler_announces_the_selection(self):
        source = self._source("music/static/music/js/album-client-filtering.js")
        handler = source.split("'add-genre'", 1)
        self.assertEqual(len(handler), 2, "no add-genre handler to check")
        self.assertIn(
            self.EVENT,
            handler[1][:900],
            "the add-genre handler no longer announces the selection, so the "
            "heading and the genre tree will not follow it",
        )

    def test_the_controls_component_listens_and_updates_the_title(self):
        source = self._source("core/static/core/js/media-list-controls.js")
        self.assertIn(f"'{self.EVENT}'", source)
        listener = source.split("_genresSelectedListener = ", 1)
        self.assertEqual(len(listener), 2, "no listener to check")
        body = listener[1][:500]
        self.assertIn("filters.genres", body)
        self.assertIn("_applyTitle", body)

    def test_the_listener_is_registered_and_torn_down(self):
        source = self._source("core/static/core/js/media-list-controls.js")
        self.assertIn(f"addEventListener(\n                '{self.EVENT}'", source)
        self.assertIn(
            f"removeEventListener(\n                    '{self.EVENT}'", source
        )

    def test_the_minified_copies_carry_it(self):
        # The page loads the minified files, so a stale `.min.js` would ship
        # the bug with the fix sitting in the source beside it.
        for path in (
            "core/static/core/js/media-list-controls.min.js",
            "music/static/music/js/album-client-filtering.min.js",
            "music/static/music/js/music-client-side-filtering.bundle.min.js",
        ):
            with self.subTest(path=path):
                self.assertIn(self.EVENT, self._source(path))


class SavedFilterSortDirectionRoundTripsTests(SimpleTestCase):
    """A saved filter has to come back with the direction it went in with.

    Games stored `sortDirection` from the day saved filters shipped and
    never read it back, so applying a saved "Year, newest first" quietly
    returned it ascending. The bug was invisible from the server: the blob
    was correct in the database, and only the apply path dropped it.

    Pinned in source *and* minified form for both components, because the
    page loads only the minified copy - a fix that forgets `/minify` ships
    the bug with its own fix sitting beside it.
    """

    COMPONENTS = (
        "core/static/core/js/media-list-controls.js",
        "games/static/games/js/filter-component.js",
    )

    def _source(self, relative_path):
        path = Path(settings.BASE_DIR) / relative_path
        self.assertTrue(path.exists(), f"missing {relative_path}")
        return path.read_text()

    def test_each_component_writes_the_direction_when_applying(self):
        for relative_path in self.COMPONENTS:
            with self.subTest(component=relative_path):
                source = self._source(relative_path)
                applied = source.split("applySavedFilter(filter) {", 1)
                self.assertEqual(len(applied), 2, "no applySavedFilter to check")
                # The body ends at the next method; 2000 characters covers
                # the longest of the two by a wide margin.
                self.assertIn(
                    "filters.sortDirection",
                    applied[1][:2000],
                    "applySavedFilter no longer restores sortDirection, so a "
                    "saved filter loses its sort direction when applied",
                )

    def test_each_component_stores_the_direction_when_saving(self):
        # The other half of the round trip: restoring a key nothing saves
        # would be just as broken, and reads as correct in isolation.
        for relative_path in self.COMPONENTS:
            with self.subTest(component=relative_path):
                self.assertIn("sortDirection", self._source(relative_path))

    def test_the_minified_copies_carry_it(self):
        for relative_path in self.COMPONENTS:
            minified = relative_path.replace(".js", ".min.js")
            with self.subTest(component=minified):
                self.assertIn("sortDirection", self._source(minified))


class SavedFilterYearGridHookIsLiveTests(SimpleTestCase):
    """The shared year grid's saved-filter hook needs a flag to read.

    `core/includes/_year_grid.html` has always passed
    `isApplyingSavedFilter` behind a `typeof` guard, so a component without
    an `applyingSavedFilter` flag silently gets `false` and the grid treats
    a range mid-apply as a hover preview. The guard means the omission
    cannot throw, which is exactly why it needs a test.
    """

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_the_grid_still_asks_for_the_flag(self):
        template = self._source("core/templates/core/includes/_year_grid.html")
        self.assertIn("isApplyingSavedFilter", template)
        self.assertIn("applyingSavedFilter", template)

    def test_the_subcomponent_consults_it(self):
        self.assertIn(
            "isApplyingSavedFilter",
            self._source("core/static/core/js/filter-subcomponents.js"),
        )

    def test_both_filter_components_define_the_flag(self):
        for relative_path in (
            "core/static/core/js/media-list-controls.js",
            "games/static/games/js/filter-component.js",
        ):
            with self.subTest(component=relative_path):
                self.assertIn(
                    "applyingSavedFilter:",
                    self._source(relative_path),
                    "the component defines no applyingSavedFilter, so the "
                    "year grid's guard resolves to false and the grid "
                    "previews a range while a saved filter is applied",
                )


class SavedFilterPartialsAreSharedTests(SimpleTestCase):
    """The saved-filter UI lives in core, and music is wired to it.

    Games keeps its own copy for now, deliberately. This records which of
    the two is on the shared partials, so the migration is a visible change
    rather than a silent drift.
    """

    PARTIALS = (
        "core/templates/core/includes/_saved_filters_dropdown.html",
        "core/templates/core/includes/_saved_filter_modals.html",
        "core/templates/core/includes/_mobile_saved_filters.html",
    )

    def test_every_shared_partial_exists(self):
        for relative_path in self.PARTIALS:
            with self.subTest(partial=relative_path):
                self.assertTrue((Path(settings.BASE_DIR) / relative_path).exists())

    def test_music_includes_all_three(self):
        pages = "".join(
            (Path(settings.BASE_DIR) / relative_path).read_text()
            for relative_path in (
                "music/templates/music/home.html",
                "music/templates/music/includes/_mobile_filter_sheet.html",
            )
        )
        for partial in (
            "core/includes/_saved_filters_dropdown.html",
            "core/includes/_saved_filter_modals.html",
            "core/includes/_mobile_saved_filters.html",
        ):
            with self.subTest(partial=partial):
                self.assertIn(partial, pages)


class ApplyingASavedFilterMustNotAnnounceAResetTests(SimpleTestCase):
    """Applying a saved filter must not announce `year-reset`/`genres-reset`.

    Those two events do not mean "refresh yourselves". The mobile sheet's
    subcomponents answer them by clearing the state outright -
    `core/includes/_mobile_filter_time.html` assigns the full year range and
    `_mobile_filter_genres.html` assigns `[]` - and the sheet shares the
    rankings page's Alpine state at every width, desktop included.

    So dispatching them *after* restoring a stored combination wiped it:
    the sort and its direction survived, while the genre and the year range
    silently did not, and the heading went on naming the unfiltered page.
    Caught in a real browser, because every server-side test passed and the
    stored JSON was correct throughout.

    The selected state in both controls is derived from `filters`
    reactively, so neither needs telling.
    """

    RESET_EVENTS = ("year-reset", "genres-reset")

    def _apply_body(self, relative_path):
        source = (Path(settings.BASE_DIR) / relative_path).read_text()
        parts = source.split("applySavedFilter(filter) {", 1)
        self.assertEqual(len(parts), 2, f"no applySavedFilter in {relative_path}")
        # Up to the next method at the same indentation.
        body = parts[1]
        end = body.find("\n        },")
        self.assertNotEqual(end, -1, "could not find the end of applySavedFilter")
        # Comments are stripped, because the comment explaining *why* the
        # reset is not dispatched necessarily names the events.
        return "\n".join(
            line for line in body[:end].split("\n") if not line.strip().startswith("//")
        )

    def test_the_mobile_subcomponents_really_do_clear_on_reset(self):
        # The premise of the rule above. If these ever stop clearing state,
        # the rule stops being necessary and this suite should be revisited.
        time_sheet = (
            Path(settings.BASE_DIR)
            / "core/templates/core/includes/_mobile_filter_time.html"
        ).read_text()
        genre_sheet = (
            Path(settings.BASE_DIR)
            / "core/templates/core/includes/_mobile_filter_genres.html"
        ).read_text()
        self.assertIn('@year-reset.window="filters.start', time_sheet)
        self.assertIn('@genres-reset.window="filters.genres = []', genre_sheet)

    def test_applying_drops_an_artist_the_page_was_opened_with(self):
        # A saved combination has no artist; a ?artists= the page carried in
        # its hidden field would otherwise narrow it.
        body = self._apply_body("core/static/core/js/media-list-controls.js")
        self.assertIn("""querySelector('[name="artists"]')""", body)
        self.assertIn("artists.value = ''", body)

    def test_the_client_heading_keeps_the_artist(self):
        # No control sets the artist, so its name rides on the hidden field;
        # without it the heading lost "by Prince" on the first client change.
        for relative_path in (
            "core/static/core/js/media-list-controls.js",
            "core/static/core/js/media-list-controls.min.js",
        ):
            with self.subTest(path=relative_path):
                source = (Path(settings.BASE_DIR) / relative_path).read_text()
                self.assertIn("dataset.label", source)
                self.assertIn(" by ", source)

    def test_neither_component_dispatches_a_reset_while_applying(self):
        for relative_path in (
            "core/static/core/js/media-list-controls.js",
            "games/static/games/js/filter-component.js",
        ):
            body = self._apply_body(relative_path)
            for event in self.RESET_EVENTS:
                with self.subTest(component=relative_path, event=event):
                    self.assertNotIn(
                        event,
                        body,
                        f"applySavedFilter announces {event}, which the "
                        f"mobile sheet answers by clearing the state the "
                        f"saved filter just restored",
                    )


class GamesGridIsClientRenderedTests(SimpleTestCase):
    """The games grid exists only once the bundle has built it.

    The server stopped rendering 100 hidden grid cards (~160 KB a page), so
    three things now have to hold or grid mode shows an empty list: the CSS
    hides the rows only when a grid exists, the page fetches the bundle at
    once for a reader in grid mode, and the filter component renders the
    grid as soon as the bundle is ready, filtered page or not. Each lives in
    a different file and nothing server-side exercises any of them.
    """

    def _read(self, relative_path):
        path = Path(settings.BASE_DIR) / relative_path
        self.assertTrue(path.exists(), f"missing {relative_path}")
        return path.read_text()

    def test_rows_are_hidden_only_once_a_grid_exists(self):
        for path in (
            "theme/static_src/src/styles.css",
            "theme/static/css/dist/styles.css",
        ):
            with self.subTest(path=path):
                css = self._read(path)
                self.assertIn(
                    "#game-list-container.view-grid:has(.game-grid) .game-row-wrapper",
                    css,
                )
                self.assertNotIn(
                    "#game-list-container.view-grid .game-row-wrapper", css
                )

    def test_grid_mode_fetches_the_bundle_at_once(self):
        page = self._read("games/templates/games/home.html")
        self.assertIn("localStorage.getItem('gameViewMode') === 'grid'", page)
        self.assertIn("pathFiltered || gridView ||", page)

    def test_the_component_renders_the_grid_when_ready(self):
        for path in (
            "games/static/games/js/filter-component.js",
            "games/static/games/js/filter-component.min.js",
        ):
            with self.subTest(path=path):
                source = self._read(path)
                self.assertIn("_needsClientGrid", source)
                self.assertRegex(source, r"\w+\._needsClientGrid\(\)")
                # The grid render keeps the URL: same filters as the server's.
                self.assertRegex(source, r"historyMethod:\s*null")
                self.assertIn(
                    "'grid-view'" if "min" not in path else '"grid-view"', source
                )


class ClientLoadMoreClaimsItsClickTests(SimpleTestCase):
    """A client-rendered Load More must load one page, not two.

    The button's own listener (filter-component.js / client-filtering.js)
    and utils-loadmore.js's delegated one on #game-results-container both
    answered the click, so every press of a client-rendered list's button
    appended two pages. Grid mode is always client-rendered now, which made
    that every grid reader's Load More.
    """

    def test_the_button_listeners_stop_the_click(self):
        for path in (
            "games/static/games/js/filter-component.js",
            "games/static/games/js/client-filtering.js",
        ):
            with self.subTest(path=path):
                source = (Path(settings.BASE_DIR) / path).read_text()
                handler = re.search(
                    r"button\.addEventListener\('click', \(event\) => \{(.{0,400})",
                    source,
                    re.S,
                )
                self.assertIsNotNone(handler, "Load More click handler changed")
                self.assertIn("event.stopPropagation();", handler.group(1))


class SharedPlayedMenuTests(SimpleTestCase):
    """Every played button opens the one #played-menu.

    The wrapper stops click propagation, so the mobile row it sits in does
    not navigate. The menu's listener therefore has to run in the capture
    phase, or it would never see a click on a button at all.
    """

    SOURCE = "games/static/games/js/played-menu.js"

    def test_the_minified_menu_is_findable(self):
        self.assertIsNotNone(finders.find("games/js/played-menu.min.js"))

    def test_the_click_listener_captures(self):
        source = (Path(settings.BASE_DIR) / self.SOURCE).read_text()
        listener = source.split("document.addEventListener('click'", 1)
        self.assertEqual(len(listener), 2, "no click listener")
        body = listener[1].split("document.addEventListener('keydown'", 1)[0]
        self.assertRegex(body.rstrip(), r"\}, true\);$")

    def test_the_post_inherits_the_csrf_header_from_the_wrapper(self):
        # htmx.ajax reads hx-headers from its source and the source's
        # ancestors, which is how the body's CSRF token reaches the POST.
        source = (Path(settings.BASE_DIR) / self.SOURCE).read_text()
        self.assertIn("source: wrapper, target: wrapper, swap: 'outerHTML'", source)


class QuickMarkTests(SimpleTestCase):
    """One click applies the picked status (core/js/quick-mark.js).

    Like the played menu, the listener has to capture: the tracking button's
    own Alpine handler would open its menu, and the wrapper stops the click
    in the bubble phase. Pinned in source and in the minified copy, because
    the pages load only the latter.
    """

    SOURCE = "core/static/core/js/quick-mark.js"
    MINIFIED = "core/static/core/js/quick-mark.min.js"

    def _read(self, path):
        return (Path(settings.BASE_DIR) / path).read_text()

    def test_the_minified_script_is_findable(self):
        self.assertIsNotNone(finders.find("core/js/quick-mark.min.js"))

    def test_the_click_listener_captures(self):
        source = self._read(self.SOURCE)
        listener = source.split("document.addEventListener('click'", 1)
        self.assertEqual(len(listener), 2, "no click listener")
        body = listener[1].split("const sync", 1)[0]
        self.assertIn("}, true);", body)
        self.assertIn("event.stopPropagation()", body)

    def test_a_double_click_does_not_undo_its_own_mark(self):
        # The second click of a double-click reports detail 2; acting on it
        # would mark and then clear the item.
        self.assertIn("event.detail >= 2", self._read(self.SOURCE))
        self.assertIn(
            "event.detail < 2", self._read("games/static/games/js/played-menu.js")
        )

    def test_a_mode_only_acts_where_a_picker_is_shown(self):
        # Otherwise a mode set on the rankings page would also take over the
        # album page's button, which has no picker to switch it off.
        source = self._read(self.SOURCE)
        active = source.split("active(scope) {", 1)[1].split("next(", 1)[0]
        self.assertIn("data-quick-mark-scope", active)

    def test_clicking_a_marked_item_again_clears_it(self):
        source = self._read(self.SOURCE)
        self.assertIn("current === mode ? 'none' : mode", source)

    def test_the_post_inherits_the_csrf_header_from_the_wrapper(self):
        for path in (self.SOURCE, self.MINIFIED):
            with self.subTest(path=path):
                source = self._read(path)
                self.assertIn("htmx.ajax(", source)
                self.assertRegex(source, r"source:\s*\w+,\s*target:\s*\w+")

    def test_the_played_menu_asks_quick_mark_before_opening(self):
        for path in (
            "games/static/games/js/played-menu.js",
            "games/static/games/js/played-menu.min.js",
        ):
            with self.subTest(path=path):
                source = self._read(path)
                self.assertIn("QuickMark.active('game')", source.replace('"', "'"))
                self.assertIn("QuickMark.mark(", source)

    def test_both_rankings_pages_load_it_before_alpine(self):
        # The picker's x-data reads window.QuickMark as Alpine initialises.
        for path in (
            "games/templates/games/home.html",
            "music/templates/music/home.html",
        ):
            with self.subTest(path=path):
                self.assertIn(
                    "window.alpineScripts.push("
                    '\'{% static "core/js/quick-mark.min.js" %}',
                    self._read(path),
                )


class LandingPagesPushOntoTheRankingsUrlTests(SimpleTestCase):
    """Filtering on a music landing page must not keep the landing path.

    The client used to push `?query` relative to the current path, so on
    `/music/genres/rock/` clearing the genre pushed `/music/genres/rock/`
    and a reload brought rock back. It now pushes onto
    `window.albumRankingsUrl`, and both popstate readers treat a landing
    page's bare path as the params it stands for.
    """

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_the_url_push_uses_the_rankings_url(self):
        source = self._source("music/static/music/js/album-client-filtering.js")
        push = source.split("pushUrl(filters, { replace = false } = {}) {", 1)[1][:1400]
        self.assertIn("window.albumRankingsUrl", push)
        self.assertNotIn("query ? `?${query}`", push)

    def test_both_popstate_readers_know_the_landing_path(self):
        filtering = self._source("music/static/music/js/album-client-filtering.js")
        self.assertIn("window.albumLandingSearch", filtering)
        self.assertIn("const params = albumUrlParams();", filtering)
        controls = self._source("core/static/core/js/media-list-controls.js")
        sync = controls.split("_syncFromUrl() {", 1)[1][:700]
        self.assertIn("settings.landingSearch", sync)

    def test_the_minified_copies_carry_it(self):
        for path, needle in (
            ("music/static/music/js/album-client-filtering.min.js", "albumRankingsUrl"),
            (
                "music/static/music/js/music-client-side-filtering.bundle.min.js",
                "albumLandingSearch",
            ),
            ("core/static/core/js/media-list-controls.min.js", "landingSearch"),
        ):
            with self.subTest(path=path):
                self.assertIn(needle, self._source(path))


class MusicHighlightScrollsOnLoadTests(SimpleTestCase):
    """A `?highlight=` link from album detail must land on the album.

    The server marked the row highlighted, but nothing on the music page
    scrolled to it, and an album past the first hundred was not rendered at
    all. The games page has always done both; music now does too, from the
    bundle, so the minified copies have to carry it.
    """

    SOURCE = "music/static/music/js/album-client-filtering.js"

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_the_highlight_is_read_and_scrolled_to_on_load(self):
        source = self._source(self.SOURCE)
        init = source.split("function initAlbumFiltering() {", 1)[1]
        self.assertIn("const highlightOnLoad = currentHighlight();", init)
        self.assertIn("scrollToAlbumById(highlightOnLoad, ", init)

    def test_an_album_past_the_rendered_rows_is_jumped_to(self):
        # A window around it, not every row above it.
        source = self._source(self.SOURCE)
        init = source.split("function initAlbumFiltering() {", 1)[1]
        self.assertIn("csf.jumpTo(position);", init)

    def test_the_minified_copies_carry_it(self):
        for path in (
            "music/static/music/js/album-client-filtering.min.js",
            "music/static/music/js/music-client-side-filtering.bundle.min.js",
        ):
            with self.subTest(path=path):
                minified = self._source(path)
                self.assertIn("scrollToAlbumById", minified)
                self.assertIn("jumpTo(", minified)


class JumpToRankRendersAWindowTests(SimpleTestCase):
    """Jump to rank renders the target's neighbourhood, not the list above it.

    Both rankings pages used to render every row from #1 down to the
    target - at game #4,000 that was 8,000 DOM rows before the page could
    scroll. The renderer now keeps a window (`windowStart`/`windowEnd`), a
    jump renders `JUMP_RADIUS` rows either side of the target, and a Load
    Previous button above the list fills back in what a jump skipped. None
    of it runs server-side, so the source is what can be pinned.
    """

    BASE = "core/static/core/js/base-renderer.js"

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_the_renderer_keeps_a_window_and_plans_jumps(self):
        source = self._source(self.BASE)
        self.assertIn("this.JUMP_RADIUS = 50;", source)
        for method in (
            "planJump(index)",
            "showRange(container, start, end",
            "loadPrevious(container",
            "adopt(items, renderedCount)",
            "windowState()",
            "captureScrollAnchor(container)",
            "getLoadPreviousHtml(state)",
        ):
            with self.subTest(method=method):
                self.assertIn(method, source)
        # The page counter assumed the rows start at #1.
        self.assertNotIn("currentPage", source)

    def test_the_games_renderer_pages_through_the_base_class(self):
        # Its own copy of render/loadMore was what the window would have
        # had to be added to twice.
        source = self._source("games/static/games/js/game-list-renderer.js")
        self.assertNotRegex(source, r"\n    loadMore\(")
        self.assertNotRegex(source, r"\n    render\(")
        self.assertIn("this.GRID_CLASS = 'game-grid';", source)

    def test_both_pages_jump_through_the_plan(self):
        games = self._source("games/static/games/js/utils-loadmore.js")
        jump = games.split("function jumpToRankClientSide(", 1)[1]
        self.assertIn("renderer.planJump(targetRank - 1)", jump)
        self.assertIn("renderer.showRange(", jump)

        music = self._source("music/static/music/js/album-client-filtering.js")
        jump = music.split("    jumpTo(position) {", 1)[1]
        self.assertIn("this.renderer.planJump(position - 1)", jump)
        self.assertIn("this.renderer.showRange(", jump)

    def test_focusing_the_games_jump_box_starts_the_engine(self):
        # The box asked only for the bundle to load. Nothing initialised the
        # engine unless a filter had already done so, so a jump on a fresh
        # page always took the server path, which fetches every page down to
        # the target.
        for path in (
            "games/static/games/js/filter-component.js",
            "games/static/games/js/filter-component.min.js",
        ):
            with self.subTest(path=path):
                self.assertRegex(
                    self._source(path),
                    r"addEventListener\(\s*[\"']acclaimed:need-csf[\"']",
                )

    def test_scrolling_to_a_position_allows_for_the_window(self):
        # Positions are absolute, but the Nth row on the page is not rank N
        # once the window starts part-way down.
        games = self._source("games/static/games/js/utils-loadmore.js")
        scroll = games.split("function scrollToAndHighlightRank(", 1)[1]
        self.assertIn("position - 1 - renderedWindowStart()", scroll)

        music = self._source("music/static/music/js/album-client-filtering.js")
        scroll = music.split("function scrollToAlbumPosition(", 1)[1]
        self.assertIn("position - 1 - offset", scroll)

    def test_load_previous_is_answered_on_both_pages(self):
        for path in (
            "games/static/games/js/utils-loadmore.js",
            "music/static/music/js/album-client-filtering.js",
        ):
            with self.subTest(path=path):
                self.assertIn("'.load-previous-button'", self._source(path))

    def test_the_minified_copies_carry_it(self):
        for path in (
            "core/static/core/js/base-renderer.min.js",
            "games/static/games/js/client-side-filtering.bundle.min.js",
            "music/static/music/js/music-client-side-filtering.bundle.min.js",
            "games/static/games/js/utils-loadmore.min.js",
        ):
            with self.subTest(path=path):
                minified = self._source(path)
                self.assertIn("load-previous-", minified)
        for path in (
            "games/static/games/js/client-side-filtering.bundle.min.js",
            "music/static/music/js/music-client-side-filtering.bundle.min.js",
        ):
            with self.subTest(path=path):
                self.assertIn("planJump", self._source(path))

    def test_both_results_partials_place_load_previous_above_the_list(self):
        for path, container in (
            (
                "games/templates/games/includes/_game_list_results.html",
                '<div id="game-list-container"',
            ),
            (
                "music/templates/music/includes/_album_list_results.html",
                '<div id="album-list-container"',
            ),
        ):
            with self.subTest(path=path):
                self.assertIn(
                    "{% include 'core/includes/_load_previous.html' %}\n" + container,
                    self._source(path),
                )


class HighlightSurvivesTheScrollTests(SimpleTestCase):
    """A `?highlight=` link or a jump must still be lit when the row arrives.

    Every highlight faded on `mouseenter` of any other row. The click that
    sends a reader there leaves the cursor over the list, and rows sliding
    under a still cursor during the smooth scroll fire `mouseenter`, so the
    highlight was gone before the row came into view. It also went on
    `#game-<id>` / `#music-<id>`, the row wrappers, which styles.css does not
    colour. One helper in utils-base.js, loaded on every page, now does it.
    """

    HELPER = "games/static/games/js/utils-base.js"
    CALLERS = (
        "games/static/games/js/utils-loadmore.js",
        "games/static/games/js/filter-component.js",
        "games/static/games/js/game-list-renderer.js",
        "core/static/core/js/base-renderer.js",
        "music/static/music/js/album-list-renderer.js",
        "music/static/music/js/album-client-filtering.js",
        "games/templates/games/home.html",
    )

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_the_helper_waits_for_the_scroll_and_a_real_pointer_move(self):
        helper = self._source(self.HELPER).split("function flashHighlight(", 1)[1]
        self.assertIn("whenScrollSettles(", helper)
        self.assertIn("addEventListener('mousemove'", helper)
        self.assertNotIn("mouseenter'", helper)
        # The wrapper is resolved to the row the CSS colours
        self.assertIn(".map(highlightableElement)", helper)

    def test_every_highlight_goes_through_it(self):
        for path in self.CALLERS:
            with self.subTest(path=path):
                source = self._source(path)
                self.assertIn("flashHighlight(", source)
                self.assertNotRegex(
                    source, r"addEventListener\('mouseenter'[^\n]*\n[^\n]*fade"
                )
                self.assertNotIn("classList.remove('is-highlighted')", source)

    def test_the_minified_copies_carry_it(self):
        for path in (
            "games/static/games/js/utils-base.min.js",
            "games/static/games/js/utils-loadmore.min.js",
            "games/static/games/js/filter-component.min.js",
            "games/static/games/js/client-side-filtering.bundle.min.js",
            "music/static/music/js/music-client-side-filtering.bundle.min.js",
        ):
            with self.subTest(path=path):
                self.assertIn("flashHighlight", self._source(path))


class RankDistributionMorphsInEveryBrowserTests(SimpleTestCase):
    """The chart's curve is tweened in JavaScript, not by CSS.

    It used to morph through `transition: d`, which only Chrome and Firefox
    implement: WebKit (Safari, Orion) has no CSS `d` property, so there every
    filter change snapped. With both in place Chrome would also run the CSS
    transition against every frame the script writes.
    """

    SOURCES = (
        "games/static/games/js/rank-distribution.js",
        "games/static/games/js/rank-distribution.min.js",
    )

    def test_curve_is_tweened_with_animation_frames(self):
        for relative_path in self.SOURCES:
            with self.subTest(path=relative_path):
                source = (Path(settings.BASE_DIR) / relative_path).read_text()
                self.assertIn("requestAnimationFrame", source)
                self.assertIn("prefers-reduced-motion", source)

    def test_no_css_transition_on_the_path(self):
        styles = (
            Path(settings.BASE_DIR) / "theme/static_src/src/styles.css"
        ).read_text()
        self.assertNotRegex(styles, r"transition:\s*d\b")


class FilterSidebarLookupsAreIndexedTests(SimpleTestCase):
    """The sidebar's per-row helpers look items up by index, not by scanning.

    Every platform, genre and series row ran `find()`/`filter()` over the
    page's reactive array in its bindings, and a year change re-evaluates
    every row, so one filter change cost hundreds of full scans through
    Alpine's proxy - ~90 ms of a ~130 ms update on a fast machine. The
    desktop series list also sorted that reactive array in place on every
    read, writing every index and re-triggering its own readers.
    """

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_platform_and_series_lookups_use_an_index(self):
        source = self._source("games/static/games/js/filter-subcomponents.js")
        self.assertIn("indexBy(platforms,", source)
        self.assertIn(
            "function indexBy(", self._source("games/static/games/js/utils-base.js")
        )
        self.assertNotIn("platforms.find(", source)
        self.assertNotIn("seriesList.find(", source)

    def test_series_list_is_sorted_on_a_copy(self):
        source = self._source("games/static/games/js/filter-subcomponents.js")
        getter = source[source.index("get filteredSeries()") :]
        getter = getter[: getter.index("toggleSeries")]
        self.assertIn("(seriesList || []).slice()", getter)

    def test_genre_tree_lookups_use_an_index(self):
        source = self._source("core/static/core/js/filter-subcomponents.js")
        self.assertIn("function buildGenreIndex(", source)
        code = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("*")
        )
        self.assertNotIn("genres.find(", code)

    def test_minified_copies_are_current(self):
        for minified in (
            "games/static/games/js/filter-subcomponents.min.js",
            "core/static/core/js/filter-subcomponents.min.js",
        ):
            with self.subTest(path=minified):
                self.assertIn("indexBy(", self._source(minified))


class DiscreteFilterChangesApplyAtOnceTests(SimpleTestCase):
    """A single filter click is not held back by the debounce.

    The trailing 150 ms debounce was most of the time between clicking a
    year or genre and seeing the list change. It now fires on the leading
    edge and still coalesces a burst into one trailing update.
    """

    def test_filter_debounce_is_leading_edge(self):
        for relative_path in (
            "games/static/games/js/filter-component.js",
            "games/static/games/js/filter-component.min.js",
        ):
            with self.subTest(path=relative_path):
                source = (Path(settings.BASE_DIR) / relative_path).read_text()
                self.assertIn(
                    "_debouncedFilter=debounceLeading(",
                    source.replace(" ", "").replace("this.", ""),
                )

    def test_helper_is_defined_where_the_page_loads_it(self):
        for relative_path in (
            "games/static/games/js/utils-base.js",
            "games/static/games/js/utils-base.min.js",
        ):
            with self.subTest(path=relative_path):
                source = (Path(settings.BASE_DIR) / relative_path).read_text()
                self.assertIn("function debounceLeading(", source)


class LeadingFilterUpdatesCannotBeOverwrittenTests(SimpleTestCase):
    """Guards around the leading-edge filter update.

    Fired at once, a click made before the client engine is ready would
    start a server render whose response could land after a newer client
    update and swap the older results back in, so the leading edge waits
    for the engine; until then a burst is the old trailing debounce.
    """

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_leading_edge_waits_for_the_client_engine(self):
        source = self._source("games/static/games/js/filter-component.js")
        self.assertIn("canLead: () => this.clientFilterReady", source)

    def test_back_restores_without_pushing_a_new_entry(self):
        source = self._source("games/static/games/js/filter-component.js")
        popstate = source[source.index("requestClientFilteringInit('popstate')") :]
        self.assertIn(
            "this.performClientUpdate({ historyMethod: null });",
            popstate[: popstate.index("}") + 400],
        )

    def test_a_burst_replaces_rather_than_adds_a_history_entry(self):
        source = self._source("games/static/games/js/filter-component.js")
        self.assertIn(
            "historyMethod: burst.followsLeading ? 'replaceState' : 'pushState'",
            source,
        )


class AlbumFilterClicksApplyAtOnceTests(SimpleTestCase):
    """The album page's filter clicks, as the games page's.

    `mediaListControls` waited out a 250 ms trailing debounce before every
    commit. It now fires on the leading edge once the album engine can
    answer, marks a burst's trailing commit so the engine replaces rather
    than adds a history entry, and re-sends the facet counts to filter
    components created after the last update.
    """

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_commit_is_leading_edge_once_the_engine_is_ready(self):
        for path in (
            "core/static/core/js/media-list-controls.js",
            "core/static/core/js/media-list-controls.min.js",
        ):
            with self.subTest(path=path):
                source = self._source(path)
                self.assertIn("debounceLeading(", source)
                self.assertIn("_clientEngineReady()", source)

    def test_late_components_get_the_counts(self):
        controls = self._source("core/static/core/js/media-list-controls.js")
        self.assertIn("window.addEventListener('mobile-filter-opened'", controls)
        engine = self._source("music/static/music/js/album-client-filtering.js")
        self.assertIn("republishFacets() {", engine)

    def test_a_burst_replaces_its_history_entry(self):
        engine = self._source("music/static/music/js/album-client-filtering.js")
        self.assertIn("event.detail && event.detail.historyReplace", engine)
        self.assertIn("window.history[replace ? 'replaceState' : 'pushState']", engine)
        bundle = self._source(
            "music/static/music/js/music-client-side-filtering.bundle.min.js"
        )
        self.assertIn("historyReplace", bundle)


class MobileFilterSheetIsSharedTests(SimpleTestCase):
    """Both rankings pages use one lazy mobile sheet component.

    The flag the sheet's `<template x-if>` reads and the event its first open
    sends were two hand-kept copies, one per page; a change to either would
    have left the other sheet's late components without facet counts.
    """

    def test_one_component_registered_in_core(self):
        source = (
            Path(settings.BASE_DIR) / "core/static/core/js/filter-subcomponents.js"
        ).read_text()
        self.assertIn(
            'Alpine.data("mobileFilterSheet", createMobileFilterSheet);', source
        )

    def test_both_pages_use_it(self):
        for template in (
            "games/templates/includes/_advanced_filters.html",
            "music/templates/music/home.html",
        ):
            with self.subTest(template=template):
                source = (Path(settings.BASE_DIR) / template).read_text()
                self.assertIn('x-data="mobileFilterSheet()"', source)
                self.assertNotIn("hasOpenedBefore: false", source)


class JumpToRankReadsLandingPagePathsTests(SimpleTestCase):
    """Jump to rank must see the filters a clean SEO path carries.

    A filter state with its own landing page is pushed as that path
    (`/games/2010s/`) with no query string, and `getFiltersFromURL` read only
    the query string. Filtered to the 2010s (348 games), a jump to 500 passed
    validation against the whole ranking and re-rendered the list unfiltered
    at "450-550 of 1,400". Checked in Chrome on 2026-10-26; this pins the
    source and the minified copy the page loads.
    """

    def _source(self, relative_path):
        path = Path(settings.BASE_DIR) / relative_path
        self.assertTrue(path.exists(), f"missing {relative_path}")
        return path.read_text()

    def test_the_filters_are_read_from_a_landing_path(self):
        for path in (
            "games/static/games/js/utils-loadmore.js",
            "games/static/games/js/utils-loadmore.min.js",
        ):
            with self.subTest(path=path):
                source = self._source(path)
                body = source[source.index("function getFiltersFromURL") :]
                self.assertIn("currentFilterParams()", body[:400])

    def test_client_rendered_ranks_read_the_path_too(self):
        for path in (
            "games/static/games/js/client-filtering.js",
            "games/static/games/js/client-side-filtering.bundle.min.js",
        ):
            with self.subTest(path=path):
                source = self._source(path)
                start = re.search(r"_computeShowRank\(\)\s*\{", source).start()
                self.assertIn("currentFilterParams()", source[start : start + 300])

    def test_the_helper_merges_the_path_with_the_query_string(self):
        for path in (
            "games/static/games/js/utils-base.js",
            "games/static/games/js/utils-base.min.js",
        ):
            with self.subTest(path=path):
                source = self._source(path)
                body = source[source.index("function currentFilterParams") :]
                self.assertIn("seoPathSearch(window.location.pathname)", body[:400])


class AFullYearRangeStaysOutOfTheAddressTests(SimpleTestCase):
    """Every filtered games URL carried start=1971&end=2025, and clearing a
    year left the visitor on /games/?start=1971&end=2025 rather than /.
    Checked in Chrome with the mouse and the keyboard on 2026-10-26."""

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def test_the_pushed_url_drops_the_whole_range(self):
        for path in (
            "games/static/games/js/filter-component.js",
            "games/static/games/js/filter-component.min.js",
        ):
            with self.subTest(path=path):
                source = self._source(path)
                start = source.index("_filterUrl()")
                body = source[start : start + 900]
                self.assertIn('delete("start")', body.replace("'", '"'))


class NameSortSurvivesAnOldPayloadTests(SimpleTestCase):
    """game-cache.js keeps a payload five minutes without asking for its
    version, so a visitor can hold one from before `ni` existed; the sort
    falls back to comparing names rather than returning NaN for every pair."""

    def test_the_comparator_checks_for_ni(self):
        for path in (
            "games/static/games/js/client-filter.js",
            "games/static/games/js/client-side-filtering.bundle.min.js",
        ):
            with self.subTest(path=path):
                source = (Path(settings.BASE_DIR) / path).read_text()
                self.assertIn("localeCompare", source)
                # Either operand order: terser writes `void 0!==e.ni`
                self.assertRegex(
                    source,
                    r"\.ni\s*!==\s*(void 0|undefined)"
                    r"|(void 0|undefined)\s*!==\s*\w+\.ni",
                )


class YearGridGapsFadeWithTheirTilesTests(SimpleTestCase):
    """A range draws and undraws as one fade, its gaps with its tiles.

    The gaps were box-shadows on a selected tile, so under `transition-all`
    they grew from no offset while the tile cross-faded: 60 ms into the 150 ms,
    a tile was 55% there and its gaps 92%. Colour-only shadows fixed that and
    still failed on the Clear button: the tile's background ran off the main
    thread, the shadow could not, and the list render Clear sets off blocks it,
    so at 4x CPU the tiles finished at ~220 ms and the gaps started at ~640 ms.
    A background-color on a generated box waits the same way. So the fill and
    the gaps are all boxes fading opacity, and one tile owns each gap, or their
    alphas would stack. Nothing frozen shows this; measure real frames, and
    look at them: a matching percentage is not a matching colour.
    """

    GRID_RULE = r"([^{}]*year-grid[^{}]*)\{([^{}]*)\}"

    def _source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text()

    def _rules(self):
        built = self._source("theme/static/css/dist/styles.css")
        return re.findall(self.GRID_RULE, built)

    def test_the_state_classes_only_turn_the_boxes_on(self):
        for path in (
            "theme/static_src/src/styles.css",
            "theme/static/css/dist/styles.css",
        ):
            with self.subTest(path=path):
                source = self._source(path)
                for name in ("right", "bottom", "corner"):
                    self.assertRegex(source, rf"--gap-bridge-{name}:\s*1\b")
                self.assertRegex(source, r"--year-fill:\s*1\b")
                self.assertNotRegex(source, r"--gap-bridge-[a-z-]+:[^;}]*px")

    def test_every_part_of_a_tile_fades_opacity(self):
        rules = self._rules()
        for selector, opacity in (
            (".year-grid-cell:before", "--year-fill"),
            (".year-grid-decade:before", "--year-fill"),
            (".year-grid-cell:after", "--gap-bridge-right"),
            (".year-grid-decade:after", "--gap-bridge-right"),
            (".year-grid-cell-label:before", "--gap-bridge-bottom"),
            (".year-grid-decade>span:before", "--gap-bridge-bottom"),
            (".year-grid-cell-label:after", "--gap-bridge-corner"),
            (".year-grid-decade>span:after", "--gap-bridge-corner"),
        ):
            with self.subTest(selector=selector):
                declarations = " ".join(
                    body
                    for selectors, body in rules
                    if selector in selectors.split(",")
                )
                self.assertIn(f"opacity:var({opacity})", declarations)
                self.assertIn("transition-property:opacity", declarations)

    def test_the_gaps_leave_first_and_arrive_last(self):
        # In exact step with the fill they read as lingering: the primary
        # colour stays green over the page background, and turns tan over the
        # heatmap by half way. Both fades still span the fill's 150 ms.
        source = self._source("theme/static_src/src/styles.css")
        self.assertIn("transition-duration: 100ms;", source)
        self.assertRegex(
            source,
            r"\.year-grid-cell\.is-in-range\.sharp-right::after,"
            r"[^{}]*\{\s*transition-delay: 50ms;",
        )

    def test_the_boxes_overlap_at_every_join(self):
        # Meeting exactly left a hairline at every join at a fractional display
        # scale (browser zoom, or Windows scaling), and only there.
        source = self._source("theme/static_src/src/styles.css")
        self.assertIn("left-[calc(100%-1px)] w-1", source)
        self.assertIn("top-[calc(100%-1px)] left-0 right-0 h-1", source)
        self.assertIn("-right-[3px] -bottom-[3px] size-1", source)
        for side, flag in (
            ("top", "--shared-top"),
            ("right", "--gap-bridge-right"),
            ("bottom", "--gap-bridge-bottom"),
            ("left", "--shared-left"),
        ):
            with self.subTest(side=side):
                self.assertIn(f"{side}: calc(-1px * var({flag}));", source)

    def test_a_range_fades_nothing_but_opacity(self):
        # Whatever fades in a range has to keep moving through a list render,
        # or it lags the rest. The tile's own fades are the heatmap's and the
        # hover's, which are no part of a range.
        steps = {
            "border-top-left-radius",
            "border-top-right-radius",
            "border-bottom-right-radius",
            "border-bottom-left-radius",
            "top",
            "right",
            "bottom",
            "left",
        }
        tile = {"background-color", "filter", "outline-color"}
        rules = self._rules()
        self.assertTrue(rules)
        for selectors, body in rules:
            with self.subTest(selectors=selectors):
                self.assertNotIn("box-shadow", body)
                for listed in re.findall(r"transition-property:([^;]+)", body):
                    names = set(listed.split(","))
                    if ":before" in selectors or ":after" in selectors:
                        if names & steps:
                            # Not fades: zero-length, at the fade's far end
                            self.assertEqual(names - steps, {"opacity"})
                            self.assertRegex(
                                body, r"transition-duration:[^;]*(,\s*0s){8}"
                            )
                        else:
                            self.assertEqual(names, {"opacity"})
                    else:
                        self.assertLessEqual(names, tile, selectors)

    def test_a_corner_rounds_off_only_when_the_fill_has_gone(self):
        # Rounding a tile while the fill and gaps were solid opened a star
        # where four tiles meet, on Clear and on any range that shrank.
        rules = self._rules()
        for selectors, body in rules:
            if ".is-in-range" in selectors:
                with self.subTest(selectors=selectors):
                    self.assertNotIn("radius", body)
        fill = " ".join(
            body
            for selectors, body in rules
            if ".year-grid-cell:before" in selectors.split(",")
        )
        for corner in ("tl", "tr", "br", "bl"):
            with self.subTest(corner=corner):
                self.assertRegex(fill, rf"transition-delay:[^;]*--square-{corner}\b")

    def test_a_range_has_its_own_state_class(self):
        # The shared `.is-selected` brings a ring and a tint that only source
        # order kept off, at the same specificity.
        template = self._source("core/templates/core/includes/_year_grid.html")
        self.assertIn("'is-in-range':", template)
        self.assertNotIn("is-selected", template)

    def test_reduced_motion_waits_for_nothing(self):
        # The delays are on generated boxes, and would split a snap in two.
        source = self._source("theme/static_src/src/styles.css")
        block = re.search(
            r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", source, re.S
        ).group(1)
        self.assertIn("*::before", block)
        self.assertIn("*::after", block)
        self.assertIn("transition-delay: 0s !important", block)

    def test_a_corner_has_one_owner(self):
        template = self._source("core/templates/core/includes/_year_grid.html")
        self.assertEqual(
            set(re.findall(r"corner-[a-z]+", template)),
            {"corner-br"},
        )
