"""Tests for the album listen-status toggle.

The endpoint answers with the re-rendered button, which HTMX swaps in place,
so these tests check both the rows it writes and the markup it sends back.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import User
from music import config, models
from music.tests.site import setUpModule, tearDownModule  # noqa: F401

# The button's own image, not the menu's smaller copy of another state's:
# the row-size classes come only on the button.
BUTTON_IMAGE = (
    r'music/images/{}[^"]*\.svg" alt="" width="40" height="40" class="w-6 h-6 '
)


class ToggleListenedAlbumViewTests(TestCase):
    """Setting a status, and the markup that comes back."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="reader", password="pw")
        self.client.login(username="reader", password="pw")
        self.album = models.Album.objects.create(
            name="Doolittle", rank=1, slug="doolittle", wikidata_id="Q123"
        )
        self.url = reverse("music:toggle-listened", args=[self.album.pk])

    def _post(self, status, **params):
        query = "&".join([f"status={status}"] + [f"{k}={v}" for k, v in params.items()])
        return self.client.post(f"{self.url}?{query}")

    def _listened(self):
        return models.ListenedAlbum.objects.filter(
            user=self.user, album=self.album
        ).exists()

    def _wanted(self):
        return models.WantToListenAlbum.objects.filter(
            user=self.user, album=self.album
        ).exists()

    def test_setting_listened_creates_the_row(self):
        response = self._post("listened")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._listened())
        self.assertFalse(self._wanted())

    def test_setting_want_creates_the_row(self):
        response = self._post("want")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._wanted())
        self.assertFalse(self._listened())

    def test_setting_listened_clears_a_want(self):
        # The two are mutually exclusive, and nothing in the schema spans
        # both tables, so this view is where that holds.
        self._post("want")
        self._post("listened")
        self.assertTrue(self._listened())
        self.assertFalse(self._wanted())

    def test_setting_want_clears_a_listen(self):
        self._post("listened")
        self._post("want")
        self.assertTrue(self._wanted())
        self.assertFalse(self._listened())

    def test_setting_none_clears_both(self):
        self._post("listened")
        self._post("none")
        self.assertFalse(self._listened())
        self.assertFalse(self._wanted())

    def test_setting_none_on_an_untracked_album_is_harmless(self):
        response = self._post("none")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._listened())

    def test_posting_the_same_status_twice_is_idempotent(self):
        # A double-click. `update_or_create` is what keeps the second post
        # from colliding with the unique_together the first created.
        self._post("listened")
        response = self._post("listened")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(models.ListenedAlbum.objects.count(), 1)

    def test_a_post_re_adopts_a_row_orphaned_by_a_reimport(self):
        # The row survived an import with its album NULL. Toggling should
        # reconnect it rather than fail on the unique id, which is what a
        # plain `create` would do.
        models.ListenedAlbum.objects.create(
            user=self.user, album=None, wikidata_id="Q123"
        )
        response = self._post("listened")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(models.ListenedAlbum.objects.count(), 1)
        row = models.ListenedAlbum.objects.get()
        self.assertEqual(row.album, self.album)

    def test_an_unknown_status_is_rejected(self):
        response = self.client.post(f"{self.url}?status=sideways")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self._listened())

    def test_a_missing_status_is_rejected(self):
        # There is no cycle form, unlike games': the dropdown always names a
        # status, so a bare post is a mistake rather than a shortcut.
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_an_album_with_no_wikidata_id_is_rejected(self):
        # The tracking row is keyed on that id, so there is nothing to store.
        album = models.Album.objects.create(
            name="Unknown", rank=2, slug="unknown", wikidata_id=None
        )
        url = reverse("music:toggle-listened", args=[album.pk])
        response = self.client.post(f"{url}?status=listened")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.ListenedAlbum.objects.count(), 0)

    def test_an_unknown_album_is_a_404(self):
        url = reverse("music:toggle-listened", args=[999999])
        self.assertEqual(self.client.post(f"{url}?status=listened").status_code, 404)

    def test_the_response_is_the_rerendered_button(self):
        response = self._post("listened")
        html = response.content.decode()
        self.assertIn('data-status="listened"', html)
        self.assertIn(f'data-item-id="{self.album.pk}"', html)
        self.assertIn('data-tracking-scope="album"', html)
        self.assertRegex(html, BUTTON_IMAGE.format("gold-record"))
        self.assertIn("You have heard this album!", html)

    def test_the_menu_buttons_inherit_the_csrf_header_from_body(self):
        # base.html's <body hx-headers> already carries the token; three
        # copies per button were repeated for every row on the page.
        html = self._post("listened").content.decode()
        self.assertIn("hx-post=", html)
        self.assertNotIn("hx-headers", html)

    def test_the_untracked_response_shows_the_outline_record(self):
        # Untracked and heard differ in shape, not only in colour.
        html = self._post("none").content.decode()
        self.assertIn("mdi-record-circle-outline", html)
        self.assertIn('data-status="none"', html)

    def test_the_want_response_shows_the_record_with_a_plus(self):
        # The states are one record throughout; the backlog is the empty
        # record with a plus, as games' is the star with one. A solid orange
        # disc read as plain beside games' star-plus-outline.
        html = self._post("want").content.decode()
        self.assertIn("mdi mdi-record-plus text-2xl text-warning", html)
        self.assertIn('data-status="want"', html)

    def test_the_response_animates_the_new_state(self):
        self.assertIn("star-appear", self._post("listened").content.decode())

    def test_the_response_offers_the_states_it_is_not_in(self):
        html = self._post("listened").content.decode()
        self.assertIn("status=want", html)
        self.assertIn("status=none", html)
        self.assertNotIn("status=listened", html)

    def test_the_response_does_not_push_a_url(self):
        # A button swap is not navigation; without this the address bar
        # would end up pointing at the toggle endpoint.
        self.assertEqual(self._post("listened")["HX-Push-Url"], "false")

    def test_the_large_size_is_echoed_back(self):
        # The detail page's button has to stay large across a swap, so the
        # size rides along in the query string.
        html = self._post("listened", size="large").content.decode()
        self.assertIn("h-12 w-12", html)
        self.assertIn("top-full", html)
        self.assertIn("size=large", html)

    def test_a_row_sized_button_opens_its_menu_upward(self):
        html = self._post("listened").content.decode()
        self.assertIn("bottom-full", html)
        self.assertNotIn("top-full", html)

    def test_the_response_ships_no_inline_script(self):
        # The sync is one delegated listener, not a script per swap.
        self.assertNotIn("<script", self._post("listened").content.decode())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_the_toggle_drops_the_cached_id_sets(self):
        # The invalidation is deferred to transaction.on_commit, so that a
        # rolled-back write cannot clear a cache it did not change. Nothing
        # commits inside a TestCase, hence captureOnCommitCallbacks.
        from music import views

        views._get_listened_album_ids(self.user)
        views._get_want_to_listen_album_ids(self.user)
        listened_key = config.CACHE_KEY_LISTENED_ALBUMS.format(user_id=self.user.id)
        wanted_key = config.CACHE_KEY_WANT_TO_LISTEN_ALBUMS.format(user_id=self.user.id)
        self.assertIsNotNone(cache.get(listened_key))
        self.assertIsNotNone(cache.get(wanted_key))

        with self.captureOnCommitCallbacks(execute=True):
            self._post("listened")

        # Both, because a status change moves an album between them.
        self.assertIsNone(cache.get(listened_key))
        self.assertIsNone(cache.get(wanted_key))

    def test_the_invalidation_waits_for_the_commit(self):
        # Spelled out because it is easy to "simplify" into an inline call,
        # which games does - it has no transaction to be wrong about.
        from music import views

        views._get_listened_album_ids(self.user)
        key = config.CACHE_KEY_LISTENED_ALBUMS.format(user_id=self.user.id)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self._post("listened")
        self.assertTrue(callbacks)
        self.assertIsNotNone(cache.get(key))

    def test_one_users_toggle_does_not_touch_another(self):
        other = User.objects.create_user(username="other", password="pw")
        self._post("listened")
        self.assertFalse(models.ListenedAlbum.objects.filter(user=other).exists())

    # Have: a ListenedAlbum row with owned set, exclusive of the other states

    def _owned(self):
        return models.ListenedAlbum.objects.filter(
            user=self.user, album=self.album, owned=True
        ).exists()

    def test_setting_own_creates_an_owned_row(self):
        response = self._post("own")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._owned())
        self.assertFalse(self._wanted())

    def test_setting_own_clears_a_want(self):
        self._post("want")
        self._post("own")
        self.assertTrue(self._owned())
        self.assertFalse(self._wanted())

    def test_moving_between_have_and_heard_keeps_the_one_row(self):
        # The same row with the flag flipped, so its `created` - when the
        # user first marked the album - survives the move.
        self._post("listened")
        created = models.ListenedAlbum.objects.get().created
        self._post("own")
        row = models.ListenedAlbum.objects.get()
        self.assertTrue(row.owned)
        self.assertEqual(row.created, created)
        self._post("listened")
        self.assertFalse(models.ListenedAlbum.objects.get().owned)

    def test_setting_none_clears_an_owned_row(self):
        self._post("own")
        self._post("none")
        self.assertFalse(models.ListenedAlbum.objects.exists())

    def test_the_owned_response_shows_the_record_in_its_sleeve(self):
        html = self._post("own").content.decode()
        self.assertIn('data-status="own"', html)
        self.assertRegex(html, BUTTON_IMAGE.format("record-sleeve"))
        self.assertIn("You have this album!", html)
        self.assertIn('aria-label="Have - click to change"', html)
        self.assertIn("star-appear", html)

    def test_the_owned_response_offers_the_other_three_states(self):
        html = self._post("own").content.decode()
        self.assertNotIn("status=own", html)
        self.assertIn("status=listened", html)
        self.assertIn("status=want", html)
        self.assertIn("status=none", html)

    def test_an_untracked_menu_offers_have_first(self):
        html = self._post("none").content.decode()
        self.assertLess(html.index("status=own"), html.index("status=listened"))

    def test_the_wrapper_carries_its_toggle_url_for_quick_mark(self):
        html = self._post("none").content.decode()
        self.assertIn(f'data-toggle-url="{self.url}"', html)

    def test_the_toggle_drops_the_cached_owned_set(self):
        from music import views

        views._get_owned_album_ids(self.user)
        key = config.CACHE_KEY_OWNED_ALBUMS.format(user_id=self.user.id)
        self.assertIsNotNone(cache.get(key))
        with self.captureOnCommitCallbacks(execute=True):
            self._post("own")
        self.assertIsNone(cache.get(key))

    def test_the_owned_and_heard_id_sets_are_disjoint(self):
        from music import views

        heard = models.Album.objects.create(
            name="Surfer Rosa", rank=2, slug="surfer-rosa", wikidata_id="Q456"
        )
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.album, wikidata_id="Q123", owned=True
        )
        models.ListenedAlbum.objects.create(
            user=self.user, album=heard, wikidata_id="Q456"
        )
        self.assertEqual(views._get_owned_album_ids(self.user), [self.album.pk])
        self.assertEqual(views._get_listened_album_ids(self.user), [heard.pk])

    def test_the_row_names_what_it_records(self):
        row = models.ListenedAlbum.objects.create(
            user=self.user, album=self.album, wikidata_id="Q123", owned=True
        )
        self.assertEqual(str(row), "reader has Doolittle")
        row.owned = False
        self.assertEqual(str(row), "reader listened to Doolittle")


