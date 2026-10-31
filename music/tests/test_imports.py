"""Tests for the music import handler.

The importers are driven with StringIO rather than files, matching
``games/tests/test_imports.py``. The real release files in
``acclaimedgames/test_input_files/music/`` back the end-to-end test.
"""

from contextlib import ExitStack
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core import constants as core_constants
from core.models import User
from music import config, models
from music.services import caching, import_handler
from django.core.cache import cache
from django.urls import reverse
from games.models import SiteMetadata
from music.tests.test_views import ClearsCachesMixin
from music.tests.site import setUpModule, tearDownModule  # noqa: F401

FIXTURE_DIR = Path(settings.BASE_DIR) / "acclaimedgames" / "test_input_files" / "music"

LISTS_TSV = (
    "Rolling Stone\t2023\tAll Time\tThe 500 Greatest Albums of All Time\t"
    "https://rs.example\n"
    "Pitchfork\t2022\tDecade\tThe 150 Best Albums of the 1990s\thttps://pf.example\n"
    "Spin\t2010\tMisc\t125 Best Albums of the Past 25 Years\t\n"
)

# Shaped like the real ArtistInfo.txt: sparse provider ids, Wikidata ids
# without their "Q" (as the 2026-10-28 release has them; the next is to
# carry it, and both are read), an artist with none, and artists with
# several names - Neil Young's third used by no album here.
ARTISTS_TSV = (
    "3\t183048\tThe Beach Boys\n"
    "56\t633,951532\tNeil Young\tNeil Young & Crazy Horse\t"
    "Neil Young & the Stray Gators\n"
    "113\tQ214567,Q10461933\tCrosby, Stills & Nash\tCrosby, Stills, Nash & Young\n"
    "192\t\tCrazy Horse\n"
)

# Credits are `artist,variant` pairs separated by ";", VA last.
ALBUMS_TSV = (
    "1\tPet Sounds\t3,0\t1966\tQ212863\n"
    "2\tDéjà Vu\t113,1\t1970\tQ1136782\n"
    "3\tRust Never Sleeps\t56,1\t1979\tQ1140313,Q999999\n"
)

POSITIONS_TSV = "0:2\t1:5\n0:1\t2:9\n0:3\n"

# The next release: Pet Sounds is dropped and the rest move up.
SHORTER_ALBUMS_TSV = (
    "1\tDéjà Vu\t113,1\t1970\tQ1136782\n"
    "2\tRust Never Sleeps\t56,1\t1979\tQ1140313,Q999999\n"
)
SHORTER_POSITIONS_TSV = "0:1\t2:9\n0:3\n"


def import_artists(tsv=ARTISTS_TSV):
    return import_handler.import_artists(StringIO(tsv))


def import_release(**overrides):
    """``import_batch`` over the inline fixtures, any of them replaced."""
    files = {
        "lists_file": LISTS_TSV,
        "albums_file": ALBUMS_TSV,
        "positions_file": POSITIONS_TSV,
        "artists_file": ARTISTS_TSV,
    }
    files.update(overrides)
    return import_handler.import_batch(
        **{name: StringIO(text) for name, text in files.items()}
    )


class ListTypeColumnTests(TestCase):
    """Column 3 of the lists file is the type, in the games file's words."""

    def _types(self, *cells):
        tsv = "".join(
            f"Mojo\t1995\t{cell}\tList {i}\t\n" for i, cell in enumerate(cells)
        )
        return [row.type for row in import_handler.parse_lists_file(StringIO(tsv))]

    def test_the_games_words_map_to_the_shared_codes(self):
        self.assertEqual(
            self._types("All Time", "Decade", "EOY", "Misc"),
            [
                core_constants.LIST_ALLTIME,
                core_constants.LIST_DECADE,
                core_constants.LIST_EOY,
                core_constants.LIST_MISC,
            ],
        )

    def test_spelling_variants_and_bare_codes_are_read(self):
        self.assertEqual(
            self._types("all-time", " ALL  TIME ", "End of Year", "miscellaneous", "d"),
            [
                core_constants.LIST_ALLTIME,
                core_constants.LIST_ALLTIME,
                core_constants.LIST_EOY,
                core_constants.LIST_MISC,
                core_constants.LIST_DECADE,
            ],
        )

    def test_an_unknown_type_fails_with_its_row_number(self):
        # Games' importer would store "F" for this; nobody chose that.
        with self.assertRaises(ValueError) as ctx:
            self._types("Decade", "Fortnightly")
        self.assertIn("Lists row 2", str(ctx.exception))
        self.assertIn("'Fortnightly'", str(ctx.exception))

    def test_a_file_without_the_type_column_is_named_as_such(self):
        with self.assertRaises(ValueError) as ctx:
            import_handler.parse_lists_file(
                StringIO("Mojo\t1995\tThe 100 Greatest Albums\thttps://m.example\n")
            )
        self.assertIn("before list types", str(ctx.exception))

    def test_the_title_no_longer_decides_the_type(self):
        # The title inference this replaced filed this as all-time.
        rows = import_handler.parse_lists_file(
            StringIO("AllMusic\t2019\tDecade\tThe AllMusic Decade in Review\t\n")
        )
        self.assertEqual(rows[0].type, core_constants.LIST_DECADE)
        self.assertEqual(rows[0].name, "The AllMusic Decade in Review")

    def test_every_real_list_names_a_known_type(self):
        with (FIXTURE_DIR / "ListData.txt").open(encoding="utf-8-sig", newline="") as f:
            rows = import_handler.parse_lists_file(f)
        self.assertEqual(len(rows), len(_read_fixture_rows("ListData.txt")))
        self.assertEqual(
            {row.type for row in rows} - set(dict(core_constants.LIST_TYPES)), set()
        )


class NormalizeArtistNameTests(TestCase):
    def test_ampersand_and_the_are_collapsed(self):
        self.assertEqual(
            import_handler.normalize_artist_name("Bob Marley & The Wailers"),
            import_handler.normalize_artist_name("Bob Marley and the Wailers"),
        )

    def test_different_acts_do_not_collapse(self):
        self.assertNotEqual(
            import_handler.normalize_artist_name("Jimi Hendrix"),
            import_handler.normalize_artist_name("The Jimi Hendrix Experience"),
        )


