"""Tests for saved album filters.

The API wants a login and is owner-scoped, so there are two different ways to
be refused and they answer differently: a signed-out caller gets 403, as
games' saved filters answer, while a reader reaching for another reader's row
gets 404 from the owner scoping.

These use the ordinary Django test client with a session login rather than
DRF's ``force_authenticate``, for the reason ``test_api`` gives: the project
sets ``DEFAULT_AUTHENTICATION_CLASSES`` to an empty list, so
``force_authenticate`` would prove nothing about whether a browser can reach
these endpoints. It is also the only way to exercise CSRF, which applies to
this module for the first time - every other music endpoint is read-only.
"""

import json

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from core.models import User
from core.tests.utils import clear_all_caches
from music import config, models
from music.tests.site import setUpModule, tearDownModule  # noqa: F401

SAMPLE_FILTERS = {
    "q": "",
    "start": 1970,
    "end": 1979,
    "genres": ["3"],
    "listened": ["yes"],
    "sort": "rank",
    "sortDirection": "asc",
}


class SavedFilterTestMixin:
    def setUp(self):
        super().setUp()
        clear_all_caches()
        self.user = User.objects.create_user(
            username="filterreader", password="filterpass"
        )
        self.client.login(username="filterreader", password="filterpass")
        self.list_url = reverse("music-api:saved-filter-list")

    def detail_url(self, pk):
        return reverse("music-api:saved-filter-detail", args=[pk])

    def post_filter(self, name, filters=None):
        return self.client.post(
            self.list_url,
            {"name": name, "filters": SAMPLE_FILTERS if filters is None else filters},
            content_type="application/json",
        )


class SavedAlbumFilterSetModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="modeluser", password="modelpass")

    def test_a_saved_filter_keeps_the_json_it_was_given(self):
        saved = models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="Seventies rock", filters=SAMPLE_FILTERS
        )
        saved.refresh_from_db()
        self.assertEqual(saved.filters, SAMPLE_FILTERS)
        self.assertIsNotNone(saved.created)
        self.assertIsNotNone(saved.modified)

    def test_str_names_the_owner_and_the_filter(self):
        saved = models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="Seventies rock", filters={}
        )
        self.assertEqual(str(saved), "modeluser: Seventies rock")

    def test_deleting_the_user_takes_their_filters(self):
        models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="Gone", filters={}
        )
        self.user.delete()
        self.assertEqual(models.SavedAlbumFilterSet.objects.count(), 0)

    def test_the_newest_change_sorts_first(self):
        first = models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="First", filters={}
        )
        models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="Second", filters={}
        )
        # Touching the older row has to move it to the front, since the
        # dropdown orders by `modified` and relies on `auto_now` firing.
        first.name = "First, renamed"
        first.save(update_fields=["name", "modified"])
        self.assertEqual(
            [entry.name for entry in models.SavedAlbumFilterSet.objects.all()],
            ["First, renamed", "Second"],
        )

    def test_the_related_name_is_the_apps_own(self):
        # The abstract base uses `%(app_label)s_saved_filters`, so games and
        # music can both hang off the user model without colliding.
        models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="Mine", filters={}
        )
        self.assertEqual(self.user.music_saved_filters.count(), 1)


class SavedAlbumFilterSetListTests(SavedFilterTestMixin, TestCase):
    def test_an_empty_collection_reads_as_empty(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"filter_sets": [], "count": 0})

    def test_a_saved_filter_comes_back_whole(self):
        self.post_filter("Seventies rock")
        payload = self.client.get(self.list_url).json()
        self.assertEqual(payload["count"], 1)
        entry = payload["filter_sets"][0]
        self.assertEqual(entry["name"], "Seventies rock")
        self.assertEqual(entry["filters"], SAMPLE_FILTERS)
        self.assertIn("modified", entry)
        self.assertIn("id", entry)

    def test_only_the_owners_filters_are_listed(self):
        other = User.objects.create_user(username="otherreader", password="otherpass")
        models.SavedAlbumFilterSet.objects.create(
            user=other, name="Not mine", filters={}
        )
        self.post_filter("Mine")
        payload = self.client.get(self.list_url).json()
        self.assertEqual([e["name"] for e in payload["filter_sets"]], ["Mine"])

    def test_the_listing_is_capped_at_the_configured_ceiling(self):
        for index in range(config.MAX_SAVED_FILTERS + 2):
            models.SavedAlbumFilterSet.objects.create(
                user=self.user, name=f"Filter {index}", filters={}
            )
        payload = self.client.get(self.list_url).json()
        self.assertEqual(payload["count"], config.MAX_SAVED_FILTERS)

    def test_the_newest_is_listed_first(self):
        self.post_filter("Older")
        self.post_filter("Newer")
        payload = self.client.get(self.list_url).json()
        self.assertEqual(
            [e["name"] for e in payload["filter_sets"]], ["Newer", "Older"]
        )


