"""Tests for the /games/... SEO ranking pages."""

import importlib
import json
import re

from django.core.cache import cache
from django.test import TestCase

from core.mixins import AnonymousResponseCacheMixin
from core.models import User
from games import config
from games.models import Game, Platform, WikipediaGenre
from games.services import landing_pages
from games.sitemaps import LandingPageSitemap
from games.views import _landing_itemlist_json


class LandingPageDataMixin:
    """Shared fixtures: enough games for genre/platform/year/decade pages."""

    @classmethod
    def _root_genre(cls, name):
        # Root genres are seeded by data migrations, so reuse them if present
        genre, _ = WikipediaGenre.objects.get_or_create(name=name)
        return genre

    @classmethod
    def setUpTestData(cls):
        cls.action = cls._root_genre("Action")
        cls.maze, _ = WikipediaGenre.objects.get_or_create(
            name="Maze", defaults={"parent": cls.action}
        )
        cls.rpg = cls._root_genre("Role-Playing")
        cls.empty_genre = cls._root_genre("Strategy")

        cls.ps5 = Platform.objects.create(code="PS5", name="PlayStation 5")
        cls.pc = Platform.objects.create(code="WIN", name="Windows PC", slug="pc")
        cls.vectrex = Platform.objects.create(code="VECT", name="Vectrex")

        # 26 games in 1998 qualify the PS5/PC platforms, the 1998 year page,
        # and the 1990s decade page, and exceed TOP_N so the "full ranking"
        # link renders
        cls.games = []
        for i in range(landing_pages.MIN_PLATFORM_GAMES + 1):
            game = Game.objects.create(
                name=f"Test Game {i + 1}",
                slug=f"test-game-{i + 1}",
                rank=i + 1,
                year_of_release=1998,
            )
            game.platforms.add(cls.ps5, cls.pc)
            game.wikipedia_genres.add(cls.action)
            cls.games.append(game)

        # A child-genre game counts toward the root genre via expansion,
        # but 2005 stays below the year threshold
        cls.maze_game = Game.objects.create(
            name="Maze Game", slug="maze-game", rank=100, year_of_release=2005
        )
        cls.maze_game.wikipedia_genres.add(cls.maze)
        cls.maze_game.platforms.add(cls.vectrex)

        cls.rpg_game = Game.objects.create(
            name="RPG Game", slug="rpg-game", rank=101, year_of_release=2005
        )
        cls.rpg_game.wikipedia_genres.add(cls.rpg)
        cls.rpg_game.platforms.add(cls.pc)

    def setUp(self):
        cache.clear()


class LandingPagesServiceTests(LandingPageDataMixin, TestCase):
    """Tests for the landing_pages service module."""

    def test_landing_genres_include_roots_with_descendant_games(self):
        genres = landing_pages.get_landing_genres()
        by_slug = {g["slug"]: g for g in genres}
        self.assertIn("action", by_slug)
        # 26 direct games + 1 via the Maze child genre
        self.assertEqual(by_slug["action"]["game_count"], 27)
        self.assertIn("role-playing", by_slug)

    def test_landing_genres_exclude_empty_roots_and_children(self):
        slugs = {g["slug"] for g in landing_pages.get_landing_genres()}
        self.assertNotIn("strategy", slugs)
        self.assertNotIn("maze", slugs)

    def test_landing_platforms_respect_threshold(self):
        slugs = {p["slug"] for p in landing_pages.get_landing_platforms()}
        self.assertIn("playstation-5", slugs)
        self.assertIn("pc", slugs)
        self.assertNotIn("vectrex", slugs)

    def test_landing_years_respect_threshold(self):
        self.assertEqual(landing_pages.get_landing_years(), [1998])

    def test_landing_decades_require_games(self):
        self.assertEqual(landing_pages.get_landing_decades(), [1990, 2000])

    def test_enumerators_are_cached(self):
        landing_pages.get_landing_genres()
        landing_pages.get_landing_platforms()
        landing_pages.get_landing_years()
        landing_pages.get_landing_decades()
        with self.assertNumQueries(0):
            landing_pages.get_landing_genres()
            landing_pages.get_landing_platforms()
            landing_pages.get_landing_years()
            landing_pages.get_landing_decades()

    def test_resolve_slug_genre(self):
        kind, entry = landing_pages.resolve_slug("action")
        self.assertEqual(kind, "genre")
        self.assertEqual(entry["id"], self.action.id)

    def test_resolve_slug_platform(self):
        kind, entry = landing_pages.resolve_slug("playstation-5")
        self.assertEqual(kind, "platform")
        self.assertEqual(entry["id"], self.ps5.id)

    def test_resolve_slug_rejects_child_genres_and_unknowns(self):
        self.assertIsNone(landing_pages.resolve_slug("maze"))
        self.assertIsNone(landing_pages.resolve_slug("vectrex"))
        self.assertIsNone(landing_pages.resolve_slug("does-not-exist"))

    def test_genre_and_platform_slugs_never_collide(self):
        genre_slugs = {g["slug"] for g in landing_pages.get_landing_genres()}
        platform_slugs = {p["slug"] for p in landing_pages.get_landing_platforms()}
        self.assertEqual(genre_slugs & platform_slugs, set())


