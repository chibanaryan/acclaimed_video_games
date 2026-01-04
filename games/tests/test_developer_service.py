"""Tests for developer hierarchy caching service."""

from django.core.cache import cache
from django.test import TestCase

from games.models import Developer, Game
from games.services.developer_service import (
    DEVELOPER_HIERARCHY_CACHE_KEY,
    _collect_all_descendants,
    _compute_hierarchy,
    _find_root,
    get_developer_hierarchy,
    invalidate_developer_cache,
)


class DeveloperServiceTests(TestCase):
    """Tests for developer hierarchy service."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_get_developer_hierarchy_caches_result(self):
        """Test that hierarchy data is cached after first call."""
        # Create a developer
        dev = Developer.objects.create(name="Test Dev", igdb_id=1)

        # First call - should compute and cache
        result1 = get_developer_hierarchy()
        self.assertIn("subsidiary_ids", result1)
        self.assertIn(dev.id, result1["subsidiary_ids"])

        # Second call - should return cached result
        result2 = get_developer_hierarchy()
        self.assertEqual(result1, result2)

    def test_get_developer_hierarchy_returns_from_cache(self):
        """Test that cached data is returned without recomputing."""
        # Pre-populate cache with mock data
        mock_data = {"test_key": "test_value"}
        cache.set(DEVELOPER_HIERARCHY_CACHE_KEY, mock_data)

        result = get_developer_hierarchy()
        self.assertEqual(result, mock_data)

    def test_invalidate_developer_cache(self):
        """Test that cache is cleared when invalidated."""
        # Set some cache data
        cache.set(DEVELOPER_HIERARCHY_CACHE_KEY, {"data": "cached"})
        self.assertIsNotNone(cache.get(DEVELOPER_HIERARCHY_CACHE_KEY))

        # Invalidate
        invalidate_developer_cache()

        # Should be cleared
        self.assertIsNone(cache.get(DEVELOPER_HIERARCHY_CACHE_KEY))


class ComputeHierarchyTests(TestCase):
    """Tests for _compute_hierarchy function."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_compute_hierarchy_empty_database(self):
        """Test hierarchy computation with no developers."""
        result = _compute_hierarchy()

        self.assertEqual(result["subsidiary_ids"], {})
        self.assertEqual(result["root_developer_id"], {})
        self.assertEqual(result["games_by_dev"], {})
        self.assertEqual(result["recursive_game_counts"], {})
        self.assertEqual(result["recursive_game_ids"], {})
        self.assertEqual(result["recursive_subsidiary_counts"], {})
        self.assertEqual(result["top_game_id"], {})

    def test_compute_hierarchy_single_developer(self):
        """Test hierarchy with a single developer."""
        dev = Developer.objects.create(name="Solo Dev", igdb_id=1)

        result = _compute_hierarchy()

        # Root developer should be itself
        self.assertEqual(result["root_developer_id"][dev.id], dev.id)
        # No subsidiaries
        self.assertEqual(result["subsidiary_ids"][dev.id], set())
        # No games
        self.assertEqual(result["recursive_game_counts"][dev.id], 0)
        self.assertEqual(result["top_game_id"][dev.id], None)

    def test_compute_hierarchy_with_parent_child(self):
        """Test hierarchy with parent-child relationship."""
        parent = Developer.objects.create(name="Parent Corp", igdb_id=1)
        child = Developer.objects.create(name="Child Studio", igdb_id=2, parent=parent)

        result = _compute_hierarchy()

        # Parent should have child as subsidiary
        self.assertIn(child.id, result["subsidiary_ids"][parent.id])
        # Child should have no subsidiaries
        self.assertEqual(result["subsidiary_ids"][child.id], set())
        # Both should have parent as root
        self.assertEqual(result["root_developer_id"][parent.id], parent.id)
        self.assertEqual(result["root_developer_id"][child.id], parent.id)
        # Parent should have 1 subsidiary count
        self.assertEqual(result["recursive_subsidiary_counts"][parent.id], 1)
        self.assertEqual(result["recursive_subsidiary_counts"][child.id], 0)

    def test_compute_hierarchy_with_games(self):
        """Test hierarchy with games assigned to developers."""
        dev = Developer.objects.create(name="Game Studio", igdb_id=1)
        game1 = Game.objects.create(name="Game 1", rank=10, igdb_id=100)
        game2 = Game.objects.create(name="Game 2", rank=5, igdb_id=101)
        game1.developers.add(dev)
        game2.developers.add(dev)

        result = _compute_hierarchy()

        # Developer should have 2 games
        self.assertEqual(result["recursive_game_counts"][dev.id], 2)
        self.assertEqual(len(result["recursive_game_ids"][dev.id]), 2)
        self.assertIn(game1.id, result["recursive_game_ids"][dev.id])
        self.assertIn(game2.id, result["recursive_game_ids"][dev.id])
        # Top game should be the one with better rank (game2, rank=5)
        self.assertEqual(result["top_game_id"][dev.id], game2.id)

    def test_compute_hierarchy_recursive_game_counting(self):
        """Test that parent includes subsidiary games in count."""
        parent = Developer.objects.create(name="Parent", igdb_id=1)
        child = Developer.objects.create(name="Child", igdb_id=2, parent=parent)

        parent_game = Game.objects.create(name="Parent Game", rank=1, igdb_id=100)
        child_game = Game.objects.create(name="Child Game", rank=2, igdb_id=101)

        parent_game.developers.add(parent)
        child_game.developers.add(child)

        result = _compute_hierarchy()

        # Parent should have 2 games (own + child's)
        self.assertEqual(result["recursive_game_counts"][parent.id], 2)
        self.assertIn(parent_game.id, result["recursive_game_ids"][parent.id])
        self.assertIn(child_game.id, result["recursive_game_ids"][parent.id])
        # Child should only have its own game
        self.assertEqual(result["recursive_game_counts"][child.id], 1)
        self.assertIn(child_game.id, result["recursive_game_ids"][child.id])

    def test_compute_hierarchy_top_game_from_subsidiary(self):
        """Test that top game can come from a subsidiary."""
        parent = Developer.objects.create(name="Parent", igdb_id=1)
        child = Developer.objects.create(name="Child", igdb_id=2, parent=parent)

        parent_game = Game.objects.create(name="Parent Game", rank=100, igdb_id=100)
        child_game = Game.objects.create(name="Child Game", rank=1, igdb_id=101)

        parent_game.developers.add(parent)
        child_game.developers.add(child)

        result = _compute_hierarchy()

        # Parent's top game should be child's game (better rank)
        self.assertEqual(result["top_game_id"][parent.id], child_game.id)

    def test_compute_hierarchy_deep_nesting(self):
        """Test hierarchy with multiple levels of nesting."""
        root = Developer.objects.create(name="Root", igdb_id=1)
        mid = Developer.objects.create(name="Mid", igdb_id=2, parent=root)
        leaf = Developer.objects.create(name="Leaf", igdb_id=3, parent=mid)

        result = _compute_hierarchy()

        # Root should have mid and leaf as subsidiaries
        self.assertIn(mid.id, result["subsidiary_ids"][root.id])
        self.assertIn(leaf.id, result["subsidiary_ids"][root.id])
        self.assertEqual(result["recursive_subsidiary_counts"][root.id], 2)

        # Mid should only have leaf as subsidiary
        self.assertIn(leaf.id, result["subsidiary_ids"][mid.id])
        self.assertNotIn(root.id, result["subsidiary_ids"][mid.id])
        self.assertEqual(result["recursive_subsidiary_counts"][mid.id], 1)

        # Leaf should have no subsidiaries
        self.assertEqual(result["subsidiary_ids"][leaf.id], set())
        self.assertEqual(result["recursive_subsidiary_counts"][leaf.id], 0)

        # All should have root as their root developer
        self.assertEqual(result["root_developer_id"][root.id], root.id)
        self.assertEqual(result["root_developer_id"][mid.id], root.id)
        self.assertEqual(result["root_developer_id"][leaf.id], root.id)

    def test_compute_hierarchy_selects_best_ranked_top_game(self):
        """Test that top game is the one with the best (lowest) rank."""
        dev = Developer.objects.create(name="Dev", igdb_id=1)
        game_rank_50 = Game.objects.create(name="Mid Ranked", rank=50, igdb_id=100)
        game_rank_10 = Game.objects.create(name="Top Ranked", rank=10, igdb_id=101)
        game_rank_100 = Game.objects.create(name="Low Ranked", rank=100, igdb_id=102)

        game_rank_50.developers.add(dev)
        game_rank_10.developers.add(dev)
        game_rank_100.developers.add(dev)

        result = _compute_hierarchy()

        # All games should be counted
        self.assertEqual(result["recursive_game_counts"][dev.id], 3)
        # Top game should be the one with best rank (10)
        self.assertEqual(result["top_game_id"][dev.id], game_rank_10.id)


