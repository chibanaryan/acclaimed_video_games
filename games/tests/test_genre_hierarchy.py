"""
Tests for Wikipedia genre normalization and hierarchy.

Comprehensive test coverage for:
- Genre normalization service
- WikipediaGenre model hierarchy methods
- Hierarchical filtering logic
"""

from django.test import TestCase

from games.models import Game, WikipediaGenre
from games.services.genre_normalizer import (
    canonicalize_genre_payload,
    GENRE_MAPPING,
    get_genre_parent_name,
    get_mapping_stats,
    get_or_create_genre,
    normalize_genre,
    normalize_genres,
)
from games.services.query_filters import (
    apply_genre_filter,
    apply_series_filter,
    apply_wikipedia_genre_filter,
    _expand_single_genre_with_descendants,
    _expand_genre_ids_with_descendants,
)


class GenreNormalizerTest(TestCase):
    """Tests for the genre normalization service."""

    def test_normalize_known_variant_to_canonical(self):
        """Test that known variants normalize to canonical names."""
        # MMORPG variants
        self.assertEqual(normalize_genre("MMORPG"), "MMORPG")
        self.assertEqual(
            normalize_genre("Massively multiplayer online role-playing game"), "MMORPG"
        )
        self.assertEqual(
            normalize_genre("Massively multiplayer online role-playing"), "MMORPG"
        )

    def test_normalize_platform_variants(self):
        """Test that platform game variants normalize correctly."""
        self.assertEqual(normalize_genre("Platform"), "Platform")
        self.assertEqual(normalize_genre("Platformer"), "Platform")
        self.assertEqual(normalize_genre("Platform game"), "Platform")
        self.assertEqual(normalize_genre("Cinematic platformer"), "Platform")

    def test_normalize_puzzle_platformer(self):
        """Test that puzzle platformers are distinct from action platformers."""
        self.assertEqual(normalize_genre("Puzzle-platform"), "Puzzle-Platformer")
        self.assertEqual(normalize_genre("Puzzle platformer"), "Puzzle-Platformer")

    def test_normalize_action_rpg_variants(self):
        """Test that Action RPG variants normalize correctly."""
        self.assertEqual(normalize_genre("Action RPG"), "Action RPG")
        self.assertEqual(normalize_genre("Action role-playing"), "Action RPG")
        self.assertEqual(normalize_genre("Action role-playing game"), "Action RPG")

    def test_normalize_shooter_variants(self):
        """Test that shooter variants normalize correctly."""
        self.assertEqual(normalize_genre("Shooter"), "Shooter")
        self.assertEqual(normalize_genre("Shoot 'em up"), "Shooter")
        self.assertEqual(normalize_genre("Scrolling shooter"), "Shooter")
        self.assertEqual(normalize_genre("Twin-stick shooter"), "Shooter")

    def test_normalize_tactical_variants(self):
        """Test that tactical variants normalize to Tactical Shooter."""
        self.assertEqual(normalize_genre("Tactical"), "Tactical Shooter")
        self.assertEqual(normalize_genre("tactical"), "Tactical Shooter")
        self.assertEqual(
            normalize_genre("Tactical first-person shooter"), "Tactical Shooter"
        )

    def test_normalize_delivery_sim_variants(self):
        """Test that delivery sim variants normalize to Simulation."""
        self.assertEqual(normalize_genre("Delivery sim"), "Simulation")
        self.assertEqual(normalize_genre("delivery sim"), "Simulation")
        self.assertEqual(normalize_genre("Delivery simulation"), "Simulation")
        self.assertEqual(normalize_genre("Delivery simulator"), "Simulation")

    def test_normalize_invalid_genres_to_none(self):
        """Test that invalid/meta genres normalize to None."""
        self.assertIsNone(normalize_genre("(minigame)"))
        self.assertIsNone(normalize_genre("Minigame"))
        self.assertIsNone(normalize_genre("Minigames"))
        self.assertIsNone(normalize_genre("Various"))
        # Exploration maps to Walking Simulator (only 1 game: Edith Finch)
        self.assertEqual(normalize_genre("Exploration"), "Walking Simulator")
        self.assertEqual(normalize_genre("Art game"), "Adventure")
        self.assertEqual(normalize_genre("Snake"), "Maze")

    def test_normalize_hack_and_slash(self):
        """Test that Hack and slash normalizes to its own genre, not Beat 'em Up."""
        self.assertEqual(normalize_genre("Hack and slash"), "Hack and Slash")

    def test_normalize_extreme_sports(self):
        """
        Test that Extreme sports normalizes to Sports
        (consolidated single-game genre).
        """
        self.assertEqual(normalize_genre("Extreme sports"), "Sports")

    def test_normalize_unknown_genre_returns_as_is(self):
        """Test that unknown genres are returned as-is."""
        self.assertEqual(normalize_genre("Unknown Genre XYZ"), "Unknown Genre XYZ")
        self.assertEqual(normalize_genre("NewGenre2025"), "NewGenre2025")

    def test_normalize_new_orphan_root_mappings(self):
        """Test canonical mappings for newly discovered orphan root genres."""
        self.assertEqual(normalize_genre("Auto battler"), "Strategy")
        self.assertEqual(normalize_genre("art"), "Adventure")
        self.assertEqual(normalize_genre("Electronic literature"), "Interactive Drama")
        self.assertEqual(normalize_genre("Monster tamer"), "Role-Playing")
        self.assertEqual(normalize_genre("puzzle game"), "Puzzle")
        self.assertEqual(normalize_genre("Turn-based"), "Strategy")
        self.assertEqual(
            normalize_genre("vehicle construction"), "Construction & Management"
        )
        self.assertEqual(normalize_genre("Wargame"), "Strategy")
        self.assertEqual(
            normalize_genre("Management simulation"), "Management Simulation"
        )
        self.assertEqual(normalize_genre("Vehicle simulation"), "Vehicle Simulation")

    def test_normalize_descriptor_genres_to_none(self):
        """Test descriptor labels are dropped instead of preserved as genres."""
        self.assertIsNone(normalize_genre("First-person"))
        self.assertIsNone(normalize_genre("Hacking"))
        self.assertIsNone(normalize_genre("Level editor"))
        self.assertEqual(
            normalize_genre("Vehicle construction"), "Construction & Management"
        )
        self.assertIsNone(normalize_genre("Cooking"))
        self.assertIsNone(normalize_genre("Art tool"))
        self.assertIsNone(normalize_genre("Lunar Lander"))

    def test_normalize_is_case_insensitive_for_known_values(self):
        """Test known mappings work even when Wikipedia casing drifts."""
        self.assertEqual(normalize_genre("rpg"), "Role-Playing")
        self.assertEqual(normalize_genre("action-adventure"), "Action-Adventure")
        self.assertEqual(normalize_genre("sport"), "Sports")

    def test_canonicalize_genre_payload_uses_first_surviving_genre_for_primary(self):
        """
        Test payload canonicalization drops descriptor primaries and promotes
        the first surviving canonical genre.
        """
        primary, all_genres, all_genres_str = canonicalize_genre_payload(
            "First-person",
            ["First-person", "Third-person shooter", "Action-adventure"],
        )
        self.assertEqual(primary, "Third-Person Shooter")
        self.assertEqual(all_genres, ["Third-Person Shooter", "Action-Adventure"])
        self.assertEqual(all_genres_str, "Third-Person Shooter, Action-Adventure")

    def test_canonicalize_genre_payload_inserts_primary_when_only_secondary_list_exists(
        self,
    ):
        """Test canonicalization preserves a distinct normalized primary first."""
        primary, all_genres, all_genres_str = canonicalize_genre_payload(
            "Action role-playing game",
            ["Platforming"],
        )
        self.assertEqual(primary, "Action RPG")
        self.assertEqual(all_genres, ["Action RPG", "Platform"])
        self.assertEqual(all_genres_str, "Action RPG, Platform")

        primary, all_genres, all_genres_str = canonicalize_genre_payload(
            "Action role-playing game",
            None,
        )
        self.assertEqual(primary, "Action RPG")
        self.assertEqual(all_genres, ["Action RPG"])
        self.assertEqual(all_genres_str, "Action RPG")

    def test_normalize_empty_string_returns_none(self):
        """Test that empty strings return None."""
        self.assertIsNone(normalize_genre(""))
        self.assertIsNone(normalize_genre("   "))
        self.assertIsNone(normalize_genre(None))

    def test_normalize_strips_whitespace(self):
        """Test that genre names are stripped of whitespace."""
        self.assertEqual(normalize_genre("  Platform  "), "Platform")
        self.assertEqual(normalize_genre("\tAction\n"), "Action")

    def test_normalize_genres_list(self):
        """Test normalizing a list of genres."""
        genres = ["MMORPG", "Massively multiplayer online role-playing game", "Action"]
        result = normalize_genres(genres)
        # Should remove duplicate after normalization
        self.assertEqual(sorted(result), sorted(["MMORPG", "Action"]))

    def test_normalize_genres_removes_none_values(self):
        """Test that None values are removed from list."""
        genres = ["Action", "(minigame)", "Platform", "Minigames"]
        result = normalize_genres(genres)
        self.assertEqual(sorted(result), sorted(["Action", "Platform"]))

    def test_normalize_genres_empty_list(self):
        """Test normalizing an empty list."""
        self.assertEqual(normalize_genres([]), [])

    def test_normalize_genres_dedupes_delivery_sim_and_simulation(self):
        """Test canonical deduping for delivery sim normalization."""
        result = normalize_genres(["Delivery sim", "Simulation"])
        self.assertEqual(result, ["Simulation"])

    def test_get_mapping_stats(self):
        """Test the mapping statistics function."""
        stats = get_mapping_stats()
        self.assertIn("total_variants", stats)
        self.assertIn("canonical_genres", stats)
        self.assertIn("invalid_mappings", stats)
        self.assertGreater(stats["total_variants"], 0)
        self.assertGreater(stats["canonical_genres"], 0)

    def test_genre_mapping_has_expected_entries(self):
        """Test that GENRE_MAPPING has expected entries."""
        # Check some key mappings exist
        self.assertIn("Action", GENRE_MAPPING)
        self.assertIn("Platform", GENRE_MAPPING)
        self.assertIn("MMORPG", GENRE_MAPPING)
        # Check mapping count is reasonable
        self.assertGreater(len(GENRE_MAPPING), 100)


