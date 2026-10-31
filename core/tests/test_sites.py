"""The three sites one app serves: the landing page, games and music.

``core/sites.py`` tells them apart by host and ``SiteHostMiddleware`` gives
each request its site's URLconf. These tests use the real hosts, as
production does; the test client's own ``testserver`` falls back to
``ROOT_URLCONF``, which is the games site.
"""

from unittest import mock

from django.conf import settings
from django.contrib.flatpages.models import FlatPage
from django.contrib.sites.models import Site
from django.core import mail
from django.test import (
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)

from core import sites
from core.middleware import SiteHostMiddleware
from core.tests.utils import clear_all_caches, get_on_site
from games.models import Game, IGDBGameData, List, Publication
from music.models import Album, MusicList, MusicPublication

ROOT_HOST = "acclaimedmedia.org"
GAMES_HOST = "games.acclaimedmedia.org"
MUSIC_HOST = "music.acclaimedmedia.org"


class HostMappingTests(SimpleTestCase):
    def test_each_production_host_names_its_site(self):
        self.assertEqual(sites.site_for_host(ROOT_HOST), sites.ROOT)
        self.assertEqual(sites.site_for_host(GAMES_HOST), sites.GAMES)
        self.assertEqual(sites.site_for_host(MUSIC_HOST), sites.MUSIC)

    def test_the_development_hosts_follow_the_same_rule(self):
        self.assertEqual(sites.site_for_host("localhost:8000"), sites.ROOT)
        self.assertEqual(sites.site_for_host("games.localhost:8000"), sites.GAMES)
        self.assertEqual(sites.site_for_host("MUSIC.localhost"), sites.MUSIC)

    def test_a_fully_qualified_host_names_its_site(self):
        """Django's host check accepts the trailing dot, so this must too."""
        self.assertEqual(sites.site_for_host("music.acclaimedmedia.org."), sites.MUSIC)
        self.assertEqual(sites.site_for_host("acclaimedmedia.org."), sites.ROOT)

    def test_any_other_host_names_no_site(self):
        for host in (
            "testserver",
            "127.0.0.1:8000",
            "books.acclaimedmedia.org",
            "www.acclaimedmedia.org",
            "games.example.com",
        ):
            with self.subTest(host=host):
                self.assertIsNone(sites.site_for_host(host))

    def test_an_unknown_host_belongs_to_the_root_urlconfs_site(self):
        self.assertEqual(sites.default_site(), sites.GAMES)
        with self.settings(ROOT_URLCONF=settings.SITE_URLCONFS["music"]):
            self.assertEqual(sites.default_site(), sites.MUSIC)
        with self.settings(ROOT_URLCONF="some.other.urls"):
            self.assertEqual(sites.default_site(), sites.GAMES)

    def test_every_site_has_an_origin_a_urlconf_and_a_home(self):
        for site in (sites.ROOT, sites.GAMES, sites.MUSIC):
            with self.subTest(site=site):
                self.assertTrue(settings.SITE_ORIGINS[site].startswith("https://"))
                self.assertIn(site, settings.SITE_URLCONFS)
                self.assertTrue(sites.site_reverse(site, sites.HOME_VIEWS[site]))

    def test_every_site_host_is_allowed(self):
        for host in (ROOT_HOST, GAMES_HOST, MUSIC_HOST):
            self.assertIn(host, settings.ALLOWED_HOSTS)


class SiteUrlTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_without_a_request_a_link_is_on_the_public_origin(self):
        self.assertEqual(
            sites.site_url(sites.MUSIC, "music:artist-detail", slug="prince"),
            "https://music.acclaimedmedia.org/artists/prince/",
        )
        self.assertEqual(
            sites.site_url(sites.GAMES, "home"), "https://games.acclaimedmedia.org/"
        )
        self.assertEqual(
            sites.site_url(sites.ROOT, "landing"), "https://acclaimedmedia.org/"
        )

    # `.localhost` is allowed under DEBUG alone, which a developer's .env sets
    # and CI does not
    @override_settings(ALLOWED_HOSTS=[".localhost"])
    def test_a_link_from_a_dev_host_stays_on_the_dev_server(self):
        request = self.factory.get("/", HTTP_HOST="games.localhost:8000")
        self.assertEqual(
            sites.site_url(sites.MUSIC, "music:home", request=request),
            "http://music.localhost:8000/",
        )
        self.assertEqual(
            sites.site_origin(sites.ROOT, request), "http://localhost:8000"
        )

    def test_a_link_from_an_unknown_or_disallowed_host_is_public(self):
        for host in ("testserver", "evil.example.com"):
            with self.subTest(host=host):
                request = self.factory.get("/", HTTP_HOST=host)
                self.assertEqual(
                    sites.site_origin(sites.MUSIC, request),
                    "https://music.acclaimedmedia.org",
                )

    def test_positional_url_arguments_are_passed_through(self):
        self.assertEqual(
            sites.site_url(sites.MUSIC, "music:toggle-listened", 7),
            "https://music.acclaimedmedia.org/7/toggle-listened/",
        )

    def test_the_template_tags_build_the_same_links(self):
        from django.template import Context, Template

        request = self.factory.get("/", HTTP_HOST=GAMES_HOST, secure=True)
        rendered = Template(
            "{% load core_filters %}{% site_url 'music' 'music:home' %}"
        ).render(Context({"request": request}))
        self.assertEqual(rendered, "https://music.acclaimedmedia.org/")


class MiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.seen = {}

        def view(request):
            self.seen["site"] = request.site_key
            self.seen["urlconf"] = getattr(request, "urlconf", None)

        self.middleware = SiteHostMiddleware(view)

    def test_a_known_host_gets_its_sites_urlconf(self):
        self.middleware(self.factory.get("/", HTTP_HOST=MUSIC_HOST))
        self.assertEqual(self.seen["site"], sites.MUSIC)
        self.assertEqual(self.seen["urlconf"], settings.SITE_URLCONFS["music"])

    def test_an_unknown_host_keeps_the_root_urlconf(self):
        self.middleware(self.factory.get("/", HTTP_HOST="testserver"))
        self.assertEqual(self.seen["site"], sites.GAMES)
        self.assertIsNone(self.seen["urlconf"])

    def test_a_disallowed_host_is_left_for_common_middleware(self):
        self.middleware(self.factory.get("/", HTTP_HOST="evil.example.com"))
        self.assertEqual(self.seen["site"], sites.GAMES)
        self.assertIsNone(self.seen["urlconf"])

    def test_a_request_the_middleware_never_saw_is_the_default_site(self):
        self.assertEqual(sites.request_site(self.factory.get("/")), sites.GAMES)


class RoutingTests(TestCase):
    def setUp(self):
        # Under Django's runner nothing empties the page cache between
        # tests, and the landing and games pages are cached
        clear_all_caches()

    def get(self, host, path, **extra):
        return self.client.get(path, HTTP_HOST=host, secure=True, **extra)

    def test_each_host_serves_its_own_front_page(self):
        # By the view that answered, which a page served from the cache
        # still records, where the templates rendered would be none
        self.assertEqual(self.get(ROOT_HOST, "/").resolver_match.view_name, "landing")
        self.assertEqual(self.get(GAMES_HOST, "/").resolver_match.view_name, "home")
        self.assertEqual(
            self.get(MUSIC_HOST, "/").resolver_match.view_name, "music:home"
        )

    def test_music_lives_at_the_root_of_its_host(self):
        self.assertEqual(self.get(MUSIC_HOST, "/artists/").status_code, 200)
        self.assertEqual(self.get(MUSIC_HOST, "/api/meta/").status_code, 200)
        self.assertEqual(self.get(GAMES_HOST, "/music/").status_code, 404)

    def test_the_shared_pages_are_on_every_host(self):
        page = FlatPage.objects.create(url="/about/", title="About", content="Hi")
        page.sites.add(Site.objects.get_current())
        for host in (ROOT_HOST, GAMES_HOST, MUSIC_HOST):
            with self.subTest(host=host):
                response = self.get(host, "/page/about/")
                self.assertEqual(response.status_code, 200)
                # Indexed once, at the apex
                self.assertContains(
                    response,
                    '<link rel="canonical" href="https://acclaimedmedia.org'
                    '/page/about/">',
                )

    def test_a_page_at_the_apex_has_no_sidebar_and_leads_home(self):
        page = FlatPage.objects.create(url="/about/", title="About", content="Hi")
        page.sites.add(Site.objects.get_current())
        response = self.get(ROOT_HOST, "/page/about/")
        self.assertNotContains(response, "<aside")
        self.assertContains(response, 'href="/" class="inline-block mb-6')
        self.assertContains(self.get(GAMES_HOST, "/page/about/"), "<aside")

    def test_the_contact_form_tells_the_email_which_site_sent_it(self):
        data = {"name": "Ann", "category": "general", "message": "Hello there"}
        with mock.patch("games.views.content.contact_spam_guard.evaluate") as evaluate:
            evaluate.return_value.allowed = True
            response = self.client.post(
                "/contact/", data, HTTP_HOST=MUSIC_HOST, secure=True
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].subject.startswith("[Music] [General]"))
        self.assertIn("Site: Music", mail.outbox[0].body)


