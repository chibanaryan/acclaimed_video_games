"""The other sites lead to music: the site menu, both navs, the landing page
and the sitemap.

Music is its own host (core/sites.py), so these requests name the real hosts,
over HTTPS, and a link to music is an absolute one.
"""

from unittest import mock

from django.conf import settings
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import resolve, reverse

from core import sites
from core.models import User
from core.tests.utils import clear_all_caches
from music import config, models
from music.tests.site import music_site

GAMES_HOST = "games.acclaimedmedia.org"
MUSIC_HOST = "music.acclaimedmedia.org"
ROOT_HOST = "acclaimedmedia.org"
MUSIC_HOME = 'href="https://music.acclaimedmedia.org/"'
GAMES_HOME = 'href="https://games.acclaimedmedia.org/"'

# The sidebar's own links, as rendered once template indentation is stripped.
SIDEBAR_RANKINGS_LINK = (
    '<span class="mdi mdi-medal text-xl" aria-hidden="true"></span>\nRankings'
)
SIDEBAR_BACK_TO_GAMES = "Back to Games"


def site_menu(response_or_html):
    """The sidebar's site menu, the top of every page's sidebar."""
    html = getattr(response_or_html, "content", response_or_html)
    if isinstance(html, bytes):
        html = html.decode()
    start = html.index('<details class="site-menu')
    return html[start : html.index("</details>", start)]


class HostClientMixin:
    """GETs on a named site, by URL name in that site's URLconf."""

    def get_on(self, site, viewname, **kwargs):
        host = {sites.GAMES: GAMES_HOST, sites.MUSIC: MUSIC_HOST}.get(site, ROOT_HOST)
        path = sites.site_reverse(site, viewname, kwargs=kwargs or None)
        return self.client.get(path, HTTP_HOST=host, secure=True)

    def get_path_on(self, host, path):
        return self.client.get(path, HTTP_HOST=host, secure=True)


class EntryPointTests(HostClientMixin, TestCase):
    """The ways into music, and back out of it."""

    def setUp(self):
        clear_all_caches()
        self.album = models.Album.objects.create(
            name="Pet Sounds",
            rank=1,
            artist_credit="The Beach Boys",
            year_released=1966,
        )

    def test_the_games_pages_link_to_music_for_anonymous_visitors(self):
        for viewname in ("home", "developers-list", "list-list"):
            with self.subTest(viewname=viewname):
                self.assertContains(self.get_on(sites.GAMES, viewname), MUSIC_HOME)

    def test_the_landing_page_leads_to_both_sites(self):
        response = self.get_on(sites.ROOT, "landing")
        self.assertContains(response, MUSIC_HOME)
        self.assertContains(response, GAMES_HOME)

    def test_the_site_menu_offers_music_without_books(self):
        rendered = render_to_string(
            "core/includes/_site_menu.html",
            {"BOOKS_ENABLED": False, "media_type": "music"},
        )
        self.assertIn(MUSIC_HOME, rendered)
        self.assertIn(GAMES_HOME, rendered)
        self.assertNotIn("/books/", rendered)

    def test_the_mobile_nav_has_a_music_entry(self):
        response = self.get_on(sites.GAMES, "home")
        self.assertContains(response, 'data-nav-item="music"')

    def test_the_games_sidebar_shows_the_site_menu_and_its_rankings_link(self):
        # The menu chooses the site and the links the page
        response = self.get_on(sites.GAMES, "developers-list")
        self.assertContains(response, SIDEBAR_RANKINGS_LINK)
        self.assertContains(response, '<details class="site-menu')

    def test_music_pages_lead_back_through_the_site_menu(self):
        response = self.get_on(sites.MUSIC, "music:home")
        self.assertNotContains(response, SIDEBAR_BACK_TO_GAMES)
        menu = site_menu(response)
        self.assertIn(GAMES_HOME, menu)
        self.assertIn('class="active" aria-current="true">', menu)
        self.assertIn('href="https://acclaimedmedia.org/"', menu)

    def test_the_rankings_page_is_badged_beta(self):
        response = self.get_on(sites.MUSIC, "music:home")
        self.assertContains(response, "Beta</span>")

    def test_the_music_sitemap_lists_the_section_on_its_own_host(self):
        content = self.get_path_on(MUSIC_HOST, "/sitemap.xml").content.decode()
        self.assertIn("<loc>https://music.acclaimedmedia.org/</loc>", content)
        self.assertIn(
            f"https://music.acclaimedmedia.org{self.album.get_absolute_url()}</loc>",
            content,
        )

    def test_robots_txt_keeps_crawlers_off_the_import_and_csv_pages(self):
        content = self.get_path_on(MUSIC_HOST, "/robots.txt").content.decode()
        self.assertIn("Disallow: /import/", content)
        self.assertIn("Disallow: /download/", content)
        self.assertIn("Sitemap: https://music.acclaimedmedia.org/sitemap.xml", content)


