"""Tests for migration 0102 Wikipedia genre root enforcement."""

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


class GenreRootEnforcementMigrationTests(TestCase):
    """Tests for the canonical root category enforcement migration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module(
            "games.migrations.0102_enforce_genre_root_categories"
        )

    def _create_root(self, name, display_order=0):
        genre, _ = WikipediaGenre.objects.get_or_create(
            name=name,
            defaults={
                "slug": slugify(name),
                "level": 0,
                "path": name,
                "display_order": display_order,
            },
        )
        return genre

    def _create_child(self, parent, name):
        genre, _ = WikipediaGenre.objects.get_or_create(
            name=name,
            defaults={
                "slug": slugify(name),
                "parent": parent,
                "level": 1,
                "path": f"{parent.name} > {name}",
            },
        )
        return genre

    def _create_source_root(self, name):
        return WikipediaGenre.objects.create(
            name=name,
            slug=f"{slugify(name)}-source",
            level=0,
            path=name,
        )

    def setUp(self):
        action = self._create_root("Action")
        adventure = self._create_root("Adventure")
        self._create_root("Role-Playing")
        self._create_root("Shooter")
        self._create_root("Racing & Sports")
        puzzle_casual = self._create_root("Puzzle & Casual")
        self._create_root("Strategy")
        simulation = self._create_root("Simulation")

        self._create_child(action, "Maze")
        self._create_child(adventure, "Interactive Drama")
        self._create_child(puzzle_casual, "Puzzle")
        self._create_child(simulation, "Construction & Management")

    def test_forwards_recategorizes_known_orphan_roots_and_metadata(self):
        art = self._create_source_root("art")
        art_game = self._create_source_root("art game")
        electronic_literature = self._create_source_root("Electronic literature")
        puzzle_game = self._create_source_root("puzzle game")
        snake = self._create_source_root("snake")
        vehicle_construction = self._create_source_root("vehicle construction")

        game = Game.objects.create(name="Known Orphans", rank=1)
        game.wikipedia_genres.add(
            art,
            art_game,
            electronic_literature,
            puzzle_game,
            snake,
            vehicle_construction,
        )
        WikipediaGameData.objects.create(
            game=game,
            page_title="Known Orphans",
            primary_genre="art",
            all_genres=(
                "art, art game, Electronic literature, puzzle game, "
                "snake, vehicle construction"
            ),
            is_primary=True,
        )

        self.migration.forwards(_FakeApps(), None)

        game.refresh_from_db()
        self.assertEqual(
            set(game.wikipedia_genres.values_list("name", flat=True)),
            {
                "Adventure",
                "Interactive Drama",
                "Puzzle",
                "Maze",
                "Construction & Management",
            },
        )

        metadata = WikipediaGameData.objects.get(game=game, is_primary=True)
        self.assertEqual(metadata.primary_genre, "Adventure")
        self.assertEqual(
            metadata.all_genres,
            "Adventure, Interactive Drama, Puzzle, Maze, Construction & Management",
        )

        for name in [
            "art",
            "art game",
            "Electronic literature",
            "puzzle game",
            "snake",
            "vehicle construction",
        ]:
            self.assertFalse(WikipediaGenre.objects.filter(name=name).exists())

    def test_forwards_reparents_remaining_unknown_roots_under_other(self):
        unknown = self._create_source_root("Rhythm Adventure")
        game = Game.objects.create(name="Unknown Root", rank=2)
        game.wikipedia_genres.add(unknown)

        self.migration.forwards(_FakeApps(), None)

        unknown.refresh_from_db()
        self.assertEqual(unknown.parent.name, "Other")
        self.assertEqual(unknown.level, 1)
        self.assertEqual(unknown.path, "Other > Rhythm Adventure")

        other = WikipediaGenre.objects.get(name="Other")
        self.assertIsNone(other.parent)
        self.assertEqual(other.display_order, 99)

    def test_forwards_reparents_unknown_root_with_child_games_under_other(self):
        unknown = self._create_source_root("Experimental")
        child = self._create_child(unknown, "Micro Narrative")
        game = Game.objects.create(name="Unknown Child", rank=5)
        game.wikipedia_genres.add(child)

        self.migration.forwards(_FakeApps(), None)

        unknown.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(unknown.parent.name, "Other")
        self.assertEqual(unknown.path, "Other > Experimental")
        self.assertEqual(child.level, 2)
        self.assertEqual(child.path, "Other > Experimental > Micro Narrative")

    def test_forwards_reparents_known_child_root_to_canonical_parent(self):
        city_building = WikipediaGenre.objects.filter(name="City Building").first()
        if city_building is None:
            city_building = self._create_source_root("City Building")
        else:
            city_building.parent = None
            city_building.level = 0
            city_building.path = "City Building"
            city_building.save(update_fields=["parent", "level", "path"])
        game = Game.objects.create(name="Known Child Root", rank=6)
        game.wikipedia_genres.add(city_building)

        self.migration.forwards(_FakeApps(), None)

        city_building.refresh_from_db()
        self.assertEqual(city_building.parent.name, "Simulation")
        self.assertEqual(city_building.level, 1)
        self.assertEqual(city_building.path, "Simulation > City Building")
        self.assertFalse(WikipediaGenre.objects.filter(name="Other").exists())

    def test_forwards_does_not_create_other_without_unknown_children(self):
        game = Game.objects.create(name="Allowed Root", rank=3)
        game.wikipedia_genres.add(WikipediaGenre.objects.get(name="Adventure"))

        self.migration.forwards(_FakeApps(), None)

        self.assertFalse(WikipediaGenre.objects.filter(name="Other").exists())

    def test_forwards_preserves_simulation_as_allowed_root(self):
        simulation = WikipediaGenre.objects.get(name="Simulation")
        game = Game.objects.create(name="Simulation Root", rank=4)
        game.wikipedia_genres.add(simulation)

        self.migration.forwards(_FakeApps(), None)

        simulation.refresh_from_db()
        self.assertIsNone(simulation.parent)
        self.assertEqual(simulation.level, 0)
        self.assertEqual(simulation.path, "Simulation")