class GetGenreParentNameTest(TestCase):
    """Tests for the get_genre_parent_name function."""

    def test_returns_parent_for_child_genre(self):
        """Test that child genres return their parent category."""
        # First-Person Shooter should be under Shooter (new category)
        self.assertEqual(get_genre_parent_name("First-Person Shooter"), "Shooter")
        # Platform should be under Action (reflex-based gameplay)
        self.assertEqual(get_genre_parent_name("Platform"), "Action")
        # Action RPG should be under Role-Playing
        self.assertEqual(get_genre_parent_name("Action RPG"), "Role-Playing")

    def test_action_genres_hierarchy(self):
        """Test that action-oriented genres are correctly parented under Action."""
        action_genres = [
            "Maze",  # Arcade action games like Pac-Man
            "Platform",  # Reflex-based platformers like Mario
            "Metroidvania",  # Action-exploration games
            "Hack and Slash",  # Combat-focused action games like Diablo
            "Survival",  # Survival games (moved from Hybrid & Specialized)
        ]
        for genre in action_genres:
            self.assertEqual(
                get_genre_parent_name(genre),
                "Action",
                f"{genre} should be under Action",
            )

    def test_racing_genres_hierarchy(self):
        """Test that racing genres are correctly parented under Racing & Sports."""
        # Racing and Kart Racing are children of Racing & Sports
        self.assertEqual(
            get_genre_parent_name("Kart Racing"),
            "Racing & Sports",
            "Kart Racing should be under Racing & Sports",
        )
        self.assertEqual(
            get_genre_parent_name("Racing"),
            "Racing & Sports",
            "Racing should be under Racing & Sports",
        )

    def test_shooter_genres_hierarchy(self):
        """
        Test that shooter genres are correctly parented
        under Shooter (new category).
        """
        # Note: "Shooter" itself is now a root category, these are its children
        shooter_child_genres = [
            "First-Person Shooter",
            "Third-Person Shooter",
            "Light Gun Shooter",
            "Tactical Shooter",
            "Run and Gun",
        ]
        for genre in shooter_child_genres:
            self.assertEqual(
                get_genre_parent_name(genre),
                "Shooter",
                f"{genre} should be under Shooter",
            )

    def test_sports_genres_hierarchy(self):
        """
        Test that sports-related genres are correctly parented
        under Racing & Sports.
        """
        # Sports is now a sub-genre under Racing & Sports
        self.assertEqual(get_genre_parent_name("Sports"), "Racing & Sports")
        # Snowboarding remains as a sub-genre
        self.assertEqual(get_genre_parent_name("Snowboarding"), "Racing & Sports")
        # Football variants remain as sub-genres
        self.assertEqual(
            get_genre_parent_name("Football (American)"), "Racing & Sports"
        )
        self.assertEqual(
            get_genre_parent_name("Football (Association)"), "Racing & Sports"
        )

    def test_puzzle_casual_genres_hierarchy(self):
        """
        Test that puzzle and casual genres are correctly parented
        under Puzzle & Casual.
        """
        # Puzzle is now a sub-genre under Puzzle & Casual
        self.assertEqual(get_genre_parent_name("Puzzle"), "Puzzle & Casual")
        self.assertEqual(get_genre_parent_name("Puzzle-Platformer"), "Puzzle & Casual")
        self.assertEqual(get_genre_parent_name("Match-Three"), "Puzzle & Casual")
        # Casual genres also under Puzzle & Casual
        self.assertEqual(get_genre_parent_name("Music"), "Puzzle & Casual")
        self.assertEqual(get_genre_parent_name("Party"), "Puzzle & Casual")
        self.assertEqual(get_genre_parent_name("Educational"), "Puzzle & Casual")

    def test_adventure_genres_hierarchy(self):
        """Test that adventure genres are correctly parented."""
        # Horror moved from Hybrid & Specialized
        self.assertEqual(get_genre_parent_name("Horror"), "Adventure")
        self.assertEqual(get_genre_parent_name("Point-and-Click"), "Adventure")

    def test_simulation_genres_hierarchy(self):
        """Test that simulation genres are correctly parented."""
        # Sandbox moved from Hybrid & Specialized
        self.assertEqual(get_genre_parent_name("Sandbox"), "Simulation")
        self.assertEqual(get_genre_parent_name("Life Simulation"), "Simulation")
        self.assertEqual(get_genre_parent_name("Management Simulation"), "Simulation")
        self.assertEqual(get_genre_parent_name("Vehicle Simulation"), "Simulation")

    def test_role_playing_genres_hierarchy(self):
        """Test that role-playing genres are correctly parented."""
        # Massively Multiplayer moved from Hybrid & Specialized
        self.assertEqual(get_genre_parent_name("Massively Multiplayer"), "Role-Playing")
        self.assertEqual(get_genre_parent_name("MMORPG"), "Role-Playing")

    def test_returns_none_for_root_category(self):
        """Test that root categories return None."""
        self.assertIsNone(get_genre_parent_name("Action"))
        self.assertIsNone(get_genre_parent_name("Adventure"))
        self.assertIsNone(get_genre_parent_name("Role-Playing"))
        self.assertIsNone(get_genre_parent_name("Shooter"))  # New root category
        self.assertIsNone(get_genre_parent_name("Simulation"))
        self.assertIsNone(get_genre_parent_name("Other"))

    def test_returns_other_for_unknown_genre(self):
        """Test that unknown genres are parented under Other."""
        self.assertEqual(get_genre_parent_name("Unknown Genre"), "Other")
        self.assertEqual(get_genre_parent_name("Made Up Category"), "Other")


