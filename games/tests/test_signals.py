"""Tests for Django signals in the games app."""

from django.core.cache import cache
from django.test import TestCase

from games import config
from games.models import Developer, Game, WikipediaGenre
from games.signals import invalidate_genre_descendant_cache


class DeveloperCacheInvalidationSignalTests(TestCase):
    """Tests for developer hierarchy cache invalidation signals."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_developer_save_invalidates_cache(self):
        """Test that saving a developer invalidates the hierarchy cache."""
        from games.services.developer_service import DEVELOPER_HIERARCHY_CACHE_KEY

        # Pre-populate cache
        cache.set(DEVELOPER_HIERARCHY_CACHE_KEY, {"test": "data"})

        # Save a developer (triggers post_save signal)
        Developer.objects.create(name="Test Dev", igdb_id=1)

        # Cache should be invalidated
        self.assertIsNone(cache.get(DEVELOPER_HIERARCHY_CACHE_KEY))

    def test_developer_delete_invalidates_cache(self):
        """Test that deleting a developer invalidates the hierarchy cache."""
        from games.services.developer_service import DEVELOPER_HIERARCHY_CACHE_KEY

        dev = Developer.objects.create(name="Test Dev", igdb_id=1)

        # Pre-populate cache
        cache.set(DEVELOPER_HIERARCHY_CACHE_KEY, {"test": "data"})

        # Delete developer (triggers post_delete signal)
        dev.delete()

        # Cache should be invalidated
        self.assertIsNone(cache.get(DEVELOPER_HIERARCHY_CACHE_KEY))

    def test_developer_detail_cache_invalidated_on_change(self):
        """Test that developer detail page cache is invalidated."""
        dev = Developer.objects.create(name="Test Dev", igdb_id=1)

        # Pre-populate detail cache
        cache_key = f"{config.CACHE_VERSION}:developer_detail:{dev.id}"
        cache.set(cache_key, {"detail": "cached"})

        # Update developer
        dev.name = "Updated Name"
        dev.save()

        # Detail cache should be invalidated
        self.assertIsNone(cache.get(cache_key))

    def test_subsidiary_change_invalidates_root_cache(self):
        """Test that changing a subsidiary invalidates root developer's cache."""
        parent = Developer.objects.create(name="Parent", igdb_id=1, slug="parent")
        child = Developer.objects.create(name="Child", igdb_id=2, parent=parent)

        # Pre-populate root's detail cache
        parent_cache_key = f"{config.CACHE_VERSION}:developer_detail:{parent.id}"
        cache.set(parent_cache_key, {"detail": "cached"})

        # Update child
        child.name = "Updated Child"
        child.save()

        # Parent's detail cache should be invalidated
        self.assertIsNone(cache.get(parent_cache_key))

    def test_handles_deleted_parent_during_subsidiary_delete(self):
        """Test graceful handling when parent is already deleted."""
        parent = Developer.objects.create(name="Parent", igdb_id=1, slug="parent")
        child = Developer.objects.create(name="Child", igdb_id=2, parent=parent)

        # Delete parent first (child still references it)
        parent.delete()

        # Deleting child should not raise exception
        # (the signal handler should catch DoesNotExist)
        child.delete()  # Should not raise


