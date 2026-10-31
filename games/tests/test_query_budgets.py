"""Pages whose query count must not grow with the data.

`GamesHomeGenreQueryBudgetTests` and `MusicQueryBudgetTests` pin the
rankings pages. These pin the rest the 2026-10-26 audit found unpinned: each
page is rendered, more of whatever it lists is added, and the count must stay
put - a per-row query (an N+1) is the only thing that makes it grow.
"""

import itertools

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.tests.utils import clear_all_caches
from games.models import (
    Developer,
    Game,
    List,
    ListMembership,
    Publication,
    Series,
)
from music.tests.site import music_site


class QueryBudgetTestCase(TestCase):
    def setUp(self):
        clear_all_caches()

    def count(self, url, client=None):
        clear_all_caches()
        client = client or self.client
        with CaptureQueriesContext(connection) as captured:
            response = client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(captured.captured_queries)

    def assertDoesNotGrow(self, url, grow, client=None):
        self.count(url, client)  # first hits create SiteMetadata and the like
        before = self.count(url, client)
        grow()
        after = self.count(url, client)
        self.assertEqual(after, before, f"{url}: {before} queries, then {after}")


class GameDetailQueryBudgetTests(QueryBudgetTestCase):
    def test_a_deeper_studio_chain_costs_nothing_more(self):
        """`display_root_developer` walked the parent chain a query a level."""
        root = Developer.objects.create(name="Root", slug="root", igdb_id=1)
        studio = Developer.objects.create(name="Studio", igdb_id=2, parent=root)
        game = Game.objects.create(name="G", slug="g", rank=1, year_of_release=2000)
        game.developers.add(studio)

        def deepen():
            middle = Developer.objects.create(name="Middle", igdb_id=3, parent=root)
            studio.parent = middle
            studio.save()
            extra = Developer.objects.create(name="Extra", igdb_id=4, parent=middle)
            game.developers.add(extra)

        self.assertDoesNotGrow("/game/g/", deepen)

    def test_more_list_appearances_cost_nothing_more(self):
        game = Game.objects.create(name="G", slug="g", rank=1, year_of_release=2000)

        def add_lists(start=[0]):
            for n in range(start[0], start[0] + 3):
                publication = Publication.objects.create(name=f"Pub {n}")
                game_list = List.objects.create(
                    name=f"List {n}", publisher=publication, year=2000 + n, type="A"
                )
                ListMembership.objects.create(game=game, list=game_list, rank=n + 1)
            start[0] += 3

        add_lists()
        self.assertDoesNotGrow("/game/g/", add_lists)


class DeveloperListQueryBudgetTests(QueryBudgetTestCase):
    def _add(self, start, count):
        for n in range(start, start + count):
            developer = Developer.objects.create(
                name=f"Dev {n}", slug=f"dev-{n}", igdb_id=100 + n
            )
            child = Developer.objects.create(
                name=f"Dev {n} Studio", igdb_id=1000 + n, parent=developer
            )
            game = Game.objects.create(name=f"Game {n}", slug=f"game-{n}", rank=n + 1)
            game.developers.add(child)

    def test_more_developers_cost_nothing_more(self):
        self._add(0, 3)
        for sort in ("games", "name", "rank", "studios"):
            with self.subTest(sort=sort):
                self.assertDoesNotGrow(
                    f"/developers/?sort={sort}",
                    lambda: self._add(Developer.objects.count(), 3),
                )


class UnifiedSearchQueryBudgetTests(QueryBudgetTestCase):
    def _add(self, start):
        for n in range(start, start + 3):
            developer = Developer.objects.create(
                name=f"Zelda Dev {n}", slug=f"zelda-dev-{n}", igdb_id=200 + n
            )
            child = Developer.objects.create(
                name=f"Zelda Studio {n}", igdb_id=2000 + n, parent=developer
            )
            game = Game.objects.create(name=f"Zelda {n}", slug=f"zelda-{n}", rank=n + 1)
            game.developers.add(child, developer)
            series = Series.objects.create(
                name=f"Zelda {n}", slug=f"zs-{n}", igdb_id=n + 1
            )
            game.series.add(series)

    def test_more_matches_cost_nothing_more(self):
        self._add(0)
        self.assertDoesNotGrow(
            "/api/unified-search/?q=zelda&game_limit=10"
            "&developer_limit=10&series_limit=10",
            lambda: self._add(3),
        )


