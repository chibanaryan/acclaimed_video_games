"""
Management command to scrape ordered genre lists from Wikipedia for games.

Uses Wikipedia opensearch API to find articles, then scrapes infoboxes
to extract the ordered genre list (primary genre at index 0).
"""

import csv
import logging
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
        no_output = options.get("no_output", False)
        save_to_db = options.get("save", False)
        skip_existing = options.get("skip_existing", False)

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
        results = []

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

        for idx, game in enumerate(game_list):
            result = service.get_genre(game.name, year=game.year_of_release)
            # Store game reference with result for CSV output
            result.game = game
            results.append(result)

            # Update database if requested
            if save_to_db and result.source != GenreSource.FAILED:
                game.wikipedia_primary_genre = result.primary_genre
                game.wikipedia_all_genres = result.all_genres_str
                game.save(
                    update_fields=["wikipedia_primary_genre", "wikipedia_all_genres"]
                )

            # Progress output
            current = idx + 1
            if result.source != GenreSource.FAILED:
                genre_count = len(result.all_genres)
                self.stdout.write(
                    f"[{current}/{total_games}] {game.name}: "
                    f"{result.primary_genre} ({genre_count} genres)"
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"[{current}/{total_games}] {game.name}: "
                        f"FAILED - {result.error_message}"
                    )
                )

        # Summary
        success_count = sum(1 for r in results if r.source != GenreSource.FAILED)
        failure_count = len(results) - success_count
        elapsed = time.time() - self.start_time

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {success_count}/{total_games} successful, "
                f"{failure_count} failed in {elapsed:.0f}s"
            )
        )

        # Write CSV output
        if not no_output:
            self._write_csv(results, output_path)

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
