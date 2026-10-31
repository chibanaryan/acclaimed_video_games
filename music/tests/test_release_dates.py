"""The year sort orders a year's albums by release date.

``music.services.release_dates`` derives ``Album.release_date`` from the
stored metadata; the server sorts by year, then that date, then rank; and the
browser engine has to agree, so its comparator and the payload field it reads
are pinned here in source and minified form.
"""

import csv
from datetime import date
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from music import models
from music.services import data_version
from music.services.release_dates import (
    UNDATED,
    parse_partial_date,
    pick_release_date,
    refresh_release_dates,
)
from music.templatetags.music_filters import release_date_label
from music.tests.test_views import ClearsCachesMixin
from music.tests.site import setUpModule, tearDownModule  # noqa: F401

COMMAND = "music.management.commands.fetch_album_metadata"


class ParsePartialDateTests(SimpleTestCase):
    def test_a_full_date(self):
        self.assertEqual(parse_partial_date("1966-05-16"), (date(1966, 5, 16), "day"))

    def test_a_month_is_its_first_day(self):
        self.assertEqual(parse_partial_date("1966-05"), (date(1966, 5, 1), "month"))

    def test_a_bare_year_adds_nothing(self):
        self.assertEqual(parse_partial_date("1966"), UNDATED)

    def test_empty_and_junk_are_undated(self):
        for text in (None, "", "1966-xx-01", "1966-13-01", "1-2-3-4"):
            with self.subTest(text=text):
                self.assertEqual(parse_partial_date(text), UNDATED)


class PickReleaseDateTests(SimpleTestCase):
    AUG_5 = date(1966, 8, 5)

    def test_a_day_precise_wikidata_date_wins(self):
        self.assertEqual(
            pick_release_date(self.AUG_5, "day", "1966-08-08"), (self.AUG_5, "day")
        )

    def test_musicbrainz_fills_in(self):
        self.assertEqual(
            pick_release_date(None, "", "1966-08"), (date(1966, 8, 1), "month")
        )

    def test_musicbrainz_supplies_the_day_of_an_agreed_month(self):
        for precision in ("month", ""):
            with self.subTest(precision=precision):
                self.assertEqual(
                    pick_release_date(date(1966, 8, 1), precision, "1966-08-05"),
                    (self.AUG_5, "day"),
                )

    def test_a_disagreeing_month_keeps_wikidata(self):
        self.assertEqual(
            pick_release_date(date(1966, 8, 1), "month", "1966-09-05"),
            (date(1966, 8, 1), "month"),
        )

    def test_a_month_from_musicbrainz_does_not_replace_wikidata(self):
        self.assertEqual(
            pick_release_date(date(1966, 8, 1), "", "1966-08"),
            (date(1966, 8, 1), ""),
        )

    def test_nothing_known(self):
        self.assertEqual(pick_release_date(None, "", ""), UNDATED)


