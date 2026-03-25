"""Tests for migration 0100 orphan Wikipedia genre cleanup."""

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


class OrphanGenreCleanupMigrationTests(TestCase):
    """Tests for the orphan genre cleanup migration logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migration = importlib.import_module(
            "games.migrations.0100_cleanup_orphan_wikipedia_genres"
        )

    def setUp(self):
        self._create_base_hierarchy()

    def _create_root(self, name):
        genre, _ = WikipediaGenre.objects.get_or_create(
            name=name,
            defaults={"slug": slugify(name), "level": 0, "path": name},
        )
        return genre

    def _create_source_root(self, name):
        return WikipediaGenre.objects.create(
            name=name,
            slug=f"{slugify(name)}-source",
            level=0,
            path=name,
        )

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
        if genre.parent_id != parent.id:
            genre.parent = parent
            genre.level = 1
            genre.path = f"{parent.name} > {name}"
            genre.save(update_fields=["parent", "level", "path"])
        return genre

    def _create_base_hierarchy(self):
        action = self._create_root("Action")
        adventure = self._create_root("Adventure")
        role_playing = self._create_root("Role-Playing")
        strategy = self._create_root("Strategy")
        simulation = self._create_root("Simulation")
        shooter = self._create_root("Shooter")
        puzzle_casual = self._create_root("Puzzle & Casual")
        racing_sports = self._create_root("Racing & Sports")

        self._create_child(action, "Platform")
        self._create_child(action, "Fighting")
        self._create_child(adventure, "Action-Adventure")
        self._create_child(adventure, "Interactive Drama")
        self._create_child(adventure, "Point-and-Click")
        self._create_child(role_playing, "Action RPG")
        self._create_child(strategy, "Real-Time Tactics")
        self._create_child(simulation, "Flight Simulation")
        self._create_child(shooter, "Third-Person Shooter")
        self._create_child(puzzle_casual, "Puzzle")
        self._create_child(puzzle_casual, "Music")
        self._create_child(racing_sports, "Racing")
        self._create_child(racing_sports, "Sports")

    def test_forwards_moves_orphan_roots_drops_descriptors_and_normalizes_metadata(
        self,
    ):
        action_rpg_source = self._create_source_root("Action role-playing game")
        first_person_source = self._create_source_root("First-person")
        art_tool_source = self._create_source_root("Art tool")

        game1 = Game.objects.create(name="Game One", rank=1)
        game1.wikipedia_genres.add(action_rpg_source)
        WikipediaGameData.objects.create(
            game=game1,
            page_title="Game One",
            primary_genre="Action role-playing game",
            all_genres="Action role-playing game",
            is_primary=True,
        )
        game1.primary_wikipedia_game_data = WikipediaGameData.objects.get(game=game1)
        game1.save(update_fields=["primary_wikipedia_game_data"])

        third_person_shooter = WikipediaGenre.objects.get(name="Third-Person Shooter")
        game2 = Game.objects.create(name="Game Two", rank=2)
        game2.wikipedia_genres.add(first_person_source, third_person_shooter)
        WikipediaGameData.objects.create(
            game=game2,
            page_title="Game Two",
            primary_genre="First-person",
            all_genres="First-person, Third-person shooter, Action-adventure",
            is_primary=True,
        )
        game2.primary_wikipedia_game_data = WikipediaGameData.objects.get(game=game2)
        game2.save(update_fields=["primary_wikipedia_game_data"])

        game3 = Game.objects.create(name="Game Three", rank=3)
        game3.wikipedia_genres.add(art_tool_source)
        WikipediaGameData.objects.create(
            game=game3,
            page_title="Game Three",
            primary_genre="Art tool",
            all_genres="Art tool",
            is_primary=True,
        )
        game3.primary_wikipedia_game_data = WikipediaGameData.objects.get(game=game3)
        game3.save(update_fields=["primary_wikipedia_game_data"])

        self.migration.forwards(_FakeApps(), None)

        game1.refresh_from_db()
        self.assertEqual(
            set(game1.wikipedia_genres.values_list("name", flat=True)),
            {"Action RPG"},
        )
        game1_metadata = WikipediaGameData.objects.get(game=game1, is_primary=True)
        self.assertEqual(game1_metadata.primary_genre, "Action RPG")
        self.assertEqual(game1_metadata.all_genres, "Action RPG")

        game2.refresh_from_db()
        self.assertEqual(
            set(game2.wikipedia_genres.values_list("name", flat=True)),
            {"Third-Person Shooter"},
        )
        game2_metadata = WikipediaGameData.objects.get(game=game2, is_primary=True)
        self.assertEqual(game2_metadata.primary_genre, "Third-Person Shooter")
        self.assertEqual(
            game2_metadata.all_genres,
            "Third-Person Shooter, Action-Adventure",
        )

        game3.refresh_from_db()
        self.assertEqual(
            set(game3.wikipedia_genres.values_list("name", flat=True)),
            {"Puzzle & Casual"},
        )
        game3_metadata = WikipediaGameData.objects.get(game=game3, is_primary=True)
        self.assertIsNone(game3_metadata.primary_genre)
        self.assertEqual(game3_metadata.all_genres, "")

        self.assertFalse(
            WikipediaGenre.objects.filter(name="Action role-playing game").exists()
        )
        self.assertFalse(WikipediaGenre.objects.filter(name="First-person").exists())
        self.assertFalse(WikipediaGenre.objects.filter(name="Art tool").exists())

    def test_forwards_keeps_only_supported_new_leaf_genres(self):
        auto_battler_source = self._create_source_root("Auto battler")
        turn_based_source = self._create_source_root("Turn-based")
        monster_tamer_source = self._create_source_root("Monster tamer")
        management_sim_source = WikipediaGenre.objects.filter(
            slug=slugify("Management simulation")
        ).first() or WikipediaGenre.objects.create(
            name="Management simulation",
            slug=slugify("Management simulation"),
            level=0,
            path="Management simulation",
        )
        management_sim_source.name = "Management simulation"
        management_sim_source.parent = None
        management_sim_source.level = 0
        management_sim_source.path = "Management simulation"
        management_sim_source.save(update_fields=["name", "parent", "level", "path"])

        vehicle_sim_source = WikipediaGenre.objects.filter(
            slug=slugify("Vehicle simulation")
        ).first() or WikipediaGenre.objects.create(
            name="Vehicle simulation",
            slug=slugify("Vehicle simulation"),
            level=0,
            path="Vehicle simulation",
        )
        vehicle_sim_source.name = "Vehicle simulation"
        vehicle_sim_source.parent = None
        vehicle_sim_source.level = 0
        vehicle_sim_source.path = "Vehicle simulation"
        vehicle_sim_source.save(update_fields=["name", "parent", "level", "path"])

        games = {
            "auto": Game.objects.create(name="Auto", rank=10),
            "turn": Game.objects.create(name="Turn", rank=11),
            "monster": Game.objects.create(name="Monster", rank=12),
            "management": Game.objects.create(name="Management", rank=13),
            "vehicle": Game.objects.create(name="Vehicle", rank=14),
        }
        games["auto"].wikipedia_genres.add(auto_battler_source)
        games["turn"].wikipedia_genres.add(turn_based_source)
        games["monster"].wikipedia_genres.add(monster_tamer_source)
        games["management"].wikipedia_genres.add(management_sim_source)
        games["vehicle"].wikipedia_genres.add(vehicle_sim_source)

        turn_metadata = WikipediaGameData.objects.create(
            game=games["turn"],
            page_title="Turn",
            primary_genre="Turn-based",
            all_genres="Turn-based, Real-time tactics",
            is_primary=True,
        )
        games["turn"].primary_wikipedia_game_data = turn_metadata
        games["turn"].save(update_fields=["primary_wikipedia_game_data"])

        self.migration.forwards(_FakeApps(), None)

        self.assertEqual(
            WikipediaGenre.objects.get(name="Management Simulation").parent.name,
            "Simulation",
        )
        self.assertEqual(
            WikipediaGenre.objects.get(name="Vehicle Simulation").parent.name,
            "Simulation",
        )
        self.assertEqual(
            WikipediaGenre.objects.get(name="Management Simulation").slug,
            "management-simulation",
        )
        self.assertEqual(
            WikipediaGenre.objects.get(name="Vehicle Simulation").slug,
            "vehicle-simulation",
        )

        games["auto"].refresh_from_db()
        self.assertEqual(
            set(games["auto"].wikipedia_genres.values_list("name", flat=True)),
            {"Strategy"},
        )
        games["turn"].refresh_from_db()
        self.assertEqual(
            set(games["turn"].wikipedia_genres.values_list("name", flat=True)),
            {"Strategy"},
        )
        games["monster"].refresh_from_db()
        self.assertEqual(
            set(games["monster"].wikipedia_genres.values_list("name", flat=True)),
            {"Role-Playing"},
        )
        games["management"].refresh_from_db()
        self.assertEqual(
            set(games["management"].wikipedia_genres.values_list("name", flat=True)),
            {"Management Simulation"},
        )
        games["vehicle"].refresh_from_db()
        self.assertEqual(
            set(games["vehicle"].wikipedia_genres.values_list("name", flat=True)),
            {"Vehicle Simulation"},
        )
        self.assertEqual(
            games["turn"].primary_wikipedia_game_data.all_genres,
            "Strategy, Real-Time Tactics",
        )

        self.assertFalse(WikipediaGenre.objects.filter(name="Auto Battler").exists())
        self.assertFalse(WikipediaGenre.objects.filter(name="Turn-Based").exists())
        self.assertFalse(WikipediaGenre.objects.filter(name="Wargame").exists())
        self.assertFalse(WikipediaGenre.objects.filter(name="Monster Tamer").exists())
        self.assertFalse(WikipediaGenre.objects.filter(name="Auto battler").exists())
        self.assertFalse(WikipediaGenre.objects.filter(name="Turn-based").exists())
        self.assertFalse(WikipediaGenre.objects.filter(name="Monster tamer").exists())
        self.assertFalse(
            WikipediaGenre.objects.filter(name="Management simulation").exists()
        )
        self.assertFalse(
            WikipediaGenre.objects.filter(name="Vehicle simulation").exists()
        )