class EveryHostCanServeTheSharedRoutesTests(TestCase):
    """The shared routes render on all three hosts, games-only names aside."""

    HOSTS = (ROOT_HOST, GAMES_HOST, MUSIC_HOST)

    def setUp(self):
        clear_all_caches()

    def test_an_unsubscribe_link_renders_on_every_host(self):
        # Every notification email links to it at the apex
        for host in self.HOSTS:
            with self.subTest(host=host):
                response = self.client.get(
                    "/unsubscribe/not-a-token/", HTTP_HOST=host, secure=True
                )
                self.assertEqual(response.status_code, 200)

    def test_an_email_confirmation_renders_on_every_host(self):
        # A link is built from the host the visitor signed up on
        for host in self.HOSTS:
            with self.subTest(host=host):
                response = self.client.get(
                    "/accounts/confirm-email/not-a-key/", HTTP_HOST=host, secure=True
                )
                self.assertEqual(response.status_code, 200)

    def test_an_article_links_to_the_games_host_from_any_host(self):
        # The admin's "View on site" calls this under the request's URLconf
        from django.urls import set_urlconf

        from games.models import Article

        article = Article(title="A Post", slug="a-post")
        set_urlconf(settings.SITE_URLCONFS["music"])
        self.addCleanup(set_urlconf, None)
        self.assertEqual(article.get_absolute_url(), "/blog/a-post/")


class ApexRedirectTests(TestCase):
    """Every path the apex served before the split still leads somewhere."""

    def get(self, path, **extra):
        return self.client.get(path, HTTP_HOST=ROOT_HOST, secure=True, **extra)

    def test_a_games_path_moves_to_the_games_host_with_its_query(self):
        response = self.get("/game/half-life-2/", data={"x": "1"})
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "https://games.acclaimedmedia.org/game/half-life-2/?x=1",
        )

    def test_a_music_path_moves_to_the_root_of_the_music_host(self):
        for old, new in (
            ("/music/", "/"),
            ("/music", "/"),
            ("/music/artists/prince/", "/artists/prince/"),
            ("/music/genres/rock/", "/genres/rock/"),
            ("/api/music/all/", "/api/all/"),
            ("/api/music", "/api/"),
        ):
            with self.subTest(old=old):
                response = self.get(old)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(
                    response["Location"], "https://music.acclaimedmedia.org" + new
                )

    def test_a_path_that_only_starts_like_music_is_a_games_path(self):
        self.assertEqual(
            self.get("/musical/")["Location"],
            "https://games.acclaimedmedia.org/musical/",
        )

    def test_an_encoded_character_stays_encoded(self):
        self.assertEqual(
            self.get("/a%23b/")["Location"],
            "https://games.acclaimedmedia.org/a%23b/",
        )

    def test_a_post_is_redirected_too(self):
        response = self.client.post(
            "/game/1/toggle-played/", HTTP_HOST=ROOT_HOST, secure=True
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "https://games.acclaimedmedia.org/game/1/toggle-played/",
        )

    def test_a_filtered_rankings_link_moves_to_the_games_host(self):
        # The rankings were at `/`, so this is what every old filter link is
        response = self.get("/", data={"genres": "5", "highlight": "12"})
        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "https://games.acclaimedmedia.org/?genres=5&highlight=12",
        )

    def test_the_apex_keeps_its_own_routes(self):
        for path in ("/robots.txt", "/sitemap.xml", "/healthz/"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 200)


