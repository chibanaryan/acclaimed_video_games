"""The music SEO ranking pages: /genres/<slug>/, /<decade>s/ on the music host.

Modelled on ``games/tests/test_landing_pages.py``.
"""

import json
import re

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from django.urls import get_resolver, resolve, reverse
from django.urls.resolvers import URLResolver

from core.models import User
from core.tests.utils import DatabaseCacheTestCase, clear_all_caches
from music import config, models, views
from music.services import landing_pages
from music.tests.site import setUpModule, tearDownModule  # noqa: F401


class LandingFixtureMixin:
    """Rock (with a style) clears the thresholds; Jazz and the 1990s do not.

    Twenty rock albums, ten in each of the 1960s and 1970s, half of them
    tagged only with the style, so a root's count has to include its subtree. Pop has
    albums only through a style of its own, which is the case the direct
    album rule exists for.
    """

    def setUp(self):
        super().setUp()
        clear_all_caches()
        self.rock = models.MusicGenre.objects.create(name="Rock", display_order=1)
        self.art_rock = models.MusicGenre.objects.create(
            name="Art Rock", parent=self.rock
        )
        self.jazz = models.MusicGenre.objects.create(name="Jazz", display_order=2)
        self.pop = models.MusicGenre.objects.create(name="Pop", display_order=3)
        self.synth_pop = models.MusicGenre.objects.create(
            name="Synth-pop", parent=self.pop
        )

        rank = 1
        self.rock_albums = []
        for index in range(20):
            album = models.Album.objects.create(
                name=f"Rock <Record> {index}",
                rank=rank,
                artist_credit="Band",
                year_released=1960 + index,
            )
            album.genres.set([self.rock] if index % 2 else [self.art_rock])
            self.rock_albums.append(album)
            rank += 1
        for index in range(3):
            album = models.Album.objects.create(
                name=f"Jazz {index}", rank=rank, year_released=1959
            )
            album.genres.set([self.jazz])
            rank += 1
        for index in range(10):
            album = models.Album.objects.create(
                name=f"Synth {index}", rank=rank, year_released=1983
            )
            album.genres.set([self.synth_pop])
            rank += 1
        for index in range(2):
            models.Album.objects.create(
                name=f"Nineties {index}", rank=rank, year_released=1994
            )
            rank += 1


class LandingServiceTests(LandingFixtureMixin, TestCase):
    def test_only_roots_with_enough_albums_and_a_direct_one_qualify(self):
        entries = landing_pages.get_landing_genres()
        self.assertEqual(
            entries,
            [
                {
                    "id": self.rock.id,
                    "name": "Rock",
                    "slug": "rock",
                    "album_count": 20,
                }
            ],
        )

    def test_a_style_is_never_a_landing_page(self):
        self.assertIsNone(landing_pages.resolve_genre_slug("art-rock"))
        self.assertIsNone(landing_pages.resolve_genre_slug("jazz"))
        self.assertEqual(landing_pages.resolve_genre_slug("rock")["id"], self.rock.id)

    def test_decades_need_enough_albums(self):
        self.assertEqual(landing_pages.get_landing_decades(), [1960, 1970, 1980])

    def test_both_lists_are_cached_under_invalidated_keys(self):
        landing_pages.get_landing_genres()
        landing_pages.get_landing_decades()
        for key in (config.CACHE_KEY_LANDING_GENRES, config.CACHE_KEY_LANDING_DECADES):
            with self.subTest(key=key):
                self.assertIn(key, config.CACHE_KEYS)
                self.assertIsNotNone(cache.get(key))
        with self.assertNumQueries(0):
            landing_pages.get_landing_genres()
            landing_pages.get_landing_decades()