class ImportArtistsTests(TestCase):
    def test_creates_every_artist_under_its_provider_id(self):
        success, message = import_artists()
        self.assertTrue(success)
        self.assertIn("Artists: 4 (4 new, 0 removed), 3 name variants", message)
        young = models.Artist.objects.get(source_id=56)
        self.assertEqual(young.name, "Neil Young")
        self.assertEqual(young.slug, "neil-young")
        self.assertIsNone(models.Artist.objects.get(source_id=192).wikidata_id)

    def test_wikidata_ids_are_read_with_or_without_their_q(self):
        import_artists()
        young = models.Artist.objects.get(source_id=56)
        self.assertEqual(young.wikidata_id, "Q633")
        self.assertEqual(young.all_wikidata_ids, ["Q633", "Q951532"])
        csn = models.Artist.objects.get(source_id=113)
        self.assertEqual(csn.all_wikidata_ids, ["Q214567", "Q10461933"])
        self.assertEqual(models.Artist.objects.get(source_id=192).all_wikidata_ids, [])

    def test_a_repeated_or_lowercase_qid_is_kept_once(self):
        import_artists("1\tq5, Q5 ,7\tA\n")
        self.assertEqual(
            models.Artist.objects.get(source_id=1).all_wikidata_ids, ["Q5", "Q7"]
        )

    def test_every_name_is_kept_in_file_order(self):
        import_artists()
        self.assertEqual(
            models.Artist.objects.get(source_id=56).name_variants,
            [
                "Neil Young",
                "Neil Young & Crazy Horse",
                "Neil Young & the Stray Gators",
            ],
        )
        self.assertEqual(
            models.Artist.objects.get(source_id=3).name_variants, ["The Beach Boys"]
        )

    def test_trailing_blank_names_are_dropped_and_inner_ones_keep_their_place(self):
        # A variant is an index, so a blank inside the list must hold it.
        import_artists("1\t5\tA\t\tC\t\t\n")
        self.assertEqual(
            models.Artist.objects.get(source_id=1).name_variants, ["A", "", "C"]
        )

    def test_a_reimport_keeps_every_pk_and_slug(self):
        import_artists()
        before = dict(models.Artist.objects.values_list("source_id", "pk"))
        success, message = import_artists()
        self.assertIn("(0 new, 0 removed)", message)
        self.assertEqual(
            dict(models.Artist.objects.values_list("source_id", "pk")), before
        )

    def test_a_renamed_artist_gets_the_new_names_slug(self):
        import_artists()
        horse = models.Artist.objects.get(source_id=192)
        import_artists(ARTISTS_TSV.replace("\tCrazy Horse\n", "\tCrazy Horse (band)\n"))
        renamed = models.Artist.objects.get(source_id=192)
        self.assertEqual(renamed.pk, horse.pk)
        self.assertEqual(renamed.name, "Crazy Horse (band)")
        self.assertEqual(renamed.slug, "crazy-horse-band")

    def test_a_slug_edited_by_hand_is_rebuilt(self):
        import_artists()
        models.Artist.objects.filter(source_id=3).update(slug="beach-boys-old")
        import_artists()
        self.assertEqual(models.Artist.objects.get(source_id=3).slug, "the-beach-boys")

    def test_a_re_keyed_artist_is_not_slugged_by_its_old_title(self):
        import_artists("1\t5\tNirvana\n2\t7\tNirvana\n")
        models.Artist.objects.filter(source_id=2).update(wikipedia_title="Nirvana")
        models.Artist.objects.filter(source_id=1).update(
            wikipedia_title="Nirvana (British band)"
        )
        self.assertEqual(
            import_handler.plan_import_slugs(
                import_handler.parse_artists_file(
                    StringIO("1\t5\tNirvana\n2\t7\tNirvana\n")
                )
            ),
            {2: "nirvana", 1: "nirvana-british-band"},
        )
        # Artist 2 now points at another entity, so the bare-name title is
        # not its own; with no primary topic the lowest id keeps "nirvana".
        rekeyed = "1\t5\tNirvana\n2\t8\tNirvana\n"
        self.assertEqual(
            import_handler.plan_import_slugs(
                import_handler.parse_artists_file(StringIO(rekeyed))
            ),
            {1: "nirvana", 2: "nirvana-2"},
        )

    def test_a_changed_qid_drops_the_old_musicbrainz_id_and_title(self):
        import_artists()
        models.Artist.objects.filter(source_id__in=[56, 3]).update(
            musicbrainz_id="mb", wikipedia_title="Old title"
        )
        import_artists(ARTISTS_TSV.replace("633,", "634,"))
        changed = models.Artist.objects.get(source_id=56)
        self.assertEqual((changed.musicbrainz_id, changed.wikipedia_title), (None, ""))
        kept = models.Artist.objects.get(source_id=3)
        self.assertEqual(
            (kept.musicbrainz_id, kept.wikipedia_title), ("mb", "Old title")
        )

    def test_an_existing_artist_is_adopted_by_any_of_its_qids(self):
        # Rows from the credit-guessing imports carry no source id; matching
        # them keeps their pk, so links and filters keep working.
        old = models.Artist.objects.create(
            name="Neil Young (old spelling)", slug="neil-young", wikidata_id="Q951532"
        )
        import_artists()
        adopted = models.Artist.objects.get(source_id=56)
        self.assertEqual(adopted.pk, old.pk)
        self.assertEqual(adopted.name, "Neil Young")
        self.assertEqual(adopted.slug, "neil-young")

    def test_an_existing_artist_is_adopted_by_a_secondary_qid(self):
        old = models.Artist.objects.create(
            name="CSN (renamed)",
            slug="csn",
            wikidata_id="Q999",
            all_wikidata_ids=["Q999", "Q10461933"],
        )
        import_artists()
        self.assertEqual(models.Artist.objects.get(source_id=113).pk, old.pk)

    def test_an_existing_artist_is_adopted_by_name(self):
        old = models.Artist.objects.create(name="Crazy Horse", slug="horse")
        import_artists()
        self.assertEqual(models.Artist.objects.get(source_id=192).pk, old.pk)

    def test_an_existing_artist_is_adopted_by_a_normalized_name(self):
        old = models.Artist.objects.create(name="Crosby Stills and Nash", slug="csn")
        import_artists()
        self.assertEqual(models.Artist.objects.get(source_id=113).pk, old.pk)

    def test_an_adopted_artist_takes_the_slug_of_its_name(self):
        old = models.Artist.objects.create(name="Crazy Horse", slug="horse")
        import_artists()
        adopted = models.Artist.objects.get(source_id=192)
        self.assertEqual((adopted.pk, adopted.slug), (old.pk, "crazy-horse"))

    def test_artists_the_file_does_not_list_are_removed(self):
        models.Artist.objects.create(name="Guessed From A Credit", slug="guessed")
        import_artists()
        _, message = import_artists(ARTISTS_TSV.replace("192\t\tCrazy Horse\n", ""))
        self.assertIn("1 removed", message)
        self.assertFalse(
            models.Artist.objects.filter(name="Guessed From A Credit").exists()
        )
        self.assertFalse(models.Artist.objects.filter(source_id=192).exists())

    def test_same_named_artists_are_numbered_by_provider_id(self):
        # Whatever order the rows come in, the lowest id has the plain slug.
        for tsv in ("90\t\tNirvana\n12\t\tNirvana\n", "12\t\tNirvana\n90\t\tNirvana\n"):
            with self.subTest(tsv=tsv):
                import_artists(tsv)
                self.assertEqual(
                    dict(models.Artist.objects.values_list("source_id", "slug")),
                    {12: "nirvana", 90: "nirvana-2"},
                )

    def test_a_tail_never_takes_another_artists_own_slug(self):
        import_artists("1\t\tNico\n2\t\tNico\n3\t\tNico 2\n")
        self.assertEqual(
            dict(models.Artist.objects.values_list("source_id", "slug")),
            {1: "nico", 2: "nico-3", 3: "nico-2"},
        )

    def test_a_long_transliterated_name_fits_the_slug_column(self):
        import_artists("1\t\t" + "\u6771\u4eac\u4e8b\u5909" * 20 + "\n")
        slug = models.Artist.objects.get(source_id=1).slug
        self.assertLessEqual(len(slug), 200)
        self.assertFalse(slug.endswith("-"))

    def test_names_are_transliterated_before_slugifying(self):
        import_artists(
            "1\t\tR\u00f8yksopp\n2\t\t\u30b5\u30ab\u30ca\u30af\u30b7\u30e7\u30f3\n"
            "3\t\t!!!\n"
        )
        self.assertEqual(
            dict(models.Artist.objects.values_list("source_id", "slug")),
            {1: "royksopp", 2: "sakanakushiyon", 3: "artist"},
        )

    def test_progress_callback_receives_each_stage(self):
        events = []
        import_handler.import_artists(
            StringIO(ARTISTS_TSV), lambda name, data: events.append((name, data))
        )
        names = [name for name, _ in events]
        self.assertEqual(names[0], "start")
        self.assertEqual(names[-1], "complete")
        self.assertEqual(names.count("progress"), 4)
        self.assertEqual(dict(events)["complete"]["variants"], 3)

    def test_an_id_given_to_a_different_act_is_flagged(self):
        import_artists()
        _, message = import_artists(
            ARTISTS_TSV.replace("192\t\tCrazy Horse\n", "192\t999\tSun Ra\n")
        )
        self.assertIn("WARNING: 1 artist id(s) may have been reused", message)
        self.assertIn("192 'Crazy Horse' -> 'Sun Ra'", message)

    def test_a_rename_that_keeps_an_id_or_a_name_is_not_flagged(self):
        import_artists()
        renamed = ARTISTS_TSV.replace("633,951532\tNeil Young", "633\tShakey").replace(
            "\tCrazy Horse\n", "\tThe Crazy Horse\n"
        )
        _, message = import_artists(renamed)
        self.assertNotIn("WARNING", message)
        self.assertEqual(
            import_handler.suspected_reuses(
                import_handler.parse_artists_file(StringIO(renamed))
            ),
            [],
        )

    def test_a_bad_file_is_rejected_before_anything_is_written(self):
        for tsv, expected in (
            ("1\t5\n", "expected at least 3"),
            ("x\t5\tNobody\n", "is not a number"),
            ("1\t5\tA\n1\t6\tB\n", "appears twice"),
            ("1\t5\t \n", "has no name"),
            # The pre-2026-10-28 layout: name second, then tags, then the QID.
            ("1\tThe Beatles\t\tQ1299\n", "pre-2026-10-28"),
            ("1\t5;6\tA\n", "column 2 should be Wikidata ids"),
        ):
            with self.subTest(tsv=tsv):
                with self.assertRaises(ValueError) as ctx:
                    import_artists(tsv)
                self.assertIn(expected, str(ctx.exception))
                self.assertFalse(models.Artist.objects.exists())


