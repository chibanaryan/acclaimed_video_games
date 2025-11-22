from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .. import models


class CleanupOrphanedDevelopersCommandTests(TestCase):
    def test_cleanup_removes_orphaned_aliases(self):
        """Test that cleanup removes aliases with no games"""
        dev = models.Developer.objects.create(name="Orphan Studio", igdb_id=999)
        orphaned_alias = models.DeveloperAlias.objects.create(
            developer=dev, name="Orphan Alias", igdb_id=1000
        )

        out = StringIO()
        call_command("cleanup_orphaned_developers", stdout=out)

        # Alias should be deleted
        self.assertFalse(
            models.DeveloperAlias.objects.filter(id=orphaned_alias.id).exists()
        )
        self.assertIn("Deleted 1 orphaned developer aliases", out.getvalue())

    def test_cleanup_removes_orphaned_developers(self):
        """Test that cleanup removes developers with no aliases"""
        dev = models.Developer.objects.create(name="No Alias Dev", igdb_id=888)

        out = StringIO()
        call_command("cleanup_orphaned_developers", stdout=out)

        # Developer should be deleted
        self.assertFalse(models.Developer.objects.filter(id=dev.id).exists())
        self.assertIn("Deleted 1 orphaned developers", out.getvalue())

    def test_cleanup_preserves_parent_company_aliases(self):
        """Test that parent company aliases are preserved"""
        parent_dev = models.Developer.objects.create(name="Parent Co", igdb_id=777)
        parent_alias = models.DeveloperAlias.objects.create(
            developer=parent_dev, name="Parent Co", igdb_id=777
        )
        child_alias = models.DeveloperAlias.objects.create(
            developer=parent_dev, name="Child Studio", igdb_id=778
        )

        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=5000, year_of_release=2020
        )
        game.developers.add(child_alias)

        out = StringIO()
        call_command("cleanup_orphaned_developers", stdout=out)

        # Parent alias should still exist (0 games but protects parent dev)
        self.assertTrue(
            models.DeveloperAlias.objects.filter(id=parent_alias.id).exists()
        )
        # Child alias should still exist (has games)
        self.assertTrue(
            models.DeveloperAlias.objects.filter(id=child_alias.id).exists()
        )
        self.assertIn("No truly orphaned developer aliases found", out.getvalue())

    def test_cleanup_dry_run_mode(self):
        """Test that dry run doesn't delete anything"""
        dev = models.Developer.objects.create(name="Test Studio", igdb_id=666)
        models.DeveloperAlias.objects.create(
            developer=dev, name="Test Alias", igdb_id=667
        )

        initial_dev_count = models.Developer.objects.count()
        initial_alias_count = models.DeveloperAlias.objects.count()

        out = StringIO()
        call_command("cleanup_orphaned_developers", "--dry-run", stdout=out)

        # Nothing should be deleted
        self.assertEqual(models.Developer.objects.count(), initial_dev_count)
        self.assertEqual(models.DeveloperAlias.objects.count(), initial_alias_count)
        self.assertIn("DRY RUN", out.getvalue())

    def test_cleanup_aggressive_mode(self):
        """Test aggressive mode deletes all aliases with 0 games"""
        parent_dev = models.Developer.objects.create(name="Parent", igdb_id=555)
        parent_alias = models.DeveloperAlias.objects.create(
            developer=parent_dev, name="Parent", igdb_id=555
        )
        child_alias = models.DeveloperAlias.objects.create(
            developer=parent_dev, name="Child", igdb_id=556
        )

        game = models.Game.objects.create(
            name="Game", rank=1, igdb_id=6000, year_of_release=2021
        )
        game.developers.add(child_alias)

        out = StringIO()
        call_command("cleanup_orphaned_developers", "--aggressive", stdout=out)

        # Parent alias should be deleted in aggressive mode
        self.assertFalse(
            models.DeveloperAlias.objects.filter(id=parent_alias.id).exists()
        )
        # Child alias should still exist
        self.assertTrue(
            models.DeveloperAlias.objects.filter(id=child_alias.id).exists()
        )
        self.assertIn("AGGRESSIVE MODE", out.getvalue())

    def test_cleanup_when_database_clean(self):
        """Test cleanup when there's nothing to clean"""
        dev = models.Developer.objects.create(name="Clean Dev", igdb_id=444)
        alias = models.DeveloperAlias.objects.create(
            developer=dev, name="Clean Alias", igdb_id=445
        )
        game = models.Game.objects.create(
            name="Clean Game", rank=1, igdb_id=7000, year_of_release=2022
        )
        game.developers.add(alias)

        out = StringIO()
        call_command("cleanup_orphaned_developers", stdout=out)

        self.assertIn("Database is clean", out.getvalue())