class FilterSuppressorSourceTests(SimpleTestCase):
    """The client-side filter must not swallow the toggle's POST.

    `album-client-filtering.js` cancels HTMX requests once the engine can
    answer them locally, and it does so with listeners on the filter form
    and on `#album-results-container`. Every row lives inside that
    container, so a row's listen-status POST bubbles through the same
    listener - and cancelling it made the button do nothing at all, but only
    after the bundle had finished loading, which is why it looked
    intermittent. Only GETs may be suppressed.
    """

    def setUp(self):
        self.source = (
            Path(settings.BASE_DIR) / "music/static/music/js/album-client-filtering.js"
        ).read_text()

    def test_the_suppressor_only_cancels_gets(self):
        suppressor = re.search(
            r"const suppressHtmx = event => \{(.*?)\n    \};", self.source, re.S
        )
        self.assertIsNotNone(suppressor, "suppressHtmx is gone or reshaped")
        body = suppressor.group(1)
        self.assertIn("verb", body)
        self.assertIn("'get'", body)
        self.assertIn("return", body)

    def test_the_suppressor_still_guards_on_readiness(self):
        # Without the bundle there is nothing to answer locally, so the
        # server must keep filtering - this is the progressive-enhancement
        # half of the same function.
        suppressor = re.search(
            r"const suppressHtmx = event => \{(.*?)\n    \};", self.source, re.S
        )
        self.assertIn("ready", suppressor.group(1))

    def test_the_toggle_is_a_post(self):
        # The premise of the test above: if the toggle were ever made a GET
        # it would start being suppressed again.
        button = (
            Path(settings.BASE_DIR)
            / "core/templates/core/includes/_tracking_button.html"
        ).read_text()
        self.assertIn("hx-post=", button)
        self.assertNotIn("hx-get=", button)


class TrackingMarkImagesTests(SimpleTestCase):
    """Have and Heard are illustrations, named by static path in four places."""

    IMAGES = ("music/images/gold-record.svg", "music/images/record-sleeve.svg")

    def test_every_named_image_exists(self):
        named = {
            option["image"]
            for option in (*config.LISTEN_STATUS_OPTIONS, *config.QUICK_MARK_OPTIONS)
            if "image" in option
        }
        self.assertEqual(named, set(self.IMAGES))
        for path in self.IMAGES:
            with self.subTest(path=path):
                self.assertIsNotNone(finders.find(path))

    def test_the_clone_template_puts_each_image_in_its_slot(self):
        # The renderer only shows and hides slots, so the illustration has to
        # be in the clone already, with the same row-size classes.
        html = render_to_string("music/includes/_listen_button_template.html")
        for slot, image in (
            ("owned-icon", "record-sleeve"),
            ("tracked-icon", "gold-record"),
        ):
            with self.subTest(slot=slot):
                self.assertRegex(
                    html,
                    rf'data-slot="{slot}">\s*<img src="[^"]*{image}[^"]*\.svg" alt=""'
                    r' width="24" height="24" class="w-6 h-6 ',
                )
