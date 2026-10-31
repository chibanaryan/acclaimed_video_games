"""A link into a `?highlight=` URL carries `rel="nofollow"`.

robots.txt disallows `/*?*highlight=`: each is a rankings page filtered to one
platform, genre, series or year and scrolled to one item, so game x platform
alone is thousands of URLs that duplicate the landing pages. Meta's crawler
walked them anyway from the detail pages' badges, and every hit skipped the
page cache (Sentry ACCLAIMED-VIDEO-GAMES-9E). The nofollow says so at the link
too. Checked in source, templates and the renderers' HTML strings alike,
because a client-rendered row is as followable as a server-rendered one.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from games.models import Game, Platform, Series, WikipediaGenre
from music.models import Album, MusicGenre

APPS = ["games", "books", "music", "core"]

# An opening <a ...> tag, across lines, whose attributes name highlight=
HIGHLIGHT_LINK = re.compile(r"<a\s[^>]*highlight=[^>]*>")


def _sources():
    for app in APPS:
        root = Path(settings.BASE_DIR) / app
        yield from root.rglob("*.html")
        yield from (
            path for path in root.rglob("*.js") if not path.name.endswith(".min.js")
        )


class HighlightLinksAreNofollowTests(SimpleTestCase):
    def test_every_highlight_link_is_nofollow(self):
        found = []
        missing = []
        for path in _sources():
            for tag in HIGHLIGHT_LINK.findall(path.read_text(encoding="utf-8")):
                found.append(tag)
                if 'rel="nofollow"' not in tag:
                    missing.append(f"{path.relative_to(settings.BASE_DIR)}: {tag}")
        # The pattern still matches something, or the test checks nothing
        self.assertGreaterEqual(len(found), 14)
        self.assertEqual(missing, [])

    def test_the_robots_rule_it_mirrors_is_still_there(self):
        response = self.client.get("/robots.txt")
        self.assertContains(response, "Disallow: /*?*highlight=")


class RenderedHighlightLinksAreNofollowTests(TestCase):
    """The source scan cannot see a URL a template tag builds, so render too.

    The detail pages' rank links come from `game_rank_url`, `album_rank_url`
    and `album_year_url`, and were the ones the first pass missed.
    """

    def _highlight_links(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return HIGHLIGHT_LINK.findall(response.content.decode())

    def _assert_all_nofollow(self, links, at_least):
        self.assertGreaterEqual(len(links), at_least)
        self.assertEqual([tag for tag in links if 'rel="nofollow"' not in tag], [])

    def test_game_detail(self):
        game = Game.objects.create(
            name="Nofollow Game",
            slug="nofollow-game",
            rank=1,
            decade_rank=1,
            year_rank=1,
            year_of_release=1995,
        )
        game.platforms.add(Platform.objects.create(name="PC", code="PC"))
        game.wikipedia_genres.add(WikipediaGenre.objects.create(name="Nofollow Genre"))
        # A series badge shows only for a series of two games or more
        series = Series.objects.create(name="Nofollow Series", igdb_id=990001)
        game.series.add(series)
        Game.objects.create(name="Sequel", slug="sequel", rank=2).series.add(series)
        links = self._highlight_links(
            reverse("game-detail", kwargs={"slug": game.slug})
        )
        # Three rank links and a platform, genre and series badge
        self._assert_all_nofollow(links, 6)

    @override_settings(ROOT_URLCONF=settings.SITE_URLCONFS["music"])
    def test_album_detail(self):
        album = Album.objects.create(
            name="Nofollow Album",
            rank=1,
            decade_rank=1,
            year_rank=1,
            year_released=1971,
        )
        album.genres.add(MusicGenre.objects.create(name="Nofollow Rock"))
        links = self._highlight_links(album.get_absolute_url())
        # Three rank links and a genre badge
        self._assert_all_nofollow(links, 4)
