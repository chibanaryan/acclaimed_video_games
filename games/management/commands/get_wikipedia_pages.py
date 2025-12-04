"""
Management command to look up Wikipedia pages for games.

Uses Wikidata IDs as the primary method (fast), with fallback to OpenSearch API.
This is separate from genre scraping - it only finds and records Wikipedia page titles.
"""

import csv
import logging
import time
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from games import config
from games.models import Game
from games.services.wiki_page_lookup_service import WikiPageLookupService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Look up Wikipedia pages for games using Wikidata IDs and OpenSearch"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--game",
            type=str,
            help="Process specific game by name (case-insensitive)",
        )
        parser.add_argument(
            "--slug",
            type=str,
            help="Process specific game by slug",
        )
        parser.add_argument(
            "--id",
            type=int,
            help="Process specific game by database ID",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit number of games to process",
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Skip first N games (default: 0)",
        )
        parser.add_argument(
            "--delay",
            type=float,
            help="Override delay between requests (default: auth-aware)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Output CSV file path (default: wikipedia_pages_TIMESTAMP.csv)",
        )
        parser.add_argument(
            "--no-output",
            action="store_true",
            help="Skip CSV output (console only)",
        )
        parser.add_argument(
            "--save",
            action="store_true",
            help="Save results to database (default: CSV only)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip games that already have Wikipedia page titles",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh all games (ignore existing data)",
        )

    def handle(self, *args, **options):
        self.start_time = time.time()

        # Show authentication status
        if settings.WIKIDATA_ACCESS_TOKEN:
            self.stdout.write(
                self.style.SUCCESS(
                    "✓ Using authenticated Wikidata requests "
                    f"({config.WIKIDATA_AUTHENTICATED_DELAY}s delay)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "⚠ Using unauthenticated Wikidata requests "
                    f"({config.WIKIDATA_UNAUTHENTICATED_DELAY}s delay)\n"
                    "  Set WIKIDATA_ACCESS_TOKEN for 10x faster processing"
                )
            )

        # Get games to process
        games = self._get_games(options)

        if not games.exists():
            self.stdout.write(self.style.ERROR("No games found to process"))
            return

        game_count = games.count()
        self.stdout.write(f"\nProcessing {game_count} games...")

        # Initialize service
        service = WikiPageLookupService(
            delay=options.get("delay"),
            progress_callback=None,  # We'll handle progress manually
        )

        # Prepare CSV output
        csv_file = None
        csv_writer = None
        if not options.get("no_output"):
            csv_path = self._get_csv_path(options.get("output"))
            csv_file = open(csv_path, "w", newline="", encoding="utf-8")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(
                [
                    "Rank",
                    "Game Name",
                    "Wikipedia Page Title",
                    "Lookup Source",
                    "Wikipedia URL",
                    "Error",
                ]
            )
            self.stdout.write(f"Writing results to: {csv_path}\n")

        # Process games
        success_count = 0
        failure_count = 0

        try:
            for idx, game in enumerate(games, start=1):
                # Perform lookup
                result = service.lookup_page(
                    game.name, game.wikidata_id, game.year_of_release
                )

                # Display progress
                if result.success:
                    success_count += 1
                    self.stdout.write(
                        f"[{idx}/{game_count}] ✓ {game.name}: "
                        f"{result.page_title} ({result.lookup_source})"
                    )

                    # Save to database if requested
                    if options.get("save"):
                        game.wikipedia_page_title = result.page_title
                        game.wikipedia_lookup_source = result.lookup_source
                        game.save(
                            update_fields=[
                                "wikipedia_page_title",
                                "wikipedia_lookup_source",
                            ]
                        )
                else:
                    failure_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{idx}/{game_count}] ✗ {game.name}: "
                            f"{result.error_message}"
                        )
                    )

                # Write to CSV
                if csv_writer:
                    csv_writer.writerow(
                        [
                            game.rank,
                            game.name,
                            result.page_title or "",
                            result.lookup_source or "",
                            result.wikipedia_url or "",
                            result.error_message or "",
                        ]
                    )
                    csv_file.flush()  # Write immediately

        finally:
            if csv_file:
                csv_file.close()

        # Summary
        elapsed = time.time() - self.start_time
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"\nCompleted in {elapsed:.1f} seconds"))
        self.stdout.write(f"Total: {game_count}")
        self.stdout.write(self.style.SUCCESS(f"Success: {success_count}"))
        if failure_count > 0:
            self.stdout.write(self.style.WARNING(f"Failed: {failure_count}"))

        if options.get("save"):
            self.stdout.write(self.style.SUCCESS("\n✓ Results saved to database"))
        elif not options.get("no_output"):
            self.stdout.write(f"\n✓ Results written to {csv_path}")

    def _get_games(self, options):
        """Get queryset of games to process based on options."""
        # Single game by name
        if options.get("game"):
            return Game.objects.filter(name__iexact=options["game"])

        # Single game by slug
        if options.get("slug"):
            return Game.objects.filter(slug=options["slug"])

        # Single game by ID
        if options.get("id"):
            return Game.objects.filter(id=options["id"])

        # All games with filtering
        games = Game.objects.all().order_by("rank")

        # Skip existing (unless force)
        if options.get("skip_existing") and not options.get("force"):
            games = games.filter(wikipedia_page_title__isnull=True)
        elif not options.get("force"):
            # Default: only process games without Wikipedia data
            games = games.filter(wikipedia_page_title__isnull=True)

        # Apply offset
        if options.get("offset"):
            games = games[options["offset"] :]

        # Apply limit
        if options.get("limit"):
            games = games[: options["limit"]]

        return games

    def _get_csv_path(self, output_path):
        """Get CSV output path (use provided or generate timestamp-based)."""
        if output_path:
            return output_path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"wikipedia_pages_{timestamp}.csv"
