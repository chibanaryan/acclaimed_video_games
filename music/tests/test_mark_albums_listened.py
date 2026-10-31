"""Tests for the bulk listen-marking command.

The command exists to import a collection matched elsewhere, so what matters
is that it is idempotent, that it keeps the toggle's mutual exclusivity, and
that it never silently drops an id it could not place.
"""

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import User
from music import models


class MarkAlbumsListenedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ColonelChibbers", password="pw")
        self.pet_sounds = models.Album.objects.create(
            name="Pet Sounds", rank=1, slug="pet-sounds", wikidata_id="Q212863"
        )
        self.london = models.Album.objects.create(
            name="London Calling", rank=2, slug="london-calling", wikidata_id="Q19003"
        )

    def _run(self, **kwargs):
        out = StringIO()
        call_command("mark_albums_listened", stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def _listened(self):
        return set(
            models.ListenedAlbum.objects.filter(user=self.user).values_list(
                "album__slug", flat=True
            )
        )

    def test_marks_the_given_albums(self):
        out = self._run(user="ColonelChibbers", ids="Q212863,Q19003")

        self.assertEqual(self._listened(), {"pet-sounds", "london-calling"})
        self.assertIn("Marked 2 album(s) listened", out)

    def test_username_is_case_insensitive(self):
        self._run(user="colonelchibbers", ids="Q212863")

        self.assertEqual(self._listened(), {"pet-sounds"})

    def test_unknown_user_is_an_error(self):
        with self.assertRaisesMessage(CommandError, "No user named 'nobody'"):
            self._run(user="nobody", ids="Q212863")

    def test_rerunning_adds_nothing_and_keeps_the_original_mark(self):
        self._run(user="ColonelChibbers", ids="Q212863")
        original = models.ListenedAlbum.objects.get(user=self.user)

        out = self._run(user="ColonelChibbers", ids="Q212863,Q19003")

        self.assertIn("Marked 1 album(s) listened", out)
        self.assertIn("1 already were", out)
        kept = models.ListenedAlbum.objects.get(pk=original.pk)
        self.assertEqual(kept.created, original.created)

    def test_marking_listened_clears_a_want_to_listen_row(self):
        models.WantToListenAlbum.objects.create(
            user=self.user, album=self.pet_sounds, wikidata_id="Q212863"
        )

        out = self._run(user="ColonelChibbers", ids="Q212863")

        self.assertFalse(models.WantToListenAlbum.objects.exists())
        self.assertEqual(self._listened(), {"pet-sounds"})
        self.assertIn("Clearing 1 want-to-listen row(s): Pet Sounds", out)

    def test_a_secondary_wikidata_id_finds_its_album(self):
        self.pet_sounds.all_wikidata_ids = ["Q212863", "Q999999"]
        self.pet_sounds.save(update_fields=["all_wikidata_ids"])

        self._run(user="ColonelChibbers", ids="Q999999")

        row = models.ListenedAlbum.objects.get(user=self.user)
        self.assertEqual(row.album, self.pet_sounds)
        # Stored under the primary id, so a reimport reconnects it.
        self.assertEqual(row.wikidata_id, "Q212863")

    def test_two_ids_for_one_album_make_one_mark(self):
        self.pet_sounds.all_wikidata_ids = ["Q212863", "Q999999"]
        self.pet_sounds.save(update_fields=["all_wikidata_ids"])

        self._run(user="ColonelChibbers", ids="Q212863,Q999999")

        self.assertEqual(models.ListenedAlbum.objects.count(), 1)

    def test_ids_matching_no_album_are_reported_not_dropped_silently(self):
        out = self._run(user="ColonelChibbers", ids="Q212863,Q000001")

        self.assertIn("1 id(s) match no album: Q000001", out)
        self.assertEqual(self._listened(), {"pet-sounds"})

    def test_duplicate_ids_are_counted_once(self):
        out = self._run(user="ColonelChibbers", ids="Q212863,Q212863")

        self.assertIn("Ids given:       1", out)

    def test_dry_run_writes_nothing(self):
        out = self._run(user="ColonelChibbers", ids="Q212863", dry_run=True)

        self.assertIn("Dry run: nothing written", out)
        self.assertFalse(models.ListenedAlbum.objects.exists())

    def test_ids_can_come_from_a_file(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ids.txt"
            path.write_text("Q212863,Q19003\n")

            self._run(user="ColonelChibbers", ids_file=str(path))

        self.assertEqual(self._listened(), {"pet-sounds", "london-calling"})

    def test_a_missing_ids_file_is_an_error(self):
        with self.assertRaisesMessage(CommandError, "No such file"):
            self._run(user="ColonelChibbers", ids_file="/nonexistent/ids.txt")

    def test_an_empty_id_list_is_an_error(self):
        with self.assertRaisesMessage(CommandError, "No Wikidata ids given"):
            self._run(user="ColonelChibbers", ids=" ")
