"""
Management command to refresh all metadata (IGDB + Wikipedia) for games.

This command combines IGDB and Wikipedia data refreshes into one unified operation,
designed for weekly scheduled execution via Heroku Scheduler.

It performs:
1. IGDB data refresh (cover art, descriptions, studios, genres)
2. Wikipedia page lookup + genre scraping

Both operations force-refresh all games regardless of existing data.
"""

import logging
import time
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from games import config
from games.models import Game, WikipediaGameData, WikipediaGenre
from games.services.igdb_importer import IGDBImportService
from games.services.wiki_genre_service import WikiGenreService
from games.services.wiki_page_lookup_service import WikiPageLookupService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Weekly metadata refresh - force update IGDB and Wikipedia data for all games. "
        "Designed for Heroku Scheduler execution."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = None
        self.igdb_start_time = None
        self.wikipedia_start_time = None

        # Statistics
        self.igdb_processed = 0
        self.igdb_errors = 0
        self.wikipedia_pages_found = 0
        self.wikipedia_pages_failed = 0
        self.genres_scraped = 0
        self.genres_failed = 0

    def add_arguments(self, parser):
        parser.add_argument(
            "--igdb-only",
            action="store_true",
            help="Only refresh IGDB data (skip Wikipedia)",
        )
        parser.add_argument(
            "--wikipedia-only",
            action="store_true",
            help="Only refresh Wikipedia data (skip IGDB)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit number of games to process (for testing)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview operations without making database changes",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=8,
            help="Number of concurrent IGDB requests (default: 8, max: 8)",
        )
        parser.add_argument(
            "--pro",
            action="store_true",
            help="Use IGDB Pro tier (3000 req/sec vs 4 req/sec)",
        )
        parser.add_argument(
            "--weekly",
            action="store_true",
            help=(
                "Only run on Sundays (for daily Heroku Scheduler jobs). "
                "Exits silently on other days."
            ),
        )

    def handle(self, *args, **options):
        """Main command handler - orchestrates IGDB and Wikipedia refreshes."""
        self.start_time = time.time()

        # Check if weekly flag is set and today is not Sunday
        if options.get("weekly"):
            # 6 = Sunday in Python's weekday() (0=Monday, 6=Sunday)
            if datetime.now().weekday() != 6:
                self.stdout.write(
                    f"Skipping: Today is {datetime.now().strftime('%A')} "
                    "(weekly mode only runs on Sunday)"
                )
                return

        # Validate flags
        if options.get("igdb_only") and options.get("wikipedia_only"):
            self.stdout.write(
                self.style.ERROR("Cannot use --igdb-only and --wikipedia-only together")
            )
            return

        # Print header
        self._print_header(options)

        # [1/2] IGDB Refresh
        if not options.get("wikipedia_only"):
            try:
                self._refresh_igdb(options)
            except Exception as e:
                logger.exception("IGDB refresh failed")
                self.stdout.write(self.style.ERROR(f"\n  IGDB refresh failed: {e}"))
                self.igdb_errors = -1  # Flag for total failure

        # [2/2] Wikipedia Refresh
        if not options.get("igdb_only"):
            try:
                self._refresh_wikipedia(options)
            except Exception as e:
                logger.exception("Wikipedia refresh failed")
                self.stdout.write(
                    self.style.ERROR(f"\n  Wikipedia refresh failed: {e}")
                )
                self.wikipedia_pages_failed = -1  # Flag for total failure

        # Print summary
        self._print_summary()

    def _print_header(self, options):
        """Print command execution header."""
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Weekly Metadata Refresh"))
        self.stdout.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")

        if options.get("dry_run"):
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No database changes will be made")
            )

        if options.get("limit"):
            self.stdout.write(f"Limiting to first {options['limit']} games")

        self.stdout.write("=" * 70)

    def _refresh_igdb(self, options):
        """Refresh IGDB data for all games using IGDBImportService."""
        self.stdout.write("\n[1/2] Refreshing IGDB Data")
        self.stdout.write("-" * 40)

        self.igdb_start_time = time.time()

        # Initialize service with progress callback
        try:
            service = IGDBImportService(
                concurrency=options.get("concurrency", 8),
                batch_size=None,  # Auto-detect from tier
                use_pro_tier=options.get("pro"),
                progress_callback=self._igdb_progress_callback,
            )
        except RuntimeError as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to initialize IGDB service: {e}")
            )
            return

        # Show tier and mode info
        tier_name = "Pro" if service.api_client.use_pro_tier else "Free"
        self.stdout.write(f"Using IGDB {tier_name} tier")

        mode_desc = []
        if service.batch_size > 0:
            mode_desc.append(f"batch_games={service.batch_size}")
        if service.concurrency > 1:
            mode_desc.append(f"concurrency={service.concurrency}")

        # Get games to process (all with IGDB IDs)
        games = Game.objects.exclude(igdb_id__isnull=True).order_by("rank")

        if options.get("limit"):
            games = games[: options["limit"]]

        total_games = games.count()

        if total_games == 0:
            self.stdout.write(self.style.WARNING("No games with IGDB IDs found"))
            return

        self.stdout.write(f"Processing {total_games} games ({', '.join(mode_desc)})")

        if options.get("dry_run"):
            self.stdout.write(
                self.style.WARNING("  DRY RUN: Would process IGDB data for games")
            )
            return

        # Run the import
        service.import_games(games)

    def _igdb_progress_callback(self, event_type: str, data: dict) -> None:
        """Handle IGDB service progress events."""
        if event_type == "progress":
            current = data.get("current", 0)
            total = data.get("total", 0)

            # Checkpoint every 100 games (less verbose than default 50)
            if current % 100 == 0:
                elapsed = time.time() - self.igdb_start_time
                rate = current / elapsed if elapsed > 0 else 0
                self.stdout.write(f"  [{current}/{total}] ({rate:.1f} games/sec)")

        elif event_type == "error":
            self.igdb_errors += 1
            game_name = data.get("game_name", "Unknown")
            message = data.get("message", "Unknown error")
            logger.warning("IGDB error for %s: %s", game_name, message)

        elif event_type == "complete":
            self.igdb_processed = data.get("processed", 0)
            self.igdb_errors = data.get("errors", 0)
            elapsed = data.get("elapsed_seconds", 0)

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n  IGDB Complete: {self.igdb_processed} processed, "
                    f"{self.igdb_errors} errors in {elapsed:.0f}s"
                )
            )

    def _refresh_wikipedia(self, options):
        """Refresh Wikipedia data for all games."""
        self.stdout.write("\n[2/2] Refreshing Wikipedia Data")
        self.stdout.write("-" * 40)

        self.wikipedia_start_time = time.time()

        # Show authentication status
        if settings.WIKIDATA_ACCESS_TOKEN:
            delay = config.WIKIDATA_AUTHENTICATED_DELAY
            self.stdout.write(f"Using authenticated Wikidata requests ({delay}s delay)")
        else:
            delay = config.WIKIDATA_UNAUTHENTICATED_DELAY
            self.stdout.write(
                self.style.WARNING(
                    f"Using unauthenticated Wikidata requests ({delay}s delay)\n"
                    "  Set WIKIDATA_ACCESS_TOKEN for 2.5x faster processing"
                )
            )

        # Initialize services
        page_service = WikiPageLookupService()
        genre_service = WikiGenreService()

        # Get games to process (all games)
        games = Game.objects.all().order_by("rank")

        if options.get("limit"):
            games = games[: options["limit"]]

        total_games = games.count()

        if total_games == 0:
            self.stdout.write(self.style.WARNING("No games found"))
            return

        self.stdout.write(f"Processing {total_games} games...")

        if options.get("dry_run"):
            self.stdout.write(
                self.style.WARNING("  DRY RUN: Would process Wikipedia data for games")
            )
            return

        # Process games sequentially
        for idx, game in enumerate(games, start=1):
            # Checkpoint every 100 games
            if idx % 100 == 0:
                elapsed = time.time() - self.wikipedia_start_time
                rate = idx / elapsed if elapsed > 0 else 0
                self.stdout.write(f"  [{idx}/{total_games}] ({rate:.1f} games/sec)")

            # Step 1: Lookup Wikipedia page
            page_result = page_service.lookup_page(
                game.name, game.wikidata_id, game.year_of_release
            )

            if not page_result.success:
                self.wikipedia_pages_failed += 1
                continue

            self.wikipedia_pages_found += 1
            wikipedia_url = page_result.wikipedia_url

            # Save page data to database
            wiki_game_data = self._save_page_data(game, page_result, game.wikidata_id)

            # Step 2: Scrape genres from the Wikipedia page
            try:
                genre_result = genre_service.get_genre_from_url(
                    game.name, wikipedia_url
                )

                if genre_result.primary_genre:
                    self.genres_scraped += 1

                    # Capitalize first letter if lowercase
                    def capitalize_first(name):
                        return (
                            name[0].upper() + name[1:]
                            if name and name[0].islower()
                            else name
                        )

                    # Capitalize all genre names
                    capitalized_primary = capitalize_first(genre_result.primary_genre)
                    capitalized_all = [
                        capitalize_first(g) for g in genre_result.all_genres
                    ]
                    capitalized_all_str = " | ".join(capitalized_all)

                    # Update WikipediaGameData with genres
                    wiki_game_data.primary_genre = capitalized_primary
                    if capitalized_all:
                        wiki_game_data.all_genres = capitalized_all_str
                    wiki_game_data.save(update_fields=["primary_genre", "all_genres"])

                    # Create WikipediaGenre objects and link to game
                    if capitalized_all:
                        wikipedia_genres = []
                        for genre_name in capitalized_all:
                            genre, _ = WikipediaGenre.objects.get_or_create(
                                name=genre_name
                            )
                            wikipedia_genres.append(genre)
                        game.wikipedia_genres.set(wikipedia_genres)
                else:
                    self.genres_failed += 1

            except Exception as genre_error:
                self.genres_failed += 1
                logger.warning(
                    "Failed to scrape genres for '%s': %s", game.name, genre_error
                )

        # Print Wikipedia completion
        elapsed = time.time() - self.wikipedia_start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Wikipedia Complete: {self.wikipedia_pages_found} pages found, "
                f"{self.genres_scraped} genres scraped, "
                f"{self.wikipedia_pages_failed} page errors in {elapsed:.0f}s"
            )
        )

    def _save_page_data(self, game, page_result, wikidata_id):
        """
        Save Wikipedia page data to database.

        Handles orphaned record reconnection (same pattern as fetch_wikipedia_metadata).
        """
        # First, check for orphaned record with same page_title
        orphaned_record = WikipediaGameData.objects.filter(
            page_title=page_result.page_title,
            game__isnull=True,
            is_primary=True,
        ).first()

        if orphaned_record:
            # Reconnect orphaned record
            # Unset is_primary on any existing records for this game
            WikipediaGameData.objects.filter(game=game, is_primary=True).update(
                is_primary=False
            )

            # Reconnect the orphaned record
            orphaned_record.game = game
            orphaned_record.lookup_source = page_result.lookup_source
            # Update wikidata_id if available
            if wikidata_id:
                orphaned_record.wikidata_id = wikidata_id
            orphaned_record.save(update_fields=["game", "lookup_source", "wikidata_id"])
            wiki_game_data = orphaned_record
        else:
            # No orphaned record found, create or update
            # Unset is_primary on any existing records
            WikipediaGameData.objects.filter(game=game, is_primary=True).update(
                is_primary=False
            )

            # Create or update WikipediaGameData record
            defaults = {
                "lookup_source": page_result.lookup_source,
                "is_primary": True,
            }
            if wikidata_id:
                defaults["wikidata_id"] = wikidata_id

            wiki_game_data, created = WikipediaGameData.objects.update_or_create(
                game=game,
                page_title=page_result.page_title,
                defaults=defaults,
            )

        # Set primary relationship
        game.primary_wikipedia_game_data = wiki_game_data
        game.save(update_fields=["primary_wikipedia_game_data"])

        return wiki_game_data

    def _print_summary(self):
        """Print final execution summary."""
        total_elapsed = time.time() - self.start_time

        # Convert to minutes if over 90 seconds
        if total_elapsed > 90:
            duration_str = (
                f"{int(total_elapsed // 60)} minutes {int(total_elapsed % 60)} seconds"
            )
        else:
            duration_str = f"{total_elapsed:.0f} seconds"

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("Summary"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Total Duration: {duration_str}")

        # IGDB stats
        if self.igdb_processed > 0 or self.igdb_errors != 0:
            if self.igdb_errors == -1:
                self.stdout.write(self.style.ERROR("IGDB:      FAILED"))
            else:
                total_igdb = self.igdb_processed + self.igdb_errors
                success_pct = (
                    (self.igdb_processed / total_igdb * 100) if total_igdb > 0 else 0
                )
                status = (
                    self.style.SUCCESS if self.igdb_errors == 0 else self.style.WARNING
                )
                self.stdout.write(
                    status(
                        f"IGDB:      {self.igdb_processed}/{total_igdb} success "
                        f"({self.igdb_errors} errors, {success_pct:.1f}%)"
                    )
                )

        # Wikipedia stats
        if self.wikipedia_pages_found > 0 or self.wikipedia_pages_failed != 0:
            if self.wikipedia_pages_failed == -1:
                self.stdout.write(self.style.ERROR("Wikipedia: FAILED"))
            else:
                total_wiki = self.wikipedia_pages_found + self.wikipedia_pages_failed
                success_pct = (
                    (self.wikipedia_pages_found / total_wiki * 100)
                    if total_wiki > 0
                    else 0
                )
                status = (
                    self.style.SUCCESS
                    if self.wikipedia_pages_failed == 0
                    else self.style.WARNING
                )
                self.stdout.write(
                    status(
                        f"Wikipedia: {self.wikipedia_pages_found}/{total_wiki} "
                        f"pages found ({self.wikipedia_pages_failed} errors, "
                        f"{success_pct:.1f}%)"
                    )
                )

                # Genre stats
                if self.genres_scraped > 0 or self.genres_failed > 0:
                    total_genres = self.genres_scraped + self.genres_failed
                    genre_pct = (
                        (self.genres_scraped / total_genres * 100)
                        if total_genres > 0
                        else 0
                    )
                    self.stdout.write(
                        f"Genres:    {self.genres_scraped}/{total_genres} scraped "
                        f"({genre_pct:.1f}%)"
                    )

        # Overall status
        has_errors = (
            self.igdb_errors > 0
            or self.wikipedia_pages_failed > 0
            or self.genres_failed > 0
        )
        overall_status = "SUCCESS" if not has_errors else "COMPLETED WITH ERRORS"
        style = self.style.SUCCESS if not has_errors else self.style.WARNING

        self.stdout.write(f"\nOverall Status: {style(overall_status)}")
        self.stdout.write(
            f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        self.stdout.write("=" * 70)