class RefreshReleaseDatesTests(TestCase):
    def _album(self, rank, wikidata=None, musicbrainz=None, precision="day"):
        album = models.Album.objects.create(
            name=f"Album {rank}", rank=rank, year_released=1966
        )
        if wikidata is not None:
            album.primary_wikipedia_album_data = (
                models.WikipediaAlbumData.objects.create(
                    album=album,
                    wikidata_id=f"Q{rank}",
                    release_date=wikidata,
                    release_date_precision=precision,
                )
            )
        if musicbrainz is not None:
            album.primary_musicbrainz_album_data = (
                models.MusicBrainzAlbumData.objects.create(
                    album=album,
                    release_group_mbid=f"rg-{rank}",
                    first_release_date=musicbrainz,
                )
            )
        album.save()
        return album

    def test_it_derives_each_album_from_its_primary_rows(self):
        both = self._album(1, date(1966, 8, 5), "1966-08-08")
        mb_only = self._album(2, musicbrainz="1966-05")
        year_only = self._album(3, musicbrainz="1966")
        bare = self._album(4)

        self.assertEqual(refresh_release_dates(), 2)

        both.refresh_from_db()
        mb_only.refresh_from_db()
        year_only.refresh_from_db()
        bare.refresh_from_db()
        self.assertEqual(both.release_date, date(1966, 8, 5))
        self.assertEqual(both.release_date_precision, "day")
        self.assertEqual(mb_only.release_date, date(1966, 5, 1))
        self.assertEqual(mb_only.release_date_precision, "month")
        self.assertIsNone(year_only.release_date)
        self.assertIsNone(bare.release_date)

    def test_a_second_run_changes_nothing(self):
        self._album(1, date(1966, 8, 5))
        refresh_release_dates()
        self.assertEqual(refresh_release_dates(), 0)

    def test_a_change_moves_the_client_data_version(self):
        # bulk_update skips auto_now; without the explicit `modified` a
        # browser holding the payload would sort by the old dates.
        album = self._album(1, date(1966, 8, 5))
        refresh_release_dates()
        before = data_version.compute_album_data_version()
        record = album.primary_wikipedia_album_data
        record.release_date = date(1966, 8, 6)
        record.save()
        refresh_release_dates()
        self.assertNotEqual(data_version.compute_album_data_version(), before)

    def test_learning_the_precision_alone_is_a_change(self):
        # The first Wikidata pass after the deploy stores only the precision;
        # the date it fills in is the same one the migration already had.
        album = self._album(1, date(1966, 8, 5), precision="")
        refresh_release_dates()
        record = album.primary_wikipedia_album_data
        record.release_date_precision = "day"
        record.save()
        self.assertEqual(refresh_release_dates(), 1)
        album.refresh_from_db()
        self.assertEqual(album.release_date_precision, "day")

    def test_a_date_that_is_gone_is_cleared(self):
        album = self._album(1, date(1966, 8, 5))
        refresh_release_dates()
        album.refresh_from_db()
        album.primary_wikipedia_album_data = None
        album.save()
        self.assertEqual(refresh_release_dates(), 1)
        album.refresh_from_db()
        self.assertIsNone(album.release_date)


class YearSortTests(ClearsCachesMixin, TestCase):
    """Year, then release date within it, then rank - in both directions."""

    def setUp(self):
        super().setUp()
        self.artist = models.Artist.objects.create(name="The Band", slug="band")
        # 1966, in release order: May (rank 30), August (rank 10), then the
        # undated one (rank 20). 1967 has one, to check the year still leads.
        self.august = self._album("August", 10, 1966, date(1966, 8, 5))
        self.undated = self._album("Undated", 20, 1966, None)
        self.may = self._album("May", 30, 1966, date(1966, 5, 16))
        self.later = self._album("Later", 40, 1967, date(1967, 1, 1))

    def _album(self, name, rank, year, released):
        album = models.Album.objects.create(
            name=name, rank=rank, year_released=year, release_date=released
        )
        album.artists.set([self.artist])
        return album

    def _home(self, query):
        response = self.client.get(reverse("music:home") + query)
        return [album.name for album in response.context["albums"]]

    def test_ascending_is_oldest_first_within_the_year(self):
        self.assertEqual(
            self._home("?sort=year"), ["May", "August", "Undated", "Later"]
        )

    def test_descending_is_newest_first_and_undated_stays_last(self):
        self.assertEqual(
            self._home("?sort=year&dir=desc"), ["Later", "August", "May", "Undated"]
        )

    def test_same_date_falls_back_to_rank(self):
        self._album("Same Day", 5, 1966, date(1966, 8, 5))
        self.assertEqual(
            self._home("?sort=year"),
            ["May", "Same Day", "August", "Undated", "Later"],
        )

    def test_the_artist_page_sorts_the_same_way(self):
        response = self.client.get(self.artist.get_absolute_url() + "?sort=year")
        self.assertEqual(
            [album.name for album in response.context["artist_albums"]],
            ["May", "August", "Undated", "Later"],
        )

    def test_the_csv_download_sorts_the_same_way(self):
        response = self.client.get(reverse("music:download") + "?sort=year")
        rows = list(csv.reader(response.content.decode().splitlines()))[1:]
        names = [row[2] for row in rows]
        self.assertEqual(names, ["May", "August", "Undated", "Later"])

    def test_the_payload_carries_the_date(self):
        payload = self.client.get(reverse("music-api:album-all-data")).json()
        dates = {album["n"]: album["rd"] for album in payload["albums"]}
        self.assertEqual(dates["May"], "1966-05-16")
        self.assertIsNone(dates["Undated"])


