"""Tests for the music API.

These tests use the ordinary Django test client with a session login rather
than DRF's ``force_authenticate``, because session authentication is exactly
what the mixins exist to make work: the project sets
``DEFAULT_AUTHENTICATION_CLASSES`` to an empty list, so a view that does not
name an authenticator sees a logged-in reader as anonymous.
"""

import json

from django.db.models.functions import Lower
from django.test import TestCase
from django.urls import reverse

from core import constants as core_constants
from core.models import User
from music import models
from music.tests.site import setUpModule, tearDownModule  # noqa: F401


class MusicAPITestMixin:
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="apireader", password="apipass")
        self.client.login(username="apireader", password="apipass")

        self.artist = models.Artist.objects.create(
            name="Radiohead", slug="radiohead", wikidata_id="Q4075"
        )
        self.genre = models.MusicGenre.objects.create(name="Rock")
        self.child_genre = models.MusicGenre.objects.create(
            name="Art Rock", parent=self.genre
        )

        self.kid_a = models.Album.objects.create(
            name="Kid A",
            rank=1,
            artist_credit="Radiohead",
            year_released=2000,
            wikidata_id="Q202698",
        )
        self.kid_a.artists.set([self.artist])
        self.kid_a.genres.set([self.genre])

        self.ok_computer = models.Album.objects.create(
            name="OK Computer",
            rank=2,
            artist_credit="Radiohead",
            year_released=1997,
        )
        self.ok_computer.artists.set([self.artist])

        self.publication = models.MusicPublication.objects.create(name="Pitchfork")
        self.source = models.MusicList.objects.create(
            name="The Best Albums of the 1990s",
            year=2022,
            publisher=self.publication,
            order=1,
            type=core_constants.LIST_DECADE,
        )
        models.AlbumListMembership.objects.create(
            list=self.source, album=self.kid_a, rank=3
        )

    def payload(self, path, **params):
        response = self.client.get(path, params)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)


class AlbumListAPITests(MusicAPITestMixin, TestCase):
    def test_lists_albums_in_rank_order(self):
        data = self.payload(reverse("music-api:album-list"))
        self.assertEqual([a["rank"] for a in data["results"]], [1, 2])

    def test_search_matches_title_or_credit(self):
        data = self.payload(reverse("music-api:album-list"), q="kid")
        self.assertEqual([a["name"] for a in data["results"]], ["Kid A"])
        data = self.payload(reverse("music-api:album-list"), q="radiohead")
        self.assertEqual(len(data["results"]), 2)

    def test_artist_slug_filter(self):
        data = self.payload(reverse("music-api:album-list"), artist="radiohead")
        self.assertEqual(len(data["results"]), 2)
        data = self.payload(reverse("music-api:album-list"), artist="nobody")
        self.assertEqual(len(data["results"]), 0)

    def test_genre_filter(self):
        data = self.payload(reverse("music-api:album-list"), genres=str(self.genre.id))
        self.assertEqual([a["name"] for a in data["results"]], ["Kid A"])

    def test_a_non_numeric_genre_filter_is_ignored(self):
        data = self.payload(reverse("music-api:album-list"), genres="abc")
        self.assertEqual(len(data["results"]), 2)

    def test_year_range_filter(self):
        data = self.payload(reverse("music-api:album-list"), start="1999", end="2001")
        self.assertEqual([a["name"] for a in data["results"]], ["Kid A"])

    def test_a_non_numeric_year_filter_is_ignored(self):
        data = self.payload(reverse("music-api:album-list"), start="x", end="y")
        self.assertEqual(len(data["results"]), 2)

    def test_the_summary_payload_carries_the_expected_fields(self):
        data = self.payload(reverse("music-api:album-list"))
        album = data["results"][0]
        for field in [
            "id",
            "name",
            "slug",
            "rank",
            "year_rank",
            "decade_rank",
            "year_released",
            "artist_credit",
            "artists",
            "genres",
            "cover_image_url",
            "wikidata_id",
            "musicbrainz_release_group_id",
            "list_count",
        ]:
            self.assertIn(field, album)
        self.assertEqual(album["artists"][0]["slug"], "radiohead")
        self.assertEqual(album["list_count"], 1)

    def test_list_count_is_zero_for_an_album_on_no_lists(self):
        data = self.payload(reverse("music-api:album-list"))
        by_name = {a["name"]: a for a in data["results"]}
        self.assertEqual(by_name["OK Computer"]["list_count"], 0)


