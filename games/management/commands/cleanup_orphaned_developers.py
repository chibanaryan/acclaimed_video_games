import logging

from django.core.management.base import BaseCommand
from django.db.models import Count

from games.models import Developer, DeveloperAlias

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Clean up orphaned developers and developer aliases. "
        "Note: Parent company aliases with 0 games are expected and won't be deleted "
        "as they serve to prevent their Developer from being orphaned."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--aggressive",
            action="store_true",
            help="Also delete parent company aliases with 0 games (not recommended)",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        aggressive = options.get("aggressive", False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No data will be deleted\n")
            )

        # Find truly orphaned developer aliases
        # (no games AND their developer has no other aliases with games)
        if aggressive:
            # Aggressive mode: delete all aliases with no games
            orphaned_aliases = DeveloperAlias.objects.filter(games__isnull=True)
            self.stdout.write(
                self.style.WARNING(
                    "AGGRESSIVE MODE: Will delete ALL aliases with 0 games, "
                    "including parent company aliases\n"
                )
            )
        else:
            # Smart mode: only delete truly orphaned aliases
            # (where the Developer has NO aliases with games at all)
            orphaned_aliases = DeveloperAlias.objects.annotate(
                dev_total_games=Count("developer__aliases__games")
            ).filter(games__isnull=True, dev_total_games=0)

        alias_count = orphaned_aliases.count()

        if alias_count > 0:
            self.stdout.write(
                f"\nFound {alias_count} truly orphaned developer aliases:"
            )
            for alias in orphaned_aliases[:10]:  # Show first 10
                self.stdout.write(
                    f"  - {alias.name} (Developer: {alias.developer.name}, "
                    f"IGDB ID: {alias.igdb_id})"
                )
            if alias_count > 10:
                self.stdout.write(f"  ... and {alias_count - 10} more")

            if not dry_run:
                deleted_count, _ = orphaned_aliases.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nDeleted {deleted_count} orphaned developer aliases"
                    )
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nNo truly orphaned developer aliases found "
                    "(parent company aliases are preserved)"
                )
            )

        # Find orphaned developers (no aliases)
        orphaned_developers = Developer.objects.filter(aliases__isnull=True)
        dev_count = orphaned_developers.count()

        if dev_count > 0:
            self.stdout.write(f"\nFound {dev_count} orphaned developers:")
            for dev in orphaned_developers[:10]:  # Show first 10
                self.stdout.write(
                    f"  - {dev.name} (IGDB ID: {dev.igdb_id}, Slug: {dev.slug})"
                )
            if dev_count > 10:
                self.stdout.write(f"  ... and {dev_count - 10} more")

            if not dry_run:
                deleted_count, _ = orphaned_developers.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"\nDeleted {deleted_count} orphaned developers")
                )
        else:
            self.stdout.write(self.style.SUCCESS("\nNo orphaned developers found"))

        # Summary
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN COMPLETE - Would delete {alias_count} aliases "
                    f"and {dev_count} developers"
                )
            )
            self.stdout.write(
                "\nRun without --dry-run to actually delete the orphaned records"
            )
        else:
            if alias_count > 0 or dev_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Cleanup complete! Deleted {alias_count} aliases "
                        f"and {dev_count} developers"
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS("Database is clean!"))