class FindRootTests(TestCase):
    """Tests for _find_root helper function."""

    def test_find_root_no_parent(self):
        """Test finding root for developer with no parent."""
        dev_data = {1: {"id": 1, "parent_id": None, "name": "Root"}}
        result = _find_root(1, dev_data)
        self.assertEqual(result, 1)

    def test_find_root_with_parent(self):
        """Test finding root for developer with parent."""
        dev_data = {
            1: {"id": 1, "parent_id": None, "name": "Root"},
            2: {"id": 2, "parent_id": 1, "name": "Child"},
        }
        result = _find_root(2, dev_data)
        self.assertEqual(result, 1)

    def test_find_root_deep_chain(self):
        """Test finding root through multiple levels."""
        dev_data = {
            1: {"id": 1, "parent_id": None, "name": "Root"},
            2: {"id": 2, "parent_id": 1, "name": "Mid"},
            3: {"id": 3, "parent_id": 2, "name": "Leaf"},
        }
        result = _find_root(3, dev_data)
        self.assertEqual(result, 1)

    def test_find_root_circular_reference(self):
        """Test handling of circular reference (shouldn't happen but safeguard)."""
        # Create circular reference: 1 -> 2 -> 3 -> 1
        dev_data = {
            1: {"id": 1, "parent_id": 3, "name": "A"},
            2: {"id": 2, "parent_id": 1, "name": "B"},
            3: {"id": 3, "parent_id": 2, "name": "C"},
        }
        # Should not infinite loop, should return something
        result = _find_root(1, dev_data)
        self.assertIn(result, [1, 2, 3])

    def test_find_root_missing_parent(self):
        """Test handling when parent_id references non-existent developer."""
        dev_data = {
            1: {"id": 1, "parent_id": 999, "name": "Orphan"},
        }
        # Parent 999 doesn't exist in dict, function returns the orphan parent_id
        # This is the expected behavior - it walks up until it finds a missing entry
        result = _find_root(1, dev_data)
        self.assertEqual(result, 999)


