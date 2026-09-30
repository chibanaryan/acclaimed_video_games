"""Tests for migration 0112 remapping stray genres out of Other."""

import importlib

from django.test import TestCase
from django.utils.text import slugify

from games.models import Game, WikipediaGameData, WikipediaGenre


class _FakeApps:
    """Minimal apps registry shim for calling RunPython helpers in tests."""

    MODELS = {
        ("games", "Game"): Game,
        ("games", "WikipediaGameData"): WikipediaGameData,
        ("games", "WikipediaGenre"): WikipediaGenre,
    }

    def get_model(self, app_label, model_name):
        return self.MODELS[(app_label, model_name)]


class RemapStrayOtherGenresMigrationTests(TestCase):
    """Tests for moving stray Other genres to canonical genres."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module(
            "games.migrations.0112_remap_stray_other_genres"
        )

    def _genre(self, name, parent=None):
        genre, _ = WikipediaGenre.objects.get_or_create(
            name=name,
            defaults={
                "slug": slugify(name) or "amp",
                "parent": parent,
                "level": parent.level + 1 if parent else 0,
                "path": f"{parent.path} > {name}" if parent else name,
            },
        )
        return genre

    def _game(self, name, rank, genres, primary, all_genres):
        game = Game.objects.create(name=name, rank=rank)
        game.wikipedia_genres.add(*genres)
        WikipediaGameData.objects.create(
            game=game,
            page_title=name,
            primary_genre=primary,
            all_genres=all_genres,
            is_primary=True,
        )
        return game

    def setUp(self):
        self.other = self._genre("Other")
        action = self._genre("Action")
        self.platform = self._genre("Platform", action)
        self.and_genre = self._genre("and", self.other)
        self.clicker = self._genre("Clicker", self.other)
        self.mmofps = self._genre("MMOFPS", self.other)
        self.unknown = self._genre("Rhythm Adventure", self.other)

    def _names(self, game):
        return set(game.wikipedia_genres.values_list("name", flat=True))

    def test_forwards_drops_conjunction_and_fixes_primary(self):
        game = self._game(
            "Super Mario Maker",
            1,
            [self.and_genre, self.platform],
            "and",
            "and, Platform",
        )

        self.migration.forwards(_FakeApps(), None)

        game.refresh_from_db()
        self.assertEqual(self._names(game), {"Platform"})
        metadata = WikipediaGameData.objects.get(game=game)
        self.assertEqual(metadata.primary_genre, "Platform")
        self.assertEqual(metadata.all_genres, "Platform")
        self.assertFalse(WikipediaGenre.objects.filter(name="and").exists())

    def test_forwards_moves_clicker_and_mmofps(self):
        puzzle_game = self._game(
            "Universal Paperclips", 2, [self.clicker], "Clicker", "Clicker, Puzzle"
        )
        fps_game = self._game("PlanetSide", 3, [self.mmofps], "MMOFPS", "MMOFPS")

        self.migration.forwards(_FakeApps(), None)

        puzzle_game.refresh_from_db()
        fps_game.refresh_from_db()
        self.assertEqual(self._names(puzzle_game), {"Puzzle"})
        self.assertEqual(self._names(fps_game), {"First-Person Shooter"})

        puzzle = WikipediaGenre.objects.get(name="Puzzle")
        self.assertEqual(puzzle.parent.name, "Puzzle & Casual")
        fps = WikipediaGenre.objects.get(name="First-Person Shooter")
        self.assertEqual(fps.path, "Shooter > First-Person Shooter")

        puzzle_meta = WikipediaGameData.objects.get(game=puzzle_game)
        self.assertEqual(puzzle_meta.primary_genre, "Puzzle")
        self.assertEqual(puzzle_meta.all_genres, "Puzzle")
        fps_meta = WikipediaGameData.objects.get(game=fps_game)
        self.assertEqual(fps_meta.primary_genre, "First-Person Shooter")
        self.assertEqual(fps_meta.all_genres, "First-Person Shooter")

        for name in ["Clicker", "MMOFPS"]:
            self.assertFalse(WikipediaGenre.objects.filter(name=name).exists())

    def test_forwards_leaves_other_unknown_genres_alone(self):
        game = self._game(
            "Unknown", 4, [self.unknown], "Rhythm Adventure", "Rhythm Adventure"
        )

        self.migration.forwards(_FakeApps(), None)

        game.refresh_from_db()
        self.assertEqual(self._names(game), {"Rhythm Adventure"})
        self.unknown.refresh_from_db()
        self.assertEqual(self.unknown.parent, self.other)
        self.assertTrue(WikipediaGenre.objects.filter(name="Other").exists())
