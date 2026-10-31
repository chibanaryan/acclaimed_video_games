"""The album rankings sidebar uses the shared filter components.

It used to carry a row of decade chips and a flat <select> of every genre,
where a root genre and one of its styles were indistinguishable. It now
renders `core/includes/_year_grid.html` and `core/includes/_genre_filter.html`
- the same two the games rankings page renders - which need their data in a
particular shape, and need facet counts that respond to the other filters.
"""

from bs4 import BeautifulSoup
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse

from core.models import User
from music import models, views
from music.tests.test_views import MusicDataMixin
from music.tests.site import setUpModule, tearDownModule  # noqa: F401


class GenreTreeDataTests(MusicDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.electronic = models.MusicGenre.objects.create(name="Electronic")
        self.ambient = models.MusicGenre.objects.create(
            name="Ambient", parent=self.electronic, level=1
        )
        self.kid_a.genres.set([self.electronic, self.ambient])

    def test_options_carry_the_shape_the_shared_tree_reads(self):
        options = {option["name"]: option for option in views.genre_tree_options()}
        self.assertEqual(options["Ambient"]["level"], 1)
        self.assertEqual(options["Ambient"]["parent_id"], self.electronic.id)
        # The tree calls it item_count; games' payload calls it game_count.
        self.assertEqual(options["Ambient"]["item_count"], 1)

    def test_the_page_renders_the_tree_and_not_a_flat_select(self):
        page = self.client.get(reverse("music:home")).content.decode()
        soup = BeautifulSoup(page, "html.parser")
        self.assertTrue(soup.select(".genre-filter"))
        self.assertTrue(soup.select(".genre-tree"))
        self.assertIsNone(soup.select_one('select[name="genres"]'))
        # The form still carries the selection, as a field HTMX can send.
        self.assertEqual(
            soup.select_one('#album-filters [name="genres"]')["type"], "hidden"
        )

    def test_the_tree_gets_the_music_icon_map(self):
        page = self.client.get(reverse("music:home")).content.decode()
        soup = BeautifulSoup(page, "html.parser")
        block = soup.select_one("#genre-icons-data")
        self.assertIsNotNone(block, "the genre tree has no icon map")
        self.assertIn("Electronic", block.text)


class YearGridTests(MusicDataMixin, TestCase):
    def test_the_page_renders_the_heatmap(self):
        page = self.client.get(reverse("music:home")).content.decode()
        soup = BeautifulSoup(page, "html.parser")
        self.assertTrue(soup.select(".year-grid-wrapper"))
        self.assertTrue(soup.select("#year-counts-data"))

    def test_the_year_range_is_carried_by_hidden_fields(self):
        page = self.client.get(reverse("music:home")).content.decode()
        soup = BeautifulSoup(page, "html.parser")
        for name in ("start", "end"):
            with self.subTest(field=name):
                field = soup.select_one(f'#album-filters [name="{name}"]')
                self.assertEqual(field["type"], "hidden")

    def test_the_grid_counts_albums_per_year(self):
        response = self.client.get(reverse("music:home"))
        counts = {row["year"]: row["count"] for row in response.context["year_counts"]}
        self.assertEqual(counts[1966], 1)
        self.assertEqual(counts[2000], 1)


class FacetCountTests(MusicDataMixin, TestCase):
    """A facet count answers "how many would this leave me"."""

    def test_year_counts_ignore_the_year_filter_itself(self):
        # Otherwise every cell outside the selected range would read zero and
        # there would be no way to widen the range from the grid.
        response = self.client.get(reverse("music:home"), {"start": 1966, "end": 1966})
        counts = {row["year"]: row["count"] for row in response.context["year_counts"]}
        self.assertEqual(counts[1979], 1)
        self.assertEqual(counts[2000], 1)

    def test_year_counts_do_respect_the_other_filters(self):
        response = self.client.get(reverse("music:home"), {"q": "revolver"})
        counts = {row["year"]: row["count"] for row in response.context["year_counts"]}
        self.assertEqual({year for year, count in counts.items() if count}, {1966})

    def test_the_whole_year_range_is_sent_however_narrow_the_filter(self):
        """The grid builds its decades from this array, not from min/max.

        Sending only the years a filter covers shrank the grid to those
        decades on a page load, so refreshing on a narrow genre left most
        of the timeline with no cells at all.
        """
        narrow = models.MusicGenre.objects.create(name="Dub")
        self.kid_a.genres.set([narrow])
        response = self.client.get(reverse("music:home"), {"genres": str(narrow.id)})
        counts = response.context["year_counts"]
        years = [row["year"] for row in counts]
        self.assertEqual(
            years,
            list(range(response.context["min_year"], response.context["max_year"] + 1)),
        )
        # The filter still shows through, as zeros.
        self.assertEqual({row["year"] for row in counts if row["count"]}, {2000})

    def test_an_album_matching_two_genres_in_the_subtree_counts_once(self):
        # The genre filter joins through an M2M, so without `distinct` the
        # album is counted once per matching genre.
        rock = models.MusicGenre.objects.create(name="Prog")
        style = models.MusicGenre.objects.create(name="Krautrock", parent=rock, level=1)
        self.revolver.genres.set([rock, style])
        response = self.client.get(reverse("music:home"), {"genres": str(rock.id)})
        counts = {row["year"]: row["count"] for row in response.context["year_counts"]}
        self.assertEqual(counts[1966], 1)

    def test_two_albums_in_one_year_count_two_under_a_genre_filter(self):
        # The genre filter's `.distinct()` pulled `Album`'s default `rank`
        # ordering into the GROUP BY, so each album was its own group and
        # every year cell read 1 however many albums it held.
        pop = models.MusicGenre.objects.create(name="Pop")
        twin = models.Album.objects.create(
            name="Rubber Soul", slug="rubber-soul", rank=4, year_released=1966
        )
        self.revolver.genres.set([pop])
        twin.genres.set([pop])
        response = self.client.get(reverse("music:home"), {"genres": str(pop.id)})
        counts = {row["year"]: row["count"] for row in response.context["year_counts"]}
        self.assertEqual(counts[1966], 2)

    def test_genre_counts_ignore_the_genre_filter_itself(self):
        electronic = models.MusicGenre.objects.create(name="Electronic")
        self.kid_a.genres.set([electronic])
        response = self.client.get(reverse("music:home"), {"genres": str(self.rock.id)})
        counts = response.context["genre_counts"]
        self.assertEqual(counts[str(electronic.id)], 1)

    def test_genre_counts_respect_the_year_filter(self):
        response = self.client.get(reverse("music:home"), {"start": 1990})
        self.assertEqual(response.context["genre_counts"], {})

    def test_the_counts_are_rendered_for_the_sidebar_to_pick_up(self):
        page = self.client.get(reverse("music:home")).content.decode()
        soup = BeautifulSoup(page, "html.parser")
        self.assertTrue(soup.select("#year-counts-update"))
        self.assertTrue(soup.select("#genre-counts-update"))


class FilterStateTests(MusicDataMixin, TestCase):
    def test_the_component_starts_from_the_servers_filter_state(self):
        response = self.client.get(
            reverse("music:home"),
            {"q": "rust", "start": 1970, "end": 1979, "genres": str(self.rock.id)},
        )
        filters = response.context["filters"]
        self.assertEqual(filters["q"], "rust")
        self.assertEqual(filters["start"], 1970)
        self.assertEqual(filters["end"], 1979)
        self.assertEqual(filters["genres"], [str(self.rock.id)])

    def test_an_absent_year_range_becomes_the_full_range(self):
        # The grid spells "no year filter" as the whole range selected; the
        # URL spells it as no parameters at all.
        response = self.client.get(reverse("music:home"))
        filters = response.context["filters"]
        self.assertEqual(filters["start"], response.context["min_year"])
        self.assertEqual(filters["end"], response.context["max_year"])

    def test_the_state_is_rendered_as_json_for_the_component(self):
        page = self.client.get(reverse("music:home")).content.decode()
        soup = BeautifulSoup(page, "html.parser")
        self.assertTrue(soup.select("#filters-data"))
        self.assertTrue(soup.select("#genres-data"))


class ApplyAlbumFiltersTests(MusicDataMixin, TestCase):
    """The filter function the page and its facet counts share."""

    def _names(self, queryset):
        return sorted(queryset.values_list("name", flat=True))

    def test_every_dimension_applies(self):
        base = models.Album.objects.all()
        self.assertEqual(
            self._names(views.apply_album_filters(base, {"q": "revolver"})),
            ["Revolver"],
        )
        self.assertEqual(
            self._names(views.apply_album_filters(base, {"start": "2000"})),
            ["Kid A"],
        )
        self.assertEqual(
            self._names(views.apply_album_filters(base, {"genres": str(self.rock.id)})),
            ["Revolver"],
        )
        self.assertEqual(
            self._names(views.apply_album_filters(base, {"artists": self.young.slug})),
            ["Rust Never Sleeps"],
        )

    def test_a_skipped_dimension_is_left_out(self):
        base = models.Album.objects.all()
        params = {"q": "revolver", "start": "2000"}
        self.assertEqual(self._names(views.apply_album_filters(base, params)), [])
        self.assertEqual(
            self._names(views.apply_album_filters(base, params, skip=("year",))),
            ["Revolver"],
        )
        self.assertEqual(
            self._names(views.apply_album_filters(base, params, skip=("q",))),
            ["Kid A"],
        )


class GenreHierarchyTests(MusicDataMixin, TestCase):
    """Selecting a genre includes its styles, as the games filter does."""

    def setUp(self):
        super().setUp()
        self.classical = models.MusicGenre.objects.create(name="Classical")
        self.modern = models.MusicGenre.objects.create(
            name="Modern Classical", parent=self.classical, level=1
        )
        # One album, carrying both the root and the style - the shape that
        # made the sidebar claim Classical had two albums.
        self.kid_a.genres.set([self.classical, self.modern])

    def test_selecting_a_root_matches_its_styles(self):
        response = self.client.get(
            reverse("music:home"), {"genres": str(self.classical.id)}
        )
        self.assertEqual(
            [album.name for album in response.context["albums"]], ["Kid A"]
        )

    def test_a_style_only_matches_itself(self):
        other = models.Album.objects.create(name="Orchestral", rank=9)
        other.genres.set([self.classical])
        response = self.client.get(
            reverse("music:home"), {"genres": str(self.modern.id)}
        )
        self.assertEqual(
            [album.name for album in response.context["albums"]], ["Kid A"]
        )

    def test_an_album_is_counted_once_per_subtree(self):
        counts = self.client.get(reverse("music:home")).context["genre_counts"]
        self.assertEqual(counts[str(self.classical.id)], 1)
        self.assertEqual(counts[str(self.modern.id)], 1)

    def test_the_unfiltered_tree_counts_match(self):
        options = {o["name"]: o["item_count"] for o in views.genre_tree_options()}
        self.assertEqual(options["Classical"], 1)
        self.assertEqual(options["Modern Classical"], 1)

    def test_a_root_count_sums_distinct_albums_across_its_styles(self):
        jazz = models.Album.objects.create(name="Ascension", rank=8)
        jazz.genres.set([self.modern])
        counts = self.client.get(reverse("music:home")).context["genre_counts"]
        self.assertEqual(counts[str(self.classical.id)], 2)


class AlbumDownloadTests(MusicDataMixin, TestCase):
    """The CSV the sidebar offers, as the games sidebar does."""

    def _rows(self, **params):
        response = self.client.get(reverse("music:download"), params)
        self.assertEqual(response.status_code, 200)
        return response.content.decode().splitlines()

    def test_the_csv_carries_a_header_and_every_album(self):
        rows = self._rows()
        self.assertTrue(rows[0].startswith("Filtered Rank,Global Rank,Name,Year"))
        self.assertEqual(len(rows), 4)

    def test_it_respects_the_current_filters(self):
        rows = self._rows(q="revolver")
        self.assertEqual(len(rows), 2)
        self.assertIn("Revolver", rows[1])

    def test_the_filename_is_the_heading(self):
        response = self.client.get(
            reverse("music:download"), {"start": 1970, "end": 1979}
        )
        self.assertIn(
            "most-acclaimed-albums-of-the-1970s.csv",
            response["Content-Disposition"],
        )


class ListenStatusFilterTests(MusicDataMixin, TestCase):
    """The listen-status dimension of `apply_album_filters`."""

    def setUp(self):
        super().setUp()
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.revolver, wikidata_id="Q-revolver"
        )
        models.WantToListenAlbum.objects.create(
            user=self.user, album=self.rust, wikidata_id="Q-rust"
        )
        # Kid A is tracked by neither.

    def _names(self, params, **kwargs):
        base = models.Album.objects.with_listen_status(self.user)
        kwargs.setdefault("user", self.user)
        return sorted(
            views.apply_album_filters(base, params, **kwargs).values_list(
                "name", flat=True
            )
        )

    def test_listened_shows_only_what_was_listened_to(self):
        self.assertEqual(self._names({"listened": "yes"}), ["Revolver"])

    def test_want_shows_only_the_backlog(self):
        self.assertEqual(self._names({"listened": "want"}), ["Rust Never Sleeps"])

    def test_untracked_shows_what_is_tracked_by_neither(self):
        self.assertEqual(self._names({"listened": "no"}), ["Kid A"])

    def test_several_statuses_are_or_ed_together(self):
        # The point of the multi-select: the backlog and the untracked read
        # as "everything I have not heard".
        self.assertEqual(
            self._names({"listened": "want,no"}),
            ["Kid A", "Rust Never Sleeps"],
        )

    def test_all_three_statuses_match_everything(self):
        self.assertEqual(
            self._names({"listened": "yes,want,no"}),
            ["Kid A", "Revolver", "Rust Never Sleeps"],
        )

    def test_an_unknown_value_is_ignored(self):
        # A hand-edited URL narrows nothing rather than erroring.
        self.assertEqual(len(self._names({"listened": "sideways"})), 3)

    def test_an_unknown_value_among_known_ones_is_dropped(self):
        self.assertEqual(self._names({"listened": "yes,sideways"}), ["Revolver"])

    def test_an_empty_value_is_ignored(self):
        self.assertEqual(len(self._names({"listened": ""})), 3)

    def test_whitespace_is_tolerated(self):
        self.assertEqual(
            self._names({"listened": " yes , want "}),
            ["Revolver", "Rust Never Sleeps"],
        )

    def test_the_dimension_can_be_skipped(self):
        self.assertEqual(len(self._names({"listened": "yes"}, skip=("listened",))), 3)

    def test_another_users_tracking_does_not_show(self):
        stranger = User.objects.create_user(username="stranger", password="pw")
        base = models.Album.objects.with_listen_status(stranger)
        names = sorted(
            views.apply_album_filters(
                base, {"listened": "yes"}, user=stranger
            ).values_list("name", flat=True)
        )
        self.assertEqual(names, [])

    def test_it_is_a_no_op_without_a_user(self):
        # The three-positional call shape the facet counts used before this
        # dimension existed, and which the other tests here still use.
        base = models.Album.objects.all()
        self.assertEqual(len(views.apply_album_filters(base, {"listened": "yes"})), 3)

    def test_it_is_a_no_op_for_an_anonymous_user(self):
        base = models.Album.objects.all()
        self.assertEqual(
            len(
                views.apply_album_filters(
                    base, {"listened": "yes"}, user=AnonymousUser()
                )
            ),
            3,
        )

    def test_it_combines_with_another_dimension(self):
        self.assertEqual(
            self._names({"listened": "yes,want", "start": "1970"}),
            ["Rust Never Sleeps"],
        )