class LandingPageViewTests(LandingPageDataMixin, TestCase):
    """Tests for the landing page views."""

    def _get_itemlist(self, html):
        match = re.search(
            r'<script type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
            html,
            re.S,
        )
        return json.loads(match.group(1))

    def test_genre_page_renders_seo_elements(self):
        response = self.client.get("/games/action/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(
            "<title>Most Acclaimed Action Games of All Time " "| Acclaimed Video Games",
            html,
        )
        self.assertIn("Most Acclaimed Action Games of All Time</h1>", html)
        self.assertIn(
            'rel="canonical" '
            'href="https://www.acclaimedvideogames.com/games/action/"',
            html,
        )
        # The interactive filter component is seeded with the path-implied
        # genre so client-side filtering preserves it
        filters_match = re.search(
            r'<script id="filters-data" type="application/json">(.*?)</script>',
            html,
            re.S,
        )
        filters = json.loads(filters_match.group(1))
        self.assertEqual(filters["genres"], [str(self.action.id)])

    def test_genre_page_itemlist_json(self):
        response = self.client.get("/games/action/")
        data = self._get_itemlist(response.content.decode())
        self.assertEqual(data["@type"], "ItemList")
        self.assertEqual(data["numberOfItems"], landing_pages.TOP_N)
        first = data["itemListElement"][0]
        self.assertEqual(first["position"], 1)
        self.assertEqual(first["name"], "Test Game 1")
        self.assertIn("https://www.acclaimedvideogames.com/game/", first["url"])

    def test_genre_page_uses_natural_filter_title(self):
        response = self.client.get("/games/role-playing/")
        self.assertContains(response, "Most Acclaimed Role-Playing Games of All Time")

    def test_platform_page_renders(self):
        response = self.client.get("/games/playstation-5/")
        self.assertEqual(response.status_code, 200)
        # With PS5 as the only PlayStation platform in the fixture, the
        # family grouping collapses the natural title to "PlayStation"
        self.assertContains(response, "Most Acclaimed PlayStation Games of All Time")
        filters_match = re.search(
            r'<script id="filters-data" type="application/json">(.*?)</script>',
            response.content.decode(),
            re.S,
        )
        filters = json.loads(filters_match.group(1))
        self.assertEqual(filters["platforms"], [str(self.ps5.id)])

    def test_platform_page_uses_natural_filter_title(self):
        response = self.client.get("/games/pc/")
        self.assertContains(response, "Most Acclaimed PC Games of All Time")
        filters_match = re.search(
            r'<script id="filters-data" type="application/json">(.*?)</script>',
            response.content.decode(),
            re.S,
        )
        filters = json.loads(filters_match.group(1))
        self.assertEqual(filters["platforms"], [str(self.pc.id)])

    def test_unknown_and_child_genre_slugs_return_404(self):
        self.assertEqual(self.client.get("/games/maze/").status_code, 404)
        self.assertEqual(self.client.get("/games/vectrex/").status_code, 404)
        self.assertEqual(self.client.get("/games/unknown/").status_code, 404)

    def test_year_page_renders(self):
        response = self.client.get("/games/1998/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Most Acclaimed Video Games of 1998")
        # Year-filtered games are served, out-of-range games are not
        self.assertContains(response, 'id="game-')
        self.assertNotContains(response, f'id="game-{self.rpg_game.id}"')

    def test_year_page_below_threshold_returns_404(self):
        self.assertEqual(self.client.get("/games/2005/").status_code, 404)

    def test_decade_page_renders(self):
        response = self.client.get("/games/1990s/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Most Acclaimed Video Games of the 1990s")

    def test_decade_page_without_games_returns_404(self):
        self.assertEqual(self.client.get("/games/1970s/").status_code, 404)

    def test_top_index_lists_all_pages(self):
        response = self.client.get("/games/browse/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/games/action/")
        self.assertContains(response, "/games/playstation-5/")
        self.assertContains(response, "/games/1998/")
        self.assertContains(response, "/games/1990s/")

    def test_anonymous_responses_are_cached(self):
        self.client.get("/games/action/")
        cache_key = f"landing_page:{config.CACHE_VERSION}:/games/action/"
        payload = cache.get(cache_key)
        self.assertIsNotNone(payload)
        # Prove the second request is served from the cache
        payload["content"] = b"CACHED MARKER"
        cache.set(cache_key, payload, 60)
        response = self.client.get("/games/action/")
        self.assertEqual(response.content, b"CACHED MARKER")

    def test_authenticated_responses_are_not_cached(self):
        user = User.objects.create_user(
            username="player",
            email="player@example.com",
            password="testpass123",
        )
        self.client.force_login(user)
        response = self.client.get("/games/action/")
        self.assertEqual(response.status_code, 200)
        cache_key = f"landing_page:{config.CACHE_VERSION}:/games/action/"
        self.assertIsNone(cache.get(cache_key))

    def test_query_strings_bypass_the_cache(self):
        response = self.client.get("/games/action/?utm_source=x")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            cache.get(f"landing_page:{config.CACHE_VERSION}:/games/action/")
        )

    def test_top_index_is_cached_for_anonymous_users(self):
        self.client.get("/games/browse/")
        cache_key = f"landing_page:{config.CACHE_VERSION}:/games/browse/"
        self.assertIsNotNone(cache.get(cache_key))

    def test_top_index_query_strings_bypass_the_cache(self):
        response = self.client.get("/games/browse/?utm_source=x")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            cache.get(f"landing_page:{config.CACHE_VERSION}:/games/browse/")
        )

    def test_seo_url_map_is_embedded_for_client_side_filtering(self):
        response = self.client.get("/")
        html = response.content.decode()
        match = re.search(
            r'<script id="seo-urls-data" type="application/json">(.*?)</script>',
            html,
            re.S,
        )
        data = json.loads(match.group(1))
        self.assertEqual(data["genres"][str(self.action.id)], "action")
        self.assertEqual(data["platforms"][str(self.ps5.id)], "playstation-5")
        self.assertIn(1998, data["years"])
        self.assertIn(1990, data["decades"])
        # Non-qualifying entries are excluded so JS never pushes their URLs
        self.assertNotIn(str(self.maze.id), data["genres"])
        self.assertNotIn(str(self.vectrex.id), data["platforms"])

    def test_seo_routes_eager_load_client_filtering(self):
        # Clean paths carry no query string, so the CSF loader needs the
        # server-side flag to treat them as deep-linked filter URLs
        response = self.client.get("/games/action/")
        self.assertContains(response, "var pathFiltered = true;")
        response = self.client.get("/")
        self.assertContains(response, "var pathFiltered = false;")

    def test_itemlist_json_escapes_script_breakers(self):
        game = Game.objects.create(
            name="Game </script>", rank=300, year_of_release=1998, slug="esc-game"
        )
        payload = _landing_itemlist_json("Test", [game])
        self.assertNotIn("</script>", payload)
        self.assertEqual(
            json.loads(payload)["itemListElement"][0]["name"], "Game </script>"
        )

    def test_base_seo_view_requires_page_seo(self):
        from games.views import SeoRankingPageView

        with self.assertRaises(NotImplementedError):
            SeoRankingPageView().get_page_seo()

    def test_legacy_games_redirects_still_work(self):
        # The bare /games/ redirect must survive the new sub-routes: the
        # filter JS pushes /games/?params URLs whose reloads depend on it
        response = self.client.get("/games/?genres=1")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/?genres=1")
        response = self.client.get("/games/search/?q=zelda")
        self.assertEqual(response.status_code, 301)

    def test_explicit_query_params_take_precedence(self):
        # A user interacting with filters on a /games/ page sends explicit
        # params; the path-implied filter must not clobber them
        response = self.client.get(f"/games/action/?genres={self.rpg.id}")
        self.assertEqual(response.status_code, 200)
        filters_match = re.search(
            r'<script id="filters-data" type="application/json">(.*?)</script>',
            response.content.decode(),
            re.S,
        )
        filters = json.loads(filters_match.group(1))
        self.assertEqual(filters["genres"], [str(self.rpg.id)])

    def test_full_interactive_page_is_served(self):
        response = self.client.get("/games/action/")
        html = response.content.decode()
        # Filter UI and results machinery are present
        self.assertIn('id="filters-data"', html)
        self.assertIn('id="content"', html)

    def test_mixin_requires_page_cache_key(self):
        with self.assertRaises(NotImplementedError):
            AnonymousResponseCacheMixin().get_page_cache_key()