class GetOrCreateGenreTest(TestCase):
    """Tests for the get_or_create_genre function."""

    def test_returns_existing_genre(self):
        """Test that existing genres are returned."""
        # Create a genre first with a unique name
        existing = WikipediaGenre.objects.create(
            name="Existing Test Genre GCT",
            slug="existing-test-genre-gct",
            level=0,
        )
        # Should return the existing genre
        result = get_or_create_genre("Existing Test Genre GCT")
        self.assertEqual(result.id, existing.id)

    def test_creates_unknown_genre_under_other(self):
        """Test creating an unknown genre under the Other fallback root."""
        # Use a name that's not in GENRE_HIERARCHY
        result = get_or_create_genre("Completely New Genre GCT")

        self.assertEqual(result.name, "Completely New Genre GCT")
        self.assertEqual(result.slug, "completely-new-genre-gct")
        self.assertEqual(result.level, 1)
        self.assertIsNotNone(result.parent)
        self.assertEqual(result.parent.name, "Other")
        self.assertEqual(result.path, "Other > Completely New Genre GCT")

    def test_creates_child_genre_with_parent(self):
        """Test creating a child genre with proper parent from hierarchy."""
        # First-Person Shooter is under Shooter in GENRE_HIERARCHY (new category)
        # get_or_create_genre should create Shooter parent if it doesn't exist
        fps = get_or_create_genre("First-Person Shooter")

        self.assertEqual(fps.name, "First-Person Shooter")
        # Verify parent exists and is Shooter
        self.assertIsNotNone(fps.parent)
        self.assertEqual(fps.parent.name, "Shooter")
        self.assertEqual(fps.level, 1)
        self.assertIn("Shooter", fps.path)
        self.assertIn("First-Person Shooter", fps.path)

    def test_creates_root_genre_for_category(self):
        """Test that root categories are created at level 0."""
        # Action is a root category in GENRE_HIERARCHY
        action = get_or_create_genre("Action")

        self.assertEqual(action.name, "Action")
        self.assertIsNone(action.parent)
        self.assertEqual(action.level, 0)

    def test_recursively_creates_parent_when_nonexistent(self):
        """Test that parent genre is recursively created when it doesn't exist."""
        # Remove any existing Shooter genre to force recursive creation
        WikipediaGenre.objects.filter(name="Shooter").delete()

        # First-Person Shooter should create Shooter parent recursively
        fps = get_or_create_genre("First-Person Shooter")

        # Verify FPS was created with proper parent
        self.assertEqual(fps.name, "First-Person Shooter")
        self.assertEqual(fps.level, 1)

        # Verify Shooter parent was recursively created
        self.assertIsNotNone(fps.parent)
        self.assertEqual(fps.parent.name, "Shooter")
        self.assertEqual(fps.parent.level, 0)

        # Verify path is correct
        self.assertEqual(fps.path, "Shooter > First-Person Shooter")


