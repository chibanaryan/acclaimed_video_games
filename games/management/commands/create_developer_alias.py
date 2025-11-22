from django.core.management.base import BaseCommand
from games.models import Developer, DeveloperAlias


class Command(BaseCommand):
    help = "Create a developer alias if it does not exist"

    def add_arguments(self, parser):
        parser.add_argument("alias_name", type=str, help="Name of the developer alias")
        parser.add_argument(
            "developer_slug",
            type=str,
            help="Slug of the developer this alias belongs to",
        )

    def handle(self, *args, **options):
        alias_name = options["alias_name"]
        developer_slug = options["developer_slug"]

        # Look up the developer
        developer = Developer.objects.filter(slug=developer_slug).first()
        if not developer:
            self.stdout.write(
                self.style.ERROR(f"Developer not found with slug: {developer_slug}")
            )
            return

        # Check if alias already exists
        existing = DeveloperAlias.objects.filter(
            name=alias_name, developer_id=developer.id
        ).first()
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f'Alias "{alias_name}" already exists for developer '
                    f'"{developer.name}" (ID: {existing.id})'
                )
            )
            return

        # Create the alias
        alias = DeveloperAlias(name=alias_name, developer_id=developer.id)
        alias.save()
        self.stdout.write(
            self.style.SUCCESS(
                f'Created alias "{alias_name}" for developer "{developer.name}" '
                f"(Alias ID: {alias.id})"
            )
        )