class ListenStatusFacetTests(MusicDataMixin, TestCase):
    """The year and genre counts respect the status filter."""

    def setUp(self):
        super().setUp()
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.revolver, wikidata_id="Q-revolver"
        )
        models.WantToListenAlbum.objects.create(
            user=self.user, album=self.rust, wikidata_id="Q-rust"
        )

    def test_the_year_counts_respect_the_status_filter(self):
        # `listened` is left out of neither skip tuple, so a year cell counts
        # what the status filter leaves - otherwise clicking 1979 under
        # "Listened" would promise a row and deliver none.
        response = self.client.get(reverse("music:home") + "?listened=yes")
        years = {
            entry["year"] for entry in response.context["year_counts"] if entry["count"]
        }
        self.assertEqual(years, {1966})

    def test_the_genre_counts_respect_the_status_filter(self):
        response = self.client.get(reverse("music:home") + "?listened=yes")
        counts = response.context["genre_counts"]
        self.assertEqual(counts.get(str(self.rock.id)), 1)

    def test_the_year_counts_ignore_the_year_filter_itself(self):
        # The existing rule, re-checked alongside a status filter: a year
        # cell is counted with the year dimension left out.
        response = self.client.get(
            reverse("music:home") + "?listened=yes,want&start=1979&end=1979"
        )
        years = {
            entry["year"] for entry in response.context["year_counts"] if entry["count"]
        }
        self.assertEqual(years, {1966, 1979})