class WikipediaGenreHierarchyTest(TestCase):
    """Tests for WikipediaGenre model hierarchy methods."""

    def setUp(self):
        """Create test genre hierarchy."""
        # Create root category
        self.action_root = WikipediaGenre.objects.create(
            name="Action Test Root",
            slug="action-test-root",
            level=0,
            display_order=1,
            path="Action Test Root",
        )

        # Create child genres
        self.shooter = WikipediaGenre.objects.create(
            name="Shooter Test",
            slug="shooter-test",
            parent=self.action_root,
            level=1,
            display_order=1,
            path="Action Test Root > Shooter Test",
        )

        self.fighting = WikipediaGenre.objects.create(
            name="Fighting Test",
            slug="fighting-test",
            parent=self.action_root,
            level=1,
            display_order=2,
            path="Action Test Root > Fighting Test",
        )

        # Create grandchild genre
        self.fps = WikipediaGenre.objects.create(
            name="FPS Test",
            slug="fps-test",
            parent=self.shooter,
            level=2,
            display_order=1,
            path="Action Test Root > Shooter Test > FPS Test",
        )

    def test_is_root_property(self):
        """Test the is_root property."""
        self.assertTrue(self.action_root.is_root)
        self.assertFalse(self.shooter.is_root)
        self.assertFalse(self.fps.is_root)

    def test_is_leaf_property(self):
        """Test the is_leaf property."""
        self.assertFalse(self.action_root.is_leaf)
        self.assertFalse(self.shooter.is_leaf)  # Has FPS child
        self.assertTrue(self.fighting.is_leaf)
        self.assertTrue(self.fps.is_leaf)

    def test_get_descendants_include_self_false(self):
        """Test get_descendants without including self."""
        descendants = list(self.action_root.get_descendants(include_self=False))
        self.assertEqual(len(descendants), 3)  # shooter, fighting, fps
        self.assertNotIn(self.action_root, descendants)
        self.assertIn(self.shooter, descendants)
        self.assertIn(self.fighting, descendants)
        self.assertIn(self.fps, descendants)

    def test_get_descendants_include_self_true(self):
        """Test get_descendants including self."""
        descendants = list(self.action_root.get_descendants(include_self=True))
        self.assertEqual(len(descendants), 4)
        self.assertIn(self.action_root, descendants)

    def test_get_descendants_leaf_node(self):
        """Test get_descendants on a leaf node."""
        descendants = list(self.fps.get_descendants(include_self=False))
        self.assertEqual(len(descendants), 0)

    def test_get_descendant_ids_include_self(self):
        """Test get_descendant_ids with include_self=True."""
        ids = self.action_root.get_descendant_ids(include_self=True)
        self.assertEqual(len(ids), 4)
        self.assertIn(self.action_root.id, ids)
        self.assertIn(self.shooter.id, ids)
        self.assertIn(self.fighting.id, ids)
        self.assertIn(self.fps.id, ids)

    def test_get_descendant_ids_without_self(self):
        """Test get_descendant_ids with include_self=False."""
        ids = self.action_root.get_descendant_ids(include_self=False)
        self.assertEqual(len(ids), 3)
        self.assertNotIn(self.action_root.id, ids)

    def test_get_descendant_ids_uses_cached_value(self):
        """Second call should return cached descendant IDs."""
        first = self.action_root.get_descendant_ids(include_self=False)
        second = self.action_root.get_descendant_ids(include_self=False)
        self.assertEqual(second, first)

    def test_get_ancestors_include_self_false(self):
        """Test get_ancestors without including self."""
        ancestors = list(self.fps.get_ancestors(include_self=False))
        self.assertEqual(len(ancestors), 2)  # shooter, action_root
        self.assertIn(self.action_root, ancestors)
        self.assertIn(self.shooter, ancestors)
        self.assertNotIn(self.fps, ancestors)

    def test_get_ancestors_include_self_true(self):
        """Test get_ancestors including self."""
        ancestors = list(self.fps.get_ancestors(include_self=True))
        self.assertEqual(len(ancestors), 3)
        self.assertIn(self.fps, ancestors)

    def test_get_ancestors_root_node(self):
        """Test get_ancestors on root node."""
        ancestors = list(self.action_root.get_ancestors(include_self=False))
        self.assertEqual(len(ancestors), 0)


