import logging
import time

from django.core.management.base import BaseCommand

from games.models import Game

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh IGDB data for games with missing developer information"

    def add_arguments(self, parser):
        parser.add_argument(
            "--game-id",
            type=int,
            help="Refresh IGDB data for a specific game ID",
        )
        parser.add_argument(
            "--game-slug",
            type=str,
            help="Refresh IGDB data for a specific game slug",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Refresh IGDB data for all games regardless of developer data",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Delay in seconds between processing games (default: 0.5s). "
            "Helps avoid rate limiting. Set to 0 to disable.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of games to process before a longer pause (default: 50). "
            "Helps with memory management and provides progress checkpoints.",
        )

    def handle(self, *args, **kwargs):
        game_id = kwargs.get("game_id")
        game_slug = kwargs.get("game_slug")
        refresh_all = kwargs.get("all", False)
        delay = kwargs.get("delay", 0.5)
        batch_size = kwargs.get("batch_size", 50)

        # Determine which games to refresh
        if game_id:
            games = Game.objects.filter(id=game_id)
            if not games.exists():
                self.stdout.write(self.style.ERROR(f"No game found with ID {game_id}"))
                return
        elif game_slug:
            games = Game.objects.filter(slug=game_slug)
            if not games.exists():
                self.stdout.write(
                    self.style.ERROR(f"No game found with slug {game_slug}")
                )
                return
        elif refresh_all:
            # Refresh all games with IGDB IDs
            games = Game.objects.filter(igdb_id__isnull=False)
        else:
            # Find games with IGDB IDs but missing developer IGDB data
            games = (
                Game.objects.filter(igdb_id__isnull=False)
                .exclude(developers__igdb_id__isnull=False)
                .distinct()
            )

        total = games.count()
        self.stdout.write(self.style.SUCCESS(f"Found {total} games to refresh"))

        # Warning about cache bypass
        if total > 0 and refresh_all:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  WARNING: Using --all flag with cache_results=False. "
                    "This disables caching and makes MORE API calls per game. "
                    "Recommend using extended delay (e.g., --delay 1.0)"
                )
            )

        if total == 0:
            self.stdout.write(self.style.WARNING("No games to refresh."))
            return

        self.stdout.write(
            f"Processing {total} games (delay={delay}s, batch_size={batch_size})"
        )

        success_count = 0
        error_count = 0
        batch_processed = 0
        start_time = time.time()

        for i, game in enumerate(games, 1):
            try:
                game.get_igdb_data(cache_results=False)
                game.save()

                # Check if developers were added
                dev_count = game.developers.filter(igdb_id__isnull=False).count()

                status = f"{game.rank} - {game}"
                if dev_count > 0:
                    status += f" ({dev_count} developers with IGDB data)"

                self.stdout.write(f"[{i}/{total}] {status}")
                success_count += 1
                batch_processed += 1

                # Batch checkpoint
                if batch_processed >= batch_size:
                    elapsed = time.time() - start_time
                    rate = success_count / elapsed if elapsed > 0 else 0
                    remaining = total - i
                    eta = remaining / rate if rate > 0 else 0
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Batch complete: {success_count}/{total} processed "
                            f"({rate:.2f} games/sec, ~{eta:.0f}s remaining)"
                        )
                    )
                    batch_processed = 0

                # Delay between games to respect rate limiting
                if delay > 0:
                    time.sleep(delay)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"[{i}/{total}] {game.rank} - {game}: {str(e)}")
                )
                error_count += 1
                logger.error(f"{game.rank} - {game}: {str(e)}")

                # Still apply delay on error
                if delay > 0:
                    time.sleep(delay)

        elapsed = time.time() - start_time
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {success_count} successful, {error_count} failed "
                f"in {elapsed:.1f}s"
            )
        )