class CollectDescendantsTests(TestCase):
    """Tests for _collect_all_descendants helper function."""

    def test_collect_descendants_no_children(self):
        """Test collecting descendants for developer with no children."""
        children_by_parent = {1: set()}
        result = _collect_all_descendants(1, children_by_parent)
        self.assertEqual(result, set())

    def test_collect_descendants_direct_children(self):
        """Test collecting direct children only."""
        children_by_parent = {
            1: {2, 3},
            2: set(),
            3: set(),
        }
        result = _collect_all_descendants(1, children_by_parent)
        self.assertEqual(result, {2, 3})

    def test_collect_descendants_nested_children(self):
        """Test collecting nested descendants."""
        children_by_parent = {
            1: {2},
            2: {3},
            3: {4},
            4: set(),
        }
        result = _collect_all_descendants(1, children_by_parent)
        self.assertEqual(result, {2, 3, 4})

    def test_collect_descendants_tree_structure(self):
        """Test collecting from a tree structure."""
        #     1
        #    / \
        #   2   3
        #  /   / \
        # 4   5   6
        children_by_parent = {
            1: {2, 3},
            2: {4},
            3: {5, 6},
            4: set(),
            5: set(),
            6: set(),
        }
        result = _collect_all_descendants(1, children_by_parent)
        self.assertEqual(result, {2, 3, 4, 5, 6})

    def test_collect_descendants_not_in_map(self):
        """Test developer not in the children_by_parent map."""
        children_by_parent = {}
        result = _collect_all_descendants(999, children_by_parent)
        self.assertEqual(result, set())