class LandingPageSitemapTests(LandingPageDataMixin, TestCase):
    """Tests for the LandingPageSitemap class."""

    def setUp(self):
        super().setUp()
        self.sitemap = LandingPageSitemap()

    def test_items_cover_all_page_types(self):
        items = self.sitemap.items()
        self.assertIn(("games-browse", {}), items)
        self.assertIn(("games-by-category", {"slug": "action"}), items)
        self.assertIn(("games-by-category", {"slug": "playstation-5"}), items)
        self.assertIn(("games-by-year", {"year": 1998}), items)
        self.assertIn(("games-by-decade", {"decade": 1990}), items)

    def test_location_reverses_named_routes(self):
        self.assertEqual(
            self.sitemap.location(("games-by-category", {"slug": "action"})),
            "/games/action/",
        )
        self.assertEqual(self.sitemap.location(("games-browse", {})), "/games/browse/")

    def test_priority_and_changefreq(self):
        self.assertEqual(self.sitemap.priority, 0.7)
        self.assertEqual(self.sitemap.changefreq, "weekly")

    def test_sitemap_xml_includes_landing_pages(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/games/action/")


class PlatformSlugTests(TestCase):
    """Tests for the Platform slug field and backfill migration."""

    def test_save_autogenerates_slug_from_name(self):
        platform = Platform.objects.create(code="SAT", name="Sega Saturn")
        self.assertEqual(platform.slug, "sega-saturn")

    def test_save_preserves_explicit_slug(self):
        platform = Platform.objects.create(code="WIN", name="Windows PC", slug="pc")
        self.assertEqual(platform.slug, "pc")


class _FakeApps:
    """Minimal apps registry shim for calling RunPython helpers in tests."""

    def get_model(self, app_label, model_name):
        assert (app_label, model_name) == ("games", "Platform")
        return Platform

    def __init__(self):
        pass


class PlatformSlugMigrationTests(TestCase):
    """Tests for migration 0108 platform slug backfill."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module(
            "games.migrations.0108_populate_platform_slugs"
        )

    def setUp(self):
        # Simulate the pre-migration state (slugs unset)
        self.win = Platform.objects.create(code="WIN", name="Windows PC")
        self.saturn = Platform.objects.create(code="SAT", name="Sega Saturn")
        Platform.objects.update(slug=None)

    def test_forwards_applies_overrides_and_slugify(self):
        self.migration.forwards(_FakeApps(), None)
        self.win.refresh_from_db()
        self.saturn.refresh_from_db()
        self.assertEqual(self.win.slug, "pc")
        self.assertEqual(self.saturn.slug, "sega-saturn")

    def test_forwards_is_idempotent(self):
        self.migration.forwards(_FakeApps(), None)
        self.migration.forwards(_FakeApps(), None)
        self.win.refresh_from_db()
        self.assertEqual(self.win.slug, "pc")

    def test_backwards_clears_slugs(self):
        self.migration.forwards(_FakeApps(), None)
        self.migration.backwards(_FakeApps(), None)
        self.win.refresh_from_db()
        self.assertIsNone(self.win.slug)


class PlatformFamilySlugMigrationTests(TestCase):
    """Tests for migration 0110 family slug renames."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module(
            "games.migrations.0110_platform_slug_family_renames"
        )

    def setUp(self):
        self.win = Platform.objects.create(code="WIN", name="Windows PC", slug="pc")
        self.ps1 = Platform.objects.create(
            code="PS", name="PlayStation", slug="playstation"
        )

    def test_forwards_frees_family_slugs(self):
        self.migration.forwards(_FakeApps(), None)
        self.win.refresh_from_db()
        self.ps1.refresh_from_db()
        self.assertEqual(self.win.slug, "windows")
        self.assertEqual(self.ps1.slug, "playstation-1")

    def test_backwards_restores_original_slugs(self):
        self.migration.forwards(_FakeApps(), None)
        self.migration.backwards(_FakeApps(), None)
        self.win.refresh_from_db()
        self.assertEqual(self.win.slug, "pc")


