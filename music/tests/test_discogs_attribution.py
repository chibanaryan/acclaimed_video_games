"""The notices Discogs' API terms require wherever its data is shown.

Two, from the "Discogs Intellectual Property" section of the terms (last
updated 2025-05-27):

- the non-affiliation notice, verbatim, "prominently" on any public-facing
  use - rendered at the foot of every music page;
- "Data provided by Discogs" directly beside the data, linking to the
  discogs.com page that holds it, with nothing such as ``nofollow`` that
  withholds ranking credit from the link.

Every album's genres are built on its Discogs styles, so the credit sits
beside the genres on album detail (linked to the master) and once beside the
genre filter or album list on the list pages.
"""

import re

from django.test import TestCase
from django.urls import reverse

from music import models
from music.tests.test_views import ClearsCachesMixin
from music.tests.site import setUpModule, tearDownModule  # noqa: F401
from core import sites
from core.tests.utils import get_on_site

NOTICE = (
    "This application uses Discogs’ API but is not affiliated with, sponsored "
    "or endorsed by Discogs. ‘Discogs’ is a trademark of Zink Media, LLC."
)
DATA_CREDIT_LINK = re.compile(r'<p class="data-credit[^"]*"><a ([^>]*)>([^<]*)</a></p>')


def _credits(response):
    """Every data-credit link on the page, as ``(attributes, text)``."""
    return DATA_CREDIT_LINK.findall(response.content.decode())


class DiscogsAttributionTests(ClearsCachesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.rock = models.MusicGenre.objects.create(name="Rock")
        self.artist = models.Artist.objects.create(name="Wire", slug="wire")
        self.album = models.Album.objects.create(
            name="Pink Flag",
            rank=1,
            artist_credit="Wire",
            year_released=1977,
            discogs_master_id=31876,
        )
        self.album.genres.set([self.rock])
        self.album.artists.set([self.artist])

    def test_every_music_page_carries_the_notice(self):
        for url in (
            reverse("music:home"),
            reverse("music:artist-list"),
            reverse("music:list-list"),
            reverse("music:browse"),
            self.album.get_absolute_url(),
            reverse("music:artist-detail", kwargs={"slug": "wire"}),
        ):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), NOTICE)

    def test_games_pages_do_not(self):
        self.assertNotContains(get_on_site(self.client, sites.GAMES, "home"), NOTICE)

    def test_album_detail_credits_discogs_beside_the_genres(self):
        response = self.client.get(self.album.get_absolute_url())
        ((attributes, text),) = _credits(response)
        self.assertEqual(text, "Data provided by Discogs")
        self.assertIn('href="https://www.discogs.com/master/31876"', attributes)
        self.assertNotIn("nofollow", attributes)

    def test_an_album_with_no_master_carries_no_credit(self):
        self.album.discogs_master_id = None
        self.album.save()
        self.assertEqual(_credits(self.client.get(self.album.get_absolute_url())), [])

    def test_the_rankings_page_credits_discogs_beside_the_genre_filter(self):
        # Once in the sidebar tree and once in the mobile sheet's.
        credits = _credits(self.client.get(reverse("music:home")))
        self.assertEqual(len(credits), 2)
        for attributes, text in credits:
            self.assertEqual(text, "Genres use data provided by Discogs")
            self.assertIn('href="https://www.discogs.com/"', attributes)
            self.assertNotIn("nofollow", attributes)

    def test_the_artist_page_credits_discogs_above_its_albums(self):
        response = self.client.get(
            reverse("music:artist-detail", kwargs={"slug": "wire"})
        )
        self.assertEqual(
            [text for _, text in _credits(response)],
            ["Genres use data provided by Discogs"],
        )

    def test_the_games_genre_filter_carries_no_credit(self):
        self.assertEqual(_credits(get_on_site(self.client, sites.GAMES, "home")), [])