class PerSiteSeoTests(TestCase):
    def get(self, host, path):
        return self.client.get(path, HTTP_HOST=host, secure=True)

    def test_each_robots_txt_names_its_own_sitemap(self):
        for host in (ROOT_HOST, GAMES_HOST, MUSIC_HOST):
            with self.subTest(host=host):
                content = self.get(host, "/robots.txt").content.decode()
                self.assertIn(f"Sitemap: https://{host}/sitemap.xml", content)
                self.assertIn("User-agent: AhrefsBot\nDisallow: /", content)

    def test_the_apex_robots_txt_allows_the_landing_page(self):
        content = self.get(ROOT_HOST, "/robots.txt").content.decode()
        self.assertIn("User-agent: *\nAllow: /\nDisallow: /admin/\n", content)

    def test_each_sitemap_lists_its_own_host(self):
        page = FlatPage.objects.create(url="/about/", title="About", content="Hi")
        page.sites.add(Site.objects.get_current())
        root = self.get(ROOT_HOST, "/sitemap.xml").content.decode()
        self.assertIn("<loc>https://acclaimedmedia.org/</loc>", root)
        self.assertIn("<loc>https://acclaimedmedia.org/page/about/</loc>", root)
        games = self.get(GAMES_HOST, "/sitemap.xml").content.decode()
        self.assertIn("<loc>https://games.acclaimedmedia.org/</loc>", games)
        self.assertNotIn("/page/about/", games)
        music = self.get(MUSIC_HOST, "/sitemap.xml").content.decode()
        self.assertIn("<loc>https://music.acclaimedmedia.org/</loc>", music)

    def test_each_site_is_canonical_on_its_own_origin(self):
        self.assertContains(
            self.get(GAMES_HOST, "/developers/"),
            '<link rel="canonical" '
            'href="https://games.acclaimedmedia.org/developers/">',
        )
        self.assertContains(
            self.get(ROOT_HOST, "/"),
            '<link rel="canonical" href="https://acclaimedmedia.org/">',
        )


class LandingPageTests(TestCase):
    def setUp(self):
        clear_all_caches()
        publication = Publication.objects.create(name="Edge")
        List.objects.create(name="Top 100", publisher=publication, year=2000)
        for rank in range(1, 7):
            Game.objects.create(
                name=f"Game {rank}", slug=f"game-{rank}", rank=rank, igdb_id=rank
            )
        music_publication = MusicPublication.objects.create(name="Mojo")
        MusicList.objects.create(
            name="Best Albums", publisher=music_publication, year=2000, type="A"
        )
        Album.objects.create(name="Revolver", rank=1, year_released=1966)
        Album.objects.create(
            name="Hosted", rank=2, year_released=1967, cover_image_url="https://x/y.jpg"
        )
        Album.objects.create(name="Coverless", rank=3, year_released=1968)

    def get(self):
        return self.client.get("/", HTTP_HOST=ROOT_HOST, secure=True)

    def test_the_games_card_shows_the_top_games(self):
        response = self.get()
        self.assertContains(response, 'href="https://games.acclaimedmedia.org/"')
        card = response.context["games_card"]
        self.assertEqual((card["count"], card["list_count"]), (6, 1))
        self.assertEqual(
            [item["name"] for item in card["top"]][:2], ["Game 1", "Game 2"]
        )
        self.assertEqual(len(card["top"]), 5)

    def test_game_covers_are_sharp_on_a_retina_screen(self):
        game = Game.objects.get(name="Game 1")
        game.primary_igdb_game_data = IGDBGameData.objects.create(
            game=game, igdb_id=1, artwork_id="art.jpg", is_primary=True
        )
        game.save(update_fields=["primary_igdb_game_data"])

        image = "https://images.igdb.com/igdb/image/upload"
        self.assertContains(
            self.get(),
            f'src="{image}/t_cover_small/art.jpg" '
            f'srcset="{image}/t_cover_small/art.jpg 1x, '
            f'{image}/t_cover_small_2x/art.jpg 2x"',
        )

    def test_the_music_card_shows_the_top_albums(self):
        def stored_cover(album, size):
            return "/cover/a/b-250.jpg" if album.name == "Revolver" else None

        with mock.patch.object(Album, "_cover_art_url", stored_cover):
            response = self.get()
        self.assertContains(response, 'href="https://music.acclaimedmedia.org/"')
        card = response.context["music_card"]
        self.assertEqual((card["count"], card["list_count"]), (3, 1))
        # A stored cover is a path on the music host, made absolute here
        self.assertEqual(
            [item["image"] for item in card["top"]],
            [
                "https://music.acclaimedmedia.org/cover/a/b-250.jpg",
                "https://x/y.jpg",
                None,
            ],
        )

    def test_the_page_is_cached_for_anonymous_visitors(self):
        self.get()
        Game.objects.filter(rank=1).update(name="Renamed")
        self.assertNotContains(self.get(), "Renamed")

    def test_an_old_filter_link_redirects_even_with_the_page_cached(self):
        """The cache is read before the view's redirect."""
        self.get()
        response = self.client.get(
            "/", {"genres": "5"}, HTTP_HOST=ROOT_HOST, secure=True
        )
        self.assertEqual(response.status_code, 301)

    def test_every_old_filter_param_still_redirects(self):
        for param in ("q", "decade", "genres", "platforms", "sort", "page"):
            with self.subTest(param=param):
                response = self.client.get(
                    "/", {param: "1"}, HTTP_HOST=ROOT_HOST, secure=True
                )
                self.assertEqual(response.status_code, 301)

    def test_common_tracking_tags_stay_on_the_landing_page(self):
        for tag in ("utm_source", "fbclid", "igsh", "gbraid", "ref", "mc_cid"):
            with self.subTest(tag=tag):
                response = self.client.get(
                    "/", {tag: "x"}, HTTP_HOST=ROOT_HOST, secure=True
                )
                self.assertEqual(response.status_code, 200)

    def test_a_tracking_tag_shares_the_cache(self):
        """A campaign's unique tags would otherwise each render the page."""
        self.get()
        Game.objects.filter(rank=1).update(name="Renamed")
        response = self.client.get(
            "/", {"utm_source": "x"}, HTTP_HOST=ROOT_HOST, secure=True
        )
        self.assertNotContains(response, "Renamed")