class GameDeveloperM2MSignalTests(TestCase):
    """Tests for Game.developers M2M change signals."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_adding_developer_to_game_invalidates_cache(self):
        """Test that adding a developer to a game invalidates cache."""
        from games.services.developer_service import DEVELOPER_HIERARCHY_CACHE_KEY

        dev = Developer.objects.create(name="Dev", igdb_id=1)
        game = Game.objects.create(name="Test Game", rank=1, igdb_id=100)

        # Pre-populate cache
        cache.set(DEVELOPER_HIERARCHY_CACHE_KEY, {"test": "data"})

        # Add developer to game (triggers m2m_changed signal)
        game.developers.add(dev)

        # Cache should be invalidated
        self.assertIsNone(cache.get(DEVELOPER_HIERARCHY_CACHE_KEY))

    def test_removing_developer_from_game_invalidates_cache(self):
        """Test that removing a developer from a game invalidates cache."""
        from games.services.developer_service import DEVELOPER_HIERARCHY_CACHE_KEY

        dev = Developer.objects.create(name="Dev", igdb_id=1)
        game = Game.objects.create(name="Test Game", rank=1, igdb_id=100)
        game.developers.add(dev)

        # Pre-populate cache
        cache.set(DEVELOPER_HIERARCHY_CACHE_KEY, {"test": "data"})

        # Remove developer from game
        game.developers.remove(dev)

        # Cache should be invalidated
        self.assertIsNone(cache.get(DEVELOPER_HIERARCHY_CACHE_KEY))

    def test_developer_detail_cache_invalidated_on_m2m_change(self):
        """Test that developer detail cache is invalidated on M2M change."""
        dev = Developer.objects.create(name="Dev", igdb_id=1)
        game = Game.objects.create(name="Test Game", rank=1, igdb_id=100)

        # Pre-populate detail cache
        cache_key = f"{config.CACHE_VERSION}:developer_detail:{dev.id}"
        cache.set(cache_key, {"detail": "cached"})

        # Add developer to game
        game.developers.add(dev)

        # Detail cache should be invalidated
        self.assertIsNone(cache.get(cache_key))

    def test_root_developer_cache_invalidated_on_subsidiary_m2m_change(self):
        """Test root developer cache invalidation on subsidiary M2M changes."""
        parent = Developer.objects.create(name="Parent", igdb_id=1, slug="parent")
        child = Developer.objects.create(name="Child", igdb_id=2, parent=parent)
        game = Game.objects.create(name="Test Game", rank=1, igdb_id=100)

        # Pre-populate root's detail cache
        parent_cache_key = f"{config.CACHE_VERSION}:developer_detail:{parent.id}"
        cache.set(parent_cache_key, {"detail": "cached"})

        # Add subsidiary to game
        game.developers.add(child)

        # Parent's detail cache should be invalidated
        self.assertIsNone(cache.get(parent_cache_key))

    def test_handles_deleted_developer_during_m2m_change(self):
        """Test graceful handling when developer is deleted during M2M operation."""
        dev = Developer.objects.create(name="Dev", igdb_id=1)
        game = Game.objects.create(name="Test Game", rank=1, igdb_id=100)
        game.developers.add(dev)

        # Delete developer
        dev.delete()

        # Clear the game's developers (referencing deleted dev shouldn't crash)
        game.developers.clear()  # Should not raise

    def test_m2m_signal_handles_nonexistent_developer_in_pk_set(self):
        """Test that M2M signal handles developer IDs that don't exist in DB."""
        from games.signals import invalidate_developer_cache_on_game_change

        game = Game.objects.create(name="Test Game", rank=1, igdb_id=100)

        # Manually trigger the signal with a pk_set containing a nonexistent ID
        # This simulates the scenario where a developer is deleted but its ID
        # is still in the pk_set during M2M change processing
        invalidate_developer_cache_on_game_change(
            sender=Game.developers.through,
            instance=game,
            pk_set={99999},  # Nonexistent developer ID
            action="post_add",
        )
        # Should not raise - the except Developer.DoesNotExist should handle it


