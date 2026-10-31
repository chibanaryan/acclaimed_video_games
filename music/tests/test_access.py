"""Who can reach the music section: reads are public, writes want a login,
and the import page is for staff.
"""

import json
from unittest import mock

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import User
from core.tests.utils import clear_all_caches
from core.throttling import ClientIPAnonRateThrottle
from music import config, models
from music.tests.site import setUpModule, tearDownModule  # noqa: F401


class AccessFixtureMixin:
    def setUp(self):
        super().setUp()
        clear_all_caches()
        self.artist = models.Artist.objects.create(name="The Who", slug="the-who")
        self.rock = models.MusicGenre.objects.create(name="Rock")
        self.albums = []
        for index in range(12):
            album = models.Album.objects.create(
                name=f"Album {index}",
                rank=index + 1,
                artist_credit="The Who",
                year_released=1970 + index % 10,
                wikidata_id=f"Q{9000 + index}",
            )
            album.artists.set([self.artist])
            album.genres.set([self.rock])
            self.albums.append(album)
        self.album = self.albums[0]
        self.plain = User.objects.create_user(username="plain", password="plainpass")
        self.staff = User.objects.create_user(
            username="staff", password="staffpass", is_staff=True
        )

    def read_urls(self):
        return [
            reverse("music:home"),
            reverse("music:search") + "?q=album",
            reverse("music:download"),
            reverse("music:list-list"),
            reverse("music:artist-list"),
            reverse("music:artist-detail", kwargs={"slug": self.artist.slug}),
            reverse("music:browse"),
            reverse("music:by-genre", kwargs={"slug": self.rock.slug}),
            reverse("music:by-decade", kwargs={"decade": 1970}),
            self.album.get_absolute_url(),
            reverse("music-api:album-list"),
            reverse("music-api:album-all-data"),
            reverse("music-api:unified-search") + "?q=album",
            reverse("music-api:meta"),
            reverse("music-api:genre-list"),
            reverse("music-api:album-detail", kwargs={"slug": self.album.slug}),
            reverse("music-api:album-search") + "?q=album",
            reverse("music-api:artist-list"),
            reverse("music-api:artist-detail", kwargs={"slug": self.artist.slug}),
            reverse("music-api:musiclist-list"),
        ]


class PublicSectionTests(AccessFixtureMixin, TestCase):
    """Reads are public, writes want a login."""

    def test_every_read_url_renders_for_an_anonymous_visitor(self):
        for url in self.read_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_every_read_url_renders_for_a_signed_in_reader(self):
        self.client.login(username="plain", password="plainpass")
        for url in self.read_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_the_import_page_stays_staff_only(self):
        url = reverse("music:import")
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.login(username="plain", password="plainpass")
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.login(username="staff", password="staffpass")
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_a_signed_out_toggle_redirects_to_login_as_games_does(self):
        url = reverse("music:toggle-listened", args=[self.album.pk])
        response = self.client.post(f"{url}?status=listened")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/"))
        self.assertFalse(models.ListenedAlbum.objects.exists())

    def test_a_signed_in_reader_can_track_an_album(self):
        self.client.login(username="plain", password="plainpass")
        url = reverse("music:toggle-listened", args=[self.album.pk])
        response = self.client.post(f"{url}?status=listened")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            models.ListenedAlbum.objects.filter(
                user=self.plain, album=self.album
            ).exists()
        )

    def test_a_signed_out_caller_gets_403_from_saved_filters(self):
        url = reverse("music-api:saved-filter-list")
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_a_signed_in_reader_can_save_a_filter_with_a_token(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="plain", password="plainpass")
        client.get(reverse("music:home"))
        response = client.post(
            reverse("music-api:saved-filter-list"),
            json.dumps({"name": "Mine", "filters": {"genres": ["1"]}}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies[settings.CSRF_COOKIE_NAME].value,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            models.SavedAlbumFilterSet.objects.get().user_id, self.plain.pk
        )

    def test_a_failed_csrf_check_is_a_403(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("music:home"))
        self.assertEqual(response.status_code, 403)

    def test_an_anonymous_rankings_page_has_no_tracking_state(self):
        response = self.client.get(reverse("music:home"))
        self.assertContains(response, "window.isAuthenticated = false;")

    def test_music_beta_decides_the_badge(self):
        response = self.client.get(reverse("music:home"))
        self.assertContains(response, "Beta</span>")
        with mock.patch.object(config, "MUSIC_BETA", False):
            response = self.client.get(reverse("music:home"))
        self.assertNotContains(response, "Beta</span>")


LOCMEM = {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}


@override_settings(
    CACHES={
        alias: dict(LOCMEM, LOCATION=alias)
        for alias in ("default", "local", "ratelimit")
    }
)
class ReadThrottleTests(AccessFixtureMixin, TestCase):
    """A session login keeps a reader out of the anonymous limit.

    ``AnonRateThrottle`` skips an authenticated request, and a read looks at
    the user for nothing else, so this is the only thing that notices
    ``SessionAuthentication`` going. ``ratelimit`` is a DummyCache under test,
    which never counts, hence the override.
    """

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(
            ClientIPAnonRateThrottle, "rate", "1/minute", create=True
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.url = reverse("music-api:meta")

    def test_an_anonymous_reader_is_throttled(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(self.url).status_code, 429)

    def test_a_signed_in_reader_is_not(self):
        self.client.login(username="plain", password="plainpass")
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(self.url).status_code, 200)