@music_site
class NoImportLinkTests(TestCase):
    """The import page is reached by typing its URL, not from the chrome."""

    def test_staff_see_no_import_link_anywhere(self):
        User.objects.create_user(username="navstaff", password="navpass", is_staff=True)
        self.client.login(username="navstaff", password="navpass")
        import_url = f'href="{reverse("music:import")}"'
        for url in [
            reverse("music:home"),
            reverse("music:list-list"),
            reverse("music:artist-list"),
        ]:
            with self.subTest(url=url):
                self.assertNotContains(self.client.get(url), import_url)


@music_site
class SavedFilterRouteTests(TestCase):
    def test_a_signed_in_reader_reaches_the_saved_filter_api(self):
        User.objects.create_user(username="sfplain", password="sfpass")
        self.client.login(username="sfplain", password="sfpass")
        response = self.client.get(reverse("music-api:saved-filter-list"))
        self.assertEqual(response.status_code, 200)

    def test_the_route_sits_before_the_album_slug_catch_all(self):
        # `saved-filters/` would otherwise resolve as an album slug, which
        # would make a POST to it a 405 from the detail view instead.
        match = resolve("/api/saved-filters/", urlconf=settings.SITE_URLCONFS["music"])
        self.assertEqual(match.url_name, "saved-filter-list")


BETA_BADGE = ">Beta</span>"
BETA_NOTICE = "The music site is in beta."


class BetaIsClearThroughoutTests(HostClientMixin, TestCase):
    """Music is a beta, and every way into it says so."""

    def setUp(self):
        clear_all_caches()
        self.album = models.Album.objects.create(
            name="Pet Sounds",
            rank=1,
            artist_credit="The Beach Boys",
            year_released=1966,
        )
        self.artist = models.Artist.objects.create(
            name="The Beach Boys", slug="the-beach-boys", source_id=1
        )
        self.album.artists.set([self.artist])

    def music_pages(self):
        return {
            "rankings": self.get_on(sites.MUSIC, "music:home"),
            "album": self.get_path_on(MUSIC_HOST, self.album.get_absolute_url()),
            "artists": self.get_on(sites.MUSIC, "music:artist-list"),
            "artist": self.get_path_on(MUSIC_HOST, self.artist.get_absolute_url()),
            "lists": self.get_on(sites.MUSIC, "music:list-list"),
            "browse": self.get_on(sites.MUSIC, "music:browse"),
            "404": self.get_path_on(MUSIC_HOST, "/no-such-album/"),
        }

    def test_every_music_page_carries_the_notice_and_a_badge(self):
        for name, response in self.music_pages().items():
            with self.subTest(page=name):
                status = 404 if name == "404" else 200
                self.assertContains(response, BETA_NOTICE, status_code=status)
                if name != "404":
                    self.assertContains(response, BETA_BADGE)

    def test_the_notice_asks_for_feedback_through_the_contact_form(self):
        self.assertContains(
            self.get_on(sites.MUSIC, "music:home"),
            'data-message="Feedback on the music beta: ">Send feedback</button>',
        )

    def test_the_games_site_carries_no_notice(self):
        self.assertNotContains(self.get_on(sites.GAMES, "home"), BETA_NOTICE)

    def test_every_link_into_music_is_marked_beta(self):
        games = self.get_on(sites.GAMES, "home").content.decode()
        # The sidebar's site menu
        menu = site_menu(games)
        self.assertIn(BETA_BADGE, menu[menu.index(MUSIC_HOME) :])
        # The games mobile bar's Music icon, and its overflow-menu label
        self.assertIn('data-menu-label="Music (beta)"', games)
        self.assertIn('aria-label="Music (beta)"', games)
        # The landing page's Music card
        landing = self.get_on(sites.ROOT, "landing").content.decode()
        card = landing[landing.index('<span class="mdi mdi-album') :]
        self.assertIn(BETA_BADGE, card[: card.index("</h2>")])
        self.assertIn("<strong>New, and in beta:</strong>", card)

    def test_the_music_site_names_itself_beta_in_the_site_menu(self):
        menu = site_menu(self.get_on(sites.MUSIC, "music:home"))
        summary = menu[: menu.index("</summary>")]
        self.assertIn("Music", summary)
        self.assertIn(BETA_BADGE, summary)

    def test_turning_the_beta_off_removes_every_marker(self):
        with mock.patch.object(config, "MUSIC_BETA", False):
            for name, response in self.music_pages().items():
                with self.subTest(page=name):
                    status = 404 if name == "404" else 200
                    self.assertNotContains(response, BETA_NOTICE, status_code=status)
                    self.assertNotContains(response, BETA_BADGE, status_code=status)
            clear_all_caches()
            games = self.get_on(sites.GAMES, "home")
            self.assertNotContains(games, BETA_BADGE)
            self.assertContains(games, 'data-menu-label="Music"')
