import logging
import time

from django.core.management.base import BaseCommand

from games.models import Game
from games.services.igdb_importer import IGDBImportService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch game data from IGDB"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_processed = 0
        self.start_time = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--delay",
            type=float,
            default=0.0,
            help=(
                "Additional delay in seconds between processing games "
                "(default: 0.0s). Rate limiting is automatically handled "
                "by the API client. Only increase this if you need extra "
                "throttling."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of games to process before a longer pause (default: 50). "
            "Helps with memory management and provides progress checkpoints.",
        )
        parser.add_argument(
            "--game",
            type=str,
            help="Update specific game by name (case-insensitive)",
        )
        parser.add_argument(
            "--slug",
            type=str,
            help="Update specific game by slug",
        )
        parser.add_argument(
            "--id",
            type=int,
            help="Update specific game by database ID",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh even if game already has IGDB artwork data",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=8,
            help="Number of concurrent requests to make (default: 8, max: 8). "
            "IGDB allows up to 8 concurrent requests. Set to 1 to disable.",
        )
        parser.add_argument(
            "--batch-games",
            type=int,
            default=None,
            help=(
                "Batch size for multi-query mode (default: auto - 50 for free "
                "tier, 500 for Pro). Fetches multiple games per API request. "
                "Set to 0 to disable batching."
            ),
        )
        parser.add_argument(
            "--pro",
            action="store_true",
            help=(
                "Use IGDB Pro tier (3000 req/sec vs 4 req/sec). "
                "Requires Pro tier subscription. Can also set "
                "IGDB_USE_PRO_TIER=True in .env"
            ),
        )

    def handle(self, *args, **options):
        """Handle IGDB data fetch using IGDBImportService."""
        game_name = options.get("game")
        game_slug = options.get("slug")
        game_id = options.get("id")
        force = options.get("force", False)
        concurrency = max(1, min(8, options.get("concurrency", 8)))
        use_pro_tier = options.get("pro", False)
        batch_games_option = options.get("batch_games")
        batch_size = options.get("batch_size", 50)

        # Handle single game update
        if game_name or game_slug or game_id:
            return self._handle_single_game(game_name, game_slug, game_id, force)

        # Handle batch update
        if force:
            games = Game.objects.exclude(igdb_id__isnull=True)
        else:
            games = Game.objects.filter(primary_igdb_game_data__isnull=True)

        total_games = games.count()

        if total_games == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No games to fetch. All games already have IGDB data."
                )
            )
            return

        # Initialize progress callback
        self.batch_processed = 0
        self.start_time = time.time()

        def progress_callback(event_type: str, data: dict) -> None:
            """Handle progress events from service."""
            if event_type == "progress":
                self._handle_progress_event(data, total_games)
            elif event_type == "error":
                self._handle_error_event(data)
            elif event_type == "complete":
                self._handle_complete_event(data, total_games)

        # Create service with configured optimizations
        try:
            service = IGDBImportService(
                concurrency=concurrency,
                batch_size=batch_games_option,
                use_pro_tier=use_pro_tier,
                progress_callback=progress_callback,
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
        mode_desc.append(f"checkpoint_size={batch_size}")

        self.stdout.write(f"Processing {total_games} games ({', '.join(mode_desc)})")

        # Run the import
        service.import_games(games)

    def _handle_single_game(self, game_name, game_slug, game_id, force):
        """Handle updating a single game."""
        try:
            if game_id:
                game = Game.objects.get(id=game_id)
            elif game_slug:
                game = Game.objects.get(slug=game_slug)
            elif game_name:
                game = Game.objects.get(name__iexact=game_name)

            self.stdout.write(f"Updating game: {game.rank}. {game.name}")

            if not game.igdb_id:
                self.stdout.write(
                    self.style.ERROR(
                        f"Game '{game.name}' has no IGDB ID. Cannot fetch data."
                    )
                )
                return

            if game.primary_igdb_game_data and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Game '{game.name}' already has IGDB data. "
                        "Use --force to refresh."
                    )
                )
                return

            game.get_igdb_data()
            game.save(update_fields=["slug", "description"])
            self.stdout.write(self.style.SUCCESS(f"Successfully updated '{game.name}'"))

        except Game.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"Game not found with "
                    f"{'id=' + str(game_id) if game_id else ''}"
                    f"{'slug=' + game_slug if game_slug else ''}"
                    f"{'name=' + game_name if game_name else ''}"
                )
            )
        except Game.MultipleObjectsReturned:
            self.stdout.write(
                self.style.ERROR(
                    f"Multiple games found matching '{game_name}'. "
                    "Please use --slug or --id instead."
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error updating game: {str(e)}"))

    def _handle_progress_event(self, data: dict, total_games: int) -> None:
        """Handle progress event from service."""
        current = data.get("current", 0)
        game_name = data.get("game_name", "")

        self.stdout.write(f"[{current}/{total_games}] {game_name}")

        self.batch_processed += 1

        # Checkpoint every batch_size games (progress output only)
        if self.batch_processed >= 50:  # pragma: no cover
            elapsed = time.time() - self.start_time
            rate = current / elapsed if elapsed > 0 else 0
            remaining = total_games - current
            eta = remaining / rate if rate > 0 else 0
            self.stdout.write(
                self.style.SUCCESS(
                    f"Checkpoint: {current}/{total_games} processed "
                    f"({rate:.2f} games/sec, ~{eta:.0f}s remaining)"
                )
            )
            self.batch_processed = 0

    def _handle_error_event(self, data: dict) -> None:
        """Handle error event from service."""
        game_name = data.get("game_name", "Unknown")
        message = data.get("message", "Unknown error")

        self.stdout.write(self.style.ERROR(f"{game_name}: {message}"))

    def _handle_complete_event(self, data: dict, total_games: int) -> None:
        """Handle completion event from service."""
        processed = data.get("processed", 0)
        errors = data.get("errors", 0)
        elapsed = data.get("elapsed_seconds", 0)

        rate = processed / elapsed if elapsed > 0 else 0

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted: {processed}/{total_games} games "
                f"processed successfully ({errors} errors) "
                f"in {elapsed}s ({rate:.2f} games/sec)"
            )
        )
