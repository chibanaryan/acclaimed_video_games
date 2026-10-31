"""The client-side filter engines order results exactly as the server does.

AGENTS.md asks for this check after any filter change, and it was run by
hand: unit tests on either side cannot catch a divergence, because both can
be self-consistently wrong. Here the server renders each query, Node runs the
real engine files on the same data (`core/tests/js/filter_parity.js`), and
the two orders must match. Skipped where Node is not installed.
"""

import datetime
import html
import json
import re
import tempfile
from pathlib import Path

from django.test import TestCase

from core.tests.node import node_available, run_node
from core.tests.utils import clear_all_caches
from games.models import Game, HLTBGameData, Platform, Series, WikipediaGenre
from music import models as music
from music.templatetags.music_filters import artist_links
from music.tests.site import music_site


def run_engines(payloads):
    """Run the harness on ``{section: {"payload", "queries"}}``."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(payloads, handle)
    try:
        return run_node("filter_parity.js", handle.name)
    finally:
        Path(handle.name).unlink()


class ParityTestCase(TestCase):
    def setUp(self):
        if not node_available():
            self.skipTest("Node is not installed")
        clear_all_caches()

    def _server_order(self, url, id_pattern):
        clear_all_caches()
        html = self.client.get(url).content.decode()
        return [int(pk) for pk in re.findall(id_pattern, html)]

    def assertSameOrder(self, section, queries, server_url, id_pattern, payload):
        engine = run_engines({section: {"payload": payload, "queries": queries}})
        for query in queries:
            with self.subTest(query=query):
                server = self._server_order(server_url.format(query=query), id_pattern)
                self.assertTrue(server or query, "the unfiltered page listed nothing")
                self.assertEqual(engine[section][query], server)


class GamesParityTests(ParityTestCase):
    @classmethod
    def setUpTestData(cls):
        root = WikipediaGenre.objects.create(name="Parity Action", slug="parity-action")
        child = WikipediaGenre.objects.create(
            name="Parity Shooter", slug="parity-shooter", parent=root, level=1
        )
        other = WikipediaGenre.objects.create(
            name="Parity Puzzle", slug="parity-puzzle"
        )
        cls.root, cls.child = root, child
        pc = Platform.objects.create(code="PCX", name="Parity PC")
        nes = Platform.objects.create(code="NSX", name="Parity NES")
        cls.pc = pc
        cls.series = Series.objects.create(
            name="Parity Saga", slug="parity-saga", igdb_id=1
        )
        names = [
            "Pokémon Red",
            "pokemon gold",
            "Zelda",
            "zelda II",
            "Ägypten",
            "Doom",
            "DOOM 64",
            "Ōkami",
            "Tetris",
            "'Splosion Man",
            "Ico",
            "Half-Life",
            "Half Life 2",
            "Myst",
            "Rez",
            "Braid",
            "Limbo",
            "Inside",
            "Fez",
            "Celeste",
        ]
        for rank, name in enumerate(names, start=1):
            game = Game.objects.create(
                name=name,
                slug=f"parity-{rank}",
                rank=rank,
                igdb_id=rank,
                year_of_release=1985 + (rank * 3) % 30,
            )
            game.platforms.add(pc if rank % 2 else nes)
            game.wikipedia_genres.add(
                child if rank % 3 == 0 else (root if rank % 3 == 1 else other)
            )
            if rank % 4 == 0:
                game.series.add(cls.series)
            hltb = HLTBGameData.objects.create(
                game=game,
                igdb_id=rank,
                hltb_id=str(rank),
                main_story_hours=(rank * 7) % 45 or None,
                completionist_hours=(rank * 11) % 90 or None,
                is_primary=True,
            )
            game.primary_hltb_game_data = hltb
            game.save()

    def test_the_engine_matches_the_server(self):
        payload = self.client.get("/api/games/all/").json()
        payload = payload.get("data", payload)
        queries = [
            "",
            "q=zelda",
            "q=pokemon",
            "q=half",
            "sort=name",
            "sort=name&dir=desc",
            "sort=year",
            "sort=year&dir=desc",
            "dir=desc",
            "start=1990&end=1999",
            "start=2000",
            f"genres={self.root.id}",
            f"genres={self.child.id}",
            f"platforms={self.pc.id}",
            f"series={self.series.id}",
            "hltb_min=10&hltb_max=30",
            "hltb_min=20",
            "sort=playtime",
            "sort=playtime&dir=desc",
            "hltb_mode=completionist&sort=playtime",
            f"genres={self.root.id}&sort=year&dir=desc",
            f"q=o&platforms={self.pc.id}&start=1990",
        ]
        self.assertSameOrder(
            "games", queries, "/?{query}&partial=true", r'id="game-(\d+)"', payload
        )


@music_site
class MusicParityTests(ParityTestCase):
    @classmethod
    def setUpTestData(cls):
        rock = music.MusicGenre.objects.create(name="Parity Rock", slug="parity-rock")
        punk = music.MusicGenre.objects.create(
            name="Parity Punk", slug="parity-punk", parent=rock, level=1
        )
        jazz = music.MusicGenre.objects.create(name="Parity Jazz", slug="parity-jazz")
        cls.rock, cls.punk = rock, punk
        artists = [
            music.Artist.objects.create(name=name, slug=f"parity-artist-{n}")
            for n, name in enumerate(["Björk", "The Beatles", "Sigur Rós", "Nas"])
        ]
        cls.artist = artists[0]
        publication = music.MusicPublication.objects.create(name="Parity Mag")
        lists = [
            music.MusicList.objects.create(
                name=f"Parity List {n}", publisher=publication, year=2000 + n, type="A"
            )
            for n in range(3)
        ]
        names = [
            "Ágætis byrjun",
            "Abbey Road",
            "abbey road (remaster)",
            "Illmatic",
            "Homogenic",
            "Post",
            "Revolver",
            "Takk...",
            "( )",
            "Kid A",
            "Vespertine",
            "Debut",
            "Help!",
            "It Was Written",
            "Valtari",
        ]
        for rank, name in enumerate(names, start=1):
            year = 1966 + (rank * 5) % 40
            album = music.Album.objects.create(
                name=name,
                rank=rank,
                artist_credit=artists[rank % 4].name,
                year_released=year,
                release_date=(
                    datetime.date(year, 1 + rank % 12, 1) if rank % 3 else None
                ),
            )
            album.artists.set([artists[rank % 4]])
            album.genres.set(
                [punk if rank % 3 == 0 else (rock if rank % 3 == 1 else jazz)]
            )
            for game_list in lists[: 1 + rank % 3]:
                music.AlbumListMembership.objects.create(
                    album=album, list=game_list, rank=rank
                )
        # Credited under another of an artist's names, and with others: the
        # artist filter finds it by the artist, the search by the name.
        cls.artist.name_variants = ["Björk", "The Sugarcubes"]
        cls.artist.save()
        variant = music.Album.objects.create(
            name="Life's Too Good",
            rank=len(names) + 1,
            artist_credit="The Sugarcubes & Various Artists",
            various_artists=True,
            year_released=1988,
        )
        music.AlbumCredit.objects.create(
            album=variant,
            artist=cls.artist,
            variant=1,
            credited_name="The Sugarcubes",
        )
        variant.genres.set([rock])
        # An artist whose own name has quotes, credited as another: the
        # link's title must keep them inside the attribute.
        cls.quoted = music.Artist.objects.create(
            name='Bonnie "Prince" Billy',
            slug="parity-bpb",
            name_variants=['Bonnie "Prince" Billy', "Palace Brothers"],
        )
        cls.quoted_album = music.Album.objects.create(
            name="There Is No-One What Will Take Care of You",
            rank=len(names) + 2,
            artist_credit="Palace Brothers",
            year_released=1993,
        )
        music.AlbumCredit.objects.create(
            album=cls.quoted_album,
            artist=cls.quoted,
            variant=1,
            credited_name="Palace Brothers",
        )
        cls.quoted_album.genres.set([rock])
        music.AlbumListMembership.objects.create(
            album=cls.quoted_album, list=lists[0], rank=2
        )
        music.AlbumListMembership.objects.create(album=variant, list=lists[0], rank=1)

    def test_the_engine_matches_the_server(self):
        payload = self.client.get("/api/all/").json()
        payload = payload.get("data", payload)
        queries = [
            "",
            "q=abbey",
            "q=agaetis",
            "q=bjork",
            "q=sugarcubes",
            "q=various",
            "sort=name",
            "sort=name&dir=desc",
            "sort=year",
            "sort=year&dir=desc",
            "sort=lists",
            "sort=lists&dir=desc",
            "start=1970&end=1989",
            f"genres={self.rock.id}",
            f"genres={self.punk.id}",
            f"artists={self.artist.slug}",
            f"genres={self.rock.id}&sort=year&dir=desc",
        ]
        self.assertSameOrder(
            "music",
            queries,
            "/?{query}&partial=true",
            r'id="music-(\d+)"',
            payload,
        )

    def test_the_renderer_writes_the_servers_credit_line(self):
        # Each credit under its credited name, linked to the artist, and
        # "Various Artists" last - `artist_links` and `_artistCreditHtml`.
        # Compared unescaped: Django escapes quotes and the DOM does not.
        payload = self.client.get("/api/all/").json()
        payload = payload.get("data", payload)
        client = run_engines(
            {"music": {"payload": payload, "queries": [], "credits": True}}
        )["musicCredits"]
        # Unescaping cannot tell `&quot;` from a raw quote, so the attribute
        # is checked as written.
        self.assertIn(
            'title="Bonnie &quot;Prince&quot; Billy">Palace Brothers</a>',
            client[str(self.quoted_album.id)],
        )
        for album in music.Album.objects.with_relations():
            with self.subTest(album=album.name):
                self.assertEqual(
                    html.unescape(client[str(album.id)]),
                    html.unescape(str(artist_links(album))),
                )