class ImportListsTests(TestCase):
    def test_creates_publications_and_lists_with_their_types(self):
        success, message = import_handler.import_lists(StringIO(LISTS_TSV))
        self.assertTrue(success)
        self.assertIn("Lists: 3 created", message)
        self.assertEqual(models.MusicList.objects.count(), 3)
        self.assertEqual(models.MusicPublication.objects.count(), 3)

        first = models.MusicList.objects.get(order=1)
        self.assertEqual(first.type, core_constants.LIST_ALLTIME)
        self.assertEqual(first.publisher.name, "Rolling Stone")
        self.assertEqual(first.url, "https://rs.example")

        second = models.MusicList.objects.get(order=2)
        self.assertEqual(second.type, core_constants.LIST_DECADE)

        third = models.MusicList.objects.get(order=3)
        self.assertEqual(third.type, core_constants.LIST_MISC)

    def test_order_is_the_one_based_row_number(self):
        import_handler.import_lists(StringIO(LISTS_TSV))
        self.assertEqual(
            list(
                models.MusicList.objects.order_by("order").values_list(
                    "order", flat=True
                )
            ),
            [1, 2, 3],
        )

    def test_a_blank_url_is_stored_as_null(self):
        import_handler.import_lists(StringIO(LISTS_TSV))
        self.assertIsNone(models.MusicList.objects.get(order=3).url)

    def test_a_missing_url_column_is_tolerated(self):
        import_handler.import_lists(
            StringIO("Mojo\t1995\tAll Time\tThe 100 Greatest Albums\n")
        )
        self.assertIsNone(models.MusicList.objects.get(order=1).url)

    def test_reimporting_replaces_the_previous_lists(self):
        import_handler.import_lists(StringIO(LISTS_TSV))
        success, message = import_handler.import_lists(StringIO(LISTS_TSV))
        self.assertTrue(success)
        self.assertIn("deleted 3 old", message)
        self.assertEqual(models.MusicList.objects.count(), 3)

    def test_one_publication_is_reused_across_its_lists(self):
        tsv = (
            "Pitchfork\t2022\tDecade\tThe 150 Best Albums of the 1990s\t\n"
            "Pitchfork\t2019\tDecade\tThe 200 Best Albums of the 2010s\t\n"
        )
        import_handler.import_lists(StringIO(tsv))
        self.assertEqual(models.MusicPublication.objects.count(), 1)
        self.assertEqual(models.MusicList.objects.count(), 2)

    def test_blank_rows_are_skipped(self):
        import_handler.import_lists(StringIO(LISTS_TSV + "\n\n"))
        self.assertEqual(models.MusicList.objects.count(), 3)

    def test_a_short_row_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            import_handler.import_lists(StringIO("Mojo\t1995\tDecade\n"))
        self.assertIn("expected at least 4", str(ctx.exception))

    def test_progress_callback_receives_each_stage(self):
        events = []
        import_handler.import_lists(
            StringIO(LISTS_TSV), lambda name, data: events.append((name, data))
        )
        names = [name for name, _ in events]
        self.assertEqual(names[0], "start")
        self.assertEqual(names[-1], "complete")
        self.assertEqual(names.count("progress"), 3)
        self.assertEqual(len(dict(events)["complete"]["types"]), 3)