class SavedAlbumFilterSetCreateTests(SavedFilterTestMixin, TestCase):
    def test_saving_a_filter_stores_it(self):
        response = self.post_filter("Seventies rock")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["name"], "Seventies rock")
        self.assertEqual(body["filters"], SAMPLE_FILTERS)
        saved = models.SavedAlbumFilterSet.objects.get(pk=body["id"])
        self.assertEqual(saved.user, self.user)

    def test_the_name_is_trimmed(self):
        response = self.post_filter("   Padded   ")
        self.assertEqual(response.json()["name"], "Padded")

    def test_a_blank_name_is_refused(self):
        response = self.post_filter("   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Filter name is required.")
        self.assertEqual(models.SavedAlbumFilterSet.objects.count(), 0)

    def test_a_missing_name_is_refused(self):
        response = self.client.post(
            self.list_url, {"filters": {}}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_an_over_long_name_is_refused(self):
        response = self.post_filter("x" * (config.SAVED_FILTER_NAME_MAX_LENGTH + 1))
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            str(config.SAVED_FILTER_NAME_MAX_LENGTH), response.json()["error"]
        )

    def test_a_name_at_the_limit_is_accepted(self):
        response = self.post_filter("x" * config.SAVED_FILTER_NAME_MAX_LENGTH)
        self.assertEqual(response.status_code, 201)

    def test_a_duplicate_name_is_refused(self):
        self.post_filter("Seventies rock")
        response = self.post_filter("Seventies rock")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"], "A filter with this name already exists."
        )
        self.assertEqual(models.SavedAlbumFilterSet.objects.count(), 1)

    def test_another_user_may_reuse_the_same_name(self):
        other = User.objects.create_user(username="namesharer", password="sharerpass")
        models.SavedAlbumFilterSet.objects.create(
            user=other, name="Seventies rock", filters={}
        )
        self.assertEqual(self.post_filter("Seventies rock").status_code, 201)

    def test_the_cap_is_enforced(self):
        for index in range(config.MAX_SAVED_FILTERS):
            models.SavedAlbumFilterSet.objects.create(
                user=self.user, name=f"Filter {index}", filters={}
            )
        response = self.post_filter("One too many")
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            f"Maximum of {config.MAX_SAVED_FILTERS}", response.json()["error"]
        )
        self.assertEqual(
            models.SavedAlbumFilterSet.objects.count(), config.MAX_SAVED_FILTERS
        )

    def test_absent_filters_default_to_an_empty_object(self):
        response = self.client.post(
            self.list_url, {"name": "Bare"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["filters"], {})

    def test_a_non_string_name_does_not_raise(self):
        # `request.data` is whatever JSON held, so a number has to be
        # handled rather than crash on `.strip()`.
        response = self.client.post(
            self.list_url,
            {"name": 1975, "filters": {}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "1975")


class SavedAlbumFilterSetRenameTests(SavedFilterTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.saved = models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="Original", filters=SAMPLE_FILTERS
        )

    def patch_name(self, name, pk=None):
        return self.client.patch(
            self.detail_url(self.saved.pk if pk is None else pk),
            {"name": name},
            content_type="application/json",
        )

    def test_renaming_changes_the_name_and_nothing_else(self):
        response = self.patch_name("Renamed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": self.saved.pk, "name": "Renamed"})
        self.saved.refresh_from_db()
        self.assertEqual(self.saved.name, "Renamed")
        self.assertEqual(self.saved.filters, SAMPLE_FILTERS)

    def test_renaming_bumps_the_modified_stamp(self):
        before = self.saved.modified
        self.patch_name("Renamed")
        self.saved.refresh_from_db()
        self.assertGreater(self.saved.modified, before)

    def test_a_blank_name_is_refused(self):
        response = self.patch_name("  ")
        self.assertEqual(response.status_code, 400)
        self.saved.refresh_from_db()
        self.assertEqual(self.saved.name, "Original")

    def test_an_over_long_name_is_refused(self):
        response = self.patch_name("x" * (config.SAVED_FILTER_NAME_MAX_LENGTH + 1))
        self.assertEqual(response.status_code, 400)

    def test_renaming_onto_another_of_my_filters_is_refused(self):
        models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="Taken", filters={}
        )
        response = self.patch_name("Taken")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"], "A filter with this name already exists."
        )

    def test_renaming_to_the_name_it_already_has_is_allowed(self):
        # The duplicate check excludes the row being renamed, or saving a
        # filter without changing its name would look like a collision.
        self.assertEqual(self.patch_name("Original").status_code, 200)

    def test_renaming_onto_another_users_name_is_allowed(self):
        other = User.objects.create_user(username="renamesharer", password="sharerpass")
        models.SavedAlbumFilterSet.objects.create(user=other, name="Theirs", filters={})
        self.assertEqual(self.patch_name("Theirs").status_code, 200)

    def test_renaming_someone_elses_filter_is_a_404(self):
        other = User.objects.create_user(username="renametarget", password="targetpass")
        theirs = models.SavedAlbumFilterSet.objects.create(
            user=other, name="Theirs", filters={}
        )
        response = self.patch_name("Stolen", pk=theirs.pk)
        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertEqual(theirs.name, "Theirs")

    def test_renaming_a_filter_that_does_not_exist_is_a_404(self):
        self.assertEqual(self.patch_name("Ghost", pk=999999).status_code, 404)


