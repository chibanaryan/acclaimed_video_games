import logging
import time

from django.core.management.base import BaseCommand

from games.models import Game

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch game data from IGDB"

    def add_arguments(self, parser):
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

    def handle(self, *args, **options):
        delay = options.get("delay", 0.5)
        batch_size = options.get("batch_size", 50)

        games = Game.objects.filter(igdb_artwork_id__isnull=True)
        total_games = games.count()

        if total_games == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No games to fetch. All games already have IGDB data."
                )
            )
            return

        self.stdout.write(
            f"Processing {total_games} games (delay={delay}s, batch_size={batch_size})"
        )

        processed = 0
        batch_processed = 0
        start_time = time.time()

        for idx, game in enumerate(games, 1):
            try:
                game.get_igdb_data()
                game.save()
                processed += 1
                batch_processed += 1

                # Progress output
                self.stdout.write(f"[{idx}/{total_games}] {game.rank} - {game} updated")

                # Batch checkpoint
                if batch_processed >= batch_size:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = total_games - idx
                    eta = remaining / rate if rate > 0 else 0
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Batch complete: {processed}/{total_games} processed "
                            f"({rate:.2f} games/sec, ~{eta:.0f}s remaining)"
                        )
                    )
                    batch_processed = 0

                # Delay between games to respect rate limiting
                if delay > 0:
                    time.sleep(delay)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{idx}/{total_games}] {game.rank} - {game}: {str(e)}"
                    )
                )

        elapsed = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted: {processed}/{total_games} games "
                f"processed in {elapsed:.1f}s"
            )
        )