class ImportAlbumsTests(TestCase):
    def setUp(self):
        import_artists()

    def test_creates_albums_artists_and_derived_ranks(self):
        message, _ = import_handler.import_albums(StringIO(ALBUMS_TSV))
        self.assertIn("Albums: 3 (0 kept, 3 added, 0 removed)", message)
        self.assertIn("3 ranks calculated", message)
        self.assertEqual(models.Album.objects.count(), 3)

        album = models.Album.objects.get(rank=1)
        self.assertEqual(album.name, "Pet Sounds")
        self.assertEqual(album.artist_credit, "The Beach Boys")
        self.assertEqual([a.source_id for a in album.credited_artists], [3])
        self.assertEqual(album.year_released, 1966)
        self.assertEqual(album.wikidata_id, "Q212863")
        self.assertEqual(album.all_wikidata_ids, ["Q212863"])
        self.assertEqual(album.year_rank, 1)
        self.assertEqual(album.decade_rank, 1)

    def test_a_credit_under_another_name_belongs_to_the_artist(self):
        import_handler.import_albums(StringIO(ALBUMS_TSV))
        album = models.Album.objects.get(rank=2)
        self.assertEqual(
            [a.name for a in album.credited_artists], ["Crosby, Stills & Nash"]
        )
        credit = album.credits.get()
        self.assertEqual(credit.variant, 1)
        self.assertEqual(credit.credited_name, "Crosby, Stills, Nash & Young")
        self.assertEqual(album.artist_credit, "Crosby, Stills, Nash & Young")
        self.assertFalse(album.various_artists)

    def test_a_default_credit_leaves_the_name_to_the_artist(self):
        # Blank, so an artist renamed in the admin is credited by the new
        # name rather than keeping a stale copy of the old one.
        import_handler.import_albums(StringIO(ALBUMS_TSV))
        credit = models.Album.objects.get(rank=1).credits.get()
        self.assertEqual((credit.variant, credit.credited_name), (0, ""))
        self.assertEqual(credit.name, "The Beach Boys")
        models.Artist.objects.filter(source_id=3).update(name="Beach Boys")
        credit = models.Album.objects.get(rank=1).credits.get()
        self.assertEqual(credit.name, "Beach Boys")
        self.assertFalse(credit.uses_variant)

    def test_various_artists_after_a_named_artist(self):
        import_handler.import_albums(
            StringIO("1\tThe Harder They Come\t56,0;VA\t1972\tQ937034\n")
        )
        album = models.Album.objects.get(rank=1)
        self.assertEqual(album.artist_credit, "Neil Young & Various Artists")
        self.assertTrue(album.various_artists)
        self.assertEqual([a.source_id for a in album.credited_artists], [56])

    def test_several_artists_keep_the_files_order_in_the_credit(self):
        import_handler.import_albums(StringIO("1\tTogether\t192,0;56,0;3,0\t1990\n"))
        album = models.Album.objects.get(rank=1)
        self.assertEqual(
            [a.name for a in album.credited_artists],
            ["Crazy Horse", "Neil Young", "The Beach Boys"],
        )
        self.assertEqual(
            album.artist_credit, "Crazy Horse, Neil Young & The Beach Boys"
        )

    def test_two_artists_are_joined_with_an_ampersand(self):
        import_handler.import_albums(StringIO("1\tTogether\t56,0;192,0\t1990\n"))
        self.assertEqual(
            models.Album.objects.get(rank=1).artist_credit, "Neil Young & Crazy Horse"
        )

    def test_a_repeated_id_is_credited_once(self):
        import_handler.import_albums(StringIO("1\tTwice\t56,0;56,0\t1990\n"))
        self.assertEqual(models.AlbumCredit.objects.count(), 1)

    def test_va_must_be_the_last_credit(self):
        for credits in ("VA;56,0", "56,0;VA;3,0"):
            with self.subTest(credits=credits):
                with self.assertRaises(ValueError) as ctx:
                    import_handler.import_albums(StringIO(f"1\tX\t{credits}\t1972\n"))
                self.assertIn("VA must be the last credit", str(ctx.exception))

    def test_va_alone_is_a_compilation(self):
        import_handler.import_albums(StringIO("1\tNuggets\tva\t1972\tQ744572\n"))
        album = models.Album.objects.get(rank=1)
        self.assertEqual(album.artist_credit, "Various Artists")
        self.assertTrue(album.various_artists)
        self.assertEqual(album.credited_artists, [])

    def test_a_blank_credit_is_rejected(self):
        # The old encoding of a compilation; the new one says VA.
        with self.assertRaises(ValueError) as ctx:
            import_handler.import_albums(StringIO("1\tNuggets\t\t1972\tQ744572\n"))
        self.assertIn("credits nobody", str(ctx.exception))

    def test_a_quoted_title_keeps_its_quotes(self):
        import_handler.import_albums(StringIO('1\t"Heroes"\t3,0\t1977\tQ595352\n'))
        self.assertEqual(models.Album.objects.get(rank=1).name, '"Heroes"')

    def test_an_old_format_credit_is_rejected_by_name(self):
        for credits in ("The Beach Boys", "3"):
            with self.subTest(credits=credits):
                with self.assertRaises(ValueError) as ctx:
                    import_handler.import_albums(
                        StringIO(f"1\tPet Sounds\t{credits}\t1966\tQ212863\n")
                    )
                self.assertIn("pre-2026-10-28", str(ctx.exception))

    def test_a_variant_the_artist_does_not_have_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            import_handler.import_albums(StringIO("1\tPet Sounds\t3,1\t1966\n"))
        self.assertIn("as name 1", str(ctx.exception))
        self.assertIn("gives it 1 name(s)", str(ctx.exception))

    def test_a_blank_variant_is_rejected(self):
        import_artists("1\t5\tA\t\tC\n")
        with self.assertRaises(ValueError) as ctx:
            import_handler.import_albums(StringIO("1\tX\t1,1\t1966\n"))
        self.assertIn("as name 1", str(ctx.exception))

    def test_an_unknown_artist_id_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            import_handler.import_albums(StringIO("1\tPet Sounds\t999,0\t1966\n"))
        self.assertIn("credits artist 999", str(ctx.exception))

    def test_the_first_wikidata_id_is_primary_and_the_rest_are_kept(self):
        import_handler.import_albums(StringIO(ALBUMS_TSV))
        album = models.Album.objects.get(rank=3)
        self.assertEqual(album.wikidata_id, "Q1140313")
        self.assertEqual(album.all_wikidata_ids, ["Q1140313", "Q999999"])

    def test_a_missing_wikidata_column_is_tolerated(self):
        import_handler.import_albums(StringIO("1\tUntitled\t3,0\t1999\n"))
        album = models.Album.objects.get(rank=1)
        self.assertIsNone(album.wikidata_id)
        self.assertEqual(album.all_wikidata_ids, [])

    def test_a_blank_year_is_stored_as_null(self):
        import_handler.import_albums(StringIO("1\tUndated\t3,0\t\tQ1\n"))
        self.assertIsNone(models.Album.objects.get(rank=1).year_released)

    def test_a_title_collision_is_disambiguated_by_the_credit(self):
        import_handler.import_albums(
            StringIO("1\tHarvest\t56,0\t1972\n2\tHarvest\t3,0\t1980\n")
        )
        self.assertEqual(
            models.Album.objects.get(rank=2).slug, "harvest-the-beach-boys"
        )

    def test_a_short_row_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            import_handler.import_albums(StringIO("1\tPet Sounds\n"))
        self.assertIn("expected at least 4", str(ctx.exception))

    def test_progress_callback_receives_each_stage(self):
        events = []
        import_handler.import_albums(
            StringIO(ALBUMS_TSV), lambda name, data: events.append((name, data))
        )
        names = [name for name, _ in events]
        self.assertEqual(names[0], "start")
        self.assertEqual(names[-1], "complete")
        complete = dict(events)["complete"]
        self.assertEqual(complete["count"], 3)
        self.assertEqual(
            (complete["kept"], complete["added"], complete["removed"]), (0, 3, 0)
        )