class ClientComparatorSourceTests(SimpleTestCase):
    """The browser's year sort reads `rd`, in the copy the page loads too."""

    def _source(self, path):
        return (Path(settings.BASE_DIR) / path).read_text()

    def test_the_engine_compares_release_dates_within_a_year(self):
        source = self._source("music/static/music/js/album-filter.js")
        year = source.split("year: (a, b) =>", 1)[1][:250]
        self.assertIn("_compareYears(a.y, b.y, descending)", year)
        self.assertIn("_compareReleaseDates(a.rd, b.rd, descending)", year)
        self.assertLess(year.index("_compareYears"), year.index("byRank"))

    def test_the_minified_copies_carry_it(self):
        for path in (
            "music/static/music/js/album-filter.min.js",
            "music/static/music/js/music-client-side-filtering.bundle.min.js",
        ):
            with self.subTest(path=path):
                self.assertIn("_compareReleaseDates", self._source(path))
                self.assertIn(".rd", self._source(path))

    def test_the_payload_schema_was_bumped(self):
        # A client holding a version-2 payload has no `rd` to sort by.
        self.assertGreaterEqual(data_version.SCHEMA_VERSION, 3)


class FetchCommandRefreshesDatesTests(TestCase):
    def setUp(self):
        models.Album.objects.create(name="Pet Sounds", rank=1, slug="pet-sounds")

    def _run(self, **kwargs):
        result = mock.Mock(errors=[])
        result.summary.return_value = "ok"
        service = mock.Mock()
        for name in ("run_wikidata", "run_covers", "run_discogs", "run_musicbrainz"):
            getattr(service, name).return_value = result
        out = StringIO()
        with mock.patch(
            f"{COMMAND}.AlbumMetadataService", return_value=service
        ), mock.patch(f"{COMMAND}.rebuild_album_genres"), mock.patch(
            f"{COMMAND}.write_report"
        ), mock.patch(
            f"{COMMAND}.refresh_release_dates", return_value=7
        ) as refresh:
            call_command("fetch_album_metadata", stdout=out, **kwargs)
        return refresh, out.getvalue()

    def test_a_musicbrainz_run_refreshes_dates(self):
        refresh, output = self._run(musicbrainz=True)
        refresh.assert_called_once_with()
        self.assertIn("Release dates: 7 updated", output)

    def test_a_covers_run_does_not(self):
        refresh, _ = self._run(covers_only=True)
        refresh.assert_not_called()


class ReleaseDateLabelTests(SimpleTestCase):
    """The artist page's date, never more precise than what is known."""

    def _label(self, released, precision, year=1966):
        album = models.Album(
            year_released=year, release_date=released, release_date_precision=precision
        )
        return release_date_label(album)

    def test_a_day(self):
        self.assertEqual(self._label(date(1966, 5, 16), "day"), "May 16, 1966")

    def test_a_month_or_an_unknown_precision_shows_the_month(self):
        for precision in ("month", ""):
            with self.subTest(precision=precision):
                self.assertEqual(self._label(date(1966, 5, 1), precision), "May 1966")

    def test_undated_shows_the_year(self):
        self.assertEqual(self._label(None, ""), 1966)

    def test_a_date_in_another_year_shows_the_published_year(self):
        self.assertEqual(self._label(date(1965, 12, 3), "day"), 1966)


class ArtistPageShowsReleaseDatesTests(ClearsCachesMixin, TestCase):
    def test_rows_carry_the_full_date_where_known(self):
        artist = models.Artist.objects.create(name="The Band", slug="band")
        for name, rank, released, precision in (
            ("Day", 1, date(1966, 5, 16), "day"),
            ("Month", 2, date(1967, 6, 1), "month"),
            ("Undated", 3, None, ""),
        ):
            album = models.Album.objects.create(
                name=name,
                rank=rank,
                year_released=released.year if released else 1968,
                release_date=released,
                release_date_precision=precision,
            )
            album.artists.set([artist])
        response = self.client.get(artist.get_absolute_url())
        self.assertContains(response, "May 16, 1966", count=2)  # both row halves
        self.assertContains(response, "June 1967", count=2)
        self.assertNotContains(response, "June 1, 1967")
        self.assertContains(response, "(1968)", count=1)  # mobile half