class AlbumDetailAPITests(MusicAPITestMixin, TestCase):
    def test_returns_the_album_with_its_list_appearances(self):
        data = self.payload(reverse("music-api:album-detail", kwargs={"slug": "kid-a"}))
        self.assertEqual(data["name"], "Kid A")
        self.assertEqual(data["list_count"], 1)
        self.assertEqual(len(data["lists"]), 1)
        entry = data["lists"][0]
        self.assertEqual(entry["name"], "The Best Albums of the 1990s")
        self.assertEqual(entry["publication"], "Pitchfork")
        self.assertEqual(entry["type"], core_constants.LIST_DECADE)
        self.assertEqual(entry["year"], 2022)
        self.assertEqual(entry["rank"], 3)

    def test_includes_the_description_field(self):
        data = self.payload(reverse("music-api:album-detail", kwargs={"slug": "kid-a"}))
        self.assertIn("description", data)

    def test_unknown_slug_is_404(self):
        response = self.client.get(
            reverse("music-api:album-detail", kwargs={"slug": "nope"})
        )
        self.assertEqual(response.status_code, 404)


class AlbumSearchAPITests(MusicAPITestMixin, TestCase):
    def test_returns_matching_albums_unpaginated(self):
        data = self.payload(reverse("music-api:album-search"), q="kid")
        self.assertIsInstance(data, list)
        self.assertEqual([a["name"] for a in data], ["Kid A"])

    def test_matches_the_artist_credit(self):
        data = self.payload(reverse("music-api:album-search"), q="radiohead")
        self.assertEqual(len(data), 2)

    def test_no_query_returns_an_empty_list(self):
        data = self.payload(reverse("music-api:album-search"))
        self.assertEqual(data, [])


class ArtistAPITests(MusicAPITestMixin, TestCase):
    def test_lists_artists_with_album_counts(self):
        data = self.payload(reverse("music-api:artist-list"))
        self.assertEqual(data["results"][0]["name"], "Radiohead")
        self.assertEqual(data["results"][0]["albums_count"], 2)

    def test_excludes_artists_with_no_albums(self):
        models.Artist.objects.create(name="Nobody", slug="nobody")
        data = self.payload(reverse("music-api:artist-list"))
        self.assertEqual([a["name"] for a in data["results"]], ["Radiohead"])

    def test_search_filters_by_name(self):
        data = self.payload(reverse("music-api:artist-list"), q="radio")
        self.assertEqual(len(data["results"]), 1)
        data = self.payload(reverse("music-api:artist-list"), q="zzz")
        self.assertEqual(len(data["results"]), 0)

    def test_detail_includes_the_artist_albums(self):
        data = self.payload(
            reverse("music-api:artist-detail", kwargs={"slug": "radiohead"})
        )
        self.assertEqual(data["name"], "Radiohead")
        self.assertEqual(data["wikidata_id"], "Q4075")
        self.assertEqual(data["albums_count"], 2)
        self.assertEqual([a["rank"] for a in data["albums"]], [1, 2])

    def test_detail_unknown_slug_is_404(self):
        response = self.client.get(
            reverse("music-api:artist-detail", kwargs={"slug": "nope"})
        )
        self.assertEqual(response.status_code, 404)

    def _variant(self):
        """An album credited to Radiohead under another of its names."""
        self.artist.name_variants = ["Radiohead", "Radiohead Project", "Unused"]
        self.artist.save()
        album = models.Album.objects.create(
            name="Side Album", rank=50, artist_credit="Radiohead Project"
        )
        models.AlbumCredit.objects.create(
            album=album,
            artist=self.artist,
            variant=1,
            credited_name="Radiohead Project",
        )
        return album

    def test_counts_include_albums_under_another_name(self):
        self._variant()
        data = self.payload(reverse("music-api:artist-list"))
        self.assertEqual(
            [(a["name"], a["albums_count"]) for a in data["results"]],
            [("Radiohead", 3)],
        )
        self.assertEqual(data["results"][0]["also_credited_as"], ["Radiohead Project"])

    def test_the_list_search_matches_a_credited_name(self):
        self._variant()
        data = self.payload(reverse("music-api:artist-list"), q="project")
        self.assertEqual([a["name"] for a in data["results"]], ["Radiohead"])
        data = self.payload(reverse("music-api:artist-list"), q="unused")
        self.assertEqual(data["results"], [])

    def test_detail_lists_albums_under_every_name(self):
        self._variant()
        data = self.payload(
            reverse("music-api:artist-detail", kwargs={"slug": "radiohead"})
        )
        self.assertEqual(
            [a["name"] for a in data["albums"]], ["Kid A", "OK Computer", "Side Album"]
        )
        self.assertEqual(data["albums_count"], 3)
        self.assertEqual(data["also_credited_as"], ["Radiohead Project"])
        side = data["albums"][2]
        self.assertEqual(side["artists"][0]["slug"], "radiohead")
        self.assertEqual(side["artists"][0]["credited_name"], "Radiohead Project")

    def test_detail_lists_albums_with_other_artists_apart(self):
        guest = models.Artist.objects.create(name="Guest", slug="guest")
        models.AlbumCredit.objects.create(album=self.kid_a, artist=guest, position=1)
        data = self.payload(
            reverse("music-api:artist-detail", kwargs={"slug": "radiohead"})
        )
        self.assertEqual([a["name"] for a in data["albums"]], ["OK Computer"])
        self.assertEqual([a["name"] for a in data["with_other_artists"]], ["Kid A"])
        self.assertEqual(data["albums_count"], 2)

    def test_the_album_list_artist_filter_finds_every_name(self):
        self._variant()
        data = self.payload(reverse("music-api:album-list"), artist="radiohead")
        self.assertIn("Side Album", [a["name"] for a in data["results"]])