class GenreDescendantMapTests(MusicDataMixin, TestCase):
    """The shared descendant map replaced a walk through `children`.

    The walk cost one query per genre visited - 418 of them on a `/music/`
    render. These pin that threading the map through changed none of the
    answers, which is the only thing that made the swap safe.
    """

    def setUp(self):
        super().setUp()
        self.electronic = models.MusicGenre.objects.create(name="Electronic")
        self.ambient = models.MusicGenre.objects.create(
            name="Ambient", parent=self.electronic
        )
        self.dark_ambient = models.MusicGenre.objects.create(
            name="Dark Ambient", parent=self.ambient
        )
        self.kid_a.genres.set([self.electronic, self.ambient])
        self.rust.genres.set([self.dark_ambient])

    def test_passing_the_map_gives_the_same_counts_as_building_one(self):
        built = views._genre_counts(models.Album.objects.all())
        shared = views._genre_counts(
            models.Album.objects.all(), views._genre_descendant_map()
        )
        self.assertEqual(built, shared)
        # And the key order, since the counts are serialized into the page
        # for the shared tree to read.
        self.assertEqual(list(built), list(shared))

    def test_passing_the_map_gives_the_same_tree_as_building_one(self):
        self.assertEqual(
            views.genre_tree_options(),
            views.genre_tree_options(views._genre_descendant_map()),
        )

    def test_the_map_agrees_with_the_per_instance_walk(self):
        # `MusicGenre.get_descendant_ids` stays on the model for one-off use;
        # it is the contract the map has to reproduce, ordering included.
        descendants = views._genre_descendant_map()
        for genre in models.MusicGenre.objects.all():
            with self.subTest(genre=genre.name):
                self.assertEqual(
                    descendants[genre.id],
                    genre.get_descendant_ids(include_self=False),
                )

    def test_expansion_reaches_a_grandchild_style(self):
        # Selecting Electronic has to mean Dark Ambient too, two levels down.
        self.assertEqual(
            views.expand_genre_ids([self.electronic.id]),
            sorted([self.electronic.id, self.ambient.id, self.dark_ambient.id]),
        )

    def test_expansion_keeps_an_id_that_is_not_a_genre(self):
        # It used to survive because the seed is the selection itself and the
        # table lookup simply found nothing. An unknown id has to go on
        # matching no album rather than being dropped, which would silently
        # widen the filter to everything.
        self.assertEqual(views.expand_genre_ids([999999]), [999999])
        self.assertEqual(
            views.expand_genre_ids([self.rock.id, 999999]),
            sorted([self.rock.id, 999999]),
        )

    def test_expansion_matches_the_shared_map(self):
        shared = views._genre_descendant_map()
        for genre in models.MusicGenre.objects.all():
            with self.subTest(genre=genre.name):
                self.assertEqual(
                    views.expand_genre_ids([genre.id]),
                    views.expand_genre_ids([genre.id], shared),
                )