class GamesAllDataQueryBudgetTests(QueryBudgetTestCase):
    def test_more_games_cost_nothing_more(self):
        def add(start=[0]):
            for n in range(start[0], start[0] + 5):
                developer = Developer.objects.create(
                    name=f"D{n}", slug=f"d{n}", igdb_id=300 + n
                )
                game = Game.objects.create(name=f"All {n}", slug=f"all-{n}", rank=n + 1)
                game.developers.add(developer)
            start[0] += 5

        add()
        self.assertDoesNotGrow("/api/games/all/", add)


class LandingPageQueryBudgetTests(QueryBudgetTestCase):
    def test_a_decade_page_costs_nothing_more_with_more_games(self):
        def add(start=[0]):
            for n in range(start[0], start[0] + 30):
                Game.objects.create(
                    name=f"Nineties {n}",
                    slug=f"n-{n}",
                    rank=n + 1,
                    year_of_release=1990 + n % 10,
                )
            start[0] += 30

        add()
        self.assertDoesNotGrow("/games/1990s/", add)


class GameDeleteQueryBudgetTests(QueryBudgetTestCase):
    def test_a_deep_studio_chain_costs_a_deleted_game_nothing_more(self):
        """`pre_delete` runs for every game an import replaces."""
        root = Developer.objects.create(name="Root", igdb_id=1)
        shallow = Game.objects.create(name="S", slug="s", rank=1, igdb_id=10)
        shallow.developers.add(
            Developer.objects.create(name="A", igdb_id=2, parent=root)
        )
        middle = Developer.objects.create(name="M", igdb_id=3, parent=root)
        deep = Game.objects.create(name="D", slug="d", rank=2, igdb_id=11)
        deep.developers.add(
            Developer.objects.create(name="B", igdb_id=4, parent=middle)
        )

        with CaptureQueriesContext(connection) as first:
            shallow.delete()
        with CaptureQueriesContext(connection) as second:
            deep.delete()

        self.assertEqual(len(first), len(second))


class AccountModalQueryBudgetTests(QueryBudgetTestCase):
    def test_more_tracked_albums_cost_nothing_more(self):
        from core.models import User
        from music.models import Album, ListenedAlbum

        reader = User.objects.create_user(username="reader", password="pw")
        other = User.objects.create_user(username="other", password="pw")
        self.client.login(username="reader", password="pw")

        numbers = itertools.count(1)

        def add():
            for _ in range(3):
                n = next(numbers)
                album = Album.objects.create(
                    name=f"A {n}", rank=n, slug=f"a-{n}", wikidata_id=f"Q{n}"
                )
                for user in (reader, other):
                    ListenedAlbum.objects.create(
                        user=user, album=album, wikidata_id=album.wikidata_id
                    )

        add()
        self.assertDoesNotGrow("/auth/modal/profile/", add)


@music_site
class MusicListsQueryBudgetTests(QueryBudgetTestCase):
    def test_more_lists_cost_nothing_more(self):
        from music.models import MusicList, MusicPublication

        def add(start=[0]):
            for n in range(start[0], start[0] + 3):
                publication = MusicPublication.objects.create(name=f"Mag {n}")
                MusicList.objects.create(
                    name=f"Albums {n}", publisher=publication, year=2000 + n, type="A"
                )
            start[0] += 3

        add()
        self.assertDoesNotGrow("/lists/", add)


class GenreTreeQueryBudgetTests(QueryBudgetTestCase):
    def test_a_bigger_tree_costs_nothing_more(self):
        """Each node asked for its children and its count: two queries a genre."""
        from games.models import WikipediaGenre

        def add(start=[0]):
            for n in range(start[0], start[0] + 3):
                root = WikipediaGenre.objects.create(name=f"Tree {n}", slug=f"tree-{n}")
                child = WikipediaGenre.objects.create(
                    name=f"Tree {n} Child", slug=f"tree-{n}-c", parent=root, level=1
                )
                WikipediaGenre.objects.create(
                    name=f"Tree {n} Leaf", slug=f"tree-{n}-l", parent=child, level=2
                )
            start[0] += 3

        add()
        self.assertDoesNotGrow("/api/genres/tree/", add)
