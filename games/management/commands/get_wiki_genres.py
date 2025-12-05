"""
Management command to scrape ordered genre lists from Wikipedia for games.

Uses Wikipedia opensearch API to find articles, then scrapes infoboxes
to extract the ordered genre list (primary genre at index 0).
"""

import csv
import logging
import os
import time
from datetime import datetime

from django.core.management.base import BaseCommand

from games import config
from games.models import Game
from games.services.wiki_genre_service import GenreSource, WikiGenreService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scrape ordered genre lists from Wikipedia for games"

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
            default=config.WIKI_REQUEST_DELAY,
            help=f"Delay between requests (default: {config.WIKI_REQUEST_DELAY}s)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Output CSV file path (default: game_genres_ordered_TIMESTAMP.csv)",
        )
        parser.add_argument(
            "--resume",
            type=str,
            help="Resume from existing CSV file (skips games already processed)",
        )
        parser.add_argument(
            "--no-output",
            action="store_true",
            help="Skip CSV output (console only)",
        )
        parser.add_argument(
            "--save",
            action="store_true",
            help="Save results to database (wikipedia_primary_genre field)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip games that already have wikipedia_primary_genre set",
        )

    def handle(self, *args, **options):
        """Handle Wikipedia genre scraping."""
        game_name = options.get("game")
        game_slug = options.get("slug")
        game_id = options.get("id")
        limit = options.get("limit")
        offset = options.get("offset", 0)
        delay = options.get("delay", config.WIKI_REQUEST_DELAY)
        output_path = options.get("output")
        resume_path = options.get("resume")
        no_output = options.get("no_output", False)
        save_to_db = options.get("save", False)
        skip_existing = options.get("skip_existing", False)

        # Handle resume mode - read already-processed game ranks from CSV
        processed_ranks = set()
        if resume_path:
            processed_ranks = self._read_processed_ranks(resume_path)
            if processed_ranks:
                self.stdout.write(
                    f"Resuming from {resume_path}: {len(processed_ranks)} games "
                    "already processed"
                )
                # Use resume file as output (append mode)
                output_path = resume_path
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"No existing data in {resume_path}, starting fresh"
                    )
                )

        # Build game queryset
        if game_name or game_slug or game_id:
            # Single game mode
            games = self._get_single_game_queryset(game_name, game_slug, game_id)
            if games is None:
                return
        else:
            # Batch mode
            games = Game.objects.all()
            if skip_existing:
                games = games.filter(wikipedia_primary_genre__isnull=True)
            games = games.order_by("rank")
            # Apply offset and limit
            if limit:
                games = games[offset : offset + limit]
            elif offset:
                games = games[offset:]

        total_games = games.count() if hasattr(games, "count") else len(games)

        if total_games == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No games to process. "
                    "Use --skip-existing=False to reprocess games with existing data."
                )
            )
            return

        self.stdout.write(f"Processing {total_games} games...")
        self.stdout.write(f"Rate limit: {delay}s between requests")
        self.stdout.write(f"Save to database: {'Yes' if save_to_db else 'No'}")

        # Initialize service
        self.start_time = time.time()
        success_count = 0
        failure_count = 0

        def progress_callback(event_type: str, data: dict) -> None:
            """Handle progress events from service."""
            if event_type == "progress":
                self._handle_progress_event(data)
            elif event_type == "error":
                self._handle_error_event(data)
            elif event_type == "complete":
                self._handle_complete_event(data)

        service = WikiGenreService(
            delay=delay,
            progress_callback=progress_callback,
        )

        # Process games - prefetch genres for CSV comparison
        game_list = list(games.prefetch_related("genres"))

        # Set up incremental CSV writing (append after each game)
        csv_file = None
        csv_writer = None
        if not no_output:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"wiki_genres_{timestamp}.csv"

            # Append mode if resuming, write mode if new
            is_append = resume_path and processed_ranks
            file_mode = "a" if is_append else "w"
            csv_file = open(output_path, file_mode, newline="", encoding="utf-8")
            csv_writer = csv.writer(csv_file)

            # Only write header for new files
            if not is_append:
                csv_writer.writerow(
                    [
                        "Rank",
                        "Original Title",
                        "Primary Genre",
                        "All Genres",
                        "IGDB Genres",
                        "Source URL",
                        "Error",
                    ]
                )
                csv_file.flush()
                self.stdout.write(f"Starting fresh run: {output_path}")
            else:
                self.stdout.write(f"Appending to: {output_path}")

        skipped_count = 0
        try:
            for idx, game in enumerate(game_list):
                # Skip already-processed games (resume mode)
                if game.rank in processed_ranks:
                    skipped_count += 1
                    continue

                result = service.get_genre(game.name, year=game.year_of_release)
                # Store game reference with result
                result.game = game

                # Update database if requested
                if save_to_db and result.source != GenreSource.FAILED:
                    # Use the new get_wikipedia_data method to create
                    # WikipediaGameData records
                    from games.models import WikipediaGameData

                    # First, unset is_primary on any existing records for this game
                    # to avoid UNIQUE constraint violation
                    WikipediaGameData.objects.filter(game=game, is_primary=True).update(
                        is_primary=False
                    )

                    # Create or update WikipediaGameData record
                    wiki_game_data, created = (
                        WikipediaGameData.objects.update_or_create(
                            game=game,
                            page_title=result.game_name,
                            defaults={
                                "primary_genre": result.primary_genre,
                                "all_genres": result.all_genres_str,
                                "lookup_source": result.source_url,
                                "is_primary": True,
                            },
                        )
                    )

                    # Set primary relationship
                    game.primary_wikipedia_game_data = wiki_game_data
                    # Update deprecated fields for backward compatibility
                    game.wikipedia_primary_genre = result.primary_genre
                    game.wikipedia_all_genres = result.all_genres_str
                    game.save(
                        update_fields=[
                            "primary_wikipedia_game_data",
                            "wikipedia_primary_genre",
                            "wikipedia_all_genres",
                        ]
                    )

                # Write to CSV immediately (incremental save)
                if csv_writer:
                    igdb_genres = ", ".join(g.name for g in game.genres.all())
                    csv_writer.writerow(
                        [
                            game.rank,
                            result.game_name,
                            result.primary_genre or "",
                            result.all_genres_str,
                            igdb_genres,
                            result.source_url or "",
                            result.error_message or "",
                        ]
                    )
                    csv_file.flush()  # Ensure data is written to disk

                # Progress output (show processed count, not index)
                processed_so_far = success_count + failure_count + 1
                games_to_process = total_games - skipped_count
                if result.source != GenreSource.FAILED:
                    success_count += 1
                    genre_count = len(result.all_genres)
                    self.stdout.write(
                        f"[{processed_so_far}/{games_to_process}] {game.name}: "
                        f"{result.primary_genre} ({genre_count} genres)"
                    )
                else:
                    failure_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{processed_so_far}/{games_to_process}] {game.name}: "
                            f"FAILED - {result.error_message}"
                        )
                    )
        finally:
            if csv_file:
                csv_file.close()

        # Summary
        elapsed = time.time() - self.start_time
        processed_total = success_count + failure_count

        self.stdout.write("")
        summary_parts = [f"{success_count} successful", f"{failure_count} failed"]
        if skipped_count > 0:
            summary_parts.append(f"{skipped_count} skipped (already processed)")
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed {processed_total} games in {elapsed:.0f}s: "
                + ", ".join(summary_parts)
            )
        )

        if not no_output:
            self.stdout.write(self.style.SUCCESS(f"Results saved to: {output_path}"))

    def _get_single_game_queryset(self, game_name, game_slug, game_id):
        """Get queryset for a single game."""
        try:
            if game_id:
                return Game.objects.filter(id=game_id)
            elif game_slug:
                return Game.objects.filter(slug=game_slug)
            elif game_name:
                return Game.objects.filter(name__iexact=game_name)
        except Game.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"Game not found with "
                    f"{'id=' + str(game_id) if game_id else ''}"
                    f"{'slug=' + game_slug if game_slug else ''}"
                    f"{'name=' + game_name if game_name else ''}"
                )
            )
            return None

    def _read_processed_ranks(self, csv_path: str) -> set:
        """Read already-processed game ranks from CSV file."""
        processed_ranks = set()
        if not os.path.exists(csv_path):
            return processed_ranks

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if row and row[0]:  # First column is Rank
                        try:
                            processed_ranks.add(int(row[0]))
                        except ValueError:
                            continue  # Skip non-numeric ranks
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error reading {csv_path}: {e}"))

        return processed_ranks

    def _handle_progress_event(self, data: dict) -> None:
        """Handle progress event from service."""
        # Progress is handled inline in the main loop for better control
        pass

    def _handle_error_event(self, data: dict) -> None:
        """Handle error event from service."""
        # Errors are handled inline in the main loop for better control
        pass

    def _handle_complete_event(self, data: dict) -> None:
        """Handle completion event from service."""
        # Completion is handled inline in the main loop for better control
        pass

    def _write_csv(self, results, output_path):
        """Write results to CSV file."""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"game_genres_ordered_{timestamp}.csv"

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Rank",
                    "Original Title",
                    "Primary Genre",
                    "All Genres",
                    "IGDB Genres",
                    "Source URL",
                    "Error",
                ]
            )
            for result in results:
                # Get IGDB genres from the game object
                igdb_genres = ""
                if hasattr(result, "game") and result.game:
                    igdb_genres = ", ".join(g.name for g in result.game.genres.all())
                writer.writerow(
                    [
                        result.game.rank if hasattr(result, "game") else "",
                        result.game_name,
                        result.primary_genre or "",
                        result.all_genres_str,
                        igdb_genres,
                        result.source_url or "",
                        result.error_message or "",
                    ]
                )

        self.stdout.write(self.style.SUCCESS(f"Results written to: {output_path}"))
