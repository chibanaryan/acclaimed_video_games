"""The music sitemap sections."""

from django.test import TestCase

from core.tests.utils import clear_all_caches
from music import models, sitemaps
from music.tests.site import setUpModule, tearDownModule  # noqa: F401


class MusicSitemapTests(TestCase):
    def setUp(self):
        clear_all_caches()
        self.artist = models.Artist.objects.create(name="Can", slug="can")
        models.Artist.objects.create(name="No Albums", slug="no-albums")
        self.album = models.Album.objects.create(
            name="Tago Mago", rank=1, artist_credit="Can", year_released=1971
        )
        self.album.artists.set([self.artist])

    def test_the_sections_list_the_public_pages(self):
        static = sitemaps.MusicStaticSitemap()
        self.assertEqual(
            [static.location(item) for item in static.items()],
            ["/", "/artists/", "/lists/", "/browse/"],
        )
        albums = sitemaps.AlbumSitemap()
        self.assertEqual(list(albums.items()), [self.album])
        self.assertEqual(albums.lastmod(self.album), self.album.modified)
        self.assertEqual(list(sitemaps.ArtistSitemap().items()), [self.artist])

    def test_the_landing_section_follows_the_landing_service(self):
        rock = models.MusicGenre.objects.create(name="Rock")
        for index in range(10):
            album = models.Album.objects.create(
                name=f"Rock {index}", rank=10 + index, year_released=1970 + index
            )
            album.genres.set([rock])
        landing = sitemaps.MusicLandingPageSitemap()
        self.assertEqual(
            [landing.location(item) for item in landing.items()],
            ["/genres/rock/", "/1970s/"],
        )
