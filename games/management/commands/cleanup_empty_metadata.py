"""Management command to clean up empty IGDB and Wikipedia metadata records."""

from django.core.management.base import BaseCommand

from games.models import IGDBGameData, WikipediaGameData


class Command(BaseCommand):
    help = "Clean up empty IGDB and Wikipedia metadata records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        # Find empty Wikipedia records (no page_title, wikidata_id, or primary_genre)
        empty_wiki = WikipediaGameData.objects.filter(
            page_title="", wikidata_id="", primary_genre=""
        )

        # Find empty IGDB records (no artwork_id, url, or description)
        empty_igdb = IGDBGameData.objects.filter(artwork_id="", url="", description="")

        wiki_count = empty_wiki.count()
        igdb_count = empty_igdb.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {wiki_count} empty Wikipedia records"
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {igdb_count} empty IGDB records"
                )
            )
            return

        # Delete empty records
        wiki_deleted, _ = empty_wiki.delete()
        igdb_deleted, _ = empty_igdb.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {wiki_deleted} empty Wikipedia records")
        )
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {igdb_deleted} empty IGDB records")
        )