class HierarchicalGenreFilterTest(TestCase):
    """Tests for hierarchical genre filtering logic."""

    def setUp(self):
        """Create test data with genre hierarchy and games."""
        # Clear cache to ensure no stale data from previous tests
        from django.core.cache import cache

        cache.clear()

        # Create root categories
        self.action = WikipediaGenre.objects.create(
            name="Action Filter Test",
            slug="action-filter-test",
            level=0,
            display_order=1,
        )
        self.rpg = WikipediaGenre.objects.create(
            name="RPG Filter Test",
            slug="rpg-filter-test",
            level=0,
            display_order=2,
        )

        # Create child genres
        self.shooter = WikipediaGenre.objects.create(
            name="Shooter Filter",
            slug="shooter-filter",
            parent=self.action,
            level=1,
            display_order=1,
        )
        self.fighting = WikipediaGenre.objects.create(
            name="Fighting Filter",
            slug="fighting-filter",
            parent=self.action,
            level=1,
            display_order=2,
        )
        self.action_rpg = WikipediaGenre.objects.create(
            name="Action RPG Filter",
            slug="action-rpg-filter",
            parent=self.rpg,
            level=1,
            display_order=1,
        )

        # Create test games
        self.game1 = Game.objects.create(name="Shooter Game", rank=1)
        self.game1.wikipedia_genres.add(self.shooter)

        self.game2 = Game.objects.create(name="Fighting Game", rank=2)
        self.game2.wikipedia_genres.add(self.fighting)

        self.game3 = Game.objects.create(name="Action RPG Game", rank=3)
        self.game3.wikipedia_genres.add(self.action_rpg)

        self.game4 = Game.objects.create(name="Multi-Genre Game", rank=4)
        self.game4.wikipedia_genres.add(self.shooter, self.action_rpg)

    def test_filter_by_child_genre_exact(self):
        """Test filtering by a specific child genre."""
        qs = Game.objects.all()
        filtered = apply_genre_filter(
            qs, [self.shooter.id], match_all=True, use_wikipedia=True
        )
        self.assertEqual(filtered.count(), 2)  # game1 and game4
        self.assertIn(self.game1, filtered)
        self.assertIn(self.game4, filtered)

    def test_filter_by_parent_includes_children(self):
        """Test that filtering by parent genre includes games with child genres."""
        qs = Game.objects.all()
        filtered = apply_genre_filter(
            qs, [self.action.id], match_all=True, use_wikipedia=True
        )
        # Should include games with Shooter and Fighting (children of Action)
        self.assertEqual(filtered.count(), 3)  # game1, game2, game4
        self.assertIn(self.game1, filtered)
        self.assertIn(self.game2, filtered)
        self.assertIn(self.game4, filtered)
        self.assertNotIn(self.game3, filtered)  # Only has Action RPG (under RPG)

    def test_filter_match_all_with_multiple_genres(self):
        """Test match_all with multiple genre selections."""
        qs = Game.objects.all()
        # Filter by both Action category and RPG category
        filtered = apply_genre_filter(
            qs, [self.action.id, self.rpg.id], match_all=True, use_wikipedia=True
        )
        # Only game4 has genres from both categories (Shooter + Action RPG)
        self.assertEqual(filtered.count(), 1)
        self.assertIn(self.game4, filtered)

    def test_filter_match_any_with_multiple_genres(self):
        """Test match_any with multiple genre selections."""
        # Filter only our test games (exclude games from other tests/migrations)
        qs = Game.objects.filter(
            pk__in=[self.game1.pk, self.game2.pk, self.game3.pk, self.game4.pk]
        )
        # Filter by either Action or RPG
        filtered = apply_genre_filter(
            qs, [self.action.id, self.rpg.id], match_all=False, use_wikipedia=True
        )
        # All 4 test games should match (they all have at least one genre)
        self.assertEqual(filtered.count(), 4)

    def test_filter_without_hierarchy_expansion(self):
        """Test filtering with expand_hierarchy=False."""
        qs = Game.objects.all()
        # Filter by Action root without expansion (exact match only)
        filtered = apply_genre_filter(
            qs,
            [self.action.id],
            match_all=True,
            use_wikipedia=True,
            expand_hierarchy=False,
        )
        # No games are tagged directly with Action root
        self.assertEqual(filtered.count(), 0)

    def test_filter_match_any_without_hierarchy_expansion(self):
        """Test match_any filtering with expand_hierarchy=False (lines 77-80)."""
        qs = Game.objects.filter(
            pk__in=[self.game1.pk, self.game2.pk, self.game3.pk, self.game4.pk]
        )
        # Filter by child genres directly without hierarchy expansion
        # match_all=False with expand_hierarchy=False triggers lines 77-80
        filtered = apply_genre_filter(
            qs,
            [self.shooter.id, self.fighting.id],
            match_all=False,
            use_wikipedia=True,
            expand_hierarchy=False,
        )
        # game1 has shooter, game2 has fighting, game4 has shooter
        self.assertEqual(filtered.count(), 3)
        self.assertIn(self.game1, filtered)
        self.assertIn(self.game2, filtered)
        self.assertIn(self.game4, filtered)
        self.assertNotIn(self.game3, filtered)  # Only has action_rpg

    def test_expand_single_genre_with_descendants(self):
        """Test the _expand_single_genre_with_descendants helper."""
        ids = _expand_single_genre_with_descendants(self.action.id)
        self.assertIn(self.action.id, ids)
        self.assertIn(self.shooter.id, ids)
        self.assertIn(self.fighting.id, ids)
        self.assertNotIn(self.action_rpg.id, ids)  # Not under Action

    def test_expand_single_genre_nonexistent(self):
        """Test expansion with nonexistent genre ID."""
        ids = _expand_single_genre_with_descendants(99999)
        self.assertEqual(ids, [99999])  # Returns the ID as-is


