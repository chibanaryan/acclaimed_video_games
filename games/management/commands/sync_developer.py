from django.core.management.base import BaseCommand
from games.models import Developer, DeveloperAlias, Game


class Command(BaseCommand):
    help = "Sync a developer from local to production database"

    def add_arguments(self, parser):
        parser.add_argument(
            "developer_slug",
            type=str,
            help="Slug of the developer to sync",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force creation even if developer exists",
        )

    def handle(self, *args, **options):
        developer_slug = options["developer_slug"]
        force = options.get("force", False)

        # Developer data mapping from local to production
        # Includes name, slug, IGDB ID, and associated game slugs

        developer_data = {
            "florian-himsl": {
                "name": "Florian Himsl",
                "slug": "florian-himsl",
                "igdb_id": 40025,
                "games": ["the-binding-of-isaac"],
            },
            "shout-designworks": {
                "name": "Shout! Designworks",
                "slug": "shout-designworks",
                "igdb_id": 21727,
                "games": ["streets-of-rage-2"],
            },
            "vivid-games": {
                "name": "Vivid Games",
                "slug": "vivid-games",
                "igdb_id": 4770,
                "games": ["paperboy"],
            },
        }

        if developer_slug not in developer_data:
            self.stdout.write(
                self.style.ERROR(f"Unknown developer slug: {developer_slug}")
            )
            return

        dev_info = developer_data[developer_slug]

        # Check if developer already exists
        existing = Developer.objects.filter(slug=dev_info["slug"]).first()
        if existing and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Developer "{existing.name}" already exists (ID: {existing.id})'
                )
            )
            return

        if existing and force:
            developer = existing
            self.stdout.write(
                self.style.WARNING(f"Updating existing developer: {existing.name}")
            )
        else:
            developer = Developer.objects.create(
                name=dev_info["name"],
                slug=dev_info["slug"],
                igdb_id=dev_info["igdb_id"],
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created developer "{developer.name}" (ID: {developer.id})'
                )
            )

        # Create or update alias
        alias, created = DeveloperAlias.objects.get_or_create(
            name=dev_info["name"],
            developer=developer,
            defaults={"igdb_id": dev_info["igdb_id"]},
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created alias "{alias.name}" (ID: {alias.id})')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Alias "{alias.name}" already exists')
            )

        # Associate with games
        for game_slug in dev_info["games"]:
            game = Game.objects.filter(slug=game_slug).first()
            if game:
                game.developers.add(alias)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Associated with game "{game.name}" (slug: {game.slug})'
                    )
                )
            else:
                self.stdout.write(self.style.WARNING(f"Game not found: {game_slug}"))

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully synced developer: {developer.name}")
        )