class ImportAlbumsInPlaceTests(TestCase):
    """A re-import updates albums in place rather than replacing them.

    Everything hung off an album - its metadata rows, genres, release date,
    covers, tracking rows - is keyed on its pk, so keeping the pk is what
    spares a new release a full metadata refresh.
    """

    def setUp(self):
        import_artists()
        import_handler.import_albums(StringIO(ALBUMS_TSV))
        self.pet_sounds = models.Album.objects.get(wikidata_id="Q212863")

    def reimport(self, tsv=ALBUMS_TSV):
        return import_handler.import_albums(StringIO(tsv))

    def test_a_reimport_keeps_every_pk_and_slug(self):
        before = dict(models.Album.objects.values_list("wikidata_id", "pk"))
        slugs = set(models.Album.objects.values_list("slug", flat=True))
        message, _ = self.reimport()
        self.assertIn("Albums: 3 (3 kept, 0 added, 0 removed)", message)
        self.assertEqual(
            dict(models.Album.objects.values_list("wikidata_id", "pk")), before
        )
        self.assertEqual(
            set(models.Album.objects.values_list("slug", flat=True)), slugs
        )
        self.assertEqual(models.AlbumCredit.objects.count(), 3)

    def test_metadata_genres_and_covers_stay_attached(self):
        album = self.pet_sounds
        genre = models.MusicGenre.objects.create(name="Rock")
        album.genres.add(genre)
        wikipedia = models.WikipediaAlbumData.objects.create(
            album=album, wikidata_id=album.wikidata_id, is_primary=True
        )
        discogs = models.DiscogsAlbumData.objects.create(
            album=album, master_id=12345, is_primary=True
        )
        musicbrainz = models.MusicBrainzAlbumData.objects.create(
            album=album,
            release_group_mbid="rg-1",
            cover_art_release_mbid="rel-1",
            cover_art_image_id="1",
            cover_art_stored=True,
            is_primary=True,
        )
        cover = models.AlbumCover.objects.create(
            album=album, release_mbid="rel-1", image_id="1", size=250, data=b"x"
        )
        album.primary_wikipedia_album_data = wikipedia
        album.primary_discogs_album_data = discogs
        album.primary_musicbrainz_album_data = musicbrainz
        album.musicbrainz_release_group_id = "rg-1"
        album.discogs_master_id = 12345
        album.cover_image_url = "https://coverartarchive.org/x.jpg"
        album.release_date = date(1966, 5, 16)
        album.release_date_precision = "day"
        album.save()

        self.reimport()

        album = models.Album.objects.get(pk=album.pk)
        self.assertEqual(list(album.genres.all()), [genre])
        self.assertEqual(album.primary_wikipedia_album_data, wikipedia)
        self.assertEqual(album.primary_discogs_album_data, discogs)
        self.assertEqual(album.primary_musicbrainz_album_data, musicbrainz)
        self.assertEqual(album.musicbrainz_release_group_id, "rg-1")
        self.assertEqual(album.discogs_master_id, 12345)
        self.assertEqual(album.cover_image_url, "https://coverartarchive.org/x.jpg")
        self.assertEqual(album.release_date, date(1966, 5, 16))
        self.assertEqual(album.release_date_precision, "day")
        cover.refresh_from_db()
        self.assertEqual(cover.album, album)

    def test_the_file_updates_rank_name_year_and_credits(self):
        self.reimport(
            "1\tRust Never Sleeps\t56,1\t1979\tQ1140313\n"
            "2\tPet Sounds (Mono)\t56,0;3,0\t1970\tQ212863\n"
            "3\tDéjà Vu\t113,1\t1970\tQ1136782\n"
        )
        album = models.Album.objects.get(pk=self.pet_sounds.pk)
        self.assertEqual(album.rank, 2)
        self.assertEqual(album.name, "Pet Sounds (Mono)")
        self.assertEqual(album.year_released, 1970)
        self.assertEqual(album.artist_credit, "Neil Young & The Beach Boys")
        self.assertEqual([a.source_id for a in album.credited_artists], [56, 3])
        rust = models.Album.objects.get(wikidata_id="Q1140313")
        self.assertEqual(rust.artist_credit, "Neil Young & Crazy Horse")
        # Recomputed from the new ranks and years: second in the 1970s behind
        # Rust Never Sleeps, first in 1970 ahead of Deja Vu.
        self.assertEqual(album.year_rank, 1)
        self.assertEqual(album.decade_rank, 2)

    def test_a_renamed_album_keeps_its_slug(self):
        self.reimport(ALBUMS_TSV.replace("Pet Sounds", "Pet Sounds (Remastered)"))
        album = models.Album.objects.get(pk=self.pet_sounds.pk)
        self.assertEqual(album.slug, self.pet_sounds.slug)
        self.assertEqual(album.name, "Pet Sounds (Remastered)")

    def test_a_rename_recomputes_the_normalized_name(self):
        deja_vu = models.Album.objects.get(wikidata_id="Q1136782")
        self.assertEqual(deja_vu.name_normalized, "Deja Vu")
        self.reimport(ALBUMS_TSV.replace("Déjà Vu", "Deja Vu"))
        deja_vu.refresh_from_db()
        self.assertIsNone(deja_vu.name_normalized)
        self.reimport()
        deja_vu.refresh_from_db()
        self.assertEqual(deja_vu.name_normalized, "Deja Vu")

    def test_an_album_is_matched_on_a_secondary_id(self):
        rust = models.Album.objects.get(wikidata_id="Q1140313")
        self.reimport(ALBUMS_TSV.replace("Q1140313,Q999999", "Q999999"))
        album = models.Album.objects.get(pk=rust.pk)
        self.assertEqual(album.wikidata_id, "Q999999")
        self.assertEqual(album.all_wikidata_ids, ["Q999999"])

    def test_an_album_gaining_an_id_is_still_matched(self):
        self.reimport(ALBUMS_TSV.replace("Q212863", "Q42,Q212863"))
        album = models.Album.objects.get(pk=self.pet_sounds.pk)
        self.assertEqual(album.wikidata_id, "Q42")

    def test_dropped_albums_are_removed_and_new_ones_added(self):
        message, _ = self.reimport(
            "1\tPet Sounds\t3,0\t1966\tQ212863\n" "2\tHarvest\t56,0\t1972\tQ1191683\n"
        )
        self.assertIn("Albums: 2 (1 kept, 1 added, 2 removed)", message)
        self.assertEqual(
            set(models.Album.objects.values_list("name", flat=True)),
            {"Pet Sounds", "Harvest"},
        )
        self.assertEqual(models.Album.objects.get(name="Pet Sounds"), self.pet_sounds)
        self.assertEqual(models.AlbumCredit.objects.count(), 2)

    def test_a_removed_albums_slug_is_free_for_a_new_one(self):
        # Same title, a different album: the old row goes before the new one
        # is slugged, so it takes the plain slug rather than a numeric tail.
        self.reimport("1\tPet Sounds\t56,0\t1990\tQ1\n")
        self.assertEqual(models.Album.objects.get().slug, "pet-sounds")

    def test_one_album_is_claimed_by_one_row(self):
        message, _ = self.reimport(
            "1\tPet Sounds\t3,0\t1966\tQ212863\n"
            "2\tPet Sounds (Stereo)\t3,0\t1966\tQ212863\n"
        )
        self.assertIn("(1 kept, 1 added, 2 removed)", message)
        self.assertEqual(
            models.Album.objects.get(pk=self.pet_sounds.pk).name, "Pet Sounds"
        )
        self.assertEqual(models.Album.objects.count(), 2)

    def test_a_row_without_a_wikidata_id_is_always_new(self):
        self.reimport("1\tUntitled\t3,0\t1999\n")
        album = models.Album.objects.get()
        message, _ = self.reimport("1\tUntitled\t3,0\t1999\n")
        self.assertIn("(0 kept, 1 added, 1 removed)", message)
        self.assertNotEqual(models.Album.objects.get().pk, album.pk)


class MatchAlbumsTests(TestCase):
    """The matching on its own, which ``--dry-run`` reports without writing."""

    def row(self, *wikidata_ids, name="X"):
        return import_handler.AlbumRow(
            rank=1,
            name=name,
            credits=[],
            various_artists=False,
            year=None,
            wikidata_ids=list(wikidata_ids),
        )

    def test_the_primary_id_is_tried_first(self):
        first = models.Album.objects.create(name="A", rank=1, wikidata_id="Q1")
        models.Album.objects.create(name="B", rank=2, wikidata_id="Q2")
        match = import_handler.match_albums(
            [self.row("Q1", "Q2")], list(models.Album.objects.all())
        )
        self.assertEqual(match.kept[0][1], first)
        self.assertEqual([a.name for a in match.removed], ["B"])

    def test_a_claimed_album_falls_through_to_the_next_id(self):
        first = models.Album.objects.create(name="A", rank=1, wikidata_id="Q1")
        second = models.Album.objects.create(name="B", rank=2, wikidata_id="Q2")
        match = import_handler.match_albums(
            [self.row("Q1"), self.row("Q1", "Q2")], list(models.Album.objects.all())
        )
        self.assertEqual([album for _, album in match.kept], [first, second])
        self.assertEqual(match.added, [])
        self.assertEqual(match.removed, [])