def _artist_dicts_with_an_id(value, slug="radiohead"):
    """Every dict in a payload naming the artist ``slug`` that carries an id."""
    if isinstance(value, dict):
        if value.get("slug") == slug and "id" in value:
            yield value
        for item in value.values():
            yield from _artist_dicts_with_an_id(item, slug)
    elif isinstance(value, list):
        for item in value:
            yield from _artist_dicts_with_an_id(item, slug)


class MusicListAPITests(MusicAPITestMixin, TestCase):
    def test_lists_sources_in_order(self):
        data = self.payload(reverse("music-api:musiclist-list"))
        self.assertEqual(data["results"][0]["name"], "The Best Albums of the 1990s")
        self.assertEqual(data["results"][0]["publication"], "Pitchfork")
        self.assertEqual(data["results"][0]["order"], 1)

    def test_type_filter(self):
        data = self.payload(
            reverse("music-api:musiclist-list"), type=core_constants.LIST_DECADE
        )
        self.assertEqual(len(data["results"]), 1)
        data = self.payload(
            reverse("music-api:musiclist-list"), type=core_constants.LIST_ALLTIME
        )
        self.assertEqual(len(data["results"]), 0)

    def test_an_unknown_type_filter_is_ignored(self):
        data = self.payload(reverse("music-api:musiclist-list"), type="Z")
        self.assertEqual(len(data["results"]), 1)

    def test_a_list_without_a_publisher_serializes(self):
        models.MusicList.objects.create(name="Unattributed", year=2001, order=2)
        data = self.payload(reverse("music-api:musiclist-list"))
        by_name = {entry["name"]: entry for entry in data["results"]}
        self.assertEqual(by_name["Unattributed"]["publication"], "")


class MusicGenreAPITests(MusicAPITestMixin, TestCase):
    def test_lists_genres_ordered_for_tree_reassembly(self):
        data = self.payload(reverse("music-api:genre-list"))
        self.assertEqual([g["name"] for g in data], ["Rock", "Art Rock"])
        self.assertEqual(data[0]["level"], 0)
        self.assertIsNone(data[0]["parent_id"])
        self.assertEqual(data[1]["parent_id"], self.genre.id)
        self.assertEqual(data[1]["path"], "Rock > Art Rock")