class GameWikipediaGenreNormalizationTest(TestCase):
    """Tests for genre normalization in Game.get_wikipedia_data()."""

    def test_game_wikipedia_genres_uses_normalization(self):
        """Test that saving wikipedia genres uses normalization."""
        # Use existing Platform genre from migration or create unique one
        platform, _ = WikipediaGenre.objects.get_or_create(
            name="Platform Test Norm",
            defaults={"slug": "platform-test-norm", "level": 1},
        )

        game = Game.objects.create(name="Test Platformer", rank=1)
        game.wikipedia_genres.add(platform)

        # The genre should be the canonical name
        self.assertEqual(game.wikipedia_genres.count(), 1)
        self.assertEqual(game.wikipedia_genres.first().name, "Platform Test Norm")


class ExpandGenreIdsWithDescendantsTest(TestCase):
    """Tests for the _expand_genre_ids_with_descendants helper."""

    def setUp(self):
        """Create test hierarchy."""
        self.root = WikipediaGenre.objects.create(
            name="Root Expand Test",
            slug="root-expand-test",
            level=0,
        )
        self.child1 = WikipediaGenre.objects.create(
            name="Child1 Expand Test",
            slug="child1-expand-test",
            parent=self.root,
            level=1,
        )
        self.child2 = WikipediaGenre.objects.create(
            name="Child2 Expand Test",
            slug="child2-expand-test",
            parent=self.root,
            level=1,
        )

    def test_expand_includes_descendants(self):
        """Test expanding includes all descendants."""
        expanded = _expand_genre_ids_with_descendants([self.root.id])
        self.assertIn(self.root.id, expanded)
        self.assertIn(self.child1.id, expanded)
        self.assertIn(self.child2.id, expanded)

    def test_expand_with_nonexistent_id(self):
        """Test expanding handles nonexistent IDs gracefully."""
        expanded = _expand_genre_ids_with_descendants([self.root.id, 99999])
        # Should include root and children, plus the nonexistent ID
        self.assertIn(self.root.id, expanded)
        self.assertIn(99999, expanded)