class ContactPageCanonicalTests(TestCase):
    def test_every_host_names_the_apexs_copy(self):
        """One page, served on every site, as the flat pages are."""
        for name, path in (
            ("contact", "/contact/"),
            ("contact_thank_you", "/contact/thank-you/"),
        ):
            for site in (sites.ROOT, sites.GAMES, sites.MUSIC):
                with self.subTest(site=site, name=name):
                    response = get_on_site(self.client, site, name)
                    self.assertContains(
                        response,
                        '<link rel="canonical" '
                        f'href="https://acclaimedmedia.org{path}"',
                    )


class CookieSettingsTests(SimpleTestCase):
    def test_the_cookies_carry_names_of_their_own(self):
        # A host-only cookie of the old name, left on the apex, would be sent
        # beside the new domain-wide one
        self.assertEqual(settings.SESSION_COOKIE_NAME, "am_sessionid")
        self.assertEqual(settings.CSRF_COOKIE_NAME, "am_csrftoken")

    def test_production_shares_them_across_the_subdomains(self):
        from pathlib import Path

        source = (
            Path(settings.BASE_DIR) / "acclaimedgames" / "settings.py"
        ).read_text()
        self.assertRegex(
            source,
            r'SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = \(\s*"\." \+ '
            r"urlsplit\(CANONICAL_ORIGIN\)\.hostname",
        )

    def test_every_javascript_reader_of_the_csrf_cookie_uses_its_name(self):
        from pathlib import Path

        base = Path(settings.BASE_DIR)
        for name in (
            "core/static/core/js/media-list-controls.js",
            "core/static/core/js/base-renderer.js",
            "games/static/games/js/filter-component.js",
        ):
            with self.subTest(file=name):
                source = (base / name).read_text()
                self.assertIn(settings.CSRF_COOKIE_NAME, source)
                self.assertNotRegex(source, r"[^_]csrftoken=")


class NoPathAssumesTheOldLayoutTests(SimpleTestCase):
    """Music moved from /music/ to the root of its host."""

    def test_no_music_script_or_template_writes_a_music_prefixed_path(self):
        from pathlib import Path

        base = Path(settings.BASE_DIR)
        sources = [
            *base.glob("music/static/music/js/*.js"),
            *base.glob("core/static/core/js/*.js"),
            base / "games/templates/includes/_sidebar.html",
            base / "games/templates/includes/_nav_mobile.html",
        ]
        for path in sources:
            if path.name.endswith(".min.js"):
                continue
            with self.subTest(file=path.name):
                source = path.read_text()
                for literal in ("'/music/", '"/music/', "`/music/", "/api/music/"):
                    self.assertNotIn(literal, source)


class ThemeFollowsTheReaderTests(TestCase):
    def test_the_theme_is_kept_in_a_cookie_on_the_whole_domain(self):
        # localStorage is per origin, so a choice made on games would not
        # reach music without it
        html = self.client.get("/", HTTP_HOST=GAMES_HOST, secure=True).content.decode()
        self.assertIn("window.saveThemeCookie=function(t)", html)
        self.assertIn("';domain=.'+p.join('.')", html)
        # And it names no site: the same script runs on all three
        self.assertNotIn("(games|music)", html)
        self.assertIn("window.saveThemeCookie(t);document.documentElement", html)
