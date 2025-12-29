import json
import os
import subprocess

from django.core.management import call_command
from django.core.management.base import BaseCommand

from games.models import (
    Developer,
    Game,
    IGDBGenre,
    List,
    ListMembership,
    Platform,
    Post,
    Publication,
    SiteMetadata,
    Snippet,
)


class Command(BaseCommand):
    help = "Sync production database to local SQLite"

    def add_arguments(self, parser):
        parser.add_argument(
            "--app",
            type=str,
            default="acclaimedgames",
            help="Heroku app name (default: acclaimedgames)",
        )
        parser.add_argument(
            "--keep-fixture",
            action="store_true",
            help="Keep the downloaded fixture file after import",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        app_name = options["app"]
        keep_fixture = options["keep_fixture"]
        no_input = options["no_input"]

        self.stdout.write("Syncing production database to local SQLite...")
        self.stdout.write(f"Heroku app: {app_name}")

        # Confirmation prompt
        if not no_input:
            confirm = input(
                "\nThis will DELETE all local game data and replace it with "
                "production data. Continue? [y/N] "
            )
            if confirm.lower() != "y":
                self.stdout.write("Aborted.")
                return

        # Step 1: Dump production data via heroku run
        self.stdout.write("\n1. Dumping production data...")
        dump_cmd = [
            "heroku",
            "run",
            "--app",
            app_name,
            "--no-tty",
            "python manage.py dumpdata games --indent 2",
        ]

        try:
            result = subprocess.run(
                dump_cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f"Failed to dump production data: {e}"))
            self.stderr.write(e.stderr)
            return
        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR(
                    "Heroku CLI not found. Install it: brew install heroku/brew/heroku"
                )
            )
            return

        # Filter out heroku run noise (lines before JSON starts)
        json_data = result.stdout
        json_start = json_data.find("[")
        if json_start == -1:
            self.stderr.write(self.style.ERROR("No JSON data found in output"))
            self.stderr.write(f"Output: {json_data[:500]}")
            return
        json_data = json_data[json_start:]

        # Strip author references from Post (FK to User which isn't synced)
        try:
            fixture_data = json.loads(json_data)
            for item in fixture_data:
                if item.get("model") == "games.post":
                    item["fields"].pop("author", None)
            json_data = json.dumps(fixture_data, indent=2)
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f"Invalid JSON from Heroku: {e}"))
            return

        # Step 2: Save to temporary fixture file
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "fixtures",
            "prod_dump.json",
        )
        os.makedirs(os.path.dirname(fixture_path), exist_ok=True)

        with open(fixture_path, "w") as f:
            f.write(json_data)

        self.stdout.write(f"   Saved fixture to {fixture_path}")

        # Step 3: Run migrations to ensure database exists
        self.stdout.write("\n2. Running migrations...")
        call_command("migrate", verbosity=0)
        self.stdout.write("   Migrations complete")

        # Step 4: Clear local data (order matters for foreign keys)
        self.stdout.write("\n3. Clearing local data...")
        # Delete in order to respect foreign key constraints
        ListMembership.objects.all().delete()
        List.objects.all().delete()
        Publication.objects.all().delete()
        Game.objects.all().delete()
        Developer.objects.all().delete()
        IGDBGenre.objects.all().delete()
        Platform.objects.all().delete()
        Post.objects.all().delete()
        Snippet.objects.all().delete()
        SiteMetadata.objects.all().delete()
        self.stdout.write("   Cleared all games app data")

        # Step 5: Load into local database
        self.stdout.write("\n4. Loading data into local database...")
        try:
            call_command("loaddata", fixture_path, verbosity=1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to load data: {e}"))
            return

        # Step 6: Clean up
        if not keep_fixture:
            os.remove(fixture_path)
            self.stdout.write("   Cleaned up fixture file")
        else:
            self.stdout.write(f"   Fixture kept at: {fixture_path}")

        # Success message
        self.stdout.write(self.style.SUCCESS("\nSync complete!"))
        self.stdout.write(
            "\nNote: Admin users were not synced. Create a local superuser with:"
        )
        self.stdout.write(self.style.WARNING("  python3 manage.py createsuperuser"))