class GenreLandingViewTests(LandingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("music:by-genre", kwargs={"slug": "rock"})

    def test_the_page_is_titled_by_its_filters(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "<title>Most Acclaimed Rock Albums of All Time | Acclaimed Media"
            "</title>",
            html=False,
        )
        self.assertContains(
            response,
            '<span id="search-title-text">Most Acclaimed Rock Albums of All Time'
            "</span>",
        )

    def test_the_page_is_self_canonical(self):
        response = self.client.get(self.url)
        self.assertContains(
            response,
            '<link rel="canonical" href="https://music.acclaimedmedia.org'
            '/genres/rock/">',
        )

    def test_the_page_lists_its_genre_including_the_style(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["total_count"], 20)
        self.assertEqual(response.context["filters"]["genres"], [str(self.rock.id)])

    def test_the_description_names_the_genre_and_its_count(self):
        response = self.client.get(self.url)
        self.assertIn(
            "most critically acclaimed Rock albums of all time",
            response.context["seo_meta_description"],
        )
        self.assertIn("20 acclaimed albums", response.context["seo_meta_description"])

    def test_the_itemlist_names_the_ranked_albums_and_escapes_markup(self):
        response = self.client.get(self.url)
        raw = response.context["itemlist_json"]
        self.assertNotIn("<", raw)
        payload = json.loads(raw)
        self.assertEqual(payload["@type"], "ItemList")
        self.assertEqual(payload["numberOfItems"], 20)
        first = payload["itemListElement"][0]
        self.assertEqual(first["name"], "Rock <Record> 0")
        self.assertEqual(
            first["url"],
            settings.SITE_ORIGINS["music"] + self.rock_albums[0].get_absolute_url(),
        )
        self.assertContains(response, '"@type": "ItemList"')

    def test_the_page_tells_the_client_what_its_bare_path_means(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'window.albumLandingPath = "/genres/rock/"')
        self.assertEqual(response.context["landing_search"], f"genres={self.rock.id}")
        # escapejs spells "=" as \u003D, which is still "=" to the browser.
        self.assertContains(
            response, f'window.albumLandingSearch = "genres\\u003D{self.rock.id}"'
        )
        self.assertContains(response, 'window.albumRankingsUrl = "/"')

    def test_an_explicit_param_wins_over_the_path(self):
        response = self.client.get(self.url, {"genres": str(self.pop.id)})
        self.assertEqual(response.context["total_count"], 10)

    def test_an_unknown_or_child_slug_is_a_404(self):
        for slug in ("nonexistent", "art-rock", "jazz"):
            with self.subTest(slug=slug):
                url = reverse("music:by-genre", kwargs={"slug": slug})
                self.assertEqual(self.client.get(url).status_code, 404)


class DecadeLandingViewTests(LandingFixtureMixin, TestCase):
    def test_the_page_is_titled_by_its_decade(self):
        response = self.client.get(reverse("music:by-decade", kwargs={"decade": 1970}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["seo_title"], "Most Acclaimed Albums of the 1970s"
        )
        self.assertEqual(response.context["total_count"], 10)
        self.assertIn("albums of the 1970s", response.context["seo_meta_description"])

    def test_a_decade_below_the_threshold_is_a_404(self):
        for decade in (1950, 1990, 2020):
            with self.subTest(decade=decade):
                url = reverse("music:by-decade", kwargs={"decade": decade})
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_the_rankings_page_itself_has_no_seo_extras(self):
        response = self.client.get(reverse("music:home"))
        self.assertNotIn("seo_title", response.context)
        self.assertContains(response, 'window.albumLandingPath = ""')
        self.assertContains(response, '"@type": "WebSite"')


class BrowseIndexTests(LandingFixtureMixin, TestCase):
    def test_the_index_links_every_landing_page(self):
        response = self.client.get(reverse("music:browse"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/genres/rock/"')
        for decade in (1960, 1970, 1980):
            with self.subTest(decade=decade):
                self.assertContains(response, f'href="/{decade}s/"')
        self.assertContains(response, "Albums of the 1980s")
        self.assertNotContains(response, "/genres/jazz/")


class MusicLandingPageViewTests(TestCase):
    def test_the_base_view_names_no_page(self):
        view = views.MusicLandingPageView()
        with self.assertRaises(NotImplementedError):
            view.get_page_seo()


class MusicCacheRoundTripTests(LandingFixtureMixin, DatabaseCacheTestCase):
    """The rankings pages read the shared cache in one batch, not per value.

    As games' `/` did (Sentry ACCLAIMED-VIDEO-GAMES-9E): in production every
    `cache.get` is a query on ``cache_table``. Music has no page cache, so
    every visit paid each read; a landing page's path lookups now join the
    batch too, because they run inside it (`render_rankings`).
    """

    # The batch. The articles check the nav makes is the games site's
    READS = 1

    def test_rankings_page(self):
        self.assertEqual(len(self.warm_cache_reads("/")), self.READS)

    def test_landing_pages(self):
        for url in ("/1970s/", "/genres/rock/"):
            with self.subTest(url=url):
                self.assertEqual(len(self.warm_cache_reads(url)), self.READS)

    def test_signed_in_batches_the_tracking_ids_too(self):
        User.objects.create_user(username="batched", password="pw")
        self.client.login(username="batched", password="pw")
        self.assertEqual(len(self.warm_cache_reads("/")), self.READS)


class LandingRoutingTests(TestCase):
    def test_a_decade_path_is_not_read_as_an_album_slug(self):
        self.assertEqual(resolve("/1970s/").url_name, "by-decade")
        self.assertEqual(resolve("/1975s/").url_name, "album-detail")

    def test_every_static_route_segment_is_reserved(self):
        # Album detail is the catch-all /<slug>/ at the root of the music
        # host, so a fixed first segment an album could slugify to - music's
        # own routes and the ones every site shares - would shadow that album.
        segments = set()

        def walk(patterns):
            for pattern in patterns:
                first = str(pattern.pattern).lstrip("^").split("/")[0]
                if isinstance(pattern, URLResolver) and not first:
                    walk(pattern.url_patterns)
                elif first and not first.startswith(("<", "(", "\\")):
                    # Segments that carry a "." (robots.txt) are no slug
                    if "." not in first:
                        segments.add(first.rstrip("$"))

        walk(get_resolver(settings.SITE_URLCONFS["music"]).url_patterns)
        self.assertIn("lists", segments)
        self.assertIn("accounts", segments)
        self.assertLessEqual(segments, config.RESERVED_ALBUM_SLUGS)
        self.assertTrue(re.match(config.RESERVED_ALBUM_SLUG_PATTERN, "1970s"))