class MusicMetaAPITests(MusicAPITestMixin, TestCase):
    def test_reports_album_counts_and_year_bounds(self):
        data = self.payload(reverse("music-api:meta"))
        self.assertEqual(data["albums"]["total_count"], 2)
        self.assertEqual(data["albums"]["min_year"], 1997)
        self.assertEqual(data["albums"]["max_year"], 2000)
        self.assertEqual(
            data["albums"]["years"],
            [
                {"year_released": 1997, "count": 1},
                {"year_released": 2000, "count": 1},
            ],
        )

    def test_reports_decade_buckets(self):
        data = self.payload(reverse("music-api:meta"))
        self.assertEqual(
            data["albums"]["decades"],
            [{"decade": "1990-99", "count": 1}, {"decade": "2000-09", "count": 1}],
        )

    def test_an_album_with_no_year_is_left_out_of_the_distributions(self):
        models.Album.objects.create(name="Undated", rank=3)
        data = self.payload(reverse("music-api:meta"))
        self.assertEqual(data["albums"]["total_count"], 3)
        self.assertEqual(len(data["albums"]["years"]), 2)

    def test_reports_artist_list_and_publication_counts(self):
        data = self.payload(reverse("music-api:meta"))
        self.assertEqual(data["artists"]["total_count"], 1)
        self.assertEqual(data["lists"]["total_count"], 1)
        self.assertEqual(data["publications"]["total_count"], 1)
        self.assertEqual(data["lists"]["years"], [{"year": 2022, "count": 1}])

    def test_reports_list_counts_by_type_in_importance_order(self):
        data = self.payload(reverse("music-api:meta"))
        by_type = data["lists"]["by_type"]
        self.assertEqual(
            [entry["type"] for entry in by_type],
            list(core_constants.LIST_TYPE_IMPORTANCE_ORDER),
        )
        counts = {entry["type"]: entry["count"] for entry in by_type}
        self.assertEqual(counts[core_constants.LIST_DECADE], 1)
        self.assertEqual(counts[core_constants.LIST_ALLTIME], 0)
        labels = {entry["type"]: entry["label"] for entry in by_type}
        self.assertEqual(labels[core_constants.LIST_DECADE], "Decade")