class SavedFilterShapeTests(MusicDataMixin, TestCase):
    """What a saved filter stores has to be what the page filters on.

    `savedFilterPayload()` in `core/static/core/js/media-list-controls.js`
    enumerates the keys it stores. The server builds the same state in
    `AlbumHomePageView`'s `filters` context. Nothing joins the two, so a new
    filter dimension can be added to the page and silently not be saved -
    the dropdown would keep working and quietly drop that dimension.
    """

    #: The keys `savedFilterPayload()` writes, in that function's own order.
    SAVED_KEYS = {"q", "start", "end", "genres", "listened", "sort", "sortDirection"}

    def test_the_saved_keys_are_exactly_the_servers_filter_state(self):
        filters = self.client.get(reverse("music:home")).context["filters"]
        self.assertEqual(set(filters), self.SAVED_KEYS)

    def test_the_js_payload_names_every_one_of_them(self):
        from pathlib import Path

        from django.conf import settings

        source = (
            Path(settings.BASE_DIR) / "core/static/core/js/media-list-controls.js"
        ).read_text()
        body = source.split("savedFilterPayload() {", 1)
        self.assertEqual(len(body), 2, "no savedFilterPayload to check")
        body = body[1][:700]
        for key in self.SAVED_KEYS:
            with self.subTest(key=key):
                # `listened` is written through the statusKey variable, so
                # it is the one key that appears by indirection.
                needle = "[statusKey]" if key == "listened" else key
                self.assertIn(needle, body)

    def test_a_round_trip_through_the_api_preserves_the_state(self):
        # The end-to-end property the dropdown depends on: whatever the page
        # put in `filters` comes back out of the API byte for byte.
        state = self.client.get(
            reverse("music:home"),
            {"q": "rust", "start": 1970, "end": 1979, "genres": str(self.rock.id)},
        ).context["filters"]

        created = self.client.post(
            reverse("music-api:saved-filter-list"),
            {"name": "Seventies rock", "filters": state},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        listed = self.client.get(reverse("music-api:saved-filter-list")).json()
        self.assertEqual(listed["filter_sets"][0]["filters"], state)


class SavedFilterSidebarTests(MusicDataMixin, TestCase):
    def test_the_sidebar_offers_the_saved_dropdown(self):
        page = self.client.get(reverse("music:home")).content.decode()
        self.assertIn("loadSavedFilters()", page)

    def test_the_mobile_sheet_offers_the_saved_block(self):
        soup = BeautifulSoup(
            self.client.get(reverse("music:home")).content.decode(), "html.parser"
        )
        sheet = soup.select_one("#mobile-filter-form")
        self.assertIsNotNone(sheet)
        # The sheet's filters sit in a <template x-if> until it is first
        # opened, and get_text() leaves template content out, so check the
        # markup instead.
        self.assertIn("Saved Filters", str(sheet))

    def test_a_signed_out_visitor_never_sees_it(self):
        # Unreachable in practice - the section 404s for them - but the
        # partial is shared, so its signed-out branch is what games will
        # render once it migrates.
        from django.template.loader import render_to_string

        rendered = render_to_string(
            "core/includes/_saved_filters_dropdown.html",
            {"max_saved": 10, "user": AnonymousUser()},
        )
        self.assertNotIn("loadSavedFilters()", rendered)
        self.assertIn("Sign in to save filters", rendered)