class DeveloperHierarchyIntegrationTests(TestCase):
    """Integration tests for the full developer hierarchy workflow."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def test_full_hierarchy_workflow(self):
        """Test complete workflow with multiple developers and games."""
        # Create complex hierarchy
        nintendo = Developer.objects.create(name="Nintendo", igdb_id=1, slug="nintendo")
        nintendo_ead = Developer.objects.create(
            name="Nintendo EAD", igdb_id=2, parent=nintendo
        )
        nintendo_epd = Developer.objects.create(
            name="Nintendo EPD", igdb_id=3, parent=nintendo
        )
        retro = Developer.objects.create(
            name="Retro Studios", igdb_id=4, parent=nintendo
        )

        # Create games
        zelda = Game.objects.create(name="Zelda", rank=1, igdb_id=100)
        mario = Game.objects.create(name="Mario", rank=2, igdb_id=101)
        metroid = Game.objects.create(name="Metroid Prime", rank=5, igdb_id=102)

        zelda.developers.add(nintendo_ead)
        mario.developers.add(nintendo_epd)
        metroid.developers.add(retro)

        # Get hierarchy
        hierarchy = get_developer_hierarchy()

        # Nintendo should have all 3 subsidiaries
        self.assertEqual(
            len(hierarchy["subsidiary_ids"][nintendo.id]),
            3,
        )
        # Nintendo should have all 3 games recursively
        self.assertEqual(hierarchy["recursive_game_counts"][nintendo.id], 3)
        # Nintendo's top game should be Zelda (rank 1)
        self.assertEqual(hierarchy["top_game_id"][nintendo.id], zelda.id)

        # Nintendo EAD should have its own game
        self.assertEqual(hierarchy["recursive_game_counts"][nintendo_ead.id], 1)
        self.assertEqual(hierarchy["top_game_id"][nintendo_ead.id], zelda.id)

    def test_cache_invalidation_clears_cache(self):
        """Test that cache invalidation removes cached data."""
        # Set some test data in cache
        test_data = {"test": "data"}
        cache.set(DEVELOPER_HIERARCHY_CACHE_KEY, test_data)

        # Verify it was set
        self.assertEqual(cache.get(DEVELOPER_HIERARCHY_CACHE_KEY), test_data)

        # Invalidate the cache
        invalidate_developer_cache()

        # Cache should now be empty
        self.assertIsNone(cache.get(DEVELOPER_HIERARCHY_CACHE_KEY))

    def test_get_hierarchy_recomputes_after_invalidation(self):
        """Test that hierarchy is recomputed after cache invalidation."""
        cache.clear()

        # Create developer with game
        dev = Developer.objects.create(name="Dev", igdb_id=1)
        game = Game.objects.create(name="Game", rank=1, igdb_id=100)
        game.developers.add(dev)

        # Get hierarchy - should compute and show game
        hierarchy = get_developer_hierarchy()
        self.assertEqual(hierarchy["recursive_game_counts"][dev.id], 1)

        # Invalidate and get again - should recompute (still 1 game)
        invalidate_developer_cache()
        hierarchy2 = get_developer_hierarchy()
        self.assertEqual(hierarchy2["recursive_game_counts"][dev.id], 1)