class ImportMusicDataCommandTests(TestCase):
    """``import_music_data --dry-run`` reports the album changes, writing nothing."""

    def setUp(self):
        import_artists()
        import_handler.import_albums(StringIO(ALBUMS_TSV))
        self.dir = Path(self.enterContext(TemporaryDirectory()))
        self.paths = {}
        for key, name, text in (
            ("artists", "ArtistInfo.txt", ARTISTS_TSV),
            ("lists", "ListData.txt", LISTS_TSV),
            (
                "albums",
                "WebRankings.txt",
                "1\tPet Sounds\t3,0\t1966\tQ212863\n"
                "2\tHarvest\t56,0\t1972\tQ1191683\n"
                "3\tDéjà Vu\t113,1\t1970\tQ1136782\n",
            ),
            ("positions", "ListPositions.txt", POSITIONS_TSV),
        ):
            (self.dir / name).write_text(text, encoding="utf-8")
            self.paths[key] = str(self.dir / name)

    def run_command(self, **options):
        out = StringIO()
        call_command("import_music_data", stdout=out, **self.paths, **options)
        return out.getvalue()

    def test_a_cache_warning_reaches_the_operator(self):
        with mock.patch(
            "music.services.import_handler.invalidate_release_caches",
            return_value=False,
        ):
            output = self.run_command()
        self.assertIn(caching.CACHES_NOT_CLEARED, output)

    def test_a_dry_run_names_a_bad_lists_file_without_a_traceback(self):
        (self.dir / "ListData.txt").write_text(
            "Mojo\t1995\tThe 100 Greatest Albums\t\n", encoding="utf-8"
        )
        with self.assertRaisesMessage(CommandError, "before list types"):
            self.run_command(dry_run=True)

    def test_a_dry_run_reports_kept_added_and_removed(self):
        before = list(models.Album.objects.values_list("pk", "name", "rank"))
        output = self.run_command(dry_run=True)
        self.assertIn("Albums file: 3 rows - 2 kept, 1 added, 1 removed", output)
        self.assertIn("+     2 Harvest [Q1191683]", output)
        self.assertIn("-     3 Rust Never Sleeps [Q1140313, Q999999]", output)
        self.assertEqual(
            list(models.Album.objects.values_list("pk", "name", "rank")), before
        )

    def test_a_dry_run_lists_name_variants_and_artists_the_file_drops(self):
        models.Artist.objects.create(name="Dropped", slug="dropped", source_id=999)
        models.Artist.objects.create(name="Crazy Horse (legacy)", slug="legacy")
        output = self.run_command(dry_run=True)
        self.assertIn("4 artists, 2 with name variants", output)
        self.assertIn("56 0: Neil Young | 1: Neil Young & Crazy Horse", output)
        self.assertIn("- 999 Dropped (removed)", output)
        self.assertNotRegex(output, r"(?m)^  ~ \d+ slug ")
        self.assertNotIn("!", output)
        # A row without a provider id may yet be adopted, so is not listed.
        self.assertNotIn("legacy", output)

    def test_a_dry_run_warns_of_a_reused_id(self):
        models.Artist.objects.filter(source_id=192).update(name="Sun Ra")
        output = self.run_command(dry_run=True)
        self.assertIn("! 192 was 'Sun Ra', now 'Crazy Horse'", output)

    def test_a_dry_run_lists_slug_changes(self):
        models.Artist.objects.filter(source_id=56).update(slug="neil-young-old")
        output = self.run_command(dry_run=True)
        self.assertIn("~ 56 slug neil-young-old -> neil-young", output)

    def test_a_dry_run_lists_every_bad_credit(self):
        Path(self.paths["albums"]).write_text(
            "1\tPet Sounds\t3,1\t1966\tQ212863\n2\tHarvest\t999,0\t1972\tQ1\n",
            encoding="utf-8",
        )
        output = self.run_command(dry_run=True)
        self.assertIn("! Albums row 1 (Pet Sounds) credits artist 3", output)
        self.assertIn("! Albums row 2 (Harvest) credits artist 999", output)

    def test_the_import_reports_kept_added_and_removed(self):
        output = self.run_command()
        self.assertIn("Albums: 3 (2 kept, 1 added, 1 removed)", output)


class ImportListMembershipsTests(TestCase):
    def setUp(self):
        import_artists()
        import_handler.import_lists(StringIO(LISTS_TSV))
        import_handler.import_albums(StringIO(ALBUMS_TSV))

    def test_joins_positions_to_the_right_list_and_album(self):
        success, message = import_handler.import_listmemberships(
            StringIO(POSITIONS_TSV)
        )
        self.assertTrue(success)
        self.assertIn("5 created", message)

        first_list = models.MusicList.objects.get(order=1)
        pet_sounds = models.Album.objects.get(rank=1)
        membership = models.AlbumListMembership.objects.get(
            list=first_list, album=pet_sounds
        )
        # Row 1, cell "0:2": list index 0 is order 1, position 2.
        self.assertEqual(membership.rank, 2)

    def test_the_second_row_belongs_to_the_album_at_rank_two(self):
        import_handler.import_listmemberships(StringIO(POSITIONS_TSV))
        third_list = models.MusicList.objects.get(order=3)
        membership = models.AlbumListMembership.objects.get(list=third_list)
        self.assertEqual(membership.album.rank, 2)
        self.assertEqual(membership.rank, 9)

    def test_an_unknown_list_index_is_skipped(self):
        success, message = import_handler.import_listmemberships(
            StringIO("0:1\t99:1\n")
        )
        self.assertTrue(success)
        self.assertIn("1 created", message)

    def test_a_row_with_no_matching_album_is_rejected(self):
        models.Album.objects.filter(rank=3).delete()
        with self.assertRaises(ValueError) as ctx:
            import_handler.import_listmemberships(StringIO(POSITIONS_TSV))
        self.assertIn("no album at rank 3", str(ctx.exception))

    def test_reimporting_replaces_the_previous_memberships(self):
        import_handler.import_listmemberships(StringIO(POSITIONS_TSV))
        import_handler.import_listmemberships(StringIO(POSITIONS_TSV))
        self.assertEqual(models.AlbumListMembership.objects.count(), 5)

    def test_blank_cells_are_ignored(self):
        success, message = import_handler.import_listmemberships(
            StringIO("0:1\t\t1:2\n")
        )
        self.assertTrue(success)
        self.assertIn("2 created", message)

    def test_memberships_are_written_in_batches(self):
        with self.settings():
            original = import_handler.config.IMPORT_BATCH_SIZE
            import_handler.config.IMPORT_BATCH_SIZE = 1
            try:
                success, message = import_handler.import_listmemberships(
                    StringIO(POSITIONS_TSV)
                )
            finally:
                import_handler.config.IMPORT_BATCH_SIZE = original
        self.assertTrue(success)
        self.assertEqual(models.AlbumListMembership.objects.count(), 5)

    def test_progress_callback_receives_each_stage(self):
        events = []
        import_handler.import_listmemberships(
            StringIO(POSITIONS_TSV), lambda name, data: events.append((name, data))
        )
        names = [name for name, _ in events]
        self.assertEqual(names[0], "start")
        self.assertEqual(names[-1], "complete")
        self.assertEqual(dict(events)["complete"]["count"], 5)