class SavedAlbumFilterSetDeleteTests(SavedFilterTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.saved = models.SavedAlbumFilterSet.objects.create(
            user=self.user, name="Doomed", filters={}
        )

    def test_deleting_removes_the_row(self):
        response = self.client.delete(self.detail_url(self.saved.pk))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(models.SavedAlbumFilterSet.objects.count(), 0)

    def test_deleting_someone_elses_filter_is_a_404(self):
        other = User.objects.create_user(username="deletetarget", password="targetpass")
        theirs = models.SavedAlbumFilterSet.objects.create(
            user=other, name="Theirs", filters={}
        )
        response = self.client.delete(self.detail_url(theirs.pk))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            models.SavedAlbumFilterSet.objects.filter(pk=theirs.pk).exists()
        )

    def test_deleting_a_filter_that_does_not_exist_is_a_404(self):
        self.assertEqual(self.client.delete(self.detail_url(999999)).status_code, 404)


class SavedAlbumFilterAccessTests(TestCase):
    """A signed-out caller gets 403; someone else's row is a 404."""

    def setUp(self):
        clear_all_caches()
        self.list_url = reverse("music-api:saved-filter-list")
        self.owner = User.objects.create_user(
            username="accessowner", password="ownerpass"
        )
        self.saved = models.SavedAlbumFilterSet.objects.create(
            user=self.owner, name="Private", filters={}
        )
        self.detail_url = reverse("music-api:saved-filter-detail", args=[self.saved.pk])

    def test_an_anonymous_visitor_gets_403_on_the_listing(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_an_anonymous_visitor_cannot_save_a_filter(self):
        response = self.client.post(
            self.list_url, {"name": "Sneaky"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.SavedAlbumFilterSet.objects.count(), 1)

    def test_another_reader_cannot_delete(self):
        User.objects.create_user(username="plain2", password="plainpass")
        self.client.login(username="plain2", password="plainpass")
        self.assertEqual(self.client.delete(self.detail_url).status_code, 404)
        self.assertTrue(
            models.SavedAlbumFilterSet.objects.filter(pk=self.saved.pk).exists()
        )


class SavedAlbumFilterCsrfTests(TestCase):
    """CSRF applies to this module for the first time.

    Every other music endpoint is read-only, so no unsafe method ever
    reached ``CsrfViewMiddleware``. The ordinary test client does not
    enforce CSRF at all - which is how `test_views` came to assert a 404 for
    a POST that production answers 403 - so this suite builds a client that
    does.
    """

    def setUp(self):
        clear_all_caches()
        self.user = User.objects.create_user(username="csrfreader", password="csrfpass")
        self.list_url = reverse("music-api:saved-filter-list")

    def test_a_post_without_a_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="csrfreader", password="csrfpass")
        response = client.post(
            self.list_url,
            {"name": "No token", "filters": {}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.SavedAlbumFilterSet.objects.count(), 0)

    def test_a_post_carrying_the_token_succeeds(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="csrfreader", password="csrfpass")
        # The token the browser would have, obtained the way the browser
        # obtains it: by loading a music page.
        client.get(reverse("music:home"))
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        response = client.post(
            self.list_url,
            json.dumps({"name": "With token", "filters": {}}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.SavedAlbumFilterSet.objects.count(), 1)