class AlbumAllDataAPITests(MusicAPITestMixin, TestCase):
    """The bulk payload the client-side filtering bundle runs on."""

    def url(self):
        return reverse("music-api:album-all-data")

    def test_returns_every_album_in_rank_order(self):
        data = self.payload(self.url())
        self.assertEqual(sorted(data), ["albums", "artists", "genres", "version"])
        self.assertEqual([album["r"] for album in data["albums"]], [1, 2])
        self.assertEqual(
            [album["n"] for album in data["albums"]], ["Kid A", "OK Computer"]
        )

    def test_album_fields_are_the_ones_the_renderer_reads(self):
        data = self.payload(self.url())
        album = data["albums"][0]
        self.assertEqual(
            sorted(album),
            ["ar", "c", "g", "id", "lc", "n", "ni", "nn", "r", "rd", "s", "t", "y"],
        )
        # "cv" and "va" are sent only for the albums that need them.
        self.assertEqual(album["id"], self.kid_a.id)
        self.assertEqual(album["s"], "kid-a")
        self.assertEqual(album["y"], 2000)
        self.assertIsNone(album["rd"])  # undated until the metadata pass
        self.assertEqual(album["c"], "Radiohead")
        self.assertEqual(album["ar"], ["radiohead"])
        self.assertEqual(album["g"], [self.genre.id])
        self.assertEqual(album["lc"], 1)

    def test_the_payload_carries_no_per_user_state(self):
        # Deliberately absent. The bundle caches this payload in
        # sessionStorage keyed only on its version, with no user in the key,
        # so a listened flag here would be served to whoever used the
        # browser session next. The album pk is the join key instead, and the
        # page renders window.listenedAlbumIds per request.
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.kid_a, wikidata_id="Q-kid-a"
        )
        album = self.payload(self.url())["albums"][0]
        for key in ("listened", "l", "tracked", "w", "wikidata_id"):
            with self.subTest(key=key):
                self.assertNotIn(key, album)

    def test_the_payload_version_does_not_depend_on_the_user(self):
        # Corollary of the above: the key is version-only, so the version had
        # better not be either, or every user would miss the cache.
        before = self.payload(self.url())["version"]
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.kid_a, wikidata_id="Q-kid-a"
        )
        self.assertEqual(self.payload(self.url())["version"], before)

    def test_name_normalized_is_sent_for_the_text_search(self):
        # The server's `q` searches name_normalized too, so the client needs
        # it rather than reimplementing unidecode in the browser.
        album = models.Album.objects.create(name="Ágætis byrjun", rank=3)
        data = self.payload(self.url())
        sent = {entry["id"]: entry["nn"] for entry in data["albums"]}
        self.assertEqual(sent[album.id], "Agaetis byrjun")
        # Stored only when it differs from the name; sent as "" otherwise.
        self.assertEqual(sent[self.kid_a.id], "")

    def test_the_alphabetical_order_is_precomputed(self):
        # The client sorts by this rather than recomputing `Lower(name)`:
        # no JavaScript comparator reproduces a database collation, and
        # local SQLite does not even agree with production Postgres.
        models.Album.objects.create(name="Ágætis byrjun", rank=3)
        data = self.payload(self.url())
        by_position = sorted(data["albums"], key=lambda album: album["ni"])
        self.assertEqual(
            [album["n"] for album in by_position],
            list(
                models.Album.objects.order_by(Lower("name")).values_list(
                    "name", flat=True
                )
            ),
        )

    def test_a_credit_under_another_name_sends_the_names(self):
        self.artist.name_variants = ["Radiohead", "On a Friday"]
        self.artist.save()
        album = models.Album.objects.create(
            name="Demo", rank=3, artist_credit="On a Friday & Various Artists"
        )
        album.various_artists = True
        album.save()
        models.AlbumCredit.objects.create(
            album=album, artist=self.artist, variant=1, credited_name="On a Friday"
        )
        compilation = models.Album.objects.create(
            name="Nuggets",
            rank=4,
            artist_credit="Various Artists",
            various_artists=True,
        )
        sent = {entry["id"]: entry for entry in self.payload(self.url())["albums"]}
        self.assertEqual(sent[album.id]["ar"], ["radiohead"])
        self.assertEqual(sent[album.id]["cv"], ["On a Friday"])
        self.assertEqual(sent[album.id]["va"], 1)
        self.assertEqual(sent[compilation.id]["ar"], [])
        self.assertEqual(sent[compilation.id]["va"], 1)
        self.assertNotIn("cv", sent[compilation.id])
        self.assertNotIn("cv", sent[self.kid_a.id])
        self.assertNotIn("va", sent[self.kid_a.id])

    def test_artists_are_a_lookup_table_keyed_by_slug(self):
        # Never by pk: those were handed out in the provider's entry order.
        data = self.payload(self.url())
        self.assertEqual(data["artists"], {"radiohead": {"n": "Radiohead"}})

    def test_no_artist_endpoint_exposes_an_artist_pk(self):
        for url, params in (
            (reverse("music-api:artist-list"), {}),
            (reverse("music-api:artist-detail", kwargs={"slug": "radiohead"}), {}),
            (reverse("music-api:unified-search"), {"q": "radiohead"}),
            (reverse("music-api:album-list"), {}),
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    list(_artist_dicts_with_an_id(self.payload(url, **params))), []
                )

    def test_genres_carry_their_descendants(self):
        data = self.payload(self.url())
        by_id = {entry["id"]: entry for entry in data["genres"]}
        self.assertEqual(by_id[self.genre.id]["d"], [self.child_genre.id])
        self.assertEqual(by_id[self.child_genre.id]["p"], self.genre.id)

    def test_a_grandchild_follows_its_parent_in_the_descendant_list(self):
        """`"d"` is depth first and excludes the genre itself.

        `AlbumFilterEngine._expandGenres` reads this list straight, so its
        order and its exclude-self shape are the contract - they survived the
        switch from walking `children` to one in-memory map, and this pins
        that they keep surviving.
        """
        grandchild = models.MusicGenre.objects.create(
            name="Dark Ambient", parent=self.child_genre
        )
        data = self.payload(self.url())
        by_id = {entry["id"]: entry for entry in data["genres"]}
        self.assertEqual(
            by_id[self.genre.id]["d"], [self.child_genre.id, grandchild.id]
        )
        self.assertEqual(by_id[self.child_genre.id]["d"], [grandchild.id])
        self.assertEqual(by_id[grandchild.id]["d"], [])

    def test_the_descendants_match_the_per_instance_walk(self):
        models.MusicGenre.objects.create(name="Dark Ambient", parent=self.child_genre)
        data = self.payload(self.url())
        by_id = {entry["id"]: entry for entry in data["genres"]}
        for genre in models.MusicGenre.objects.all():
            with self.subTest(genre=genre.name):
                self.assertEqual(
                    by_id[genre.id]["d"],
                    genre.get_descendant_ids(include_self=False),
                )

    def test_version_is_a_short_hash(self):
        data = self.payload(self.url())
        self.assertEqual(len(data["version"]), 12)

    def test_version_changes_when_an_album_changes(self):
        before = self.payload(self.url())["version"]
        self.kid_a.name = "Kid A Mnesia"
        self.kid_a.save()
        self.assertNotEqual(self.payload(self.url())["version"], before)

    def test_version_changes_when_a_genre_is_added(self):
        before = self.payload(self.url())["version"]
        models.MusicGenre.objects.create(name="Ambient")
        self.assertNotEqual(self.payload(self.url())["version"], before)

    def test_version_changes_when_cover_art_is_stored(self):
        # Cover art is written to the MusicBrainz row, which does not touch
        # Album.modified - so without this signal a client would hold a copy
        # with missing covers and no way to know it was stale.
        before = self.payload(self.url())["version"]
        models.MusicBrainzAlbumData.objects.create(
            album=self.kid_a, cover_art_stored=True
        )
        self.assertNotEqual(self.payload(self.url())["version"], before)