class RestoreIndividualSlugMigrationTests(TestCase):
    """Tests for migration 0111 restoring individual platform slugs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module(
            "games.migrations.0111_restore_individual_platform_slugs"
        )

    def setUp(self):
        self.win = Platform.objects.create(
            code="WIN", name="Windows PC", slug="windows"
        )
        self.ps1 = Platform.objects.create(
            code="PS", name="PlayStation", slug="playstation-1"
        )

    def test_forwards_restores_original_slugs(self):
        self.migration.forwards(_FakeApps(), None)
        self.win.refresh_from_db()
        self.ps1.refresh_from_db()
        self.assertEqual(self.win.slug, "pc")
        self.assertEqual(self.ps1.slug, "playstation")

    def test_backwards_reapplies_family_era_slugs(self):
        self.migration.forwards(_FakeApps(), None)
        self.migration.backwards(_FakeApps(), None)
        self.win.refresh_from_db()
        self.assertEqual(self.win.slug, "windows")


class SiteDomainMigrationTests(TestCase):
    """Tests for migration 0109 Site domain alignment."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module("games.migrations.0109_site_domain_www")

    class _Apps:
        def get_model(self, app_label, model_name):
            assert (app_label, model_name) == ("sites", "Site")
            from django.contrib.sites.models import Site

            return Site

    def test_forwards_sets_canonical_domain(self):
        from django.contrib.sites.models import Site

        Site.objects.update_or_create(
            pk=1, defaults={"domain": "acclaimedvideogames.com"}
        )
        self.migration.forwards(self._Apps(), None)
        self.assertEqual(Site.objects.get(pk=1).domain, "www.acclaimedvideogames.com")
        # Idempotent
        self.migration.forwards(self._Apps(), None)
        self.assertEqual(Site.objects.get(pk=1).domain, "www.acclaimedvideogames.com")

    def test_backwards_restores_apex_domain(self):
        from django.contrib.sites.models import Site

        Site.objects.update_or_create(
            pk=1, defaults={"domain": "www.acclaimedvideogames.com"}
        )
        self.migration.backwards(self._Apps(), None)
        self.assertEqual(Site.objects.get(pk=1).domain, "acclaimedvideogames.com")
