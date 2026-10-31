"""The year heatmap keeps the whole corpus as its colour scale.

The grid scaled its colours to the counts the page rendered with. Loaded
with a filter (`/music/?listened=no`, top count 1) that meant a 20-album
year asked for 1620% opacity once the filter was cleared, which the CSS
rejects, and only the previously filtered years stayed coloured. The page
now renders the corpus's counts as `year-baseline-counts-data` for the grid
to scale by, and the grid caps the opacity.
"""

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.tests.node import node_available, run_node
from music import config, models
from music.services.caching import invalidate_music_caches
from music.tests.site import music_site
from music.tests.test_views import MusicDataMixin


class YearGridScaleTests(SimpleTestCase):
    """The real grid under Node (`core/tests/js/year_grid_baseline.js`)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not node_available():
            raise cls.skipException("Node is not installed")
        cls.output = run_node("year_grid_baseline.js")

    def test_the_page_baseline_sets_the_scale(self):
        grid = self.output["withBaseline"]
        self.assertEqual((grid["maxCount"], grid["originalMaxCount"]), (20, 20))
        # The cells still show the page's own, filtered counts.
        self.assertEqual(grid["current"], [1, 0, 0])
        self.assertEqual(grid["cells"], [1970, 1971, 1972])

    def test_without_one_the_rendered_counts_are_the_scale(self):
        # Games sends none, and keeps its old behaviour.
        grid = self.output["withoutBaseline"]
        self.assertEqual((grid["maxCount"], grid["originalMaxCount"]), (1, 1))

    def test_a_count_above_the_scale_is_full_colour_not_invalid(self):
        self.assertEqual(self.output["opacityAboveScale"], "100%")

    def test_a_tile_bridges_the_gap_to_a_year_with_no_count(self):
        # A tile alone paints the gaps to its right and below, so a cell the
        # grid filled in has to count as a neighbour, and a cell it never
        # drew must not.
        self.assertEqual(
            self.output["neighbours"],
            {
                "rightOntoFilledCell": True,
                "belowOntoFilledCell": True,
                "cornerOntoFilledCell": True,
                "rightOntoNoCell": False,
            },
        )


@music_site
class AlbumYearBaselineTests(MusicDataMixin, TestCase):
    def baseline(self, **params):
        response = self.client.get(reverse("music:home"), params)
        return response, {
            entry["year"]: entry["count"]
            for entry in response.context["year_baseline_counts"]
            if entry["count"]
        }

    def test_a_filtered_page_scales_by_the_whole_corpus(self):
        response, baseline = self.baseline(q="revolver")
        self.assertEqual(baseline, {1966: 1, 1979: 1, 2000: 1})
        current = {e["year"]: e["count"] for e in response.context["year_counts"]}
        self.assertEqual(current[1979], 0)
        self.assertContains(response, 'id="year-baseline-counts-data"')

    def test_a_page_whose_counts_are_the_corpus_sends_no_second_copy(self):
        for params in ({}, {"start": "1970", "end": "1980"}):
            with self.subTest(params=params):
                response = self.client.get(reverse("music:home"), params)
                self.assertNotIn("year_baseline_counts", response.context)
                self.assertNotContains(response, 'id="year-baseline-counts-data"')

    def test_partial_and_load_more_responses_skip_it(self):
        for params, headers in (
            ({"q": "revolver"}, {"HTTP_HX_REQUEST": "true"}),
            ({"q": "revolver", "append": "true", "page": "1"}, {}),
        ):
            with self.subTest(params=params):
                response = self.client.get(reverse("music:home"), params, **headers)
                self.assertNotIn("year_baseline_counts", response.context)

    def test_new_bounds_rebuild_the_baseline(self):
        self.baseline(q="revolver")
        models.Album.objects.create(name="Early", rank=9, year_released=1950)
        # The bounds are cached apart; dropped alone, as their expiry would.
        cache.delete(config.CACHE_KEY_YEAR_STATS)
        _, baseline = self.baseline(q="revolver")
        self.assertEqual(baseline[1950], 1)

    def test_the_baseline_is_cached_and_dropped_on_import(self):
        self.baseline(genres=str(self.rock.id))
        models.Album.objects.create(name="Late", rank=9, year_released=1966)
        _, cached = self.baseline(genres=str(self.rock.id))
        self.assertEqual(cached[1966], 1)
        invalidate_music_caches()  # what an import and a metadata run call
        _, fresh = self.baseline(genres=str(self.rock.id))
        self.assertEqual(fresh[1966], 2)