class MusicUnifiedSearchViewTests(MusicAPITestMixin, TestCase):
    """The endpoint behind the sidebar and mobile search boxes.

    Music had no unified search at all, which is why the shared search box in
    the chrome was gated on ``media_type == 'games'`` and the section showed
    no search anywhere.
    """

    def setUp(self):
        super().setUp()
        self.url = reverse("music-api:unified-search")

    def test_a_short_query_returns_empty_groups(self):
        # Two characters is the floor the search box itself enforces; the
        # endpoint must not run a full scan for a single letter.
        response = self.client.get(self.url, {"q": "a"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"albums": [], "artists": [], "order": ["artists", "albums"]},
        )

    def test_albums_match_on_title_and_on_credit(self):
        by_title = self.client.get(self.url, {"q": "kid a"}).json()
        self.assertEqual([album["name"] for album in by_title["albums"]], ["Kid A"])

        by_credit = self.client.get(self.url, {"q": "radiohead"}).json()
        self.assertEqual(
            sorted(album["name"] for album in by_credit["albums"]),
            ["Kid A", "OK Computer"],
        )

    def test_an_album_carries_what_the_dropdown_renders(self):
        album = self.client.get(self.url, {"q": "kid a"}).json()["albums"][0]
        self.assertEqual(album["slug"], self.kid_a.slug)
        self.assertEqual(album["rank"], self.kid_a.rank)
        self.assertEqual(album["year_released"], 2000)
        self.assertEqual(album["artist_credit"], "Radiohead")
        self.assertIn("thumbnail", album)

    def test_artists_are_matched_and_counted(self):
        artists = self.client.get(self.url, {"q": "radiohead"}).json()["artists"]
        self.assertEqual(artists[0]["name"], "Radiohead")
        self.assertEqual(artists[0]["albums_count"], 2)
        self.assertEqual(artists[0]["summary"], "2 albums")
        self.assertEqual(artists[0]["slug"], "radiohead")

    def test_an_artist_is_found_by_a_name_an_album_credits_them_as(self):
        self.artist.name_variants = ["Radiohead", "On a Friday"]
        self.artist.save()
        models.AlbumCredit.objects.filter(album=self.kid_a).update(
            variant=1, credited_name="On a Friday"
        )
        artists = self.client.get(self.url, {"q": "friday"}).json()["artists"]
        self.assertEqual([a["name"] for a in artists], ["Radiohead"])
        self.assertEqual(artists[0]["summary"], "2 albums")

    def test_an_artist_with_no_albums_is_not_offered(self):
        models.Artist.objects.create(name="Radio Ghost", slug="radio-ghost")
        names = [
            artist["name"]
            for artist in self.client.get(self.url, {"q": "radio"}).json()["artists"]
        ]
        self.assertNotIn("Radio Ghost", names)

    def test_results_are_limited(self):
        response = self.client.get(self.url, {"q": "radiohead", "album_limit": "1"})
        self.assertEqual(len(response.json()["albums"]), 1)

    def test_a_nonsense_limit_falls_back_rather_than_raising(self):
        for raw in ("", "many", "0", "500"):
            with self.subTest(limit=raw):
                response = self.client.get(
                    self.url, {"q": "radiohead", "album_limit": raw}
                )
                self.assertEqual(response.status_code, 200)
                self.assertGreaterEqual(len(response.json()["albums"]), 1)

    def _album(self, name, rank, credit, artist=None):
        album = models.Album.objects.create(name=name, rank=rank, artist_credit=credit)
        if artist:
            album.artists.set([artist])
        return album

    def test_artists_lead_when_the_query_names_an_artist(self):
        # "Beatles" filled all five album rows with Beatles albums, matched
        # on their credit, and the band sat below the dropdown's fold.
        data = self.client.get(self.url, {"q": "radiohead"}).json()
        self.assertEqual(data["order"], ["artists", "albums"])

    def test_albums_lead_when_a_title_is_the_better_match(self):
        self._album(
            "Kid Astray Live",
            40,
            "Kid Astray",
            models.Artist.objects.create(name="Kid Astray", slug="kid-astray"),
        )
        data = self.client.get(self.url, {"q": "kid a"}).json()
        self.assertEqual([a["name"] for a in data["artists"]], ["Kid Astray"])
        self.assertEqual(data["order"], ["albums", "artists"])
        self.assertEqual(data["albums"][0]["name"], "Kid A")

    def test_an_artist_and_a_self_titled_album_tie_to_the_artist(self):
        self._album("Radiohead", 30, "Radiohead", self.artist)
        data = self.client.get(self.url, {"q": "radiohead"}).json()
        self.assertEqual(data["order"], ["artists", "albums"])
        # Among the albums, the exact title comes first all the same.
        self.assertEqual(data["albums"][0]["name"], "Radiohead")

    def test_with_no_artist_match_albums_lead(self):
        data = self.client.get(self.url, {"q": "computer"}).json()
        self.assertEqual(data["artists"], [])
        self.assertEqual(data["order"], ["albums", "artists"])

    def test_albums_keep_rank_order_but_for_an_exact_title(self):
        # By match alone "Beatles" put Meet the Beatles! (#820) above Abbey
        # Road (#4); only an exact title jumps the ranking.
        self._album("Radiohead Covered", 900, "Various Artists")
        self._album("Radiohead", 950, "Various Artists")
        names = [
            album["name"]
            for album in self.client.get(self.url, {"q": "radiohead"}).json()["albums"]
        ]
        self.assertEqual(
            names, ["Radiohead", "Kid A", "OK Computer", "Radiohead Covered"]
        )

    def test_the_album_limit_keeps_the_exact_title(self):
        self._album("Radiohead", 950, "Various Artists")
        data = self.client.get(self.url, {"q": "radiohead", "album_limit": "1"}).json()
        self.assertEqual([a["name"] for a in data["albums"]], ["Radiohead"])

    def test_only_the_albums_shown_decide_which_group_leads(self):
        stray = models.Artist.objects.create(name="Kid Astray", slug="kid-astray")
        self._album("Live", 3, "Kid Astray", stray)
        self._album("Strays", 900, "Somebody Else")
        # "Strays" starts with the query, and Kid Astray only contains it,
        # but the one album shown is matched on its credit alone.
        data = self.client.get(self.url, {"q": "stray", "album_limit": "1"}).json()
        self.assertEqual([a["name"] for a in data["albums"]], ["Live"])
        self.assertEqual(data["order"], ["artists", "albums"])
        data = self.client.get(self.url, {"q": "stray"}).json()
        self.assertEqual(data["order"], ["albums", "artists"])

    def test_artists_are_ordered_by_match_before_album_count(self):
        tribute = models.Artist.objects.create(
            name="Radiohead Tribute Band", slug="radiohead-tribute-band"
        )
        for rank in (50, 51, 52):
            self._album(f"Tribute {rank}", rank, "Radiohead Tribute Band", tribute)
        artists = self.client.get(self.url, {"q": "radiohead"}).json()["artists"]
        self.assertEqual(
            [(a["name"], a["albums_count"]) for a in artists],
            [("Radiohead", 2), ("Radiohead Tribute Band", 3)],
        )
        # With the match equal, the most albums still come first.
        artists = self.client.get(self.url, {"q": "radioh"}).json()["artists"]
        self.assertEqual(
            [a["name"] for a in artists], ["Radiohead Tribute Band", "Radiohead"]
        )