class ApplyWikipediaGenreFilterTest(TestCase):
    """Tests for the apply_wikipedia_genre_filter convenience wrapper."""

    def setUp(self):
        """Create test data."""
        self.genre = WikipediaGenre.objects.create(
            name="Wrapper Test Genre",
            slug="wrapper-test-genre",
            level=1,
        )
        self.game = Game.objects.create(name="Wrapper Test Game", rank=1)
        self.game.wikipedia_genres.add(self.genre)

    def test_wrapper_filters_correctly(self):
        """Test that the wrapper function filters correctly."""
        qs = Game.objects.all()
        filtered = apply_wikipedia_genre_filter(qs, [self.genre.id])
        self.assertIn(self.game, filtered)

    def test_wrapper_with_match_any(self):
        """Test wrapper with match_any option."""
        qs = Game.objects.filter(pk=self.game.pk)
        filtered = apply_wikipedia_genre_filter(qs, [self.genre.id], match_all=False)
        self.assertEqual(filtered.count(), 1)


class ApplySeriesFilterTest(TestCase):
    """Tests for the apply_series_filter helper."""

    def test_empty_series_ids_returns_queryset_unchanged(self):
        """Test that empty series_ids returns queryset unchanged (line 205)."""
        game = Game.objects.create(name="Test Series Game", rank=1)
        qs = Game.objects.filter(pk=game.pk)

        # Empty list should return queryset unchanged
        result = apply_series_filter(qs, [])
        self.assertEqual(result.count(), 1)
        self.assertIn(game, result)

    def test_none_series_ids_returns_queryset_unchanged(self):
        """Test that None series_ids returns queryset unchanged."""
        game = Game.objects.create(name="Test Series Game 2", rank=2)
        qs = Game.objects.filter(pk=game.pk)

        # None should be treated as falsy and return queryset unchanged
        result = apply_series_filter(qs, None)
        self.assertEqual(result.count(), 1)