class ImportBatchTests(TestCase):
    def test_runs_all_four_importers_in_order(self):
        message, warnings = import_release()
        self.assertEqual(warnings, [])
        self.assertTrue(message.startswith("Artists: 4"))
        self.assertIn("Lists: 3 created", message)
        self.assertIn("Albums: 3 (0 kept, 3 added, 0 removed)", message)
        self.assertIn("memberships: 5 created", message)
        self.assertEqual(models.Artist.objects.count(), 4)
        self.assertEqual(models.MusicList.objects.count(), 3)
        self.assertEqual(models.Album.objects.count(), 3)
        self.assertEqual(models.AlbumListMembership.objects.count(), 5)

    def test_an_empty_lists_file_stops_the_batch(self):
        with self.assertRaises(ValueError) as ctx:
            import_release(lists_file="\n")
        self.assertIn("No lists were imported", str(ctx.exception))

    def test_an_empty_albums_file_stops_the_batch(self):
        with self.assertRaises(ValueError) as ctx:
            import_release(albums_file="\n")
        self.assertIn("No albums were imported", str(ctx.exception))

    def test_albums_cannot_credit_artists_the_release_lacks(self):
        with self.assertRaises(ValueError) as ctx:
            import_release(artists_file="3\t183048\tThe Beach Boys\n")
        self.assertIn("not in the artists file", str(ctx.exception))

    def test_a_failure_rolls_the_whole_batch_back(self):
        # A positions file with more rows than albums fails mid-import; the
        # artists, lists and albums written before it must not survive.
        with self.assertRaises(ValueError):
            import_release(positions_file=POSITIONS_TSV + "0:1\n")
        self.assertEqual(models.Artist.objects.count(), 0)
        self.assertEqual(models.MusicList.objects.count(), 0)
        self.assertEqual(models.Album.objects.count(), 0)


class RealReleaseFilesTests(TestCase):
    """End-to-end over the files the rankings actually shipped with."""

    def test_the_supplied_release_imports_completely(self):
        import_real_release()

        # Counted from the files, so a new release does not fail the suite
        # just for being bigger. What matters is that every row lands.
        album_rows = _read_fixture_rows("WebRankings.txt")
        list_rows = _read_fixture_rows("ListData.txt")
        self.assertEqual(models.Album.objects.count(), len(album_rows))
        self.assertEqual(models.MusicList.objects.count(), len(list_rows))
        self.assertEqual(
            models.MusicPublication.objects.count(),
            len({row[0] for row in list_rows}),
        )
        self.assertGreater(models.AlbumListMembership.objects.count(), 0)

        top = models.Album.objects.get(rank=1)
        self.assertEqual(top.name, "Pet Sounds")
        self.assertEqual(top.artist_credit, "The Beach Boys")
        self.assertEqual(top.year_released, 1966)
        self.assertEqual(top.wikidata_id, "Q212863")
        self.assertEqual(top.year_rank, 1)
        self.assertEqual(top.decade_rank, 1)

    def test_every_artist_lands_under_its_provider_id(self):
        import_real_release()
        artist_rows = _read_fixture_rows("ArtistInfo.txt")
        self.assertEqual(models.Artist.objects.count(), len(artist_rows))
        self.assertFalse(models.Artist.objects.filter(source_id__isnull=True).exists())
        variants = sum(len([n for n in row[2:] if n]) for row in artist_rows)
        self.assertEqual(
            sum(len(a.name_variants) for a in models.Artist.objects.all()), variants
        )
        slugs = list(models.Artist.objects.values_list("slug", flat=True))
        self.assertEqual(len(set(slugs)), len(slugs))
        self.assertNotIn("", slugs)

    def test_the_credits_read_as_the_artist_system_intends(self):
        # The cases the name-variant system was designed around, from the
        # 2026-10-28 release and the data provider's notes on it.
        import_real_release()

        def credit(name):
            return models.Album.objects.get(name=name).artist_credit

        def artists(name):
            return [
                artist.name
                for artist in models.Album.objects.get(name=name).credited_artists
            ]

        def owns(artist_name, album_name):
            return models.Album.objects.filter(
                name=album_name, artists__name=artist_name
            ).exists()

        self.assertEqual(credit("Purple Rain"), "Prince and the Revolution")
        self.assertEqual(artists("Purple Rain"), ["Prince"])
        self.assertTrue(owns("Prince", "Sign o' the Times"))
        self.assertEqual(credit("Band on the Run"), "Paul McCartney and Wings")
        self.assertEqual(credit("Déjà Vu"), "Crosby, Stills, Nash & Young")
        self.assertTrue(owns("Crosby, Stills & Nash", "Déjà Vu"))
        # Credited to each artist separately; "The Velvet Underground &
        # Nico" is a leftover variant no credit uses.
        self.assertEqual(
            artists("The Velvet Underground & Nico"),
            ["The Velvet Underground", "Nico"],
        )
        self.assertEqual(
            credit("The Harder They Come"), "Jimmy Cliff & Various Artists"
        )
        self.assertEqual(credit("Saturday Night Fever"), "Bee Gees & Various Artists")
        nuggets = models.Album.objects.get(name__startswith="Nuggets")
        self.assertEqual(nuggets.artist_credit, "Various Artists")
        self.assertTrue(nuggets.various_artists)
        self.assertEqual(nuggets.credited_artists, [])

    def test_every_album_appears_on_at_least_one_list(self):
        self._import_release()
        orphaned = models.Album.objects.filter(lists__isnull=True).count()
        self.assertEqual(orphaned, 0)

    def test_every_album_slug_is_unique(self):
        self._import_release()
        slugs = list(models.Album.objects.values_list("slug", flat=True))
        self.assertEqual(len(set(slugs)), len(slugs))
        self.assertEqual(len(slugs), len(_read_fixture_rows("WebRankings.txt")))

    def test_the_unranked_lists_record_every_member_at_rank_one(self):
        # An unranked list is one where every position in the file is the
        # same; the importer records all of its albums at rank 1.
        self._import_release()
        unranked = [
            source
            for source in models.MusicList.objects.all()
            if set(
                models.AlbumListMembership.objects.filter(list=source).values_list(
                    "rank", flat=True
                )
            )
            == {1}
            and models.AlbumListMembership.objects.filter(list=source).count() > 1
        ]
        self.assertTrue(unranked, "the release has no unranked list any more")
        for source in unranked:
            with self.subTest(list=source.name):
                memberships = models.AlbumListMembership.objects.filter(list=source)
                self.assertEqual(set(memberships.values_list("rank", flat=True)), {1})

    def _import_release(self):
        import_real_release()


def import_real_release():
    """``import_batch`` over the checked-in release, as the command opens it."""
    with ExitStack() as stack:
        files = {
            field: stack.enter_context(
                (FIXTURE_DIR / name).open(
                    encoding="utf-8-sig",
                    newline=None if field == "positions_file" else "",
                )
            )
            for field, name in (
                ("artists_file", "ArtistInfo.txt"),
                ("lists_file", "ListData.txt"),
                ("albums_file", "WebRankings.txt"),
                ("positions_file", "ListPositions.txt"),
            )
        }
        return import_handler.import_batch(**files)


def _read_fixture_rows(filename):
    """Read a release TSV into a list of column lists."""
    with (FIXTURE_DIR / filename).open(encoding="utf-8-sig") as handle:
        return [line.rstrip("\r\n").split("\t") for line in handle if line.strip()]