class WikipediaGenreCacheInvalidationTests(TestCase):
    """Tests for WikipediaGenre cache invalidation signals."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()
        # Use unique counter for each test to avoid slug collisions
        import uuid

        self.unique_id = uuid.uuid4().hex[:8]

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_genre_save_invalidates_own_cache(self):
        """Test that saving a genre invalidates its descendant cache."""
        genre = WikipediaGenre.objects.create(name=f"Action-{self.unique_id}")

        # Pre-populate cache (both include_self variants)
        cache_key_true = f"{config.CACHE_VERSION}:genre_descendants:{genre.id}:True"
        cache_key_false = f"{config.CACHE_VERSION}:genre_descendants:{genre.id}:False"
        cache.set(cache_key_true, {"descendants": []})
        cache.set(cache_key_false, {"descendants": []})

        # Update genre (change a non-slug field to avoid unique constraint)
        genre.description = "Updated description"
        genre.save()

        # Both cache variants should be invalidated
        self.assertIsNone(cache.get(cache_key_true))
        self.assertIsNone(cache.get(cache_key_false))

    def test_genre_delete_invalidates_cache(self):
        """Test that deleting a genre invalidates cache."""
        genre = WikipediaGenre.objects.create(name=f"RPG-{self.unique_id}")
        genre_id = genre.id

        # Pre-populate cache (both include_self variants)
        cache_key_true = f"{config.CACHE_VERSION}:genre_descendants:{genre_id}:True"
        cache_key_false = f"{config.CACHE_VERSION}:genre_descendants:{genre_id}:False"
        cache.set(cache_key_true, {"descendants": []})
        cache.set(cache_key_false, {"descendants": []})

        # Delete genre
        genre.delete()

        # Both cache variants should be invalidated
        self.assertIsNone(cache.get(cache_key_true))
        self.assertIsNone(cache.get(cache_key_false))

    def test_child_genre_invalidates_ancestor_caches(self):
        """Test that changing a child genre invalidates ancestor caches."""
        parent = WikipediaGenre.objects.create(name=f"Strategy-{self.unique_id}")
        child = WikipediaGenre.objects.create(
            name=f"RTS-{self.unique_id}", parent=parent
        )

        # Pre-populate parent's cache (both variants)
        parent_cache_key_true = (
            f"{config.CACHE_VERSION}:genre_descendants:{parent.id}:True"
        )
        parent_cache_key_false = (
            f"{config.CACHE_VERSION}:genre_descendants:{parent.id}:False"
        )
        cache.set(parent_cache_key_true, {"descendants": [child.id]})
        cache.set(parent_cache_key_false, {"descendants": [child.id]})

        # Update child (change a non-slug field)
        child.description = "Real-time strategy games"
        child.save()

        # Parent's cache should be invalidated (both variants)
        self.assertIsNone(cache.get(parent_cache_key_true))
        self.assertIsNone(cache.get(parent_cache_key_false))


class InvalidateGenreDescendantCacheTests(TestCase):
    """Tests for the invalidate_genre_descendant_cache function."""

    def setUp(self):
        """Clear cache before each test."""
        cache.clear()
        import uuid

        self.unique_id = uuid.uuid4().hex[:8]

    def tearDown(self):
        """Clear cache after each test."""
        cache.clear()

    def test_invalidate_specific_genre(self):
        """Test invalidating a specific genre's cache."""
        genre = WikipediaGenre.objects.create(name=f"Puzzle-{self.unique_id}")

        cache_key_true = f"{config.CACHE_VERSION}:genre_descendants:{genre.id}:True"
        cache_key_false = f"{config.CACHE_VERSION}:genre_descendants:{genre.id}:False"
        cache.set(cache_key_true, {"data": "cached"})
        cache.set(cache_key_false, {"data": "cached"})

        invalidate_genre_descendant_cache(genre.id)

        self.assertIsNone(cache.get(cache_key_true))
        self.assertIsNone(cache.get(cache_key_false))

    def test_invalidate_all_genres(self):
        """Test invalidating all genre caches when no ID provided."""
        genre1 = WikipediaGenre.objects.create(name=f"Adventure-{self.unique_id}")
        genre2 = WikipediaGenre.objects.create(name=f"Horror-{self.unique_id}")

        cache_key1_true = f"{config.CACHE_VERSION}:genre_descendants:{genre1.id}:True"
        cache_key1_false = f"{config.CACHE_VERSION}:genre_descendants:{genre1.id}:False"
        cache_key2_true = f"{config.CACHE_VERSION}:genre_descendants:{genre2.id}:True"
        cache_key2_false = f"{config.CACHE_VERSION}:genre_descendants:{genre2.id}:False"
        cache.set(cache_key1_true, {"data": "cached1"})
        cache.set(cache_key1_false, {"data": "cached1"})
        cache.set(cache_key2_true, {"data": "cached2"})
        cache.set(cache_key2_false, {"data": "cached2"})

        invalidate_genre_descendant_cache()

        self.assertIsNone(cache.get(cache_key1_true))
        self.assertIsNone(cache.get(cache_key1_false))
        self.assertIsNone(cache.get(cache_key2_true))
        self.assertIsNone(cache.get(cache_key2_false))

    def test_invalidate_nonexistent_genre_does_not_raise(self):
        """Test that invalidating a non-existent genre doesn't raise."""
        # Should not raise exception
        invalidate_genre_descendant_cache(99999)

    def test_invalidates_ancestor_caches(self):
        """Test that ancestor genre caches are also invalidated."""
        grandparent = WikipediaGenre.objects.create(name=f"Games-{self.unique_id}")
        parent = WikipediaGenre.objects.create(
            name=f"Simulation-{self.unique_id}", parent=grandparent
        )
        child = WikipediaGenre.objects.create(
            name=f"Racing-{self.unique_id}", parent=parent
        )

        # Pre-populate all caches (both variants for each)
        gp_key_true = f"{config.CACHE_VERSION}:genre_descendants:{grandparent.id}:True"
        gp_key_false = (
            f"{config.CACHE_VERSION}:genre_descendants:{grandparent.id}:False"
        )
        p_key_true = f"{config.CACHE_VERSION}:genre_descendants:{parent.id}:True"
        p_key_false = f"{config.CACHE_VERSION}:genre_descendants:{parent.id}:False"
        c_key_true = f"{config.CACHE_VERSION}:genre_descendants:{child.id}:True"
        c_key_false = f"{config.CACHE_VERSION}:genre_descendants:{child.id}:False"
        cache.set(gp_key_true, {"data": "gp"})
        cache.set(gp_key_false, {"data": "gp"})
        cache.set(p_key_true, {"data": "p"})
        cache.set(p_key_false, {"data": "p"})
        cache.set(c_key_true, {"data": "c"})
        cache.set(c_key_false, {"data": "c"})

        # Invalidate child's cache
        invalidate_genre_descendant_cache(child.id)

        # Child's cache should be invalidated (both variants)
        self.assertIsNone(cache.get(c_key_true))
        self.assertIsNone(cache.get(c_key_false))
        # Parent's cache should also be invalidated (ancestor)
        self.assertIsNone(cache.get(p_key_true))
        self.assertIsNone(cache.get(p_key_false))
        # Grandparent's cache should also be invalidated (ancestor)
        self.assertIsNone(cache.get(gp_key_true))
        self.assertIsNone(cache.get(gp_key_false))
