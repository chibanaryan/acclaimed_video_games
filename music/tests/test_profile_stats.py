"""The Account modal's Music block, and the rank it shows.

The modal is a shared route, so it is requested on each site's real host:
which site it was opened on decides the order.
"""

from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core import sites
from core.models import User
from core.services import percentile
from core.tests.utils import get_on_site
from games.models import Game, PlayedGame
from music import config, models
from music.services.listening_stats import (
    RANK_WORDING,
    get_listener_counts,
    listening_stats,
)
from music.tests.site import setUpModule, tearDownModule  # noqa: F401
from music.tests.test_imports import import_release

MUSIC_ROW = "albums heard or owned"
GAMES_ROW = "games played"


def make_album(n):
    return models.Album.objects.create(
        name=f"Album {n}", rank=n, slug=f"album-{n}", wikidata_id=f"Q{n}"
    )


def mark(user, album, **fields):
    return models.ListenedAlbum.objects.create(
        user=user, album=album, wikidata_id=album.wikidata_id, **fields
    )


class ListeningStatsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="reader", password="pw")

    def test_each_state_is_counted_apart(self):
        albums = [make_album(n) for n in range(1, 7)]
        mark(self.user, albums[0])
        mark(self.user, albums[1])
        mark(self.user, albums[2], owned=True)
        models.WantToListenAlbum.objects.create(
            user=self.user, album=albums[3], wikidata_id=albums[3].wikidata_id
        )

        stats = listening_stats(self.user)

        self.assertEqual(stats["heard"], 2)
        self.assertEqual(stats["owned"], 1)
        self.assertEqual(stats["collected"], 3)
        self.assertEqual(stats["want"], 1)
        self.assertEqual(stats["total_albums"], 6)

    def test_rows_orphaned_by_a_release_do_not_count(self):
        models.ListenedAlbum.objects.create(
            user=self.user, album=None, wikidata_id="Q1"
        )
        models.WantToListenAlbum.objects.create(
            user=self.user, album=None, wikidata_id="Q2"
        )

        stats = listening_stats(self.user)

        self.assertEqual(stats["collected"], 0)
        self.assertEqual(stats["want"], 0)
        self.assertEqual(get_listener_counts(), [])

    def test_another_readers_rows_do_not_count(self):
        other = User.objects.create_user(username="other", password="pw")
        mark(other, make_album(1))
        self.assertEqual(listening_stats(self.user)["collected"], 0)


class RankMessageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="reader", password="pw")
        self.albums = [make_album(n) for n in range(1, 13)]

    def _others(self, *counts):
        for index, count in enumerate(counts):
            other = User.objects.create_user(username=f"other{index}", password="pw")
            for album in self.albums[:count]:
                mark(other, album)

    def _message(self):
        return listening_stats(self.user)["rank_message"]

    def test_nothing_tracked_invites_tracking_and_reads_no_distribution(self):
        self._others(1)
        with CaptureQueriesContext(connection) as captured:
            message = self._message()
        self.assertEqual(message, "Mark an album Heard or Have to see your rank!")
        self.assertEqual(cache.get(config.CACHE_KEY_LISTENER_COUNTS), None)
        self.assertEqual(len(captured.captured_queries), 3)

    def test_the_first_listener_is_told_so(self):
        mark(self.user, self.albums[0])
        self.assertEqual(self._message(), "You're the first to start tracking albums!")

    def test_a_small_population_shows_a_position(self):
        mark(self.user, self.albums[0])
        self._others(2)
        self.assertEqual(self._message(), "You're #2 of 2 listeners")

    def test_the_top_of_a_small_population_is_told_so(self):
        mark(self.user, self.albums[0])
        mark(self.user, self.albums[1])
        self._others(1)
        self.assertEqual(self._message(), "You're #1 of 2 listeners!")

    def test_a_tie_shares_the_better_rank_and_says_so(self):
        mark(self.user, self.albums[0])
        self._others(1)
        self.assertEqual(self._message(), "You're tied for #1 of 2 listeners!")

    def test_a_tie_below_first_says_so(self):
        mark(self.user, self.albums[0])
        self._others(1, 2)
        self.assertEqual(self._message(), "You're tied for #2 of 3 listeners")

    def test_a_stale_distribution_cannot_rank_past_its_own_size(self):
        """The reader's count is live and the cached distribution is not."""
        stale = [2, 2]
        result = percentile.calculate_percentile(1, lambda: stale, RANK_WORDING)
        self.assertEqual(result["message"], "You're #2 of 2 listeners")

    def test_a_large_population_shows_a_percentile(self):
        mark(self.user, self.albums[0])
        mark(self.user, self.albums[1])
        self._others(1, 1, 3, 3, 3, 3, 3, 3, 3)
        self.assertEqual(
            self._message(), "You've tracked more albums than 22% of listeners"
        )

    def test_a_leader_under_a_hundred_gets_a_position_not_a_share(self):
        """The leader of 20 is not in the top 1%, and beat everyone, not 95%."""
        mark(self.user, self.albums[0])
        mark(self.user, self.albums[1])
        self._others(*[1] * 19)
        self.assertEqual(self._message(), "You're #1 of 20 listeners!")

    def test_last_place_gets_a_position_not_zero_percent(self):
        mark(self.user, self.albums[0])
        self._others(*[2] * 19)
        self.assertEqual(self._message(), "You're #20 of 20 listeners")

    def test_a_full_tie_is_shared_first_place(self):
        mark(self.user, self.albums[0])
        self._others(*[1] * 19)
        self.assertEqual(self._message(), "You're tied for #1 of 20 listeners!")

    def test_a_share_that_rounds_to_zero_gets_a_position(self):
        result = self._rank(2, [5] * 998 + [2, 1])
        self.assertEqual(result["message"], "You're #999 of 1000 listeners")

    def test_a_percentile_cannot_pass_100_on_stale_counts(self):
        """The reader's count is live; the cached counts may not hold them."""
        result = percentile.calculate_percentile(5, lambda: [1] * 10, RANK_WORDING)
        self.assertEqual(result["percentile"], 100)

    def _rank(self, count, counts):
        return percentile.calculate_percentile(count, lambda: counts, RANK_WORDING)

    def test_the_real_top_one_percent_is_told_so(self):
        result = self._rank(5, [9, 5] + [1] * 198)
        self.assertEqual(result["message"], "You're in the top 1% of listeners!")

    def test_a_tie_cannot_claim_the_top_one_percent(self):
        """30 level at the top of 150, and 100 level behind one, are not 1%."""
        self.assertEqual(
            self._rank(5, [5] * 30 + [1] * 120)["message"],
            "You're tied for #1 of 150 listeners!",
        )
        self.assertNotIn(
            "top 1%", self._rank(5, [9] + [5] * 100 + [1] * 199)["message"]
        )

    def test_someone_ahead_means_never_more_than_100_percent(self):
        """Stale counts hold the reader's old number and someone above them."""
        result = self._rank(5, [4] + [1] * 8 + [9])
        self.assertEqual(result["percentile"], 99)
        self.assertEqual(
            result["message"], "You've tracked more albums than 99% of listeners"
        )

    def test_have_counts_towards_the_rank_as_heard_does(self):
        """Have is for readers who track what they own, and they are ranked."""
        mark(self.user, self.albums[0], owned=True)
        mark(self.user, self.albums[1], owned=True)
        self._others(1)
        self.assertEqual(self._message(), "You're #1 of 2 listeners!")


class ListenerDistributionCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="reader", password="pw")
        self.album = make_album(1)
        mark(self.user, self.album)
        self.second = make_album(2)

    def _reads_stale(self):
        """Whether a change made behind the cache's back goes unnoticed."""
        return get_listener_counts() == [1]

    def _prime(self):
        self.assertEqual(get_listener_counts(), [1])
        mark(self.user, self.second)
        self.assertTrue(self._reads_stale())

    def test_a_toggle_drops_it(self):
        self._prime()
        self.client.login(username="reader", password="pw")
        url = reverse("music:toggle-listened", args=[self.second.pk])
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(f"{url}?status=own").status_code, 200)
        self.assertFalse(self._reads_stale())

    def test_the_bulk_command_drops_it(self):
        self._prime()
        third = make_album(3)
        with self.captureOnCommitCallbacks(execute=True):
            call_command("mark_albums_listened", user="reader", ids=third.wikidata_id)
        self.assertFalse(self._reads_stale())

    def test_an_import_drops_it(self):
        self._prime()
        import_release()
        self.assertFalse(self._reads_stale())


class ProfileModalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.reader = User.objects.create_user(
            username="reader", email="r@example.com", password="pw"
        )
        self.client.login(username="reader", password="pw")
        self.album = make_album(1)
        mark(self.reader, self.album)
        self.game = Game.objects.create(name="G", slug="g", rank=1)
        PlayedGame.objects.create(user=self.reader, game=self.game, igdb_id=1)

    def _page(self, site):
        return get_on_site(self.client, site, "auth-modal-profile").content.decode()

    def test_the_music_site_puts_music_first(self):
        page = self._page(sites.MUSIC)
        self.assertLess(page.index(MUSIC_ROW), page.index(GAMES_ROW))

    def test_the_games_site_puts_games_first(self):
        page = self._page(sites.GAMES)
        self.assertLess(page.index(GAMES_ROW), page.index(MUSIC_ROW))

    def test_both_sections_are_named_with_the_beta_badge(self):
        page = self._page(sites.GAMES)
        self.assertIn(">Games</h4>", page)
        self.assertIn("Music ", page)
        self.assertIn(">Beta<", page)

    def test_the_breakdown_shows_only_when_both_states_are_held(self):
        self.assertNotIn(" heard, ", self._page(sites.MUSIC))
        mark(self.reader, make_album(2), owned=True)
        self.assertIn("1 heard, 1 have", self._page(sites.MUSIC))

    def test_the_want_row_hides_at_zero(self):
        self.assertNotIn("want list", self._page(sites.MUSIC))
        album = make_album(2)
        models.WantToListenAlbum.objects.create(
            user=self.reader, album=album, wikidata_id=album.wikidata_id
        )
        self.assertIn("album on your want list", self._page(sites.MUSIC))

    def test_a_reader_who_only_owns_albums_gets_haves_mark(self):
        self.assertIn("gold-record", self._page(sites.MUSIC))
        models.ListenedAlbum.objects.filter(user=self.reader).update(owned=True)
        page = self._page(sites.MUSIC)
        self.assertIn("record-sleeve", page)
        self.assertNotIn("gold-record", page)

    def test_a_rejected_username_keeps_the_music_block(self):
        response = self.client.post(
            sites.site_reverse(sites.MUSIC, "auth-modal-profile"),
            {"username": "x"},
            HTTP_HOST="music.acclaimedmedia.org",
            secure=True,
        )
        page = response.content.decode()
        self.assertIn("at least 3 characters", page)
        self.assertIn(MUSIC_ROW, page)