class ImportInvalidatesCachesTests(ClearsCachesMixin, TestCase):
    """An import has to drop the counts it just made wrong.

    Only the import *page* used to invalidate, so a command-line import left
    the rankings heading reading "The top 500 most recommended albums across
    54 critic lists" for up to 24 hours after the release grew to 1000.
    """

    def _import_release(self):
        return import_real_release()

    def test_the_import_drops_every_cached_key(self):
        for key in config.CACHE_KEYS:
            cache.set(key, "stale", 600)
        self._import_release()
        for key in config.CACHE_KEYS:
            with self.subTest(key=key):
                self.assertIsNone(cache.get(key))

    def test_the_heading_counts_are_right_straight_after_an_import(self):
        # The symptom, end to end: cache the old counts, import a bigger
        # release, and the page must not still be describing the old one.
        self.client.get(reverse("music:home"))
        self._import_release()
        response = self.client.get(reverse("music:home"))
        self.assertEqual(response.context["album_count"], models.Album.objects.count())
        self.assertEqual(
            response.context["list_count"], models.MusicList.objects.count()
        )
        self.assertEqual(
            response.context["publication_count"],
            models.MusicPublication.objects.count(),
        )

    def test_the_import_stamps_the_update_time(self):
        self._import_release()
        self.assertIsNotNone(
            SiteMetadata.get_instance(config.SITE_METADATA_KEY).last_full_update
        )


class ImportReconnectsTrackingTests(TestCase):
    """An import must never empty a collection.

    A kept album keeps its tracking rows outright. An album the release
    drops is deleted, and its rows survive with their album FK nulled; the
    importer's reconnection pass points them at the album again if a later
    release brings it back.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="listener", password="pw")
        import_artists()
        import_handler.import_albums(StringIO(ALBUMS_TSV))

    def test_a_tracked_album_that_is_kept_keeps_its_row_untouched(self):
        album = models.Album.objects.get(rank=1)
        row = models.ListenedAlbum.objects.create(
            user=self.user, album=album, wikidata_id=album.wikidata_id, owned=True
        )

        import_handler.import_albums(StringIO(ALBUMS_TSV))

        self.assertEqual(
            list(models.ListenedAlbum.objects.values("pk", "album", "owned")),
            [{"pk": row.pk, "album": album.pk, "owned": True}],
        )

    def test_an_album_dropped_and_then_brought_back_is_re_adopted(self):
        album = models.Album.objects.get(rank=1)
        models.ListenedAlbum.objects.create(
            user=self.user, album=album, wikidata_id=album.wikidata_id
        )
        models.WantToListenAlbum.objects.create(
            user=self.user,
            album=models.Album.objects.get(rank=2),
            wikidata_id="Q1136782",
        )
        without_them = ALBUMS_TSV.split("\n", 2)[2]

        import_handler.import_albums(StringIO(without_them))
        self.assertIsNone(models.ListenedAlbum.objects.get().album)
        self.assertIsNone(models.WantToListenAlbum.objects.get().album)

        import_handler.import_albums(StringIO(ALBUMS_TSV))
        self.assertEqual(models.ListenedAlbum.objects.get().album.name, "Pet Sounds")
        self.assertEqual(models.WantToListenAlbum.objects.get().album.name, "Déjà Vu")
        self.assertNotEqual(models.ListenedAlbum.objects.get().album_id, album.pk)

    def test_a_reimport_normalizes_a_secondary_wikidata_id(self):
        # Rust Never Sleeps carries two ids in the fixture; a row stored
        # under the second has to find its way home and then be renamed to
        # the primary, or the next import orphans it again.
        models.ListenedAlbum.objects.create(
            user=self.user, album=None, wikidata_id="Q999999"
        )

        import_handler.import_albums(StringIO(ALBUMS_TSV))

        row = models.ListenedAlbum.objects.get()
        self.assertEqual(row.album.name, "Rust Never Sleeps")
        self.assertEqual(row.wikidata_id, "Q1140313")

    def test_a_reimport_merges_two_rows_that_now_point_at_one_album(self):
        models.ListenedAlbum.objects.create(
            user=self.user, album=None, wikidata_id="Q1140313"
        )
        models.ListenedAlbum.objects.create(
            user=self.user, album=None, wikidata_id="Q999999"
        )

        import_handler.import_albums(StringIO(ALBUMS_TSV))

        self.assertEqual(models.ListenedAlbum.objects.count(), 1)
        self.assertEqual(
            models.ListenedAlbum.objects.get().album.name, "Rust Never Sleeps"
        )

    def test_a_reimport_leaves_an_untracked_database_alone(self):
        # The common case, and the reason the pass is behind an existence
        # check rather than run unconditionally.
        import_handler.import_albums(StringIO(ALBUMS_TSV))
        self.assertEqual(models.ListenedAlbum.objects.count(), 0)

    def _tracked_album_key(self):
        """A cached set for a tracked album the next release drops."""
        album = models.Album.objects.get(rank=1)
        models.ListenedAlbum.objects.create(
            user=self.user, album=album, wikidata_id=album.wikidata_id
        )
        key = config.CACHE_KEY_LISTENED_ALBUMS.format(user_id=self.user.id)
        cache.set(key, [album.id], 300)
        return key, album

    def test_a_whole_release_drops_a_trackers_caches(self):
        key, _ = self._tracked_album_key()
        import_release(
            albums_file=SHORTER_ALBUMS_TSV,
            positions_file=SHORTER_POSITIONS_TSV,
        )
        self.assertIsNone(cache.get(key))

    def test_a_failed_release_leaves_a_trackers_caches(self):
        """Its rows rolled back, so what the cache holds is still true."""
        key, album = self._tracked_album_key()
        with mock.patch.object(
            import_handler, "import_listmemberships", side_effect=ValueError
        ):
            with self.assertRaises(ValueError):
                import_release(albums_file=ALBUMS_TSV.split("\n", 1)[1])
        self.assertEqual(cache.get(key), [album.id])

    def test_a_cache_error_cannot_fail_a_committed_release(self):
        """Staff told it failed, with the new rankings live, would re-run it."""
        _, dropped = self._tracked_album_key()
        with mock.patch(
            "core.cache_helpers.cache.delete_many", side_effect=ConnectionError
        ):
            with self.assertLogs("core.cache_helpers", "ERROR"):
                _, warnings = import_release(
                    albums_file=SHORTER_ALBUMS_TSV,
                    positions_file=SHORTER_POSITIONS_TSV,
                )
        self.assertEqual(warnings, [caching.CACHES_NOT_CLEARED])
        self.assertFalse(models.Album.objects.filter(pk=dropped.pk).exists())

    def test_a_release_makes_one_drop_for_everyone_it_touched(self):
        _, dropped = self._tracked_album_key()
        returning = models.Album.objects.get(rank=2)
        reader = User.objects.create_user(username="returning", password="pw")
        models.ListenedAlbum.objects.create(
            user=reader, album=None, wikidata_id=returning.wikidata_id
        )

        with mock.patch(
            "music.services.import_handler.invalidate_release_caches",
            return_value=True,
        ) as invalidate:
            import_release(
                albums_file=SHORTER_ALBUMS_TSV,
                positions_file=SHORTER_POSITIONS_TSV,
            )

        invalidate.assert_called_once_with({self.user.id, reader.id})

    def test_a_failed_release_makes_no_drop(self):
        self._tracked_album_key()
        with mock.patch.object(
            import_handler, "import_listmemberships", side_effect=ValueError
        ), mock.patch(
            "music.services.import_handler.invalidate_release_caches"
        ) as invalidate:
            with self.assertRaises(ValueError):
                import_release(albums_file=ALBUMS_TSV.split("\n", 1)[1])

        invalidate.assert_not_called()

    def test_keeping_an_album_leaves_its_trackers_caches_alone(self):
        # The cached sets hold album pks, which a kept album does not change.
        album = models.Album.objects.get(rank=1)
        models.ListenedAlbum.objects.create(
            user=self.user, album=album, wikidata_id=album.wikidata_id
        )
        key = config.CACHE_KEY_LISTENED_ALBUMS.format(user_id=self.user.id)
        cache.set(key, [album.id], 300)

        import_release()

        self.assertEqual(cache.get(key), [album.id])
